import time
import os
import sys
import httpx
from supabase import create_client, ClientOptions

_cached_settings = None
_settings_cache_time = 0.0
SETTINGS_CACHE_TTL = 30.0  # cache settings for 30 seconds

def get_db_client():
    """Returns a client bypassing RLS if service role key is available."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
    if not url or not key:
        return None
    try:
        http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
        options = ClientOptions(httpx_client=http_client)
        return create_client(url, key, options=options)
    except Exception as e:
        print(f"[get_db_client] Error initializing supabase client: {e}", file=sys.stderr)
        return None

def load_platform_settings(force_refresh=False):
    global _cached_settings, _settings_cache_time
    now = time.time()
    if force_refresh or _cached_settings is None or (now - _settings_cache_time) > SETTINGS_CACHE_TTL:
        # Default fallback values
        settings = {
            'platform_name': 'PickleballHub',
            'support_email': 'support@pickleballhub.com',
            'maintenance_mode': False,
            'require_2fa': False,
            'seo_meta_title': 'PickleballHub - Centralized Court & Tournament Management',
            'seo_meta_description': 'Discover and book pickleball courts, participate in tournaments, connect with players of your skill level, and manage your pickleball queue.',
            'seo_meta_keywords': 'pickleball, court booking, tournament brackets, matchmaker, queue monitoring, sports club management',
            'seo_og_image': '',
            'google_analytics_id': '',
            'facebook_pixel_id': '',
            'custom_head_scripts': '',
        }
        db = get_db_client()
        if db:
            try:
                resp = db.table('platform_settings').select('*').execute()
                for row in (resp.data or []):
                    k, v = row.get('key'), row.get('value')
                    if k in ('maintenance_mode', 'require_2fa'):
                        settings[k] = (v == '1')
                    elif k in settings:
                        settings[k] = v
            except Exception as e:
                print(f"[load_platform_settings] Error reading settings from DB: {e}", file=sys.stderr)
        _cached_settings = settings
        _settings_cache_time = now
    return _cached_settings

def clear_settings_cache():
    global _cached_settings, _settings_cache_time
    _cached_settings = None
    _settings_cache_time = 0.0
