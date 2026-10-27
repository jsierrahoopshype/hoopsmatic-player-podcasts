# hoopsmatic-player-podcasts

NBA player podcasts ranked by YouTube numbers, live at
https://hoopsmatic.com/player-podcasts/ (GitHub Pages, served through the
HoopsMatic Worker). No API keys anywhere.

## How it updates

`.github/workflows/update.yml`, every day at 06:15 UTC and again at 18:15 UTC
(a safety net: GitHub sometimes skips a scheduled run; a second run the same
day only refreshes that day's numbers):

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
  when there is none), `channel_id`, `youtube_url`, optional `playlist_id` (a show that lives
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
- Breakout: an episode's views divided by its show's typical episode; 5x or more is flagged.

All numbers live in `pp/config.py`.

## Local run

```
pip install -r requirements.txt
python -m pytest -q
python -m pp build      # from committed data, no fetching
```
