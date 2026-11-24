import argparse
import os
import subprocess
import sys
import pandas as pd
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ACTOR_ID = "memo23/magicbricks-property-scraper"


def normalize_magicbricks_items(items: list[dict]) -> pd.DataFrame:
    rows = []
    for item in items:
        if item.get("rowType") and item.get("rowType") != "property":
            continue

        listing_id = str(item.get("listingId") or item.get("propertyId") or "").strip()
        project = (item.get("project") or "").strip()
        address = (item.get("address") or item.get("locality") or "Unknown").strip()

        # Keep unnamed listings distinct so they don't collide during deduplication
        if not project:
            project = f"Unlisted ({address}) #{listing_id}" if listing_id else f"Unlisted ({address})"

        bedrooms = item.get("bedrooms")
        config = f"{int(bedrooms)} BHK" if bedrooms is not None else ""

        carpet_area = item.get("carpetArea")
        price = item.get("price")

        rows.append(
            {
                "Project Name": project,
                "Configuration": config,
                "Carpet Area": carpet_area if carpet_area else "",
                "Asking Price": price if price else "",
                "Locality": item.get("locality") or "",
                "Possession": item.get("possessionStatus") or "",
                "Floor": item.get("floor") or "",
                "Lister Type": item.get("listerType") or "",
                "Listing ID": listing_id,
                "Property URL": item.get("propertyUrl") or "",
            }
        )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Pull MagicBricks listings from Apify and feed ingest_portal_listings.py")
    parser.add_argument("--run-id", default=None, help="Existing Apify Run ID (pulls dataset for $0 extra cost)")
    parser.add_argument("--url", default=None, help="MagicBricks search URL for a fresh scrape")
    parser.add_argument("--max-items", type=int, default=50, help="Max properties for a fresh scrape (default: 50)")
    parser.add_argument("--city", default="Mumbai", help="City name (default: Mumbai)")
    parser.add_argument("--micro-market", required=True, help="Micro-market tag (e.g., 'Ghatkopar East')")
    parser.add_argument("--out", default="apify_magicbricks.csv", help="Output CSV path")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to ingest_portal_listings.py")
    args = parser.parse_args()

    token = os.getenv("APIFY_TOKEN")
    if not token:
        sys.exit("Error: APIFY_TOKEN not found in .env")

    client = ApifyClient(token)

    if args.run_id:
        print(f"Fetching dataset from existing Apify run: {args.run_id} ...")
        run = client.run(args.run_id).get()
        dataset_id = run.default_dataset_id
    elif args.url:
        print(f"Starting fresh scrape via {DEFAULT_ACTOR_ID} (max {args.max_items} items)...")
        run_input = {
            "startUrls": [args.url],
            "maxItems": args.max_items,
            "maxItemsPerSearch": args.max_items,
            "scrapeDetails": False,
            "agentMode": False,
            "transactionType": "sale",
        }
        run = client.actor(DEFAULT_ACTOR_ID).call(run_input=run_input)
        dataset_id = run.default_dataset_id
    else:
        sys.exit("Error: Provide either --run-id <RUN_ID> or --url <MAGICBRICKS_URL>")

    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        sys.exit("No items returned from Apify dataset.")

    df = normalize_magicbricks_items(items)
    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} raw MagicBricks rows to {args.out}\n")

    cmd = [
        sys.executable,
        "ingest_portal_listings.py",
        args.out,
        "--portal",
        "magicbricks",
        "--city",
        args.city,
        "--micro-market",
        args.micro_market,
        "--currency",
        "INR",
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()