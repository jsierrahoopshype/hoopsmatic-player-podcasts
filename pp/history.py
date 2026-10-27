"""View history.

data/snapshots/daily/<date>.json   views of every video published in the last
                                   90 days, read that day
data/snapshots/weekly/<date>.json  views of every video, from the Monday listing

Both are compact: one line per source, {"<video id>": views}. A daily file
also keeps the like counts the public feed gave that day, as
{"<video id>": [likes, views at that moment]}. Nothing else is repeated
there (titles, dates and lengths live in the catalog).

Daily files older than 90 days are rolled into the weekly file of their week
(only what that weekly file lacks) and deleted, so the history stays one
point per video per day for recent videos and one per week for older ones.
"""
import json
import re
from datetime import date, timedelta

from . import config
from .util import load_json, save_json

DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def daily_dir():
    return config.SNAPSHOTS_DIR / "daily"


def weekly_dir():
    return config.SNAPSHOTS_DIR / "weekly"


def daily_path(day):
    return daily_dir() / (day + ".json")


def weekly_path(day):
    return weekly_dir() / (day + ".json")


def monday_of(day):
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def _save(path, doc):
    # One line per source keeps a day's file small and its diffs readable.
    save_json(path, doc, line_per_key="v")


def load_daily(day):
    return load_json(daily_path(day))


def load_weekly(day):
    return load_json(weekly_path(day))


def write_daily(day, at, views, likes=None):
    """views {sid: {vid: n}}, likes {sid: {vid: [likes, views]}}. A second run
    the same day updates the file: newer numbers replace older ones."""
    doc = load_daily(day) or {"date": day, "v": {}}
    for sid, vv in views.items():
        doc["v"].setdefault(sid, {}).update(vv)
    if likes:
        doc.setdefault("l", {})
        for sid, ll in likes.items():
            doc["l"].setdefault(sid, {}).update(ll)
    doc["at"] = at
    _save(daily_path(day), doc)
    return doc


def write_weekly(day, views):
    doc = load_weekly(day) or {"date": day, "v": {}}
    for sid, vv in views.items():
        doc["v"].setdefault(sid, {}).update(vv)
    _save(weekly_path(day), doc)
    return doc


def days_on_file(kind="daily"):
    d = daily_dir() if kind == "daily" else weekly_dir()
    if not d.exists():
        return []
    return sorted(m.group(1) for m in (DAY_RE.match(p.name) for p in d.iterdir()) if m)


def migrate_legacy():
    """The first snapshots (data/snapshots/<date>.json, feed-shaped) become
    daily files. Returns the dates migrated."""
    done = []
    if not config.SNAPSHOTS_DIR.exists():
        return done
    for p in sorted(config.SNAPSHOTS_DIR.iterdir()):
        m = DAY_RE.match(p.name)
        if not m or not p.is_file():
            continue
        old = json.loads(p.read_text(encoding="utf-8"))
        views, likes = {}, {}
        for sid, src in (old.get("sources") or {}).items():
            for vid, v in (src.get("videos") or {}).items():
                if v.get("views") is not None:
                    views.setdefault(sid, {})[vid] = v["views"]
                if v.get("likes") is not None and v.get("views"):
                    likes.setdefault(sid, {})[vid] = [v["likes"], v["views"]]
        write_daily(m.group(1), old.get("fetched_at") or (m.group(1) + "T00:00:00Z"), views, likes)
        p.unlink()
        done.append(m.group(1))
    return done


def rollup(today, keep_days=None):
    """Daily files older than keep_days (90) go into their week's weekly file
    (values that file lacks) and are deleted. Returns the dates rolled up."""
    keep_days = config.DAILY_DAYS if keep_days is None else keep_days
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    rolled = []
    for day in days_on_file("daily"):
        if day >= cutoff:
            continue
        doc = load_daily(day) or {}
        wk = monday_of(day)
        wdoc = load_weekly(wk) or {"date": wk, "v": {}}
        for sid, vv in (doc.get("v") or {}).items():
            dst = wdoc["v"].setdefault(sid, {})
            for vid, n in vv.items():
                dst.setdefault(vid, n)
        _save(weekly_path(wk), wdoc)
        daily_path(day).unlink()
        rolled.append(day)
    return rolled


def views_on(day, tolerance=1):
    """{vid: views} as of `day`: that day's daily file, else the nearest
    daily or weekly file within `tolerance` days (None when there is none).
    Returns (actual_day, {vid: views})."""
    want = date.fromisoformat(day)
    best = None
    for kind in ("daily", "weekly"):
        for d in days_on_file(kind):
            gap = abs((date.fromisoformat(d) - want).days)
            if gap <= tolerance and (best is None or gap < best[0] or (gap == best[0] and kind == "daily")):
                best = (gap, kind, d)
    if best is None:
        return None, None
    doc = load_daily(best[2]) if best[1] == "daily" else load_weekly(best[2])
    flat = {}
    for vv in (doc.get("v") or {}).values():
        flat.update(vv)
    return best[2], flat


def gained(now_views, then_views, new_ids=()):
    """Views gained per video between two readings: videos read both times,
    plus videos published after the earlier reading (new_ids), which gained
    all their views. Never below zero (YouTube sometimes trims counts)."""
    new_ids = set(new_ids)
    out = {}
    for vid, n in now_views.items():
        if n is None:
            continue
        b = then_views.get(vid)
        if b is None and vid in new_ids:
            b = 0
        if b is not None:
            out[vid] = max(0, n - b)
    return out
