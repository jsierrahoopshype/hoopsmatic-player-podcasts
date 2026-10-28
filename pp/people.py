"""Player pages: /player-podcasts/players/<Career Map slug>/.

A player gets a page with 3 or more confirmed guest appearances (clips of
the same episode count once), or as a host of a show on the site with 3 or
more videos, or (without either) when 10 or more discussions on the site
talk about him (pp/talk.py; such a page is "talk_only"). Once published, a
page stays (data/published_players.json) even if the player falls under
these thresholds later: they only decide creation. Only players with a Career Map slug qualify (it is the page's
address). Everywhere else on the site, a player's name links to this page
when there is one, and to their NBA Career Map page otherwise.
"""
from . import config
from .guests import appearance_count

# The players with a page in this build (set by the build before rendering),
# so every place that links a player name can point at that page.
CURRENT = {}

MIN_APPEARANCES = 3
MIN_SHOW_VIDEOS = 3
CAREER_MAP = "https://hoopsmatic.com/nba-career-map/player/%s.html"


def slug_from_url(url):
    if not url or "/nba-career-map/player/" not in url:
        return None
    return url.rstrip("/").rsplit("/", 1)[-1].replace(".html", "")


def page_url(slug):
    return config.BASE_PATH + "/players/" + slug + "/"


def build(shows, shown, items_by_show, appearances, names):
    """-> {slug: {"slug", "name", "hosts": [show slugs], "former": [show slugs],
    "guest": [appearance items], "groups": n}} for every player with a page.

    shows: {slug: roster record}; shown: show slugs on the site;
    items_by_show: {show slug: [video items]}; appearances: confirmed guests;
    names: Career Map display names by slug."""
    people = {}

    def person(slug, name):
        return people.setdefault(slug, {"slug": slug, "name": name or names.get(slug, slug), "hosts": [],
                                        "former": [], "guest": [], "groups": 0})

    for s in sorted(shown):
        show = shows[s]
        for key, role in (("hosts", "hosts"), ("former_hosts", "former")):
            for h in show.get(key) or []:
                if not isinstance(h, dict):
                    continue
                slug = slug_from_url(h.get("url"))
                if slug and len(items_by_show.get(s, [])) >= MIN_SHOW_VIDEOS:
                    person(slug, h["name"])[role].append(s)
    # Only appearances in videos the site shows (dated, not deleted) count.
    on_site = {it["id"] for s in shown for it in items_by_show.get(s, [])}
    guests = {}
    for it in appearances.values():
        if it["video"] in on_site:
            guests.setdefault(it["player"], []).append(it)
    for slug, apps in guests.items():
        n = appearance_count({k: a for k, a in enumerate(apps)}, slug)
        if n >= MIN_APPEARANCES or slug in people:
            p = person(slug, names.get(slug))
            p["guest"] = apps
            p["groups"] = n
    return people


def add_talked_about(people, talk, names, appearances=None, on_site=()):
    """Pages for players without one whom 10+ discussions talk about (with
    their one or two guest appearances, if any)."""
    from .talk import MIN_TALK_PAGE
    for (kind, slug), groups in talk.items():
        if kind == "player" and slug not in people and len(groups) >= MIN_TALK_PAGE:
            apps = [a for a in (appearances or {}).values() if a["player"] == slug and a["video"] in on_site]
            people[slug] = {"slug": slug, "name": names.get(slug, slug), "hosts": [], "former": [], "guest": apps,
                            "groups": appearance_count({k: a for k, a in enumerate(apps)}, slug) if apps else 0,
                            "talk_only": True}
    return people


def keep_published(people, published, names, appearances=None, on_site=(), ignored=()):
    """Pages stay once published: a player in data/published_players.json
    who no longer meets any threshold keeps a page ("sticky"), with whatever
    guest appearances and discussions there are. Ignored players
    (data/mention_ignore.json) never keep a page that came from mentions."""
    for slug in list(people):
        if slug in ignored and people[slug].get("talk_only"):
            del people[slug]
    for slug in published:
        if slug in people or slug in ignored or slug not in names:
            continue
        apps = [a for a in (appearances or {}).values() if a["player"] == slug and a["video"] in on_site]
        people[slug] = {"slug": slug, "name": names[slug], "hosts": [], "former": [], "guest": apps,
                        "groups": appearance_count({k: a for k, a in enumerate(apps)}, slug) if apps else 0,
                        "talk_only": True, "sticky": True}
    return people


def link_for(slug, people=None, fallback=None):
    """A player's page here when there is one, else their Career Map page."""
    people = CURRENT if people is None else people
    if slug and slug in people:
        return page_url(slug)
    return fallback or (CAREER_MAP % slug if slug else None)


def host_link(url):
    """A roster host url (Career Map) -> the link to use on the site."""
    slug = slug_from_url(url)
    return link_for(slug, fallback=url) if slug else url
