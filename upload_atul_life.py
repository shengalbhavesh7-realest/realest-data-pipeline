import os
import re
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EXCEL_FILE = "Atul_Life_Phase_I_Feasibility_Model_V2.xlsx"
RERA_ID = "P51800055779"

def extract_floor(val):
    match = re.search(r"\d+", str(val))
    return int(match.group()) if match else None

def clean_status(val):
    s = str(val).strip().lower()
    if "unsold" in s:
        return "Unsold"
    if "booked" in s:
        return "Booked"
    return "Sold"  # Maps Sold / Landowner / Investor Share safely

# --- 1. INGEST UNIT INVENTORY ---
inv_df = pd.read_excel(EXCEL_FILE, sheet_name="Unit Inventory")
inv_df.columns = inv_df.columns.str.strip()
inv_df = inv_df.dropna(subset=["Unit Number"])

unit_rows = []
for _, row in inv_df.iterrows():
    area_sqm = pd.to_numeric(row.get("Carpet Area(sq.m)"), errors="coerce")
    area_sqft = round(float(area_sqm) * 10.7639, 2) if pd.notna(area_sqm) else None

    unit_rows.append({
        "rera_id": RERA_ID,
        "wing": str(row.get("Wing", "")).strip(),
        "floor_no": extract_floor(row.get("Floor")),
        "unit_no": str(row.get("Unit Number")).split(".")[0].strip(),
        "config_type": str(row.get("Configuration", "")).strip(),
        "carpet_area_sqft": area_sqft,
        "status": clean_status(row.get("Inventory status", "Unsold")),
    })

# Upload in batches of 100
for i in range(0, len(unit_rows), 100):
    supabase.table("unit_inventory").insert(unit_rows[i:i+100]).execute()

print(f"Uploaded {len(unit_rows)} rows to unit_inventory.")

# --- 2. INGEST MARKET RESEARCH ---
mkt_df = pd.read_excel(EXCEL_FILE, sheet_name="Market Research")
mkt_df.columns = mkt_df.columns.str.strip()
mkt_df = mkt_df.dropna(subset=["Project Name", "Asking price(Rs.)"])

comp_rows = []
for _, row in mkt_df.iterrows():
    config = re.sub(r"(\d)\s*BHK", r"\1 BHK", str(row.get("Configuration", "")).strip(), flags=re.IGNORECASE)
    area = pd.to_numeric(row.get("Carpet area(sq.ft)"), errors="coerce")
    price = pd.to_numeric(row.get("Asking price(Rs.)"), errors="coerce")
    ppsf = pd.to_numeric(row.get("Price per sq.ft(Rs.)"), errors="coerce")

    comp_rows.append({
        "source_portal": str(row.get("source", "Market Research")).strip()[:50],
        "city": "Mumbai",
        "micro_market": "Mulund West",
        "building_name": str(row.get("Project Name")).strip(),
        "config_type": config,
        "carpet_area_sqft": round(float(area), 2) if pd.notna(area) else None,
        "asking_price": round(float(price), 2) if pd.notna(price) else None,
        "currency": "INR",
        "price_per_sqft": round(float(ppsf), 2) if pd.notna(ppsf) else None,
    })

if comp_rows:
    supabase.table("market_comps").insert(comp_rows).execute()

print(f"Uploaded {len(comp_rows)} rows to market_comps.")