import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
)

if not SUPABASE_URL:
    raise Exception("SUPABASE_URL missing in Render Environment Variables")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise Exception("SUPABASE_SERVICE_ROLE_KEY missing in Render Environment Variables")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)