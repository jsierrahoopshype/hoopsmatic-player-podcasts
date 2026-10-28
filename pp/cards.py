"""Video cards, shelves and the featured card.

A card's thumbnail is a link to the video on YouTube. The page script turns a
click on it into YouTube's player (youtube-nocookie.com), loaded only then and
only for that video; without the script the link simply opens YouTube. Videos
whose owner turned embedding off get a plain "Watch on YouTube" link instead
of a play button. Every card also has a small "Watch on YouTube" link.
"""
from html import escape

from . import config
from .metrics import FULL, CLIP, SHORT

B = config.BASE_PATH
FMT_LABEL = {FULL: "Full episode", CLIP: "Clip", SHORT: "Short", "unknown": "Video"}


def e(s):
    return escape("" if s is None else str(s), quote=True)


def yt(vid, start=None):
    """YouTube link; with start, it opens at that second (t= parameter)."""
    return "https://www.youtube.com/watch?v=" + vid + ("&t=%ds" % start if start else "")


def fmt_len(sec):
    if sec is None:
        return ""
    sec = int(sec)
    h, m = divmod(sec // 60, 60)
    return ("%d:%02d:%02d" % (h, m, sec % 60)) if h else ("%d:%02d" % (m, sec % 60))


def host_people(show, ctx):
    """[(name, url or None, headshot slug or None)] for a show's hosts. The
    url is the host's page under /players/ when there is one, else their
    Career Map page."""
    from .people import host_link, slug_from_url
    out = []
    for h in show.get("hosts") or []:
        name, url = (h, None) if isinstance(h, str) else (h["name"], h.get("url"))
        slug = slug_from_url(url)
        out.append((name, host_link(url), slug if slug and slug in ctx.get("headshots", ()) else None))
    return out


def avatar(name, head_slug, size=22, big=False):
    """face-fill headshot in a grey circle (the 320px copy when big), else initials."""
    from .headshots import initials
    if head_slug:
        return ('<img class="av" src="%s/headshots/%s%s.webp" width="%d" height="%d" loading="lazy" alt="">'
                % (B, "320/" if big else "", e(head_slug), size, size))
    return '<span class="av av-i" aria-hidden="true">%s</span>' % e(initials(name))


def hosts_html(show, ctx, avatars=True):
    bits = []
    for name, url, head in host_people(show, ctx):
        face = avatar(name, head) if avatars else ""
        bits.append(('<a class="host" href="%s">%s%s</a>' % (e(url), face, e(name))) if url
                    else '<span class="host">%s%s</span>' % (face, e(name)))
    return "".join(bits)


def _media(it, ctx, big=False, start=None):
    vid = it["id"]
    thumb_set = ctx.get("thumbs_big" if big else "thumbs", ())
    w, h = (640, 360) if big else (320, 180)
    if vid in thumb_set:
        img = ('<img src="%s/thumbs/%s%s.webp" width="%d" height="%d"%s alt="">'
               % (B, "big/" if big else "", e(vid), w, h, "" if big else ' loading="lazy"'))
    else:
        img = '<span class="vc-noimg"></span>'
    dur = ('<span class="vc-dur">%s</span>' % fmt_len(it.get("duration"))) if it.get("duration") else ""
    if it.get("embed") == "no":
        return ('<a class="vc-media vc-noembed" href="%s" target="_blank" rel="noopener">%s'
                '<span class="vc-ext">Watch on YouTube</span>%s</a>' % (e(yt(vid, start)), img, dur))
    # data-start: the in-page player starts at that second too.
    return ('<a class="vc-media" href="%s" target="_blank" rel="noopener" data-play="%s"%s aria-label="Play: %s">%s'
            '<span class="vc-btn" aria-hidden="true"></span>%s</a>'
            % (e(yt(vid, start)), e(vid), (' data-start="%d"' % start) if start else "", e(it["title"]), img, dur))


def badge(it):
    b = it.get("breakout")
    if b is None:
        return ""
    return '<span class="bo%s">%.1fx</span>' % (" hot" if b >= config.BREAKOUT_X else "", b)


def video_card(it, ctx, show_breakout=False, extra="", label="", start=None, more=""):
    """start: open (and play) at that second, e.g. a chapter that talks
    about someone; more: extra HTML under the meta line (related clips)."""
    from .render import fmt_date, full
    show = ctx["shows"][it["show"]]
    gain = ""
    if extra == "gain24" and it.get("gain24") is not None:
        gain = ' · <span class="gain">+%s in 24h</span>' % full(it["gain24"])
    elif extra == "gain7" and it.get("gain7") is not None:
        gain = ' · <span class="gain">+%s in 7 days</span>' % full(it["gain7"])
    return ('<article class="vc">%s<div class="vc-body">'
            '<div class="vc-top"><span class="fmt fmt-%s">%s</span>%s%s</div>'
            '<h3 class="vc-t"><a href="%s" target="_blank" rel="noopener">%s</a></h3>'
            '<div class="vc-show"><a href="%s/%s/">%s</a></div>'
            '<div class="vc-hosts">%s</div>'
            '<div class="vc-meta">%s · %s views%s%s</div>%s'
            '<a class="vc-yt" href="%s" target="_blank" rel="noopener">Watch on YouTube</a>'
            '</div></article>'
            % (_media(it, ctx, start=start), e(it["fmt"]), FMT_LABEL.get(it["fmt"], "Video"),
               badge(it) if show_breakout else "", ('<span class="role">%s</span>' % e(label)) if label else "",
               e(yt(it["id"], start)), e(it["title"]), B, e(show["slug"]), e(show["name"]),
               hosts_html(show, ctx), fmt_date(it["published"]), full(it["views"]), gain,
               (' · <span class="at">from %s</span>' % fmt_len(start)) if start else "", more, e(yt(it["id"], start))))


def talk_card(g, ctx):
    """One discussion: the full episode (or the most viewed video) as the
    card, opening at the chapter that talks about them when there is one,
    with the other clips of the same episode listed under it."""
    more = ""
    if g.clips:
        links = "".join('<li><a href="%s" target="_blank" rel="noopener">%s</a>%s</li>'
                        % (e(yt(c["id"], g.starts.get(c["id"]))), e(c["title"]),
                           (' <span class="at">from %s</span>' % fmt_len(g.starts[c["id"]])) if g.starts.get(c["id"]) else "")
                        for c in g.clips[:4])
        extra = (' <span class="at">and %d more</span>' % (len(g.clips) - 4)) if len(g.clips) > 4 else ""
        more = ('<div class="vc-more"><span class="lbl">Also from this episode</span><ul>%s</ul>%s</div>'
                % (links, extra))
    return video_card(g.lead, ctx, start=g.starts.get(g.lead["id"]), more=more)


def featured(it, ctx, why):
    from .render import fmt_date, full
    show = ctx["shows"][it["show"]]
    return ('<article class="vc vc-feat">%s<div class="vc-body">'
            '<div class="vc-top"><span class="fmt fmt-%s">%s</span></div>'
            '<h3 class="vc-t"><a href="%s" target="_blank" rel="noopener">%s</a></h3>'
            '<div class="vc-show"><a href="%s/%s/">%s</a></div>'
            '<div class="vc-hosts">%s</div>'
            '<div class="vc-meta">%s · %s · <strong>%s</strong> views</div>'
            '<p class="vc-why">%s</p>'
            '<a class="vc-yt" href="%s" target="_blank" rel="noopener">Watch on YouTube</a>'
            '</div></article>'
            % (_media(it, ctx, big=True), e(it["fmt"]), FMT_LABEL.get(it["fmt"], "Video"),
               e(yt(it["id"])), e(it["title"]), B, e(show["slug"]), e(show["name"]),
               hosts_html(show, ctx), fmt_date(it["published"]), fmt_len(it.get("duration")) or "",
               full(it["views"]), e(why), e(yt(it["id"]))))


def shelf(title, items, ctx, note="", extra="", show_breakout=False, anchor=None):
    """A titled row of cards: scrolls sideways inside itself on small screens
    (never the page), a grid on wide ones."""
    if not items:
        return ""
    return ('<section class="block"%s><div class="block-head"><h2>%s</h2></div>'
            '<div class="shelf">%s</div>%s</section>\n'
            % ((' id="%s"' % anchor) if anchor else "", e(title),
               "".join(video_card(it, ctx, show_breakout, extra) for it in items),
               ('<p class="hint-below">%s</p>' % note) if note else ""))
