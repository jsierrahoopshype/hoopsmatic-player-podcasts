"""What the homepage shows above the rankings, and the Latest Videos stream
data, all from the video list (podcasts only)."""
import hashlib
import json
from datetime import timedelta

from . import config
from .metrics import FULL, CLIP, SHORT
from .util import parse_ts

SHELF = 8
STREAM_FIRST = 12      # cards in the page itself
CHUNK = 24             # cards per "Load more"
STREAM_DAYS = 90


def sections(items, now, flags):
    recent48 = [it for it in items if it["fmt"] in (FULL, CLIP)
                and parse_ts(it["published"]) >= now - timedelta(hours=48)]
    watch = max(recent48, key=lambda it: it["views"]) if recent48 else None
    week = sorted((it for it in items if parse_ts(it["published"]) >= now - timedelta(days=7)
                   and (not watch or it["id"] != watch["id"])), key=lambda it: -it["views"])[:SHELF]
    trending, trend_label = [], None
    if flags.get("g24"):
        trending = sorted((it for it in items if it.get("gain24")), key=lambda it: -it["gain24"])[:SHELF]
        trend_label = "gain24"
    elif flags.get("g7"):
        trending = sorted((it for it in items if it.get("gain7")), key=lambda it: -it["gain7"])[:SHELF]
        trend_label = "gain7"
    latest_eps = sorted((it for it in items if it["fmt"] == FULL), key=lambda it: it["published"], reverse=True)[:SHELF]
    month = [it for it in items if parse_ts(it["published"]) >= now - timedelta(days=30) and it.get("breakout")]
    breakouts = sorted((it for it in month if it["breakout"] >= 2), key=lambda it: -it["breakout"])[:SHELF]
    return {"watch": watch, "week": week, "trending": trending, "trend_label": trend_label,
            "latest_eps": latest_eps, "breakouts": breakouts}


def stream_items(items, now):
    cut = now - timedelta(days=STREAM_DAYS)
    return sorted((it for it in items if parse_ts(it["published"]) >= cut),
                  key=lambda it: it["published"], reverse=True)


def _row(it, show_idx, ctx):
    return [it["id"], show_idx[it["show"]], it["fmt"], it["published"][:16] + "Z", it["views"],
            it.get("duration"), it["title"], it.get("gain24"), round(it["breakout"], 2) if it.get("breakout") else None,
            0 if it.get("embed") == "no" else 1, 1 if it["id"] in ctx["thumbs"] else 0, it.get("gain7")]


def video_files(prefix, pool, tabs, ctx, first, extra_meta=None):
    """{published path: bytes} for one filterable list of video cards: a meta
    file (shows, hosts), each tab's order in chunks, and one index for filters
    and search (loaded only when a filter or search is used). Row fields:
    id, show index, format, published, views, duration, title, views gained
    in 24h, breakout score, embeddable, thumbnail on file, views gained in 7 days."""
    from .cards import host_people
    show_slugs = sorted({it["show"] for it in pool})
    show_idx = {s: i for i, s in enumerate(show_slugs)}
    shows = []
    hosts = {}
    for s in show_slugs:
        show = ctx["shows"][s]
        people = host_people(show, ctx)
        shows.append([s, show["name"], [[n, u, h] for n, u, h in people]])
        for n, u, _ in people:
            hosts.setdefault(n, u)
    files = {}
    counts = {}
    for tab, rows in tabs.items():
        chunks = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)]
        counts[tab] = len(chunks)
        for n, ch in enumerate(chunks):
            files["data/%s-%s-%d.json" % (prefix, tab, n)] = json.dumps([_row(it, show_idx, ctx) for it in ch],
                                                                       separators=(",", ":"))
    files["data/%s-index.json" % prefix] = json.dumps([_row(it, show_idx, ctx) for it in pool], separators=(",", ":"))
    ver = hashlib.sha256("".join(files[k] for k in sorted(files)).encode()).hexdigest()[:10]
    meta = dict({"v": ver, "chunk": CHUNK, "first": first, "tabs": counts, "shows": shows,
                 "hosts": sorted([[n, u] for n, u in hosts.items()], key=lambda x: x[0])}, **(extra_meta or {}))
    files["data/%s-meta.json" % prefix] = json.dumps(meta, separators=(",", ":"))
    return {k: v.encode("utf-8") for k, v in files.items()}, ver


def stream_files(stream, ctx, flags):
    """The Latest Videos stream on the homepage (last 90 days)."""
    tabs = {"latest": stream, "views": sorted(stream, key=lambda it: -it["views"])}
    if flags.get("g24"):
        tabs["trending"] = sorted((it for it in stream if it.get("gain24")), key=lambda it: -it["gain24"])
    return video_files("stream", stream, tabs, ctx, STREAM_FIRST, {"trending": bool(flags.get("g24"))})


# ── Top videos page ──

TOP_PER_SHOW = 12      # per show and format, all time
TOP_OVERALL = 100      # per format, all time; also the longest unfiltered all-time list
TOP_FIRST = 12


def top_pool(items, now):
    """Videos the Top videos page can show: every video of the last 90 days,
    plus each show's 12 most viewed of each format and the 100 most viewed of
    each format, all time. Filters on older videos work within this pool."""
    cut = now - timedelta(days=STREAM_DAYS)
    chosen = {it["id"]: it for it in items if parse_ts(it["published"]) >= cut}
    by_views = sorted(items, key=lambda it: -it["views"])
    per, per_fmt = {}, {}
    for it in by_views:
        k = (it["show"], it["fmt"])
        if per.get(k, 0) < TOP_PER_SHOW:
            per[k] = per.get(k, 0) + 1
            chosen.setdefault(it["id"], it)
        if per_fmt.get(it["fmt"], 0) < TOP_OVERALL:
            per_fmt[it["fmt"]] = per_fmt.get(it["fmt"], 0) + 1
            chosen.setdefault(it["id"], it)
    return sorted(chosen.values(), key=lambda it: -it["views"])


def top_sections(pool, now, flags):
    def top(seq, key, n=SHELF):
        return sorted(seq, key=key)[:n]
    recent = [it for it in pool if parse_ts(it["published"]) >= now - timedelta(days=STREAM_DAYS)]
    return {
        "views": pool[:TOP_OVERALL],
        "full": [it for it in pool if it["fmt"] == FULL][:SHELF],
        "clip": [it for it in pool if it["fmt"] == CLIP][:SHELF],
        "short": [it for it in pool if it["fmt"] == SHORT][:SHELF],
        "gain24": top((it for it in pool if it.get("gain24")), lambda it: -it["gain24"]) if flags.get("g24") else [],
        "gain7": top((it for it in pool if it.get("gain7")), lambda it: -it["gain7"]) if flags.get("g7") else [],
        "breakout": top((it for it in recent if it.get("breakout")), lambda it: -it["breakout"]),
    }


def top_files(pool, ctx, flags):
    tabs = {"views": pool[:TOP_OVERALL],
            "breakout": sorted((it for it in pool if it.get("breakout")), key=lambda it: -it["breakout"])[:TOP_OVERALL]}
    if flags.get("g24"):
        tabs["trending"] = sorted((it for it in pool if it.get("gain24")), key=lambda it: -it["gain24"])[:TOP_OVERALL]
    if flags.get("g7"):
        tabs["gain7"] = sorted((it for it in pool if it.get("gain7")), key=lambda it: -it["gain7"])[:TOP_OVERALL]
    return video_files("top", pool, tabs, ctx, TOP_FIRST,
                       {"alltime": {"all": TOP_OVERALL, "show": TOP_PER_SHOW}, "recent_days": STREAM_DAYS})
