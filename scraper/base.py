import os
import re
import time

from playwright_stealth import stealth_async  # noqa: F401  (re-exported for scrapers)

BROWSER_CTX = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "viewport": {"width": 1920, "height": 1080},
    "locale": "mk-MK",
}

# Price ranges in EUR used for pagination splitting.
# NULL upper bound means no PriceTo filter is applied.
PRICE_RANGES = [
    (0, 1000),
    (1000, 2000),
    (2000, 3000),
    (3000, 5000),
    (5000, 7500),
    (7500, 10000),
    (10000, 15000),
    (15000, 20000),
    (20000, 30000),
    (30000, 50000),
    (50000, None),
]

MAX_RUNTIME_SECONDS = 5 * 3600  # stop well before the 6-hour GitHub cap


def browser_context_options():
    opts = dict(BROWSER_CTX)
    proxy_url = os.environ.get("SCRAPING_PROXY_URL", "").strip()
    if proxy_url:
        opts["proxy"] = {"server": proxy_url}
    return opts


def parse_price_eur(text: str) -> int | None:
    if not text:
        return None
    low = text.lower()
    if "договор" in low or "dogovor" in low:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    price = int(digits)
    # Very rough MKD→EUR guard: MKD prices are 60× larger
    if price > 500_000:
        price = round(price / 61.5)
    return price if price > 0 else None


def parse_year(text: str) -> int | None:
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text or "")
    return int(m.group(1)) if m else None


def parse_mileage(text: str) -> int | None:
    m = re.search(r"([\d\s,\.]+)\s*(?:km|км)", text or "", re.IGNORECASE)
    if m:
        cleaned = re.sub(r"[^\d]", "", m.group(1))
        return int(cleaned) if cleaned else None
    return None


def parse_make_model(title: str) -> tuple[str | None, str | None]:
    if not title:
        return None, None
    clean = re.sub(r"\b(19[5-9]\d|20[0-2]\d)\b", "", title).strip()
    parts = clean.split()
    make = parts[0].title() if parts else None
    model = parts[1] if len(parts) > 1 else None
    return make, model


class BaseScraper:
    def __init__(self, db_client, start_time: float, source: str):
        self.db = db_client
        self.start_time = start_time
        self.source = source
        self.known_ids: set[str] = set()
        self.new_count = 0

    def time_up(self) -> bool:
        return (time.time() - self.start_time) > MAX_RUNTIME_SECONDS
