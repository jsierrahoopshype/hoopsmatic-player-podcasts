"""python -m pp daily | weekly | weekly-if-due | build"""
import sys

from . import build, collect


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "daily":
        collect.daily()
    elif cmd == "weekly":
        collect.weekly()          # never raises; a blocked run is recorded in data/status.json
    elif cmd == "weekly-if-due":
        # Mondays, or whenever the last full listing is a week old (a skipped
        # Monday run is caught up by the next scheduled run).
        if collect.weekly_due():
            collect.weekly()
        else:
            print("full listing not due today")
    elif cmd == "build":
        build.build()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
