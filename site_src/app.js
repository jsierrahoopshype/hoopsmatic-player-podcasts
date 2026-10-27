/* NBA Player Podcasts: sort the rankings (and switch their format), filter
   Most watched by show. The numbers for every format are in the HTML; this
   only swaps, reorders and hides them. */
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

/* Video cards: a click on the thumbnail loads YouTube's player
   (youtube-nocookie.com) for that one video, only then. Nothing from YouTube
   loads before. Without this script the thumbnail is a plain YouTube link. */
(function () {
  'use strict';
  function play(a) {
    var id = a.getAttribute('data-play');
    var f = document.createElement('iframe');
    var start = parseInt(a.getAttribute('data-start') || '0', 10);
    f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(id) + '?autoplay=1&rel=0' + (start > 0 ? '&start=' + start : '');
    f.title = a.getAttribute('aria-label') || 'YouTube video';
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.loading = 'eager';
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    var box = document.createElement('div');
    box.className = 'vc-media vc-player';
    box.appendChild(f);
    a.parentNode.replaceChild(box, a);
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-play]');
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    play(a);
  });
})();

/* Video lists (Latest videos on the homepage, Top videos): tabs, filters,
   search and "Load more". The first cards are in the page; more come in
   chunks of 24. Filters and search load one index file the first time they
   are used. */
(function () {
  'use strict';
  var root = document.querySelector('.stream');
  if (!root) return;
  var B = root.getAttribute('data-base');
  var PREFIX = root.getAttribute('data-prefix') || 'stream';
  var FIRST_TAB = root.getAttribute('data-first-tab') || 'latest';
  var RANGE0 = +(root.getAttribute('data-range') || 90);
  var grid = root.querySelector('.stream-grid');
  var more = root.querySelector('.loadmore');
  var count = root.querySelector('.stream-count');
  var meta = null, index = null, tab = FIRST_TAB, loaded = 0, chunkNo = 0, list = null, shown = 0;
  var FMT = { full: 'Full episode', clip: 'Clip', short: 'Short', unknown: 'Video' };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); }
  function n(x) { return Number(x).toLocaleString('en-US'); }
  function dur(s) { if (!s) return ''; var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') + m : m) + ':' + (x < 10 ? '0' : '') + x; }
  function date(iso) { var d = new Date(iso); return MON[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear(); }
  function initials(name) { var p = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase(); }
  function card(r) {
    var show = meta.shows[r[1]], id = r[0], yt = 'https://www.youtube.com/watch?v=' + encodeURIComponent(id);
    var img = r[10] ? '<img src="' + B + '/thumbs/' + esc(id) + '.webp" width="320" height="180" loading="lazy" alt="">' : '<span class="vc-noimg"></span>';
    var d = r[5] ? '<span class="vc-dur">' + dur(r[5]) + '</span>' : '';
    var media = r[9] ? '<a class="vc-media" href="' + yt + '" target="_blank" rel="noopener" data-play="' + esc(id) + '" aria-label="Play: ' + esc(r[6]) + '">' + img + '<span class="vc-btn" aria-hidden="true"></span>' + d + '</a>'
      : '<a class="vc-media vc-noembed" href="' + yt + '" target="_blank" rel="noopener">' + img + '<span class="vc-ext">Watch on YouTube</span>' + d + '</a>';
    var hosts = show[2].map(function (h) {
      var face = h[2] ? '<img class="av" src="' + B + '/headshots/' + esc(h[2]) + '.webp" width="22" height="22" loading="lazy" alt="">' : '<span class="av av-i" aria-hidden="true">' + esc(initials(h[0])) + '</span>';
      return h[1] ? '<a class="host" href="' + esc(h[1]) + '">' + face + esc(h[0]) + '</a>' : '<span class="host">' + face + esc(h[0]) + '</span>';
    }).join('');
    var gain = (tab === 'trending' && r[7] != null) ? ' · <span class="gain">+' + n(r[7]) + ' in 24h</span>'
      : (tab === 'gain7' && r[11] != null) ? ' · <span class="gain">+' + n(r[11]) + ' in 7 days</span>' : '';
    var bo = (tab === 'breakout' && r[8] != null) ? '<span class="bo' + (r[8] >= 5 ? ' hot' : '') + '">' + r[8].toFixed(1) + 'x</span>' : '';
    return '<article class="vc">' + media + '<div class="vc-body"><div class="vc-top"><span class="fmt fmt-' + esc(r[2]) + '">' + (FMT[r[2]] || 'Video') + '</span>' + bo + '</div>' +
      '<h3 class="vc-t"><a href="' + yt + '" target="_blank" rel="noopener">' + esc(r[6]) + '</a></h3>' +
      '<div class="vc-show"><a href="' + B + '/' + esc(show[0]) + '/">' + esc(show[1]) + '</a></div>' +
      '<div class="vc-hosts">' + hosts + '</div><div class="vc-meta">' + date(r[3]) + ' · ' + n(r[4]) + ' views' + gain + '</div>' +
      '<a class="vc-yt" href="' + yt + '" target="_blank" rel="noopener">Watch on YouTube</a></div></article>';
  }
  function get(url) { return fetch(url, { credentials: 'omit' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function loadMeta() { return meta ? Promise.resolve(meta) : get(root.getAttribute('data-meta')).then(function (m) { meta = m; return m; }); }
  function v() { return '?v=' + meta.v; }
  function filters() {
    return { q: root.querySelector('#sf-q').value.trim().toLowerCase(), show: root.querySelector('#sf-show').value,
      host: root.querySelector('#sf-host').value, fmt: root.querySelector('#sf-fmt').value, days: +root.querySelector('#sf-range').value };
  }
  function active(f) { return f.q || f.show || f.host || f.fmt || f.days !== RANGE0; }
  function render(rows, append) {
    var html = rows.map(card).join('');
    if (append) grid.insertAdjacentHTML('beforeend', html); else grid.innerHTML = html;
  }
  function setMore(on) { more.hidden = !on; }
  // Unfiltered: chunks for the chosen tab.
  function nextChunk(reset) {
    return loadMeta().then(function () {
      if (reset) { chunkNo = 0; grid.innerHTML = ''; }
      if (chunkNo >= (meta.tabs[tab] || 0)) { setMore(false); return; }
      return get(B + '/data/' + PREFIX + '-' + tab + '-' + chunkNo + '.json' + v()).then(function (rows) {
        // The page already shows the first cards of the first tab.
        if (!reset && chunkNo === 0 && tab === FIRST_TAB) rows = rows.slice(meta.first || 12);
        chunkNo++;
        render(rows, !reset);
        setMore(chunkNo < meta.tabs[tab]);
        count.textContent = '';
      });
    });
  }
  // Filtered or searched: one index, filtered here, shown 24 at a time.
  function applyFilters() {
    var f = filters();
    if (!active(f)) { list = null; return nextChunk(true); }
    return loadMeta().then(function () {
      return index ? index : get(B + '/data/' + PREFIX + '-index.json' + v()).then(function (x) { index = x; return x; });
    }).then(function (rows) {
      var cut = f.days ? Date.now() - f.days * 86400000 : -Infinity;
      list = rows.filter(function (r) {
        var show = meta.shows[r[1]];
        if (f.show && show[0] !== f.show) return false;
        if (f.fmt && r[2] !== f.fmt) return false;
        if (f.host && !show[2].some(function (h) { return h[0] === f.host; })) return false;
        if (new Date(r[3]).getTime() < cut) return false;
        if (f.q) {
          var hay = (r[6] + ' ' + show[1] + ' ' + show[2].map(function (h) { return h[0]; }).join(' ')).toLowerCase();
          if (hay.indexOf(f.q) === -1) return false;
        }
        return !((tab === 'trending' && r[7] == null) || (tab === 'gain7' && r[11] == null) || (tab === 'breakout' && r[8] == null));
      });
      if (tab === 'views') list.sort(function (a, b) { return b[4] - a[4]; });
      else if (tab === 'trending') list.sort(function (a, b) { return b[7] - a[7]; });
      else if (tab === 'gain7') list.sort(function (a, b) { return b[11] - a[11]; });
      else if (tab === 'breakout') list.sort(function (a, b) { return b[8] - a[8]; });
      else list.sort(function (a, b) { return a[3] < b[3] ? 1 : a[3] > b[3] ? -1 : 0; });
      // Older than the last 90 days, the Top videos file holds only each
      // show's top videos of each format and the overall top: show no more
      // than those are sure to cover.
      if (meta.alltime && (!f.days || f.days > meta.recent_days)) {
        list = list.slice(0, (f.show || f.host) ? meta.alltime.show : meta.alltime.all);
      }
      shown = 0;
      grid.innerHTML = '';
      showMore();
      count.textContent = list.length === 1 ? '1 video' : n(list.length) + ' videos';
    });
  }
  function showMore() {
    var page = list.slice(shown, shown + (meta.chunk || 24));
    shown += page.length;
    render(page, true);
    setMore(shown < list.length);
    if (!list.length) grid.innerHTML = '<div class="empty">No videos match.</div>';
  }
  more.addEventListener('click', function () {
    more.disabled = true;
    Promise.resolve(list ? showMore() : nextChunk(false)).then(function () { more.disabled = false; }, function () { more.disabled = false; });
  });
  root.querySelector('.stream-tabs').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-tab]');
    if (!b) return;
    tab = b.getAttribute('data-tab');
    root.querySelectorAll('.stream-tabs button').forEach(function (x) { x.classList.toggle('active', x === b); });
    applyFilters();
  });
  var t = null;
  root.querySelector('#sf-q').addEventListener('input', function () { clearTimeout(t); t = setTimeout(applyFilters, 250); });
  ['#sf-show', '#sf-host', '#sf-fmt', '#sf-range'].forEach(function (s) { root.querySelector(s).addEventListener('change', applyFilters); });
})();

/* Player pages: filter the cards by role, show and format. Every card is in
   the page already; this only hides the ones that do not match. */
(function () {
  'use strict';
  var bar = document.querySelector('.pfilter');
  if (!bar) return;
  var grid = document.querySelector(bar.getAttribute('data-target'));
  var count = document.querySelector('.pf-count');
  var sels = bar.querySelectorAll('select[data-attr]');
  function apply() {
    var want = {};
    sels.forEach(function (s) { if (s.value) want[s.getAttribute('data-attr')] = s.value; });
    var shown = 0, cards = grid.querySelectorAll('.vc');
    cards.forEach(function (c) {
      var on = Object.keys(want).every(function (k) { return c.getAttribute('data-' + k) === want[k]; });
      c.hidden = !on;
      if (on) shown++;
    });
    count.textContent = shown === cards.length ? '' : (shown === 1 ? '1 video' : shown + ' videos');
  }
  sels.forEach(function (s) { s.addEventListener('change', apply); });
})();

/* Homepage "Most talked about": switch between the 7-day and 30-day lists
   (both are in the page). */
(function () {
  'use strict';
  var bar = document.querySelector('.talk-toggle');
  if (!bar) return;
  bar.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-days]');
    if (!b) return;
    var d = b.getAttribute('data-days');
    bar.querySelectorAll('button').forEach(function (x) { x.classList.toggle('active', x === b); });
    document.querySelectorAll('.talk-pane').forEach(function (p) { p.hidden = p.getAttribute('data-days') !== d; });
    var h = bar.closest('section').querySelector('h2');
    if (h) h.textContent = d === '7' ? 'Most talked about this week' : 'Most talked about in the last 30 days';
  });
})();
