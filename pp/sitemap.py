"""sitemap.xml with a <lastmod> that moves only when that page's content does.

data/sitemap-state.json keeps, per URL, the hash of the page's content and the
date it last changed. Each build hashes every page again: an unchanged hash
keeps the old date, a new or changed one gets today's. Parts of a page that
change on every build without being content (the "updated" stamp) are wrapped
in <!--volatile-->...<!--/volatile--> and left out of the hash.
"""
import hashlib
import re
from xml.sax.saxutils import escape

VOLATILE = re.compile(r"<!--volatile-->.*?<!--/volatile-->", re.S)


def content_hash(html):
    return hashlib.sha256(VOLATILE.sub("", html).encode("utf-8")).hexdigest()


def update_state(state, pages, today):
    """state {url: {"hash", "lastmod"}}, pages {url: html} -> new state.
    URLs no longer built are dropped."""
    new = {}
    for url, html in pages.items():
        h = content_hash(html)
        old = (state or {}).get(url)
        if old and old.get("hash") == h:
            new[url] = old
        else:
            new[url] = {"hash": h, "lastmod": today}
    return new


def render(state):
    rows = []
    for url in sorted(state):
        rows.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (escape(url), state[url]["lastmod"]))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")
