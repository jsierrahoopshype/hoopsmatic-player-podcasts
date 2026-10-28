"""Paths and the numbers the rankings are built on."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VIDEOS_DIR = DATA / "videos"          # one catalog file per source (channel or playlist)
SNAPSHOTS_DIR = DATA / "snapshots"    # daily/ (videos of the last 90 days) and weekly/ (every video)
FORMAT_OVERRIDES_FILE = DATA / "format_overrides.json"   # manual format by video ID
CAREERMAP_PLAYERS_FILE = DATA / "careermap_players.json"  # Career Map's player names (its slugs)
APPEARANCES_FILE = DATA / "appearances.json"              # confirmed guest appearances (generated)
APPEARANCES_REVIEW_FILE = DATA / "appearances_review.json"  # possible guests, not shown (generated)
APPEARANCES_MANUAL_FILE = DATA / "appearances_manual.json"  # manual adds/removes, win over automatic
THUMBS_DIR = DATA / "thumbs"          # small thumbnails, committed, served from our own domain
HEADSHOTS_DIR = DATA / "headshots"    # player headshots from nba-headshots, committed
HEADSHOTS_INDEX_FILE = DATA / "headshots_index.json"
NBA_ACTIVE_FILE = DATA / "nba_active.json"        # active players and current teams (generated weekly)
TEAMS_FILE = DATA / "teams.json"                  # the 30 franchises and the names that mean each
NICKNAMES_FILE = DATA / "nicknames.json"          # nicknames that always mean one player (editable)
MENTIONS_FILE = DATA / "mentions.json"            # "talked about": players and teams per video (generated)
MENTIONS_MANUAL_FILE = DATA / "mentions_manual.json"  # manual adds/removes, win over automatic
PUBLISHED_PLAYERS_FILE = DATA / "published_players.json"  # player pages once published stay (updated each build)
MENTION_IGNORE_FILE = DATA / "mention_ignore.json"  # names never matched to a Career Map player in mentions
MOVED_PAGES_FILE = DATA / "moved_pages.json"      # old page address -> new one (a stub redirects)
ALWAYS_REVIEW_FILE = DATA / "always_review.json"  # names never matched automatically without a suffix
SURNAME_STOPWORDS_FILE = DATA / "surname_stopwords.json"  # surnames that are everyday words: no lone match
SURNAME_DEFAULTS_FILE = DATA / "surname_defaults.json"  # shared name -> default player, instead of review
ART_DIR = DATA / "art"                # show artwork (channel avatars), committed
EMBED_FILE = DATA / "embed.json"      # oEmbed result per video (ok / no / gone)
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

DAILY_DAYS = 90         # videos this recent get a daily view count; older ones weekly
MOMENTUM_DAYS = 30      # main ranking: views on full episodes posted in the last 30 days
TYPICAL_DAYS = 90       # median window, episodes-per-month window, ranked window
WEEK_DAYS = 7
# Saved with each day's ranking (data/ranks.json); rank arrows compare only
# rankings made with the same rule. Change it whenever the ranking rules change.
RANK_RULE = "full-30d-2026-10-27"
BREAKOUT_X = 5.0        # a breakout score of 5x or more is highlighted (score: see pp/videos.py)
# Ranked: at least 4 full episodes in the last 90 days, or 1 to 3 in the last
# 90 days with at least 4 in the last 180. Occasional: 1 to 3 in the last 90
# days but fewer than 4 in the last 180 (not ranked). Dormant: none in the last
# 90 days. No full episode ever: excluded.
RANKED_MIN_EPISODES = 4
LONG_DAYS = 180
SEASON_START = date(2026, 10, 1)

# Slugs a show may never take: they are pages or folders of their own.
RESERVED_SLUGS = {"most-watched", "dormant", "player-channels", "thumbs", "assets", "sitemap.xml", "404.html", "index.html"}
