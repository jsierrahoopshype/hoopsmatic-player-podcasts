from pp import guests
from tests.helpers import cat, vid

INDEX = guests.PlayerIndex(["Kevin Garnett", "Jamal Crawford", "James Johnson", "Kevin Durant", "Isiah Thomas",
                            "Charles Jones (1957)", "Charles Jones (1975)", "Michael Jordan", "Tyrese Haliburton",
                            "Shaquille O'Neal"])


def show(hosts=("Jeff Teague",), slug="club-520"):
    return {"slug": slug, "name": "Club 520", "channel_id": "UCx", "type": "podcast",
            "hosts": [{"name": h, "url": None} for h in hosts]}


def run(titles, hosts=("Jeff Teague",), manual=None, durations=None):
    vids = [vid(i + 1, 100 + i, title=t, duration=(durations or {}).get(i, 3600)) for i, t in enumerate(titles)]
    c = cat(*vids)
    return guests.build([show(hosts)], {"UCx": c}, index=INDEX, manual=manual or {}), c


def test_explicit_patterns_confirm_a_matched_player():
    (conf, review), _ = run(["Club 520 ft. James Johnson & Jamal Crawford",
                             "Kevin Garnett joins the crew | Ep 4",
                             "Guest: Shaquille O'Neal",
                             "Season finale with Tyrese Haliburton"])
    got = sorted((it["player"], it["how"]) for it in conf.values())
    assert got == [("jamal-crawford", "ft."), ("james-johnson", "ft."), ("kevin-garnett", "joins"),
                   ("shaquille-o-neal", "guest:"), ("tyrese-haliburton", "with")]


def test_mentions_without_a_pattern_go_to_review_not_the_site():
    (conf, review), _ = run(["Kevin Garnett | Hooping with MICHAEL JORDAN"])
    assert conf == {}
    names = sorted(it["player"] for it in review.values())
    assert names == ["kevin-garnett", "michael-jordan"]
    assert all(it["reason"].startswith("named in the title") for it in review.values())


def test_same_name_players_are_never_auto_confirmed():
    (conf, review), _ = run(["Club 520 ft. Charles Jones"])
    assert conf == {}
    assert [it["reason"] for it in review.values()] == ["name belongs to more than one Career Map player"]


def test_hosts_are_not_guests():
    (conf, _), _ = run(["Isiah Thomas Joins The ETCs with Kevin Durant"], hosts=("Kevin Durant",))
    assert [it["player"] for it in conf.values()] == ["isiah-thomas"]


def test_manual_file_adds_and_removes():
    manual = {"add": [{"video": "v00", "player": "michael-jordan"}],
              "remove": [{"video": "v01", "player": "jamal-crawford"}]}
    (conf, review), _ = run(["Kevin Garnett | Hooping with MICHAEL JORDAN", "Club 520 ft. Jamal Crawford"], manual=manual)
    assert sorted((it["video"], it["player"], it["how"]) for it in conf.values()) == [("v00", "michael-jordan", "manual")]
    assert not any(it["player"] == "michael-jordan" and it["video"] == "v00" for it in review.values())


def test_clips_of_one_episode_count_once():
    # helpers.vid(days_ago): v00 is 1 day old, v01 2 days, v02 3 days: the full episode is the oldest
    # and both clips came out within 10 days after it.
    titles = ["James Johnson clip 2 ft. James Johnson", "James Johnson clip 1 ft. James Johnson",
              "Full episode ft. James Johnson"]
    (conf, _), _ = run(titles, durations={0: 300, 1: 300, 2: 3600})
    groups = {it["video"]: it["group"] for it in conf.values()}
    assert len(set(groups.values())) == 1
    assert guests.appearance_count(conf, "james-johnson") == 1


def test_episode_numbers_group_and_separate():
    assert guests.episode_number("Dawg Talk EP57") == "e57"
    assert guests.episode_number("Knuckleheads Podcast S8: EP6") == "s8e6"
    assert guests.episode_number("Ep. 12 | Guest") == "e12"
    assert guests.episode_number("The #2 Pick talks") is None


def test_description_link_groups_a_clip_with_its_episode():
    vids = [vid(1, 10, title="Full ft. Jamal Crawford"), vid(40, 10, title="Old clip ft. Jamal Crawford", duration=300)]
    vids[1]["desc"] = "Full episode: https://youtu.be/v00xxxxxxxx"
    c = {"videos": {"v00xxxxxxxx": vids[0], "v01": vids[1]}}
    conf, _ = guests.build([show()], {"UCx": c}, index=INDEX, manual={})
    assert len({it["group"] for it in conf.values()}) == 1


def test_with_counts_only_as_a_guest_line():
    (conf, review), _ = run(["Jeff Teague REACTS to Lakers being CAUTIOUS with Kevin Durant this season | Club 520",
                             "Why working out with Kevin Garnett is a BAD thing",
                             "Jeff Teague on Lakers since pairing Isiah Thomas with Jamal Crawford | Club 520",
                             "Club 520 Podcast w/ Tyrese Haliburton",
                             "With Michael Jordan | Episode 3"])
    assert sorted(it["player"] for it in conf.values()) == ["michael-jordan", "tyrese-haliburton"]
    assert {"kevin-durant", "kevin-garnett", "jamal-crawford"} <= {it["player"] for it in review.values()}


def test_former_hosts_are_not_guests_of_their_own_show():
    s = dict(show(), former_hosts=[{"name": "Kevin Durant", "url": None}])
    c = cat(vid(1, 100, title="The Club 520 Podcast w/ Kevin Durant"))
    conf, _ = guests.build([s], {"UCx": c}, index=INDEX, manual={})
    assert conf == {}


def test_someone_in_ten_episodes_is_a_regular_not_a_guest():
    titles = ["Episode %d ft. Jamal Crawford" % i for i in range(guests.REGULAR_MIN)] + ["Ep 99 ft. Kevin Garnett"]
    # One full episode per 20 days so none share a group.
    vids = [vid(1 + 20 * i, 100, title=t) for i, t in enumerate(titles)]
    conf, review = guests.build([show()], {"UCx": cat(*vids)}, index=INDEX, manual={})
    assert [it["player"] for it in conf.values()] == ["kevin-garnett"]
    regular = [it for it in review.values() if it["player"] == "jamal-crawford"]
    assert len(regular) == guests.REGULAR_MIN and "regular" in regular[0]["reason"]


def test_joins_takes_only_the_names_right_before_it():
    (conf, _), _ = run(["EP. 2 - Danny Meets the Raps & Kevin Durant, Michael Jordan Joins the Pod"])
    assert [it["player"] for it in conf.values()] == ["michael-jordan"]


def test_former_hosts_are_not_review_mentions_on_their_own_show():
    s = dict(show(), former_hosts=[{"name": "Kevin Durant", "url": None, "note": "season one"}])
    c = cat(vid(1, 100, title="What Makes a Great Player? | Kevin Durant & Jeff Teague | Full Episode"))
    conf, review = guests.build([s], {"UCx": c}, index=INDEX, manual={})
    assert conf == {} and not any(it["player"] == "kevin-durant" for it in review.values())
