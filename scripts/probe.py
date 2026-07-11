#!/usr/bin/env python3
"""
Phase 0 — IP viability probe.

Loads one search-results page from each site with stealth mode enabled and
asserts that listing markup is present in the HTML.
Exits 0 on success, 1 on failure.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scraper.base import browser_context_options

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


CHECKS = [
    {
        "site": "reklama5.mk",
        "url": "https://www.reklama5.mk/Search?cat=24&page=1",
        "markers": ["OglasResults", "OglasCell", "oglasresults", "oglas"],
        "block_markers": ["just a moment", "captcha", "blocked", "access denied", "robot"],
    },
    {
        "site": "pazar3.mk",
        "url": "https://www.pazar3.mk/mk/mali-oglasi/avtomobili/",
        "markers": ["listing", "oglas", "avtomobili", "cena", "price"],
        "block_markers": ["captcha", "blocked", "forbidden"],
    },
]


async def probe() -> bool:
    ok = True
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(**browser_context_options())
        page = await ctx.new_page()

        # Apply stealth patches to avoid Cloudflare headless detection
        await stealth_async(page)

        for check in CHECKS:
            site = check["site"]
            url = check["url"]
            print(f"\n--- Probing {site} ---")
            print(f"URL: {url}")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                status = resp.status if resp else "N/A"
                print(f"HTTP status: {status}")

                # Give Cloudflare JS challenges time to complete
                await page.wait_for_timeout(10_000)

                html = await page.content()
                print(f"HTML length: {len(html)} chars")

                title = await page.title()
                print(f"Page title: {title}")

                snippet = html[:2000].replace("\n", " ")
                print(f"HTML snippet: {snippet}")

                html_lower = html.lower()
                found = any(m.lower() in html_lower for m in check["markers"])
                is_blocked = any(b in html_lower for b in check["block_markers"])

                if found and not is_blocked:
                    matched = [m for m in check["markers"] if m.lower() in html_lower]
                    print(f"PASS — found markers: {matched}")
                elif is_blocked:
                    blocked = [b for b in check["block_markers"] if b in html_lower]
                    print(f"FAIL — block page detected: {blocked}")
                    ok = False
                else:
                    print(f"FAIL — none of {check['markers']} found in page HTML")
                    ok = False

                # Navigate away before next check (fresh page state)
                await page.goto("about:blank")
                await page.wait_for_timeout(1_000)

            except Exception as e:
                print(f"FAIL — exception: {e}")
                ok = False

        await browser.close()

    return ok


if __name__ == "__main__":
    passed = asyncio.run(probe())
    print("\n=== Phase 0 result:", "PASS" if passed else "FAIL", "===")
    sys.exit(0 if passed else 1)
