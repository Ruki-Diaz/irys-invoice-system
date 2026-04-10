import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TARGET_USER_ID = "eea809b7-53d5-43ee-8d73-0d570403001b"
NEW_PASSWORD = "12345678"

def reset_password():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in your .env file.")
        return

    try:
        # Initialize Supabase admin client using the Service Role Key
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        
        # Update the existing user using the Admin Auth API
        response = supabase_admin.auth.admin.update_user_by_id(
            TARGET_USER_ID,
            {"password": 123456}
        )
        
        print(f"Success: Password for user '{TARGET_USER_ID}' has been updated.")
        
    except Exception as e:
        print(f"Error resetting password: {e}")

if __name__ == "__main__":
    reset_password()
