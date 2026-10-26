from pp import metrics
from tests.helpers import NOW, SHOW, cat, vid


def test_breakout_score_is_views_over_median():
    assert metrics.breakout(5000, 1000) == 5.0
    assert metrics.breakout(100, None) is None
    assert metrics.is_breakout(5.0)
    assert not metrics.is_breakout(4.99)
    assert not metrics.is_breakout(None)


def test_breakouts_flagged_per_episode():
    s = metrics.show_stats(SHOW, cat(vid(1, 1000), vid(5, 1000), vid(9, 1000), vid(12, 6000)), NOW)
    by_views = {v["views"]: v["breakout"] for v in s["episodes"]}
    assert s["typical"] == 1000
    assert by_views[6000] == 6.0 and metrics.is_breakout(by_views[6000])
    assert by_views[1000] == 1.0


def test_no_breakout_score_with_too_few_episodes():
    s = metrics.show_stats(SHOW, cat(vid(1, 100), vid(5, 9000)), NOW)
    assert all(v["breakout"] is None for v in s["episodes"])
