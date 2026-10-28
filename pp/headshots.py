"""Player headshots from the jsierrahoopshype/nba-headshots repo, copied into
this repo (data/headshots/<Career Map slug>.webp, 160px, about 3 KB) so
visitors never load them from GitHub. They are the one HoopsMatic headshot
look, face-fill (the face fills the circle, transparent). Player pages draw
the head at 88px, so those players also get the 320px copy
(data/headshots/320/<slug>.webp).

data/headshots_index.json maps a normalised player name to that repo's file
name; it is refreshed with the weekly listing. A player without a headshot
gets initials on the page instead.
"""
import json
import sys
import urllib.request

from . import config
from .feeds import UA
from .util import load_json, save_json

INDEX_URL = "https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/players/metadata/players_all.json"
FILE_URL = "https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/players/headshots/face-fill/%s.webp"
FILE_URL_BIG = "https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/players/headshots/face-fill-320/%s.webp"


def _norm(name):
    from .guests import norm
    return norm(name)


def refresh_index():
    """Rebuild data/headshots_index.json from nba-headshots. Keeps the old one
    on failure."""
    try:
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            doc = json.loads(r.read().decode("utf-8"))
        idx = {}
        for p in doc.get("players") or []:
            hs = p.get("headshot") or {}
            if not hs.get("face"):
                continue
            stem = "%s-%s" % (p["nba_id"], p["slug"])
            idx.setdefault(_norm(p["full_name"]), stem)
        if len(idx) > 500:
            save_json(config.HEADSHOTS_INDEX_FILE, {"source": INDEX_URL, "files": idx}, line_per_key="files")
            # Active players and their current team, for "talked about": a
            # lone surname counts only when a team named next to it settles who.
            active = sorted([p["full_name"], p.get("last_name") or p["full_name"].split()[-1], p.get("team_abbrev") or ""]
                            for p in doc.get("players") or [] if p.get("active"))
            if len(active) > 300:
                save_json(config.NBA_ACTIVE_FILE, {"source": INDEX_URL, "_about": "[full name, last name, team] of "
                                                   "active NBA players. Generated weekly.", "players": active},
                          line_per_key="players")
            return len(idx)
    except Exception as e:
        print("headshots index: kept the last copy (%s)" % e, file=sys.stderr)
    return None


def path_for(slug, big=False):
    return config.HEADSHOTS_DIR / ("320" if big else "") / (slug + ".webp")


def ensure(players, big=False):
    """players: {Career Map slug: display name}. Downloads missing headshots
    (the 320px copies when big). Returns {slug: True} for those that have one."""
    idx = (load_json(config.HEADSHOTS_INDEX_FILE, {}) or {}).get("files") or {}
    path_for("", big).parent.mkdir(parents=True, exist_ok=True)
    have = {}
    for slug, name in players.items():
        p = path_for(slug, big)
        if p.exists() and p.stat().st_size > 0:
            have[slug] = True
            continue
        stem = idx.get(_norm(name))
        if not stem:
            continue
        try:
            req = urllib.request.Request((FILE_URL_BIG if big else FILE_URL) % stem, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
            if body[:4] == b"RIFF":
                p.write_bytes(body)
                have[slug] = True
        except Exception as e:
            print("headshot failed:", slug, e, file=sys.stderr)
    return have


def available(players, big=False):
    return {s: True for s in players if path_for(s, big).exists()}


def initials(name):
    parts = [w for w in name.replace(".", " ").split() if w[:1].isalpha()]
    return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")) if parts else "?").upper()
