"""Video feeds: the one way every page lists videos.

A feed is a sticky row of chips (Trending, Most watched, Latest, Episodes...)
over a vertical stream of full-width cards on phones and a grid on wider
screens, never a sideways carousel. The first 12 videos of the default chip
(and, on the homepage and Top videos, the first module card) are in the HTML;
the page script loads the rest from data/feed-<id>.json as the visitor nears
the bottom, with a "Load more" button as the fallback.

A chip is {k, label, note, f: {fmt, days, role, has}, s: sort}:
  f.fmt   full / clip / short        f.days  posted in the last N days
  f.role  host / guest / talk        f.has   g24 / g7 / bo (that number exists)
  s       pub (newest), views, g24, g7, bo (highest first)
The page script applies the same rules to the same rows (pp/cards.py and
site_src/app.js write the same card).

Rows: [id, show index, format, published, views, duration, title, views
gained in 24h, breakout, embeddable 0/1, thumbnail 0/1/2 (2 = a vertical one
for a Short), views gained in 7 days, extra]. extra (or null): {"r": role,
"t": seconds to start at, "c": [[clip id, title, seconds], ...]} for the
clips of one discussion.
"""
import hashlib
import json
from datetime import timedelta

from . import config
from .metrics import FULL, CLIP, SHORT
from .util import parse_ts

FIRST = 12           # cards in the HTML
MODULE_EVERY = 8     # a module card after every 8 videos (homepage, Top videos)
PAGE_CAP = 36        # show, player and team pages: the first 36 of each chip


def chip(k, label, note, s="pub", **f):
    return {"k": k, "label": label, "note": note, "f": {a: b for a, b in f.items() if b is not None}, "s": s}


def _key(it, s):
    if s == "pub":
        return it["published"][:16]
    if s == "views":
        return it["views"]
    if s == "g24":
        return it.get("gain24") or 0
    if s == "g7":
        return it.get("gain7") or 0
    if s == "bo":
        return it.get("breakout") or 0
    raise ValueError(s)


def apply(items, c, now):
    """The videos one chip shows, in order. items: [(item, extra)]."""
    f = c["f"]
    out = []
    for it, x in items:
        if f.get("fmt") and it["fmt"] != f["fmt"]:
            continue
        if f.get("days") and parse_ts(it["published"]) < now - timedelta(days=f["days"]):
            continue
        if f.get("role") and (x or {}).get("r") != f["role"]:
            continue
        has = f.get("has")
        if has == "g24" and it.get("gain24") is None or has == "g7" and it.get("gain7") is None \
                or has == "bo" and it.get("breakout") is None:
            continue
        out.append((it, x))
    s = c["s"]
    # Ties: newest first, to the minute (the data file keeps minutes), then id.
    out.sort(key=lambda p: (_key(p[0], s), p[0]["published"][:16], p[0]["id"]), reverse=True)
    return out


class Feed:
    """One page's feed: its videos, chips and default chip."""

    def __init__(self, fid, items, chips, default=None, cap=None, modules=False, filters=(), end_link=None):
        self.fid = fid
        self.chips = [c for c in chips if c]
        self.cap = cap
        self.modules = modules
        self.filters = filters            # ("q", "show", "host") shown in "Search and filter"
        self.end_link = end_link          # (label, url) after the last video
        self.default = default if any(c["k"] == default for c in self.chips) else \
            (self.chips[0]["k"] if self.chips else None)
        self.items = items
        self.display_cap = cap            # most videos one chip shows (None: all)
        self.alltime = None               # Top videos: {"show": n, "days": d}, see app.js

    def lists(self, now):
        """{chip key: [(item, extra)]}, capped."""
        out = {}
        for c in self.chips:
            lst = apply(self.items, c, now)
            out[c["k"]] = lst[:self.cap] if self.cap else lst
        return out

    def rows_items(self, now):
        """The videos the data file needs: every chip's list (capped)."""
        seen, out = set(), []
        for lst in self.lists(now).values():
            for it, x in lst:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    out.append((it, x))
        return out

    def ids(self, now):
        return {it["id"] for it, _ in self.rows_items(now)}


def thumb_flag(it, ctx):
    if it["fmt"] == SHORT and it["id"] in ctx.get("thumbs_v", ()):
        return 2
    return 1 if it["id"] in ctx.get("thumbs", ()) else 0


def data_file(feed, ctx):
    """(JSON text, version) of data/feed-<id>.json."""
    from .cards import host_people
    pairs = feed.rows_items(ctx["now"])
    show_slugs = sorted({it["show"] for it, _ in pairs})
    idx = {s: i for i, s in enumerate(show_slugs)}
    shows = [[s, ctx["shows"][s]["name"], [[n, u, h] for n, u, h in host_people(ctx["shows"][s], ctx)]]
             for s in show_slugs]
    rows = []
    for it, x in pairs:
        rows.append([it["id"], idx[it["show"]], it["fmt"], it["published"][:16] + "Z", it["views"], it.get("duration"),
                     it["title"], it.get("gain24"), round(it["breakout"], 2) if it.get("breakout") else None,
                     0 if it.get("embed") == "no" else 1, thumb_flag(it, ctx), it.get("gain7"), x or None])
    body = {"now": ctx["now"].strftime("%Y-%m-%dT%H:%M:%SZ"), "cap": feed.display_cap, "shows": shows, "rows": rows}
    if feed.alltime:
        body["alltime"] = feed.alltime
    text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    return text, hashlib.sha256(text.encode()).hexdigest()[:10]


ROLE_LABEL = {"host": "Host", "guest": "Guest", "talk": "Talked about"}


def card_for(it, x, ctx, c):
    """The card for one video in this chip (same as app.js card())."""
    from .cards import clips_more, video_card
    x = x or {}
    extra = "gain24" if c["s"] == "g24" else "gain7" if c["s"] == "g7" else ""
    label = x.get("l") or ROLE_LABEL.get(x.get("r"), "")
    return video_card(it, ctx, show_breakout=c["s"] == "bo", extra=extra, label=label,
                      start=x.get("t"), more=clips_more(x.get("c")))


def feed_html(feed, ctx, modules=(), hint="", heading=None, anchor=None):
    """The feed section. modules: [(key, html)] rotated every 8 videos (the
    first one is in the HTML, after the 8th video)."""
    from html import escape
    e = lambda s: escape("" if s is None else str(s), quote=True)
    B = config.BASE_PATH
    text, ver = data_file(feed, ctx)
    ctx.setdefault("feed_files", {})["data/feed-%s.json" % feed.fid] = text
    lists = feed.lists(ctx["now"])
    c = next(x for x in feed.chips if x["k"] == feed.default)
    first = lists[feed.default][:FIRST]
    mods = [(k, h) for k, h in modules if h]
    cards = []
    for i, (it, x) in enumerate(first, 1):
        cards.append(card_for(it, x, ctx, c))
        if mods and i == MODULE_EVERY and len(first) > MODULE_EVERY:
            cards.append(mods[0][1])
    chips = "".join('<button type="button" class="chip%s" data-chip="%s" aria-pressed="%s">%s</button>'
                    % (" active" if x["k"] == feed.default else "", e(x["k"]),
                       "true" if x["k"] == feed.default else "false", e(x["label"])) for x in feed.chips)
    filt = ""
    if feed.filters:
        shows = sorted({it["show"] for it, _ in feed.rows_items(ctx["now"])}, key=lambda s: ctx["shows"][s]["name"].lower())
        hosts = sorted({n for s in shows for n in ctx["stream_hosts"].get(s, [])})
        opt = lambda pairs: "".join('<option value="%s">%s</option>' % (e(v), e(l)) for v, l in pairs)
        bits = []
        if "q" in feed.filters:
            bits.append('<label class="sr" for="%s-q">Search</label><input id="%s-q" class="sel ff-q" type="search" '
                        'placeholder="Search title, show or host" autocomplete="off">' % (feed.fid, feed.fid))
        if "show" in feed.filters and len(shows) > 1:
            bits.append('<label class="sr" for="%s-show">Show</label><select id="%s-show" class="sel ff-show">'
                        '<option value="">All shows</option>%s</select>'
                        % (feed.fid, feed.fid, opt([(s, ctx["shows"][s]["name"]) for s in shows])))
        if "host" in feed.filters and len(hosts) > 1:
            bits.append('<label class="sr" for="%s-host">Host</label><select id="%s-host" class="sel ff-host">'
                        '<option value="">All hosts</option>%s</select>' % (feed.fid, feed.fid, opt([(h, h) for h in hosts])))
        if "days" in feed.filters:
            bits.append('<label class="sr" for="%s-days">Posted</label><select id="%s-days" class="sel ff-days">'
                        '<option value="">Any time</option>%s</select>'
                        % (feed.fid, feed.fid, opt([("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"),
                                                    ("365", "Last 365 days")])))
        if bits:
            filt = '<details class="feed-filters"><summary>Search and filter</summary><div class="ff">%s</div></details>' % "".join(bits)
    tpl = ('<template class="feed-mods">%s</template>' % "".join(h for _, h in mods)) if mods else ""
    # The end of a list: every video, or (when the list was cut at the cap) the cap.
    cut = ('<span class="fe-cap" hidden>Lists here stop at %d videos.</span>' % feed.display_cap) if feed.display_cap else ""
    end = ('<p class="feed-end hint-below" hidden><span class="fe-all">That is every video here.</span>%s%s</p>'
           % (cut, (' <a href="%s" target="_blank" rel="noopener">%s</a>' % (e(feed.end_link[1]), e(feed.end_link[0])))
              if feed.end_link else ""))
    more_left = len(lists[feed.default]) > len(first)
    return ('<section class="block feed" id="%s" data-src="%s/data/feed-%s.json?v=%s" data-base="%s" '
            'data-chips=\'%s\' data-default="%s" data-first="%d"%s>%s'
            '<div class="feed-bar"><div class="chips" role="group" aria-label="Show videos">%s</div>'
            '<p class="feed-note" aria-live="polite">%s</p></div>%s'
            '<div class="feed-list">%s</div>'
            '<div class="feed-sentinel" aria-hidden="true"></div>'
            '<button class="loadmore" type="button"%s>Load more</button>%s%s%s</section>\n'
            % (e(anchor or feed.fid), B, e(feed.fid), ver, B,
               e(json.dumps(feed.chips, separators=(",", ":"))), e(feed.default), len(first),
               ' data-modules="1"' if mods else "",
               ('<div class="block-head"><h2>%s</h2></div>' % e(heading)) if heading else "",
               chips, e(c["note"]), filt, "".join(cards), "" if more_left else " hidden", end,
               ('<p class="hint-below">%s</p>' % hint) if hint else "", tpl))


# ── each page's feed ──

def _nonempty(chips, items, now):
    return [c for c in chips if c and apply(items, c, now)]


def home(ctx):
    """Homepage: podcast videos of the last 90 days. Trending first when
    there are at least 12 videos with a 24-hour gain, else Most watched."""
    now = ctx["now"]
    items = [(it, None) for it in ctx["stream"]]
    n24 = sum(1 for it in ctx["stream"] if it.get("gain24") is not None)
    chips = [
        chip("trending", "Trending", "Views gained in the last 24 hours, from our daily view counts", "g24", has="g24")
        if ctx["flags"].get("g24") and n24 >= 3 else None,
        chip("watched", "Most watched", "Videos posted in the last 7 days, by views", "views", days=7),
        chip("latest", "Latest", "Every video from the last 90 days, newest first"),
        chip("episodes", "Episodes", "Full episodes (20 minutes or longer), newest first", fmt=FULL),
        chip("clips", "Clips", "Clips (1 to 20 minutes), newest first", fmt=CLIP),
        chip("shorts", "Shorts", "Shorts (under a minute, or from the Shorts tab), newest first", fmt=SHORT),
    ]
    chips = _nonempty(chips, items, now)
    default = "trending" if n24 >= FIRST and any(c["k"] == "trending" for c in chips) else "watched"
    return Feed("home", items, chips, default, modules=True, filters=("q", "show", "host"))


def top(ctx):
    """Top videos: the all-time pool (pp/home.py top_pool)."""
    from . import home
    now = ctx["now"]
    items = [(it, None) for it in ctx["top_pool"]]
    f = ctx["flags"]
    chips = [
        chip("views", "Most viewed", "The most viewed videos, all time", "views"),
        chip("trending", "Trending", "Views gained in the last 24 hours, from our daily view counts", "g24", has="g24")
        if f.get("g24") else None,
        chip("gain7", "Gained, 7 days", "Views gained in the last 7 days, from our daily view counts", "g7", has="g7")
        if f.get("g7") else None,
        chip("episodes", "Episodes", "The most viewed full episodes (20 minutes or longer), all time", "views", fmt=FULL),
        chip("clips", "Clips", "The most viewed clips (1 to 20 minutes), all time", "views", fmt=CLIP),
        chip("shorts", "Shorts", "The most viewed Shorts, all time", "views", fmt=SHORT),
        chip("breakouts", "Breakouts", "Highest breakout scores: views divided by the median views of the same show's "
             "videos of the same format from the 90 days before (at least 8 of them)", "bo", has="bo"),
    ]
    fd = Feed("top", items, _nonempty(chips, items, now), "views", modules=True, filters=("q", "show", "host", "days"))
    fd.display_cap = home.TOP_OVERALL
    fd.alltime = {"show": home.TOP_PER_SHOW, "days": home.STREAM_DAYS}
    return fd


def _page_chips(items, now, extra=()):
    chips = [
        chip("latest", "Latest", "Newest first"),
        chip("views", "Most viewed", "The most viewed, all time", "views"),
        chip("episodes", "Episodes", "Full episodes (20 minutes or longer), newest first", fmt=FULL),
        chip("clips", "Clips", "Clips (1 to 20 minutes), newest first", fmt=CLIP),
        chip("shorts", "Shorts", "Shorts, newest first", fmt=SHORT),
    ] + list(extra)
    return _nonempty(chips, items, now)


def show(ctx, slug):
    s = ctx["shows"][slug]
    items = [(it, None) for it in ctx["per_show"].get(slug, [])]
    end = ("More on the show's YouTube channel", "https://www.youtube.com/channel/" + s["channel_id"])
    return Feed("show-" + slug, items, _page_chips(items, ctx["now"]), cap=PAGE_CAP, filters=("q",), end_link=end)


def player(ctx, p):
    """A player's own appearances (host and guest) and the discussions that
    talk about him (one card per episode, its clips listed under it)."""
    from .cards import talk_extra
    from .render import player_videos
    items, seen = [], set()
    for it, role in player_videos(p, ctx):
        x = {"r": "guest"} if role == "guest" else {"r": "host"}
        if role == "former host":
            x["l"] = "Former host"
        items.append((it, x))
        seen.add(it["id"])
    for g in ctx["talk"].get(("player", p["slug"])) or []:
        if g.lead["id"] not in seen:
            seen.add(g.lead["id"])
            items.append((g.lead, talk_extra(g)))
    extra = [chip("host", "Host", "Videos from the shows he hosts, newest first", role="host"),
             chip("guest", "Guest", "Episodes and clips where he is a guest, newest first", role="guest"),
             chip("talk", "Talked about", "Videos whose title or chapters talk about him, newest first", role="talk")]
    return Feed("player-" + p["slug"], items, _page_chips(items, ctx["now"], extra), cap=PAGE_CAP,
                filters=("q", "show"))


def team(ctx, t):
    from .cards import talk_extra
    items = [(g.lead, talk_extra(g)) for g in ctx["talk"].get(("team", t["slug"])) or []]
    return Feed("team-" + t["slug"], items, _page_chips(items, ctx["now"]), cap=PAGE_CAP, filters=("q", "show"))


def all_feeds(ctx):
    """Every page's feed, built once before thumbnails are fetched (the
    cards need them) and rendered later."""
    out = {"home": home(ctx), "top": top(ctx)}
    for s in ctx["ranked"] + ctx["ranked_pc"] + ctx["occasional"] + ctx["dormant"]:
        out["show-" + s["slug"]] = show(ctx, s["slug"])
    for p in ctx["players"].values():
        out["player-" + p["slug"]] = player(ctx, p)
    for t in ctx["teams"]:
        out["team-" + t["slug"]] = team(ctx, t)
    return {k: v for k, v in out.items() if v.chips}
