from datetime import timedelta

from pp import catalog, feeds, reldates
from tests.helpers import NOW

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <author><name>Club 520 Podcast</name></author>
 <entry>
  <yt:videoId>QqKUdpiP1XI</yt:videoId><title>Jeff Teague ARGUES</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=QqKUdpiP1XI"/>
  <published>2026-10-22T21:00:39+00:00</published>
  <media:group><media:community><media:starRating count="513" average="5.00" min="1" max="5"/>
  <media:statistics views="60668"/></media:community></media:group>
 </entry>
 <entry>
  <yt:videoId>abcdefghijk</yt:videoId><title>A short</title>
  <link rel="alternate" href="https://www.youtube.com/shorts/abcdefghijk"/>
  <published>2026-10-21T21:00:39+00:00</published>
 </entry>
</feed>"""


def test_parse_feed():
    title, vids = feeds.parse_feed(FEED)
    assert title == "Club 520 Podcast"
    assert vids[0] == {"id": "QqKUdpiP1XI", "title": "Jeff Teague ARGUES", "published": "2026-10-22T21:00:39+00:00",
                       "views": 60668, "likes": 513, "short": False, "desc": ""}
    assert vids[1]["short"] and vids[1]["views"] is None


def test_feed_urls_prefer_long_form_playlist():
    urls = feeds.feed_urls({"kind": "channel", "channel_id": "UCoA3lm9UTWDWK8Z1kcoWQcA"})
    assert urls[0] == ("UULF", feeds.FEED + "playlist_id=UULFoA3lm9UTWDWK8Z1kcoWQcA")
    assert urls[1][0] == "channel"


def test_merge_keeps_exact_over_rounded():
    c = {"videos": {}}
    catalog.merge_feed(c, feeds.parse_feed(FEED)[1], "2026-10-24")
    v = c["videos"]["QqKUdpiP1XI"]
    assert v["views"] == 60668 and v["views_exact"] and v["likes"] == 513
    # same-day rounded listing does not overwrite, but brings the length; exact date kept
    catalog.merge_listing(c, [{"id": "QqKUdpiP1XI", "duration": 601, "views": 61000}], [NOW], "videos", "2026-10-24")
    assert v["views"] == 60668 and v["duration"] == 601 and v["published"] == "2026-10-22T21:00:39Z"
    # a later listing does update the views
    catalog.merge_listing(c, [{"id": "QqKUdpiP1XI", "duration": 601, "views": 90000}], [NOW], "videos", "2026-11-02")
    assert v["views"] == 90000 and not v["views_exact"]


def test_relative_buckets():
    assert reldates.bucket("13d ago") == (13.0, 14.0)
    assert reldates.bucket("streamed 2w ago") == (14.0, 21.0)
    assert reldates.bucket("3 weeks ago") == (21.0, 28.0)
    assert reldates.bucket("1mo ago")[0] > 30
    assert reldates.bucket("nonsense") is None


def test_estimates_follow_listing_order_and_respect_anchors():
    exact = NOW - timedelta(days=16)
    rows = [{"rel": "2w ago"}, {"rel": "2w ago"}, {"exact": exact}, {"rel": "2w ago"}, {"rel": "1mo ago"}]
    est = reldates.estimate(rows, NOW)
    ages = [(NOW - d).total_seconds() / 86400 for d in est]
    assert ages == sorted(ages)                  # never goes backwards
    assert est[2] == exact                       # exact stays exact
    assert 14 <= ages[0] <= 16 and ages[3] >= 16 and ages[4] >= 30.4
