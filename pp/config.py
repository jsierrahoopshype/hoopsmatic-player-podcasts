"""Paths and the numbers the rankings are built on."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VIDEOS_DIR = DATA / "videos"          # one catalog file per source (channel or playlist)
SNAPSHOTS_DIR = DATA / "snapshots"    # one file per day, straight from the public feeds
THUMBS_DIR = DATA / "thumbs"          # small thumbnails, committed, served from our own domain
CHANNELS_FILE = DATA / "channels.json"
SUBSCRIBERS_FILE = DATA / "subscribers.json"
RANKS_FILE = DATA / "ranks.json"
STATUS_FILE = DATA / "status.json"
EXCLUDED_FILE = DATA / "excluded.json"
SITEMAP_STATE_FILE = DATA / "sitemap-state.json"
SITE_SRC = ROOT / "site_src"          # stylesheet and script copied into the build
SITE_OUT = ROOT / "site"              # the build output GitHub Pages serves (not committed)

SITE_ORIGIN = "https://hoopsmatic.com"
BASE_PATH = "/player-podcasts"
SITE_BASE = SITE_ORIGIN + BASE_PATH

# Video types by length (seconds).
SHORT_MAX = 60          # under 1 minute: Short
FULL_MIN = 20 * 60      # 20 minutes and up: full episode; anything between is a clip

MOMENTUM_DAYS = 30      # main ranking: views on full episodes posted in the last 30 days
TYPICAL_DAYS = 90       # median window, episodes-per-month window, ranked window
WEEK_DAYS = 7
BREAKOUT_X = 5.0        # an episode at 5x its show's median or more is a breakout
# Ranked: at least 4 full episodes in the last 90 days, or 1 to 3 in the last
# 90 days with at least 4 in the last 180. Otherwise Dormant (no full episode
# ever: excluded).
RANKED_MIN_EPISODES = 4
LONG_DAYS = 180
SEASON_START = date(2026, 10, 1)

# Slugs a show may never take: they are pages or folders of their own.
RESERVED_SLUGS = {"most-watched", "dormant", "player-channels", "thumbs", "assets", "sitemap.xml", "404.html", "index.html"}
