import json

import pytest

from pp import config, roster


def write(tmp_path, shows):
    p = tmp_path / "channels.json"
    p.write_text(json.dumps({"shows": shows}))
    return p


def test_every_show_in_the_real_roster_has_a_type():
    shows = roster.load_roster()
    assert shows and all(s["type"] in roster.SHOW_TYPES for s in shows)


def test_missing_or_unknown_type_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        roster.load_roster(write(tmp_path, [{"slug": "a", "name": "A", "channel_id": "UCa"}]))
    with pytest.raises(ValueError):
        roster.load_roster(write(tmp_path, [{"slug": "a", "name": "A", "channel_id": "UCa", "type": "vlog"}]))


def test_player_channels_slug_is_reserved(tmp_path):
    assert "player-channels" in config.RESERVED_SLUGS
    with pytest.raises(ValueError):
        roster.load_roster(write(tmp_path, [{"slug": "player-channels", "name": "X", "channel_id": "UCa",
                                             "type": "podcast"}]))
