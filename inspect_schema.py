
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
sb = create_client(url, key)

try:
    # Try to select one row to see keys
    res = sb.table("factor_returns").select("*").limit(1).execute()
    if res.data:
        print("Columns:", res.data[0].keys())
    else:
        print("Table exists but is empty. Cannot infer columns from data.")
        # Try inserting a dummy to see error or success? No, that's risky.
except Exception as e:
    print("Error:", e)
