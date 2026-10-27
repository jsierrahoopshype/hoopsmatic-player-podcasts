"""'Talked about': the players and teams a video discusses. Kept apart from
appearances (a host or a confirmed guest is IN the video; a mention is
someone the video is ABOUT).

Sources: the video's title, and the chapter lines of its description
(pp/chapters.py: "12:30 Wemby's debut"). The rest of a description is never
read. A mention found only in a chapter keeps that chapter's time, so links
open the video at that moment.

Players are matched
  - by full name, against NBA Career Map's names (accents and Jr./Sr. ignored);
  - by a nickname in data/nicknames.json (Wemby, Giannis, SGA, KD, ...);
  - by a lone surname or a shared name ONLY when a team named in the same
    title (or chapter line) settles it: exactly one active player with that
    name plays for that team. Otherwise the name goes to the review file
    (data/appearances_review.json, "mentions"), not to the site.
Teams are matched by nickname only (Lakers, Sixers, Cavs, Wolves, Pels, ...)
or a historical name of the franchise (SuperSonics, Bobcats, New Jersey
Nets), never by a city alone. A word inside a matched player's name ("Magic"
in "Magic Johnson") is not a team.

Not counted: a player's own appearance (host or confirmed guest) in that
video, and any mention of a show's host or former host on that show.
data/mentions_manual.json adds or removes mentions and wins over all of this.

Clips of the same episode are grouped (as for guests: a description link to
the episode, the same episode number, or a clip within 10 days after a full
episode of the show mentioning the same player or team), so one discussion
counts once.
"""
import re
import unicodedata

from . import config, metrics
from .guests import PlayerIndex, group_keys, norm
from .util import load_json

WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\.\-]*")
# Capitalised words that are surnames of active players but mostly ordinary
# words in titles: never sent to review as a lone surname.
COMMON = set("""
able all allen anthony bad ball banks battle black blue boston brooks brown
burns butler can cash case champion chase christian cook cooper curry daniels
davis day early ellis evans fields ford fox francis freeman frye gay george
gordon grant green hall hardy harris hart hayes hill holiday house hunter
jackson james johnson jones jordan king knight lamb lee lewis little love
martin mann miles miller mitchell moody moore morris murray nance noel
paul payne porter powell price queen reed rich richards rivers roberts robinson
rose ross sharpe simmons smart smith stewart strong taylor thomas thompson
tucker turner walker wallace walton ward washington watson wells white
williams wilson wood woods young bridges brunson champagnie council edwards
jalen marcus duncan
""".split())


# A team word followed by these is not the team ("Heat Check").
NOT_TEAM = {"miami-heat": r"\s+(?:Check|CHECK)\b"}


def _fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _cased_forms(name):
    """A nickname matches as written or in ALL CAPS."""
    return {name, name.upper()}


class Matcher:
    def __init__(self, index, nicknames, teams, active):
        self.index = index
        # nickname -> slug; patterns longest first so "Ant Edwards" beats "Ant"
        self.suffixed = {}
        for slug, disp in index.display.items():
            m = re.match(r"^(.*)\s+(II|III|IV)$", disp)
            if m:
                self.suffixed[(norm(m.group(1)), m.group(2))] = slug
        self.nick = []
        for name, slug in sorted(nicknames.items(), key=lambda kv: -len(kv[0])):
            if slug in index.display:
                for form in _cased_forms(_fold(name)):
                    self.nick.append((re.compile(r"(?<![\w'’-])%s(?![\w-])" % re.escape(form)), slug))
        self.teams = []
        self.team_by_abbrev = {}
        for t in teams:
            self.team_by_abbrev[t["abbrev"]] = t["slug"]
            for name in sorted(t["historical"] + t["names"], key=len, reverse=True):
                for form in _cased_forms(name):
                    self.teams.append((re.compile(r"(?<![\w-])%s(?!['’]?\w)" % re.escape(form)), t["slug"]))
        # active players: full name / surname -> [(slug or None, team slug)]
        self.active_full, self.active_last = {}, {}
        for full, last, abbrev in active:
            slug, _ = index.lookup(full)
            if not slug and len(set(index.by_key.get(norm(full)) or [])) == 1:
                # two Career Map players filed under one slug (a Jr. and his
                # father): the team settles it, and the page is the same
                slug = index.by_key[norm(full)][0]
            team = self.team_by_abbrev.get(abbrev)
            self.active_full.setdefault(norm(full), []).append((slug, team))
            self.active_last.setdefault(norm(last), []).append((slug, team))

    @classmethod
    def load(cls, index=None):
        return cls(index or PlayerIndex.load(),
                   (load_json(config.NICKNAMES_FILE, {}) or {}).get("names", {}),
                   (load_json(config.TEAMS_FILE, {}) or {}).get("teams", []),
                   (load_json(config.NBA_ACTIVE_FILE, {}) or {}).get("players", []))

    def find(self, text):
        """-> (players {slug: how}, teams {slug}, unresolved [(name, reason)])
        for one title or chapter line."""
        text = _fold(text or "")
        taken = []          # spans used by a player's name

        def free(a, b):
            return all(b <= x or a >= y for x, y in taken)

        players, unresolved, ambiguous = {}, [], []
        # 1. Full names (3 then 2 capitalised words), leftmost-longest.
        words = [(m.start(), m.end(), re.sub(r"['’][sS]$", "", m.group(0)).rstrip(".'’")) for m in WORD.finditer(text)]
        i = 0
        while i < len(words):
            done = False
            for size in (3, 2):
                win = words[i:i + size]
                if len(win) < size or not all(w[2][:1].isupper() for w in win):
                    continue
                # the words must be adjacent (only spaces between them)
                if any(text[win[k][1]:win[k + 1][0]].strip() for k in range(size - 1)):
                    continue
                name = " ".join(w[2] for w in win)
                slug, amb = self.index.lookup(name)
                # "Gary Payton II" is its own Career Map player, though the
                # suffix is dropped when names are compared.
                if amb:
                    if win[-1][2] in ("II", "III", "IV"):
                        exact = self.suffixed.get((norm(name), win[-1][2]))
                    elif len(words) > i + size and words[i + size][2] in ("II", "III", "IV"):
                        exact = self.suffixed.get((norm(name), words[i + size][2]))
                        if exact:
                            size += 1
                            win = words[i:i + size]
                    else:
                        exact = None
                    if exact:
                        slug, amb = exact, False
                if slug or amb:
                    taken.append((win[0][0], win[-1][1]))
                    if slug:
                        players.setdefault(slug, "name")
                    else:
                        ambiguous.append(name)
                    i += size
                    done = True
                    break
            if not done:
                i += 1
        # 2. Nicknames.
        for rx, slug in self.nick:
            for m in rx.finditer(text):
                if free(m.start(), m.end()):
                    taken.append((m.start(), m.end()))
                    players.setdefault(slug, "nickname")
        # 3. Teams, outside players' names.
        teams = set()
        for rx, slug in self.teams:
            for m in rx.finditer(text):
                if slug in NOT_TEAM and re.match(NOT_TEAM[slug], text[m.end():]):
                    continue
                if free(m.start(), m.end()):
                    taken.append((m.start(), m.end()))
                    teams.add(slug)
        # 4. Shared names, settled by a team named alongside.
        for name in ambiguous:
            cands = [c for c in self.active_full.get(norm(name), []) if c[1] in teams and c[0]]
            if len({c[0] for c in cands}) == 1:
                players.setdefault(cands[0][0], "name+team")
            else:
                unresolved.append((name, "name belongs to more than one Career Map player"))
        # 5. Lone surnames of active players, settled the same way.
        for k, (s, e, w) in enumerate(words):
            if not w[:1].isupper() or not free(s, e) or len(w) < 4:
                continue
            # the second half of a name already matched ("Steph Curry")
            if k and not free(words[k - 1][0], words[k - 1][1]) and not text[words[k - 1][1]:s].strip():
                continue
            # the first name of someone else ("Shannon Sharpe", "Ryan Coogler")
            nxt = words[k + 1] if k + 1 < len(words) else None
            if nxt and nxt[2][:1].isupper() and nxt[2][1:2].islower() and not text[e:nxt[0]].strip() \
                    and free(nxt[0], nxt[1]):
                continue
            key = norm(w)
            cands = self.active_last.get(key)
            if not cands:
                continue
            hit = {c[0] for c in cands if c[1] in teams and c[0]}
            if len(hit) == 1:
                players.setdefault(hit.pop(), "surname+team")
            elif key not in COMMON:
                # after another capitalised word it is someone's surname
                # ("Caitlin Clark", "Eddie Murphy"), not a player on his own
                prv = words[k - 1] if k else None
                if prv and prv[2][:1].isupper() and prv[2][1:2].islower() and not text[prv[1]:s].strip():
                    continue
                unresolved.append((w, "surname alone, no team in the same line settles who"))
        return players, teams, unresolved


def _video_texts(v):
    """[(source, seconds or None, text)]: the title, then each chapter line."""
    out = [("title", None, v.get("title") or "")]
    for sec, line in v.get("chapters") or []:
        out.append(("chapter", sec, line))
    return out


def build(shows, cats, items, appearances, matcher=None, manual=None):
    """-> (mentions {video id: [{kind, slug, src, t, how}]}, review {key: item}).

    shows: roster records of the shows on the site; cats: {source id:
    catalog}; items: the site's videos (dated, not deleted); appearances:
    confirmed guests."""
    from . import roster
    matcher = matcher or Matcher.load()
    manual = manual if manual is not None else (load_json(config.MENTIONS_MANUAL_FILE, {}) or {})
    on_site = {it["id"]: it for it in items}
    guests_in = {}
    for a in appearances.values():
        guests_in.setdefault(a["video"], set()).add(a["player"])
    out, review = {}, {}
    for show in shows:
        own = set()
        for h in (show.get("hosts") or []) + (show.get("former_hosts") or []):
            if isinstance(h, dict) and h.get("url"):
                own.add(h["url"].rstrip("/").rsplit("/", 1)[-1].replace(".html", ""))
            name = h["name"] if isinstance(h, dict) else h
            slug, _ = matcher.index.lookup(name)
            if slug:
                own.add(slug)
        # the hosts' surnames on their own show are not "unresolved" names
        own_names = {norm(matcher.index.display.get(sl, "")).split(" ")[-1] for sl in own} - {""}
        cat = cats.get(roster.source_id(show)) or {}
        for v in metrics.show_videos(show, cat):
            if v["id"] not in on_site:
                continue
            found = {}
            for src, sec, text in _video_texts(v):
                players, teams, unresolved = matcher.find(text)
                for slug, how in players.items():
                    if slug in own or slug in guests_in.get(v["id"], ()):
                        continue
                    found.setdefault(("player", slug), {"kind": "player", "slug": slug, "src": src, "t": sec, "how": how})
                for slug in sorted(teams):
                    found.setdefault(("team", slug), {"kind": "team", "slug": slug, "src": src, "t": sec, "how": "nickname"})
                for name, reason in unresolved:
                    if norm(name) in own_names:
                        continue
                    review.setdefault("%s:m:%s" % (v["id"], norm(name).replace(" ", "-")), {
                        "kind": "mention", "video": v["id"], "show": show["slug"], "name": name, "player": None,
                        "reason": "mention: " + reason, "source": src, "t": sec,
                        "title": v.get("title") or "", "views": v.get("views")})
            if found:
                out[v["id"]] = list(found.values())
    # Manual file wins.
    for r in manual.get("remove", []):
        kind = "player" if r.get("player") else "team"
        slug = r.get("player") or r.get("team")
        if r.get("video") in out:
            out[r["video"]] = [m for m in out[r["video"]] if not (m["kind"] == kind and m["slug"] == slug)]
            if not out[r["video"]]:
                del out[r["video"]]
    for a in manual.get("add", []):
        kind = "player" if a.get("player") else "team"
        slug = a.get("player") or a.get("team")
        if a.get("video") in on_site and slug:
            lst = [m for m in out.get(a["video"], []) if not (m["kind"] == kind and m["slug"] == slug)]
            lst.append({"kind": kind, "slug": slug, "src": "manual", "t": a.get("t"), "how": "manual"})
            out[a["video"]] = lst
    return out, review


def groups(mentions, items, cats_videos):
    """Group clips of the same episode per show and per player or team.
    -> {(kind, slug): {group key: [video ids]}}, group keys "<show>/<key>".

    cats_videos: {video id: catalog video} (titles, descriptions, dates)."""
    by_show = {}
    for it in items:
        by_show.setdefault(it["show"], []).append(it)
    full_ids = {s: {it["id"] for it in vs if it["fmt"] == metrics.FULL} for s, vs in by_show.items()}
    show_of = {it["id"]: it["show"] for it in items}
    per = {}
    for vid, ms in mentions.items():
        for m in ms:
            per.setdefault((m["kind"], m["slug"], show_of[vid]), []).append(vid)
    out = {}
    for (kind, slug, show), vids in per.items():
        vs = [dict(cats_videos.get(v) or {}, id=v) for v in vids]
        keys = group_keys(vs, full_ids.get(show, set()))
        g = out.setdefault((kind, slug), {})
        for v in vids:
            g.setdefault("%s/%s" % (show, keys[v]), []).append(v)
    return out
