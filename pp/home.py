"""The video pools behind the homepage and Top videos feeds (pp/feed.py)
and the homepage's breakouts, all from the video list (podcasts only)."""
from datetime import timedelta

from . import config
from .metrics import FULL, CLIP, SHORT
from .util import parse_ts

SHELF = 8
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


# ── Top videos page ──

TOP_PER_SHOW = 12      # per show and format, all time
TOP_OVERALL = 100      # per format, all time


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
