"""Channel listings through yt-dlp: flat listings only, nothing is downloaded.

A flat listing reads a channel's Videos, Live and Shorts tabs (the same pages
a visitor scrolls) and returns every upload's title, length, rounded view
count and "N days ago" text, plus the channel's subscriber count. The Shorts
tab gives views only: no length, no date. No key, no login.

YouTube sometimes blocks cloud servers. Every call here returns an error
string instead of raising, so the workflow keeps the last good data and
carries on.
"""
import time

from . import reldates

try:
    import yt_dlp
except ImportError:  # the build and tests do not need it
    yt_dlp = None

# The listing gives "3 weeks ago" text; yt-dlp turns it into a timestamp and
# drops the text. This hook keeps the text so reldates can use the real bucket.
_REL_BY_TS = {}


def _install_rel_hook():
    if yt_dlp is None:
        return
    try:
        from yt_dlp.extractor.youtube._base import YoutubeBaseInfoExtractor as B
    except Exception:
        return
    if getattr(B, "_pp_hooked", False):
        return
    orig = B._parse_time_text

    def patched(self, text, *a, **kw):
        ts = orig(self, text, *a, **kw)
        if ts is not None and text:
            _REL_BY_TS[ts] = text
        return ts

    B._parse_time_text = patched
    B._pp_hooked = True


def _ydl():
    return yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "extractor_args": {"youtubetab": {"approximate_date": [""]}},
        # Pace the page requests: deep pages of big channels get 403s when
        # asked for too fast.
        "sleep_interval_requests": 1.0,
        "socket_timeout": 30,
        "retries": 5,
        "extractor_retries": 5,
    })


def _rel_for(entry, now_ts):
    """Relative text for a flat entry, reconstructed when the hook missed it."""
    ts = entry.get("timestamp")
    if ts is None:
        return None
    if ts in _REL_BY_TS:
        return _REL_BY_TS[ts]
    days = max(0, int((now_ts - ts) // 86400))
    return "%d days ago" % days


def list_tab(url, playlistend=None, stop=None):
    """-> (meta, [entries], error). Entries keep listing order (newest first).

    The listing is read page by page; when YouTube refuses a later page the
    pages already read are kept and returned along with the error, so a long
    channel still gets its newest uploads refreshed. stop(entries_so_far) ->
    True ends the listing early (no more pages are requested)."""
    if yt_dlp is None:
        return None, [], "yt-dlp is not installed"
    _install_rel_hook()
    now_ts = time.time()
    out, err = [], None
    try:
        with _ydl() as ydl:
            info = ydl.extract_info(url, download=False, process=False)
            meta = {k: info.get(k) for k in ("channel_follower_count", "channel", "title", "description")}
            try:
                for e in info.get("entries") or []:
                    if playlistend and len(out) >= playlistend:
                        break
                    if not e or not e.get("id") or len(e["id"]) != 11:
                        continue
                    out.append({
                        "id": e["id"],
                        "title": e.get("title"),
                        "duration": e.get("duration"),
                        "views": e.get("view_count"),
                        "rel": _rel_for(e, now_ts),
                    })
                    if stop is not None and stop(out):
                        break
            except Exception as ex:
                err = str(ex)[:300]
    except Exception as ex:
        msg = str(ex)
        # A channel with no Live tab is not an error.
        if "does not have a" in msg and "tab" in msg:
            return {}, [], None
        return None, [], msg[:300]
    return meta, out, err


def tab_urls(src, shorts=True):
    if src["kind"] == "playlist":
        return [("videos", "https://www.youtube.com/playlist?list=" + src["playlist_id"])]
    base = "https://www.youtube.com/channel/" + src["channel_id"]
    out = [("videos", base + "/videos"), ("streams", base + "/streams")]
    if shorts:
        out.append(("shorts", base + "/shorts"))
    return out


def stop_past_days(days, run=3):
    """Stop a dated listing once `run` entries in a row are older than `days`."""
    def stop(entries):
        tail = entries[-run:]
        if len(tail) < run:
            return False
        for e in tail:
            b = reldates.bucket(e.get("rel"))
            if not b or b[0] <= days:
                return False
        return True
    return stop


def stop_at_known_shorts(catalog_videos, days, now, run=15):
    """Stop a Shorts listing (no dates) once `run` Shorts in a row are ones we
    already know and that are either undated or older than `days`."""
    from .util import parse_ts

    def old(e):
        v = catalog_videos.get(e["id"])
        if not v:
            return False
        p = parse_ts(v.get("published"))
        return p is None or (now - p).days > days
    def stop(entries):
        tail = entries[-run:]
        return len(tail) == run and all(old(e) for e in tail)
    return stop


def subscriber_url(channel_id):
    return "https://www.youtube.com/channel/" + channel_id + "/videos"


def estimate_dates(entries, catalog_videos, now):
    """Feed-exact anchors plus relative buckets -> estimated publish datetimes."""
    from .util import parse_ts
    rows = []
    for e in entries:
        v = catalog_videos.get(e["id"]) or {}
        exact = parse_ts(v["published"]) if v.get("published_exact") and v.get("published") else None
        rows.append({"exact": exact, "rel": e.get("rel")})
    return reldates.estimate(rows, now)
