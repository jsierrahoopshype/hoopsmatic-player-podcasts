from pp import metrics, roster
from tests.helpers import NOW, cat, vid

BOARDROOM = {"slug": "boardroom", "name": "Boardroom", "channel_id": "UCB", "title_filter": {"exclude": r"\bETCs\b"}}
ETCS = {"slug": "the-etcs", "name": "The ETCs", "channel_id": "UCB", "title_filter": {"include": r"\bETCs\b"}}
PLAIN = {"slug": "plain", "name": "Plain", "channel_id": "UCP"}


def test_include_and_exclude():
    assert roster.title_matches(ETCS, "Isiah Thomas Joins The ETCs with Kevin Durant")
    assert roster.title_matches(ETCS, "kd on the etcs")                 # case-insensitive
    assert not roster.title_matches(ETCS, "Keanu Reeves on custom bikes")
    assert roster.title_matches(BOARDROOM, "Keanu Reeves on custom bikes")
    assert not roster.title_matches(BOARDROOM, "Isiah Thomas Joins The ETCs")
    assert roster.title_matches(PLAIN, "anything at all")
    assert roster.title_matches(PLAIN, None)


def test_one_channel_feeds_two_shows_without_overlap():
    c = cat(vid(3, 900, title="Isiah Thomas Joins The ETCs"), vid(5, 400, title="Emma Grede story"),
            vid(9, 300, title="Master P on No Limit"))
    etcs = metrics.show_videos(ETCS, c)
    board = metrics.show_videos(BOARDROOM, c)
    assert [v["views"] for v in etcs] == [900]
    assert sorted(v["views"] for v in board) == [300, 400]
    assert metrics.momentum(etcs, NOW) == 900
    assert metrics.momentum(board, NOW) == 700


def test_shared_channel_is_one_source():
    srcs = roster.sources([BOARDROOM, ETCS, PLAIN])
    assert set(srcs) == {"UCB", "UCP"}
    assert roster.shares_channel(ETCS, [BOARDROOM, ETCS, PLAIN])
    assert not roster.shares_channel(PLAIN, [BOARDROOM, ETCS, PLAIN])


def test_playlist_show_collects_from_playlist():
    off = {"slug": "off", "name": "Off Guard", "channel_id": "UCnbc", "playlist_id": "PLx"}
    assert roster.source_id(off) == "PLx"
    assert roster.sources([off])["PLx"]["kind"] == "playlist"
    assert roster.shares_channel(off, [off])
