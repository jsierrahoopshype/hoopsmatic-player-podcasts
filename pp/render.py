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
             ("most-watched", "Most watched", B + "/most-watched/"),
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
        return ('<img class="%s" src="%s/thumbs/%s.jpg" width="160" height="90" loading="lazy" alt="">'
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
    if ch is None:
        return '<span class="chg flat">–</span>'
    if ch == "NEW":
        return '<span class="chg new">NEW</span>'
    if ch > 0:
        return '<span class="chg up">▲%d</span>' % ch
    if ch < 0:
        return '<span class="chg down">▼%d</span>' % -ch
    return '<span class="chg flat">–</span>'


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
    a bare string is a host with no player page."""
    return [(h, None) if isinstance(h, str) else (h["name"], h.get("url")) for h in show.get("hosts") or []]


def hosts_line(show):
    """Plain text, for meta descriptions."""
    return ", ".join(n for n, _ in _hosts(show))


def hosts_html(show):
    """Each host linked to their HoopsMatic player page when there is one."""
    return ", ".join('<a class="host" href="%s">%s</a>' % (e(u), e(n)) if u else e(n) for n, u in _hosts(show))


# ── pages ──

def leaderboard(ctx, ranked=None):
    rows, cards = [], []
    for s in (ctx["ranked"] if ranked is None else ranked):
        show = ctx["shows"][s["slug"]]
        ch = ctx["changes"].get(s["slug"]) if ctx["changes"] else None
        shared = ctx["shared"][s["slug"]]
        subs_txt = "shared" if shared else compact(s["subs"])
        cells = [
            ('rank', s["rank"], '<td class="rank">%d</td>' % s["rank"]),
            ('chg', change_sort(ch), '<td>%s</td>' % change_html(ch)),
            ('name', show["name"].lower(),
             '<td class="name"><a class="q" href="%s">%s</a><span class="ev">%s</span></td>'
             % (show_url(show["slug"]), e(show["name"]), hosts_html(show))),
            ('mom', s["momentum"], '<td class="pct">%s</td>' % compact(s["momentum"])),
            ('typ', s["typical"] or 0, '<td>%s</td>' % compact(s["typical"])),
            ('subs', -1 if shared else (s["subs"] or 0), '<td>%s</td>' % subs_txt),
            ('subw', -1e12 if (shared or s["subs_change"] is None) else s["subs_change"],
             '<td>%s</td>' % subs_change_html(s, shared)),
            ('subp', -1e12 if (shared or s["subs_change_pct"] is None) else s["subs_change_pct"], None),
            ('likes', s["likes_per_1k"] or 0, '<td>%s</td>' % one_dec(s["likes_per_1k"])),
            ('epm', s["episodes_per_month"], '<td>%s</td>' % one_dec(s["episodes_per_month"])),
        ]
        attrs = " ".join('data-%s="%s"' % (k, e(v)) for k, v, _ in cells)
        rows.append('<tr %s>%s</tr>' % (attrs, "".join(c for _, _, c in cells if c)))
        cards.append(
            '<div class="card" %s><div class="now"><span class="p">%s</span><span class="lbl">30-day views</span></div>'
            '<div class="q"><span class="crank">%d</span> %s <a href="%s">%s</a></div>'
            '<div class="ev">%s</div>'
            '<div class="card-foot"><span><span class="lbl">Typical</span>%s</span>'
            '<span><span class="lbl">Subs</span>%s</span>'
            '<span><span class="lbl">Likes/1K</span>%s</span>'
            '<span><span class="lbl">Eps/mo</span>%s</span></div></div>'
            % (attrs, compact(s["momentum"]), s["rank"], change_html(ch), show_url(show["slug"]), e(show["name"]),
               hosts_html(show), compact(s["typical"]), subs_txt, one_dec(s["likes_per_1k"]),
               one_dec(s["episodes_per_month"])))
    head_cells = [("rank", "#", "asc"), ("chg", "Change", "desc"), ("name", "Show", "asc"),
                  ("mom", "30-day views", "desc"), ("typ", "Typical episode", "desc"),
                  ("subs", "Subscribers", "desc"), ("subw", "Subs this week", "desc"),
                  ("likes", "Likes per 1K", "desc"), ("epm", "Episodes / month", "desc")]
    th = "".join('<th class="sortable%s%s" data-sort="%s" data-dir="%s">%s</th>'
                 % (" left" if k == "name" else "", " sorted-by" if k == "rank" else "", k, d, lbl)
                 for k, lbl, d in head_cells)
    sort_opts = "".join('<option value="%s:%s">%s</option>' % (k, d, "Rank" if k == "rank" else lbl) for k, lbl, d in head_cells
                        if k not in ("chg",)) + '<option value="subp:desc">Subs this week (%)</option><option value="chg:desc">Rank change</option>'
    return ('<div class="sortbar"><label for="lb-sort">Sort by</label> <select id="lb-sort" class="sel">%s</select></div>'
            '<div class="table-wrap"><table class="lb" id="lb"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            '<div class="cards" id="lb-cards">%s</div>'
            % (sort_opts, th, "\n".join(rows), "\n".join(cards)))


def index_page(ctx):
    url = config.SITE_BASE + "/"
    top = ctx["ranked"][:3]
    top_names = ", ".join(ctx["shows"][s["slug"]]["name"] for s in top)
    desc = ("NBA player podcasts ranked by YouTube views on full episodes from the last 30 days. "
            "Top right now: %s." % top_names) if top else "NBA player podcasts ranked by YouTube views."
    body = ['<div class="hdr"><h1>NBA Player Podcasts</h1></div>\n'
            '<p class="subtitle">%d podcasts hosted by NBA players, ranked by YouTube views on full episodes '
            '(20 minutes or longer) posted in the last 30 days. %s</p>\n' % (len(ctx["ranked"]), stamp(ctx))]
    eow = ctx["episode_of_week"]
    if eow:
        show = ctx["shows"][eow["slug"]]
        body.append('<section class="block"><div class="block-head"><h2>Episode of the week</h2></div>'
                    '<div class="eow">%s<div class="eow-body">%s'
                    '<div class="ep-meta"><a class="ep-show" href="%s">%s</a> · %s · %s</div>'
                    '<div class="eow-num"><span class="v">%s</span> views%s</div></div></div></section>\n'
                    % (thumb(eow["id"], ctx, "th big"), ep_link(eow), show_url(show["slug"]), e(show["name"]),
                       fmt_date(eow["published"]), fmt_len(eow.get("duration")), full(eow["views"]),
                       (" · " + breakout_tag(eow.get("breakout")) + " its show's typical episode")
                       if eow.get("breakout") else ""))
    if ctx["breakouts"]:
        body.append('<section class="block"><div class="block-head"><h2>Latest breakouts</h2></div><div class="eps">')
        for v in ctx["breakouts"]:
            body.append(ep_row(v, ctx, ctx["shows"][v["slug"]]))
        body.append('</div><p class="hint-below">Full episodes from the last 30 days with at least 5 times '
                    'their show\'s typical views.</p></section>\n')
    body.append('<section class="block"><div class="block-head"><h2>Rankings</h2></div>')
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
    return page("NBA Player Podcasts Rankings by YouTube Views | HoopsMatic", desc, url, ctx["assets_v"],
                "rankings", "".join(body), extra)


def method_html(ctx):
    rc = ("Rank change compares with the ranking from a week earlier." if ctx["changes"]
          else "Rank changes start once there is a ranking from a week earlier.")
    return ('<section class="section method"><h2>How the rankings work</h2>'
            '<p>Only YouTube numbers count, and only full episodes (20 minutes or longer); clips (1 to 20 minutes) '
            'and Shorts (under a minute) are left out. 30-day views add up the current views of every full episode '
            'posted in the last 30 days. Typical episode is the median views of full episodes from the last 90 days. '
            'A breakout is an episode with at least 5 times its show\'s typical views. Likes per 1K is likes per '
            '1,000 views on recent full episodes. Subscribers come from YouTube\'s public (rounded) counts; shows '
            'that share a channel with another show say "shared". %s</p>'
            '<p>A show is ranked with at least 4 full episodes in the last 90 days, or 1 to 3 in the last 90 days '
            'and at least 4 in the last 180. Shows with 1 to 3 in the last 90 days (and fewer than 4 in 180) are '
            '<a href="%s/dormant/">occasional</a>, and shows with none in the last 90 days are dormant; neither is '
            'ranked until it posts more. Podcasts and players\' personal channels are ranked separately, with the '
            'same numbers and rules.</p></section>\n' % (rc, B))


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


def show_page(ctx, s):
    show = ctx["shows"][s["slug"]]
    url = config.SITE_BASE + "/" + show["slug"] + "/"
    shared = ctx["shared"][s["slug"]]
    eps = s["episodes"]
    if s["status"] == "ranked":
        ch = ctx["changes"].get(s["slug"]) if ctx["changes"] else None
        pc = s["type"] == "player_channel"
        status = 'Ranked <strong>No. %d</strong> of %d %s by 30-day views%s' % (
            s["rank"], len(ctx["ranked_pc"] if pc else ctx["ranked"]),
            '<a href="%s/player-channels/">player channels</a>' % B if pc else "podcasts",
            (" " + change_html(ch)) if ch not in (None, 0) else "")
    else:
        label = "Occasional" if s["status"] == "occasional" else "Dormant"
        status = '<a href="%s/dormant/">%s</a>: last full episode %s' % (B, label, fmt_date(s["last_episode"]))
    hosts = hosts_line(show)
    body = ['<div class="phead"><h1>%s</h1><div class="meta">%s<span>%s</span>'
            '<span class="sep">·</span><a href="%s" target="_blank" rel="noopener">YouTube</a></div>'
            '<div class="meta">%s</div></div>\n'
            % (e(show["name"]), ('<span>Hosted by %s</span><span class="sep">·</span>' % hosts_html(show)) if hosts else "",
               stamp(ctx), e(show["youtube_url"]), status)]
    subs_card = ('<div class="num">shared</div><div class="sub">channel carries other shows</div>' if shared else
                 '<div class="num">%s</div><div class="sub">%s this week</div>'
                 % (compact(s["subs"]), (signed(s["subs_change"]) + " (" + pct(s["subs_change_pct"]) + ")")
                    if s["subs_change"] is not None else "change: –"))
    body.append('<div class="stat-cards">'
                '<div class="stat-card"><div class="lbl">30-day views</div><div class="num">%s</div><div class="sub">full episodes, last 30 days</div></div>'
                '<div class="stat-card"><div class="lbl">Typical episode</div><div class="num">%s</div><div class="sub">median, last 90 days</div></div>'
                '<div class="stat-card"><div class="lbl">Subscribers</div>%s</div>'
                '<div class="stat-card"><div class="lbl">Likes per 1K views</div><div class="num">%s</div><div class="sub">full episodes, last 90 days</div></div>'
                '<div class="stat-card"><div class="lbl">Episodes per month</div><div class="num">%s</div><div class="sub">%d full episodes in 90 days</div></div>'
                '<div class="stat-card"><div class="lbl">Full episodes</div><div class="num">%s</div><div class="sub">on YouTube, all time</div></div>'
                '</div>\n'
                % (compact(s["momentum"]), compact(s["typical"]), subs_card, one_dec(s["likes_per_1k"]),
                   one_dec(s["episodes_per_month"]), s["episodes_90"], full(len(eps))))
    body.append('<section class="section"><h2>Views per episode</h2><p class="hint">Last %d full episodes, oldest '
                'to newest. Dashed line: typical episode. Highlighted: breakouts.</p>%s</section>\n'
                % (min(len(eps), 40), chart_svg(eps, s["typical"])))
    recent = sorted(eps, key=lambda v: v["published"], reverse=True)[:12]
    body.append('<section class="block"><div class="block-head"><h2>Recent episodes</h2></div><div class="eps">%s</div></section>\n'
                % "".join(ep_row(v, ctx) for v in recent))
    best = sorted(eps, key=lambda v: -v["views"])[:10]
    body.append('<section class="block"><div class="block-head"><h2>Top episodes, all time</h2></div><div class="eps">%s</div></section>\n'
                % "".join(ep_row(v, ctx, rank=i) for i, v in enumerate(best, 1)))
    if show.get("note"):
        body.append('<p class="note">%s</p>\n' % e(show["note"]))
    desc = ("%s%s on YouTube: %s views on full episodes in the last 30 days, %s on a typical episode. "
            "Top episodes and views per episode." % (show["name"], (" (" + hosts + ")") if hosts else "",
                                                     full(s["momentum"]), full(s["typical"])))
    title = "%s: YouTube Views and Top Episodes | HoopsMatic" % show["name"]
    return page(title, desc, url, ctx["assets_v"], None, "".join(body))


def not_found_page(ctx):
    body = ('<div class="hdr"><h1>Page not found</h1></div>'
            '<p class="subtitle">That page is not here. The <a href="%s/">NBA player podcast rankings</a> are.</p>' % B)
    html = page("Page not found | HoopsMatic", "Page not found.", config.SITE_BASE + "/", ctx["assets_v"], None, body)
    return html.replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex">')
