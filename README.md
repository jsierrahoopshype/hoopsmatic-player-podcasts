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
   `data/snapshots/YYYY-MM-DD.json` and merged into `data/videos/`. Uploads whose
   length is still unknown get a short listing to fill it in.
3. Tests, then `python -m pp build` writes the site to `site/`, downloads any
   new thumbnails into `data/thumbs/`, updates `data/ranks.json`,
   `data/excluded.json` and `data/sitemap-state.json`, and the site is deployed.

A push to `main` rebuilds and redeploys from the committed data only.

## Files you may want to edit

- `data/channels.json`: the roster. One record per show: `slug`, `name`,
  `hosts`, `channel_id`, `youtube_url`, optional `playlist_id` (a show that lives
  in one playlist of a network's channel), optional `title_filter`
  (`{"include": regex, "exclude": regex}`, case-insensitive) so one channel can
  feed several shows, and `shared_channel` (hides subscriber numbers that belong
  to the whole channel). `not_ranked` lists channels deliberately left out.
- `data/excluded.json` (generated): shows that fail the rules, with the reason.

## Rules

- Full episode: 20 minutes or longer. Clip: 1 to 20 minutes. Short: under 1 minute.
  Rankings use full episodes only.
- Active: at least one full episode in the last 90 days; otherwise Dormant.
- Real show: more than half of the uploads in the last 90 days are full episodes
  (Shorts are not counted: the Shorts tab carries no dates).
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
