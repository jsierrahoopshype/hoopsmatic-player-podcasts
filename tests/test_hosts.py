import json

from pp import render, roster


def test_hosts_render_linked_and_plain():
    show = {"hosts": [{"name": "Jeff Teague", "url": "https://hoopsmatic.com/nba-career-map/player/jeff-teague.html"},
                      {"name": "B Hen", "url": None}]}
    assert render.hosts_line(show) == "Jeff Teague, B Hen"
    assert render.hosts_html(show) == ('<a class="host" href="https://hoopsmatic.com/nba-career-map/player/'
                                       'jeff-teague.html">Jeff Teague</a>, B Hen')
    assert render.hosts_html({"hosts": ["Old Style"]}) == "Old Style"


def test_every_host_in_the_roster_is_a_name_and_url_record():
    for s in roster.load_roster():
        for h in s["hosts"]:
            assert set(h) == {"name", "url"}, (s["slug"], h)
            assert h["url"] is None or h["url"].startswith("https://hoopsmatic.com/nba-career-map/player/")


def test_boardroom_is_excluded_and_the_etcs_is_not():
    shows = {s["slug"]: s for s in roster.load_roster()}
    assert shows["boardroom"]["exclude_reason"] == "network channel, not a player podcast"
    assert "exclude_reason" not in shows["the-etcs"]
    assert shows["the-etcs"]["channel_id"] == shows["boardroom"]["channel_id"]
