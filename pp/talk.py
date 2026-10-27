"""Counts and lists for 'talked about' (pp/mentions.py finds the mentions).

One discussion = one group: a full episode and its clips count once. A
group's date is its latest video's; a window ("this week", "last 30 days")
counts the groups with a video posted in it, and says how many videos that
is ("based on N videos").
"""
from datetime import timedelta

from . import metrics
from .util import parse_ts

MIN_TALK_PAGE = 10          # discussions (groups) for a player page from mentions alone
WEEKS = 12                  # mentions-per-week chart


class Group:
    def __init__(self, key, items, starts):
        self.key = key
        self.items = sorted(items, key=lambda it: it["published"], reverse=True)
        fulls = [it for it in items if it["fmt"] == metrics.FULL]
        # The card shows the full episode when the group has one, else its most viewed video.
        self.lead = max(fulls or items, key=lambda it: it["views"])
        self.clips = [it for it in self.items if it is not self.lead]
        self.starts = starts                    # {video id: seconds into it, from a chapter}
        self.latest = self.items[0]["published"]
        self.views = max(it["views"] for it in items)
        self.show = self.lead["show"]

    def in_window(self, cut):
        return [it for it in self.items if parse_ts(it["published"]) >= cut]


def build(mentions, groups, item_by_id):
    """-> {(kind, slug): [Group]} newest first."""
    out = {}
    for target, gs in groups.items():
        lst = []
        for key, vids in gs.items():
            items = [item_by_id[v] for v in vids if v in item_by_id]
            if not items:
                continue
            starts = {}
            for v in vids:
                for m in mentions.get(v, []):
                    if (m["kind"], m["slug"]) == target and m.get("t") is not None and m["src"] == "chapter":
                        starts[v] = m["t"]
            lst.append(Group(key, items, starts))
        lst.sort(key=lambda g: g.latest, reverse=True)
        if lst:
            out[target] = lst
    return out


def window(groups, now, days):
    """(discussions, videos) with a video posted in the last `days` days."""
    cut = now - timedelta(days=days)
    n = vids = 0
    for g in groups:
        w = g.in_window(cut)
        if w:
            n += 1
            vids += len(w)
    return n, vids


def leaders(talk, kind, now, days, n=10):
    """[(slug, discussions, videos)] most talked about in the window."""
    rows = []
    for (k, slug), gs in talk.items():
        if k != kind:
            continue
        c, v = window(gs, now, days)
        if c:
            rows.append((slug, c, v))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows[:n]


def top_shows(groups, n=8):
    """[(show, discussions)] most first."""
    c = {}
    for g in groups:
        c[g.show] = c.get(g.show, 0) + 1
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def per_week(groups, now):
    """[(week start date, discussions)] for the last 12 weeks (by when the
    videos were posted), or [] when fewer than 3 of those weeks have any."""
    start = (now - timedelta(days=now.weekday())).date()
    weeks = [start - timedelta(weeks=i) for i in range(WEEKS - 1, -1, -1)]
    counts = {w: 0 for w in weeks}
    for g in groups:
        d = parse_ts(g.latest).date()
        w = d - timedelta(days=d.weekday())
        if w in counts:
            counts[w] += 1
    rows = [(w.isoformat(), counts[w]) for w in weeks]
    return rows if sum(1 for _, c in rows if c) >= 3 else []


def team_players(talk, active_by_team, team, now, days=90, n=10):
    """The team's current players discussed most in the last `days` days."""
    rows = []
    for slug in active_by_team.get(team, ()):
        gs = talk.get(("player", slug))
        if gs:
            c, v = window(gs, now, days)
            if c:
                rows.append((slug, c, v))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows[:n]
