"""Send Telegram alert messages via the Bot API."""
import os
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _fmt(listing: dict) -> str:
    pct = round((listing.get("deal_score") or 0) * 100)
    km = listing.get("mileage")
    km_str = f"{km:,} km" if km else "km N/A"
    return (
        f"[DEAL] {listing.get('title', 'N/A')}\n"
        f"Price: {listing.get('price_eur', '?')} EUR ({pct}% below market)\n"
        f"Year: {listing.get('year', '?')} | {km_str}\n"
        f"Source: {listing.get('source', '?')}\n"
        f"{listing.get('listing_url', '')}"
    )


def send(listing: dict) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = _fmt(listing)
    r = requests.post(
        _API.format(token=token),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    if not r.ok:
        print(f"Telegram error: {r.status_code} {r.text}")
    return r.ok


def send_summary(new_count: int, pazar3_total: int) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = (
        f"DealBot MK — incremental run complete\n"
        f"New listings: {new_count}\n"
        f"pazar3 total: {pazar3_total:,}"
    )
    r = requests.post(
        _API.format(token=token),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    return r.ok
