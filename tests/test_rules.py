from pp import metrics
from tests.helpers import NOW, SHOW, cat, vid


def stats(*videos):
    return metrics.show_stats(SHOW, cat(*videos), NOW)


def test_active_needs_a_full_episode_in_90_days():
    assert metrics.is_active(metrics.show_videos(SHOW, cat(vid(89, 10))), NOW)
    assert not metrics.is_active(metrics.show_videos(SHOW, cat(vid(91, 10))), NOW)
    # a recent clip does not make a show active
    assert not metrics.is_active(metrics.show_videos(SHOW, cat(vid(2, 10, duration=600), vid(120, 10))), NOW)


def test_four_full_episodes_in_90_days_is_ranked():
    assert stats(vid(5, 10), vid(20, 10), vid(50, 10), vid(89, 10))["status"] == "ranked"
    # three in 90 days and nothing older: occasional, not ranked
    assert stats(vid(5, 10), vid(20, 10), vid(50, 10))["status"] == "occasional"


def test_one_to_three_in_90_days_needs_four_in_180():
    # 1 in 90 days, 4 in 180: ranked
    assert stats(vid(10, 10), vid(100, 10), vid(120, 10), vid(170, 10))["status"] == "ranked"
    # 2 in 90 days, 3 in 180: occasional
    assert stats(vid(10, 10), vid(30, 10), vid(170, 10))["status"] == "occasional"
    # the 180-day count stops at 180 days
    assert stats(vid(10, 10), vid(100, 10), vid(120, 10), vid(185, 10))["status"] == "occasional"


def test_occasional_versus_dormant():
    # 1 full episode in 90 days, nothing else: occasional, keeps its last date
    s = stats(vid(30, 10), vid(40, 10, duration=600))
    assert s["status"] == "occasional" and s["last_episode"].startswith("2026-09-26")
    # zero in 90 days: dormant, however busy the 180-day window was
    assert stats(vid(91, 10), vid(100, 10), vid(120, 10), vid(130, 10), vid(140, 10))["status"] == "dormant"
    # clips in the last 90 days do not make a show occasional
    assert stats(vid(5, 10, duration=600), vid(100, 10))["status"] == "dormant"


def test_roster_exclude_reason_wins():
    show = dict(SHOW, exclude_reason="network channel, not a player podcast")
    s = metrics.show_stats(show, cat(vid(1, 10), vid(2, 10), vid(3, 10), vid(4, 10)), NOW)
    assert s["status"] == "excluded" and s["reason"] == "network channel, not a player podcast"


def test_none_in_90_days_is_dormant_even_with_many_older():
    s = stats(*[vid(d, 10) for d in (95, 100, 110, 120, 130, 150)])
    assert s["status"] == "dormant"
    assert s["last_episode"].startswith("2026-07-23")


def test_clips_no_longer_matter():
    # 4 full episodes and 40 clips: ranked (the old clips-versus-episodes rule is gone)
    clips = [vid(d % 89 + 1, 10, duration=600) for d in range(40)]
    assert stats(vid(1, 10), vid(2, 10), vid(3, 10), vid(4, 10), *clips)["status"] == "ranked"


def test_no_full_episodes_ever_is_excluded():
    s = stats(vid(3, 10, duration=300), vid(4, 10, duration=40))
    assert s["status"] == "excluded"
    assert s["reason"].startswith("No full-length episodes")


def test_pending_length_counts_as_a_full_episode():
    assert stats(vid(1, 10), vid(2, 10), vid(3, 10), vid(0.5, 10, duration=None, tab="feed"))["status"] == "ranked"
