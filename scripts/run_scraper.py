#!/usr/bin/env python3
"""
Entry point for the scraper.  Used by both full-crawl and incremental workflows.

Usage:
  python scripts/run_scraper.py --mode full
  python scripts/run_scraper.py --mode incremental [--source reklama5|pazar3|all]
"""
import asyncio
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from playwright.async_api import async_playwright
from scraper.db import get_client
from scraper.reklama5 import Reklama5Scraper
from scraper.pazar3 import Pazar3Scraper


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], required=True)
    parser.add_argument("--source", choices=["reklama5", "pazar3", "all"], default="all")
    args = parser.parse_args()

    db = get_client()
    start_time = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            scrapers = []
            if args.source in ("reklama5", "all"):
                scrapers.append(Reklama5Scraper(db, start_time))
            if args.source in ("pazar3", "all"):
                scrapers.append(Pazar3Scraper(db, start_time))

            for scraper in scrapers:
                if args.mode == "full":
                    await scraper.crawl_full(browser)
                else:
                    await scraper.crawl_incremental(browser)

            total_new = sum(s.new_count for s in scrapers)
            print(f"\nTotal new listings this run: {total_new}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
