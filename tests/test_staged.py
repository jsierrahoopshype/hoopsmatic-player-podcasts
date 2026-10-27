from datetime import timedelta

from pp import build, history, people, render
from tests.helpers import NOW


def it(i, show, days=5, views=100):
    d = NOW - timedelta(days=days)
    return {"id": "v%03d" % i, "show": show, "fmt": "full", "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "views": views, "duration": 3700, "title": "T%d" % i}


SHOWS = {"a": {"slug": "a", "name": "A", "type": "podcast",
               "hosts": [{"name": "Al Host", "url": "https://hoopsmatic.com/nba-career-map/player/al-host.html"},
                         {"name": "No Page", "url": None}]},
         "b": {"slug": "b", "name": "B", "type": "podcast",
               "hosts": [{"name": "Bo Small", "url": "https://hoopsmatic.com/nba-career-map/player/bo-small.html"}]}}
ITEMS = {"a": [it(i, "a") for i in range(5)], "b": [it(10 + i, "b") for i in range(2)]}


def app(vid, player, show="a", group=None):
    return {"video": vid, "player": player, "show": show, "group": group or "%s/v:%s" % (show, vid)}


def test_player_pages_need_three_appearances_or_a_show_with_three_videos():
    apps = {"1": app("v000", "gus"), "2": app("v001", "gus"), "3": app("v002", "gus"),
            "4": app("v000", "two"), "5": app("v001", "two"),
            # three videos but two are clips of one episode: 2 appearances
            "6": app("v000", "grp", group="a/ep:1"), "7": app("v001", "grp", group="a/ep:1"), "8": app("v002", "grp"),
            # an appearance in a video the site does not show does not count
            "9": app("v000", "off"), "10": app("v001", "off"), "11": app("gone1", "off")}
    ps = people.build(SHOWS, ["a", "b"], ITEMS, apps, {"gus": "Gus", "two": "Two"})
    assert set(ps) == {"al-host", "gus"}                    # Bo's show has 2 videos; No Page has no Career Map slug
    assert ps["al-host"]["hosts"] == ["a"] and ps["gus"]["groups"] == 3


def test_names_link_to_the_player_page_when_there_is_one_else_career_map():
    ps = {"gus": {}}
    assert people.link_for("gus", ps) == "/player-podcasts/players/gus/"
    assert people.link_for("bo", ps) == "https://hoopsmatic.com/nba-career-map/player/bo.html"
    people.CURRENT = ps
    try:
        assert people.host_link("https://hoopsmatic.com/nba-career-map/player/gus.html") == "/player-podcasts/players/gus/"
        assert people.host_link(None) is None
    finally:
        people.CURRENT = {}


def test_related_shows_prefer_same_type_then_shared_guests():
    shown = [{"slug": s, "type": t} for s, t in (("a", "podcast"), ("b", "podcast"), ("c", "podcast"),
                                                    ("d", "player_channel"), ("e", "podcast"))]
    m = {s["slug"]: {"x": {"typf": [1000, 3]}} for s in shown}
    m["e"]["x"]["typf"] = [1100, 3]
    apps = {"1": app("x", "kd", "a"), "2": app("y", "kd", "c")}
    rel = build.related_shows(shown, apps, m)
    assert rel["a"][0] == "c"                               # shares a guest
    assert "d" not in rel["a"]                              # other type last
    assert len(rel["a"]) == 3


def test_structured_data_for_videos_and_breadcrumbs():
    assert render.iso_duration(3725) == "PT1H2M5S" and render.iso_duration(59) == "PT59S"
    ctx = {"shows": {"a": {"name": "A"}}, "thumbs": {"v001"}}
    v = render.video_ld(dict(it(1, "a"), views=42), ctx)
    assert v["@type"] == "VideoObject" and v["thumbnailUrl"].startswith("https://hoopsmatic.com/player-podcasts/thumbs/")
    assert v["embedUrl"] == "https://www.youtube-nocookie.com/embed/v001"
    assert v["interactionStatistic"]["userInteractionCount"] == 42
    bc = render.breadcrumbs_ld([("HoopsMatic", "https://hoopsmatic.com/"), ("A", "https://hoopsmatic.com/x/")])
    assert [x["position"] for x in bc["itemListElement"]] == [1, 2]


def test_views_history_waits_for_three_weekly_readings(tmp_path, monkeypatch):
    monkeypatch.setattr(history.config, "SNAPSHOTS_DIR", tmp_path)
    history.write_weekly("2026-10-12", {"s": {"a": 10, "b": 5}})
    history.write_weekly("2026-10-19", {"s": {"a": 20, "b": 6}})
    assert render.weekly_history(["a", "b"]) == []
    history.write_weekly("2026-10-26", {"s": {"a": 30, "b": 9, "new": 1}})
    assert render.weekly_history(["a", "b", "new"]) == [("2026-10-12", 15), ("2026-10-19", 26), ("2026-10-26", 39)]


def test_description_drops_links_and_emails():
    t = render._clean_desc("Best show. Business: deals@x.com https://x.com/y " + "word " * 100)
    assert "@" not in t and "http" not in t and t.endswith("…") and len(t) <= 330


def test_embed_run_with_too_many_gone_answers_is_ignored(tmp_path, monkeypatch):
    from pp import embed
    monkeypatch.setattr(embed.config, "EMBED_FILE", tmp_path / "embed.json")
    monkeypatch.setattr(embed, "_check", lambda vid: "gone")
    cache = embed.update(["v%02d" % i for i in range(30)], "2026-10-27")
    assert cache == {}                                      # 30 of 30 "gone": a refusing server, not 30 deleted videos
    monkeypatch.setattr(embed, "_check", lambda vid: "gone" if vid == "v00" else "ok")
    cache = embed.update(["v%02d" % i for i in range(30)], "2026-10-27")
    assert cache["v00"][0] == "gone" and cache["v01"][0] == "ok"
    monkeypatch.setattr(embed, "_check", lambda vid: "no")
    cache = embed.update(["w%02d" % i for i in range(30)], "2026-10-27")
    assert not any(k.startswith("w") for k in cache)        # mass "embedding off": ignored too
