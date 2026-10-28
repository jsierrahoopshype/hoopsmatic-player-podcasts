"""HTML for every page. Plain functions returning strings; numbers are written
into the HTML itself (the script only sorts and filters what is already there)."""
import json
from datetime import timedelta
from html import escape

from . import config, metrics
from .util import parse_ts

B = config.BASE_PATH

FOOTER = ('<footer class="site-foot">'
          '<p>Anything wrong? Email us at <a href="mailto:hoopsmatic@hoopsmatic.com">hoopsmatic@hoopsmatic.com</a></p>'
          '<p>For business inquiries, contact us at <a href="mailto:ads@hoopsmatic.com">ads@hoopsmatic.com</a></p>'
          '</footer>')


def e(s):
    return escape("" if s is None else str(s), quote=True)


# ── number and date formatting ──

def compact(n):
    if n is None:
        return "–"
    n = float(n)
    a = abs(n)
    if a >= 1e9:
        s = "%.2fB" % (n / 1e9)
    elif a >= 1e6:
        s = ("%.2fM" if a < 1e7 else "%.1fM") % (n / 1e6)
    elif a >= 1e3:
        s = ("%.1fK" if a < 1e5 else "%.0fK") % (n / 1e3)
    else:
        return "%d" % round(n)
    return s.replace(".00M", "M").replace(".0K", "K").replace(".0M", "M")


def full(n):
    return "–" if n is None else "{:,}".format(int(round(n)))


def signed(n):
    if n is None:
        return "–"
    return ("+" if n > 0 else "") + compact(n) if n else "0"


def pct(p):
    if p is None:
        return ""
    return "%+.1f%%" % p


def one_dec(x):
    return "–" if x is None else "%.1f" % x


def fmt_date(iso_s):
    d = parse_ts(iso_s)
    return d.strftime("%b %-d, %Y") if d else "–"


def fmt_len(sec):
    if sec is None:
        return "length pending"
    sec = int(sec)
    h, m = divmod(sec // 60, 60)
    return ("%d:%02d:%02d" % (h, m, sec % 60)) if h else ("%d:%02d" % (m, sec % 60))


def yt_url(vid):
    return "https://www.youtube.com/watch?v=" + vid


def show_url(slug):
    return B + "/" + slug + "/"


# ── building blocks ──

def head(title, desc, url, assets_v, extra=""):
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n"
            '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "<title>%s</title>\n" % e(title) +
            '<meta name="description" content="%s">\n' % e(desc) +
            '<link rel="canonical" href="%s">\n' % e(url) +
            '<meta name="robots" content="index, follow">\n'
            '<meta property="og:type" content="website">\n'
            '<meta property="og:site_name" content="HoopsMatic">\n'
            '<meta property="og:title" content="%s">\n' % e(title) +
            '<meta property="og:description" content="%s">\n' % e(desc) +
            '<meta property="og:url" content="%s">\n' % e(url) +
            '<meta name="twitter:card" content="summary">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@400;500;600&amp;display=swap" rel="stylesheet">\n'
            '<link rel="stylesheet" href="%s/assets/style.css?v=%s">\n' % (B, assets_v) +
            extra + "</head>\n")


def tabs(active):
    items = [("rankings", "Rankings", B + "/"), ("player-channels", "Player channels", B + "/player-channels/"),
             ("top-videos", "Top videos", B + "/top-videos/"),
             ("most-watched", "Most watched", B + "/most-watched/"),
             ("players", "Players", B + "/players/"),
             ("teams", "Teams", B + "/teams/"),
             ("dormant", "Occasional & dormant", B + "/dormant/")]
    return '<nav class="tabs">' + "".join(
        '<a href="%s"%s>%s</a>' % (href, ' class="active"' if k == active else "", label)
        for k, label, href in items) + "</nav>\n"


def page(title, desc, url, assets_v, active, body, extra_head=""):
    return (head(title, desc, url, assets_v, extra_head) + "<body>\n<div class=\"container\">\n" +
            tabs(active) + body + FOOTER + "\n</div>\n"
            '<script src="%s/assets/app.js?v=%s" defer></script>\n</body>\n</html>\n' % (B, assets_v))


def stamp(ctx):
    """'Updated <date>' line, kept out of the sitemap hash."""
    bits = ["Last updated " + ctx["updated_label"]]
    yd = ctx.get("listing_label")
    if yd:
        bits.append("lengths and subscribers from " + yd)
    return '<!--volatile--><span class="stamp">%s</span><!--/volatile-->' % e(" · ".join(bits))


def thumb(vid, ctx, cls="th"):
    if vid in ctx["thumbs"]:
        return ('<img class="%s" src="%s/thumbs/%s.webp" width="160" height="90" loading="lazy" alt="">'
                % (cls, B, e(vid)))
    return '<span class="%s th-empty"></span>' % cls


def ep_link(v):
    return ('<a class="ep-t" href="%s" target="_blank" rel="noopener">%s</a>'
            % (e(yt_url(v["id"])), e(v.get("title"))))


def breakout_tag(b):
    if b is None:
        return ""
    cls = "bo hot" if metrics.is_breakout(b) else "bo"
    return '<span class="%s">%.1fx</span>' % (cls, b)


def ep_row(v, ctx, show=None, rank=None, extra_attrs=""):
    """One episode as a responsive row: thumbnail, title, show, date, numbers."""
    show_bit = ('<a class="ep-show" href="%s">%s</a> · ' % (show_url(show["slug"]), e(show["name"]))) if show else ""
    rk = '<span class="ep-rank">%d</span>' % rank if rank else ""
    return ('<div class="ep"%s>%s%s<div class="ep-body">%s'
            '<div class="ep-meta">%s%s · %s</div></div>'
            '<div class="ep-num"><span class="v">%s</span><span class="lbl">views</span>%s</div></div>\n'
            % (extra_attrs, rk, thumb(v["id"], ctx), ep_link(v), show_bit, fmt_date(v["published"]),
               fmt_len(v.get("duration")), full(v["views"]), breakout_tag(v.get("breakout"))))


def change_html(ch):
    """Rank arrow. Nothing at all without a comparable earlier ranking."""
    if ch is None:
        return ""
    if ch == "NEW":
        return '<span class="chg new">NEW</span>'
    if ch > 0:
        return '<span class="chg up">▲%d</span>' % ch
    if ch < 0:
        return '<span class="chg down">▼%d</span>' % -ch
    return '<span class="chg flat" title="Same place as a week earlier">=</span>'


def change_sort(ch):
    if ch is None:
        return 0
    if ch == "NEW":
        return 1000
    return ch


def subs_change_html(s, shared):
    if shared:
        return '<span class="dash">shared</span>'
    if s["subs_change"] is None:
        return '<span class="dash">–</span>'
    cls = "pos" if s["subs_change"] > 0 else "neg" if s["subs_change"] < 0 else "flat"
    return ('<span class="delta %s">%s</span> <span class="pc">%s</span>'
            % (cls, signed(s["subs_change"]), pct(s["subs_change_pct"])))


def _hosts(show):
    """Hosts as (name, url or None). Roster records are {"name", "url"};
    a bare string is a host with no player page. The url is the host's page
    under /players/ when there is one, else their Career Map page."""
    from .people import host_link
    return [(h, None) if isinstance(h, str) else (h["name"], host_link(h.get("url"))) for h in show.get("hosts") or []]


def hosts_line(show):
    """Plain text, for meta descriptions."""
    return ", ".join(n for n, _ in _hosts(show))


def hosts_html(show):
    """Each host linked to their player page here, or on NBA Career Map."""
    return ", ".join('<a class="host" href="%s">%s</a>' % (e(u), e(n)) if u else e(n) for n, u in _hosts(show))


# ── pages ──

# Rankings table metrics: key, column header, sort-menu label, default
# direction. Format-dependent ones change with the format filter.
LB_METRICS = [
    ("v7", "Views, 7 days", "Views on videos from the last 7 days", "desc"),
    ("v30", "Views, 30 days", "Views on videos from the last 30 days", "desc"),
    ("g7", "Gained, 7 days", "Views gained in 7 days", "desc"),
    ("g30", "Gained, 30 days", "Views gained in 30 days", "desc"),
    ("typf", "Typical full episode", "Typical full-episode views", "desc"),
    ("typc", "Typical clip", "Typical clip views", "desc"),
    ("total", "Total views", "Total views", "desc"),
    ("subs", "Channel subscribers", "Channel subscribers", "desc"),
    ("subg", "Subscriber growth", "Subscriber growth", "desc"),
    ("vids", "Videos, 30 days", "Videos published", "desc"),
    ("likes", "Likes per 1K", "Likes per 1,000 views", "desc"),
]
LB_FORMATS = [("full", "Full episodes"), ("clip", "Clips"), ("short", "Shorts"), ("all", "All formats")]


def lb_definitions(ctx):
    """One line per metric: what it is and the period it covers."""
    f = ctx["flags"]
    span = lambda since: ("%s to %s" % (fmt_date(since + "T00:00:00Z"), fmt_date(f["gain_day"] + "T00:00:00Z"))
                          if since and f.get("gain_day") else "")
    subs_day = ctx.get("listing_label")
    d = {
        "rank": "Rank: by views in the last 30 days on full episodes (20 minutes or longer), among ranked shows.",
        "chg": ("Change: places moved since the ranking of %s." % fmt_date(ctx["changes_day"] + "T00:00:00Z"))
        if ctx.get("changes_day") else "",
        "v7": "Views, 7 days: current views on videos posted in the last 7 days.",
        "v30": "Views, 30 days: current views on videos posted in the last 30 days (full episodes: the number the rank is based on).",
        "g7": "Gained, 7 days: views gained by videos posted in the last 90 days, %s." % span(f.get("g7_since")),
        "g30": "Gained, 30 days: views gained by videos posted in the last 90 days, %s." % span(f.get("g30_since")),
        "typf": "Typical full episode: median views of full episodes (20 minutes or longer) posted in the last 90 days.",
        "typc": "Typical clip: median views of clips (1 to 20 minutes) posted in the last 90 days.",
        "total": "Total views: current views on every video of the show on YouTube, all time.",
        "subs": ("Channel subscribers: YouTube's public, rounded count for the show's channel%s; "
                 "\"shared channel\" when the channel carries other shows too." % ((", read " + subs_day) if subs_day else "")),
        "subg": "Subscriber growth: change in channel subscribers since the reading a week or more earlier.",
        "vids": "Videos, 30 days: videos posted in the last 30 days.",
        "likes": "Likes per 1K: likes per 1,000 views on videos from the last 90 days that YouTube's feed gave likes for.",
    }
    return d


def _lb_cell(key, val, n, shared=False, pct_=None):
    """(sort value, html) for one number with the count it is based on."""
    if key == "subs" and shared:
        return -1, '<span class="nd">shared channel</span>'
    if val is None:
        return "", '<span class="nd">no data</span>'
    if key == "likes":
        txt = "%.1f" % val
    elif key == "subg":
        txt = signed(val) + ((' <span class="pc">%s</span>' % pct(pct_)) if pct_ is not None else "")
        return val, txt
    elif key == "subs":
        return val, compact(val)
    elif key == "vids":
        return val, "%d" % val
    elif key in ("g7", "g30"):
        txt = "+" + compact(val) if val else "0"
    else:
        txt = compact(val)
    return val, '%s<span class="bn">%d video%s</span>' % (txt, n, "" if n == 1 else "s")


def leaderboard(ctx, ranked=None):
    """The rankings table (cards on phones), sortable by every metric that
    has data, with a format filter. Numbers for every format sit in each
    row's data-m; the page shows full episodes first."""
    ranked = ctx["ranked"] if ranked is None else ranked
    have = ctx["metrics_have"]
    cols = [m for m in LB_METRICS if m[0] in have]
    show_chg = bool(ctx["changes"])
    defs = lb_definitions(ctx)
    rows, cards = [], []
    for s in ranked:
        show = ctx["shows"][s["slug"]]
        shared = ctx["shared"][s["slug"]]
        m = ctx["rank_metrics"][s["slug"]]
        ch = ctx["changes"].get(s["slug"]) if show_chg else None
        tds, attrs = [], {"rank": s["rank"], "name": show["name"].lower()}
        for key, *_ in cols:
            src = m["x"] if key in ("typf", "typc", "subs", "subg") else m["full"]
            val, n = src[key]
            sv, html = _lb_cell(key, val, n, shared, n if key == "subg" else None)
            attrs[key] = sv
            tds.append('<td data-k="%s">%s</td>' % (key, html))
        if show_chg:
            attrs["chg"] = change_sort(ch)
        data = " ".join('data-%s="%s"' % (k, e(v)) for k, v in attrs.items())
        data += " data-m='%s'" % e(json.dumps(m, separators=(",", ":")))
        if shared:
            data += ' data-shared="1"'
        rows.append('<tr %s><td class="rank">%d</td>%s<td class="name"><a class="q" href="%s">%s</a>'
                    '<span class="ev">%s</span></td>%s</tr>'
                    % (data, s["rank"], ('<td>%s</td>' % change_html(ch)) if show_chg else "",
                       show_url(show["slug"]), e(show["name"]), hosts_html(show), "".join(tds)))
        v30, n30 = m["full"]["v30"]
        cards.append(
            '<div class="card" %s><div class="now"><span class="p">%s</span><span class="lbl">%s</span>'
            '<span class="bn">%s</span></div>'
            '<div class="q"><span class="crank">%d</span>%s <a href="%s">%s</a></div>'
            '<div class="ev">%s</div>'
            '<div class="card-foot"><span><span class="lbl">Typical episode</span>%s</span>'
            '<span><span class="lbl">%s</span>%s</span>'
            '<span><span class="lbl">Videos, 30 days</span><span class="cf-vids">%s</span></span></div></div>'
            % (data, compact(v30), "Views, 30 days", ("based on %d video%s" % (n30, "" if n30 == 1 else "s")) if v30 is not None else "",
               s["rank"], (" " + change_html(ch)) if show_chg else "", show_url(show["slug"]), e(show["name"]),
               hosts_html(show), compact(m["x"]["typf"][0]) if m["x"]["typf"][0] is not None else "no data",
               "Channel subscribers", "shared channel" if shared else compact(m["x"]["subs"][0]) if m["x"]["subs"][0] is not None else "no data",
               m["full"]["vids"][0]))
    th = ['<th class="sortable sorted-by" data-sort="rank" data-dir="asc" title="%s">#</th>' % e(defs["rank"])]
    if show_chg:
        th.append('<th class="sortable" data-sort="chg" data-dir="desc" title="%s">Change</th>' % e(defs["chg"]))
    th.append('<th class="sortable left" data-sort="name" data-dir="asc">Show</th>')
    th += ['<th class="sortable" data-sort="%s" data-dir="%s" title="%s">%s</th>' % (k, d, e(defs[k]), h)
           for k, h, _, d in cols]
    opts = ['<option value="rank:asc">Rank</option>'] + \
           ['<option value="%s:%s">%s</option>' % (k, d, lbl) for k, _, lbl, d in cols] + \
           (['<option value="chg:desc">Rank change</option>'] if show_chg else []) + ['<option value="name:asc">Show name</option>']
    deflines = [defs["rank"]] + ([defs["chg"]] if show_chg else []) + [defs[k] for k, *_ in cols]
    defs_json = {k: defs[k] for k in ["rank"] + [c[0] for c in cols] + (["chg"] if show_chg else [])}
    defs_json["name"] = defs["rank"]
    return ('<div class="lb-tools" data-defs=\'%s\'>'
            '<label><span>Sort by</span> <select id="lb-sort" class="sel">%s</select></label>'
            '<label><span>Videos</span> <select id="lb-fmt" class="sel">%s</select></label></div>'
            '<p class="lb-def hint-below" id="lb-def">%s</p>'
            '<div class="table-wrap lbw"><table class="lb" id="lb"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            '<div class="cards" id="lb-cards">%s</div>'
            '<p class="hint-below">Numbers for full episodes unless another format is picked; typical episode and clip, '
            'subscribers and subscriber growth do not change with it. The small line under a number is how many '
            'videos it is based on.</p>'
            '<details class="defs"><summary>What the numbers mean</summary><ul>%s</ul></details>'
            % (e(json.dumps(defs_json, separators=(",", ":"))), "".join(opts),
               "".join('<option value="%s">%s</option>' % kv for kv in LB_FORMATS), e(defs["rank"]),
               "".join(th), "\n".join(rows), "\n".join(cards),
               "".join("<li>%s</li>" % e(x) for x in deflines if x)))


STREAM_FMTS = [("", "All formats"), ("full", "Full episodes"), ("clip", "Clips"), ("short", "Shorts")]
STREAM_RANGES = [("90", "Last 90 days"), ("30", "Last 30 days"), ("7", "Last 7 days"), ("1", "Last 24 hours")]
TOP_RANGES = [("0", "All time")] + STREAM_RANGES


def explorer_html(ctx, prefix, ver, items, tabs, first_tab, ranges, note="", extra=""):
    """A filterable list of video cards (tabs, search, show, host, format and
    date filters, "Load more"): the first 12 cards in the page, the rest
    loaded from data/<prefix>-*.json by the page script."""
    from .cards import video_card
    shows = sorted({it["show"] for it in items}, key=lambda x: ctx["shows"][x]["name"].lower())
    hosts = sorted({n for x in shows for n in ctx["stream_hosts"].get(x, [])})
    opt = lambda pairs: "".join('<option value="%s">%s</option>' % (e(v), e(l)) for v, l in pairs)
    return ('<div class="stream" data-meta="%s/data/%s-meta.json?v=%s" data-base="%s" data-prefix="%s" '
            'data-first-tab="%s" data-range="%s">'
            '<div class="toggle stream-tabs" role="tablist">%s</div>'
            '<div class="stream-filters">'
            '<label class="sr" for="sf-q">Search</label><input id="sf-q" class="sel sf-q" type="search" '
            'placeholder="Search title, show or host" autocomplete="off">'
            '<label class="sr" for="sf-show">Show</label><select id="sf-show" class="sel"><option value="">All shows</option>%s</select>'
            '<label class="sr" for="sf-host">Host</label><select id="sf-host" class="sel"><option value="">All hosts</option>%s</select>'
            '<label class="sr" for="sf-fmt">Format</label><select id="sf-fmt" class="sel">%s</select>'
            '<label class="sr" for="sf-range">Date range</label><select id="sf-range" class="sel">%s</select>'
            '</div>%s<p class="stream-count hint-below" aria-live="polite"></p>'
            '<div class="grid stream-grid">%s</div>'
            '<button class="loadmore" type="button">Load more</button></div>\n'
            % (B, prefix, ver, B, prefix, first_tab, ranges[0][0],
               "".join('<button type="button" data-tab="%s"%s>%s</button>' % (k, ' class="active"' if k == first_tab else "", l)
                       for k, l in tabs),
               opt([(x, ctx["shows"][x]["name"]) for x in shows]), opt([(h, h) for h in hosts]),
               opt(STREAM_FMTS), opt(ranges), ('<p class="hint-below">%s</p>' % note) if note else "",
               "".join(video_card(it, ctx, extra=extra) for it in items[:12])))


def stream_html(ctx):
    """Latest Videos: the first cards in the page, the rest loaded in chunks."""
    st = ctx["stream"]
    if len(st) < 3:
        return ""
    tabs = [("latest", "Latest"), ("views", "Most viewed")] + ([("trending", "Trending")] if ctx["flags"].get("g24") else [])
    return ('<section class="block" id="latest-videos"><div class="block-head"><h2>Latest videos</h2></div>%s</section>\n'
            % explorer_html(ctx, "stream", ctx["stream_v"], st, tabs, "latest", STREAM_RANGES))


def index_page(ctx):
    from .cards import featured, shelf
    url = config.SITE_BASE + "/"
    top = ctx["ranked"][:3]
    top_names = ", ".join(ctx["shows"][s["slug"]]["name"] for s in top)
    desc = ("Watch the latest NBA player podcast episodes and clips, the most watched videos this week and the "
            "rankings by YouTube views. Top right now: %s." % top_names) if top else \
        "Watch the latest NBA player podcast episodes and clips, and the rankings by YouTube views."
    h = ctx["home"]
    body = ['<div class="hdr"><h1>NBA Player Podcasts: Rankings, Episodes and Clips</h1></div>\n'
            '<p class="subtitle">Episodes, clips and Shorts from %d podcasts hosted by NBA players, playable right '
            'here, with the rankings by YouTube views on full episodes (20 minutes or longer) from the last 30 days. '
            '%s</p>\n' % (len(ctx["ranked"]), stamp(ctx)),
            '<nav class="jump"><a href="#latest-videos">Latest videos</a><a href="#rankings">Rankings</a>'
            '<a href="%s/most-watched/">Most watched</a></nav>\n' % B]
    if h["watch"]:
        body.append('<section class="block"><div class="block-head"><h2>Watch now</h2></div>%s</section>\n'
                    % featured(h["watch"], ctx, "The most viewed podcast video posted in the last 48 hours."))
    body.append(shelf("Most watched this week", h["week"], ctx, "Videos posted in the last 7 days, by views."))
    body.append(talked_home(ctx))
    if h["trending"]:
        lbl = "24 hours" if h["trend_label"] == "gain24" else "7 days"
        body.append(shelf("Trending", h["trending"], ctx, "Views gained in the last %s, from our daily view counts." % lbl,
                          extra=h["trend_label"]))
    body.append(shelf("Latest episodes", h["latest_eps"], ctx, "Full episodes (20 minutes or longer), newest first."))
    body.append(shelf("Biggest breakouts", h["breakouts"], ctx,
                      "Breakout = a video's views divided by the median views of the same show's videos of the same "
                      "format from the 90 days before it (at least 8 of them). Last 30 days.", show_breakout=True))
    body.append(stream_html(ctx))
    body.append('<section class="block" id="rankings"><div class="block-head"><h2>Rankings</h2></div>')
    body.append(leaderboard(ctx))
    body.append('<p class="hint-below">Players\' personal channels (vlogs, behind the scenes, highlights) are '
                'ranked separately: <a href="%s/player-channels/">%d player channels</a>.</p>'
                % (B, len(ctx["ranked_pc"])))
    body.append("</section>\n")
    body.append(method_html(ctx))
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "NBA Player Podcasts by YouTube views",
          "itemListElement": [{"@type": "ListItem", "position": s["rank"], "name": ctx["shows"][s["slug"]]["name"],
                               "url": config.SITE_BASE + "/" + s["slug"] + "/"} for s in ctx["ranked"][:25]]}
    extra = '<script type="application/ld+json">%s</script>\n' % json.dumps(ld).replace("</", "<\\/")
    return page("NBA Player Podcasts: Rankings, Episodes and Clips | HoopsMatic", desc, url, ctx["assets_v"],
                "rankings", "".join(body), extra)


def method_html(ctx):
    rc = ("Rank change compares with the ranking from a week earlier made with the same rules."
          if ctx["changes"] else "Rank changes appear once there is a ranking from a week earlier made with the same rules.")
    return ('<section class="section method"><h2>How the rankings work</h2>'
            '<p>Only YouTube numbers count. The rank uses full episodes (20 minutes or longer): the current views of '
            'every full episode posted in the last 30 days. Clips (1 to 20 minutes) and Shorts (under a minute) do '
            'not count toward the rank; pick them in the Videos menu to see their numbers. Each number says how '
            'many videos it is based on, and one that cannot be worked out yet says "no data". %s</p>'
            '<p>A show is ranked with at least 4 full episodes in the last 90 days, or 1 to 3 in the last 90 days '
            'and at least 4 in the last 180. Shows with 1 to 3 in the last 90 days (and fewer than 4 in 180) are '
            '<a href="%s/dormant/">occasional</a>, and shows with none in the last 90 days are dormant; neither is '
            'ranked until it posts more. Podcasts and players\' personal channels are ranked separately, with the '
            'same numbers and rules.</p>'
            '<p>A breakout score is a video\'s views divided by the median views of the same show\'s videos of the '
            'same format published in the 90 days before it, when there are at least 8 of them (otherwise there is '
            'no score: not enough data); 5x or more is highlighted. <a href="%s/methodology/">Full methodology</a>.'
            '</p></section>\n' % (rc, B, B))


def most_watched_page(ctx):
    url = config.SITE_BASE + "/most-watched/"
    opts = "".join('<option value="%s">%s</option>' % (e(slug), e(ctx["shows"][slug]["name"]))
                   for slug in sorted(ctx["mw_shows"], key=lambda s: ctx["shows"][s]["name"].lower()))
    body = ['<div class="hdr"><h1>Most watched NBA player podcast episodes</h1></div>\n'
            '<p class="subtitle">Full episodes (20 minutes or longer) with the most YouTube views, '
            'from this week back to all time. %s</p>\n' % stamp(ctx),
            '<div class="filters"><label for="mw-show" class="sr">Show</label>'
            '<select id="mw-show" class="sel"><option value="">All shows</option>%s</select></div>\n' % opts]
    for key, label, note in (("week", "This week", "posted in the last 7 days"),
                             ("month", "This month", "posted in the last 30 days"),
                             ("season", "This season", "posted since October 1, 2026"),
                             ("all", "All time", "")):
        rows = ctx["most_watched"][key]
        body.append('<section class="block mw" data-mw="%s"><div class="block-head"><h2>%s</h2></div>'
                    % (key, label))
        if not rows:
            body.append('<div class="empty">No full episodes in this window yet.</div></section>\n')
            continue
        body.append('<div class="eps">')
        for i, v in enumerate(rows, 1):
            hide = i > 25
            body.append(ep_row(v, ctx, ctx["shows"][v["slug"]], rank=i,
                               extra_attrs=' data-show="%s"%s' % (e(v["slug"]), ' hidden' if hide else "")))
        body.append('</div><div class="empty mw-none" hidden>No episodes from this show in this window.</div>%s</section>\n'
                    % (('<p class="hint-below">Full episodes %s.</p>' % note) if note else ""))
    top = ctx["most_watched"]["all"][:1]
    desc = "The most watched NBA player podcast episodes on YouTube this week, this month, this season and all time."
    if top:
        desc += " All-time No. 1: %s (%s views)." % (top[0].get("title", "")[:80], compact(top[0]["views"]))
    return page("Most Watched NBA Player Podcast Episodes | HoopsMatic", desc, url, ctx["assets_v"],
                "most-watched", "".join(body))


def _dormant_table(rows, ctx):
    out = ['<div class="dirtable"><table class="lb static"><thead><tr><th class="left">Show</th>'
           '<th>Last full episode</th><th class="hide-s">Full episodes, 90 days</th><th>Channel</th></tr></thead><tbody>']
    for s in rows:
        show = ctx["shows"][s["slug"]]
        out.append('<tr><td class="name"><a class="q" href="%s">%s</a><span class="ev">%s</span></td>'
                   '<td>%s</td><td class="hide-s">%d</td>'
                   '<td><a href="%s" target="_blank" rel="noopener">YouTube</a></td></tr>'
                   % (show_url(show["slug"]), e(show["name"]), hosts_html(show),
                      fmt_date(s["last_episode"]), s["episodes_90"], e(show["youtube_url"])))
    out.append("</tbody></table></div>")
    return "".join(out)


def dormant_page(ctx):
    url = config.SITE_BASE + "/dormant/"
    body = ['<div class="hdr"><h1>Occasional &amp; dormant shows</h1></div>\n'
            '<p class="subtitle">Shows without enough recent full episodes (20 minutes or longer) to be ranked. '
            'Occasional: 1 to 3 in the last 90 days and fewer than 4 in the last 180. Dormant: none in the last '
            '90 days. They return to the rankings when they post more. %s</p>\n' % stamp(ctx)]
    groups = [("Occasional podcasts", "occasional", "podcast"), ("Occasional player channels", "occasional", "player_channel"),
              ("Dormant podcasts", "dormant", "podcast"), ("Dormant player channels", "dormant", "player_channel")]
    shown = 0
    for label, status, kind in groups:
        rows = [s for s in ctx[status] if s["type"] == kind]
        if rows:
            shown += 1
            body.append('<section class="block"><div class="block-head"><h2>%s</h2></div>%s</section>\n'
                        % (label, _dormant_table(rows, ctx)))
    if not shown:
        body.append('<div class="empty">No occasional or dormant shows right now.</div>')
    names = ", ".join(ctx["shows"][s["slug"]]["name"] for s in (ctx["occasional"] + ctx["dormant"])[:4]
                      if s["type"] == "podcast")
    desc = ("NBA player podcasts that post only now and then, or not at all lately, with each show's last full "
            "YouTube episode" + (": " + names + "." if names else "."))
    return page("Occasional & Dormant NBA Player Podcasts | HoopsMatic", desc, url, ctx["assets_v"], "dormant",
                "".join(body))


def player_channels_page(ctx):
    url = config.SITE_BASE + "/player-channels/"
    top = ", ".join(ctx["shows"][s["slug"]]["name"] for s in ctx["ranked_pc"][:3])
    desc = ("NBA players' personal YouTube channels (vlogs, behind the scenes, highlights) ranked by views on "
            "videos of 20 minutes or longer from the last 30 days" + (". Top right now: %s." % top if top else "."))
    body = ['<div class="hdr"><h1>NBA player YouTube channels</h1></div>\n'
            '<p class="subtitle">%d players\' personal channels (vlogs, behind the scenes, highlights rather than '
            'a recurring show), ranked like the <a href="%s/">podcasts</a>: by YouTube views on videos of 20 '
            'minutes or longer posted in the last 30 days. %s</p>\n' % (len(ctx["ranked_pc"]), B, stamp(ctx))]
    if ctx["ranked_pc"]:
        body.append('<section class="block"><div class="block-head"><h2>Rankings</h2></div>')
        body.append(leaderboard(ctx, ctx["ranked_pc"]))
        body.append("</section>\n")
    else:
        body.append('<div class="empty">No player channels ranked right now.</div>')
    body.append(method_html(ctx))
    return page("NBA Player YouTube Channels Ranked by Views | HoopsMatic", desc, url, ctx["assets_v"],
                "player-channels", "".join(body))


BREAKOUT_NOTE = ("Breakout = a video's views divided by the median views of the same show's videos of the same "
                 "format published in the 90 days before it, when there are at least 8 of them; with fewer there "
                 "is no score (not enough data).")


def top_videos_page(ctx):
    from .cards import shelf
    url = config.SITE_BASE + "/top-videos/"
    t = ctx["top"]
    f = ctx["flags"]
    tabs = [("views", "Most viewed")] + ([("trending", "Gained, 24 hours")] if f.get("g24") else []) + \
           ([("gain7", "Gained, 7 days")] if f.get("g7") else []) + [("breakout", "Breakouts")]
    body = ['<div class="hdr"><h1>Top NBA player podcast videos</h1></div>\n'
            '<p class="subtitle">The most viewed full episodes, clips and Shorts from NBA player podcasts on '
            'YouTube, the biggest gainers and the breakouts, playable right here. %s</p>\n' % stamp(ctx),
            '<section class="block" id="most-viewed"><div class="block-head"><h2>Most viewed overall</h2></div>%s</section>\n'
            % explorer_html(ctx, "top", ctx["top_v"], t["views"], tabs, "views", TOP_RANGES,
                            note="All time: each show's 12 most viewed videos of each format and the 100 most viewed "
                                 "overall; the last 90 days: every video. " + BREAKOUT_NOTE)]
    body.append(shelf("Most viewed full episodes", t["full"], ctx, "Full episodes (20 minutes or longer), all time."))
    body.append(shelf("Most viewed clips", t["clip"], ctx, "Clips (1 to 20 minutes), all time."))
    body.append(shelf("Most viewed Shorts", t["short"], ctx, "Shorts (under a minute, or from the Shorts tab), all time."))
    if t["gain24"]:
        body.append(shelf("Most gained in 24 hours", t["gain24"], ctx, "Views gained in the last 24 hours, from our "
                          "daily view counts.", extra="gain24"))
    if t["gain7"]:
        body.append(shelf("Most gained in 7 days", t["gain7"], ctx, "Views gained in the last 7 days, from our daily "
                          "view counts.", extra="gain7"))
    body.append(shelf("Breakouts", t["breakout"], ctx, "Highest breakout scores among videos from the last 90 days. "
                      + BREAKOUT_NOTE, show_breakout=True))
    top1 = t["views"][:1]
    desc = "The most viewed NBA player podcast videos on YouTube: full episodes, clips and Shorts, the biggest gainers and the breakouts."
    if top1:
        desc += " No. 1: %s (%s views)." % (top1[0]["title"][:80], compact(top1[0]["views"]))
    return page("Top NBA Player Podcast Videos: Most Viewed Episodes, Clips and Shorts | HoopsMatic", desc, url,
                ctx["assets_v"], "top-videos", "".join(body))


def chart_svg(eps, med):
    """Views per full episode, oldest to newest, last 40. Median as a dashed line."""
    eps = sorted(eps, key=lambda v: v["published"])[-40:]
    if len(eps) < 2:
        return '<div class="chart-empty">Not enough full episodes for a chart yet.</div>'
    W, H, pad_l, pad_b, pad_t = 720, 220, 46, 22, 10
    mx = max(v["views"] for v in eps) or 1
    n = len(eps)
    bw = (W - pad_l - 4) / n
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="Views per episode">' % (W, H)]
    for frac in (0, 0.5, 1):
        y = H - pad_b - frac * (H - pad_b - pad_t)
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (pad_l, W, y, y))
        out.append('<text class="ax" x="%d" y="%.1f">%s</text>' % (pad_l - 6, y + 3, compact(mx * frac)))
    for i, v in enumerate(eps):
        h = (H - pad_b - pad_t) * v["views"] / mx
        x = pad_l + 2 + i * bw
        cls = "bar hot" if metrics.is_breakout(v.get("breakout")) else "bar"
        out.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"><title>%s: %s views (%s)</title></rect>'
                   % (cls, x, H - pad_b - h, max(bw - 2, 1), h, e(v.get("title")), full(v["views"]), fmt_date(v["published"])))
    if med:
        y = H - pad_b - (H - pad_b - pad_t) * med / mx
        out.append('<line class="med" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (pad_l, W, y, y))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="start">%s</text>' % (pad_l + 2, H - 6, fmt_date(eps[0]["published"])))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="end">%s</text>' % (W - 2, H - 6, fmt_date(eps[-1]["published"])))
    out.append("</svg>")
    return "".join(out)


# ── structured data ──

def iso_duration(sec):
    if not sec:
        return None
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, x = divmod(rem, 60)
    return "PT" + ("%dH" % h if h else "") + ("%dM" % m if m else "") + "%dS" % x


def video_ld(it, ctx):
    """schema.org VideoObject for one video card on the page."""
    d = {"@type": "VideoObject", "name": it["title"], "uploadDate": it["published"],
         "url": yt_url(it["id"]), "embedUrl": "https://www.youtube-nocookie.com/embed/" + it["id"],
         "description": "%s, %s on YouTube." % (it["title"], ctx["shows"][it["show"]]["name"]),
         "thumbnailUrl": config.SITE_BASE + "/thumbs/" + it["id"] + ".webp" if it["id"] in ctx["thumbs"]
         else "https://i.ytimg.com/vi/%s/hqdefault.jpg" % it["id"],
         "interactionStatistic": {"@type": "InteractionCounter", "interactionType": {"@type": "WatchAction"},
                                  "userInteractionCount": it["views"]}}
    if it.get("duration"):
        d["duration"] = iso_duration(it["duration"])
    return d


def breadcrumbs_ld(trail):
    """trail: [(name, absolute url)], home first."""
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": n, "item": u} for i, (n, u) in enumerate(trail, 1)]}


def ld_script(*nodes):
    doc = {"@context": "https://schema.org", "@graph": list(nodes)}
    return '<script type="application/ld+json">%s</script>\n' % json.dumps(doc).replace("</", "<\\/")


def crumbs_html(trail):
    return ('<nav class="crumbs" aria-label="Breadcrumb">%s</nav>\n'
            % " / ".join('<a href="%s">%s</a>' % (e(u.replace(config.SITE_ORIGIN, "")), e(n)) for n, u in trail[:-1]))


TRAIL_HOME = [("HoopsMatic", config.SITE_ORIGIN + "/"), ("NBA Player Podcasts", config.SITE_BASE + "/")]


# ── show pages ──

def _clean_desc(text, limit=320):
    """A channel's About text, without links and email addresses, cut at a
    word near `limit`."""
    import re
    t = re.sub(r"\S+@\S+|https?://\S+|www\.\S+", "", text or "")
    t = re.sub(r"\s+", " ", t).strip(" -|•")
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return t


def art_html(show, ctx, size=88):
    cid = show["channel_id"]
    if cid in ctx.get("art", ()):
        return '<img class="art" src="%s/art/%s.webp" width="%d" height="%d" alt="">' % (B, e(cid), size, size)
    from .headshots import initials
    return '<span class="art art-i" aria-hidden="true">%s</span>' % e(initials(show["name"]))


def people_html(entries, ctx, size=28):
    """[(name, link, headshot slug)] -> linked names with headshots."""
    from .cards import avatar
    return "".join(('<a class="host" href="%s">%s%s</a>' % (e(u), avatar(n, h, size), e(n))) if u
                   else '<span class="host">%s%s</span>' % (avatar(n, h, size), e(n)) for n, u, h in entries)


def _former_hosts(show, ctx):
    from .people import host_link, slug_from_url
    out = []
    for h in show.get("former_hosts") or []:
        slug = slug_from_url(h.get("url"))
        out.append((h["name"], host_link(h.get("url")), slug if slug in ctx.get("headshots", ()) else None, h.get("note")))
    return out


def _metric_cards(ctx, s):
    """The show's key numbers, each with what it is, its period and the
    videos it is based on."""
    m = ctx["show_metrics"][s["slug"]]
    shared = ctx["shared"][s["slug"]]
    f = ctx["flags"]
    based = lambda n: "based on %d video%s" % (n, "" if n == 1 else "s")
    rows = [
        ("Views, 30 days", m["full"]["v30"], "current views on full episodes posted in the last 30 days"),
        ("Views, 7 days", m["all"]["v7"], "current views on every video posted in the last 7 days"),
        ("Typical full episode", m["x"]["typf"], "median views, full episodes from the last 90 days"),
        ("Typical clip", m["x"]["typc"], "median views, clips from the last 90 days"),
        ("Total views", m["all"]["total"], "every video on YouTube, all time"),
        ("Videos, 30 days", m["all"]["vids"], "videos of every format posted in the last 30 days"),
        ("Likes per 1K views", m["all"]["likes"], "videos from the last 90 days with likes from YouTube's feed"),
    ]
    if f.get("g7"):
        rows.insert(2, ("Gained, 7 days", m["all"]["g7"], "views gained by videos from the last 90 days, %s to %s"
                        % (fmt_date(f["g7_since"] + "T00:00:00Z"), fmt_date(f["gain_day"] + "T00:00:00Z"))))
    out = []
    for lbl, (val, n), sub in rows:
        if lbl == "Videos, 30 days":
            num = "%d" % val
            sub_txt = sub
        elif lbl == "Likes per 1K views":
            num = ("%.1f" % val) if val is not None else '<span class="nd">no data</span>'
            sub_txt = sub + (" (" + based(n) + ")" if val is not None else "")
        else:
            num = compact(val) if val is not None else '<span class="nd">no data</span>'
            sub_txt = sub + (" (" + based(n) + ")" if val is not None else "")
        out.append('<div class="stat-card"><div class="lbl">%s</div><div class="num">%s</div><div class="sub">%s</div></div>'
                   % (lbl, num, e(sub_txt)))
    if shared:
        out.append('<div class="stat-card"><div class="lbl">Channel subscribers</div><div class="num">shared</div>'
                   '<div class="sub">shared channel: the count belongs to every show on it</div></div>')
    else:
        subs = m["x"]["subs"][0]
        g, gp = m["x"]["subg"]
        sub = "YouTube's public, rounded count" + ((", read " + ctx["listing_label"]) if ctx.get("listing_label") else "")
        if g is not None:
            sub += "; %s (%s) since a week earlier" % (signed(g), pct(gp)) if gp is not None else "; %s since a week earlier" % signed(g)
        out.append('<div class="stat-card"><div class="lbl">Channel subscribers</div><div class="num">%s</div><div class="sub">%s</div></div>'
                   % (compact(subs) if subs is not None else '<span class="nd">no data</span>', e(sub)))
    return '<div class="stat-cards">%s</div>\n' % "".join(out)


def weekly_history(ids):
    """[(date, total views)] of these videos from each weekly snapshot,
    counting only videos every reading has (so the line compares like with
    like). Empty until there are 3 readings."""
    from . import history
    days = history.days_on_file("weekly")
    if len(days) < 3:
        return []
    reads = []
    for d in days:
        doc = history.load_weekly(d) or {}
        flat = {}
        for vv in (doc.get("v") or {}).values():
            flat.update(vv)
        reads.append((d, flat))
    common = set(ids)
    for _, flat in reads:
        common &= set(flat)
    if not common:
        return []
    return [(d, sum(flat[i] for i in common)) for d, flat in reads]


def history_svg(points):
    W, H, pl, pb, pt = 720, 200, 54, 22, 10
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    xs = [pl + (W - pl - 8) * i / (len(points) - 1) for i in range(len(points))]
    ys = [H - pb - (H - pb - pt) * (v - lo) / span for v in vals]
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="Total views by week">' % (W, H)]
    for frac in (0, 1):
        y = H - pb - frac * (H - pb - pt)
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (pl, W, y, y))
        out.append('<text class="ax" x="%d" y="%.1f">%s</text>' % (pl - 6, y + 3, compact(lo + frac * span)))
    out.append('<polyline class="line" fill="none" points="%s"/>' % " ".join("%.1f,%.1f" % p for p in zip(xs, ys)))
    for (d, v), x, y in zip(points, xs, ys):
        out.append('<circle class="pt" cx="%.1f" cy="%.1f" r="3"><title>%s: %s views</title></circle>' % (x, y, fmt_date(d + "T00:00:00Z"), full(v)))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="start">%s</text>' % (pl, H - 6, fmt_date(points[0][0] + "T00:00:00Z")))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="end">%s</text>' % (W - 2, H - 6, fmt_date(points[-1][0] + "T00:00:00Z")))
    out.append("</svg>")
    return "".join(out)


def guests_html(ctx, slug):
    """Confirmed guests of one show, linked, with how many appearances."""
    from .people import link_for
    by = {}
    for it in ctx["appearances"].values():
        if it["show"] == slug and it["video"] in ctx["item_by_id"]:
            by.setdefault(it["player"], []).append(it)
    if not by:
        return ""
    names = ctx["player_names"]
    rows = []
    for player, apps in by.items():
        vids = sorted((ctx["item_by_id"][a["video"]] for a in apps), key=lambda v: v["published"], reverse=True)
        n = len({a.get("group") or a["video"] for a in apps})
        rows.append((vids[0]["published"], player, n, vids[0]))
    rows.sort(reverse=True)
    from .cards import avatar
    items = []
    for _, player, n, v in rows[:60]:
        name = names.get(player, player)
        head = player if player in ctx.get("headshots", ()) else None
        items.append('<li><a class="host" href="%s">%s%s</a> <span class="g-n">%d appearance%s · latest %s: '
                     '<a href="%s" target="_blank" rel="noopener">%s</a></span></li>'
                     % (e(link_for(player)), avatar(name, head, 24), e(name), n, "" if n == 1 else "s",
                        fmt_date(v["published"]), e(yt_url(v["id"])), e(v["title"][:90])))
    more = (' <span class="g-n">and %d more</span>' % (len(rows) - 60)) if len(rows) > 60 else ""
    return ('<section class="block" id="guests"><div class="block-head"><h2>Guests</h2></div>'
            '<ul class="guests">%s</ul>%s<p class="hint-below">Players stated as guests in a video\'s title or '
            'description and matched to one NBA Career Map player; clips of the same episode count once.</p></section>\n'
            % ("".join(items), more))


def related_html(ctx, slug):
    rel = ctx["related"].get(slug) or []
    if not rel:
        return ""
    cards = []
    for o in rel:
        show = ctx["shows"][o]
        st = ctx["stats_by_slug"][o]
        status = ("No. %d" % st["rank"]) if st["status"] == "ranked" else st["status"].capitalize()
        cards.append('<a class="rel" href="%s">%s<span class="rel-b"><span class="rel-n">%s</span>'
                     '<span class="rel-h">%s</span><span class="rel-s">%s</span></span></a>'
                     % (show_url(o), art_html(show, ctx, 56), e(show["name"]), e(hosts_line(show)), e(status)))
    return ('<section class="block"><div class="block-head"><h2>Related shows</h2></div><div class="rels">%s</div></section>\n'
            % "".join(cards))


def show_page(ctx, s):
    from .cards import host_people, shelf, video_card
    from .metrics import FULL, CLIP
    show = ctx["shows"][s["slug"]]
    url = config.SITE_BASE + "/" + show["slug"] + "/"
    eps = s["episodes"]
    vids = sorted(ctx["per_show"].get(s["slug"], []), key=lambda it: it["published"], reverse=True)
    pc = s["type"] == "player_channel"
    if s["status"] == "ranked":
        ch = ctx["changes"].get(s["slug"]) if ctx["changes"] else None
        status = 'Ranked <strong>No. %d</strong> of %d %s by views on full episodes from the last 30 days%s' % (
            s["rank"], len(ctx["ranked_pc"] if pc else ctx["ranked"]),
            '<a href="%s/player-channels/">player channels</a>' % B if pc else '<a href="%s/#rankings">podcasts</a>' % B,
            (" " + change_html(ch)) if ch not in (None, 0) else "")
    else:
        label = "Occasional" if s["status"] == "occasional" else "Dormant"
        status = '<a href="%s/dormant/">%s</a>: last full episode %s' % (B, label, fmt_date(s["last_episode"]))
    hosts = hosts_line(show)
    former = _former_hosts(show, ctx)
    links = ['<a href="%s" target="_blank" rel="noopener">YouTube channel</a>'
             % e("https://www.youtube.com/channel/" + show["channel_id"])]
    if show.get("playlist_id"):
        links.append('<a href="%s" target="_blank" rel="noopener">Official playlist</a>'
                     % e("https://www.youtube.com/playlist?list=" + show["playlist_id"]))
    desc_txt = _clean_desc(ctx["descriptions"].get(s["slug"]))
    trail = TRAIL_HOME + [(show["name"], url)]
    body = [crumbs_html(trail),
            '<div class="phead show-head">%s<div class="sh-b"><h1>%s</h1>'
            '<div class="meta">%s</div>%s<div class="meta">%s</div><div class="meta">%s</div></div></div>\n'
            % (art_html(show, ctx), e(show["name"]),
               ('Hosted by ' + people_html(host_people(show, ctx), ctx)) if hosts else "",
               ('<div class="meta">Former host%s: %s</div>' % ("s" if len(former) > 1 else "", "".join(
                   people_html([f[:3]], ctx) + ((' <span class="g-n">(%s)</span>' % e(f[3])) if f[3] else "") for f in former)))
               if former else "", status, " · ".join(links))]
    if desc_txt:
        body.append('<p class="show-desc">%s</p>\n' % e(desc_txt))
    body.append('<p class="hint-below">%s</p>' % stamp(ctx))
    body.append(_metric_cards(ctx, s))
    if len(vids) >= 3:
        body.append('<section class="block" id="latest"><div class="block-head"><h2>Latest videos</h2></div>'
                    '<div class="grid">%s</div></section>\n' % "".join(video_card(it, ctx) for it in vids[:12]))
    trend_key = "gain24" if ctx["flags"].get("g24") else "gain7" if ctx["flags"].get("g7") else None
    if trend_key:
        tr = sorted((it for it in vids if it.get(trend_key)), key=lambda it: -it[trend_key])[:8]
        if len(tr) >= 3:
            body.append(shelf("Trending", tr, ctx, "Views gained in the last %s, from our daily view counts."
                              % ("24 hours" if trend_key == "gain24" else "7 days"), extra=trend_key))
    top_eps = sorted((it for it in vids if it["fmt"] == FULL), key=lambda it: -it["views"])[:8]
    top_clips = sorted((it for it in vids if it["fmt"] == CLIP), key=lambda it: -it["views"])[:8]
    if len(top_eps) >= 3:
        body.append(shelf("Most viewed episodes", top_eps, ctx, "Full episodes (20 minutes or longer), all time.", show_breakout=True))
    if len(top_clips) >= 3:
        body.append(shelf("Most viewed clips", top_clips, ctx, "Clips (1 to 20 minutes), all time.", show_breakout=True))
    hist = weekly_history([it["id"] for it in vids if it["fmt"] == FULL])
    if hist:
        body.append('<section class="section"><h2>Views over time</h2><p class="hint">Total views of the full '
                    'episodes in every weekly reading, week by week.</p>%s</section>\n' % history_svg(hist))
    body.append('<section class="section"><h2>Views per episode</h2><p class="hint">Last %d full episodes, oldest '
                'to newest. Dashed line: typical episode. Highlighted: breakouts (5x or more).</p>%s</section>\n'
                % (min(len(eps), 40), chart_svg(eps, s["typical"])))
    body.append(guests_html(ctx, s["slug"]))
    body.append(related_html(ctx, s["slug"]))
    if show.get("note"):
        body.append('<p class="note">%s</p>\n' % e(show["note"]))
    m = ctx["show_metrics"][s["slug"]]
    desc = ("%s%s: latest episodes and clips, playable here, with YouTube rankings: %s views on full episodes "
            "in the last 30 days, %s on a typical episode." % (show["name"], (" (" + hosts + ")") if hosts else "",
                                                              full(m["full"]["v30"][0] or 0), full(s["typical"])))
    title = "%s: Episodes, Clips and YouTube Rankings | HoopsMatic" % show["name"]
    extra = ld_script(breadcrumbs_ld(trail), *[video_ld(it, ctx) for it in vids[:12]])
    return page(title, desc, url, ctx["assets_v"], None, "".join(body), extra)


# ── player pages ──

def _player_main_show(p, ctx):
    hosted = p["hosts"] or p["former"]
    if hosted:
        return max(hosted, key=lambda x: ctx["show_metrics"][x]["all"]["total"][0] or 0)
    counts = {}
    for a in p["guest"]:
        counts[a["show"]] = counts.get(a["show"], 0) + 1
    return max(counts, key=lambda x: (counts[x], x)) if counts else None


def player_videos(p, ctx):
    """[(item, role)]: every confirmed guest appearance, and for each show
    they host the latest 12 and the 6 most viewed videos."""
    out, seen = [], set()
    for a in sorted(p["guest"], key=lambda a: ctx["item_by_id"].get(a["video"], {}).get("published", ""), reverse=True):
        it = ctx["item_by_id"].get(a["video"])
        if it and it["id"] not in seen:
            seen.add(it["id"])
            out.append((it, "guest"))
    for role, shows in (("host", p["hosts"]), ("former host", p["former"])):
        for sl in shows:
            vids = ctx["per_show"].get(sl, [])
            pick = sorted(vids, key=lambda it: it["published"], reverse=True)[:12] + \
                sorted(vids, key=lambda it: -it["views"])[:6]
            for it in pick:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    out.append((it, role))
    return out


# ── talked about ──

def team_url(slug):
    return B + "/teams/" + slug + "/"


def player_link_html(slug, ctx, size=24):
    """A player's name (with headshot) linked to their page here, else
    NBA Career Map."""
    from .cards import avatar
    from .people import link_for
    name = ctx["player_names"].get(slug, slug)
    head = slug if slug in ctx.get("headshots", ()) else None
    return '<a class="host" href="%s">%s%s</a>' % (e(link_for(slug)), avatar(name, head, size), e(name))


def weeks_svg(rows, label):
    W, H, pl, pb, pt = 720, 150, 30, 22, 10
    mx = max(c for _, c in rows) or 1
    bw = (W - pl - 4) / len(rows)
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (W, H, e(label))]
    out.append('<line class="grid" x1="%d" x2="%d" y1="%d" y2="%d"/>' % (pl, W, H - pb, H - pb))
    out.append('<text class="ax" x="%d" y="%d">%d</text>' % (pl - 6, pt + 4, mx))
    for i, (wk, c) in enumerate(rows):
        h = (H - pb - pt) * c / mx
        x = pl + 2 + i * bw
        out.append('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f"><title>Week of %s: %d</title></rect>'
                   % (x, H - pb - h, max(bw - 3, 1), h, fmt_date(wk + "T00:00:00Z"), c))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="start">%s</text>' % (pl + 2, H - 6, fmt_date(rows[0][0] + "T00:00:00Z")))
    out.append('<text class="ax" x="%d" y="%d" text-anchor="end">week of %s</text>' % (W - 2, H - 6, fmt_date(rows[-1][0] + "T00:00:00Z")))
    out.append("</svg>")
    return "".join(out)


def talk_section(ctx, target, name, pronoun="them"):
    """'Talked about' for one player or team: counts, most recent, most
    viewed, the shows that talk about them most, and mentions per week."""
    from . import talk
    from .cards import talk_card
    groups = ctx["talk"].get(target) or []
    if len(groups) < 3:
        return ""
    now = ctx["now"]
    c7, v7 = talk.window(groups, now, 7)
    c30, v30 = talk.window(groups, now, 30)
    vids = sum(len(g.items) for g in groups)
    recent = groups[:8]
    viewed = sorted(groups, key=lambda g: -g.views)[:8]
    shows = talk.top_shows(groups)
    out = ['<section class="block talk" id="talked-about"><div class="block-head"><h2>Talked about</h2></div>'
           '<p class="talk-sum">%d discussions (%d videos) talk about %s: %d in the last 7 days, %d in the last 30.</p>'
           '<p class="hint-below">Videos whose title or chapters name %s, apart from %s own appearances. Clips of the '
           'same episode count once and are listed under the episode.</p>'
           % (len(groups), vids, e(name), c7, c30, e(name), "their" if target[0] == "team" else "his")]
    out.append('<h3 class="sub-h">Most recent</h3><div class="grid">%s</div>' % "".join(talk_card(g, ctx) for g in recent))
    out.append('<h3 class="sub-h">Most viewed</h3><div class="grid">%s</div>' % "".join(talk_card(g, ctx) for g in viewed))
    out.append('<h3 class="sub-h">Shows that talk about %s most</h3><ol class="talk-shows">%s</ol>'
               % (pronoun, "".join('<li><a href="%s">%s</a> <span class="g-n">%d discussion%s</span></li>'
                                   % (show_url(sl), e(ctx["shows"][sl]["name"]), n, "" if n == 1 else "s") for sl, n in shows)))
    weeks = talk.per_week(groups, now)
    if weeks:
        out.append('<h3 class="sub-h">Discussions per week</h3><p class="hint-below">By the week the videos were posted, '
                   'last 12 weeks.</p>%s' % weeks_svg(weeks, "Discussions per week"))
    out.append("</section>\n")
    return "".join(out)


def talked_home(ctx):
    """Homepage: most talked about players and teams, this week and in the
    last 30 days (a toggle between two lists already in the page)."""
    from . import talk
    now = ctx["now"]

    def lst(kind, days):
        rows = talk.leaders(ctx["talk"], kind, now, days)
        if len(rows) < 3:
            return ""
        items = []
        for i, (slug, c, v) in enumerate(rows, 1):
            if kind == "player":
                who = player_link_html(slug, ctx, 26)
            else:
                t = ctx["team_by_slug"][slug]
                who = '<a class="host" href="%s">%s</a>' % (team_url(slug), e(t["name"]))
            items.append('<li><span class="tl-r">%d</span>%s<span class="tl-n">%d discussion%s'
                         '<span class="bn">based on %d video%s</span></span></li>'
                         % (i, who, c, "" if c == 1 else "s", v, "" if v == 1 else "s"))
        return '<ol class="talk-list">%s</ol>' % "".join(items)

    cols = []
    for days in (7, 30):
        p, t = lst("player", days), lst("team", days)
        if not (p or t):
            continue
        cols.append('<div class="talk-pane" data-days="%d"%s><div class="talk-cols">'
                    '<div><h3 class="sub-h">Players</h3>%s</div><div><h3 class="sub-h">Teams</h3>%s</div></div></div>'
                    % (days, "" if days == 7 else " hidden", p, t))
    if not cols:
        return ""
    return ('<section class="block" id="talked-about"><div class="block-head"><h2>Most talked about this week</h2></div>'
            '<div class="toggle talk-toggle" role="tablist"><button type="button" data-days="7" class="active">7 days</button>'
            '<button type="button" data-days="30">30 days</button></div>%s'
            '<p class="hint-below">Distinct episodes (clips of one episode count once) whose title or chapters name the '
            'player or team, posted in the last 7 or 30 days, apart from a player\'s own appearances. '
            '<a href="%s/teams/">All teams</a> · <a href="%s/methodology/#talked-about">How it works</a></p></section>\n'
            % ("".join(cols), B, B))


# ── player pages ──

def player_page(ctx, p):
    from .cards import avatar, video_card
    from .people import CAREER_MAP
    url = config.SITE_ORIGIN + config.BASE_PATH + "/players/" + p["slug"] + "/"
    main = _player_main_show(p, ctx)
    main_name = ctx["shows"][main]["name"] if main else "NBA podcasts"
    vids = player_videos(p, ctx)
    roles = []
    if p["hosts"]:
        roles.append("Host of " + ", ".join('<a href="%s">%s</a>' % (show_url(x), e(ctx["shows"][x]["name"])) for x in p["hosts"]))
    if p["former"]:
        roles.append("Former host of " + ", ".join('<a href="%s">%s</a>' % (show_url(x), e(ctx["shows"][x]["name"])) for x in p["former"]))
    gshows = sorted({a["show"] for a in p["guest"]}, key=lambda x: ctx["shows"][x]["name"].lower())
    if p["guest"]:
        roles.append("Guest %d time%s on %s" % (p["groups"], "" if p["groups"] == 1 else "s", ", ".join(
            '<a href="%s">%s</a>' % (show_url(x), e(ctx["shows"][x]["name"])) for x in gshows)))
    team = ctx["player_team"].get(p["slug"])
    if team:
        roles.append('Plays for the <a href="%s">%s</a>' % (team_url(team), e(ctx["team_by_slug"][team]["name"])))
    head = p["slug"] if p["slug"] in ctx.get("headshots", ()) else None
    trail = TRAIL_HOME + [("Players", config.SITE_BASE + "/players/"), (p["name"], url)]
    talk_only = p.get("talk_only")
    h1 = ("%s on NBA player podcasts" if talk_only else "%s: podcast appearances") % p["name"]
    body = [crumbs_html(trail),
            '<div class="phead show-head">%s<div class="sh-b"><h1>%s</h1>%s'
            '<div class="meta"><a href="%s">NBA career on NBA Career Map</a></div></div></div>\n'
            % (avatar(p["name"], head, 88, big=head in ctx.get("headshots_big", ())).replace('class="av', 'class="art av'), e(h1),
               "".join('<div class="meta">%s</div>' % r for r in roles), e(CAREER_MAP % p["slug"]))]
    if vids and not talk_only:
        shows_in = sorted({it["show"] for it, _ in vids}, key=lambda x: ctx["shows"][x]["name"].lower())
        role_opts = [("", "All roles")] + ([("host", "Host")] if p["hosts"] or p["former"] else []) + ([("guest", "Guest")] if p["guest"] else [])
        opt = lambda pairs: "".join('<option value="%s">%s</option>' % (e(v), e(l)) for v, l in pairs)
        body.append('<div class="pfilter" data-target="#pv">'
                    '<label class="sr" for="pf-role">Role</label><select id="pf-role" class="sel" data-attr="role">%s</select>'
                    '<label class="sr" for="pf-show">Show</label><select id="pf-show" class="sel" data-attr="show"><option value="">All shows</option>%s</select>'
                    '<label class="sr" for="pf-fmt">Format</label><select id="pf-fmt" class="sel" data-attr="fmt">%s</select></div>'
                    '<p class="pf-count hint-below" aria-live="polite"></p>'
                    % (opt(role_opts), opt([(x, ctx["shows"][x]["name"]) for x in shows_in]), opt(STREAM_FMTS)))
        cards = []
        for it, role in vids:
            r = "guest" if role == "guest" else "host"
            c = video_card(it, ctx, label=role.capitalize())
            cards.append(c.replace('<article class="vc">', '<article class="vc" data-role="%s" data-show="%s" data-fmt="%s">'
                                   % (r, e(it["show"]), e(it["fmt"])), 1))
        body.append('<div class="grid" id="pv">%s</div>\n' % "".join(cards))
        body.append('<p class="hint-below">Guest appearances: the player is stated as a guest in the title or description '
                    '(or added by hand) and matched to one NBA Career Map player. As a host: the latest 12 and the 6 most '
                    'viewed videos of each show.</p>')
    elif vids:
        body.append('<section class="block"><div class="block-head"><h2>Appearances</h2></div><div class="grid">%s</div></section>\n'
                    % "".join(video_card(it, ctx, label=role.capitalize()) for it, role in vids))
    body.append(talk_section(ctx, ("player", p["slug"]), p["name"], "him"))
    body.append('<p class="hint-below">%s</p>' % stamp(ctx))
    if talk_only:
        title = "%s on NBA Player Podcasts: Appearances and What Players Say About Him | HoopsMatic" % p["name"]
        n = len(ctx["talk"].get(("player", p["slug"])) or [])
        desc = ("What NBA players say about %s on their podcasts: %d discussions on YouTube, the latest and most "
                "viewed, playable here, and the shows that talk about him most." % (p["name"], n))
    else:
        title = "%s Podcast Appearances: %s, Guest Episodes and Clips | HoopsMatic" % (p["name"], main_name)
        desc = ("%s on NBA player podcasts: %s. Episodes and clips, playable here."
                % (p["name"], "; ".join(__import__("re").sub("<[^>]+>", "", r) for r in roles)))
    lds = [video_ld(it, ctx) for it, _ in vids[:12]] or [video_ld(g.lead, ctx) for g in (ctx["talk"].get(("player", p["slug"])) or [])[:12]]
    return page(title, desc, url, ctx["assets_v"], "players", "".join(body), ld_script(breadcrumbs_ld(trail), *lds))


def players_index_page(ctx):
    from .cards import avatar
    url = config.SITE_BASE + "/players/"
    ps = list(ctx["players"].values())
    hosts = sorted((p for p in ps if p["hosts"] or p["former"]), key=lambda p: p["name"])
    guests_ = sorted((p for p in ps if not (p["hosts"] or p["former"]) and not p.get("talk_only")),
                     key=lambda p: (-p["groups"], p["name"]))
    talked = sorted((p for p in ps if p.get("talk_only")),
                    key=lambda p: (-len(ctx["talk"].get(("player", p["slug"])) or []), p["name"]))

    def row(p):
        head = p["slug"] if p["slug"] in ctx.get("headshots", ()) else None
        bits = []
        if p["hosts"]:
            bits.append("Host: " + ", ".join(ctx["shows"][x]["name"] for x in p["hosts"]))
        if p["former"]:
            bits.append("Former host: " + ", ".join(ctx["shows"][x]["name"] for x in p["former"]))
        if p["groups"]:
            bits.append("%d guest appearance%s" % (p["groups"], "" if p["groups"] == 1 else "s"))
        n = len(ctx["talk"].get(("player", p["slug"])) or [])
        if n:
            bits.append("talked about in %d discussion%s" % (n, "" if n == 1 else "s"))
        return ('<li><a class="pl" href="%s/players/%s/">%s<span class="pl-b"><span class="pl-n">%s</span>'
                '<span class="pl-r">%s</span></span></a></li>' % (B, e(p["slug"]), avatar(p["name"], head, 40),
                                                                 e(p["name"]), e(" · ".join(bits))))
    trail = TRAIL_HOME + [("Players", url)]
    body = [crumbs_html(trail), '<div class="hdr"><h1>NBA players on podcasts</h1></div>\n'
            '<p class="subtitle">Every NBA player who hosts a show here, has been a confirmed guest at least 3 times, '
            'or is talked about in at least 10 discussions, with their episodes and clips. %s</p>\n' % stamp(ctx)]
    for label, rows in (("Hosts", hosts), ("Guests", guests_), ("Talked about", talked)):
        if rows:
            body.append('<section class="block"><div class="block-head"><h2>%s</h2></div><ul class="players">%s</ul></section>\n'
                        % (label, "".join(row(p) for p in rows)))
    desc = ("NBA players on podcasts: %d hosts, %d frequent guests and %d players the shows talk about most, with "
            "their episodes and clips from YouTube." % (len(hosts), len(guests_), len(talked)))
    return page("NBA Players on Podcasts: Hosts and Guest Appearances | HoopsMatic", desc, url, ctx["assets_v"],
                "players", "".join(body), ld_script(breadcrumbs_ld(trail)))


# ── team pages ──

TEAM_CM = "https://hoopsmatic.com/nba-career-map/team/%s.html"


def team_page(ctx, t):
    from . import talk
    url = config.SITE_BASE + "/teams/" + t["slug"] + "/"
    trail = TRAIL_HOME + [("Teams", config.SITE_BASE + "/teams/"), (t["name"], url)]
    groups = ctx["talk"].get(("team", t["slug"])) or []
    names = t["names"] + t["historical"]
    body = [crumbs_html(trail),
            '<div class="phead"><h1>%s on NBA player podcasts</h1>'
            '<div class="meta">Matched by: %s</div>'
            '<div class="meta"><a href="%s">%s on NBA Career Map</a></div></div>\n'
            % (e(t["name"]), e(", ".join(names)), e(TEAM_CM % t["slug"]), e(t["name"]))]
    body.append(talk_section(ctx, ("team", t["slug"]), "the " + t["nickname"]))
    rows = talk.team_players(ctx["talk"], ctx["active_by_team"], t["slug"], ctx["now"])
    if rows:
        body.append('<section class="block"><div class="block-head"><h2>Their players discussed most</h2></div>'
                    '<ol class="talk-list">%s</ol><p class="hint-below">Current %s players, by discussions in the last '
                    '90 days.</p></section>\n'
                    % ("".join('<li><span class="tl-r">%d</span>%s<span class="tl-n">%d discussion%s'
                               '<span class="bn">based on %d video%s</span></span></li>'
                               % (i, player_link_html(sl, ctx, 26), c, "" if c == 1 else "s", v, "" if v == 1 else "s")
                               for i, (sl, c, v) in enumerate(rows, 1)), e(t["name"])))
    body.append('<p class="hint-below">%s</p>' % stamp(ctx))
    title = "%s on NBA Player Podcasts: Episodes and Clips About the %s | HoopsMatic" % (t["name"], t["nickname"])
    desc = ("What NBA players say about the %s on their podcasts: %d discussions on YouTube, the latest and most "
            "viewed, playable here, and the shows that talk about them most." % (t["name"], len(groups)))
    lds = [video_ld(g.lead, ctx) for g in groups[:12]]
    return page(title, desc, url, ctx["assets_v"], "teams", "".join(body), ld_script(breadcrumbs_ld(trail), *lds))


def teams_index_page(ctx):
    from . import talk
    url = config.SITE_BASE + "/teams/"
    trail = TRAIL_HOME + [("Teams", url)]
    rows = []
    for t in sorted(ctx["teams"], key=lambda t: t["name"]):
        groups = ctx["talk"].get(("team", t["slug"])) or []
        c7, _ = talk.window(groups, ctx["now"], 7)
        c30, _ = talk.window(groups, ctx["now"], 30)
        rows.append('<li><a class="pl" href="%s"><span class="pl-b"><span class="pl-n">%s</span>'
                    '<span class="pl-r">%d this week · %d in 30 days · %d in all</span></span></a></li>'
                    % (team_url(t["slug"]), e(t["name"]), c7, c30, len(groups)))
    body = [crumbs_html(trail), '<div class="hdr"><h1>NBA teams on player podcasts</h1></div>\n'
            '<p class="subtitle">The 30 NBA teams and the podcast episodes and clips that talk about them, counted '
            'by distinct discussions (clips of one episode count once). %s</p>\n' % stamp(ctx),
            '<section class="block"><ul class="players">%s</ul></section>\n' % "".join(rows)]
    desc = "All 30 NBA teams on NBA player podcasts: the episodes and clips that talk about each team, playable here."
    return page("NBA Teams on Player Podcasts: Episodes and Clips About Every Team | HoopsMatic", desc, url,
                ctx["assets_v"], "teams", "".join(body), ld_script(breadcrumbs_ld(trail)))


def methodology_page(ctx):
    url = config.SITE_BASE + "/methodology/"
    trail = TRAIL_HOME + [("Methodology", url)]
    sec = lambda h, *ps: '<section class="section method"><h2>%s</h2>%s</section>\n' % (h, "".join("<p>%s</p>" % p for p in ps))
    body = [crumbs_html(trail), '<div class="hdr"><h1>How NBA Player Podcasts works</h1></div>\n'
            '<p class="subtitle">Where every number on these pages comes from, what it means and what it cannot '
            'tell you. %s</p>\n' % stamp(ctx)]
    body.append(sec("What we collect",
        "Only public YouTube pages and feeds, with no API key and no login: each show's public video feeds and "
        "a listing of its channel's Videos, Live and Shorts tabs (the list a visitor sees). That gives every "
        "video's title, length, date and view count. Feeds also give exact view counts, likes and the start of "
        "the description for a channel's latest 15 videos.",
        "Twice a day (06:37 and 18:37 UTC, with backup runs at 09:41 and 21:41 UTC when one was missed) the feeds "
        "are read and every video from the last 90 days is listed "
        "again. Once a week (Mondays, or whenever the last full pass is a week old) every video ever posted is "
        "listed, with subscriber counts, show artwork, the NBA Career Map player names and the headshots index.",
        "Show list: <a href=\"%s/\">the rankings</a>, the <a href=\"%s/player-channels/\">player channels</a> and "
        "the <a href=\"%s/dormant/\">occasional and dormant shows</a>. A show that shares a network's channel "
        "is read from its official playlist, or by its titles." % (B, B, B)))
    body.append(sec("Formats",
        "Full episode: 20 minutes or longer. Clip: 1 to 20 minutes. Short: under a minute, or anything on a "
        "channel's Shorts tab. A video can be set by hand when the automatic format is wrong."))
    body.append(sec("Rankings",
        "The rank uses full episodes only: the current views of every full episode posted in the last 30 days. "
        "A show is ranked with at least 4 full episodes in the last 90 days, or 1 to 3 in the last 90 days and "
        "at least 4 in the last 180. Shows with 1 to 3 in 90 days (and fewer than 4 in 180) are occasional; "
        "shows with none in 90 days are dormant. Podcasts and players' personal channels are ranked separately.",
        "The table can be sorted by any of its numbers and switched to clips, Shorts or all formats. Each number "
        "says how many videos it is based on; one that cannot be worked out yet says \"no data\". Rank arrows "
        "compare with a ranking at least a week old made with the same rules, and appear only once there is one."))
    body.append(sec("Views gained and trending",
        "We save every video's view count each day (videos from the last 90 days) and each week (every video). "
        "Views gained is today's count minus the count 1, 7 or 30 days earlier, per video. A video posted after "
        "the earlier count gains all its views; a video the earlier count missed gets no number. Gained numbers "
        "appear only once both counts exist.",
        "Listing view counts are rounded by YouTube to 3 significant figures (1.24M), while feed counts are exact. "
        "When either count is rounded, both are rounded the same way before subtracting, so a big video's daily "
        "gain moves in steps (10,000 views at 1.24M) rather than showing gains that never happened."))
    body.append(sec("Breakouts",
        BREAKOUT_NOTE + " A score of 5x or more is highlighted. Homepage breakouts are from the last 30 days and "
        "score at least 2x."))
    body.append(sec("Subscribers",
        "YouTube's public, rounded subscriber count for each show's channel, read weekly. Shows that share a "
        "channel with other shows say \"shared channel\": the count belongs to all of them. Subscriber growth "
        "needs two readings at least a week apart."))
    body.append(sec("Guests and player pages",
        "A guest is confirmed only when a video's title or description states it (\"ft.\", \"feat.\", "
        "\"featuring\", \"Guest:\", \"&lt;Name&gt; joins\", or \"with\" / \"w/\" at the start of a title part or "
        "right after a show word such as \"Podcast\" or \"Episode 12\") and the name matches exactly one NBA "
        "Career Map player. Hosts and former hosts are never their own show's guests, and someone in 10 or "
        "more of one show's episodes counts as a regular, not a guest. Everything else goes to a review list that "
        "is not shown; appearances can be added or removed by hand. Clips of the same episode count once.",
        "A player gets a page with 3 or more confirmed appearances, or as the host of a show with 3 or more "
        "videos. Player names link to that page, or to the player's NBA Career Map page."))
    body.append('<section class="section method" id="talked-about"><h2>Talked about: mentions vs appearances</h2>'
                '<p>An appearance is someone IN a video: a show\'s host, or a guest stated in the title or description. '
                'A mention is someone the video is ABOUT: a player or team named in its title or in one of its chapter '
                'lines (description lines that start with a timestamp, like "12:30 Wemby\'s debut"). The rest of a '
                'description is never read. A mention found only in a chapter opens the video at that moment, on '
                'YouTube and in the player here. Full descriptions come only from YouTube\'s public feeds (each '
                'channel\'s latest 15 videos), so chapters are read from the day a video first shows up there.</p>'
                '<p>Players are matched by full name against NBA Career Map\'s players, or by a nickname on our '
                'list (<a href="https://github.com/jsierrahoopshype/hoopsmatic-player-podcasts/blob/main/data/nicknames.json">'
                'data/nicknames.json</a>: Wemby, Giannis, SGA, Bron, KD, Steph, AD, Jokic and more; it can be edited). '
                'A name written with a suffix ("Jr.", "Sr.", "II", "III") means only the player with that suffix '
                '(Jaren Jackson Jr. is never his father). A plain name shared by a father and son, where only one has a '
                'suffix on Career Map, means the one without it (Gary Payton), except for names on our always-review '
                'list (data/always_review.json: Tim Hardaway, Larry Nance, Glenn Robinson, Kelly Oubre, Jaren Jackson, '
                'Gary Trent), whose sons are often written without the suffix. A surname on its own matches when exactly '
                'one Career Map player has it (Kuminga, Haliburton); a surname shared by several players, or any other '
                'name shared by different players, is matched only when a team named in the same title or chapter line '
                'settles who it is (exactly one current player with that name on that team); otherwise it goes to a '
                'review list and is not shown. A first name on its own is ignored unless it is on the nickname list, and '
                'so is a surname that is also an everyday word (data/surname_stopwords.json: Battle, Block, Day...). '
                'Teams are matched by nickname '
                '(Lakers, Celtics, Sixers, Cavs, Mavs, Wolves, Blazers, Pels...) or a former name of the franchise '
                '(SuperSonics, Bobcats, New Jersey Nets), never by a city alone.</p>'
                '<p>A player\'s own appearance in a video does not also count as a mention of him there, and a show\'s '
                'hosts are never "talked about" on their own show. Clips of the same episode count once (as for guests: '
                'a link to the episode in the description, the same episode number, or a clip within 10 days after a '
                'full episode of the show that mentions the same player or team) and are listed under the episode. '
                'Counts are distinct discussions, with how many videos they cover. Players get a page with 10 or more '
                'discussions; all 30 teams have one. Mentions can be added or removed by hand.</p></section>\n')
    body.append(sec("Playback and privacy",
        "Thumbnails, headshots and artwork are served from hoopsmatic.com. Nothing loads from YouTube until you "
        "press play; then the video plays in YouTube's privacy-enhanced player (youtube-nocookie.com) and "
        "YouTube's privacy policy applies. See our <a href=\"/privacy\">privacy policy</a>. Videos whose owner "
        "turned off embedding link to YouTube instead, and videos that were deleted or made private are no "
        "longer shown."))
    body.append(sec("Limits",
        "YouTube sometimes refuses listings from cloud servers; when that happens the last good data stays and "
        "the next run catches up. Shorts carry no date in YouTube's listing: they are dated from the Shorts feed "
        "(latest 15), from neighbouring Shorts, or from the day we first saw them. Likes and descriptions come "
        "only from feeds, so likes per 1,000 views covers recent videos only. Only YouTube is counted: audio "
        "platforms are not."))
    desc = ("How NBA Player Podcasts collects YouTube numbers without an API key, ranks shows, works out views "
            "gained and breakouts, confirms guests and plays videos.")
    return page("Methodology: How NBA Player Podcast Rankings Work | HoopsMatic", desc, url, ctx["assets_v"], None,
                "".join(body), ld_script(breadcrumbs_ld(trail)))


def moved_page(url):
    """A stub at a page's old address: sends the visitor to the new one."""
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="robots" content="noindex"><link rel="canonical" href="%s">'
            '<meta http-equiv="refresh" content="0; url=%s"><title>Moved | HoopsMatic</title></head>'
            '<body><p>This page moved to <a href="%s">%s</a>.</p></body></html>\n' % (e(url), e(url), e(url), e(url)))


def not_found_page(ctx):
    body = ('<div class="hdr"><h1>Page not found</h1></div>'
            '<p class="subtitle">That page is not here. The <a href="%s/">NBA player podcast rankings</a> are.</p>' % B)
    html = page("Page not found | HoopsMatic", "Page not found.", config.SITE_BASE + "/", ctx["assets_v"], None, body)
    return html.replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex">')
