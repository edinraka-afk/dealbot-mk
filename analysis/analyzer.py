"""Price analysis: group listings, compute medians, flag underpriced deals."""
import pandas as pd
import numpy as np
from supabase import Client

DEAL_THRESHOLD = 0.15   # 15% below group median
MIN_COMPARABLES = 5     # minimum group size to flag a deal
MILEAGE_BAND_KM = 25_000


def _fetch_all(client: Client) -> pd.DataFrame:
    rows = []
    page, size = 0, 1000
    while True:
        chunk = (
            client.table("listings")
            .select("id,source,listing_id,title,make,model,price_eur,year,mileage,listing_url")
            .not_.is_("price_eur", "null")
            .range(page * size, (page + 1) * size - 1)
            .execute()
        ).data
        rows.extend(chunk)
        if len(chunk) < size:
            break
        page += 1
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _mileage_band(km: float) -> int:
    return int((km // MILEAGE_BAND_KM) * MILEAGE_BAND_KM)


def run(client: Client, threshold: float = DEAL_THRESHOLD, min_comp: int = MIN_COMPARABLES) -> int:
    """Score all listings, write is_deal + deal_score back to DB. Returns deal count."""
    df = _fetch_all(client)
    if df.empty:
        print("No listings with price found.")
        return 0

    print(f"Loaded {len(df)} priced listings")

    # Drop rows with missing grouping keys
    df = df.dropna(subset=["make", "model", "year", "mileage", "price_eur"])
    df["year"] = df["year"].astype(int)
    df["mileage"] = df["mileage"].astype(int)
    df["price_eur"] = df["price_eur"].astype(int)
    df["mileage_band"] = df["mileage"].apply(_mileage_band)

    # For each listing, comparables = same make+model, year within ±2, same mileage band
    deal_ids: set[int] = set()
    updates = []

    for (make, model), grp in df.groupby(["make", "model"]):
        for idx, row in grp.iterrows():
            mask = (
                (grp["year"] >= row["year"] - 2)
                & (grp["year"] <= row["year"] + 2)
                & (grp["mileage_band"] == row["mileage_band"])
            )
            comp = grp.loc[mask, "price_eur"]
            if len(comp) < min_comp:
                continue
            median = float(np.median(comp.values))
            score = (median - row["price_eur"]) / median
            is_deal = bool(score >= threshold)
            updates.append({
                "id": int(row["id"]),
                "is_deal": is_deal,
                "deal_score": round(score, 4),
            })
            if is_deal:
                deal_ids.add(int(row["id"]))

    # Batch-write scores back (upsert by primary key)
    for u in updates:
        client.table("listings").update(
            {"is_deal": u["is_deal"], "deal_score": u["deal_score"]}
        ).eq("id", u["id"]).execute()

    print(f"Scored {len(updates)} listings, {len(deal_ids)} deals flagged")
    return len(deal_ids)
