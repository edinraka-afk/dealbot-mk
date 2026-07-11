#!/usr/bin/env python3
"""
Run pricing analysis, flag deals in DB, send Telegram alerts for new deals.

Usage:
  python scripts/run_analysis.py [--threshold 0.15] [--min-comp 5]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scraper.db import get_client, get_unalerted_deals, mark_alerted, count_listings
from analysis.analyzer import run as run_analysis
from alerts.telegram import send, send_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.15)
    parser.add_argument("--min-comp", type=int, default=5)
    parser.add_argument("--max-alerts", type=int, default=10,
                        help="Cap alerts per run to avoid flooding")
    args = parser.parse_args()

    db = get_client()

    deal_count = run_analysis(db, threshold=args.threshold, min_comp=args.min_comp)
    print(f"Analysis complete. {deal_count} deals in DB.")

    deals = get_unalerted_deals(db)
    print(f"{len(deals)} unalerted deals to send")

    sent = 0
    for deal in deals[:args.max_alerts]:
        ok = send(deal)
        if ok:
            mark_alerted(db, deal["id"])
            sent += 1
            print(f"Alerted: {deal.get('title')} @ {deal.get('price_eur')} EUR")
        else:
            print(f"Alert failed for listing id={deal['id']}")

    r5 = count_listings(db, "reklama5")
    p3 = count_listings(db, "pazar3")
    print(f"DB totals — reklama5: {r5:,}  pazar3: {p3:,}")

    if sent > 0:
        send_summary(sent, r5, p3)


if __name__ == "__main__":
    main()
