from datetime import timedelta

from pp import history, home, rankmetrics, render, videos
from tests.helpers import NOW


def it(i, days, views, fmt="full", show="s", **kw):
    d = NOW - timedelta(days=days)
    return dict({"id": "v%03d" % i, "show": show, "fmt": fmt, "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "views": views, "duration": 3600, "title": "T%d" % i}, **kw)


NOFLAGS = {"g24": False, "g7": False, "g30": False}


def test_metrics_per_format_with_the_count_they_are_based_on():
    items = [it(1, 2, 100), it(2, 10, 200), it(3, 40, 300), it(4, 3, 50, fmt="clip"), it(5, 200, 1000)]
    m = rankmetrics.show_metrics(items, {"subs": 5000}, NOW, NOFLAGS, shared=False)
    assert m["full"]["v7"] == [100, 1]
    assert m["full"]["v30"] == [300, 2]
    assert m["full"]["total"] == [1600, 4]
    assert m["full"]["vids"] == [2, 2]
    assert m["clip"]["v7"] == [50, 1]
    assert m["all"]["v7"] == [150, 2]
    assert m["short"]["v30"] == [None, 0]                     # no Shorts: no number, not a zero
    assert m["x"]["typf"] == [200, 3]                          # median of the 3 full episodes in 90 days
    assert m["x"]["typc"] == [50, 1]
    assert m["x"]["subs"] == [5000, 1]


def test_gained_and_subscriber_growth_only_with_the_data_behind_them():
    items = [it(1, 2, 100, gain7=40, gain30=None), it(2, 10, 200, gain7=10)]
    m = rankmetrics.show_metrics(items, {"subs": 5000, "subs_change": None}, NOW, NOFLAGS, shared=False)
    assert m["full"]["g7"] == [None, 0] and m["full"]["g30"] == [None, 0]
    assert m["x"]["subg"] == [None, 0]
    m = rankmetrics.show_metrics(items, {"subs": 5000, "subs_change": 100, "subs_change_pct": 2.04}, NOW,
                                 dict(NOFLAGS, g7=True), shared=False)
    assert m["full"]["g7"] == [50, 2]
    assert m["x"]["subg"] == [100, 2.04]
    # A shared channel: neither its subscribers nor their growth belong to one show.
    m = rankmetrics.show_metrics(items, {"subs": 5000, "subs_change": 100, "subs_change_pct": 2.0}, NOW, NOFLAGS, shared=True)
    assert m["x"]["subs"] == [None, 0] and m["x"]["subg"] == [None, 0]


def test_likes_per_thousand_from_videos_with_likes_only():
    items = [it(1, 5, 1000, likes=30, likes_views=1000), it(2, 6, 500), it(3, 100, 9, likes=9, likes_views=9)]
    m = rankmetrics.show_metrics(items, {}, NOW, NOFLAGS, shared=False)
    assert m["full"]["likes"] == [30.0, 1]


def test_available_leaves_out_metrics_nobody_has():
    m = rankmetrics.show_metrics([it(1, 2, 100)], {"subs": None}, NOW, NOFLAGS, shared=False)
    have = rankmetrics.available([m])
    assert "v7" in have and "typf" in have
    assert not {"g7", "g30", "subg", "subs", "typc", "likes"} & have


def test_table_cell_never_shows_a_zero_for_missing_data():
    assert render._lb_cell("v7", None, 0)[1] == '<span class="nd">no data</span>'
    assert "shared channel" in render._lb_cell("subs", None, 0, shared=True)[1]
    assert render._lb_cell("v30", 1500, 2)[1] == '1.5K<span class="bn">2 videos</span>'
    assert render.change_html(None) == ""                      # no comparable ranking: no arrow at all


def test_views_on_merges_weekly_under_daily(tmp_path, monkeypatch):
    monkeypatch.setattr(history.config, "SNAPSHOTS_DIR", tmp_path)
    history.write_weekly("2026-10-26", {"src": {"old": 10, "new": 1}})
    history.write_daily("2026-10-26", "2026-10-26T18:00:00Z", {"src": {"new": 5}})
    day, views = history.views_on("2026-10-26", tolerance=0)
    assert day == "2026-10-26" and views == {"old": 10, "new": 5}


def test_top_pool_keeps_recent_videos_and_each_shows_all_time_best(monkeypatch):
    monkeypatch.setattr(home, "TOP_OVERALL", 5)
    items = [it(i, 200 + i, 1000 - i) for i in range(20)]                    # 20 old full episodes
    items += [it(100 + i, 200, 5, fmt="clip") for i in range(3)]              # 3 old clips
    items += [it(200, 5, 1)]                                                  # 1 recent, few views
    pool = home.top_pool(items, NOW)
    ids = {x["id"] for x in pool}
    assert "v200" in ids                                                      # last 90 days: always in
    assert len([x for x in pool if x["fmt"] == "full" and x["id"] != "v200"]) == home.TOP_PER_SHOW
    assert {"v100", "v101", "v102"} <= ids
    assert pool[0]["views"] == max(x["views"] for x in items)
    s = home.top_sections(pool, NOW, NOFLAGS)
    assert s["gain24"] == [] and s["gain7"] == []                             # hidden until snapshots support it
    assert [x["fmt"] for x in s["clip"]] == ["clip"] * 3


def test_gains_over_30_days_need_a_reading_from_30_days_earlier(tmp_path, monkeypatch):
    monkeypatch.setattr(history.config, "SNAPSHOTS_DIR", tmp_path)
    history.write_daily("2026-10-26", "2026-10-26T06:00:00Z", {"s": {"a": 500}})
    assert videos.gains("2026-10-26", 30) is None
    history.write_daily("2026-09-26", "2026-09-26T06:00:00Z", {"s": {"a": 100}})
    g = videos.gains("2026-10-26", 30)
    assert g["day_then"] == "2026-09-26" and g["now"]["a"] - g["then"]["a"] == 400
