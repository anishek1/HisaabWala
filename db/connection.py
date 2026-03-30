"""
HisaabWala - Supabase Client
Owner: Dev 3
"""

from supabase import create_client, Client

from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
