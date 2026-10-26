"""Thumbnails, copied into the repo so visitors never load images from YouTube.

The 320x180 "mqdefault" image is about 10-20 KB. A thumbnail is fetched once,
the first time an episode appears on a page, and kept.
"""
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config
from .feeds import UA

URL = "https://i.ytimg.com/vi/%s/mqdefault.jpg"


def path_for(vid):
    return config.THUMBS_DIR / (vid + ".jpg")


def _fetch(vid):
    p = path_for(vid)
    if p.exists() and p.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(URL % vid, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
        if not body.startswith(b"\xff\xd8"):
            return False
        p.write_bytes(body)
        return True
    except Exception as e:
        print("thumb failed:", vid, e, file=sys.stderr)
        return False


def ensure(video_ids):
    """Download the missing ones. Returns the set of ids that have a thumbnail."""
    config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    ids = sorted(set(video_ids))
    with ThreadPoolExecutor(max_workers=8) as ex:
        ok = list(ex.map(_fetch, ids))
    return {vid for vid, good in zip(ids, ok) if good}


def available(video_ids):
    return {vid for vid in video_ids if path_for(vid).exists()}
