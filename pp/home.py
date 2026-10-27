"""What the homepage shows above the rankings, and the Latest Videos stream
data, all from the video list (podcasts only)."""
import hashlib
import json
from datetime import timedelta

from . import config
from .metrics import FULL, CLIP
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


def stream_files(stream, ctx, flags):
    """{published path: bytes} for the stream: a meta file (shows, hosts),
    chunked tabs and one index for filters and search (loaded only when a
    filter or search is used)."""
    from .cards import host_people
    show_slugs = sorted({it["show"] for it in stream})
    show_idx = {s: i for i, s in enumerate(show_slugs)}
    shows = []
    hosts = {}
    for s in show_slugs:
        show = ctx["shows"][s]
        people = host_people(show, ctx)
        shows.append([s, show["name"], [[n, u, h] for n, u, h in people]])
        for n, u, _ in people:
            hosts.setdefault(n, u)

    def row(it):
        return [it["id"], show_idx[it["show"]], it["fmt"], it["published"][:16] + "Z", it["views"],
                it.get("duration"), it["title"], it.get("gain24"), round(it["breakout"], 2) if it.get("breakout") else None,
                0 if it.get("embed") == "no" else 1, 1 if it["id"] in ctx["thumbs"] else 0]

    tabs = {"latest": stream, "views": sorted(stream, key=lambda it: -it["views"])}
    if flags.get("g24"):
        tabs["trending"] = sorted((it for it in stream if it.get("gain24")), key=lambda it: -it["gain24"])
    files = {}
    counts = {}
    for tab, rows in tabs.items():
        chunks = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)]
        counts[tab] = len(chunks)
        for n, ch in enumerate(chunks):
            files["data/stream-%s-%d.json" % (tab, n)] = json.dumps([row(it) for it in ch], separators=(",", ":"))
    files["data/stream-index.json"] = json.dumps([row(it) for it in stream], separators=(",", ":"))
    ver = hashlib.sha256("".join(files[k] for k in sorted(files)).encode()).hexdigest()[:10]
    meta = {"v": ver, "chunk": CHUNK, "first": STREAM_FIRST, "tabs": counts, "shows": shows,
            "hosts": sorted([[n, u] for n, u in hosts.items()], key=lambda x: x[0]),
            "trending": bool(flags.get("g24"))}
    files["data/stream-meta.json"] = json.dumps(meta, separators=(",", ":"))
    return {k: v.encode("utf-8") for k, v in files.items()}, ver
