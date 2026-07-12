#!/usr/bin/env python3
"""
DOM inspector — dumps rendered HTML structure for both listing pages so we
can identify the correct CSS selectors.  Run this in CI before tweaking
scraper selectors; no Supabase credentials needed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scraper.base import browser_context_options

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


SITES = [
    {
        "site": "reklama5.mk",
        "url": "https://www.reklama5.mk/Search?cat=24&page=1",
        "use_proxy": True,
        "timeout_ms": 120_000,
        "wait_ms": 12_000,
    },
    {
        "site": "pazar3.mk",
        "url": "https://www.pazar3.mk/oglasi/vozila/avtomobili",
        "use_proxy": False,
        "timeout_ms": 30_000,
        "wait_ms": 3_000,
    },
]

# Candidate selectors to probe — we count matches for each.
CANDIDATE_SELECTORS = [
    ".OglasCell",
    "[class*='OglasCell']",
    "[class*='oglas-cell']",
    "a[href*='/Oglas/']",
    "a[href*='/AdDetails']",
    ".listing-item",
    ".ad-item",
    "[class*='listing-item']",
    "[class*='ad-item']",
    "article",
    "[class*='listing']",
    "[class*='card']",
    "[class*='ad-']",
    "a[href*='/oglas/']",
    "[class*='product']",
    "[class*='item']",
]


async def inspect_site(browser, cfg: dict) -> None:
    site = cfg["site"]
    print(f"\n{'='*60}")
    print(f"INSPECTING: {site}")
    print(f"URL: {cfg['url']}")
    print(f"proxy={cfg['use_proxy']}")
    print("=" * 60)

    ctx = await browser.new_context(**browser_context_options(use_proxy=cfg["use_proxy"]))
    page = await ctx.new_page()
    await stealth_async(page)

    try:
        resp = await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=cfg["timeout_ms"])
        print(f"HTTP status: {resp.status if resp else 'N/A'}")
        await page.wait_for_timeout(cfg["wait_ms"])

        title = await page.title()
        print(f"Page title: {title}")

        html = await page.content()
        print(f"HTML length: {len(html)} chars")

        # --- HTML snippet ---
        print("\n--- First 5000 chars of rendered HTML ---")
        print(html[:5000])

        # --- Selector probe ---
        print("\n--- Candidate selector element counts ---")
        for sel in CANDIDATE_SELECTORS:
            try:
                els = await page.query_selector_all(sel)
                if els:
                    print(f"  {len(els):4d}  {sel}")
            except Exception:
                pass

        # --- All unique class tokens in the page ---
        classes = await page.evaluate("""() => {
            const tokens = new Set();
            document.querySelectorAll('[class]').forEach(el => {
                el.className.toString().split(/\\s+/).forEach(c => {
                    if (c) tokens.add(c);
                });
            });
            return [...tokens].sort();
        }""")
        print(f"\n--- All unique CSS classes ({len(classes)} total) ---")
        print("  " + "\n  ".join(classes))

        # --- Unique href patterns ---
        hrefs = await page.evaluate("""() => {
            const seen = new Set();
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                // keep only the path up to first query/hash
                const path = h.replace(/[?#].*/, '');
                // collapse numeric IDs
                const pattern = path.replace(/\\d{4,}/g, '{ID}');
                seen.add(pattern);
            });
            return [...seen].sort().slice(0, 50);
        }""")
        print(f"\n--- Unique href patterns (first 50) ---")
        print("  " + "\n  ".join(hrefs))

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await ctx.close()


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for cfg in SITES:
            await inspect_site(browser, cfg)
        await browser.close()
    print("\n=== Inspection complete ===")


if __name__ == "__main__":
    asyncio.run(main())
