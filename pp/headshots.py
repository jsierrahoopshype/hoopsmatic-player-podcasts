"""Player headshots from the jsierrahoopshype/nba-headshots repo, copied into
this repo (data/headshots/<Career Map slug>.webp, 160px, about 3 KB) so
visitors never load them from GitHub.

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
FILE_URL = "https://raw.githubusercontent.com/jsierrahoopshype/nba-headshots/main/players/headshots/face2-160/%s.webp"


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
            return len(idx)
    except Exception as e:
        print("headshots index: kept the last copy (%s)" % e, file=sys.stderr)
    return None


def path_for(slug):
    return config.HEADSHOTS_DIR / (slug + ".webp")


def ensure(players):
    """players: {Career Map slug: display name}. Downloads missing headshots.
    Returns {slug: True} for those that have one."""
    idx = (load_json(config.HEADSHOTS_INDEX_FILE, {}) or {}).get("files") or {}
    config.HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    have = {}
    for slug, name in players.items():
        p = path_for(slug)
        if p.exists() and p.stat().st_size > 0:
            have[slug] = True
            continue
        stem = idx.get(_norm(name))
        if not stem:
            continue
        try:
            req = urllib.request.Request(FILE_URL % stem, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
            if body[:4] == b"RIFF":
                p.write_bytes(body)
                have[slug] = True
        except Exception as e:
            print("headshot failed:", slug, e, file=sys.stderr)
    return have


def available(players):
    return {s: True for s in players if path_for(s).exists()}


def initials(name):
    parts = [w for w in name.replace(".", " ").split() if w[:1].isalpha()]
    return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")) if parts else "?").upper()
