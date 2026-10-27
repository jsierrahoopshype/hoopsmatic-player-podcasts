# hoopsmatic-player-podcasts

NBA player podcasts ranked by YouTube numbers, live at
https://hoopsmatic.com/player-podcasts/ (GitHub Pages, served through the
HoopsMatic Worker). No API keys anywhere.

## How it updates

`.github/workflows/update.yml`, every day at 06:15 UTC:

1. **Mondays only** (or a manual run with "listing" ticked): `python -m pp weekly`
   reads every channel's Videos and Live tabs with yt-dlp (flat listing, nothing
   is downloaded): every upload's length, rounded views and "3 weeks ago" date,
   plus subscriber counts. If YouTube blocks GitHub's servers the step only
   warns; the last good data stays and `data/status.json` records it.
2. `python -m pp daily` reads every show's public feed (the long-form-only
   `UULF…` playlist feed, falling back to the plain channel feed): exact views,
   likes and publish times for the latest 15 uploads. Saved to
   `data/snapshots/YYYY-MM-DD.json` and merged into `data/videos/`. From
   GitHub's servers YouTube often answers feeds with a 404; a source whose feed
   still fails after retries gets a short yt-dlp listing of its latest 30
   uploads instead (rounded views, no likes; marked `"feed": "yt-dlp"` in the
   snapshot). Uploads whose length is still unknown get the same short listing.
3. Tests, then `python -m pp build` writes the site to `site/`, downloads any
   new thumbnails into `data/thumbs/`, updates `data/ranks.json`,
   `data/excluded.json` and `data/sitemap-state.json`, and the site is deployed.

A push to `main` rebuilds and redeploys from the committed data only.

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
  reason in `data/excluded.json`). `not_ranked` lists channels deliberately left out.
- `data/excluded.json` (generated): shows with no full episode at all, or left out by `exclude_reason`, with the reason.

## Rules

- Full episode: 20 minutes or longer. Clip: 1 to 20 minutes. Short: under 1 minute.
  Rankings use full episodes only.
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
