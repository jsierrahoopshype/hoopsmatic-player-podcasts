"""Thumbnails, copied into the repo so visitors never load images from YouTube.

Cards use a 320x180 WebP (about 9 KB, quality 45) made from YouTube's
"mqdefault" image; a large card can use a 640x360 WebP cut from "hqdefault"
or "sddefault" (their 4:3 frame has the 16:9 picture in the middle). Shorts
also get a vertical 270x480 WebP made from "oar2" (YouTube's 1080x1920 Shorts
frame), kept in thumbs/v/. A thumbnail is fetched once, the first time a video
appears on a page, and kept.
Older JPEG thumbnails are converted to WebP the first time they are needed.
"""
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config
from .feeds import UA

try:
    from PIL import Image
except ImportError:  # tests and the offline build do not need it
    Image = None

URL = "https://i.ytimg.com/vi/%s/%s.jpg"


def path_for(vid, big=False):
    return config.THUMBS_DIR / ("big" if big else "") / (vid + ".webp")


def _get(vid, name):
    req = urllib.request.Request(URL % (vid, name), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def _to_webp(raw, size, crop43=False, quality=45):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if crop43:
        w, h = im.size
        ch = int(w * 9 / 16)
        top = (h - ch) // 2
        im = im.crop((0, top, w, top + ch))
    im = im.resize(size, Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "WEBP", quality=quality, method=6)
    return out.getvalue()


def _fetch(args):
    vid, big = args
    p = path_for(vid, big)
    if p.exists() and p.stat().st_size > 0:
        return True
    if Image is None:
        return False
    try:
        if big:
            for name in ("sddefault", "hqdefault"):
                try:
                    raw = _get(vid, name)
                    break
                except Exception:
                    raw = None
            if not raw:
                return False
            data = _to_webp(raw, (640, 360), crop43=True, quality=55)
        else:
            old = config.THUMBS_DIR / (vid + ".jpg")
            raw = old.read_bytes() if old.exists() else _get(vid, "mqdefault")
            data = _to_webp(raw, (320, 180))
            if old.exists():
                old.unlink()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return True
    except Exception as e:
        print("thumb failed:", vid, e, file=sys.stderr)
        return False


def ensure(video_ids, big_ids=()):
    """Make the missing ones. Returns (ids with a card thumbnail, ids with a big one)."""
    config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    small = sorted(set(video_ids))
    big = sorted(set(big_ids))
    with ThreadPoolExecutor(max_workers=8) as ex:
        ok_small = list(ex.map(_fetch, [(v, False) for v in small]))
        ok_big = list(ex.map(_fetch, [(v, True) for v in big]))
    return ({v for v, g in zip(small, ok_small) if g}, {v for v, g in zip(big, ok_big) if g})


def available(video_ids, big_ids=()):
    return ({v for v in video_ids if path_for(v).exists()}, {v for v in big_ids if path_for(v, True).exists()})


# ── vertical (9:16) thumbnails for Shorts ──

def path_for_vertical(vid):
    return config.THUMBS_DIR / "v" / (vid + ".webp")


def _fetch_vertical(vid):
    p = path_for_vertical(vid)
    if p.exists() and p.stat().st_size > 0:
        return True
    if Image is None:
        return False
    try:
        im = Image.open(io.BytesIO(_get(vid, "oar2"))).convert("RGB")
        w, h = im.size
        if h < w:          # not a vertical frame: keep the 16:9 card thumbnail
            return False
        ch = int(w * 16 / 9)
        if ch < h:          # taller than 9:16: cut the middle
            top = (h - ch) // 2
            im = im.crop((0, top, w, top + ch))
        im = im.resize((270, 480), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=45, method=6)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(out.getvalue())
        return True
    except Exception as e:
        print("vertical thumb failed:", vid, e, file=sys.stderr)
        return False


def ensure_vertical(video_ids):
    """Make the missing vertical thumbnails. Returns the ids that have one."""
    ids = sorted(set(video_ids))
    with ThreadPoolExecutor(max_workers=8) as ex:
        ok = list(ex.map(_fetch_vertical, ids))
    return {v for v, g in zip(ids, ok) if g}


def available_vertical(video_ids):
    return {v for v in video_ids if path_for_vertical(v).exists()}
