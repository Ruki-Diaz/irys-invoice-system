import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
TARGET_USER_ID = "eea809b7-53d5-43ee-8d73-0d570403001b"

def reset_password(new_password=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
        return

    password_to_set = new_password or (sys.argv[1] if len(sys.argv) > 1 else "dias123")

    try:
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = supabase_admin.auth.admin.update_user_by_id(
            TARGET_USER_ID,
            {"password": password_to_set}
        )
        print(f"Success: Password for '{response.user.email}' has been updated to: {password_to_set}")
    except Exception as e:
        print(f"Error resetting password: {e}")

if __name__ == "__main__":
    reset_password()

