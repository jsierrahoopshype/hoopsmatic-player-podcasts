"""Video feeds (pp/feed.py): chips, the first cards and module in the HTML,
the data file the page script reads, and the vertical Shorts card."""
import json
from datetime import timedelta

from pp import cards, feed
from tests.helpers import NOW


def it(i, days, views, fmt="full", show="s", **kw):
    d = NOW - timedelta(days=days)
    return dict({"id": "v%03d" % i, "show": show, "fmt": fmt, "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "views": views, "duration": 3600 if fmt == "full" else 30 if fmt == "short" else 300,
                 "title": "T%d" % i, "embed": "ok"}, **kw)


def ctx_for(items, **kw):
    return dict({"now": NOW, "shows": {"s": {"slug": "s", "name": "Show S", "hosts": [{"name": "B Hen", "url": None}]}},
                 "thumbs": {x["id"] for x in items}, "thumbs_v": set(), "thumbs_big": set(), "headshots": set(),
                 "stream": items, "flags": {"g24": False}, "stream_hosts": {"s": ["B Hen"]}}, **kw)


def ids(pairs):
    return [p[0]["id"] for p in pairs]


def test_chip_filters_and_sorts():
    items = [(it(1, 1, 10), None), (it(2, 3, 50, fmt="clip"), None), (it(3, 9, 99), {"r": "guest"}),
             (it(4, 2, 70, gain24=5), {"r": "host"})]
    assert ids(feed.apply(items, feed.chip("a", "", "", "views", days=7), NOW)) == ["v004", "v002", "v001"]
    assert ids(feed.apply(items, feed.chip("a", "", "", fmt="clip"), NOW)) == ["v002"]
    assert ids(feed.apply(items, feed.chip("a", "", "", role="guest"), NOW)) == ["v003"]
    assert ids(feed.apply(items, feed.chip("a", "", "", "g24", has="g24"), NOW)) == ["v004"]
    assert ids(feed.apply(items, feed.chip("a", "", ""), NOW)) == ["v001", "v004", "v002", "v003"]   # newest first


def test_home_defaults_to_most_watched_without_daily_counts():
    items = [it(i, i * 0.3, 100 + i) for i in range(40)]
    f = feed.home(ctx_for(items))
    assert f.default == "watched" and [c["k"] for c in f.chips] == ["watched", "latest", "episodes"]
    assert f.chips[0]["note"] == "Videos posted in the last 7 days, by views"


def test_home_defaults_to_trending_with_enough_gains():
    items = [it(i, i * 0.3, 100 + i, gain24=i) for i in range(40)]
    f = feed.home(ctx_for(items, flags={"g24": True}))
    assert f.default == "trending" and f.chips[0]["k"] == "trending"


def test_feed_html_has_first_12_cards_and_a_module_after_the_8th():
    items = [it(i, i * 0.1, 1000 - i) for i in range(30)]
    ctx = ctx_for(items)
    f = feed.home(ctx)
    html = feed.feed_html(f, ctx, [("talked", '<div class="vc-mod" data-mod="talked">T</div>'),
                                   ("rankings", '<div class="vc-mod" data-mod="rankings">R</div>')])
    lst = html.split('<div class="feed-list">')[1].split('<div class="feed-sentinel"')[0]
    assert lst.count('<article class="vc ') == 12
    assert lst.index('data-mod="talked"') > lst.index('<article', 0) and lst.split('data-mod="talked"')[0].count("<article") == 8
    assert '<template class="feed-mods">' in html and 'data-modules="1"' in html
    assert '<button class="loadmore" type="button">Load more</button>' in html      # 30 > 12: more to load
    assert 'class="shelf"' not in html
    # full label for desktop and screen readers, short one for phones
    assert 'aria-pressed="true"><span class="cl">Most watched</span><span class="cs" aria-hidden="true">Top</span></button>' in html
    assert '><span class="cl">Latest</span><span class="cs" aria-hidden="true">New</span></button>' in html
    assert 'aria-pressed="false">Episodes</button>' in html
    data = json.loads(ctx["feed_files"]["data/feed-home.json"])
    assert len(data["rows"]) == 30 and data["shows"][0][:2] == ["s", "Show S"] and data["cap"] is None


def test_page_feeds_are_capped_and_drop_empty_chips():
    items = [it(i, i, 1000 - i) for i in range(50)]
    ctx = ctx_for(items, per_show={"s": items})
    ctx["shows"]["s"]["channel_id"] = "UCx"
    f = feed.show(ctx, "s")
    assert [c["k"] for c in f.chips] == ["latest", "views", "episodes"]
    assert all(len(v) == feed.PAGE_CAP for v in f.lists(NOW).values())
    html = feed.feed_html(f, ctx, heading="Videos")
    assert "Lists here stop at 36 videos." in html and "youtube.com/channel/UCx" in html
    assert json.loads(ctx["feed_files"]["data/feed-show-s.json"])["cap"] == feed.PAGE_CAP


def test_short_card_uses_the_vertical_thumbnail():
    s = it(7, 1, 500, fmt="short")
    ctx = ctx_for([s], thumbs_v={"v007"})
    c = cards.video_card(s, ctx)
    assert '<article class="vc vc-short">' in c and 'src="/player-podcasts/thumbs/v/v007.webp" width="270" height="480"' in c
    assert feed.thumb_flag(s, ctx) == 2
    assert feed.thumb_flag(s, ctx_for([s])) == 1                     # no vertical one yet: the 16:9 one


def test_talk_rows_carry_start_and_clips():
    lead = it(1, 1, 100)
    rows = [(lead, {"r": "talk", "t": 95, "c": [["v002", "Clip", 30]]})]
    ctx = ctx_for([lead])
    c = feed.card_for(lead, rows[0][1], ctx, feed.chip("latest", "", ""))
    assert 'data-start="95"' in c and "&amp;t=95s" in c and "Also from this episode" in c and ">Talked about<" in c


def fmts(pairs):
    return "".join({"full": "F", "clip": "C", "short": "S"}[p[0]["fmt"]] for p in pairs)


def windows_ok(seq):
    return all(seq[i:i + 4].count("S") <= 1 for i in range(len(seq)))


def test_mixed_lists_hold_at_most_one_short_in_any_four():
    # by views: 4 Shorts on top, then episodes and clips
    items = [(it(i, 1, 1000 - i, fmt="short"), None) for i in range(4)] + \
            [(it(10 + i, 2, 500 - i, fmt="full" if i % 2 else "clip"), None) for i in range(9)]
    out = feed.apply(items, feed.chip("views", "Most viewed", "", "views"), NOW)
    assert fmts(out) == "SCFCSFCFSCFCS" and windows_ok(fmts(out))
    # nothing dropped, the Shorts keep their order among themselves, the others too
    assert sorted(ids(out)) == sorted(ids(items))
    assert [x for x in ids(out) if x < "v010"] == ["v000", "v001", "v002", "v003"]
    assert [x for x in ids(out) if x >= "v010"] == ["v0%d" % (10 + i) for i in range(9)]


def test_held_back_shorts_move_down_not_out():
    items = [(it(i, 1, 100 - i, fmt="short"), None) for i in range(5)] + [(it(9, 1, 1), None)]
    out = feed.apply(items, feed.chip("views", "", "", "views"), NOW)
    assert fmts(out) == "SFSSSS" and len(out) == 6          # too few other videos: the rest go at the end


def test_homepage_never_opens_with_a_short_and_the_shorts_chip_is_unchanged():
    items = [it(i, 1 + i * 0.01, 1000 - i, fmt="short" if i < 3 else "full") for i in range(12)]
    f = feed.home(ctx_for(items))
    lists = f.lists(NOW)
    assert fmts(lists["watched"])[0] == "F" and windows_ok(fmts(lists["watched"]))
    assert fmts(lists["watched"]) == "FSFFFSFFFSFF"
    assert fmts(lists["latest"])[0] == "F"
    assert ids(lists["shorts"]) == ["v000", "v001", "v002"]    # the Shorts chip: plain order
    assert all(c.get("m") for c in f.chips if not c["f"].get("fmt")) and not any(c.get("m") for c in f.chips if c["f"].get("fmt"))


def test_page_feeds_cap_shorts_in_latest_and_most_viewed_but_may_open_with_one():
    items = [it(i, i * 0.1, 1000 - i, fmt="short" if i % 4 < 2 else "clip") for i in range(16)]   # SSCC SSCC...
    ctx = ctx_for(items, per_show={"s": items})
    ctx["shows"]["s"]["channel_id"] = "UCx"
    lists = feed.show(ctx, "s").lists(NOW)
    for k in ("latest", "views"):
        assert windows_ok(fmts(lists[k])[:11]) and fmts(lists[k])[0] == "S"
    assert fmts(lists["latest"]) == "SCCCSCCCSCCSSSSS"            # Shorts beyond the clips: at the end
    assert fmts(lists["shorts"]) == "S" * 8
