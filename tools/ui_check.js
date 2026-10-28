// UI check for the built or live site: node tools/ui_check.js [base URL]
// (default http://localhost:8000/player-podcasts/, e.g. after
// `cd site/.. && python -m http.server` with site/ served as player-podcasts/).
// Needs Playwright. For each page at 1280, 375 and 320 px wide it checks: no
// sideways scroll, and at 375 and 320 no element that scrolls sideways (no
// carousels), one H1, a hoopsmatic.com canonical and og:url, the contact
// footer, no script errors, and that nothing loads from YouTube before a play
// button is pressed. At 375 it presses play on two videos: exactly one
// youtube-nocookie.com player must be loaded afterwards; "Load more" must add
// cards; and the homepage feed must have at least 12 cards and a module card
// in the HTML.
const { chromium } = require('playwright');
const base = (process.argv[2] || 'http://localhost:8000/player-podcasts/').replace(/\/?$/, '/');
const paths = ['', 'top-videos/', 'players/', 'teams/', 'methodology/', 'most-watched/', 'player-channels/', 'dormant/'];
(async () => {
  const b = await chromium.launch();
  let fail = 0;
  const first = await b.newPage();
  await first.goto(base, { waitUntil: 'networkidle' });
  const show = await first.$eval('#lb tbody tr td.name a', a => a.getAttribute('href'));
  const player = await first.$eval('a.host[href*="/players/"]', a => a.getAttribute('href')).catch(() => null);
  const html = await first.evaluate(() => ({
    cards: document.querySelectorAll('.feed .feed-list > .vc').length,
    mod: !!document.querySelector('.feed .feed-list > .vc-mod'),
  }));
  await first.goto(base + 'teams/', { waitUntil: 'networkidle' });
  const team = await first.$eval('ul.players a.pl', a => a.getAttribute('href')).catch(() => null);
  await first.close();
  if (html.cards < 12 || !html.mod) { console.log('FAIL homepage feed in the HTML: ' + html.cards + ' cards, module: ' + html.mod); fail++; }
  const all = paths.map(p => base + p).concat([new URL(show, base).href]).concat(player ? [new URL(player, base).href] : [])
    .concat(team ? [new URL(team, base).href] : []);
  for (const url of all) {
    for (const w of [1280, 375, 320]) {
      const p = await b.newPage({ viewport: { width: w, height: 900 } });
      const errs = [], yt = [];
      p.on('pageerror', e => errs.push(e.message));
      p.on('request', r => { if (/youtube\.com|ytimg\.com|googlevideo/.test(r.url())) yt.push(r.url()); });
      await p.goto(url, { waitUntil: 'networkidle' });
      const r = await p.evaluate(() => ({
        sideways: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        h1: document.querySelectorAll('h1').length,
        canon: (document.querySelector('link[rel=canonical]') || {}).href || '',
        og: (document.querySelector('meta[property="og:url"]') || {}).content || '',
        foot: !!document.querySelector('.site-foot') && document.querySelector('.site-foot').innerText.includes('ads@hoopsmatic.com'),
      }));
      const problems = [];
      if (r.sideways) problems.push('sideways scroll');
      if (r.h1 !== 1) problems.push(r.h1 + ' H1s');
      if (!r.canon.startsWith('https://hoopsmatic.com/') || !r.og.startsWith('https://hoopsmatic.com/')) problems.push('canonical/og:url');
      if (!r.foot) problems.push('footer');
      if (errs.length) problems.push('errors: ' + errs.join('; '));
      if (yt.length) problems.push('YouTube loaded before play: ' + yt[0]);
      if (w < 1000) {
        // Anything that scrolls sideways inside the page (a carousel, a wide table).
        const scrollers = await p.evaluate(() => Array.prototype.filter.call(document.querySelectorAll('main *, .container *'), el => {
          const ox = getComputedStyle(el).overflowX;
          return (ox === 'auto' || ox === 'scroll') && el.scrollWidth > el.clientWidth + 1;
        }).map(el => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')));
        if (scrollers.length) problems.push('scrolls sideways: ' + scrollers.slice(0, 3).join(', '));
      }
      if (w === 375) {
        const more = await p.$('.feed .loadmore:not([hidden])');
        if (more) {
          const n0 = await p.$$eval('.feed-list > .vc', x => x.length);
          await more.click();
          await p.waitForTimeout(1500);
          const n1 = await p.$$eval('.feed-list > .vc', x => x.length);
          if (n1 <= n0) problems.push('Load more added no cards');
        }
        const plays = await p.$$('.vc a.vc-media[data-play]');
        if (plays.length >= 2) {
          await plays[0].click();
          await p.waitForTimeout(800);
          await plays[1].click();
          await p.waitForTimeout(800);
          const n = await p.$$eval('iframe[src*="youtube-nocookie.com/embed/"]', f => f.length);
          if (n !== 1) problems.push(n + ' YouTube players after two plays (want 1)');
        } else if (plays.length) {
          await plays[0].click();
          await p.waitForTimeout(800);
          const src = await p.$eval('iframe[src*="youtube-nocookie.com/embed/"]', f => f.src).catch(() => null);
          if (!src) problems.push('no youtube-nocookie player after play');
        }
      }
      console.log((problems.length ? 'FAIL ' : 'ok   ') + w + ' ' + url + (problems.length ? ': ' + problems.join(', ') : ''));
      fail += problems.length ? 1 : 0;
      await p.close();
    }
  }
  await b.close();
  process.exit(fail ? 1 : 0);
})();
