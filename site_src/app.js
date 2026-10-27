/* NBA Player Podcasts: sort the leaderboard, filter Most watched by show.
   Every number is already in the HTML; this only reorders and hides rows. */
(function () {
  'use strict';
  function num(el, key) {
    var v = el.getAttribute('data-' + key);
    var n = parseFloat(v);
    return isNaN(n) ? String(v || '') : n;
  }
  function sortBy(key, dir) {
    var tbody = document.querySelector('#lb tbody');
    var cards = document.getElementById('lb-cards');
    var cmp = function (a, b) {
      var x = num(a, key), y = num(b, key);
      var r = (typeof x === 'string' || typeof y === 'string') ? String(x).localeCompare(String(y)) : x - y;
      if (r === 0) r = num(a, 'rank') - num(b, 'rank');
      return dir === 'asc' ? r : -r;
    };
    if (tbody) Array.prototype.slice.call(tbody.rows).sort(cmp).forEach(function (r) { tbody.appendChild(r); });
    if (cards) Array.prototype.slice.call(cards.children).sort(cmp).forEach(function (c) { cards.appendChild(c); });
    document.querySelectorAll('#lb th.sortable').forEach(function (th) {
      th.classList.toggle('sorted-by', th.getAttribute('data-sort') === key);
    });
    var sel = document.getElementById('lb-sort');
    if (sel) sel.value = key + ':' + dir;
  }
  var lb = document.getElementById('lb');
  if (lb) {
    var cur = { key: 'rank', dir: 'asc' };
    lb.querySelector('thead').addEventListener('click', function (e) {
      var th = e.target.closest('th.sortable');
      if (!th) return;
      var key = th.getAttribute('data-sort');
      var dir = cur.key === key ? (cur.dir === 'asc' ? 'desc' : 'asc') : th.getAttribute('data-dir');
      cur = { key: key, dir: dir };
      sortBy(key, dir);
    });
    var sel = document.getElementById('lb-sort');
    if (sel) {
      sel.value = 'rank:asc';
      sel.addEventListener('change', function () {
        var p = sel.value.split(':');
        cur = { key: p[0], dir: p[1] };
        sortBy(p[0], p[1]);
      });
    }
  }
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
    f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(id) + '?autoplay=1&rel=0';
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

/* Latest videos: tabs, filters, search and "Load more". The first cards are
   in the page; more come in chunks of 24. Filters and search load one index
   file the first time they are used. */
(function () {
  'use strict';
  var root = document.querySelector('.stream');
  if (!root) return;
  var B = root.getAttribute('data-base');
  var grid = root.querySelector('.stream-grid');
  var more = root.querySelector('.loadmore');
  var count = root.querySelector('.stream-count');
  var meta = null, index = null, tab = 'latest', loaded = 0, chunkNo = 0, list = null, shown = 0;
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
    var gain = (tab === 'trending' && r[7] != null) ? ' · <span class="gain">+' + n(r[7]) + ' in 24h</span>' : '';
    return '<article class="vc">' + media + '<div class="vc-body"><div class="vc-top"><span class="fmt fmt-' + esc(r[2]) + '">' + (FMT[r[2]] || 'Video') + '</span></div>' +
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
  function active(f) { return f.q || f.show || f.host || f.fmt || f.days !== 90; }
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
      return get(B + '/data/stream-' + tab + '-' + chunkNo + '.json' + v()).then(function (rows) {
        // The page already shows the first cards of the Latest tab.
        if (!reset && chunkNo === 0 && tab === 'latest') rows = rows.slice(meta.first || 12);
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
      return index ? index : get(B + '/data/stream-index.json' + v()).then(function (x) { index = x; return x; });
    }).then(function (rows) {
      var cut = Date.now() - f.days * 86400000;
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
        return !(tab === 'trending' && r[7] == null);
      });
      if (tab === 'views') list.sort(function (a, b) { return b[4] - a[4]; });
      else if (tab === 'trending') list.sort(function (a, b) { return b[7] - a[7]; });
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
