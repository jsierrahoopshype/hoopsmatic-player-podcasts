"""Chapter lines in a video description: lines that start with a timestamp
("0:00 Intro", "12:30 - Wemby's debut", "(1:02:15) Lakers talk"). Only these
lines are read for "talked about"; the rest of a description is ignored.

Full descriptions come only from the public feeds (each channel's latest 15
videos), so chapters build up from the day a video is first seen in a feed.
"""
import re

LINE = re.compile(r"^\s*[\(\[]?(?P<ts>\d{1,2}(?::\d{2}){1,2})[\)\]]?\s*(?:[-–—:|•.]\s*)?(?P<text>\S.*?)\s*$")


def seconds(ts):
    """'1:02:15' -> 3735, '12:30' -> 750."""
    parts = [int(p) for p in ts.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def parse(description, limit=60):
    """-> [[seconds, text]] in the order written. A description counts as
    having chapters only with 2 or more such lines (one stray timestamp is
    not a chapter list)."""
    out = []
    for line in (description or "").splitlines():
        m = LINE.match(line)
        if not m:
            continue
        parts = m.group("ts").split(":")
        if any(len(p) != 2 for p in parts[1:]):
            continue
        out.append([seconds(m.group("ts")), m.group("text")[:160]])
        if len(out) >= limit:
            break
    return out if len(out) >= 2 else []
