import json
from datetime import timedelta

from pp import cards, config, history, home, videos
from tests.helpers import NOW


def it(i, days, views, fmt="full", show="s"):
    d = NOW - timedelta(days=days)
    return {"id": "v%03d" % i, "show": show, "fmt": fmt, "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "views": views, "duration": 3600 if fmt == "full" else 300, "title": "T%d" % i}


def test_breakout_needs_eight_videos_in_the_90_days_before():
    base = [it(i, 80 - i * 5, 1000) for i in range(8)]           # 8 full episodes, days 80..45 ago
    new = it(99, 1, 6000)
    s = videos.breakout_scores(base + [new])
    assert s["v099"] == 6.0                                          # 8 in the 90 days before it: median 1000
    assert all(s["v%03d" % i] is None for i in range(8))           # each had fewer than 8 before it


def test_breakout_compares_the_same_format_only():
    base = [it(i, 60 - i, 1000) for i in range(8)]
    clips = [it(50 + i, 50 - i, 50, fmt="clip") for i in range(3)]
    new_clip = it(98, 1, 500, fmt="clip")
    s = videos.breakout_scores(base + clips + [new_clip])
    assert s["v098"] is None                                         # only 3 clips before it: not enough data


def test_breakout_ignores_videos_older_than_90_days():
    old = [it(i, 200 + i, 10) for i in range(10)]
    new = it(99, 1, 500)
    assert videos.breakout_scores(old + [new])["v099"] is None


def test_gains_need_two_readings_with_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    today = NOW.date().isoformat()
    assert videos.gains(today, 1) is None
    history.write_daily(today, "t", {"UCa": {"a": 100, "b": 50, "c": 10, "d": 5}})
    history.write_daily((NOW - timedelta(days=1)).date().isoformat(), "t", {"UCa": {"a": 80}})
    assert videos.gains(today, 1) is None                           # yesterday read 1 of 4: too partial
    history.write_daily((NOW - timedelta(days=1)).date().isoformat(), "t", {"UCa": {"b": 40, "c": 9}})
    g = videos.gains(today, 1)
    assert g and g["day_then"] == "2026-10-25"
    item = {"id": "a", "published": "2026-10-01T00:00:00Z"}
    assert videos._gain(item, g) == 20
    assert videos._gain({"id": "d", "published": "2026-10-26T01:00:00Z"}, g) == 5      # new since: all its views
    assert videos._gain({"id": "zz", "published": "2026-10-01T00:00:00Z"}, g) is None


def ctx_for():
    return {"shows": {"s": {"slug": "s", "name": "Show S", "hosts": [{"name": "Jeff Teague",
                                                                       "url": "https://hoopsmatic.com/nba-career-map/player/jeff-teague.html"},
                                                                      {"name": "B Hen", "url": None}]}},
            "thumbs": {"v001"}, "thumbs_big": set(), "headshots": {"jeff-teague"}}


def test_card_plays_in_page_only_on_click_and_always_links_youtube():
    c = cards.video_card(dict(it(1, 2, 1234), embed="ok"), ctx_for())
    assert 'data-play="v001"' in c and 'href="https://www.youtube.com/watch?v=v001"' in c
    assert "<iframe" not in c and "youtube-nocookie" not in c      # nothing from YouTube until a click
    assert 'src="/player-podcasts/thumbs/v001.webp"' in c
    assert ">Full episode<" in c and "1,234 views" in c
    assert '<img class="av" src="/player-podcasts/headshots/jeff-teague.webp"' in c
    assert '<span class="av av-i" aria-hidden="true">BH</span>B Hen' in c
    assert "Watch on YouTube" in c


def test_non_embeddable_video_gets_a_link_not_a_play_button():
    c = cards.video_card(dict(it(2, 2, 10), embed="no"), ctx_for())
    assert "data-play" not in c and "vc-noembed" in c and "Watch on YouTube" in c


def test_stream_files_are_chunked():
    stream = [dict(it(i, i * 0.5, 1000 - i), embed="ok") for i in range(60)]
    files, ver = home.stream_files(stream, ctx_for(), {"g24": False})
    meta = json.loads(files["data/stream-meta.json"])
    assert meta["tabs"] == {"latest": 3, "views": 3}                 # 60 videos, 24 per chunk; no Trending yet
    assert len(json.loads(files["data/stream-latest-0.json"])) == 24
    assert len(json.loads(files["data/stream-latest-2.json"])) == 12
    assert len(json.loads(files["data/stream-index.json"])) == 60
    assert meta["v"] == ver and meta["shows"][0][0] == "s"


def test_home_sections_hide_trending_without_snapshots():
    items = [dict(it(i, i * 0.4, 100 * i), embed="ok") for i in range(1, 20)]
    h = home.sections(items, NOW, {"g24": False, "g7": False})
    assert h["trending"] == [] and h["watch"]["views"] == 500          # most viewed of the last 48h (v005: exactly 2 days, included)
    assert all((NOW - __import__("pp.util", fromlist=["parse_ts"]).parse_ts(x["published"])).days <= 7 for x in h["week"])
