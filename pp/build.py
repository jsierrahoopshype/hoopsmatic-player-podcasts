"""Build the static site into site/ from the committed data.

Also writes the files the build owns in data/: ranks.json (daily ranking
history, for the weekly rank change), excluded.json (shows left out of the
rankings, with the reason) and sitemap-state.json (content hash per URL).
"""
import hashlib
import shutil
import sys
from datetime import timedelta

from . import catalog, config, embed, guests, headshots, home, metrics, render, roster, sitemap, thumbs, videos
from .util import load_json, save_json, utcnow, today_str, parse_ts


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _period_lists(pool, now):
    """Most-watched lists: the top 50 overall plus each show's top 10, by views."""
    season_start = now.replace(year=config.SEASON_START.year, month=config.SEASON_START.month,
                               day=config.SEASON_START.day, hour=0, minute=0, second=0)
    windows = {
        "week": lambda v: metrics.age_days(v, now) <= config.WEEK_DAYS,
        "month": lambda v: metrics.age_days(v, now) <= config.MOMENTUM_DAYS,
        "season": lambda v: parse_ts(v["published"]) >= season_start,
        "all": lambda v: True,
    }
    out = {}
    for key, keep in windows.items():
        eps = sorted((v for v in pool if keep(v)), key=lambda v: -v["views"])
        chosen = {v["id"]: v for v in eps[:50]}
        per = {}
        for v in eps:
            if per.get(v["slug"], 0) < 10:
                per[v["slug"]] = per.get(v["slug"], 0) + 1
                chosen.setdefault(v["id"], v)
        out[key] = sorted(chosen.values(), key=lambda v: -v["views"])
    return out


def compute(now=None):
    """Everything the pages need, from data/ alone (no network)."""
    now = now or utcnow()
    today = today_str(now)
    shows = roster.load_roster()
    by_slug = {s["slug"]: s for s in shows}
    srcs = roster.sources(shows)
    cats = {sid: catalog.load(sid, src) for sid, src in srcs.items()}
    subs = load_json(config.SUBSCRIBERS_FILE, {}) or {}

    stats, shared = [], {}
    for show in shows:
        sh = roster.shares_channel(show, shows)
        shared[show["slug"]] = sh
        st = metrics.show_stats(show, cats[roster.source_id(show)], now,
                                subs_history=subs.get(show["channel_id"]), shared=sh)
        for v in st["episodes"]:
            v["slug"] = show["slug"]
        stats.append(st)

    # Podcasts and player channels are ranked separately, each from No. 1.
    ranked = metrics.rank_shows(stats, "podcast")
    ranked_pc = metrics.rank_shows(stats, "player_channel")
    history = load_json(config.RANKS_FILE, {}) or {}
    changes = metrics.rank_changes(ranked, history, today)
    changes.update(metrics.rank_changes(ranked_pc, history, today))
    dormant = sorted((s for s in stats if s["status"] == "dormant"),
                     key=lambda s: s["last_episode"] or "", reverse=True)
    occasional = sorted((s for s in stats if s["status"] == "occasional"),
                        key=lambda s: s["last_episode"] or "", reverse=True)
    excluded = [s for s in stats if s["status"] == "excluded"]
    uncertain = [s for s in stats if s["status"] == "uncertain"]
    appearances, review = guests.build(shows, cats)

    # Every shown video, both show types; breakout scores use the new rule
    # everywhere (same show, same format, the 90 days before, 8+ videos).
    stats_by_slug = {s["slug"]: s for s in stats}
    embeds = embed.load()
    items, flags = videos.build_items(shows, cats, stats_by_slug, today, kinds=("podcast", "player_channel"))
    items = [it for it in items if embed.status(embeds, it["id"]) != "gone"]
    for it in items:
        it["embed"] = embed.status(embeds, it["id"])
    score = {it["id"]: it["breakout"] for it in items}
    for st in stats:
        st["episodes"] = [dict(v, breakout=score.get(v["id"])) for v in st["episodes"]
                          if embed.status(embeds, v["id"]) != "gone"]
    pod_items = [it for it in items if by_slug[it["show"]]["type"] == "podcast"]

    ranked_eps = [v for s in ranked for v in s["episodes"]]
    week = [v for v in ranked_eps if metrics.age_days(v, now) <= config.WEEK_DAYS]
    eow = max(week, key=lambda v: v["views"]) if week else None
    breakouts = sorted((v for v in ranked_eps if metrics.age_days(v, now) <= config.MOMENTUM_DAYS
                        and metrics.is_breakout(v.get("breakout"))),
                       key=lambda v: v["published"], reverse=True)[:6]
    # Most watched: podcasts only, like the main rankings.
    pool = [v for s in ranked + occasional + dormant if s["type"] == "podcast" for v in s["episodes"]]
    mw = _period_lists(pool, now)

    status = load_json(config.STATUS_FILE, {}) or {}
    last_ok = (status.get("ytdlp") or {}).get("last_ok")
    last_run = parse_ts(status.get("last_success"))
    return {
        "now": now, "today": today, "shows": by_slug, "shared": shared, "stats": stats,
        "ranked": ranked, "ranked_pc": ranked_pc, "occasional": occasional, "dormant": dormant, "excluded": excluded, "uncertain": uncertain,
        "appearances": appearances, "appearances_review": review, "changes": changes,
        "history": history, "episode_of_week": eow, "breakouts": breakouts,
        "most_watched": mw, "mw_shows": sorted({v["slug"] for v in pool}),
        "updated_label": (last_run or now).strftime("%b %-d, %Y, %H:%M UTC"),
        "listing_label": render.fmt_date(last_ok + "T00:00:00Z") if last_ok else None,
        "thumbs": set(), "thumbs_big": set(), "headshots": set(),
        "items": items, "flags": flags, "home": home.sections(pod_items, now, flags),
        "stream": home.stream_items(pod_items, now),
        "stream_hosts": {s["slug"]: [h["name"] if isinstance(h, dict) else h for h in s.get("hosts") or []]
                         for s in shows},
    }


def home_ids(ctx):
    h = ctx["home"]
    ids = [it["id"] for k in ("week", "trending", "latest_eps", "breakouts") for it in h[k]]
    if h["watch"]:
        ids.insert(0, h["watch"]["id"])
    return ids


def displayed_ids(ctx):
    ids = set(home_ids(ctx))
    ids.update(it["id"] for it in ctx["stream"])
    if ctx["episode_of_week"]:
        ids.add(ctx["episode_of_week"]["id"])
    ids.update(v["id"] for v in ctx["breakouts"])
    for rows in ctx["most_watched"].values():
        ids.update(v["id"] for v in rows)
    for s in ctx["ranked"] + ctx["ranked_pc"] + ctx["occasional"] + ctx["dormant"]:
        eps = s["episodes"]
        ids.update(v["id"] for v in sorted(eps, key=lambda v: v["published"], reverse=True)[:12])
        ids.update(v["id"] for v in sorted(eps, key=lambda v: -v["views"])[:10])
    return ids


def build(now=None, fetch_thumbs=True, out=None):
    ctx = compute(now)
    out = out or config.SITE_OUT
    ids = displayed_ids(ctx)
    big = [ctx["home"]["watch"]["id"]] if ctx["home"]["watch"] else []
    host_slugs = {}
    for show in ctx["shows"].values():
        for h in show.get("hosts") or []:
            if isinstance(h, dict) and h.get("url"):
                host_slugs[h["url"].rstrip("/").rsplit("/", 1)[-1].replace(".html", "")] = h["name"]
    if fetch_thumbs:
        ctx["thumbs"], ctx["thumbs_big"] = thumbs.ensure(ids, big)
        ctx["headshots"] = set(headshots.ensure(host_slugs))
        # Embed checks: homepage first, then the stream, then the rest.
        order = home_ids(ctx) + [it["id"] for it in ctx["stream"]] + sorted(ids)
        cache = embed.update(order, ctx["today"])
        for it in ctx["items"]:
            it["embed"] = embed.status(cache, it["id"])
    else:
        ctx["thumbs"], ctx["thumbs_big"] = thumbs.available(ids, big)
        ctx["headshots"] = set(headshots.available(host_slugs))
    stream_files, ctx["stream_v"] = home.stream_files(ctx["stream"], ctx, ctx["flags"])

    css = (config.SITE_SRC / "style.css").read_bytes()
    js = (config.SITE_SRC / "app.js").read_bytes()
    ctx["assets_v"] = hashlib.sha256(css + js).hexdigest()[:10]

    pages = {config.SITE_BASE + "/": ("index.html", render.index_page(ctx)),
             config.SITE_BASE + "/most-watched/": ("most-watched/index.html", render.most_watched_page(ctx)),
             config.SITE_BASE + "/player-channels/": ("player-channels/index.html", render.player_channels_page(ctx)),
             config.SITE_BASE + "/dormant/": ("dormant/index.html", render.dormant_page(ctx))}
    for s in ctx["ranked"] + ctx["ranked_pc"] + ctx["occasional"] + ctx["dormant"]:
        pages[config.SITE_BASE + "/" + s["slug"] + "/"] = (s["slug"] + "/index.html", render.show_page(ctx, s))

    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    (out / "thumbs" / "big").mkdir(parents=True)
    (out / "headshots").mkdir()
    (out / "data").mkdir()
    for rel, body in stream_files.items():
        (out / rel).write_bytes(body)
    for slug in ctx["headshots"]:
        shutil.copyfile(headshots.path_for(slug), out / "headshots" / (slug + ".webp"))
    for vid in ctx["thumbs_big"]:
        shutil.copyfile(thumbs.path_for(vid, True), out / "thumbs" / "big" / (vid + ".webp"))
    (out / "assets" / "style.css").write_bytes(css)
    (out / "assets" / "app.js").write_bytes(js)
    for vid in ctx["thumbs"]:
        shutil.copyfile(thumbs.path_for(vid), out / "thumbs" / (vid + ".webp"))
    for url, (rel, html) in pages.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    (out / "404.html").write_text(render.not_found_page(ctx), encoding="utf-8")

    state = sitemap.update_state(load_json(config.SITEMAP_STATE_FILE, {}),
                                 {u: html for u, (_, html) in pages.items()}, ctx["today"])
    save_json(config.SITEMAP_STATE_FILE, state)
    (out / "sitemap.xml").write_text(sitemap.render(state), encoding="utf-8")

    # Today's ranking, for next week's arrows. Kept 120 days.
    hist = ctx["history"]
    hist[ctx["today"]] = {s["slug"]: s["rank"] for s in ctx["ranked"] + ctx["ranked_pc"]}
    cutoff = (ctx["now"].date() - timedelta(days=120)).isoformat()
    save_json(config.RANKS_FILE, {d: r for d, r in hist.items() if d >= cutoff})

    roster_doc = load_json(config.CHANNELS_FILE)
    save_json(config.EXCLUDED_FILE, {
        "_about": "Shows not in the rankings and why. Rebuilt on every run; review and edit data/channels.json to change the roster.",
        "updated": ctx["today"],
        "excluded_by_rules": [{"slug": s["slug"], "name": ctx["shows"][s["slug"]]["name"], "type": s["type"],
                               "channel_id": ctx["shows"][s["slug"]]["channel_id"], "reason": s["reason"]}
                              for s in ctx["excluded"]],
        "uncertain": [{"slug": s["slug"], "name": ctx["shows"][s["slug"]]["name"], "reason": s["reason"]}
                      for s in ctx["uncertain"]],
        "not_in_roster": roster_doc.get("not_ranked", []),
    })
    write_appearances(ctx)
    _log("built %d pages: %d podcasts and %d player channels ranked, %d occasional, %d dormant, %d excluded, %d thumbnails"
         % (len(pages), len(ctx["ranked"]), len(ctx["ranked_pc"]), len(ctx["occasional"]), len(ctx["dormant"]),
            len(ctx["excluded"]),
            len(ctx["thumbs"])))
    return ctx


REVIEW_MENTIONS = 1000   # plain title mentions kept in appearances_review.json


def write_appearances(ctx):
    """data/appearances.json (confirmed guests, shown on the site) and
    data/appearances_review.json (possible guests, not shown)."""
    names = guests.PlayerIndex.load().display
    items = {k: dict(v, name=names.get(v["player"], v["player"])) for k, v in ctx["appearances"].items()}
    save_json(config.APPEARANCES_FILE, {
        "_about": ("Confirmed guest appearances: stated explicitly in the title or description and matched to "
                   "one NBA Career Map player, or added in data/appearances_manual.json. group: clips of the "
                   "same episode share one group and count as one appearance. Generated on every build."),
        "items": items}, line_per_key="items")
    rev = sorted(ctx["appearances_review"].items(), key=lambda kv: -(kv[1].get("views") or 0))
    # Plain title mentions run to tens of thousands: keep the most viewed
    # ones, and every stated guest held back (same name, or a regular).
    plain = [kv for kv in rev if kv[1]["reason"].startswith("named in the title")]
    keep = {k for k, _ in plain[:REVIEW_MENTIONS]}
    rev = [kv for kv in rev if kv[0] in keep or not kv[1]["reason"].startswith("named in the title")]
    save_json(config.APPEARANCES_REVIEW_FILE, {
        "_about": ("Possible guests, NOT shown on the site: players named in a title without being stated as "
                   "guests (the %d most viewed of %d), a stated guest whose name belongs to more than one "
                   "player, or someone stated in so many of one show's episodes that they are likely a co-host "
                   "or regular. To confirm one, add {\"video\": ..., \"player\": <Career Map slug>} to \"add\" "
                   "in data/appearances_manual.json. Sorted by views. Generated on every build."
                   % (min(REVIEW_MENTIONS, len(plain)), len(plain))),
        "total_title_mentions": len(plain),
        "items": [dict(v, key=k) for k, v in rev]}, line_per_key="items")

