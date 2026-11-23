\# realest-data-pipeline



Centralized PostgreSQL data infrastructure and Python ETL pipeline for \*\*REALEST\*\*, managing residential project feasibility, unit-level inventory, market comparables, and home-loan lending policy matrices.



\## Architecture



\- \*\*Database:\*\* Supabase (PostgreSQL) hosted in `ap-southeast-1` (Singapore) with Row Level Security (RLS) enabled across all tables.

\- \*\*Ingestion Layer:\*\* Python (`pandas`, `openpyxl`, `supabase-py`, `python-dotenv`) automating schema normalization, unit conversions (`sq.m` to `sq.ft`), and batched API writes.



\## Database Schema



| Table | Purpose | Primary Contents |

| :--- | :--- | :--- |

| `projects\_master` | Project-level feasibility metadata | RERA ID, developer, land area, sanctioned BUA, cost estimates, completion dates |

| `unit\_inventory` | Granular apartment-level inventory | Wing, floor, unit number, configuration, carpet area (sq.ft), sales status |

| `market\_comps` | Micro-market pricing benchmarks | Portal source, micro-market, building name, configuration, asking price, PPSF |

| `lending\_rules` | Home-loan underwriting parameters | Lender name, min CIBIL, base rate, max tenure/age, FOIR tiers, LTV slabs, fees |



\## Repository Structure



\- `test\_db.py` — Verifies authenticated HTTPS connectivity to Supabase and queries `projects\_master`.

\- `upload\_atul\_life.py` — Extracts, cleans, converts, and batch-inserts unit inventory (632 units) and market comparables (12 comps) from Excel feasibility workbooks.

\- `upload\_lending\_rules.py` — Upserts the 6-lender baseline policy matrix (SBI, HDFC Bank, ICICI Bank, Axis Bank, Bajaj Housing Finance, LIC HFL) into `lending\_rules`.

\- `requirements.txt` — Python package dependencies.



\## Setup \& Execution



1\. \*\*Install dependencies:\*\*

&#x20;  ```bash

&#x20;  pip install -r requirements.txt

