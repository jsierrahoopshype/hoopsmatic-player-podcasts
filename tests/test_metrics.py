from pp import metrics
from tests.helpers import NOW, SHOW, cat, vid


def vids(*v):
    return metrics.show_videos(SHOW, cat(*v))


def test_momentum_counts_full_episodes_from_last_30_days_only():
    v = vids(vid(1, 1000), vid(29, 500), vid(31, 9999), vid(5, 7777, duration=900))
    assert metrics.momentum(v, NOW) == 1500


def test_momentum_counts_episodes_with_pending_length():
    v = vids(vid(1, 1000), vid(0.5, 300, duration=None, tab="feed"))
    assert metrics.momentum(v, NOW) == 1300


def test_typical_is_median_of_last_90_days():
    assert metrics.typical(vids(vid(1, 100), vid(20, 300), vid(60, 200)), NOW) == 200
    assert metrics.typical(vids(vid(1, 100), vid(20, 300), vid(60, 200), vid(80, 1000)), NOW) == 250
    assert metrics.typical(vids(vid(1, 100), vid(100, 5000)), NOW) == 100
    assert metrics.typical(vids(vid(100, 5000)), NOW) is None


def test_episodes_per_month_and_likes():
    s = metrics.show_stats(SHOW, cat(vid(1, 1000, likes=40), vid(10, 3000, likes=60), vid(50, 10), vid(95, 10)), NOW)
    assert s["episodes_90"] == 3
    assert s["episodes_per_month"] == 1.0
    assert s["likes_per_1k"] == 25.0


def test_subscriber_change_against_a_week_ago():
    hist = {"2026-10-05": 900000, "2026-10-12": 1000000, "2026-10-19": 1010000}
    subs, raw, pct = metrics.subscriber_stats(hist, "2026-10-19")
    assert (subs, raw) == (1010000, 10000)
    assert round(pct, 2) == 1.0
    assert metrics.subscriber_stats({"2026-10-19": 5}, "2026-10-19") == (5, None, None)


def test_rank_order_and_changes():
    stats = [{"slug": "a", "status": "ranked", "momentum": 10, "typical": 1},
             {"slug": "b", "status": "ranked", "momentum": 30, "typical": 1},
             {"slug": "c", "status": "ranked", "momentum": 20, "typical": 1},
             {"slug": "d", "status": "dormant", "momentum": 99, "typical": 1}]
    ranked = metrics.rank_shows(stats)
    assert [s["slug"] for s in ranked] == ["b", "c", "a"]
    assert metrics.rank_changes(ranked, {}, "2026-10-26") == {}
    hist = {"2026-10-19": {"a": 1, "b": 2}, "2026-10-25": {"a": 3}}
    ch = metrics.rank_changes(ranked, hist, "2026-10-26")
    assert ch == {"b": 1, "c": "NEW", "a": -2}


def test_podcasts_and_player_channels_rank_separately():
    stats = [{"slug": "p1", "type": "podcast", "status": "ranked", "momentum": 10, "typical": 1},
             {"slug": "c1", "type": "player_channel", "status": "ranked", "momentum": 99, "typical": 1},
             {"slug": "p2", "type": "podcast", "status": "ranked", "momentum": 30, "typical": 1},
             {"slug": "c2", "type": "player_channel", "status": "ranked", "momentum": 5, "typical": 1}]
    pods = metrics.rank_shows(stats, "podcast")
    chans = metrics.rank_shows(stats, "player_channel")
    assert [(s["slug"], s["rank"]) for s in pods] == [("p2", 1), ("p1", 2)]
    assert [(s["slug"], s["rank"]) for s in chans] == [("c1", 1), ("c2", 2)]
