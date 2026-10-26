from pp import sitemap

U = "https://hoopsmatic.com/player-podcasts/"


def page(views, stamp):
    return "<h1>Rankings</h1><!--volatile--><span>Updated %s</span><!--/volatile--><td>%s</td>" % (stamp, views)


def test_lastmod_stays_when_only_the_stamp_changes():
    s1 = sitemap.update_state({}, {U: page("1.2M", "Oct 25")}, "2026-10-25")
    s2 = sitemap.update_state(s1, {U: page("1.2M", "Oct 26")}, "2026-10-26")
    assert s2[U]["lastmod"] == "2026-10-25"


def test_lastmod_moves_when_content_changes():
    s1 = sitemap.update_state({}, {U: page("1.2M", "Oct 25")}, "2026-10-25")
    s2 = sitemap.update_state(s1, {U: page("1.3M", "Oct 26")}, "2026-10-26")
    assert s2[U]["lastmod"] == "2026-10-26"
    assert s2[U]["hash"] != s1[U]["hash"]


def test_new_and_removed_urls():
    s1 = sitemap.update_state({}, {U: "a"}, "2026-10-25")
    s2 = sitemap.update_state(s1, {U: "a", U + "club-520/": "b"}, "2026-10-26")
    assert s2[U]["lastmod"] == "2026-10-25"
    assert s2[U + "club-520/"]["lastmod"] == "2026-10-26"
    s3 = sitemap.update_state(s2, {U: "a"}, "2026-10-27")
    assert list(s3) == [U]


def test_rendered_sitemap_uses_hoopsmatic_urls():
    xml = sitemap.render(sitemap.update_state({}, {U: "a"}, "2026-10-25"))
    assert "<loc>https://hoopsmatic.com/player-podcasts/</loc><lastmod>2026-10-25</lastmod>" in xml
    assert "github.io" not in xml
