"""Thin wrappers around the Supabase client."""
import os
from datetime import datetime, timezone
from supabase import create_client, Client


def get_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


def get_known_ids(client: Client, source: str) -> set[str]:
    """Return all listing_ids already stored for *source*."""
    ids: set[str] = set()
    page, size = 0, 1000
    while True:
        rows = (
            client.table("listings")
            .select("listing_id")
            .eq("source", source)
            .range(page * size, (page + 1) * size - 1)
            .execute()
        ).data
        for r in rows:
            ids.add(r["listing_id"])
        if len(rows) < size:
            break
        page += 1
    return ids


def upsert_listing(client: Client, listing: dict) -> None:
    listing["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.table("listings").upsert(listing, on_conflict="source,listing_id").execute()


def get_checkpoint(
    client: Client, source: str, crawl_type: str, price_from: int, price_to: int | None
) -> dict | None:
    q = (
        client.table("crawl_checkpoints")
        .select("*")
        .eq("source", source)
        .eq("crawl_type", crawl_type)
        .eq("price_range_start", price_from)
    )
    q = q.is_("price_range_end", "null") if price_to is None else q.eq("price_range_end", price_to)
    rows = q.limit(1).execute().data
    return rows[0] if rows else None


def upsert_checkpoint(client: Client, row: dict) -> dict:
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = client.table("crawl_checkpoints").upsert(
        row, on_conflict="source,crawl_type,price_range_start,price_range_end"
    ).execute()
    return result.data[0] if result.data else row


def mark_checkpoint_done(client: Client, source: str, crawl_type: str, price_from: int, price_to: int | None) -> None:
    q = (
        client.table("crawl_checkpoints")
        .update({"status": "done", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("source", source)
        .eq("crawl_type", crawl_type)
        .eq("price_range_start", price_from)
    )
    q = q.is_("price_range_end", "null") if price_to is None else q.eq("price_range_end", price_to)
    q.execute()


def all_ranges_done(client: Client) -> bool:
    from scraper.base import PRICE_RANGES
    for source in ("reklama5", "pazar3"):
        for pf, pt in PRICE_RANGES:
            cp = get_checkpoint(client, source, "full", pf, pt)
            if not cp or cp["status"] != "done":
                return False
    return True


def count_listings(client: Client, source: str) -> int:
    r = client.table("listings").select("id", count="exact").eq("source", source).execute()
    return r.count or 0


def get_unalerted_deals(client: Client) -> list[dict]:
    return (
        client.table("listings")
        .select("*")
        .eq("is_deal", True)
        .is_("alerted_at", "null")
        .execute()
    ).data


def mark_alerted(client: Client, listing_id_db: int) -> None:
    client.table("listings").update(
        {"alerted_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", listing_id_db).execute()
