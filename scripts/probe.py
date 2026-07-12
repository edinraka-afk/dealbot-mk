#!/usr/bin/env python3
"""
Phase 0 — IP viability probe.

reklama5.mk is checked through the scraping proxy (Cloudflare-blocked from
Azure IPs). pazar3.mk is checked via direct connection (works fine from
GitHub runners).

Exits 0 if both pass, 1 if either fails.
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
        "block_markers": ["just a moment", "captcha", "access denied"],
        "use_proxy": True,
        "timeout_ms": 120_000,   # proxy + Cloudflare challenge needs time
        "wait_ms": 12_000,
    },
    {
        "site": "pazar3.mk",
        "url": "https://www.pazar3.mk/oglasi/vozila/avtomobili",
        "markers": ["listing", "oglas", "avtomobili", "cena", "price"],
        # "blocked" omitted — appears in Facebook Pixel JS on legitimate pages
        "block_markers": ["captcha", "access denied"],
        "use_proxy": False,
        "timeout_ms": 30_000,
        "wait_ms": 3_000,
    },
]


async def probe() -> bool:
    ok = True
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for check in CHECKS:
            site = check["site"]
            url = check["url"]
            print(f"\n--- Probing {site} (proxy={check['use_proxy']}) ---")
            print(f"URL: {url}")

            ctx = await browser.new_context(**browser_context_options(use_proxy=check["use_proxy"]))
            page = await ctx.new_page()
            await stealth_async(page)

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=check["timeout_ms"])
                status = resp.status if resp else "N/A"
                print(f"HTTP status: {status}")

                await page.wait_for_timeout(check["wait_ms"])

                html = await page.content()
                print(f"HTML length: {len(html)} chars")

                title = await page.title()
                print(f"Page title: {title}")

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
                    # Print snippet for debugging (first 2000 chars)
                    print(f"Snippet: {html[:2000].replace(chr(10), ' ')}")
                    ok = False

            except Exception as e:
                print(f"FAIL — exception: {e}")
                ok = False
            finally:
                await ctx.close()

        await browser.close()

    return ok


if __name__ == "__main__":
    passed = asyncio.run(probe())
    print("\n=== Phase 0 result:", "PASS" if passed else "FAIL", "===")
    sys.exit(0 if passed else 1)
