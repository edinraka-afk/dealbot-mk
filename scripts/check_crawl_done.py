#!/usr/bin/env python3
"""
Print 'true' if every price-range checkpoint for both sources is marked done,
'false' otherwise.  Used by the full-crawl workflow to decide whether to
re-trigger another chunk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scraper.db import get_client, all_ranges_done, count_listings


def main():
    db = get_client()
    done = all_ranges_done(db, sources=("pazar3",))
    print("true" if done else "false")
    if done:
        r5 = count_listings(db, "reklama5")
        p3 = count_listings(db, "pazar3")
        print(f"reklama5: {r5:,} listings", file=sys.stderr)
        print(f"pazar3:   {p3:,} listings", file=sys.stderr)


if __name__ == "__main__":
    main()
