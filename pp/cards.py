"""Video cards.

A card's thumbnail (and its title) is a link to the video on YouTube. The
page script turns a tap on it into YouTube's player (youtube-nocookie.com),
loaded only then, in place, and only one at a time; without the script the
link simply opens YouTube. Videos whose owner turned embedding off say "Watch
on YouTube" on the thumbnail instead of a play button. Each card also has a
small YouTube icon linking to the video. Shorts get a vertical (9:16)
thumbnail; episodes and clips 16:9. site_src/app.js writes the same card for
the videos it loads later.
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


YT_ICON = ('<svg viewBox="0 0 24 17" width="22" height="16" aria-hidden="true"><rect width="24" height="17" rx="4" '
           'fill="#ff0033"/><path d="M9.5 4.5v8l6.5-4z" fill="#fff"/></svg>')


def _media(it, ctx, big=False, start=None):
    vid = it["id"]
    vertical = it["fmt"] == SHORT
    if vertical and vid in ctx.get("thumbs_v", ()):
        img = '<img src="%s/thumbs/v/%s.webp" width="270" height="480" loading="lazy" alt="">' % (B, e(vid))
    elif vid in ctx.get("thumbs_big" if big else "thumbs", ()):
        w, h = (640, 360) if big else (320, 180)
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
    about someone; more: extra HTML under the card (related clips); extra:
    "gain24" / "gain7" adds the views gained; label: a role ("Guest")."""
    from .render import compact, fmt_date
    show = ctx["shows"][it["show"]]
    meta = [fmt_date(it["published"]), compact(it["views"]) + " views"]
    if it.get("duration"):
        meta.append(fmt_len(it["duration"]))
    if extra == "gain24" and it.get("gain24") is not None:
        meta.append('<span class="gain">+%s in 24h</span>' % compact(it["gain24"]))
    elif extra == "gain7" and it.get("gain7") is not None:
        meta.append('<span class="gain">+%s in 7 days</span>' % compact(it["gain7"]))
    if start:
        meta.append('<span class="at">from %s</span>' % fmt_len(start))
    play = ' data-play="%s"%s' % (e(it["id"]), (' data-start="%d"' % start) if start else "") \
        if it.get("embed") != "no" else ""
    return ('<article class="vc vc-%s">%s<div class="vc-body">'
            '<h3 class="vc-t"><a href="%s" target="_blank" rel="noopener"%s>%s</a></h3>'
            '<div class="vc-show"><a href="%s/%s/">%s</a></div>'
            '<div class="vc-hosts">%s</div>'
            '<div class="vc-meta">%s</div>'
            '<div class="vc-foot"><span class="fmt fmt-%s">%s</span>%s%s'
            '<a class="vc-ytic" href="%s" target="_blank" rel="noopener" aria-label="Watch on YouTube" '
            'title="Watch on YouTube">%s</a></div>%s'
            '</div></article>'
            % (e(it["fmt"]), _media(it, ctx, start=start), e(yt(it["id"], start)), play, e(it["title"]),
               B, e(show["slug"]), e(show["name"]), hosts_html(show, ctx), " · ".join(meta),
               e(it["fmt"]), FMT_LABEL.get(it["fmt"], "Video"),
               badge(it) if show_breakout else "", ('<span class="role">%s</span>' % e(label)) if label else "",
               e(yt(it["id"], start)), YT_ICON, more))


def clips_more(clips):
    """'Also from this episode': [(id, title, seconds or None)]."""
    if not clips:
        return ""
    links = "".join('<li><a href="%s" target="_blank" rel="noopener">%s</a>%s</li>'
                    % (e(yt(c, t)), e(title), (' <span class="at">from %s</span>' % fmt_len(t)) if t else "")
                    for c, title, t in clips[:4])
    extra = (' <span class="at">and %d more</span>' % (len(clips) - 4)) if len(clips) > 4 else ""
    return '<div class="vc-more"><span class="lbl">Also from this episode</span><ul>%s</ul>%s</div>' % (links, extra)


def talk_extra(g):
    """A discussion's feed extra: where to start and its other clips."""
    x = {"r": "talk"}
    if g.starts.get(g.lead["id"]):
        x["t"] = g.starts[g.lead["id"]]
    if g.clips:
        x["c"] = [[c["id"], c["title"], g.starts.get(c["id"])] for c in g.clips]
    return x
