"""Turning YouTube's "3 weeks ago" into a usable publish date.

A channel listing (what yt-dlp reads without touching any video page) only says
how long ago each video went up, in YouTube's coarse buckets: days for the
first week, then weeks, then months, then years. Two things make that good
enough:

  * the listing is in upload order, newest first, and
  * the public feed gives the exact time for the latest uploads,

so every video lies between its neighbours. Videos that share a bucket are
spread evenly across it in listing order, then clamped so dates never go
backwards. Exact dates are never replaced by estimates.
"""
import re
from datetime import timedelta

# YouTube writes these both long ("3 weeks ago") and short ("3w ago", "1mo ago",
# "2y ago", "streamed 5d ago"); days run up to 13 in the short form.
UNITS = {
    "s": "second", "sec": "second", "second": "second",
    "min": "minute", "minute": "minute",
    "h": "hour", "hr": "hour", "hour": "hour",
    "d": "day", "day": "day",
    "w": "week", "wk": "week", "week": "week",
    "mo": "month", "month": "month",
    "y": "year", "yr": "year", "year": "year",
}
REL_RE = re.compile(r"(\d+)\s*(seconds?|secs?|s|minutes?|mins?|hours?|hrs?|h|days?|d|weeks?|wks?|w|"
                    r"months?|mo|years?|yrs?|y)\.?\s+ago", re.I)


def bucket(text):
    """Relative text -> (min_age_days, max_age_days) or None."""
    if not text:
        return None
    t = text.lower()
    if "today" in t or "just now" in t:
        return (0.0, 1.0)
    if "yesterday" in t:
        return (1.0, 2.0)
    m = REL_RE.search(t)
    if not m:
        return None
    n = int(m.group(1))
    word = m.group(2).lower()
    unit = UNITS.get(word) or UNITS.get(word.rstrip("s"))
    if unit in ("second", "minute", "hour"):
        return (0.0, 1.0)
    if unit == "day":
        return (float(n), float(n + 1))
    if unit == "week":
        # YouTube switches to "1 month ago" at about 30 days.
        return (7.0 * n, min(7.0 * (n + 1), 30.44))
    if unit == "month":
        return (30.44 * n, 30.44 * (n + 1))
    return (365.25 * n, 365.25 * (n + 1))


def estimate(entries, now):
    """Fill in estimated publish times for one listing.

    entries: list in listing order (newest first) of dicts with
      "exact": aware datetime or None, "rel": relative text or None.
    Returns a list of aware datetimes (or None when nothing is known)."""
    n = len(entries)
    lo = [None] * n
    hi = [None] * n
    for i, e in enumerate(entries):
        if e.get("exact") is not None:
            age = (now - e["exact"]).total_seconds() / 86400.0
            lo[i] = hi[i] = max(age, 0.0)
        else:
            b = bucket(e.get("rel"))
            if b:
                lo[i], hi[i] = b

    # Spread each run of same-bucket estimates evenly across its bucket.
    age = [None] * n
    i = 0
    while i < n:
        if lo[i] is None or entries[i].get("exact") is not None:
            age[i] = lo[i]
            i += 1
            continue
        j = i
        while (j + 1 < n and entries[j + 1].get("exact") is None
               and lo[j + 1] == lo[i] and hi[j + 1] == hi[i]):
            j += 1
        k = j - i + 1
        for r in range(k):
            age[i + r] = lo[i] + (hi[i] - lo[i]) * (r + 0.5) / k
        i = j + 1

    # Ages never decrease down the listing: clamp estimates between known
    # neighbours (exact entries are left alone).
    prev = 0.0
    for i in range(n):
        if age[i] is None:
            continue
        if entries[i].get("exact") is None and age[i] < prev:
            age[i] = prev
        prev = max(prev, age[i])
    nxt = None
    for i in range(n - 1, -1, -1):
        if age[i] is None:
            continue
        if entries[i].get("exact") is None and nxt is not None and age[i] > nxt:
            age[i] = nxt
        nxt = age[i] if nxt is None else min(nxt, age[i])

    # Entries with no date text at all (a Shorts tab lists none) that sit
    # between two dated entries are spread evenly between them. Nothing is
    # guessed before the first or after the last dated entry.
    known = [i for i in range(n) if age[i] is not None]
    for a_i, b_i in zip(known, known[1:]):
        gap = b_i - a_i
        for r in range(1, gap):
            age[a_i + r] = age[a_i] + (age[b_i] - age[a_i]) * r / gap

    return [None if a is None else now - timedelta(days=a) for a in age]
