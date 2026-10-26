"""Daily and weekly collection.

daily():  every source's public feed -> data/snapshots/<date>.json and the
          catalog; then a short yt-dlp listing (latest 30 uploads) only for
          sources with uploads whose length is still unknown.
weekly(): full yt-dlp listing of every source (every past upload's length,
          rounded views and estimated date) plus subscriber counts. Also the
          one-time backfill. Never raises: a blocked run is recorded in
          data/status.json and the last good data stays.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import catalog, config, feeds, roster, ytdlp_fetch
from .util import load_json, save_json, utcnow, today_str, parse_ts


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _status():
    return load_json(config.STATUS_FILE, {}) or {}


def daily(now=None, fill_lengths=True):
    now = now or utcnow()
    day = today_str(now)
    shows = roster.load_roster()
    srcs = roster.sources(shows)

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = dict(zip(srcs, ex.map(feeds.fetch_source, srcs.values())))

    snap_path = config.SNAPSHOTS_DIR / (day + ".json")
    snap = load_json(snap_path, {"date": day, "sources": {}})
    ok = failed = 0
    for sid, res in results.items():
        if not res["ok"]:
            failed += 1
            _log("feed failed:", sid, res["error"])
            # keep whatever an earlier run today already got
            snap["sources"].setdefault(sid, {"ok": False, "error": res["error"], "videos": {}})
            continue
        ok += 1
        snap["sources"][sid] = {
            "ok": True,
            "feed": res["feed"],
            "title": res["title"],
            "videos": {v["id"]: {"published": v["published"], "views": v["views"], "likes": v["likes"],
                                 "title": v["title"]} for v in res["videos"]},
        }
        cat = catalog.load(sid, srcs[sid])
        if res["title"]:
            cat["title"] = res["title"]
        catalog.merge_feed(cat, res["videos"], day)
        catalog.save(cat)
    snap["fetched_at"] = now.isoformat().replace("+00:00", "Z")
    save_json(snap_path, snap, line_per_key="sources")

    st = _status()
    st["feeds"] = {"last_run": snap["fetched_at"], "ok": ok, "failed": failed}
    save_json(config.STATUS_FILE, st)
    _log("feeds: %d ok, %d failed" % (ok, failed))

    if fill_lengths:
        fill_unknown_lengths(srcs, now)


def fill_unknown_lengths(srcs, now):
    """Short listing (latest 30) for sources with recent uploads of unknown length."""
    day = today_str(now)
    st = _status()
    tried = filled = 0
    errors = []
    for sid, src in srcs.items():
        cat = catalog.load(sid, src)
        pending = [vid for vid, v in cat["videos"].items()
                   if v.get("duration") is None and v.get("tab") != "shorts"
                   and v.get("published") and (now - parse_ts(v["published"])).days <= config.TYPICAL_DAYS]
        if not pending:
            continue
        tried += 1
        for tab, url in ytdlp_fetch.tab_urls(src):
            meta, entries, err = ytdlp_fetch.list_tab(url, playlistend=30)
            if err:
                errors.append("%s %s: %s" % (sid, tab, err))
                if not entries:
                    break
            est = ytdlp_fetch.estimate_dates(entries, cat["videos"], now)
            catalog.merge_listing(cat, entries, est, tab, day)
        after = [vid for vid in pending if cat["videos"][vid].get("duration") is not None]
        filled += len(after)
        catalog.save(cat)
    st["length_fill"] = {"last_run": now.isoformat().replace("+00:00", "Z"), "sources_tried": tried,
                         "videos_filled": filled, "errors": errors[:10]}
    save_json(config.STATUS_FILE, st)
    _log("length fill: %d sources, %d videos filled, %d errors" % (tried, filled, len(errors)))


def _list_source(sid, src):
    """All tabs of one source -> (sid, [(tab, meta, entries)], error or None).
    A tab cut short by YouTube still returns the uploads read before the cut."""
    tabs = []
    for tab, url in ytdlp_fetch.tab_urls(src):
        meta, entries, err = ytdlp_fetch.list_tab(url)
        if entries or meta:
            tabs.append((tab, meta, entries))
        _log("  %s %s: %d uploads%s" % (sid, tab, len(entries), " (cut short)" if err else ""))
        if err:
            return sid, tabs, "%s: %s" % (tab, err)
    return sid, tabs, None


def _read_any(result):
    return any(entries for _, _, entries in result[1])


def weekly(now=None, only=None, workers=2):
    """Full listing of every source. `only` limits it to some source ids."""
    now = now or utcnow()
    day = today_str(now)
    shows = roster.load_roster()
    srcs = {sid: src for sid, src in roster.sources(shows).items() if not only or sid in only}
    subs = load_json(config.SUBSCRIBERS_FILE, {}) or {}
    st = _status()
    ok_sources, failed = [], []
    t0 = time.time()

    # Probe one source first: when YouTube blocks this server, stop there
    # instead of hammering it, and keep the last good data.
    order = list(srcs)
    results = []
    if order:
        results.append(_list_source(order[0], srcs[order[0]]))
        if _read_any(results[0]) or len(order) == 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results += list(ex.map(lambda sid: _list_source(sid, srcs[sid]), order[1:]))

    for sid, tabs, err in results:
        src = srcs[sid]
        cat = catalog.load(sid, src)
        for tab, meta, entries in tabs:
            if tab == "videos" and meta:
                if meta.get("channel_follower_count") and src["kind"] == "channel":
                    subs.setdefault(src["channel_id"], {})[day] = int(meta["channel_follower_count"])
                if meta.get("description") is not None:
                    cat["description"] = (meta.get("description") or "")[:600]
                if meta.get("channel") and src["kind"] == "channel":
                    cat["title"] = meta["channel"]
            est = ytdlp_fetch.estimate_dates(entries, cat["videos"], now)
            catalog.merge_listing(cat, entries, est, tab, day)
        if err:
            failed.append({"source": sid, "error": err[:300], "uploads_read": sum(len(t[2]) for t in tabs)})
            _log("listing failed:", sid, err)
        if _read_any((sid, tabs, err)):
            # A listing cut short still refreshed the newest uploads.
            cat["listing_date"] = day
            ok_sources.append(sid)
        catalog.save(cat)
    save_json(config.SUBSCRIBERS_FILE, subs)

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
    save_json(config.STATUS_FILE, st)
    _log("weekly listing: %d read, %d with errors%s" % (len(ok_sources), len(failed), " (BLOCKED)" if blocked else ""))
    return st["ytdlp"]
