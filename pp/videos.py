"""Every playable video in one list, for the cards, the homepage shelves and
the Latest Videos stream.

Each item: id, show (slug), fmt (full / clip / short / unknown), published,
views, duration, title, breakout (or None), gain24 / gain7 (or None).

Breakout: a video's views divided by the median views of the same show's
videos of the same format published in the 90 days before it. At least 8
videos are needed in that baseline; otherwise there is no score ("not enough
data").

Views gained come from the daily snapshots (data/snapshots/): today's reading
minus the reading 1 or 7 days earlier. They exist only when both readings do
and the earlier one covered most of the videos the later one did; until then
they are None and the pages leave them out instead of showing zeros.
"""
from bisect import bisect_left
from datetime import timedelta
from statistics import median

from . import config, history, metrics, roster
from .util import parse_ts

BREAKOUT_MIN_BASELINE = 8
BREAKOUT_DAYS = 90
# An earlier reading counts only if it read at least this share of the videos
# the later one did (the first days of history were feed-only and partial).
MIN_COVERAGE = 0.5


def breakout_scores(items):
    """{video id: score or None} per the rule above. items: one show's videos."""
    out = {}
    by_fmt = {}
    for it in items:
        if it.get("published"):
            by_fmt.setdefault(it["fmt"], []).append(it)
    for fmt, vids in by_fmt.items():
        vids.sort(key=lambda v: v["published"])
        times = [parse_ts(v["published"]) for v in vids]
        for i, v in enumerate(vids):
            start = bisect_left(times, times[i] - timedelta(days=BREAKOUT_DAYS))
            base = [w["views"] for w in vids[start:i] if w.get("views") is not None]
            if len(base) >= BREAKOUT_MIN_BASELINE and median(base) > 0:
                out[v["id"]] = v["views"] / median(base)
            else:
                out[v["id"]] = None
    return out


def gains(today, days):
    """{video id: views gained over `days`} or None when the snapshots cannot
    support it yet."""
    t0 = parse_ts(today + "T00:00:00Z")
    day_now, now = history.views_on(today, tolerance=0)
    if not now:
        return None
    then_day = (t0 - timedelta(days=days)).date().isoformat()
    day_then, then = history.views_on(then_day, tolerance=0 if days == 1 else 1)
    if not then:
        return None
    shared = sum(1 for k in now if k in then)
    if shared < MIN_COVERAGE * len(now):
        return None
    return {"day_then": day_then, "day_now": day_now, "then": then, "now": now}


def build_items(shows, cats, stats_by_slug, today, kinds=("podcast",)):
    """All dated, non-gone videos of shows of these kinds that are shown on
    the site (ranked, occasional or dormant)."""
    g24 = gains(today, 1)
    g7 = gains(today, 7)
    items = []
    for show in shows:
        st = stats_by_slug.get(show["slug"])
        if show.get("type") not in kinds or not st or st["status"] not in ("ranked", "occasional", "dormant"):
            continue
        cat = cats.get(roster.source_id(show)) or {}
        mine = []
        for v in metrics.show_videos(show, cat):
            mine.append({"id": v["id"], "show": show["slug"], "fmt": metrics.video_format(v),
                         "published": v["published"], "views": v["views"], "duration": v.get("duration"),
                         "title": v.get("title") or "", "embed": v.get("embed", True)})
        scores = breakout_scores(mine)
        for it in mine:
            it["breakout"] = scores.get(it["id"])
            it["gain24"] = _gain(it, g24)
            it["gain7"] = _gain(it, g7)
        items.extend(mine)
    return items, {"g24": g24 is not None, "g7": g7 is not None,
                   "g24_since": g24 and g24["day_then"], "g7_since": g7 and g7["day_then"]}


def _gain(it, g):
    if not g:
        return None
    now = g["now"].get(it["id"])
    if now is None:
        return None
    then = g["then"].get(it["id"])
    if then is None:
        # Published after the earlier reading: everything it has is new.
        if it["published"][:10] > g["day_then"]:
            then = 0
        else:
            return None
    return max(0, now - then)


def within_hours(items, now, hours):
    cut = now - timedelta(hours=hours)
    return [it for it in items if parse_ts(it["published"]) >= cut]
