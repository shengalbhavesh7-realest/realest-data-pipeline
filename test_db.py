import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

response = supabase.table("projects_master").select("*").execute()
print("Connected! Rows found:", len(response.data))
print(response.data)
