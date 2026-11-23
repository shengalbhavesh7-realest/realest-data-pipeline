import argparse
import os
import re
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

COLUMN_ALIASES = {
    "building_name": ["building_name", "building", "project name", "project", "society", "tower", "title"],
    "config_type": ["config_type", "configuration", "config", "bhk", "beds", "bedrooms", "type"],
    "carpet_area_sqft": ["carpet_area_sqft", "carpet area", "carpet area(sq.ft)", "area", "size", "sqft", "area_sqft"],
    "asking_price": ["asking_price", "asking price", "asking price(rs.)", "price", "amount"],
}


def find_column(df_cols: list[str], aliases: list[str]) -> str | None:
    lower_map = {c.strip().lower(): c for c in df_cols}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    for alias in aliases:
        for col_lower, orig in lower_map.items():
            if alias in col_lower:
                return orig
    return None


def parse_price(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).strip().lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("aed", "").strip()
    if not s or "call" in s or "request" in s or "onwards" in s and not re.search(r"\d", s):
        return None

    match = re.search(r"(\d+(?:\.\d+)?)\s*(cr|crore|lakh|lac|l|m|million|k)?", s)
    if not match:
        return None

    num = float(match.group(1))
    unit = match.group(2) or ""
    if unit in ("cr", "crore"):
        num *= 10_000_000
    elif unit in ("lakh", "lac", "l"):
        num *= 100_000
    elif unit in ("m", "million"):
        num *= 1_000_000
    elif unit == "k":
        num *= 1_000

    return round(num, 2) if num > 0 else None


def parse_area_sqft(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", s)
    if not match:
        return None

    area = float(match.group(1))
    if "sq.m" in s or "sqm" in s or "m2" in s:
        area *= 10.7639

    return round(area, 2) if area >= 150 else None  # Drop junk/parking-sized rows


def normalize_config(val) -> str:
    if pd.isna(val):
        return "Unknown"
    s = str(val).strip()
    if re.search(r"studio", s, re.IGNORECASE):
        return "Studio"
    bhk = re.search(r"(\d+(?:\.\d+)?)\s*(bhk|br|bed|bedroom)", s, re.IGNORECASE)
    if bhk:
        unit = "BHK" if bhk.group(2).lower() == "bhk" else "BR"
        return f"{bhk.group(1)} {unit}"
    return s[:30]


def make_fingerprint(building: str, config: str, area: float, price: float) -> tuple:
    """Fuzzy fingerprint to catch duplicate broker reposts of the same unit."""
    norm_bldg = re.sub(r"[^a-z0-9]", "", building.lower())
    norm_cfg = config.lower().strip()
    area_bucket = round(float(area) / 10.0) * 10        # 10 sq.ft tolerance
    price_bucket = round(float(price) / 50_000.0) * 50_000  # 50k tolerance
    return (norm_bldg, norm_cfg, area_bucket, price_bucket)


def load_existing_fingerprints(supabase, city: str, micro_market: str) -> set[tuple]:
    existing = set()
    res = (
        supabase.table("market_comps")
        .select("building_name, config_type, carpet_area_sqft, asking_price")
        .eq("city", city)
        .eq("micro_market", micro_market)
        .execute()
    )
    for row in res.data or []:
        if row.get("building_name") and row.get("carpet_area_sqft") and row.get("asking_price"):
            existing.add(
                make_fingerprint(
                    row["building_name"],
                    row.get("config_type") or "Unknown",
                    row["carpet_area_sqft"],
                    row["asking_price"],
                )
            )
    return existing


def ingest_csv(csv_path: str, portal: str, city: str, micro_market: str, currency: str, dry_run: bool):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    raw_count = len(df)

    cols = {k: find_column(list(df.columns), aliases) for k, aliases in COLUMN_ALIASES.items()}
    missing = [k for k in ("building_name", "carpet_area_sqft", "asking_price") if not cols[k]]
    if missing:
        raise ValueError(f"Could not detect required columns {missing} in CSV headers: {list(df.columns)}")

    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    existing_fps = load_existing_fingerprints(supabase, city, micro_market)

    seen_in_csv = set()
    clean_rows = []
    skipped_invalid = 0
    skipped_csv_dup = 0
    skipped_db_dup = 0

    for _, row in df.iterrows():
        building = str(row[cols["building_name"]]).strip()
        if not building or building.lower() == "nan":
            skipped_invalid += 1
            continue

        area = parse_area_sqft(row[cols["carpet_area_sqft"]])
        price = parse_price(row[cols["asking_price"]])
        if not area or not price:
            skipped_invalid += 1
            continue

        config = normalize_config(row[cols["config_type"]]) if cols["config_type"] else "Unknown"
        fp = make_fingerprint(building, config, area, price)

        if fp in seen_in_csv:
            skipped_csv_dup += 1
            continue
        seen_in_csv.add(fp)

        if fp in existing_fps:
            skipped_db_dup += 1
            continue

        ppsf = round(price / area, 2)
        clean_rows.append({
            "source_portal": portal.strip()[:50],
            "city": city.strip(),
            "micro_market": micro_market.strip(),
            "building_name": building,
            "config_type": config,
            "carpet_area_sqft": area,
            "asking_price": price,
            "currency": currency.strip().upper(),
            "price_per_sqft": ppsf,
        })

    print("=" * 64)
    print(f"FILE: {csv_path} | PORTAL: {portal} | MARKET: {micro_market}, {city}")
    print(f"Raw rows:          {raw_count}")
    print(f"Skipped invalid:   {skipped_invalid}")
    print(f"Skipped CSV dups:  {skipped_csv_dup}")
    print(f"Skipped DB dups:   {skipped_db_dup}")
    print(f"Ready to insert:   {len(clean_rows)}")
    print("=" * 64)

    if clean_rows:
        out_df = pd.DataFrame(clean_rows)
        median_ppsf = out_df["price_per_sqft"].median()
        out_df["delta_pct"] = ((out_df["price_per_sqft"] - median_ppsf) / median_ppsf * 100).round(1)
        outliers = out_df.sort_values("price_per_sqft").head(5)

        print(f"Batch Median PPSF: {currency.upper()} {median_ppsf:,.0f}/sqft\n")
        print("Top Lowest-PPSF Candidates (MDA Stage 1 Screen):")
        for _, r in outliers.iterrows():
            print(
                f"  - {r['building_name'][:28]:28} | {r['config_type']:6} | "
                f"{r['carpet_area_sqft']:6.0f} sqft | {currency} {r['asking_price']:>11,.0f} | "
                f"PPSF: {r['price_per_sqft']:>8,.0f} ({r['delta_pct']:+.1f}%)"
            )
        print()

    if dry_run:
        print("[DRY RUN] No rows written to Supabase. Remove --dry-run to upload.")
        return

    if clean_rows:
        for i in range(0, len(clean_rows), 100):
            supabase.table("market_comps").insert(clean_rows[i:i + 100]).execute()
        print(f"Uploaded {len(clean_rows)} new deduplicated rows to market_comps.")
    else:
        print("No new rows to upload.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean, deduplicate, and ingest scraped portal listings into Supabase market_comps.")
    parser.add_argument("csv_path", help="Path to the scraped CSV file")
    parser.add_argument("--portal", required=True, help="Source portal name (e.g., 99acres, MagicBricks, PropertyFinder)")
    parser.add_argument("--city", default="Mumbai", help="City name (default: Mumbai)")
    parser.add_argument("--micro-market", required=True, help="Micro-market name (e.g., 'Ghatkopar East', 'JVC')")
    parser.add_argument("--currency", default="INR", help="Currency code (default: INR)")
    parser.add_argument("--dry-run", action="store_true", help="Preview deduplication and PPSF outliers without writing to Supabase")
    args = parser.parse_args()

    ingest_csv(args.csv_path, args.portal, args.city, args.micro_market, args.currency, args.dry_run)