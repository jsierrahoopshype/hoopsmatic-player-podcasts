"""Daily and weekly collection. Key-free: public feeds and yt-dlp flat
listings only, nothing is downloaded.

daily():  every source's public feeds (long-form, and Shorts for channels):
          exact views, likes, publish times and descriptions where YouTube
          answers them (from cloud servers it often does not). Then a listing
          of each source's Videos, Live and Shorts tabs back to 90 days
          (rounded views, lengths, dates), so every video of the last 90 days
          gets a view count every day: data/snapshots/daily/<date>.json.
weekly(): full listing of every tab of every source (every upload ever) plus
          subscriber counts: data/snapshots/weekly/<date>.json. Videos a
          complete listing no longer shows are marked gone. Also refreshes
          Career Map's player names and rolls daily files older than 90 days
          into weekly ones. Never raises: a blocked run is recorded in
          data/status.json and the last good data stays.
"""
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from . import catalog, config, feeds, history, roster, ytdlp_fetch
from .util import load_json, save_json, utcnow, today_str, parse_ts, iso

CAREERMAP_NAMES_URL = "https://raw.githubusercontent.com/jsierrahoopshype/nba-career-map/main/data/player_index.json"


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _status():
    return load_json(config.STATUS_FILE, {}) or {}


def _recent(v, now, days):
    p = parse_ts(v.get("published"))
    return p is not None and (now - p).total_seconds() <= days * 86400


def _snapshot_from_catalogs(srcs, day, now, recent_only):
    """Views observed today, per source: {sid: {vid: views}}, plus likes."""
    views, likes = {}, {}
    for sid, src in srcs.items():
        cat = catalog.load(sid, src)
        for vid, v in cat["videos"].items():
            if v.get("gone") or v.get("views") is None or v.get("views_date") != day:
                continue
            if recent_only and not _recent(v, now, config.DAILY_DAYS):
                continue
            views.setdefault(sid, {})[vid] = v["views"]
            if v.get("likes_date") == day and v.get("likes") is not None and v.get("likes_views"):
                likes.setdefault(sid, {})[vid] = [v["likes"], v["likes_views"]]
    return views, likes


# ── listings ──

def _list_tabs(sid, src, cat_videos, now, recent):
    """-> (sid, [(tab, meta, entries, err, stopped)]). recent=True stops each
    tab at 90 days (Shorts: at Shorts we already know that are older or
    undated); recent=False lists every tab to the end."""
    out = []
    for tab, url in ytdlp_fetch.tab_urls(src):
        if not recent:
            stop = None
        elif tab == "shorts":
            stop = ytdlp_fetch.stop_at_known_shorts(cat_videos, config.DAILY_DAYS + 3, now)
        else:
            stop = ytdlp_fetch.stop_past_days(config.DAILY_DAYS + 3)
        meta, entries, err = ytdlp_fetch.list_tab(url, stop=stop)
        stopped = bool(stop and entries and stop(entries))
        out.append((tab, meta, entries, err, stopped))
        _log("  %s %s: %d uploads%s%s" % (sid, tab, len(entries), " (stopped at the boundary)" if stopped else "",
                                        " (cut short)" if err else ""))
        # A hard failure on the first tab usually means YouTube is refusing
        # this server: do not try the other tabs.
        if err and not entries and tab == "videos":
            break
    return sid, out


def _merge_tabs(cat, tabs, now, day, src):
    """Merge listed tabs into the catalog; mark gone what a complete listing
    no longer shows. Returns (subscriber count or None, uploads read, error)."""
    subs, read, first_err = None, 0, None
    for tab, meta, entries, err, stopped in tabs:
        if tab == "videos" and meta:
            if meta.get("channel_follower_count") and src["kind"] == "channel":
                subs = int(meta["channel_follower_count"])
            if meta.get("description") is not None:
                cat["description"] = (meta.get("description") or "")[:600]
            if meta.get("channel") and src["kind"] == "channel":
                cat["title"] = meta["channel"]
        est = ytdlp_fetch.estimate_dates(entries, cat["videos"], now)
        catalog.merge_listing(cat, entries, est, tab, day, now=now)
        read += len(entries)
        if err:
            first_err = first_err or "%s: %s" % (tab, err)
            continue
        ids = [e["id"] for e in entries]
        if not stopped:
            catalog.mark_gone(cat, tab, ids, day)
        elif tab != "shorts" and est and est[-1] is not None:
            # Stopped at the 90-day boundary: only judge what is newer than
            # the oldest upload read.
            catalog.mark_gone(cat, tab, ids, day, newer_than=iso(est[-1]))
    return subs, read, first_err


def _run_listings(srcs, now, day, recent, workers=2, skip=()):
    todo = [sid for sid in srcs if sid not in skip]
    cats = {sid: catalog.load(sid, srcs[sid]) for sid in todo}
    results = []
    if todo:
        # Probe one source first: when YouTube blocks this server, stop there.
        results.append(_list_tabs(todo[0], srcs[todo[0]], cats[todo[0]]["videos"], now, recent))
        if any(e for _, _, e, _, _ in results[0][1]) or len(todo) == 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results += list(ex.map(lambda sid: _list_tabs(sid, srcs[sid], cats[sid]["videos"], now, recent),
                                       todo[1:]))
    subs = load_json(config.SUBSCRIBERS_FILE, {}) or {}
    ok, errors = [], []
    for sid, tabs in results:
        cat = cats[sid]
        n_subs, read, err = _merge_tabs(cat, tabs, now, day, srcs[sid])
        if n_subs and not recent:
            subs.setdefault(srcs[sid]["channel_id"], {})[day] = n_subs
        if err:
            errors.append({"source": sid, "error": err[:300], "uploads_read": read})
        if read:
            ok.append(sid)
            if not recent:
                cat["listing_date"] = day
            cat["recent_listing_date"] = day
        catalog.save(cat)
    if not recent:
        save_json(config.SUBSCRIBERS_FILE, subs)
    return ok, errors


# ── daily ──

def daily(now=None, listings=True):
    now = now or utcnow()
    day = today_str(now)
    shows = roster.load_roster()
    srcs = roster.sources(shows)
    history.migrate_legacy()

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = dict(zip(srcs, ex.map(feeds.fetch_source, srcs.values())))
        shorts = dict(zip(srcs, ex.map(feeds.fetch_shorts, srcs.values())))
    ok = failed = 0
    for sid, res in results.items():
        cat = catalog.load(sid, srcs[sid])
        if res["ok"]:
            ok += 1
            if res["title"]:
                cat["title"] = res["title"]
            catalog.merge_feed(cat, res["videos"], day)
        else:
            failed += 1
            _log("feed failed:", sid, res["error"])
        if shorts.get(sid):
            catalog.merge_feed(cat, shorts[sid], day)
        catalog.save(cat)
    _log("feeds: %d ok, %d failed; shorts feeds: %d ok" % (ok, failed, sum(1 for v in shorts.values() if v)))

    listed, errors = [], []
    if listings:
        # A source fully listed today (the Monday weekly run) needs no second pass.
        done_today = {sid for sid in srcs if catalog.load(sid, srcs[sid]).get("listing_date") == day}
        listed, errors = _run_listings(srcs, now, day, recent=True, skip=done_today)
        listed += sorted(done_today)
        _log("recent listings: %d sources read, %d with errors" % (len(listed), len(errors)))

    views, likes = _snapshot_from_catalogs(srcs, day, now, recent_only=True)
    at = iso(now)
    history.write_daily(day, at, views, likes)
    history.rollup(day)

    st = _status()
    st["feeds"] = {"last_run": at, "ok": ok, "failed": failed,
                   "shorts_ok": sum(1 for v in shorts.values() if v)}
    if listings:
        st["daily_listing"] = {"last_run": at, "sources_read": len(listed), "errors": errors[:10],
                               "sources_with_errors": len(errors)}
    st["daily_snapshot"] = {"date": day, "videos": sum(len(v) for v in views.values())}
    if ok or listed:
        st["last_success"] = at
    save_json(config.STATUS_FILE, st)


# ── weekly ──

def refresh_careermap_names():
    """Career Map's player names (the names its pages and slugs come from),
    for matching guests. Keeps the last good copy when the fetch fails."""
    try:
        req = urllib.request.Request(CAREERMAP_NAMES_URL, headers={"User-Agent": feeds.UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            import json
            names = json.loads(r.read().decode("utf-8"))
        if isinstance(names, list) and len(names) > 1000:
            save_json(config.CAREERMAP_PLAYERS_FILE, {"source": CAREERMAP_NAMES_URL, "names": sorted(set(names))})
            return len(names)
    except Exception as e:
        _log("career map names: kept the last copy (%s)" % e)
    return None


def weekly_due(now=None):
    from datetime import date
    now = now or utcnow()
    last = (_status().get("ytdlp") or {}).get("last_attempt")
    if not last:
        return True
    age = (now.date() - date.fromisoformat(last)).days
    return age >= 7 or (now.weekday() == 0 and age >= 1)


def weekly(now=None, only=None, workers=2):
    """Full listing of every source. `only` limits it to some source ids."""
    now = now or utcnow()
    day = today_str(now)
    shows = roster.load_roster()
    srcs = {sid: src for sid, src in roster.sources(shows).items() if not only or sid in only}
    st = _status()
    t0 = time.time()
    history.migrate_legacy()
    ok_sources, failed = _run_listings(srcs, now, day, recent=False, workers=workers)

    views, _ = _snapshot_from_catalogs(srcs, day, now, recent_only=False)
    history.write_weekly(day, views)
    refresh_careermap_names()
    from . import headshots
    headshots.refresh_index()
    history.rollup(day)

    blocked = bool(failed) and not ok_sources
    prev = st.get("ytdlp", {})
    st["ytdlp"] = {
        "last_attempt": day,
        "last_ok": day if ok_sources else prev.get("last_ok"),
        "blocked": blocked,
        "sources_ok": len(ok_sources),
        "sources_with_errors": len(failed),
        "errors": failed[:10],
        "seconds": int(time.time() - t0),
    }
    if ok_sources:
        st["last_success"] = iso(now)
    save_json(config.STATUS_FILE, st)
    _log("weekly listing: %d read, %d with errors%s" % (len(ok_sources), len(failed), " (BLOCKED)" if blocked else ""))
    return st["ytdlp"]
