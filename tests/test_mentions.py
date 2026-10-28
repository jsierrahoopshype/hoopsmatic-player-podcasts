from datetime import timedelta

from pp import chapters, guests, mentions, people, talk
from tests.helpers import NOW, cat, vid

INDEX = guests.PlayerIndex(["Gary Payton", "Gary Payton II", "Victor Wembanyama", "LeBron James", "Kevin Durant",
                            "Jayson Tatum", "Earl Tatum", "Nikola Jokić", "Charles Jones (1957)", "Charles Jones (1975)",
                            "Jeff Teague", "Magic Johnson", "Larry Bird", "Jaylen Brown", "Jonathan Kuminga",
                            "Jaren Jackson", "Jaren Jackson Jr", "Tim Hardaway", "Tim Hardaway Jr", "Richard Jefferson",
                            "Tyus Battle", "Kelly Oubre", "Shai Gilgeous-Alexander", "Matt Guokas, Sr.", "Matt Guokas", "Michael Porter"])
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
M = mentions.Matcher(INDEX, NICK, TEAMS, ACTIVE, always_review=["Tim Hardaway", "Kelly Oubre"], stopwords=["battle"])


def test_nicknames_match_as_written_or_all_caps_and_accents_do_not_matter():
    assert M.find("Wemby and KD talk")[0] == {"victor-wembanyama": "nickname", "kevin-durant": "nickname"}
    assert M.find("WEMBY IS HIM")[0] == {"victor-wembanyama": "nickname"}
    assert M.find("Jokić MVP again")[0] == {"nikola-jokic": "nickname"}
    assert M.find("Bronny and the kids")[0] == {}                     # whole words only
    assert M.find("kd is lowercase here")[0] == {}


def test_full_names_and_possessives():
    assert M.find("Kevin Durant's best season")[0] == {"kevin-durant": "name"}
    assert M.find("NIKOLA JOKIC DOMINATES")[0] == {"nikola-jokic": "name"}


def test_shared_names_and_shared_surnames_need_a_team_to_settle_them():
    players, _, unresolved = M.find("Charles Jones was a problem")
    assert players == {} and unresolved == [("Charles Jones", "name belongs to more than one Career Map player")]
    assert M.find("Charles Jones and the Sixers")[0] == {}             # active Charles Jones has no Career Map slug of his own
    # Tatum: Jayson and Earl, so a lone "Tatum" needs his team alongside
    players, teams, unresolved = M.find("Tatum is back")
    assert players == {} and unresolved == [("Tatum", "surname shared by more than one Career Map player, no team settles who")]
    players, teams, _ = M.find("Tatum and the Celtics are back")
    assert players == {"jayson-tatum": "surname+team"} and teams == {"boston-celtics"}


def test_a_written_suffix_matches_only_the_player_with_it():
    assert M.find("Jaren Jackson Jr. Gets Real On the Grizzlies")[0] == {"jaren-jackson-jr": "name+suffix"}
    assert M.find("JAREN JACKSON JR TALKS")[0] == {"jaren-jackson-jr": "name+suffix"}
    assert M.find("Tim Hardaway Jr. on the Mavs")[0] == {"tim-hardaway-jr": "name+suffix"}
    # the father is filed without a suffix: "Sr." means him
    assert M.find("Tim Hardaway Sr. CALLS OUT Gil's Arena")[0] == {"tim-hardaway": "name+suffix"}
    assert M.find("Matt Guokas Sr. remembers")[0] == {"matt-guokas-sr": "name+suffix"}
    assert M.find("Warriors title reaction w/ Gary Payton II")[0] == {"gary-payton-ii": "name+suffix"}
    # Career Map files Michael Porter Jr. without the suffix: the one Michael Porter
    assert M.find("Michael Porter Jr. drops 40")[0] == {"michael-porter": "name+suffix"}
    assert all(not u for u in (M.find("Jaren Jackson Jr. & Ja")[2],))   # never to review


def test_a_plain_father_and_son_name_means_the_one_without_a_suffix():
    assert M.find("Vernon Maxwell's Gary Payton Fight Story")[0] == {"gary-payton": "name (no suffix)"}
    assert M.find("Jaren Jackson on the 90s Rockets")[0] == {"jaren-jackson": "name (no suffix)"}
    assert M.find("Matt Guokas on the 76ers")[0] == {"matt-guokas": "name (no suffix)"}


def test_names_on_the_always_review_list_go_to_review_without_a_suffix():
    players, _, unresolved = M.find("Tim Hardaway SNAPS On Gil's Arena")
    assert players == {} and unresolved == [("Tim Hardaway", "name on the always-review list (written without a suffix)")]
    players, _, unresolved = M.find("Kelly Oubre drops 30")
    assert players == {} and unresolved[0][0] == "Kelly Oubre"
    assert M.find("Tim Hardaway Jr. drops 30")[0] == {"tim-hardaway-jr": "name+suffix"}


def test_a_surname_of_exactly_one_player_matches_on_its_own():
    assert M.find("KUMINGA TURNED DOWN THE LAKERS")[0] == {"jonathan-kuminga": "surname (one player)"}
    assert M.find("Draymond on Recruiting Durant")[0] == {"kevin-durant": "surname (one player)"}
    assert M.find("Finals X-Factors: Gilgeous-Alexander vs the field")[0] == {"shai-gilgeous-alexander": "surname (one player)"}
    assert M.find("Battle for the West")[0] == {}                       # an everyday word: never on its own
    assert M.find("Battle for the West")[2] == []


def test_lone_first_names_are_ignored_unless_a_nickname():
    assert M.find("The Story of Richard & Kenyon's Locker Room Fight") == ({}, set(), [])
    assert M.find("Jaren and Tim talk") == ({}, set(), [])
    assert M.find("Bron and Jokic")[0] == {"lebron-james": "nickname", "nikola-jokic": "nickname"}
    # a first name before a surname is someone else ("Shannon Sharpe")
    assert M.find("Shannon Sharpe on the Celtics")[0] == {}


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


def test_mentions_file_is_written_in_a_stable_order(tmp_path, monkeypatch):
    import json
    from pp import build, config
    monkeypatch.setattr(config, "MENTIONS_FILE", tmp_path / "m.json")
    ms = {"v1": [{"kind": "team", "slug": "san-antonio-spurs", "src": "title", "t": None, "how": "nickname"},
                 {"kind": "team", "slug": "new-york-knicks", "src": "title", "t": None, "how": "nickname"}]}
    build.write_mentions({"mentions": ms})
    first = (tmp_path / "m.json").read_text()
    ms["v1"].reverse()
    build.write_mentions({"mentions": ms})
    assert (tmp_path / "m.json").read_text() == first
    assert json.loads(first)["items"]["v1"][0][1] == "new-york-knicks"


# ── data files and defaults (Oct 28 follow-up) ──

def _real(name):
    import json
    from pp import config
    return json.load(open(getattr(config, name)))


def test_always_review_list_keeps_jackson_and_trent_but_not_oubre():
    names = _real("ALWAYS_REVIEW_FILE")["names"]
    assert "Jaren Jackson" in names and "Gary Trent" in names and "Kelly Oubre" not in names
    m = mentions.Matcher(INDEX, NICK, TEAMS, ACTIVE, always_review=names)
    assert m.find("Kelly Oubre drops 30")[0] == {"kelly-oubre": "name"}           # the one Kelly Oubre on Career Map
    assert m.find("Jaren Jackson on the 2022 Grizzlies")[0] == {}


def test_wade_alone_means_dwyane_wade_but_never_on_his_own_show():
    assert _real("NICKNAMES_FILE")["names"]["Wade"] == "dwyane-wade"
    idx = guests.PlayerIndex(["Dwyane Wade", "Dean Wade", "Wade Baldwin", "James Harden"])
    m = mentions.Matcher(idx, {"Wade": "dwyane-wade"}, TEAMS, [])
    assert m.find("Jeff Teague Sparks HEATED Wade vs. Harden debate")[0] == {"dwyane-wade": "nickname",
                                                                         "james-harden": "surname (one player)"}
    assert m.find("Dean Wade drops 20")[0] == {"dean-wade": "name"}                 # a full name wins
    assert m.find("Wade Baldwin on his rookie year")[0] == {"wade-baldwin": "name"}
    show = {"slug": "dwyane-wade", "name": "Dwyane Wade", "channel_id": "UCx", "type": "player_channel",
            "hosts": [{"name": "Dwyane Wade", "url": "https://hoopsmatic.com/nba-career-map/player/dwyane-wade.html"}]}
    c = cat(vid(1, 100, title="Wade on the 2006 Finals and Harden"))
    ms, _ = mentions.build([show], {"UCx": c}, items_for(c), {}, m, manual={})
    assert [x["slug"] for x in ms["v00"]] == ["james-harden"]                        # not himself


def test_poole_and_middleton_can_match_alone_castle_cannot():
    words = set(_real("SURNAME_STOPWORDS_FILE")["words"])
    assert "poole" not in words and "middleton" not in words and "castle" in words
    idx = guests.PlayerIndex(["Jordan Poole", "Khris Middleton", "Stephon Castle"])
    m = mentions.Matcher(idx, {}, TEAMS, [], stopwords=words)
    assert m.find("Draymond vs Poole, Middleton to the Wizards")[0] == {"jordan-poole": "surname (one player)",
                                                                     "khris-middleton": "surname (one player)"}
    assert m.find("Castle's 40 piece")[0] == {}


def test_defaults_only_where_the_name_would_go_to_review():
    defaults = {"Tatum": {"player": "jayson-tatum", "why": "x"}, "Charles Jones": {"player": "charles-jones-1975", "why": "x"},
                "Tim Hardaway": {"player": "tim-hardaway", "why": "x"}}
    m = mentions.Matcher(INDEX, NICK, TEAMS, ACTIVE, always_review=["Tim Hardaway"], defaults=defaults)
    assert m.find("Tatum a Hall of Famer?") == ({"jayson-tatum": "default"}, set(), [])
    assert m.find("Tatum and the Celtics")[0] == {"jayson-tatum": "surname+team"}     # a team still settles it first
    assert m.find("Charles Jones was a problem")[0] == {"charles-jones-1975": "default"}
    players, _, unresolved = m.find("Tim Hardaway SNAPS")                            # always-review: never a default
    assert players == {} and unresolved[0][0] == "Tim Hardaway"
    assert m.find("Earl Tatum in 1977")[0] == {"earl-tatum": "name"}                 # a full name is not overridden


def test_defaults_file_points_at_real_players_and_skips_the_ambiguous_ones():
    d = _real("SURNAME_DEFAULTS_FILE")["defaults"]
    idx = guests.PlayerIndex.load()
    assert all(v["player"] in idx.display and v["why"] for v in d.values())
    assert d["Tatum"]["player"] == "jayson-tatum" and d["Barkley"]["player"] == "charles-barkley"
    assert d["Larry Johnson"]["player"] == "larry-johnson-1969"
    for name in ("Beasley", "Bogdanovic", "Wiggins", "Harris", "Johnson", "Hardaway", "Boozer", "Sabonis", "Mobley"):
        assert name not in d


# ── sticky pages and ignored names (Oct 28) ──

def test_ignored_names_are_never_a_player_nor_review():
    idx = guests.PlayerIndex(["Michael Jackson", "Jaren Jackson Jr", "Mark Jackson (1965)", "Stephen Jackson"])
    m = mentions.Matcher(idx, {}, TEAMS, [], ignore=["Michael Jackson"])
    assert m.find("Kobe on Michael Jackson and Thriller") == ({}, set(), [])          # not the player, no review
    assert m.find("MICHAEL JACKSON MOVES") == ({}, set(), [])
    assert m.find("Stephen Jackson on the Warriors")[0] == {"stephen-jackson": "name"}
    assert "Michael Jackson" in _real("MENTION_IGNORE_FILE")["names"]


def test_published_pages_stay_when_a_player_falls_under_the_threshold():
    names = {"og-anunoby": "OG Anunoby", "michael-jackson": "Michael Jackson", "a": "A"}
    apps = {"x": {"video": "v1", "player": "og-anunoby", "show": "s", "group": "s/v:v1"}}
    ps = {"a": {"slug": "a", "talk_only": True}, "michael-jackson": {"slug": "michael-jackson", "talk_only": True}}
    people.keep_published(ps, ["og-anunoby", "michael-jackson", "gone-from-career-map"], names, apps, {"v1"},
                          ignored={"michael-jackson"})
    assert ps["og-anunoby"]["sticky"] and ps["og-anunoby"]["groups"] == 1          # kept, with what there is
    assert "michael-jackson" not in ps                                              # ignored: removed, never kept
    assert "gone-from-career-map" not in ps
    assert "a" in ps
