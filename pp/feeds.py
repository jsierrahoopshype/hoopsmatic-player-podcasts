"""YouTube's public Atom feeds: no key, no login.

Each feed lists a source's 15 most recent uploads with exact publish times,
exact view counts (media:statistics) and like counts (media:starRating count).
For a channel we prefer the long-form-only playlist UULF<id without "UC">, which
leaves out Shorts; if that fails we fall back to the plain channel feed.
"""
import time
import urllib.error
import urllib.request

from defusedxml import ElementTree as ET

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "m": "http://search.yahoo.com/mrss/",
}
FEED = "https://www.youtube.com/feeds/videos.xml?"
UA = "Mozilla/5.0 (compatible; HoopsMatic player-podcasts; +https://hoopsmatic.com/player-podcasts/)"


def feed_urls(src):
    """Feed URLs to try, in order, as (label, url)."""
    if src["kind"] == "playlist":
        return [("playlist", FEED + "playlist_id=" + src["playlist_id"])]
    cid = src["channel_id"]
    out = []
    if cid.startswith("UC"):
        out.append(("UULF", FEED + "playlist_id=UULF" + cid[2:]))
    out.append(("channel", FEED + "channel_id=" + cid))
    return out


def http_get(url, timeout=30, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:  # network hiccup: retry
            last = e
        time.sleep(2 * (i + 1))
    raise last


def parse_feed(xml_bytes):
    """-> (channel_title, [video dict]). Views/likes are None when absent."""
    root = ET.fromstring(xml_bytes)
    author = root.find("a:author/a:name", NS)
    title = author.text if author is not None else None
    vids = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        if not vid:
            continue
        link = e.find("a:link", NS)
        href = link.get("href") if link is not None else ""
        stats = e.find("m:group/m:community/m:statistics", NS)
        rating = e.find("m:group/m:community/m:starRating", NS)
        views = int(stats.get("views")) if stats is not None and stats.get("views") is not None else None
        likes = int(rating.get("count")) if rating is not None and rating.get("count") is not None else None
        vids.append({
            "id": vid,
            "title": e.findtext("a:title", namespaces=NS) or "",
            "published": e.findtext("a:published", namespaces=NS),
            "views": views,
            "likes": likes,
            # The plain channel feed links Shorts as /shorts/<id>.
            "short": "/shorts/" in (href or ""),
        })
    return title, vids


def fetch_source(src):
    """-> {"ok", "feed", "title", "videos", "error"} for one source."""
    errors = []
    for label, url in feed_urls(src):
        try:
            title, vids = parse_feed(http_get(url))
            return {"ok": True, "feed": label, "title": title, "videos": vids, "error": None}
        except Exception as e:
            errors.append("%s: %s" % (label, e))
    return {"ok": False, "feed": None, "title": None, "videos": [], "error": "; ".join(errors)}
