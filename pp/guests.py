"""Guest appearances.

A guest is confirmed automatically only when a video's title (or the start of
its description, when a feed gave one; "with" is not read there) says so
explicitly:
    "ft. <Name>", "feat. <Name>", "featuring <Name>", "with <Name>" / "w/ <Name>"
    (only at the start of a title segment or after a show word such as
    "Podcast" or "Episode 12", and followed by names alone),
    "<Name> joins" (or "stops by", "drops by", "swings by", "sits down with"),
    "Guest: <Name>"
AND the name is exactly one NBA Career Map player (the same names, slugs and
same-name checks used for hosts). A show's own hosts (and former hosts,
"former_hosts" in data/channels.json) are never its guests, and someone
stated in 10 or more of one show's episodes is treated as a regular (sent to
review) rather than a guest.

Every other mention of a Career Map player in a title goes to
data/appearances_review.json (not shown on the site), as does an explicit
guest whose name belongs to more than one player. data/appearances_manual.json
adds or removes appearances and wins over everything automatic.

Clips of the same episode count once: videos are grouped by a link in the
description to a full episode of the same show, then by episode number
("Ep. 12", "EP12", "Episode 12", "S8: E6"), then by time (a clip or Short within
10 days after a full episode of the same show with the same guest).
"""
import re
import unicodedata
from datetime import timedelta

from . import config, metrics
from .util import load_json, parse_ts

# Names Career Map files differently from how shows write them.
ALIASES = {
    "lou williams": "louis-williams",
    "cam johnson": "cameron-johnson",
    "nigel hayes-davis": "nigel-hayes",
    "nigel hayes davis": "nigel-hayes",
}

TOKEN = r"(?:[A-Z][A-Za-z'’\.\-]*|O'[A-Z][a-z]+)"
PARTICLE = r"(?:de|del|da|van|von|der|la|le|Jr\.?|Sr\.?|II|III|IV)"
NAME = r"%s(?:\s+(?:%s|%s)){1,3}" % (TOKEN, TOKEN, PARTICLE)
SEP = r"[|\-–—:!?()\[\]•]"

# "with" in titles is often not a guest ("playing with Kobe"): skip it after
# these words.
WITH_STOP = re.compile(
    r"\b(?:play(?:ing|ed|s)?|hoop(?:ing|ed|s)?|battl(?:e|ing|ed)|beef|feud|guard(?:ing|ed)?|rivalry|"
    r"teammates?|trad(?:e|ed|ing)|compar(?:e|ed|ing|ison)|vs\.?|versus|against|reunit(?:e|ed|ing)|"
    r"reunion|relationship|friendship|fight(?:ing)?|mess(?:ing)?|deal(?:ing)?|problem|issues?|"
    r"along|together|connection|chemistry|signing|meeting|talks?|conversations?)\s*$", re.I)

# "with <Name>" / "w/ <Name>" counts only as a guest line: at the start of
# a title segment or right after a show word ("Podcast w/", "Episode 12
# with", "LIVE with"), and with nothing but names after it up to the end of
# the segment. "Jeff Teague REACTS to Lakers being CAUTIOUS with LeBron
# James this season" is not a guest line.
WITH_AFTER = re.compile(
    r"(?:^|\b(?:podcast|pod|episode|ep\.?\s*\d*|show|special|live|livestream|stream|interview|chat|"
    r"sit-?down|q&a|edition|finale|premiere|party|part\s*\d+|\d+))\s*$", re.I)
NAMES_ONLY = re.compile(r"^\s*(?:[A-Z@][\w'’\.\-]*|de|del|da|van|von|der|la|le|and|&|,|\+)"
                        r"(?:\s*(?:[A-Z@][\w'’\.\-]*|de|del|da|van|von|der|la|le|and|&|,|\+))*\s*$")

PATTERNS = [
    ("ft.", re.compile(r"\b(?:ft\.?|feat\.?|featuring)\s+(?P<seg>[^|\-–—:!?()\[\]•]+)", re.I)),
    ("with", re.compile(r"(?P<pre>[^|\-–—:!?()\[\]•]*?)\b(?:with|w/)\s+(?P<seg>[^|\-–—:!?()\[\]•]+)", re.I)),
    ("joins", re.compile(r"(?P<seg>%s(?:\s*(?:&|and)\s*%s)*)\s+(?i:joins|join|stops by|drops by|swings by|"
                         r"sits down with|pulls up)\b" % (NAME, NAME))),
    ("guest:", re.compile(r"\bguests?\s*:\s*(?P<seg>[^|\-–—!?()\[\]•]+)", re.I)),
]


def norm(name):
    a = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    a = a.replace("’", "'")
    a = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", a.strip())
    a = re.sub(r"[.'`]", "", a)
    return re.sub(r"[\s\-]+", " ", a).strip()


def cm_slug(name):
    """Career Map's slug for one of its own names ("Bob Duffy (1922)" ->
    bob-duffy-1922, "D'Angelo Russell" -> d-angelo-russell)."""
    m = re.match(r"^(.*?)\s*\((\d{4})\)$", name)
    base, year = (m.group(1), m.group(2)) if m else (name, None)
    a = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    a = re.sub(r"\s+(jr|sr)\.?$", "", a)
    s = re.sub(r"[^a-z0-9]+", "-", a).strip("-")
    return s + ("-" + year if year else "")


class PlayerIndex:
    """norm(name) -> [(slug, display name)]; more than one entry = same name."""

    def __init__(self, names):
        self.by_key = {}
        self.display = {}
        for n in names:
            base = re.sub(r"\s*\(\d{4}\)$", "", n)
            slug = cm_slug(n)
            self.display[slug] = base
            self.by_key.setdefault(norm(base), []).append(slug)
        for k, slug in ALIASES.items():
            if slug in self.display:
                self.by_key.setdefault(k, [slug])

    @classmethod
    def load(cls):
        doc = load_json(config.CAREERMAP_PLAYERS_FILE, {}) or {}
        return cls(doc.get("names") or [])

    def lookup(self, name):
        """-> (slug or None, ambiguous: bool)."""
        hits = self.by_key.get(norm(name)) or []
        if len(hits) == 1:
            return hits[0], False
        return None, len(hits) > 1


def split_names(seg):
    """'Melo, Reggie & Jamal Crawford' -> candidate names (Title Case runs)."""
    out = []
    for part in re.split(r"\s*(?:,|&|\band\b|\+)\s*", seg):
        m = re.match(r"\s*(%s)" % NAME, part)
        if m:
            out.append(m.group(1).strip())
    return out


def explicit_names(text, allow_with=True):
    """-> [(name, pattern)] stated explicitly as guests. Descriptions are read
    without the "with" pattern: their boilerplate ("with us", "with the
    crew") makes it unreliable there."""
    out = []
    for label, rx in PATTERNS:
        if label == "with" and not allow_with:
            continue
        for m in rx.finditer(text or ""):
            seg = m.group("seg")
            if label == "with":
                pre = m.group("pre") or ""
                if WITH_STOP.search(pre) or not WITH_AFTER.search(pre) or not NAMES_ONLY.match(seg):
                    continue
                if seg.isupper():
                    continue   # ALL CAPS after "with" is emphasis, not a guest line
            for n in split_names(seg):
                out.append((n, label))
    return out


def _windows(run):
    toks = run.split()
    for size in (3, 2):
        for i in range(len(toks) - size + 1):
            yield " ".join(toks[i:i + size])


def mentioned_names(text):
    """Every 2- or 3-word window of a Title Case or ALL CAPS run in a title
    ("Isiah Thomas Joins The" -> "Isiah Thomas", "Thomas Joins", ...)."""
    out = []
    for m in re.finditer(NAME, text or ""):
        out.extend(_windows(m.group(0)))
    for m in re.finditer(r"\b[A-Z][A-Z'\.\-]+(?:\s+[A-Z][A-Z'\.\-]+){1,3}\b", text or ""):
        out.extend(_windows(m.group(0).title()))
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


EP_RE = re.compile(r"\b(?:s(?:eason)?\s*(\d{1,2})\s*[:,]?\s*)?(?:ep(?:isode)?|e)\.?\s*#?\s*(\d{1,4})\b", re.I)
ID_RE = re.compile(r"(?:youtu\.be/|watch\?v=)([A-Za-z0-9_-]{11})")


def episode_number(title):
    m = EP_RE.search(title or "")
    if not m:
        return None
    return ("s%se%s" % (m.group(1), m.group(2))) if m.group(1) else ("e" + m.group(2))


def group_keys(videos, full_ids):
    """videos: [video dict with id, title, published, desc] of one show and
    one player. -> {video id: group key}."""
    keys = {}
    for v in videos:
        linked = [i for i in ID_RE.findall(v.get("desc") or "") if i in full_ids and i != v["id"]]
        if linked:
            keys[v["id"]] = "ep:" + linked[0]
        elif v["id"] in full_ids:
            n = episode_number(v.get("title"))
            keys[v["id"]] = ("n:" + n) if n else ("ep:" + v["id"])
    # Clips and Shorts without a link: the same episode number, or the latest
    # full episode with this guest up to 10 days before (1 day after allowed).
    fulls = sorted((v for v in videos if v["id"] in full_ids), key=lambda v: v.get("published") or "")
    by_num = {}
    for v in fulls:
        n = episode_number(v.get("title"))
        if n:
            by_num.setdefault(n, keys[v["id"]])
    for v in videos:
        if v["id"] in keys:
            continue
        n = episode_number(v.get("title"))
        if n and n in by_num:
            keys[v["id"]] = by_num[n]
            continue
        p = parse_ts(v.get("published"))
        best = None
        for f in fulls:
            fp = parse_ts(f.get("published"))
            if p and fp and fp - timedelta(days=1) <= p <= fp + timedelta(days=10):
                best = f
        keys[v["id"]] = keys[best["id"]] if best else "v:" + v["id"]
    return keys


REGULAR_MIN = 10       # appearances on one show that make someone a regular


def build(shows, cats, index=None, manual=None):
    """-> (appearances {key: item}, review {key: item}).

    shows: roster records; cats: {source id: catalog}."""
    from . import roster
    index = index or PlayerIndex.load()
    manual = manual if manual is not None else (load_json(config.APPEARANCES_MANUAL_FILE, {}) or {})
    removed = {(r["video"], r["player"]) for r in manual.get("remove", []) if r.get("video") and r.get("player")}
    confirmed, review = {}, {}
    vids_by_show = {}
    for show in shows:
        if show.get("exclude_reason"):
            continue
        host_slugs = set()
        for h in (show.get("hosts") or []) + (show.get("former_hosts") or []):
            name = h["name"] if isinstance(h, dict) else h
            slug, _ = index.lookup(name)
            if slug:
                host_slugs.add(slug)
            url = h.get("url") if isinstance(h, dict) else None
            if url:
                host_slugs.add(url.rstrip("/").rsplit("/", 1)[-1].replace(".html", ""))
        vids = metrics.show_videos(show, cats.get(roster.source_id(show)), need_date=False)
        vids_by_show[show["slug"]] = vids
        for v in vids:
            text = v.get("title") or ""
            exp = explicit_names(text) + explicit_names((v.get("desc") or "")[:300], allow_with=False)
            seen = set()
            for name, how in exp:
                slug, amb = index.lookup(name)
                if slug and slug not in host_slugs and slug not in seen:
                    seen.add(slug)
                    confirmed["%s:%s" % (v["id"], slug)] = {"video": v["id"], "show": show["slug"],
                                                            "player": slug, "role": "guest", "how": how}
                elif amb:
                    review["%s:%s" % (v["id"], norm(name).replace(" ", "-"))] = {
                        "video": v["id"], "show": show["slug"], "name": name, "player": None,
                        "reason": "name belongs to more than one Career Map player", "title": text,
                        "views": v.get("views")}
            for name in mentioned_names(text):
                slug, amb = index.lookup(name)
                if (slug and (slug in seen or slug in host_slugs)) or not (slug or amb):
                    continue
                key = "%s:%s" % (v["id"], slug or norm(name).replace(" ", "-"))
                if key in confirmed:
                    continue
                review.setdefault(key, {
                    "video": v["id"], "show": show["slug"], "name": name, "player": slug,
                    "reason": ("name belongs to more than one Career Map player" if amb
                               else "named in the title, not stated as a guest"),
                    "title": text, "views": v.get("views")})
    for a in manual.get("add", []):
        if a.get("video") and a.get("player"):
            show = a.get("show") or next((s for s, vs in vids_by_show.items() if any(v["id"] == a["video"] for v in vs)), None)
            if show:
                confirmed["%s:%s" % (a["video"], a["player"])] = {"video": a["video"], "show": show,
                                                                  "player": a["player"], "role": a.get("role", "guest"),
                                                                  "how": "manual"}
    for key in list(confirmed):
        it = confirmed[key]
        if (it["video"], it["player"]) in removed:
            del confirmed[key]
    for key in list(review):
        it = review[key]
        if key in confirmed or (it["video"], it.get("player")) in removed:
            del review[key]

    # Group clips of the same episode: one appearance per group.
    groups = {}
    for show_slug, vids in vids_by_show.items():
        by_id = {v["id"]: v for v in vids}
        full_ids = {v["id"] for v in vids if metrics.video_format(v) == metrics.FULL}
        per_player = {}
        for it in confirmed.values():
            if it["show"] == show_slug and it["video"] in by_id:
                per_player.setdefault(it["player"], []).append(by_id[it["video"]])
        for player, pv in per_player.items():
            keys = group_keys(pv, full_ids)
            for v in pv:
                confirmed["%s:%s" % (v["id"], player)]["group"] = "%s/%s" % (show_slug, keys[v["id"]])
            groups[(show_slug, player)] = len(set(keys.values()))

    # Someone "with" a show in this many of its episodes is a co-host or a
    # regular, not a guest: back to review unless added by hand.
    for key in list(confirmed):
        it = confirmed[key]
        n = groups.get((it["show"], it["player"]), 0)
        if n >= REGULAR_MIN and it["how"] != "manual":
            v = next((x for x in vids_by_show[it["show"]] if x["id"] == it["video"]), {})
            review[key] = {"video": it["video"], "show": it["show"], "name": it.get("name") or it["player"],
                           "player": it["player"],
                           "reason": "named in %d of this show's episodes: likely a co-host or regular" % n,
                           "title": v.get("title") or "", "views": v.get("views")}
            del confirmed[key]
    return confirmed, review


def appearance_count(confirmed, player):
    return len({it.get("group") or it["video"] for it in confirmed.values() if it["player"] == player})
