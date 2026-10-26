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
