"""Scraper for pazar3.mk (car listings)."""
import asyncio
import re
from playwright.async_api import Browser

from .base import (
    BaseScraper, PRICE_RANGES, browser_context_options, stealth_async,
    parse_price_eur, parse_year, parse_mileage, parse_make_model,
)
from . import db as dbmod

# pazar3 serves both /mk/ (Macedonian) and /en/ language variants.
_BASE_SEARCH = "https://www.pazar3.mk/mk/mali-oglasi/avtomobili/"


def _build_url(price_from: int, price_to: int | None, page: int) -> str:
    params = f"?price_from={price_from}"
    if price_to is not None:
        params += f"&price_to={price_to}"
    if page > 1:
        params += f"&p={page}"
    return _BASE_SEARCH + params


def _incremental_url(page: int) -> str:
    params = "?sort=-date"
    if page > 1:
        params += f"&p={page}"
    return _BASE_SEARCH + params


def _listing_id_from_url(href: str) -> str | None:
    # e.g. /mk/oglas/avtomobili/123456/bmw-320d/ or /oglas/123456/
    m = re.search(r"/(\d{5,})/", href)
    return m.group(1) if m else None


async def _extract(cell) -> dict | None:
    """Extract one listing from a search-result card element."""
    # Resolve the anchor
    if await cell.get_attribute("href"):
        anchor = cell
    else:
        anchor = await cell.query_selector("a[href]")
    if not anchor:
        return None

    href = await anchor.get_attribute("href") or ""
    listing_id = _listing_id_from_url(href)
    if not listing_id:
        return None
    url = href if href.startswith("http") else f"https://www.pazar3.mk{href}"

    full_text = (await cell.inner_text()) or ""

    # Title
    title_el = await cell.query_selector("h2, h3, h4, .listing-title, .ad-title, .title, [class*='title']")
    if title_el:
        title = (await title_el.inner_text()).strip()
    else:
        title = next((ln.strip() for ln in full_text.splitlines() if ln.strip()), "")

    # Price
    price_el = await cell.query_selector(
        ".price, .cena, [class*='price'], [class*='cena'], [class*='Price']"
    )
    price_text = (await price_el.inner_text()).strip() if price_el else ""
    if not price_text:
        for ln in full_text.splitlines():
            if "€" in ln or "eur" in ln.lower() or "ден" in ln:
                price_text = ln.strip()
                break

    if "договор" in price_text.lower() or "dogovor" in price_text.lower():
        return None
    price_eur = parse_price_eur(price_text)
    if not price_eur:
        return None

    # Location
    loc_el = await cell.query_selector(
        ".location, .lokacija, .grad, [class*='locat'], [class*='lokacij']"
    )
    location = (await loc_el.inner_text()).strip() if loc_el else None

    # Date
    date_el = await cell.query_selector(".date, .datum, [class*='date'], [class*='datum']")
    date_posted = (await date_el.inner_text()).strip() if date_el else None

    year = parse_year(title + " " + full_text)
    mileage = parse_mileage(full_text)
    make, model = parse_make_model(title)

    return {
        "source": "pazar3",
        "listing_id": listing_id,
        "title": title,
        "make": make,
        "model": model,
        "price_eur": price_eur,
        "year": year,
        "mileage": mileage,
        "fuel_type": None,
        "transmission": None,
        "engine_size": None,
        "location": location,
        "listing_url": url,
        "date_posted": date_posted,
    }


async def _scrape_page(page, url: str) -> list[dict]:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2_000)
    except Exception as e:
        print(f"[pazar3] load error {url}: {e}")
        return []

    # Try progressively broader selectors
    cells = await page.query_selector_all(
        ".listing-item, .ad-item, [class*='listing-item'], [class*='ad-item']"
    )
    if not cells:
        cells = await page.query_selector_all("article, .card, [class*='oglas']")
    if not cells:
        # Last-resort: any anchors that look like listing URLs
        cells = await page.query_selector_all("a[href*='/oglas/']")

    results = []
    for cell in cells:
        try:
            r = await _extract(cell)
            if r:
                results.append(r)
        except Exception as e:
            print(f"[pazar3] extract error: {e}")
    return results


class Pazar3Scraper(BaseScraper):
    def __init__(self, db_client, start_time: float):
        super().__init__(db_client, start_time, "pazar3")

    async def crawl_full(self, browser: Browser) -> None:
        print("[pazar3] full crawl starting")
        self.known_ids = dbmod.get_known_ids(self.db, self.source)
        print(f"[pazar3] {len(self.known_ids)} known IDs")

        ctx = await browser.new_context(**browser_context_options())
        pg = await ctx.new_page()
        await stealth_async(pg)

        try:
            for price_from, price_to in PRICE_RANGES:
                if self.time_up():
                    print("[pazar3] time limit reached")
                    return

                cp = dbmod.get_checkpoint(self.db, self.source, "full", price_from, price_to)
                if cp and cp["status"] == "done":
                    print(f"[pazar3] range {price_from}-{price_to} already done")
                    continue

                start_page = (cp["current_page"] if cp else 1)
                print(f"[pazar3] range {price_from}-{price_to} from page {start_page}")

                current_page = start_page
                while True:
                    if self.time_up():
                        dbmod.upsert_checkpoint(self.db, {
                            "source": self.source, "crawl_type": "full",
                            "price_range_start": price_from, "price_range_end": price_to,
                            "current_page": current_page, "status": "in_progress",
                        })
                        print(f"[pazar3] saved checkpoint at page {current_page}")
                        return

                    url = _build_url(price_from, price_to, current_page)
                    listings = await _scrape_page(pg, url)
                    if not listings:
                        break

                    for listing in listings:
                        if listing["listing_id"] not in self.known_ids:
                            dbmod.upsert_listing(self.db, listing)
                            self.known_ids.add(listing["listing_id"])
                            self.new_count += 1

                    print(f"[pazar3] page {current_page}: {len(listings)} found, {self.new_count} new total")
                    dbmod.upsert_checkpoint(self.db, {
                        "source": self.source, "crawl_type": "full",
                        "price_range_start": price_from, "price_range_end": price_to,
                        "current_page": current_page + 1, "status": "in_progress",
                    })
                    current_page += 1
                    await asyncio.sleep(1)

                dbmod.mark_checkpoint_done(self.db, self.source, "full", price_from, price_to)
                print(f"[pazar3] range {price_from}-{price_to} done")
        finally:
            await ctx.close()

        print(f"[pazar3] full crawl done. new_count={self.new_count}")

    async def crawl_incremental(self, browser: Browser) -> None:
        print("[pazar3] incremental crawl starting")
        self.known_ids = dbmod.get_known_ids(self.db, self.source)

        ctx = await browser.new_context(**browser_context_options())
        pg = await ctx.new_page()
        await stealth_async(pg)

        try:
            for page_num in range(1, 11):
                if self.time_up():
                    break
                listings = await _scrape_page(pg, _incremental_url(page_num))
                if not listings:
                    break
                new_this_page = 0
                for listing in listings:
                    if listing["listing_id"] not in self.known_ids:
                        dbmod.upsert_listing(self.db, listing)
                        self.known_ids.add(listing["listing_id"])
                        self.new_count += 1
                        new_this_page += 1
                print(f"[pazar3] incremental page {page_num}: {new_this_page} new")
                if new_this_page == 0:
                    break
                await asyncio.sleep(1)
        finally:
            await ctx.close()

        print(f"[pazar3] incremental done. new_count={self.new_count}")
