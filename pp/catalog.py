"""Per-source video catalog (data/videos/<source id>.json).

Every video we have ever seen for a source, with the best data we have:
  title, published (ISO), published_exact (False = estimated from "3 weeks ago"),
  duration (seconds, None until known), tab ("videos", "streams", "shorts",
  or "feed" when only the feed has shown it), views + views_date + views_exact,
  likes + likes_views (the view count at the moment those likes were read),
  first_seen (the day we first saw it), desc (the start of its description,
  when a feed gave one), gone (the day it disappeared from a complete listing:
  deleted, private or unavailable; cleared if it comes back) and embed (False
  when YouTube does not allow it to play on other sites).

Merging rules: a newer observation replaces an older one; on the same day an
exact count (feed) beats a rounded one (channel listing); an exact publish
time is never replaced by an estimate; a known duration is never erased.
"""
from datetime import timedelta

from . import config
from .util import load_json, save_json, iso


def path_for(sid):
    return config.VIDEOS_DIR / (sid + ".json")


def load(sid, src=None):
    cat = load_json(path_for(sid))
    if cat is None:
        cat = {"source_id": sid, "videos": {}}
    if src:
        cat["kind"] = src["kind"]
        cat["channel_id"] = src["channel_id"]
        if src.get("playlist_id"):
            cat["playlist_id"] = src["playlist_id"]
    return cat


def save(cat):
    save_json(path_for(cat["source_id"]), cat, line_per_key="videos")


def _better_views(old, views, day, exact):
    if views is None:
        return False
    if old.get("views") is None:
        return True
    od = old.get("views_date") or ""
    if day > od:
        return True
    if day == od and exact and not old.get("views_exact"):
        return True
    return False


def _touch(v, day):
    v.setdefault("first_seen", day)
    v.pop("gone", None)          # seen again: not gone


def merge_feed(cat, videos, day):
    """Fold one feed read (exact numbers) into the catalog."""
    vs = cat["videos"]
    for f in videos:
        v = vs.setdefault(f["id"], {})
        _touch(v, day)
        v["title"] = f["title"]
        if f.get("published"):
            v["published"] = f["published"].replace("+00:00", "Z")
            v["published_exact"] = True
        if f.get("short"):
            v["tab"] = "shorts"
        v.setdefault("tab", "feed")
        v.setdefault("duration", None)
        if f.get("desc"):
            v["desc"] = f["desc"]
        if _better_views(v, f.get("views"), day, True):
            v["views"], v["views_date"], v["views_exact"] = f["views"], day, True
        if f.get("likes") is not None and f.get("views") is not None:
            if day >= (v.get("likes_date") or ""):
                v["likes"], v["likes_views"], v["likes_date"] = f["likes"], f["views"], day


def merge_listing(cat, entries, est_dates, tab, day, now=None):
    """Fold one channel listing (rounded views, durations, estimated dates).

    A Short that appears for the first time after this source's Shorts tab was
    already being listed (cat["shorts_since"] earlier than today) went up
    since the last listing: it is dated half a day before now. Shorts from
    the first listing that no feed or neighbour dates stay undated."""
    vs = cat["videos"]
    shorts_known = bool(cat.get("shorts_since")) and cat["shorts_since"] < day
    for e, est in zip(entries, est_dates):
        is_new = e["id"] not in vs
        v = vs.setdefault(e["id"], {})
        _touch(v, day)
        if e.get("title"):
            v["title"] = e["title"]
        if e.get("duration") is not None:
            v["duration"] = int(e["duration"])
        else:
            v.setdefault("duration", None)
        if tab == "shorts" or v.get("tab") in (None, "feed"):
            v["tab"] = tab
        if not v.get("published_exact") and est is not None:
            v["published"] = iso(est)
            v["published_exact"] = False
        elif tab == "shorts" and is_new and shorts_known and now is not None and not v.get("published"):
            v["published"] = iso(now - timedelta(hours=12))
            v["published_exact"] = False
        if _better_views(v, e.get("views"), day, False):
            v["views"], v["views_date"], v["views_exact"] = int(e["views"]), day, False
    if tab == "shorts" and not cat.get("shorts_since"):
        cat["shorts_since"] = day


def mark_gone(cat, tab, listed_ids, day, newer_than=None):
    """After a complete listing of one tab: videos of that tab we had but the
    listing no longer shows are marked gone (deleted, private or
    unavailable). With newer_than (an ISO time), only videos published after
    it are judged: a listing that stopped at a date boundary says nothing
    about older ones. Returns how many were newly marked."""
    listed = set(listed_ids)
    tab_total = sum(1 for v in cat["videos"].values() if v.get("tab") == tab and not v.get("gone"))
    todo = []
    for vid, v in cat["videos"].items():
        if v.get("tab") != tab or vid in listed or v.get("gone"):
            continue
        if newer_than is not None and not (v.get("published") and v["published"] > newer_than):
            continue
        todo.append(v)
    # A listing that suddenly misses a large share of a tab is far more likely
    # a YouTube hiccup than a mass deletion: mark nothing then.
    if len(todo) > max(5, 0.2 * tab_total):
        return -1
    for v in todo:
        v["gone"] = day
    return len(todo)
