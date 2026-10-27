"""The numbers the rankings table can be sorted by, per show and per format.

Each number comes with the count of videos it is based on. A number that
cannot be worked out yet (no videos of that format, no snapshot from 7 or 30
days earlier, a single subscriber reading) is None: the pages leave it out or
say "no data", never a zero or an estimate.

Formats: "full" (20+ minutes), "clip" (1 to 20 minutes), "short" (under a
minute or from the Shorts tab) and "all".
"""
from statistics import median

from . import config
from .metrics import FULL, CLIP
from .util import parse_ts

FORMATS = ("full", "clip", "short", "all")
# Metrics that change with the format filter, then those that do not.
BY_FORMAT = ("v7", "v30", "g7", "g30", "total", "vids", "likes")
FIXED = ("typf", "typc", "subs", "subg")


def _age(it, now):
    return (now - parse_ts(it["published"])).total_seconds() / 86400.0


def _sum(items, key):
    vals = [it[key] for it in items if it.get(key) is not None]
    return (sum(vals), len(vals)) if vals else (None, 0)


def _median(items):
    vals = [it["views"] for it in items if it.get("views") is not None]
    return (median(vals), len(vals)) if vals else (None, 0)


def for_format(items, now, flags):
    """{metric: [value or None, videos it is based on]} for one show's videos
    of one format."""
    last7 = [it for it in items if _age(it, now) <= 7]
    last30 = [it for it in items if _age(it, now) <= config.MOMENTUM_DAYS]
    last90 = [it for it in items if _age(it, now) <= config.TYPICAL_DAYS]
    liked = [it for it in last90 if it.get("likes") is not None and it.get("likes_views")]
    lv = sum(it["likes_views"] for it in liked)
    out = {
        "v7": [sum(it["views"] for it in last7), len(last7)] if last7 else [None, 0],
        "v30": [sum(it["views"] for it in last30), len(last30)] if last30 else [None, 0],
        "g7": list(_sum(items, "gain7")) if flags.get("g7") else [None, 0],
        "g30": list(_sum(items, "gain30")) if flags.get("g30") else [None, 0],
        "total": [sum(it["views"] for it in items), len(items)] if items else [None, 0],
        "vids": [len(last30), len(last30)],
        "likes": [round(1000.0 * sum(it["likes"] for it in liked) / lv, 1), len(liked)] if lv else [None, 0],
    }
    return out


def show_metrics(items, stat, now, flags, shared):
    """{"full": {...}, "clip": {...}, "short": {...}, "all": {...}, "x": {...}}
    for one show. items: the show's videos (videos.build_items)."""
    out = {}
    for f in FORMATS:
        mine = items if f == "all" else [it for it in items if it["fmt"] == f]
        out[f] = for_format(mine, now, flags)
    recent = lambda fmt: [it for it in items if it["fmt"] == fmt and _age(it, now) <= config.TYPICAL_DAYS]
    out["x"] = {
        "typf": list(_median(recent(FULL))),
        "typc": list(_median(recent(CLIP))),
        "subs": [None, 0] if shared else [stat.get("subs"), 1 if stat.get("subs") is not None else 0],
        # Subscriber growth needs two weekly readings at least 7 days apart.
        "subg": [None, 0] if shared or stat.get("subs_change") is None
        else [stat["subs_change"], round(stat["subs_change_pct"], 2) if stat.get("subs_change_pct") is not None else None],
    }
    return out


def available(all_metrics):
    """The metrics at least one show has a number for (others are left out
    of the table)."""
    have = set()
    for m in all_metrics:
        for f in FORMATS:
            have.update(k for k, (v, _) in m[f].items() if v is not None)
        have.update(k for k, (v, _) in m["x"].items() if v is not None)
    return have

