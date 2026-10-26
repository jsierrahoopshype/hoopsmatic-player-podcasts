import json

from pp import collect, config, feeds, ytdlp_fetch
from tests.helpers import NOW


def test_failed_feed_falls_back_to_short_listing(tmp_path, monkeypatch):
    roster = {"shows": [{"slug": "s", "name": "S", "channel_id": "UCabc", "hosts": [], "youtube_url": "u"}]}
    (tmp_path / "channels.json").write_text(json.dumps(roster))
    monkeypatch.setattr(config, "CHANNELS_FILE", tmp_path / "channels.json")
    monkeypatch.setattr(config, "VIDEOS_DIR", tmp_path / "videos")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(config, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(feeds, "fetch_source", lambda src: {"ok": False, "feed": None, "title": None, "videos": [],
                                                             "error": "UULF: HTTP Error 404: Not Found"})
    calls = []

    def fake_list(url, playlistend=None):
        calls.append((url, playlistend))
        if url.endswith("/streams"):
            return {}, [], None
        return {}, [{"id": "aaaaaaaaaaa", "title": "Ep 1", "duration": 3600, "views": 12000, "rel": "2d ago"}], None

    monkeypatch.setattr(ytdlp_fetch, "list_tab", fake_list)
    collect.daily(now=NOW, fill_lengths=False)

    snap = json.loads((tmp_path / "snapshots" / "2026-10-26.json").read_text())
    src = snap["sources"]["UCabc"]
    assert src["ok"] and src["feed"] == "yt-dlp"
    assert src["videos"]["aaaaaaaaaaa"]["views"] == 12000
    cat = json.loads((tmp_path / "videos" / "UCabc.json").read_text())
    assert cat["videos"]["aaaaaaaaaaa"]["duration"] == 3600
    assert all(n == 30 for _, n in calls)
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["feeds"]["failed"] == 1 and status["feeds"]["listing_fallback"] == 1
