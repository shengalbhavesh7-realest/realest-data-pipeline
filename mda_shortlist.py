import argparse
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def fetch_market_comps(city: str | None, micro_market: str | None) -> pd.DataFrame:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    query = supabase.table("market_comps").select(
        "source_portal, city, micro_market, building_name, config_type, "
        "carpet_area_sqft, asking_price, currency, price_per_sqft"
    )
    if city:
        query = query.ilike("city", city.strip())
    if micro_market:
        query = query.ilike("micro_market", micro_market.strip())

    res = query.execute()
    return pd.DataFrame(res.data or [])


def run_shortlist(
    city: str | None,
    micro_market: str | None,
    config: str | None,
    min_discount: float,
    top_n: int,
    export_path: str | None,
):
    df = fetch_market_comps(city, micro_market)
    if df.empty:
        print("No matching rows found in market_comps.")
        return

    for col in ("carpet_area_sqft", "asking_price", "price_per_sqft"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["price_per_sqft", "asking_price", "carpet_area_sqft"])
    df = df[df["price_per_sqft"] > 0].copy()
    if df.empty:
        print("No valid priced comps available after cleaning.")
        return

    # Group benchmarks: (micro_market, config_type) and fallback (micro_market)
    cfg_stats = (
        df.groupby(["micro_market", "config_type"])["price_per_sqft"]
        .agg(cfg_median="median", cfg_n="count")
        .reset_index()
    )
    mkt_stats = (
        df.groupby(["micro_market"])["price_per_sqft"]
        .agg(mkt_median="median", mkt_n="count")
        .reset_index()
    )

    df = df.merge(cfg_stats, on=["micro_market", "config_type"], how="left")
    df = df.merge(mkt_stats, on=["micro_market"], how="left")

    # Use config median if sample >= 3, else fall back to micro-market median
    use_cfg = df["cfg_n"] >= 3
    df["benchmark_ppsf"] = df["cfg_median"].where(use_cfg, df["mkt_median"])
    df["bench_basis"] = df.apply(
        lambda r: f"Cfg(n={int(r['cfg_n'])})" if r["cfg_n"] >= 3 else f"Mkt(n={int(r['mkt_n'])})",
        axis=1,
    )

    df["delta_pct"] = ((df["price_per_sqft"] - df["benchmark_ppsf"]) / df["benchmark_ppsf"] * 100).round(2)
    df["value_gap"] = ((df["benchmark_ppsf"] - df["price_per_sqft"]) * df["carpet_area_sqft"]).round(0)

    if config:
        df = df[df["config_type"].str.lower() == config.strip().lower()].copy()

    # Filter to discounts >= min_discount (i.e., delta_pct <= -min_discount)
    shortlist = df[df["delta_pct"] <= -abs(min_discount)].sort_values("delta_pct").head(top_n)

    print("=" * 98)
    scope = f"{micro_market or 'ALL MICRO-MARKETS'} | {city or 'ALL CITIES'}"
    if config:
        scope += f" | {config}"
    print(f"MDA STAGE 1 SHORTLIST  |  SCOPE: {scope}  |  TOTAL COMPS SCANNED: {len(df)}")
    print("=" * 98)

    if shortlist.empty:
        print(f"No listings found at >= {min_discount:.1f}% below benchmark median PPSF.")
        return

    header = (
        f"{'Building':26} | {'Cfg':6} | {'Area':>6} | {'Asking Price':>14} | "
        f"{'PPSF':>8} | {'Bench':>8} | {'Delta':>7} | {'Basis':10}"
    )
    print(header)
    print("-" * 98)

    for _, r in shortlist.iterrows():
        cur = str(r.get("currency") or "INR")
        price_str = f"{cur} {r['asking_price']:,.0f}"
        print(
            f"{str(r['building_name'])[:26]:26} | "
            f"{str(r['config_type'])[:6]:6} | "
            f"{r['carpet_area_sqft']:>6.0f} | "
            f"{price_str:>14} | "
            f"{r['price_per_sqft']:>8,.0f} | "
            f"{r['benchmark_ppsf']:>8,.0f} | "
            f"{r['delta_pct']:>+6.1f}% | "
            f"{r['bench_basis']:10}"
        )

    print("-" * 98)
    top_row = shortlist.iloc[0]
    cur = str(top_row.get("currency") or "INR")
    print(
        f"Deepest Outlier: {top_row['building_name']} ({top_row['config_type']}) at "
        f"{top_row['delta_pct']:+.1f}% vs {top_row['bench_basis']} "
        f"(Implied spread: {cur} {top_row['value_gap']:,.0f})"
    )

    if export_path:
        export_cols = [
            "micro_market", "building_name", "config_type", "carpet_area_sqft",
            "currency", "asking_price", "price_per_sqft", "benchmark_ppsf",
            "delta_pct", "value_gap", "bench_basis", "source_portal",
        ]
        shortlist[export_cols].to_csv(export_path, index=False)
        print(f"Exported {len(shortlist)} shortlisted rows to {export_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank below-median PPSF outliers from Supabase market_comps.")
    parser.add_argument("--city", default=None, help="Filter by city (e.g., Mumbai, Dubai)")
    parser.add_argument("--micro-market", default=None, help="Filter by micro-market (e.g., 'Mulund West', 'Ghatkopar East')")
    parser.add_argument("--config", default=None, help="Filter by configuration (e.g., '2 BHK', '3 BHK')")
    parser.add_argument("--min-discount", type=float, default=0.0, help="Minimum %% below median PPSF (default: 0.0)")
    parser.add_argument("--top", type=int, default=10, help="Max outliers to display (default: 10)")
    parser.add_argument("--export", default=None, help="Optional CSV path to export the shortlist")
    args = parser.parse_args()

    run_shortlist(args.city, args.micro_market, args.config, args.min_discount, args.top, args.export)