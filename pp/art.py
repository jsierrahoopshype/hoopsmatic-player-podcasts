"""Show artwork: each YouTube channel's public avatar, copied into the repo
(data/art/<channel id>.webp, 176px, a few KB) so visitors never load it from
YouTube. The avatar's address comes from a yt-dlp listing of the channel's
page (no key); it is refreshed with the weekly listing and kept when a fetch
fails. A show without artwork gets its initials on the page instead.
"""
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config
from .feeds import UA

SIZE = 176


def path_for(channel_id):
    return config.ART_DIR / (channel_id + ".webp")


def _avatar_url(channel_id):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": 1, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info("https://www.youtube.com/channel/%s/videos" % channel_id, download=False, process=False)
    thumbs = info.get("thumbnails") or []
    for t in thumbs:
        if t.get("id") == "avatar_uncropped":
            return t["url"]
    square = [t for t in thumbs if t.get("width") and t.get("width") == t.get("height")]
    return max(square, key=lambda t: t["width"])["url"] if square else None


def _fetch(channel_id):
    from PIL import Image
    try:
        url = _avatar_url(channel_id)
        if not url:
            return channel_id, False
        if "googleusercontent.com" in url:
            url = url.split("=")[0] + "=s%d-c-k-c0x00ffffff-no-rj" % SIZE
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw)).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=60, method=6)
        p = path_for(channel_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(out.getvalue())
        return channel_id, True
    except Exception as e:
        print("artwork %s: %s" % (channel_id, e), file=sys.stderr)
        return channel_id, False


def refresh(channel_ids, only_missing=False, workers=3):
    """Fetch the avatar of each channel (only those without one, if asked)."""
    todo = [c for c in dict.fromkeys(channel_ids) if not (only_missing and path_for(c).exists())]
    if not todo:
        return 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        ok = sum(1 for _, good in ex.map(_fetch, todo) if good)
    print("artwork: %d of %d channels" % (ok, len(todo)), file=sys.stderr)
    return ok


def available(channel_ids):
    return {c for c in channel_ids if path_for(c).exists()}
