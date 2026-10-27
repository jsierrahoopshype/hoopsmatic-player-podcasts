"""A small end-to-end build: the player-channels page exists, is in the
sitemap, and each type is ranked on its own page."""
import json
from datetime import timedelta

from pp import build, config
from tests.helpers import NOW


def ep(days, views, title):
    d = NOW - timedelta(days=days)
    return {"title": title, "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"), "published_exact": True,
            "duration": 3600, "tab": "videos", "views": views}


def test_build_writes_player_channels_page_and_sitemap(tmp_path, monkeypatch):
    shows = [{"slug": "pod", "name": "The Pod", "hosts": [{"name": "Al", "url": "https://hoopsmatic.com/nba-career-map/player/al.html"}],
              "channel_id": "UCpod", "youtube_url": "u", "type": "podcast"},
             {"slug": "occ", "name": "Now And Then", "hosts": [{"name": "Cy", "url": None}], "channel_id": "UCocc",
              "youtube_url": "u", "type": "podcast"},
             {"slug": "net", "name": "Network", "hosts": [], "channel_id": "UCnet", "youtube_url": "u", "type": "podcast",
              "exclude_reason": "network channel, not a player podcast"},
             {"slug": "vlog", "name": "Vlog Guy", "hosts": ["B"], "channel_id": "UCvlog", "youtube_url": "u",
              "type": "player_channel"}]
    (tmp_path / "videos").mkdir()
    (tmp_path / "channels.json").write_text(json.dumps({"shows": shows}))
    for sid, base, days in (("UCpod", 1000, (1, 10, 20, 40)), ("UCvlog", 50000, (1, 10, 20, 40)),
                            ("UCocc", 70, (30,)), ("UCnet", 9, (1, 2, 3, 4))):
        vids = {"%s%07d" % (sid[2:6], i): ep(d, base + i, "Episode %d" % i) for i, d in enumerate(days)}
        (tmp_path / "videos" / (sid + ".json")).write_text(json.dumps({"source_id": sid, "videos": vids}))
    for name in ("CHANNELS_FILE", "SUBSCRIBERS_FILE", "RANKS_FILE", "STATUS_FILE", "EXCLUDED_FILE", "SITEMAP_STATE_FILE",
                 "APPEARANCES_FILE", "APPEARANCES_REVIEW_FILE", "APPEARANCES_MANUAL_FILE", "EMBED_FILE"):
        monkeypatch.setattr(config, name, tmp_path / getattr(config, name).name)
    monkeypatch.setattr(config, "VIDEOS_DIR", tmp_path / "videos")
    monkeypatch.setattr(config, "THUMBS_DIR", tmp_path / "thumbs")
    out = tmp_path / "site"
    ctx = build.build(now=NOW, fetch_thumbs=False, out=out)

    assert [s["slug"] for s in ctx["ranked"]] == ["pod"]
    assert [s["slug"] for s in ctx["ranked_pc"]] == ["vlog"]
    index = (out / "index.html").read_text()
    pc = (out / "player-channels" / "index.html").read_text()
    assert "The Pod" in index and "Vlog Guy" not in index.split('id="lb"')[1].split("</table>")[0]
    assert "Vlog Guy" in pc
    assert '<link rel="canonical" href="https://hoopsmatic.com/player-podcasts/player-channels/">' in pc
    assert 'href="/player-podcasts/player-channels/"' in index
    xml = (out / "sitemap.xml").read_text()
    assert "<loc>https://hoopsmatic.com/player-podcasts/player-channels/</loc>" in xml
    assert "<loc>https://hoopsmatic.com/player-podcasts/vlog/</loc>" in xml
    assert "github.io" not in xml
    # occasional: on the occasional & dormant page with its last date, not in the rankings
    assert [s["slug"] for s in ctx["occasional"]] == ["occ"]
    dormant = (out / "dormant" / "index.html").read_text()
    assert "<h1>Occasional &amp; dormant shows</h1>" in dormant and "Occasional podcasts" in dormant
    assert "Now And Then" in dormant and "Sep 26, 2026" in dormant
    assert "Now And Then" not in index.split('id="lb"')[1].split("</table>")[0]
    assert "<loc>https://hoopsmatic.com/player-podcasts/occ/</loc>" in xml
    # roster exclusion: no page, no sitemap entry, reason in excluded.json
    assert not (out / "net").exists() and "/player-podcasts/net/" not in xml
    exc = json.loads(config.EXCLUDED_FILE.read_text())["excluded_by_rules"]
    assert [(x["slug"], x["reason"]) for x in exc] == [("net", "network channel, not a player podcast")]
    # host links: Al hosts a show with 3+ videos, so Al has a player page and
    # every host link points there; the page is in the sitemap
    assert '<a class="host" href="/player-podcasts/players/al/">Al</a>' in index
    al = (out / "players" / "al" / "index.html").read_text()
    assert "<title>Al Podcast Appearances: The Pod, Guest Episodes and Clips | HoopsMatic</title>" in al
    assert 'href="https://hoopsmatic.com/nba-career-map/player/al.html"' in al
    assert "<loc>https://hoopsmatic.com/player-podcasts/players/al/</loc>" in xml
    assert "<loc>https://hoopsmatic.com/player-podcasts/players/</loc>" in xml
    show = (out / "pod" / "index.html").read_text()
    assert "<title>The Pod: Episodes, Clips and YouTube Rankings | HoopsMatic</title>" in show
    assert '"@type": "BreadcrumbList"' in show and '"@type": "VideoObject"' in show
    # page thresholds: 4 full episodes and no clips -> episodes shelf, no clips shelf
    assert "<h2>Most viewed episodes</h2>" in show and "<h2>Most viewed clips</h2>" not in show
    # methodology page: own title, canonical on hoopsmatic.com, in the sitemap
    meth = (out / "methodology" / "index.html").read_text()
    assert "<h1>How NBA Player Podcasts works</h1>" in meth
    assert '<link rel="canonical" href="https://hoopsmatic.com/player-podcasts/methodology/">' in meth
    assert "<loc>https://hoopsmatic.com/player-podcasts/methodology/</loc>" in xml
    # every page: one H1, a distinct title, the contact footer, never github.io
    titles = set()
    for f in out.rglob("index.html"):
        html = f.read_text()
        assert html.count("<h1>") == 1, f
        t = html.split("<title>")[1].split("</title>")[0]
        assert t not in titles, t
        titles.add(t)
        assert "Anything wrong? Email us at" in html and "For business inquiries, contact us at" in html
        assert "github.io" not in html
