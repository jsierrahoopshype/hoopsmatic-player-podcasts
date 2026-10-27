import json

from pp import collect, config, feeds, ytdlp_fetch
from tests.helpers import NOW


def setup(tmp_path, monkeypatch):
    roster = {"shows": [{"slug": "s", "name": "S", "channel_id": "UCabc", "hosts": [], "youtube_url": "u",
                         "type": "podcast"}]}
    (tmp_path / "channels.json").write_text(json.dumps(roster))
    for name in ("CHANNELS_FILE", "STATUS_FILE", "SUBSCRIBERS_FILE"):
        monkeypatch.setattr(config, name, tmp_path / getattr(config, name).name)
    monkeypatch.setattr(config, "VIDEOS_DIR", tmp_path / "videos")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(feeds, "fetch_source", lambda src: {"ok": False, "feed": None, "title": None, "videos": [],
                                                             "error": "UULF: HTTP Error 404: Not Found"})
    monkeypatch.setattr(feeds, "fetch_shorts", lambda src: [])


def test_daily_lists_recent_uploads_and_writes_a_compact_snapshot(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    tabs = {
        "/videos": [{"id": "aaaaaaaaaaa", "title": "Ep 1", "duration": 3600, "views": 12000, "rel": "2d ago"},
                    {"id": "bbbbbbbbbbb", "title": "Clip", "duration": 300, "views": 900, "rel": "3d ago"},
                    {"id": "ccccccccccc", "title": "Old", "duration": 3600, "views": 5, "rel": "5mo ago"}],
        "/streams": [],
        "/shorts": [{"id": "ddddddddddd", "title": "Short", "duration": None, "views": 77, "rel": None}],
    }
    calls = []

    def fake_list(url, playlistend=None, stop=None):
        calls.append(url)
        out = []
        for e in tabs[url[url.rindex("/"):]]:
            out.append(e)
            if stop and stop(out):
                break
        return {}, out, None

    monkeypatch.setattr(ytdlp_fetch, "list_tab", fake_list)
    collect.daily(now=NOW)

    snap = json.loads((tmp_path / "snapshots" / "daily" / "2026-10-26.json").read_text())
    # only the last 90 days, one number per video, no titles or dates repeated
    assert snap["v"] == {"UCabc": {"aaaaaaaaaaa": 12000, "bbbbbbbbbbb": 900}}
    cat = json.loads((tmp_path / "videos" / "UCabc.json").read_text())
    assert cat["videos"]["ddddddddddd"]["tab"] == "shorts"
    assert cat["shorts_since"] == "2026-10-26"
    assert "published" not in cat["videos"]["ddddddddddd"]       # first Shorts listing: no date guessed
    assert {c.rsplit("/", 1)[1] for c in calls} == {"videos", "streams", "shorts"}
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["last_success"] == "2026-10-26T12:00:00Z"


def test_a_new_short_after_the_first_listing_is_dated_from_first_sight(tmp_path, monkeypatch):
    from datetime import timedelta
    setup(tmp_path, monkeypatch)
    shorts = [{"id": "ddddddddddd", "title": "Short", "duration": None, "views": 77, "rel": None}]
    monkeypatch.setattr(ytdlp_fetch, "list_tab",
                        lambda url, playlistend=None, stop=None: ({}, shorts if url.endswith("/shorts") else [], None))
    collect.daily(now=NOW)
    shorts.insert(0, {"id": "eeeeeeeeeee", "title": "New Short", "duration": None, "views": 5, "rel": None})
    collect.daily(now=NOW + timedelta(days=1))
    cat = json.loads((tmp_path / "videos" / "UCabc.json").read_text())
    assert cat["videos"]["eeeeeeeeeee"]["published"] == "2026-10-27T00:00:00Z"
    assert "published" not in cat["videos"]["ddddddddddd"]


def test_complete_listing_marks_missing_videos_gone(tmp_path, monkeypatch):
    from datetime import timedelta
    setup(tmp_path, monkeypatch)
    vids = [{"id": "v%010d" % i, "title": "Ep %d" % i, "duration": 3600, "views": 100, "rel": "%dd ago" % (i + 1)}
            for i in range(10)]
    monkeypatch.setattr(ytdlp_fetch, "list_tab",
                        lambda url, playlistend=None, stop=None: ({}, list(vids) if url.endswith("/videos") else [], None))
    collect.daily(now=NOW)
    del vids[3]
    collect.daily(now=NOW + timedelta(days=1))
    cat = json.loads((tmp_path / "videos" / "UCabc.json").read_text())
    assert cat["videos"]["v0000000003"]["gone"] == "2026-10-27"
    assert not any(v.get("gone") for k, v in cat["videos"].items() if k != "v0000000003")
