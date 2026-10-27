import json
from datetime import datetime, timezone, date
from pathlib import Path


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, line_per_key=None, also=()):
    """Write JSON with sorted keys. With line_per_key, the dict (or list) under
    that key is written one entry per line so a daily change to one video is a
    one-line diff; a list keeps its order."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Other lists to write one item per line, besides line_per_key.
    more = set(also or ())
    if line_per_key and isinstance(data.get(line_per_key), list):
        head = {k: v for k, v in data.items() if k != line_per_key}
        lines = ["{"]
        for k in sorted(head):
            if k in more and isinstance(head[k], list):
                lines.append("  %s: [" % json.dumps(k))
                lines += ["    %s%s" % (json.dumps(it, ensure_ascii=False, sort_keys=True), "," if i < len(head[k]) - 1 else "")
                          for i, it in enumerate(head[k])]
                lines.append("  ],")
                continue
            lines.append("  %s: %s," % (json.dumps(k), json.dumps(head[k], ensure_ascii=False, sort_keys=True)))
        items = data[line_per_key]
        lines.append("  %s: [" % json.dumps(line_per_key))
        for i, it in enumerate(items):
            lines.append("    %s%s" % (json.dumps(it, ensure_ascii=False, sort_keys=True), "," if i < len(items) - 1 else ""))
        lines.append("  ]")
        lines.append("}")
        text = "\n".join(lines) + "\n"
    elif line_per_key and isinstance(data.get(line_per_key), dict):
        head = {k: v for k, v in data.items() if k != line_per_key}
        lines = ["{"]
        for k in sorted(head):
            lines.append("  %s: %s," % (json.dumps(k), json.dumps(head[k], ensure_ascii=False, sort_keys=True)))
        inner = data[line_per_key]
        lines.append("  %s: {" % json.dumps(line_per_key))
        keys = sorted(inner)
        for i, k in enumerate(keys):
            comma = "," if i < len(keys) - 1 else ""
            lines.append("    %s: %s%s" % (json.dumps(k), json.dumps(inner[k], ensure_ascii=False, sort_keys=True), comma))
        lines.append("  }")
        lines.append("}")
        text = "\n".join(lines) + "\n"
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_ts(s):
    """ISO string -> aware datetime (UTC)."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str(now=None):
    return (now or utcnow()).date().isoformat()


def as_date(s):
    return date.fromisoformat(s[:10])
