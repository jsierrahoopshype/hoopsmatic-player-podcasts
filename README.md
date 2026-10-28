# hoopsmatic-player-podcasts

NBA player podcasts ranked by YouTube numbers, live at
https://hoopsmatic.com/player-podcasts/ (GitHub Pages, served through the
HoopsMatic Worker). No API keys anywhere.

## How it updates

`.github/workflows/update.yml`, every day at 06:37 and 18:37 UTC, on odd
minutes because GitHub starts scheduled runs late (or skips them) at busy
times like :00 and :15. Backup slots at 09:41 and 21:41 UTC run only when no
run has succeeded in the last 6 hours. "Run workflow" on the Actions tab
starts one by hand. A second run the same day only refreshes that day's
numbers:

1. **Full listing** (`python -m pp weekly-if-due`): on Mondays, or whenever
   the last one is a week old, yt-dlp reads every tab of every channel
   (Videos, Live, Shorts; flat listing, nothing is downloaded): every upload's
   length, rounded views and "3 weeks ago" date, plus subscriber counts.
   Saved as `data/snapshots/weekly/<date>.json`. Videos a complete listing no
   longer shows are marked `gone` (deleted, private or unavailable) and stop
   showing. It also refreshes `data/careermap_players.json` (Career Map's
   player names, for guest matching). If YouTube blocks GitHub's servers the
   step only warns; the last good data stays and `data/status.json` records it.
2. **Daily** (`python -m pp daily`): every show's public feeds (long-form, and
   Shorts for channels) give exact views, likes, publish times and the start
   of each description, where YouTube answers them (from GitHub's servers it
   often does not). Then a yt-dlp listing of each source back to 90 days, so
   every video of the last 90 days gets a view count every day:
   `data/snapshots/daily/<date>.json` (one line per source, `{"<id>": views}`,
   plus `[likes, views]` where a feed gave likes). Daily files older than 90
   days are rolled into the weekly file of their week and deleted.
3. Tests, then `python -m pp build` writes the site to `site/`, downloads any
   new thumbnails into `data/thumbs/`, updates `data/ranks.json`,
   `data/excluded.json`, `data/appearances.json`, `data/appearances_review.json`
   and `data/sitemap-state.json`, and the site is deployed.

A push to `main` rebuilds and redeploys from the committed data only.

Shorts: a channel's Shorts tab gives views but no date or length. A Short is
dated from the Shorts feed when it is among the latest 15, from its neighbours
in the tab when two dated Shorts surround it, and otherwise from the day it
first appears in a listing (half a day before that run). Shorts from before
tracking began that none of these date stay undated: they count in all-time
lists, not in date windows.

## Files you may want to edit

- `data/channels.json`: the roster. One record per show: `slug`, `name`,
  `hosts` (a list of `{"name", "url"}`; `url` is the host's HoopsMatic player
  page on NBA Career Map, the section with the most player pages, or `null`
  when there is none), optional `former_hosts` (same shape plus an optional `note`, e.g. the season; past hosts are
  never counted as guests of their own show), `channel_id`, `youtube_url`, optional `playlist_id` (a show that lives
  in one playlist of a network's channel), optional `title_filter`
  (`{"include": regex, "exclude": regex}`, case-insensitive) so one channel can
  feed several shows, `shared_channel` (hides subscriber numbers that belong
  to the whole channel), `type` (`podcast` or `player_channel`, required) and
  optional `exclude_reason` (leaves the show out of every list, with that
  reason in `data/excluded.json`) and `uncertain` (`true` keeps a show out of
  the rankings and off the site until cleared). `not_ranked` lists channels
  deliberately left out.
- `data/format_overrides.json`: `{"<video id>": "full" | "clip" | "short"}`,
  wins over the automatic format.
- `data/nicknames.json`: `{"<nickname>": "<Career Map slug>"}`, names that
  always mean one player (Wemby, SGA, KD...).
- `data/mentions_manual.json`: `add` / `remove` talked-about mentions
  (`{"video", "player" or "team", optional "t" in seconds}`); wins over automatic ones.
- `data/teams.json`: the 30 franchises with the nicknames and former names that mean each.
- `data/always_review.json`: names never matched automatically without their suffix.
- `data/surname_stopwords.json`: surnames that are everyday words, never matched on their own.
- `data/surname_defaults.json`: `{"<name>": {"player": <slug>, "why": ...}}`, the
  default player for a shared surname or name when no team settles it.
- `data/moved_pages.json`: old page addresses and where they moved (a stub redirects).
- `data/appearances_manual.json`: `add` / `remove` guest appearances
  (`{"video": "<id>", "player": "<Career Map slug>"}`); wins over automatic
  matches. `data/appearances.json` (confirmed, shown) and
  `data/appearances_review.json` (possible guests, not shown, sorted by views)
  are generated.
- `data/excluded.json` (generated): shows with no full episode at all, or left out by `exclude_reason`, with the reason.

## Rules

- Full episode: 20 minutes or longer. Clip: 1 to 20 minutes. Short: under 1
  minute, or anything on a channel's Shorts tab. Rankings use full episodes only.
- Ranked: at least 4 full episodes in the last 90 days, or 1 to 3 in the last
  90 days with at least 4 in the last 180.
- Occasional: 1 to 3 in the last 90 days and fewer than 4 in the last 180.
  Dormant: none in the last 90 days. Neither is ranked; both are listed with
  their last full-episode date on `/player-podcasts/dormant/`.
- No full episode ever: excluded (listed in `data/excluded.json`).
- Two kinds of show, set by `type` in `data/channels.json`: `podcast` (main
  rankings and Most watched) and `player_channel` (a player's personal channel
  of vlogs, behind-the-scenes and highlights; ranked separately at
  `/player-podcasts/player-channels/` with the same numbers and rules).
- 30-day views (the ranking): current views of full episodes posted in the last 30 days.
- Typical episode: median views of full episodes from the last 90 days.
- Breakout: a video's views divided by the median views of the same show's
  videos of the same format published in the 90 days before it, with at
  least 8 of them (otherwise no score); 5x or more is highlighted.
- Views gained (24 hours, 7 and 30 days): the difference between two
  snapshots, per video, at the same precision (listing counts are rounded to
  3 significant figures). Shown only once both snapshots exist.
- Rank arrows compare with a ranking at least a week old made with the same
  rules (`RANK_RULE` in `pp/config.py`); until there is one, no arrows.

## Pages

- `/player-podcasts/`: Watch now, shelves, the Latest videos stream and the rankings.
- `/player-podcasts/top-videos/`: most viewed, biggest gainers and breakouts.
- `/player-podcasts/<show>/`: one page per show on the site.
- `/player-podcasts/players/` and `/player-podcasts/players/<Career Map slug>/`:
  a page for every player with 3+ confirmed guest appearances or hosting a
  show with 3+ videos. Player names link there, or to NBA Career Map.
- `/player-podcasts/teams/` and `/player-podcasts/teams/<team slug>/`: all 30
  teams and the videos that talk about them.
- `/player-podcasts/player-channels/`, `/most-watched/`, `/dormant/`, `/methodology/`.

## Talked about (mentions)

Separate from appearances (hosts and guests). A video talks about a player or
team when its title or a chapter line of its description (a line starting
with a timestamp) names them; the rest of a description is never read.
Chapters come from feeds only, so they cover videos seen in a feed. Players:
full Career Map name or a nickname in `data/nicknames.json`. A written suffix
(Jr., Sr., II, III) means only the player with it; a plain father-and-son
name means the one without a suffix, except names in
`data/always_review.json`. A lone surname matches when exactly one Career Map
player has it (unless it is an everyday word in
`data/surname_stopwords.json`); a shared name or shared surname only when a
team named in the same line settles it, or else when `data/surname_defaults.json`
names a default (the famous one, e.g. Tatum -> Jayson Tatum); otherwise it
goes to the "mentions" list in `data/appearances_review.json`. Lone first names are ignored unless
they are nicknames. Teams: by
nickname or former franchise name (`data/teams.json`), never a city alone.
A player's own appearance in a video, and a show's hosts on their own show,
never count. Clips of one episode count once. Players with 10+ discussions
get a page. Results: `data/mentions.json` (generated).
- Videos play in the page through youtube-nocookie.com, only after a press.

All numbers live in `pp/config.py`.

## Local run

```
pip install -r requirements.txt
python -m pytest -q
python -m pp build      # from committed data; fetches only missing thumbnails, headshots and embed checks
```

UI check (needs Playwright), against a local copy or the live site:

```
node tools/ui_check.js https://hoopsmatic.com/player-podcasts/
```

It loads the main pages, one show and one player page at 1280, 375 and 320
px and fails on sideways scroll, a missing H1, canonical or footer, script
errors, or anything loaded from YouTube before a play button is pressed.
