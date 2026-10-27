"""Video types, the ranked / dormant rule, and every number on the pages.

Everything here is a pure function of the catalog, so tests can feed it small
hand-made inputs.
"""
from datetime import timedelta
from statistics import median

from . import config, roster
from .util import parse_ts, as_date

FULL, CLIP, SHORT, UNKNOWN = "full", "clip", "short", "unknown"


def video_type(duration, tab=None):
    """Full episode (20+ min), Clip (1-20 min), Short (under 1 min).

    Anything on a channel's Shorts tab is a Short. Unknown length stays
    UNKNOWN until a listing fills it in."""
    if tab == "shorts":
        return SHORT
    if duration is None:
        return UNKNOWN
    if duration < config.SHORT_MAX:
        return SHORT
    if duration < config.FULL_MIN:
        return CLIP
    return FULL


def counts_as_episode(v):
    """Rankings use full episodes only. A video whose length is not known yet
    (posted since the last listing) counts until its length is known; the
    daily run fills lengths in, so this window is normally under a day."""
    return video_type(v.get("duration"), v.get("tab")) in (FULL, UNKNOWN)


def age_days(v, now):
    p = parse_ts(v.get("published"))
    return None if p is None else (now - p).total_seconds() / 86400.0


def show_videos(show, cat):
    """The source's videos that belong to this show (title filter applied),
    with a publish date and a view count. Each gets its id under "id"."""
    out = []
    for vid, v in (cat or {}).get("videos", {}).items():
        if not v.get("published") or v.get("views") is None:
            continue
        if not roster.title_matches(show, v.get("title")):
            continue
        out.append(dict(v, id=vid))
    return out


def episodes(videos):
    return [v for v in videos if counts_as_episode(v)]


def within(videos, now, days):
    return [v for v in videos if (age_days(v, now) or 1e9) <= days]


def momentum(videos, now):
    """Total current views on full episodes posted in the last 30 days."""
    return sum(v["views"] for v in within(episodes(videos), now, config.MOMENTUM_DAYS))


def typical(videos, now):
    """Median views per full episode posted in the last 90 days (None if none)."""
    vals = [v["views"] for v in within(episodes(videos), now, config.TYPICAL_DAYS)]
    return median(vals) if vals else None


def breakout(views, show_median):
    if not show_median:
        return None
    return views / show_median


def is_breakout(score):
    return score is not None and score >= config.BREAKOUT_X


def likes_per_1k(videos, now):
    eps = [v for v in within(episodes(videos), now, config.TYPICAL_DAYS)
           if v.get("likes") is not None and v.get("likes_views")]
    lv = sum(v["likes_views"] for v in eps)
    return (1000.0 * sum(v["likes"] for v in eps) / lv) if lv else None


def is_active(videos, now):
    """At least one full episode in the last 90 days."""
    return bool(within(episodes(videos), now, config.TYPICAL_DAYS))


def ranking_status(videos, now):
    """"ranked", "occasional", "dormant" or "excluded" for one show's videos.

    Ranked: 4+ full episodes in the last 90 days, or 1 to 3 in the last 90
    days with 4+ in the last 180. Occasional: 1 to 3 in the last 90 days and
    fewer than 4 in the last 180 (not ranked). Dormant: none in the last 90
    days. Excluded: no full episode at all."""
    eps = episodes(videos)
    if not eps:
        return "excluded"
    n90 = len(within(eps, now, config.TYPICAL_DAYS))
    n180 = len(within(eps, now, config.LONG_DAYS))
    if n90 >= config.RANKED_MIN_EPISODES or (n90 >= 1 and n180 >= config.RANKED_MIN_EPISODES):
        return "ranked"
    if n90 >= 1:
        return "occasional"
    return "dormant"


def subscriber_stats(history, today):
    """history {date: count} -> (subs, change_raw, change_pct). The change is
    against the latest reading at least 7 days older than the newest one."""
    if not history:
        return None, None, None
    days = sorted(history)
    last = days[-1]
    subs = history[last]
    cutoff = (as_date(last) - timedelta(days=7)).isoformat()
    older = [d for d in days if d <= cutoff]
    if not older:
        return subs, None, None
    base = history[older[-1]]
    raw = subs - base
    return subs, raw, (100.0 * raw / base if base else None)


def show_stats(show, cat, now, subs_history=None, shared=False):
    vids = show_videos(show, cat)
    eps = episodes(vids)
    eps90 = within(eps, now, config.TYPICAL_DAYS)
    med = typical(vids, now)
    last_ep = max((v["published"] for v in eps), default=None)
    subs, subs_raw, subs_pct = (None, None, None) if shared else subscriber_stats(subs_history or {}, now.date().isoformat())

    status = ranking_status(vids, now)
    reason = "No full-length episodes (20+ minutes) found." if status == "excluded" else None
    # A show the roster leaves out on purpose (e.g. a network's own channel).
    if show.get("exclude_reason"):
        status, reason = "excluded", show["exclude_reason"]

    scored = []
    for v in eps:
        b = breakout(v["views"], med) if len(eps90) >= 3 else None
        scored.append(dict(v, breakout=b))

    return {
        "slug": show["slug"],
        "type": show.get("type", "podcast"),
        "status": status,
        "reason": reason,
        "momentum": momentum(vids, now),
        "typical": med,
        "episodes_90": len(eps90),
        "episodes_per_month": len(eps90) / 3.0,
        "likes_per_1k": likes_per_1k(vids, now),
        "subs": subs,
        "subs_change": subs_raw,
        "subs_change_pct": subs_pct,
        "episodes_180": len(within(eps, now, config.LONG_DAYS)),
        "last_episode": last_ep,
        "episodes": scored,
    }


def rank_shows(stats, kind=None):
    """Ranked shows by momentum (ties: typical episode), rank 1 first. With
    kind, only shows of that type ("podcast" or "player_channel"): each type
    has its own ranking."""
    ranked = [s for s in stats if s["status"] == "ranked" and (kind is None or s.get("type") == kind)]
    ranked.sort(key=lambda s: (-s["momentum"], -(s["typical"] or 0), s["slug"]))
    for i, s in enumerate(ranked, 1):
        s["rank"] = i
    return ranked


def rank_changes(ranked, history, today):
    """Rank change vs the latest saved ranking at least 7 days old.

    Returns {slug: int delta (positive = moved up) or "NEW"}; empty when there
    is no ranking from a week ago yet."""
    cutoff = (as_date(today) - timedelta(days=7)).isoformat()
    old_days = sorted(d for d in (history or {}) if d <= cutoff)
    if not old_days:
        return {}
    prev = history[old_days[-1]]
    out = {}
    for s in ranked:
        p = prev.get(s["slug"])
        out[s["slug"]] = "NEW" if p is None else p - s["rank"]
    return out
