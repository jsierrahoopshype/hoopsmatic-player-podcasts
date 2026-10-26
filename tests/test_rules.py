from pp import metrics
from tests.helpers import NOW, SHOW, cat, vid


def stats(*videos):
    return metrics.show_stats(SHOW, cat(*videos), NOW)


def test_active_needs_a_full_episode_in_90_days():
    assert metrics.is_active(metrics.show_videos(SHOW, cat(vid(89, 10))), NOW)
    assert not metrics.is_active(metrics.show_videos(SHOW, cat(vid(91, 10))), NOW)
    # a recent clip does not make a show active
    assert not metrics.is_active(metrics.show_videos(SHOW, cat(vid(2, 10, duration=600), vid(120, 10))), NOW)


def test_dormant_and_ranked_status():
    assert stats(vid(120, 1000), vid(200, 500))["status"] == "dormant"
    assert stats(vid(120, 1000))["last_episode"].startswith("2026-06-28")
    assert stats(vid(10, 1000), vid(40, 500))["status"] == "ranked"


def test_real_show_rule_most_uploads_are_full_episodes():
    # 2 full, 3 clips in 90 days: not a real show
    s = stats(vid(1, 10), vid(2, 10), vid(3, 10, duration=500), vid(4, 10, duration=500), vid(5, 10, duration=500))
    assert s["status"] == "excluded"
    assert "2 of its 5" in s["reason"]
    # 3 full, 2 clips: real show
    s = stats(vid(1, 10), vid(2, 10), vid(3, 10), vid(4, 10, duration=500), vid(5, 10, duration=500))
    assert s["status"] == "ranked"
    # exactly half is not "most"
    s = stats(vid(1, 10), vid(2, 10, duration=500))
    assert s["status"] == "excluded"


def test_shorts_do_not_count_against_real_show():
    s = stats(vid(1, 10), vid(2, 10, duration=30), vid(3, 10, duration=None, tab="shorts"))
    assert s["status"] == "ranked"
    assert (s["full_90"], s["long_90"]) == (1, 1)


def test_no_full_episodes_ever_is_excluded():
    assert stats(vid(3, 10, duration=300))["status"] == "excluded"


def test_minutes_basis_weighs_uploads_by_length():
    v = metrics.show_videos(SHOW, cat(vid(1, 10, duration=3600), vid(2, 10, duration=600), vid(3, 10, duration=600),
                                      vid(4, 10, duration=600)))
    assert not metrics.is_real_show(v, NOW, basis="uploads")      # 1 of 4 uploads
    assert metrics.is_real_show(v, NOW, basis="minutes")          # 60 of 90 minutes
    assert metrics.real_show_counts(v, NOW, basis="minutes") == (60, 90)
