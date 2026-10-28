"""Build the static site into site/ from the committed data.

Also writes the files the build owns in data/: ranks.json (daily ranking
history, for the weekly rank change), excluded.json (shows left out of the
rankings, with the reason) and sitemap-state.json (content hash per URL).
"""
import hashlib
import shutil
import sys
from datetime import timedelta

from . import art, catalog, config, embed, guests, headshots, home, mentions, metrics, people, rankmetrics, render, roster, sitemap, talk, thumbs, videos
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
    per_show = {}
    for it in items:
        per_show.setdefault(it["show"], []).append(it)
    rank_metrics = {s["slug"]: rankmetrics.show_metrics(per_show.get(s["slug"], []), s, now, flags, shared[s["slug"]])
                    for s in ranked + ranked_pc}
    shown = ranked + ranked_pc + occasional + dormant
    show_metrics = {s["slug"]: rank_metrics.get(s["slug"]) or
                    rankmetrics.show_metrics(per_show.get(s["slug"], []), s, now, flags, shared[s["slug"]]) for s in shown}
    pindex = guests.PlayerIndex.load()
    names = pindex.display
    players = people.build(by_slug, [s["slug"] for s in shown], per_show, appearances, names)

    # Talked about: players and teams the videos discuss (titles and chapter lines).
    item_by_id = {it["id"]: it for it in items}
    matcher = mentions.Matcher.load(pindex)
    ments, mention_review = mentions.build([by_slug[s["slug"]] for s in shown], cats, items, appearances, matcher)
    cat_videos = {}
    for c in cats.values():
        cat_videos.update(c["videos"])
    talk_map = talk.build(ments, mentions.groups(ments, items, cat_videos), item_by_id)
    people.add_talked_about(players, talk_map, names, appearances, item_by_id)
    ignored = {sl for sl in (pindex.lookup(n)[0] for n in
                             (load_json(config.MENTION_IGNORE_FILE, {}) or {}).get("names", [])) if sl}
    published = (load_json(config.PUBLISHED_PLAYERS_FILE, {}) or {}).get("players", [])
    people.keep_published(players, published, names, appearances, item_by_id, ignored)
    teams = (load_json(config.TEAMS_FILE, {}) or {}).get("teams", [])
    active_by_team, player_team = {}, {}
    for full, _, abbrev in (load_json(config.NBA_ACTIVE_FILE, {}) or {}).get("players", []):
        slug, _ = pindex.lookup(full)
        team = matcher.team_by_abbrev.get(abbrev)
        if slug and team:
            active_by_team.setdefault(team, []).append(slug)
            player_team[slug] = team

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
        "changes_day": metrics.comparable_day(history, today) if changes else None,
        "rank_metrics": rank_metrics, "metrics_have": rankmetrics.available(rank_metrics.values()),
        "show_metrics": show_metrics, "per_show": per_show, "players": players,
        "item_by_id": item_by_id, "player_names": names, "published_players": published, "ignored_players": ignored,
        "mentions": ments, "mention_review": mention_review, "talk": talk_map, "teams": teams,
        "team_by_slug": {t["slug"]: t for t in teams}, "active_by_team": active_by_team, "player_team": player_team,
        "stats_by_slug": stats_by_slug, "art": set(),
        "descriptions": {s["slug"]: (cats.get(roster.source_id(by_slug[s["slug"]])) or {}).get("description") for s in shown},
        "related": related_shows(shown, appearances, show_metrics),
        "history": history, "episode_of_week": eow, "breakouts": breakouts,
        "most_watched": mw, "mw_shows": sorted({v["slug"] for v in pool}),
        "updated_label": (last_run or now).strftime("%b %-d, %Y, %H:%M UTC"),
        "listing_label": render.fmt_date(last_ok + "T00:00:00Z") if last_ok else None,
        "thumbs": set(), "thumbs_big": set(), "headshots": set(),
        "items": items, "flags": flags, "home": home.sections(pod_items, now, flags),
        "stream": home.stream_items(pod_items, now),
        "top_pool": home.top_pool(pod_items, now),
        "stream_hosts": {s["slug"]: [h["name"] if isinstance(h, dict) else h for h in s.get("hosts") or []]
                         for s in shows},
    }


def related_shows(shown, appearances, show_metrics, n=3):
    """{show: [3 other shows]}: the same type first, then most confirmed
    guests in common, then the closest typical full-episode views."""
    import math
    guests_of = {}
    for it in appearances.values():
        guests_of.setdefault(it["show"], set()).add(it["player"])
    typ = {s["slug"]: (show_metrics[s["slug"]]["x"]["typf"][0] or 1) for s in shown}
    out = {}
    for s in shown:
        mine = guests_of.get(s["slug"], set())
        others = [o for o in shown if o["slug"] != s["slug"]]
        others.sort(key=lambda o: (o["type"] != s["type"], -len(mine & guests_of.get(o["slug"], set())),
                                   abs(math.log(typ[o["slug"]]) - math.log(typ[s["slug"]])), o["slug"]))
        out[s["slug"]] = [o["slug"] for o in others[:n]]
    return out


def _add_top(ctx):
    ctx["top"] = home.top_sections(ctx["top_pool"], ctx["now"], ctx["flags"])


def home_ids(ctx):
    h = ctx["home"]
    ids = [it["id"] for k in ("week", "trending", "latest_eps", "breakouts") for it in h[k]]
    if h["watch"]:
        ids.insert(0, h["watch"]["id"])
    return ids


def displayed_ids(ctx):
    ids = set(home_ids(ctx))
    ids.update(it["id"] for it in ctx["stream"])
    ids.update(it["id"] for it in ctx["top_pool"])
    if ctx["episode_of_week"]:
        ids.add(ctx["episode_of_week"]["id"])
    ids.update(v["id"] for v in ctx["breakouts"])
    for rows in ctx["most_watched"].values():
        ids.update(v["id"] for v in rows)
    for s in ctx["ranked"] + ctx["ranked_pc"] + ctx["occasional"] + ctx["dormant"]:
        eps = s["episodes"]
        ids.update(v["id"] for v in sorted(eps, key=lambda v: v["published"], reverse=True)[:12])
        ids.update(v["id"] for v in sorted(eps, key=lambda v: -v["views"])[:10])
        vids = ctx["per_show"].get(s["slug"], [])
        ids.update(it["id"] for it in sorted(vids, key=lambda it: it["published"], reverse=True)[:12])
        for fmt in (metrics.FULL, metrics.CLIP):
            ids.update(it["id"] for it in sorted((x for x in vids if x["fmt"] == fmt), key=lambda x: -x["views"])[:8])
        for k in ("gain24", "gain7"):
            ids.update(it["id"] for it in sorted((x for x in vids if x.get(k)), key=lambda x: -x[k])[:8])
    for p in ctx.get("players", {}).values():
        ids.update(it["id"] for it, _ in render.player_videos(p, ctx))
    # Talked about: the cards on player and team pages.
    for target, groups in ctx.get("talk", {}).items():
        if (target[0] == "team" and len(groups) >= 3) or target[1] in ctx.get("players", {}):
            for g in groups[:8] + sorted(groups, key=lambda g: -g.views)[:8]:
                ids.add(g.lead["id"])
    return ids


def build(now=None, fetch_thumbs=True, out=None):
    now = now or utcnow()
    ctx = compute(now)
    _add_top(ctx)
    if fetch_thumbs:
        # Embed checks first (homepage, then the stream, then the rest), so a
        # video found deleted or private is left out of this very build.
        order = home_ids(ctx) + [it["id"] for it in ctx["stream"]] + [it["id"] for it in ctx["top_pool"]] \
            + sorted(displayed_ids(ctx))
        before = embed.load()
        cache = embed.update(order, ctx["today"])
        if any(embed.status(cache, i) == "gone" and embed.status(before, i) != "gone" for i in order):
            ctx = compute(now)
            _add_top(ctx)
    out = out or config.SITE_OUT
    ids = displayed_ids(ctx)
    big = [ctx["home"]["watch"]["id"]] if ctx["home"]["watch"] else []
    people.CURRENT = ctx["players"]
    host_slugs = {}
    for show in ctx["shows"].values():
        for h in (show.get("hosts") or []) + (show.get("former_hosts") or []):
            if isinstance(h, dict) and h.get("url"):
                host_slugs[h["url"].rstrip("/").rsplit("/", 1)[-1].replace(".html", "")] = h["name"]
    # Players with a page, and the guests named on show pages.
    for p in ctx["players"].values():
        host_slugs.setdefault(p["slug"], p["name"])
    for it in ctx["appearances"].values():
        host_slugs.setdefault(it["player"], ctx["player_names"].get(it["player"], it["player"]))
    ctx["art"] = art.available({s["channel_id"] for s in ctx["shows"].values()})
    if fetch_thumbs:
        ctx["thumbs"], ctx["thumbs_big"] = thumbs.ensure(ids, big)
        ctx["headshots"] = set(headshots.ensure(host_slugs))
    else:
        ctx["thumbs"], ctx["thumbs_big"] = thumbs.available(ids, big)
        ctx["headshots"] = set(headshots.available(host_slugs))
    # Player pages draw the head at 88px: those use the 320px face-fill copy.
    page_heads = {p["slug"]: p["name"] for p in ctx["players"].values() if p["slug"] in ctx["headshots"]}
    ctx["headshots_big"] = set(headshots.ensure(page_heads, big=True) if fetch_thumbs
                               else headshots.available(page_heads, big=True))
    stream_files, ctx["stream_v"] = home.stream_files(ctx["stream"], ctx, ctx["flags"])
    top_files, ctx["top_v"] = home.top_files(ctx["top_pool"], ctx, ctx["flags"])
    stream_files.update(top_files)

    css = (config.SITE_SRC / "style.css").read_bytes()
    js = (config.SITE_SRC / "app.js").read_bytes()
    ctx["assets_v"] = hashlib.sha256(css + js).hexdigest()[:10]

    pages = {config.SITE_BASE + "/": ("index.html", render.index_page(ctx)),
             config.SITE_BASE + "/most-watched/": ("most-watched/index.html", render.most_watched_page(ctx)),
             config.SITE_BASE + "/top-videos/": ("top-videos/index.html", render.top_videos_page(ctx)),
             config.SITE_BASE + "/player-channels/": ("player-channels/index.html", render.player_channels_page(ctx)),
             config.SITE_BASE + "/dormant/": ("dormant/index.html", render.dormant_page(ctx))}
    for s in ctx["ranked"] + ctx["ranked_pc"] + ctx["occasional"] + ctx["dormant"]:
        pages[config.SITE_BASE + "/" + s["slug"] + "/"] = (s["slug"] + "/index.html", render.show_page(ctx, s))
    pages[config.SITE_BASE + "/methodology/"] = ("methodology/index.html", render.methodology_page(ctx))
    pages[config.SITE_BASE + "/teams/"] = ("teams/index.html", render.teams_index_page(ctx))
    for t in ctx["teams"]:
        pages[config.SITE_BASE + "/teams/" + t["slug"] + "/"] = ("teams/%s/index.html" % t["slug"], render.team_page(ctx, t))
    if ctx["players"]:
        pages[config.SITE_BASE + "/players/"] = ("players/index.html", render.players_index_page(ctx))
    for p in ctx["players"].values():
        pages[config.SITE_BASE + "/players/" + p["slug"] + "/"] = ("players/%s/index.html" % p["slug"],
                                                                   render.player_page(ctx, p))

    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    (out / "thumbs" / "big").mkdir(parents=True)
    (out / "headshots" / "320").mkdir(parents=True)
    (out / "art").mkdir()
    for cid in ctx["art"]:
        shutil.copyfile(art.path_for(cid), out / "art" / (cid + ".webp"))
    (out / "data").mkdir()
    for rel, body in stream_files.items():
        (out / rel).write_bytes(body)
    for slug in ctx["headshots"]:
        shutil.copyfile(headshots.path_for(slug), out / "headshots" / (slug + ".webp"))
    for slug in ctx["headshots_big"]:
        shutil.copyfile(headshots.path_for(slug, True), out / "headshots" / "320" / (slug + ".webp"))
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
    # Pages that moved: a stub at the old address pointing at the new one.
    for old_rel, new_rel in ((load_json(config.MOVED_PAGES_FILE, {}) or {}).get("moved") or {}).items():
        if (out / new_rel / "index.html").exists() and not (out / old_rel / "index.html").exists():
            (out / old_rel).mkdir(parents=True, exist_ok=True)
            (out / old_rel / "index.html").write_text(render.moved_page(config.SITE_BASE + "/" + new_rel), encoding="utf-8")

    state = sitemap.update_state(load_json(config.SITEMAP_STATE_FILE, {}),
                                 {u: html for u, (_, html) in pages.items()}, ctx["today"])
    save_json(config.SITEMAP_STATE_FILE, state)
    (out / "sitemap.xml").write_text(sitemap.render(state), encoding="utf-8")

    # Today's ranking, for next week's arrows. Kept 120 days.
    hist = ctx["history"]
    hist[ctx["today"]] = dict({s["slug"]: s["rank"] for s in ctx["ranked"] + ctx["ranked_pc"]}, _rule=config.RANK_RULE)
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
    write_mentions(ctx)
    # Every published player page, kept for later builds (pages are sticky).
    doc = load_json(config.PUBLISHED_PLAYERS_FILE, {}) or {}
    doc["players"] = sorted((set(ctx["published_players"]) | set(ctx["players"])) - set(ctx["ignored_players"]))
    save_json(config.PUBLISHED_PLAYERS_FILE, doc, line_per_key="players")
    _log("built %d pages: %d podcasts and %d player channels ranked, %d occasional, %d dormant, %d excluded, %d thumbnails"
         % (len(pages), len(ctx["ranked"]), len(ctx["ranked_pc"]), len(ctx["occasional"]), len(ctx["dormant"]),
            len(ctx["excluded"]),
            len(ctx["thumbs"])))
    return ctx


REVIEW_MENTIONS = 1000   # plain title mentions kept in appearances_review.json


def write_mentions(ctx):
    """data/mentions.json: the players and teams each video talks about."""
    # Sorted, so the file only changes when a mention does (set order is not stable between runs).
    items = {vid: sorted([m["kind"], m["slug"], m["src"], m["t"], m["how"]] for m in ms)
             for vid, ms in sorted(ctx["mentions"].items())}
    save_json(config.MENTIONS_FILE, {
        "_about": ("Talked about: per video, [kind (player or team), Career Map or team slug, source (title, "
                   "chapter or manual), seconds into the video (chapters) or null, how it was matched]. Generated on "
                   "every build; edit data/mentions_manual.json to add or remove one."),
        "items": items}, line_per_key="items")


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
        "items": [dict(v, key=k) for k, v in rev],
        # Talked about: shared names and lone surnames no team settled.
        "mentions_total": len(ctx["mention_review"]),
        "mentions": [dict(v, key=k) for k, v in sorted(ctx["mention_review"].items(),
                                                       key=lambda kv: -(kv[1].get("views") or 0))[:REVIEW_MENTIONS]]},
        line_per_key="items", also=("mentions",))

