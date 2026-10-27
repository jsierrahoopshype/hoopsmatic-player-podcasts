"""Every playable video in one list, for the cards, the homepage shelves and
the Latest Videos stream.

Each item: id, show (slug), fmt (full / clip / short / unknown), published,
views, duration, title, likes / likes_views (or None), breakout (or None),
gain24 / gain7 / gain30 (or None).

Breakout: a video's views divided by the median views of the same show's
videos of the same format published in the 90 days before it. At least 8
videos are needed in that baseline; otherwise there is no score ("not enough
data").

Views gained come from the snapshots (data/snapshots/): today's reading
minus the reading 1, 7 or 30 days earlier, per video. They exist only when
both readings do and most of the videos the earlier one read are read again;
until then they are None and the pages leave them out instead of showing
zeros. A video the earlier reading missed has no gain (unless it was posted
after it: then all its views are new). Listing view counts are rounded to 3
significant figures and feed counts are exact, so when either side is rounded
both are, before subtracting.
"""
from bisect import bisect_left
from datetime import timedelta
from statistics import median

from . import config, history, metrics, roster
from .util import parse_ts

BREAKOUT_MIN_BASELINE = 8
BREAKOUT_DAYS = 90
# The later reading must read again at least this share of the videos the
# earlier one read (a blocked or partial run is not compared).
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
    shared = sum(1 for k in then if k in now)
    if shared < MIN_COVERAGE * len(then):
        return None
    return {"day_then": day_then, "day_now": day_now, "then": then, "now": now}


def build_items(shows, cats, stats_by_slug, today, kinds=("podcast",)):
    """All dated, non-gone videos of shows of these kinds that are shown on
    the site (ranked, occasional or dormant)."""
    g24 = gains(today, 1)
    g7 = gains(today, 7)
    g30 = gains(today, 30)
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
                         "title": v.get("title") or "", "embed": v.get("embed", True),
                         "likes": v.get("likes"), "likes_views": v.get("likes_views")})
        scores = breakout_scores(mine)
        for it in mine:
            it["breakout"] = scores.get(it["id"])
            it["gain24"] = _gain(it, g24)
            it["gain7"] = _gain(it, g7)
            it["gain30"] = _gain(it, g30)
        items.extend(mine)
    return items, {"g24": g24 is not None, "g7": g7 is not None, "g30": g30 is not None,
                   "g24_since": g24 and g24["day_then"], "g7_since": g7 and g7["day_then"],
                   "g30_since": g30 and g30["day_then"], "gain_day": (g24 or g7 or g30 or {}).get("day_now")}


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
    if _rounded(now) or _rounded(then):
        now, then = _round3(now), _round3(then)
    return max(0, now - then)


def _rounded(n):
    """Looks like a listing count (3 significant figures or fewer, 1,000+)."""
    return n >= 1000 and len(str(int(n)).rstrip("0")) <= 3


def _round3(n):
    if n < 1000:
        return n
    p = 10 ** (len(str(int(n))) - 3)
    return int(round(n / p) * p)


def within_hours(items, now, hours):
    cut = now - timedelta(hours=hours)
    return [it for it in items if parse_ts(it["published"]) >= cut]
