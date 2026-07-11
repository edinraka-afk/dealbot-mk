#!/usr/bin/env python3
"""
Phase 0 — IP viability probe.

Loads one search-results page from each site and asserts that listing
markup is present in the HTML.  Exits 0 on success, 1 on failure.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scraper.base import browser_context_options

from playwright.async_api import async_playwright


CHECKS = [
    {
        "site": "reklama5.mk",
        "url": "https://www.reklama5.mk/Search?cat=24&page=1",
        "markers": ["OglasResults", "OglasCell", "oglasresults", "oglas"],
    },
    {
        "site": "pazar3.mk",
        "url": "https://www.pazar3.mk/mk/mali-oglasi/avtomobili/",
        "markers": ["listing", "oglas", "avtomobili", "cena", "price"],
    },
]


async def probe() -> bool:
    ok = True
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(**browser_context_options())
        page = await ctx.new_page()

        for check in CHECKS:
            site = check["site"]
            url = check["url"]
            print(f"\n--- Probing {site} ---")
            print(f"URL: {url}")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(3_000)
                status = resp.status if resp else "N/A"
                print(f"HTTP status: {status}")

                html = await page.content()
                print(f"HTML length: {len(html)} chars")

                # Dump first listing-like snippet for debugging
                snippet = html[:3000].replace("\n", " ")
                print(f"HTML snippet: {snippet}")

                found = any(m.lower() in html.lower() for m in check["markers"])
                if found:
                    matched = [m for m in check["markers"] if m.lower() in html.lower()]
                    print(f"PASS — found markers: {matched}")
                else:
                    print(f"FAIL — none of {check['markers']} found in page HTML")
                    # Check for common block pages
                    if any(w in html.lower() for w in ["captcha", "blocked", "forbidden", "access denied", "robot"]):
                        print("  => Site appears to be blocking the request (captcha/block page detected)")
                    ok = False
            except Exception as e:
                print(f"FAIL — exception: {e}")
                ok = False

        await browser.close()

    return ok


if __name__ == "__main__":
    passed = asyncio.run(probe())
    print("\n=== Phase 0 result:", "PASS" if passed else "FAIL", "===")
    sys.exit(0 if passed else 1)
