from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)


def vid(days_ago, views, duration=3600, title="Episode", tab="videos", likes=None):
    d = NOW - timedelta(days=days_ago)
    v = {"title": title, "published": d.strftime("%Y-%m-%dT%H:%M:%SZ"), "published_exact": True,
         "duration": duration, "tab": tab, "views": views}
    if likes is not None:
        v["likes"], v["likes_views"] = likes, views
    return v


def cat(*videos):
    return {"videos": {"v%02d" % i: v for i, v in enumerate(videos)}}


SHOW = {"slug": "s", "name": "S", "channel_id": "UCx", "hosts": []}
