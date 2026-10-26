"""The show roster (data/channels.json).

A show is what gets ranked. A source is what gets collected: a channel, or a
playlist on someone else's channel. One source can feed several shows (the
Boardroom channel carries both Boardroom and The ETCs with Kevin Durant), and a
per-show title filter decides which of that source's videos belong to which show.
"""
import re

from . import config
from .util import load_json

# "podcast": a recurring show with episodes or guests (main rankings).
# "player_channel": a player's personal channel of vlogs, behind-the-scenes
# and highlights (its own page, /player-podcasts/player-channels/).
SHOW_TYPES = ("podcast", "player_channel")


def load_roster(path=None):
    data = load_json(path or config.CHANNELS_FILE)
    shows = data["shows"]
    seen = set()
    for s in shows:
        if s["slug"] in seen:
            raise ValueError("duplicate slug: " + s["slug"])
        if s["slug"] in config.RESERVED_SLUGS:
            raise ValueError("reserved slug: " + s["slug"])
        if s.get("type") not in SHOW_TYPES:
            raise ValueError("%s: type must be one of %s" % (s["slug"], ", ".join(SHOW_TYPES)))
        seen.add(s["slug"])
    return shows


def source_id(show):
    """Playlist shows are collected from the playlist, everything else from the channel."""
    return show.get("playlist_id") or show["channel_id"]


def sources(shows):
    """Unique collection units: {source_id: {"kind", "channel_id", "playlist_id"}}."""
    out = {}
    for s in shows:
        sid = source_id(s)
        out[sid] = {
            "kind": "playlist" if s.get("playlist_id") else "channel",
            "channel_id": s["channel_id"],
            "playlist_id": s.get("playlist_id"),
        }
    return out


def _compile(pattern):
    return re.compile(pattern, re.IGNORECASE) if pattern else None


def title_matches(show, title):
    """True when a video with this title belongs to the show.

    title_filter is optional: {"include": regex, "exclude": regex}, both
    case-insensitive. No filter means every video on the source counts."""
    f = show.get("title_filter") or {}
    inc, exc = _compile(f.get("include")), _compile(f.get("exclude"))
    t = title or ""
    if inc and not inc.search(t):
        return False
    if exc and exc.search(t):
        return False
    return True


def shares_channel(show, shows):
    """A channel that feeds more than one show, or a playlist on a network's
    channel: its subscriber count is not this show's, so it is not shown."""
    if show.get("playlist_id") or show.get("shared_channel"):
        return True
    return sum(1 for s in shows if s["channel_id"] == show["channel_id"]) > 1
