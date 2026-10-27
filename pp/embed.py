"""Can a video play on our page? YouTube's public oEmbed endpoint (no key)
answers per video: 200 = embeddable, 401/403 = the owner turned embedding off,
400/404 = deleted, private or otherwise unavailable.

Results are cached in data/embed.json ({"<id>": ["ok" | "no" | "gone", date]}).
A video is checked once; "gone" is checked again after 7 days (it may come
back). A network error leaves a video unchecked, and an unchecked video is
treated as playable: every player also has a "Watch on YouTube" link.
"""
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from . import config
from .feeds import UA
from .util import load_json, save_json

URL = "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v="
def load():
    return (load_json(config.EMBED_FILE, {}) or {}).get("v", {})


def _check(vid):
    try:
        req = urllib.request.Request(URL + vid, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return "ok" if r.status == 200 else None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "no"
        if e.code in (400, 404):
            return "gone"
        return None
    except Exception:
        return None


def due(cache, vid, today):
    got = cache.get(vid)
    if not got:
        return True
    if got[0] == "gone":
        return (date.fromisoformat(today) - date.fromisoformat(got[1])) >= timedelta(days=7)
    return False


def update(video_ids, today, limit=2500, workers=8):
    """Check the videos not checked yet (at most `limit` per run, in the
    order given: most important first). Returns the cache."""
    cache = load()
    todo = [v for v in dict.fromkeys(video_ids) if due(cache, v, today)][:limit]
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for vid, res in zip(todo, ex.map(_check, todo)):
                if res:
                    cache[vid] = [res, today]
        print("embed checks: %d done" % len(todo), file=sys.stderr)
    save_json(config.EMBED_FILE, {"_about": "Embed check per video (YouTube oEmbed): ok, no (embedding off), gone. Generated.",
                     "v": cache}, line_per_key="v")
    return cache


def status(cache, vid):
    got = cache.get(vid)
    return got[0] if got else "unchecked"
