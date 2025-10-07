#!/usr/bin/env python3
"""
Supabase client configuration for the FastAPI backend.
"""

import os
from typing import Optional
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# Get Supabase credentials from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

def get_supabase_client(use_service_role: bool = False) -> Optional[Client]:
    """
    Create and return a Supabase client.
    
    Args:
        use_service_role: If True, use the service role key (bypasses RLS).
                         If False, use the anon key (respects RLS).
    
    Returns:
        Supabase client instance or None if credentials are missing.
    """
    if not SUPABASE_URL:
        print("⚠️  SUPABASE_URL not found in environment variables")
        return None
    
    key = SUPABASE_SERVICE_ROLE_KEY if use_service_role else SUPABASE_ANON_KEY
    if not key:
        key_type = "SUPABASE_SERVICE_ROLE_KEY" if use_service_role else "SUPABASE_ANON_KEY"
        print(f"⚠️  {key_type} not found in environment variables")
        return None
    
    try:
        client_options = ClientOptions(
            auto_refresh_token=False,  # Backend doesn't need auto refresh
            persist_session=False     # Backend doesn't persist sessions
        )
        
        client = create_client(SUPABASE_URL, key, options=client_options)
        return client
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        return None

# Create global client instances
supabase_service = get_supabase_client(use_service_role=True)
supabase_anon = get_supabase_client(use_service_role=False)

def verify_supabase_connection() -> bool:
    """
    Verify that we can connect to Supabase.
    
    Returns:
        True if connection is successful, False otherwise.
    """
    if not supabase_anon:
        return False
    
    try:
        # Try a simple query to verify connection
        result = supabase_anon.table('profiles').select('id').limit(1).execute()
        return True
    except Exception as e:
        print(f"❌ Supabase connection verification failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Supabase connection...")
    if verify_supabase_connection():
        print("✅ Supabase connection successful!")
    else:
        print("❌ Supabase connection failed!")