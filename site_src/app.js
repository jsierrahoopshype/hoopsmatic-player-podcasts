/* NBA Player Podcasts: sort the rankings (and switch their format) and
   filter Most watched by show. The numbers for every format are in the HTML;
   this only swaps, reorders and hides them. The video player and the video
   feeds are further down. */
(function () {
  'use strict';
  // Same rounding as the build (pp/render.py compact / signed / pct).
  function compact(n) {
    var a = Math.abs(n), s;
    if (a >= 1e9) s = (n / 1e9).toFixed(2) + 'B';
    else if (a >= 1e6) s = (n / 1e6).toFixed(a < 1e7 ? 2 : 1) + 'M';
    else if (a >= 1e3) s = (n / 1e3).toFixed(a < 1e5 ? 1 : 0) + 'K';
    else return String(Math.round(n));
    return s.replace('.00M', 'M').replace('.0K', 'K').replace('.0M', 'M');
  }
  function signed(n) { return n ? (n > 0 ? '+' : '') + compact(n) : '0'; }
  function pct(p) { return (p >= 0 ? '+' : '') + p.toFixed(1) + '%'; }
  var FIXED = { typf: 1, typc: 1, subs: 1, subg: 1 };
  var ND = '<span class="nd">no data</span>';
  function based(n) { return n + ' video' + (n === 1 ? '' : 's'); }
  // [sort value, html] for one metric, as the build writes it.
  function cell(key, pair, shared) {
    var v = pair[0], n = pair[1];
    if (key === 'subs' && shared) return [-1, '<span class="nd">shared channel</span>'];
    if (v == null) return ['', ND];
    if (key === 'subg') return [v, signed(v) + (n != null ? ' <span class="pc">' + pct(n) + '</span>' : '')];
    if (key === 'subs') return [v, compact(v)];
    if (key === 'vids') return [v, String(v)];
    var txt = key === 'likes' ? v.toFixed(1) : (key === 'g7' || key === 'g30') ? (v ? '+' + compact(v) : '0') : compact(v);
    return [v, txt + '<span class="bn">' + based(n) + '</span>'];
  }
  var lb = document.getElementById('lb');
  if (!lb) return;
  var tools = document.querySelector('.lb-tools');
  var defs = JSON.parse(tools.getAttribute('data-defs') || '{}');
  var defEl = document.getElementById('lb-def');
  var sel = document.getElementById('lb-sort'), fmtSel = document.getElementById('lb-fmt');
  var tbody = lb.querySelector('tbody'), cards = document.getElementById('lb-cards');
  var labels = {};
  lb.querySelectorAll('th[data-sort]').forEach(function (th) { labels[th.getAttribute('data-sort')] = th.textContent; });
  var cur = { key: 'rank', dir: 'asc' }, fmt = 'full';
  function pair(el, key) {
    var m = el._m || (el._m = JSON.parse(el.getAttribute('data-m')));
    return (FIXED[key] ? m.x : m[fmt])[key];
  }
  function val(el, key) {
    var v = el.getAttribute('data-' + key);
    if (v === '' || v == null) return null;
    var n = parseFloat(v);
    return isNaN(n) ? v : n;
  }
  // Phone cards: the big number is the metric sorted by (30-day views for rank and name).
  function headline(c) {
    var key = (cur.key in labels && !(cur.key in { rank: 1, name: 1, chg: 1 })) ? cur.key : 'v30';
    var p = pair(c, key), r = cell(key, p, c.hasAttribute('data-shared'));
    var big = c.querySelector('.now .p'), lbl = c.querySelector('.now .lbl'), bn = c.querySelector('.now .bn');
    var tmp = document.createElement('span');
    tmp.innerHTML = r[1];
    var sub = tmp.querySelector('.bn');
    if (sub) sub.parentNode.removeChild(sub);
    big.innerHTML = tmp.innerHTML;
    lbl.textContent = labels[key] || 'Views, 30 days';
    bn.textContent = (p[0] != null && !(key in { subs: 1, subg: 1, vids: 1 })) ? 'based on ' + based(p[1]) : '';
  }
  function setFormat(f) {
    fmt = f;
    var rows = Array.prototype.slice.call(tbody.rows).concat(Array.prototype.slice.call(cards.children));
    rows.forEach(function (el) {
      Object.keys(labels).forEach(function (key) {
        if (key in { rank: 1, name: 1, chg: 1 }) return;
        var r = cell(key, pair(el, key), el.hasAttribute('data-shared'));
        el.setAttribute('data-' + key, r[0]);
        var td = el.querySelector && el.querySelector('td[data-k="' + key + '"]');
        if (td) td.innerHTML = r[1];
      });
      var cv = el.querySelector('.cf-vids');
      if (cv) cv.textContent = String(pair(el, 'vids')[0]);
    });
    sortBy(cur.key, cur.dir);
  }
  function sortBy(key, dir) {
    var cmp = function (a, b) {
      var x = val(a, key), y = val(b, key);
      // Rows without a number go last whichever way the sort runs.
      if (x === null || y === null) return x === y ? val(a, 'rank') - val(b, 'rank') : (x === null ? 1 : -1);
      var r = (typeof x === 'string' || typeof y === 'string') ? String(x).localeCompare(String(y)) : x - y;
      if (dir !== 'asc') r = -r;
      return r || val(a, 'rank') - val(b, 'rank');
    };
    Array.prototype.slice.call(tbody.rows).sort(cmp).forEach(function (r) { tbody.appendChild(r); });
    Array.prototype.slice.call(cards.children).sort(cmp).forEach(function (c) { cards.appendChild(c); headline(c); });
    lb.querySelectorAll('th.sortable').forEach(function (th) { th.classList.toggle('sorted-by', th.getAttribute('data-sort') === key); });
    if (sel) sel.value = key + ':' + dir;
    if (defEl) defEl.textContent = defs[key] || defs.rank || '';
  }
  lb.querySelector('thead').addEventListener('click', function (e) {
    var th = e.target.closest('th.sortable');
    if (!th) return;
    var key = th.getAttribute('data-sort');
    var dir = cur.key === key ? (cur.dir === 'asc' ? 'desc' : 'asc') : th.getAttribute('data-dir');
    cur = { key: key, dir: dir };
    sortBy(key, dir);
  });
  sel.value = 'rank:asc';
  sel.addEventListener('change', function () {
    var p = sel.value.split(':');
    cur = { key: p[0], dir: p[1] };
    sortBy(p[0], p[1]);
  });
  fmtSel.value = 'full';
  fmtSel.addEventListener('change', function () { setFormat(fmtSel.value); });
})();

(function () {
  'use strict';
  var mw = document.getElementById('mw-show');
  if (mw) {
    var apply = function () {
      var slug = mw.value;
      document.querySelectorAll('section.mw').forEach(function (sec) {
        var rows = sec.querySelectorAll('.ep');
        var shown = 0, i = 0;
        rows.forEach(function (r) {
          i++;
          var on = slug ? r.getAttribute('data-show') === slug : i <= 25;
          r.hidden = !on;
          if (on) shown++;
          var rk = r.querySelector('.ep-rank');
          if (rk) rk.textContent = on ? String(shown) : '';
        });
        var none = sec.querySelector('.mw-none');
        if (none) none.hidden = shown > 0 || rows.length === 0;
      });
    };
    mw.addEventListener('change', apply);
    if (mw.value) apply();
  }
})();

/* Video cards: a tap on the thumbnail (or the title) loads YouTube's player
   (youtube-nocookie.com) for that one video, in place, only then. Nothing
   from YouTube loads before, and nothing plays on its own. Only one player
   at a time: starting a video puts the previous one back to its thumbnail,
   which unloads it. Without this script the thumbnail is a plain YouTube link. */
(function () {
  'use strict';
  var cur = null;   // { box: the player, a: the thumbnail link it replaced }
  function stop() {
    if (cur && cur.box.parentNode) {
      var mini = cur.box.closest('.mini');
      if (mini) mini.classList.remove('playing');
      cur.box.parentNode.replaceChild(cur.a, cur.box);
    }
    cur = null;
  }
  function play(a) {
    var id = a.getAttribute('data-play');
    var start = parseInt(a.getAttribute('data-start') || '0', 10);
    // A title link plays in its card's thumbnail.
    var media = a.classList.contains('vc-media') ? a : (a.closest('.vc, .mini') || document).querySelector('a.vc-media[data-play]');
    if (!media) return false;
    stop();
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(id) + '?autoplay=1&rel=0' + (start > 0 ? '&start=' + start : '');
    f.title = media.getAttribute('aria-label') || 'YouTube video';
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.loading = 'eager';
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    var box = document.createElement('div');
    box.className = 'vc-media vc-player';
    box.appendChild(f);
    var mini = media.closest('.mini');
    if (mini) mini.classList.add('playing');
    media.parentNode.replaceChild(box, media);
    cur = { box: box, a: media };
    return true;
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-play]');
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.button === 1) return;
    if (play(a)) e.preventDefault();
  });
})();

/* "Most talked about" module: switch between the 7-day and 30-day lists
   (both are in the page). Works for every copy of the module in a feed. */
(function () {
  'use strict';
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.talk-toggle button[data-days]');
    if (!b) return;
    var mod = b.closest('.vc-mod, section');
    var d = b.getAttribute('data-days');
    b.parentNode.querySelectorAll('button').forEach(function (x) { x.classList.toggle('active', x === b); });
    mod.querySelectorAll('.talk-pane').forEach(function (p) { p.hidden = p.getAttribute('data-days') !== d; });
    var h = mod.querySelector('.mod-h, h2');
    if (h) h.textContent = d === '7' ? 'Most talked about this week' : 'Most talked about in the last 30 days';
  });
})();

/* Video feeds (pp/feed.py): chips over a vertical stream of cards (a grid on
   wider screens). The first cards of the default chip are in the page; the
   rest come from data/feed-<id>.json, loaded the first time they are needed.
   Near the bottom the next 12 load on their own (4 times per chip, so the
   rest of the page stays within reach), and "Load more" loads them on a tap.
   Every 8 videos, a module card (talked about, breakouts, rankings), never
   the same one twice in a row. The card here is the same as pp/cards.py. */
(function () {
  'use strict';
  var BATCH = 12, AUTO = 4, EVERY = 8, BREAKOUT_X = 5;
  var FMT = { full: 'Full episode', clip: 'Clip', short: 'Short', unknown: 'Video' };
  var ROLE = { host: 'Host', guest: 'Guest', talk: 'Talked about' };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var YT_ICON = '<svg viewBox="0 0 24 17" width="22" height="16" aria-hidden="true"><rect width="24" height="17" rx="4" fill="#ff0033"/><path d="M9.5 4.5v8l6.5-4z" fill="#fff"/></svg>';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); }
  // Same rounding as pp/render.py compact.
  function compact(n) {
    var a = Math.abs(n), s;
    if (a >= 1e9) s = (n / 1e9).toFixed(2) + 'B';
    else if (a >= 1e6) s = (n / 1e6).toFixed(a < 1e7 ? 2 : 1) + 'M';
    else if (a >= 1e3) s = (n / 1e3).toFixed(a < 1e5 ? 1 : 0) + 'K';
    else return String(Math.round(n));
    return s.replace('.00M', 'M').replace('.0K', 'K').replace('.0M', 'M');
  }
  function dur(s) { if (!s) return ''; var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') + m : m) + ':' + (x < 10 ? '0' : '') + x; }
  function date(iso) { var d = new Date(iso); return MON[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear(); }
  function initials(name) { var p = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase(); }
  function yt(id, t) { return 'https://www.youtube.com/watch?v=' + encodeURIComponent(id) + (t ? '&t=' + t + 's' : ''); }

  function card(B, shows, r, c) {
    var id = r[0], show = shows[r[1]], x = r[12] || {}, t = x.t || null, url = esc(yt(id, t));
    var img = r[10] === 2 ? '<img src="' + B + '/thumbs/v/' + esc(id) + '.webp" width="270" height="480" loading="lazy" alt="">'
      : r[10] ? '<img src="' + B + '/thumbs/' + esc(id) + '.webp" width="320" height="180" loading="lazy" alt="">' : '<span class="vc-noimg"></span>';
    var d = r[5] ? '<span class="vc-dur">' + dur(r[5]) + '</span>' : '';
    var st = t ? ' data-start="' + t + '"' : '';
    var media = r[9] ? '<a class="vc-media" href="' + url + '" target="_blank" rel="noopener" data-play="' + esc(id) + '"' + st + ' aria-label="Play: ' + esc(r[6]) + '">' + img + '<span class="vc-btn" aria-hidden="true"></span>' + d + '</a>'
      : '<a class="vc-media vc-noembed" href="' + url + '" target="_blank" rel="noopener">' + img + '<span class="vc-ext">Watch on YouTube</span>' + d + '</a>';
    var hosts = show[2].map(function (h) {
      var face = h[2] ? '<img class="av" src="' + B + '/headshots/' + esc(h[2]) + '.webp" width="22" height="22" loading="lazy" alt="">' : '<span class="av av-i" aria-hidden="true">' + esc(initials(h[0])) + '</span>';
      return h[1] ? '<a class="host" href="' + esc(h[1]) + '">' + face + esc(h[0]) + '</a>' : '<span class="host">' + face + esc(h[0]) + '</span>';
    }).join('');
    var meta = [date(r[3]), compact(r[4]) + ' views'];
    if (r[5]) meta.push(dur(r[5]));
    if (c.s === 'g24' && r[7] != null) meta.push('<span class="gain">+' + compact(r[7]) + ' in 24h</span>');
    else if (c.s === 'g7' && r[11] != null) meta.push('<span class="gain">+' + compact(r[11]) + ' in 7 days</span>');
    if (t) meta.push('<span class="at">from ' + dur(t) + '</span>');
    var bo = (c.s === 'bo' && r[8] != null) ? '<span class="bo' + (r[8] >= BREAKOUT_X ? ' hot' : '') + '">' + r[8].toFixed(1) + 'x</span>' : '';
    var label = x.l || ROLE[x.r] || '';
    var more = '';
    if (x.c && x.c.length) {
      more = '<div class="vc-more"><span class="lbl">Also from this episode</span><ul>' + x.c.slice(0, 4).map(function (k) {
        return '<li><a href="' + esc(yt(k[0], k[2])) + '" target="_blank" rel="noopener">' + esc(k[1]) + '</a>' + (k[2] ? ' <span class="at">from ' + dur(k[2]) + '</span>' : '') + '</li>';
      }).join('') + '</ul>' + (x.c.length > 4 ? ' <span class="at">and ' + (x.c.length - 4) + ' more</span>' : '') + '</div>';
    }
    return '<article class="vc vc-' + esc(r[2]) + '">' + media + '<div class="vc-body">' +
      '<h3 class="vc-t"><a href="' + url + '" target="_blank" rel="noopener"' + (r[9] ? ' data-play="' + esc(id) + '"' + st : '') + '>' + esc(r[6]) + '</a></h3>' +
      '<div class="vc-show"><a href="' + B + '/' + esc(show[0]) + '/">' + esc(show[1]) + '</a></div>' +
      '<div class="vc-hosts">' + hosts + '</div><div class="vc-meta">' + meta.join(' · ') + '</div>' +
      '<div class="vc-foot"><span class="fmt fmt-' + esc(r[2]) + '">' + (FMT[r[2]] || 'Video') + '</span>' + bo +
      (label ? '<span class="role">' + esc(label) + '</span>' : '') +
      '<a class="vc-ytic" href="' + url + '" target="_blank" rel="noopener" aria-label="Watch on YouTube" title="Watch on YouTube">' + YT_ICON + '</a></div>' +
      more + '</div></article>';
  }

  function key(r, s) {
    if (s === 'pub') return r[3];
    if (s === 'views') return r[4];
    if (s === 'g24') return r[7] || 0;
    if (s === 'g7') return r[11] || 0;
    return r[8] || 0;
  }
  function cmp(s) {
    return function (a, b) {
      var x = key(a, s), y = key(b, s);
      if (x !== y) return x < y ? 1 : -1;
      if (a[3] !== b[3]) return a[3] < b[3] ? 1 : -1;
      return a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0;
    };
  }

  // The sticky chips sit under the site's sticky navigation bar.
  function navOffset() {
    var nav = document.getElementById('hm-nav');
    var h = 0;
    if (nav) { var cs = getComputedStyle(nav); if (cs.position === 'sticky' || cs.position === 'fixed') h = nav.offsetHeight; }
    document.documentElement.style.setProperty('--feed-top', h + 'px');
  }
  navOffset();
  window.addEventListener('resize', navOffset);

  document.querySelectorAll('section.feed').forEach(function (root) {
    var B = root.getAttribute('data-base');
    var chips = JSON.parse(root.getAttribute('data-chips') || '[]');
    var byKey = {};
    chips.forEach(function (c) { byKey[c.k] = c; });
    var chip = byKey[root.getAttribute('data-default')] || chips[0];
    var list = root.querySelector('.feed-list');
    var more = root.querySelector('.loadmore');
    var note = root.querySelector('.feed-note');
    var endEl = root.querySelector('.feed-end');
    var sentinel = root.querySelector('.feed-sentinel');
    var tpl = root.querySelector('template.feed-mods');
    var mods = [];
    if (tpl) Array.prototype.forEach.call(tpl.content.children, function (m) { mods.push(m); });
    var data = null, loading = null;
    var rows = null;                      // the current chip's list (null: not loaded yet)
    var shown = +(root.getAttribute('data-first') || 0);
    var modsIn = list.querySelectorAll('.vc-mod').length, lastMod = modsIn ? mods[0].getAttribute('data-mod') : null;
    var autos = 0, capped = false;
    function load() {
      if (data) return Promise.resolve(data);
      if (!loading) loading = fetch(root.getAttribute('data-src'), { credentials: 'omit' })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { data = d; return d; }, function (err) { loading = null; throw err; });
      return loading;
    }
    function filters() {
      var f = {};
      ['q', 'show', 'host', 'days'].forEach(function (k) {
        var el = root.querySelector('.ff-' + k);
        f[k] = el ? el.value.trim() : '';
      });
      f.q = f.q.toLowerCase();
      return f;
    }
    function active(f) { return !!(f.q || f.show || f.host || f.days); }
    function compute() {
      var f = chip.f || {}, ff = filters(), now = new Date(data.now).getTime();
      var cut = f.days ? now - f.days * 864e5 : -Infinity;
      var cut2 = ff.days ? now - (+ff.days) * 864e5 : -Infinity;
      var out = data.rows.filter(function (r) {
        var x = r[12] || {}, show = data.shows[r[1]], t = new Date(r[3]).getTime();
        if (f.fmt && r[2] !== f.fmt) return false;
        if (t < cut || t < cut2) return false;
        if (f.role && x.r !== f.role) return false;
        if ((f.has === 'g24' && r[7] == null) || (f.has === 'g7' && r[11] == null) || (f.has === 'bo' && r[8] == null)) return false;
        if (ff.show && show[0] !== ff.show) return false;
        if (ff.host && !show[2].some(function (h) { return h[0] === ff.host; })) return false;
        if (ff.q) {
          var hay = (r[6] + ' ' + show[1] + ' ' + show[2].map(function (h) { return h[0]; }).join(' ')).toLowerCase();
          if (hay.indexOf(ff.q) === -1) return false;
        }
        return true;
      });
      out.sort(cmp(chip.s));
      // Top videos: older than the last 90 days, the file holds each show's
      // 12 most viewed of each format; one show (or host) shows no more.
      if (data.alltime && (ff.show || ff.host) && !(ff.days && +ff.days <= data.alltime.days)) out = out.slice(0, data.alltime.show);
      capped = !!data.cap && out.length > data.cap;
      return capped ? out.slice(0, data.cap) : out;
    }
    function nextMod() {
      if (!mods.length) return null;
      var m = mods[modsIn % mods.length];
      if (m.getAttribute('data-mod') === lastMod) return null;   // only one module: show it once
      modsIn++;
      lastMod = m.getAttribute('data-mod');
      return m.cloneNode(true);
    }
    function append(n) {
      var end = Math.min(rows.length, shown + n), frag = document.createDocumentFragment(), tmp = document.createElement('div');
      for (var i = shown; i < end; i++) {
        tmp.innerHTML = card(B, data.shows, rows[i], chip);
        frag.appendChild(tmp.firstChild);
        if ((i + 1) % EVERY === 0 && i + 1 < rows.length) { var m = nextMod(); if (m) frag.appendChild(m); }
      }
      list.appendChild(frag);
      shown = end;
      state();
    }
    function state() {
      var left = rows ? shown < rows.length : !more.hidden;
      more.hidden = !left;
      if (endEl) {
        endEl.hidden = left || !rows || !rows.length;
        var all = endEl.querySelector('.fe-all'), cap = endEl.querySelector('.fe-cap');
        if (cap) { cap.hidden = !capped; all.hidden = capped; }
      }
    }
    function setNote(n) {
      var f = filters();
      note.textContent = chip.note + (rows && active(f) ? ' · ' + (n === 1 ? '1 video matches' : n + ' videos match') : '');
    }
    function reset() {
      return load().then(function () {
        rows = compute();
        list.innerHTML = rows.length ? '' : '<div class="empty">No videos match.</div>';
        shown = 0; modsIn = 0; lastMod = null; autos = 0;
        append(BATCH);
        setNote(rows.length);
      });
    }
    function loadMore() {
      if (rows) { append(BATCH); return Promise.resolve(); }
      // First time: the page shows the first cards of the default chip, unfiltered.
      return load().then(function () { rows = compute(); append(BATCH); });
    }
    root.querySelector('.chips').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-chip]');
      if (!b || b.getAttribute('data-chip') === chip.k) return;
      chip = byKey[b.getAttribute('data-chip')];
      root.querySelectorAll('.chip').forEach(function (x) {
        var on = x === b;
        x.classList.toggle('active', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      note.textContent = chip.note;
      reset().then(function () {
        // Back to the top of the feed when its top is out of view.
        var top = root.getBoundingClientRect().top;
        if (top < 0) root.scrollIntoView({ block: 'start' });
      }, function () { note.textContent = 'Could not load the videos. Try again.'; });
    });
    more.addEventListener('click', function () {
      more.disabled = true;
      loadMore().then(function () { more.disabled = false; }, function () { more.disabled = false; });
    });
    var tq = null;
    root.querySelectorAll('.ff-q').forEach(function (el) { el.addEventListener('input', function () { clearTimeout(tq); tq = setTimeout(reset, 250); }); });
    root.querySelectorAll('.ff-show, .ff-host, .ff-days').forEach(function (el) { el.addEventListener('change', reset); });
    if ('IntersectionObserver' in window && sentinel) {
      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting || more.hidden || more.disabled || autos >= AUTO) return;
        autos++;
        more.disabled = true;
        loadMore().then(function () {
          more.disabled = false;
          // Still near the bottom (short cards): observing again checks once more.
          io.unobserve(sentinel);
          io.observe(sentinel);
        }, function () { more.disabled = false; });
      }, { rootMargin: '0px 0px 600px 0px' });
      io.observe(sentinel);
    }
  });
})();
