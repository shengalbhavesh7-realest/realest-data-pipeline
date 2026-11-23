import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# 6-Lender Baseline Policy Matrix (Upsert-safe on lender_name)
lenders = [
    {
        "lender_name": "SBI",
        "min_cibil": 700,
        "base_interest_rate_pct": 8.50,
        "max_tenure_years": 30,
        "max_age_at_maturity": 70,
        "foir_tier_1_pct": 50.0,
        "foir_tier_2_pct": 60.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "0.35% of loan amount (Min Rs 2,000, Max Rs 10,000) + GST",
        "confidence_tag": "Baseline",
    },
    {
        "lender_name": "HDFC Bank",
        "min_cibil": 725,
        "base_interest_rate_pct": 8.75,
        "max_tenure_years": 30,
        "max_age_at_maturity": 65,
        "foir_tier_1_pct": 50.0,
        "foir_tier_2_pct": 65.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "Up to 0.50% or Rs 3,000 whichever is higher + GST",
        "confidence_tag": "Baseline",
    },
    {
        "lender_name": "ICICI Bank",
        "min_cibil": 725,
        "base_interest_rate_pct": 8.75,
        "max_tenure_years": 30,
        "max_age_at_maturity": 65,
        "foir_tier_1_pct": 50.0,
        "foir_tier_2_pct": 65.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "0.50% to 2.00% of loan amount + GST",
        "confidence_tag": "Baseline",
    },
    {
        "lender_name": "Axis Bank",
        "min_cibil": 725,
        "base_interest_rate_pct": 8.75,
        "max_tenure_years": 30,
        "max_age_at_maturity": 65,
        "foir_tier_1_pct": 50.0,
        "foir_tier_2_pct": 60.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "Up to 1.00% of loan amount (Min Rs 10,000) + GST",
        "confidence_tag": "Baseline",
    },
    {
        "lender_name": "Bajaj Housing Finance",
        "min_cibil": 725,
        "base_interest_rate_pct": 8.50,
        "max_tenure_years": 32,
        "max_age_at_maturity": 70,
        "foir_tier_1_pct": 55.0,
        "foir_tier_2_pct": 65.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "Up to 0.50% of loan amount + GST",
        "confidence_tag": "Baseline",
    },
    {
        "lender_name": "LIC HFL",
        "min_cibil": 700,
        "base_interest_rate_pct": 8.50,
        "max_tenure_years": 30,
        "max_age_at_maturity": 70,
        "foir_tier_1_pct": 50.0,
        "foir_tier_2_pct": 60.0,
        "ltv_up_to_30l_pct": 90.0,
        "ltv_30l_to_75l_pct": 80.0,
        "ltv_above_75l_pct": 75.0,
        "processing_fee_notes": "Rs 10,000 to Rs 15,000 slab-based + GST",
        "confidence_tag": "Baseline",
    },
]

res = supabase.table("lending_rules").upsert(lenders, on_conflict="lender_name").execute()
print(f"Upserted {len(res.data)} lenders into lending_rules.")