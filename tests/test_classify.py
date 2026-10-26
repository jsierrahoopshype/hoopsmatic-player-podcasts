from pp import metrics


def test_length_buckets():
    assert metrics.video_type(30) == metrics.SHORT
    assert metrics.video_type(59) == metrics.SHORT
    assert metrics.video_type(60) == metrics.CLIP          # 1 minute is a clip
    assert metrics.video_type(19 * 60 + 59) == metrics.CLIP
    assert metrics.video_type(20 * 60) == metrics.FULL     # 20 minutes is a full episode
    assert metrics.video_type(3 * 3600) == metrics.FULL


def test_shorts_tab_and_unknown_length():
    assert metrics.video_type(None, "shorts") == metrics.SHORT
    assert metrics.video_type(3600, "shorts") == metrics.SHORT
    assert metrics.video_type(None, "videos") == metrics.UNKNOWN


def test_only_full_and_pending_count_as_episodes():
    assert metrics.counts_as_episode({"duration": 1500, "tab": "videos"})
    assert metrics.counts_as_episode({"duration": None, "tab": "feed"})   # length pending
    assert not metrics.counts_as_episode({"duration": 600, "tab": "videos"})
    assert not metrics.counts_as_episode({"duration": 40, "tab": "videos"})
