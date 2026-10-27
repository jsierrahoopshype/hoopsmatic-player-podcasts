// UI check for the built or live site: node tools/ui_check.js [base URL]
// (default http://localhost:8000/player-podcasts/, e.g. after
// `cd site/.. && python -m http.server` with site/ served as player-podcasts/).
// Needs Playwright. For each page at 1280, 375 and 320 px wide it checks: no
// sideways scroll, one H1, a hoopsmatic.com canonical and og:url, the contact
// footer, no script errors, and that nothing loads from YouTube before a play
// button is pressed (and the youtube-nocookie.com player after it).
const { chromium } = require('playwright');
const base = (process.argv[2] || 'http://localhost:8000/player-podcasts/').replace(/\/?$/, '/');
const paths = ['', 'top-videos/', 'players/', 'methodology/', 'most-watched/', 'player-channels/', 'dormant/'];
(async () => {
  const b = await chromium.launch();
  let fail = 0;
  const first = await b.newPage();
  await first.goto(base, { waitUntil: 'networkidle' });
  const show = await first.$eval('#lb tbody tr td.name a', a => a.getAttribute('href'));
  const player = await first.$eval('a.host[href*="/players/"]', a => a.getAttribute('href')).catch(() => null);
  await first.close();
  const all = paths.map(p => base + p).concat([new URL(show, base).href]).concat(player ? [new URL(player, base).href] : []);
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
      if (w === 375 && await p.$('a[data-play]')) {
        await p.click('a[data-play]');
        await p.waitForTimeout(800);
        const src = await p.$eval('iframe[src*="youtube-nocookie.com/embed/"]', f => f.src).catch(() => null);
        if (!src) problems.push('no youtube-nocookie player after play');
      }
      console.log((problems.length ? 'FAIL ' : 'ok   ') + w + ' ' + url + (problems.length ? ': ' + problems.join(', ') : ''));
      fail += problems.length ? 1 : 0;
      await p.close();
    }
  }
  await b.close();
  process.exit(fail ? 1 : 0);
})();
