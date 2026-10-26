"""Per-source video catalog (data/videos/<source id>.json).

Every video we have ever seen for a source, with the best data we have:
  title, published (ISO), published_exact (False = estimated from "3 weeks ago"),
  duration (seconds, None until known), tab ("videos", "streams", "shorts",
  or "feed" when only the feed has shown it), views + views_date + views_exact,
  likes + likes_views (the view count at the moment those likes were read).

Merging rules: a newer observation replaces an older one; on the same day an
exact count (feed) beats a rounded one (channel listing); an exact publish
time is never replaced by an estimate; a known duration is never erased.
"""
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


def merge_feed(cat, videos, day):
    """Fold one feed read (exact numbers) into the catalog."""
    vs = cat["videos"]
    for f in videos:
        v = vs.setdefault(f["id"], {})
        v["title"] = f["title"]
        if f.get("published"):
            v["published"] = f["published"].replace("+00:00", "Z")
            v["published_exact"] = True
        if f.get("short"):
            v["tab"] = "shorts"
        v.setdefault("tab", "feed")
        v.setdefault("duration", None)
        if _better_views(v, f.get("views"), day, True):
            v["views"], v["views_date"], v["views_exact"] = f["views"], day, True
        if f.get("likes") is not None and f.get("views") is not None:
            if day >= (v.get("likes_date") or ""):
                v["likes"], v["likes_views"], v["likes_date"] = f["likes"], f["views"], day


def merge_listing(cat, entries, est_dates, tab, day):
    """Fold one channel listing (rounded views, durations, estimated dates)."""
    vs = cat["videos"]
    for e, est in zip(entries, est_dates):
        v = vs.setdefault(e["id"], {})
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
        if _better_views(v, e.get("views"), day, False):
            v["views"], v["views_date"], v["views_exact"] = int(e["views"]), day, False
