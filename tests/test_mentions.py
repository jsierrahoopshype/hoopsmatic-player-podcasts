from datetime import timedelta

from pp import chapters, guests, mentions, people, talk
from tests.helpers import NOW, cat, vid

INDEX = guests.PlayerIndex(["Victor Wembanyama", "LeBron James", "Kevin Durant", "Jayson Tatum", "Nikola Jokić",
                            "Charles Jones (1957)", "Charles Jones (1975)", "Jeff Teague", "Magic Johnson",
                            "Larry Bird", "Jaylen Brown"])
TEAMS = [{"slug": "boston-celtics", "name": "Boston Celtics", "nickname": "Celtics", "abbrev": "BOS",
          "names": ["Celtics"], "historical": []},
         {"slug": "oklahoma-city-thunder", "name": "Oklahoma City Thunder", "nickname": "Thunder", "abbrev": "OKC",
          "names": ["Thunder"], "historical": ["SuperSonics", "Sonics"]},
         {"slug": "philadelphia-76ers", "name": "Philadelphia 76ers", "nickname": "76ers", "abbrev": "PHI",
          "names": ["76ers", "Sixers"], "historical": []},
         {"slug": "orlando-magic", "name": "Orlando Magic", "nickname": "Magic", "abbrev": "ORL",
          "names": ["Magic"], "historical": []},
         {"slug": "miami-heat", "name": "Miami Heat", "nickname": "Heat", "abbrev": "MIA", "names": ["Heat"], "historical": []}]
NICK = {"Wemby": "victor-wembanyama", "KD": "kevin-durant", "Jokic": "nikola-jokic", "Bron": "lebron-james"}
ACTIVE = [["Jayson Tatum", "Tatum", "BOS"], ["Jaylen Brown", "Brown", "BOS"], ["Charles Jones", "Jones", "PHI"]]
M = mentions.Matcher(INDEX, NICK, TEAMS, ACTIVE)


def test_nicknames_match_as_written_or_all_caps_and_accents_do_not_matter():
    assert M.find("Wemby and KD talk")[0] == {"victor-wembanyama": "nickname", "kevin-durant": "nickname"}
    assert M.find("WEMBY IS HIM")[0] == {"victor-wembanyama": "nickname"}
    assert M.find("Jokić MVP again")[0] == {"nikola-jokic": "nickname"}
    assert M.find("Bronny and the kids")[0] == {}                     # whole words only
    assert M.find("kd is lowercase here")[0] == {}


def test_full_names_and_possessives():
    assert M.find("Kevin Durant's best season")[0] == {"kevin-durant": "name"}
    assert M.find("NIKOLA JOKIC DOMINATES")[0] == {"nikola-jokic": "name"}


def test_shared_names_and_lone_surnames_need_a_team_to_settle_them():
    players, _, unresolved = M.find("Charles Jones was a problem")
    assert players == {} and unresolved == [("Charles Jones", "name belongs to more than one Career Map player")]
    assert M.find("Charles Jones and the Sixers")[0] == {}             # active Charles Jones has no Career Map slug of his own
    players, teams, unresolved = M.find("Tatum is back")
    assert players == {} and unresolved[0][0] == "Tatum"
    players, teams, _ = M.find("Tatum and the Celtics are back")
    assert players == {"jayson-tatum": "surname+team"} and teams == {"boston-celtics"}
    assert M.find("Shannon Sharpe on Tatum's future")[2] == [("Tatum", "surname alone, no team in the same line settles who")]


def test_teams_by_nickname_never_by_city():
    assert M.find("Boston beats Oklahoma City")[1] == set()
    assert M.find("Sixers at Celtics")[1] == {"philadelphia-76ers", "boston-celtics"}
    assert M.find("Seattle SuperSonics memories")[1] == {"oklahoma-city-thunder"}
    assert M.find("Magic Johnson on Larry Bird")[1] == set()          # inside a player's name
    assert M.find("Steph's HEAT CHECK")[1] == set()
    assert M.find("Heat Culture is real")[1] == {"miami-heat"}


def test_chapter_lines():
    assert chapters.parse("Intro\n0:00 Intro\n12:30 - Wemby's debut\n(1:02:15) Celtics talk") == \
        [[0, "Intro"], [750, "Wemby's debut"], [3735, "Celtics talk"]]
    assert chapters.parse("Follow us\n3:30 one stray time") == []       # one line is not a chapter list
    assert chapters.parse("0:00 a\n1:5 bad\n2:00 b") == [[0, "a"], [120, "b"]]


SHOW = {"slug": "club", "name": "Club", "channel_id": "UCx", "type": "podcast",
        "hosts": [{"name": "Jeff Teague", "url": "https://hoopsmatic.com/nba-career-map/player/jeff-teague.html"}]}


def items_for(c):
    return [{"id": k, "show": "club", "fmt": "full" if v["duration"] >= 1200 else "clip", "published": v["published"],
             "views": v["views"], "duration": v["duration"], "title": v["title"]} for k, v in c["videos"].items()]


def test_hosts_and_guests_are_not_talked_about_in_their_own_videos():
    c = cat(vid(1, 100, title="Jeff Teague on KD and Wemby"), vid(2, 50, title="KD ft. Kevin Durant"))
    apps = {"x": {"video": "v01", "player": "kevin-durant", "show": "club"}}
    ms, _ = mentions.build([SHOW], {"UCx": c}, items_for(c), apps, M, manual={})
    assert {m["slug"] for m in ms["v00"]} == {"kevin-durant", "victor-wembanyama"}    # host Jeff Teague left out
    assert "v01" not in ms                                                             # KD is the guest there


def test_chapter_mentions_keep_their_time_and_the_title_wins():
    v = vid(1, 100, title="Episode 5")
    v["chapters"] = [[0, "Intro"], [750, "Wemby's debut"], [900, "More Wemby"]]
    c = cat(v)
    ms, _ = mentions.build([SHOW], {"UCx": c}, items_for(c), {}, M, manual={})
    assert ms["v00"] == [{"kind": "player", "slug": "victor-wembanyama", "src": "chapter", "t": 750, "how": "nickname"}]


def test_manual_file_wins():
    c = cat(vid(1, 100, title="KD talk"))
    manual = {"remove": [{"video": "v00", "player": "kevin-durant"}], "add": [{"video": "v00", "team": "boston-celtics", "t": 60}]}
    ms, _ = mentions.build([SHOW], {"UCx": c}, items_for(c), {}, M, manual=manual)
    assert ms["v00"] == [{"kind": "team", "slug": "boston-celtics", "src": "manual", "t": 60, "how": "manual"}]


def test_clips_of_one_episode_count_once():
    # A full episode and two clips posted after it, all about Wemby; one more episode later.
    vs = [vid(20, 1000, title="Episode 7: Wemby"), vid(19, 300, duration=600, title="Wemby clip"),
          vid(18, 200, duration=500, title="More Wemby"), vid(2, 900, title="Episode 8: Wemby again")]
    c = cat(*vs)
    items = items_for(c)
    ms, _ = mentions.build([SHOW], {"UCx": c}, items, {}, M, manual={})
    g = mentions.groups(ms, items, c["videos"])[("player", "victor-wembanyama")]
    assert len(g) == 2 and sorted(len(v) for v in g.values()) == [1, 3]
    t = talk.build(ms, mentions.groups(ms, items, c["videos"]), {it["id"]: it for it in items})
    groups = t[("player", "victor-wembanyama")]
    assert talk.window(groups, NOW, 30) == (2, 4)                  # 2 discussions, based on 4 videos
    first = [x for x in groups if len(x.items) == 3][0]
    assert first.lead["id"] == "v00" and len(first.clips) == 2     # the episode leads, clips under it


def test_player_pages_from_mentions_need_ten_discussions():
    class G:
        pass
    talk_map = {("player", "a"): [G()] * talk.MIN_TALK_PAGE, ("player", "b"): [G()] * (talk.MIN_TALK_PAGE - 1),
                ("team", "boston-celtics"): [G()] * 50, ("player", "host"): [G()] * 99}
    ps = {"host": {"slug": "host"}}
    people.add_talked_about(ps, talk_map, {"a": "A"})
    assert set(ps) == {"host", "a"} and ps["a"]["talk_only"] and "talk_only" not in ps["host"]
