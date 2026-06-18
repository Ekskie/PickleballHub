"""
Thread-safe, request-scoped database helper for Supabase.
Provides separation between anon client (respecting RLS) and admin client (bypassing RLS).
"""

import os
from flask import g, session, current_app
import httpx
from supabase import create_client, ClientOptions, Client

def is_jwt_expired(token: str) -> bool:
    """Decodes a JWT payload locally to check if it's expired or close to it (5-minute window)."""
    import base64
    import json
    import time
    if not token:
        return True
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return True
        payload_b64 = parts[1]
        # Base64 padding correction
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8'))
        exp = payload.get('exp')
        if exp:
            # Refresh if it expires in less than 5 minutes (300 seconds)
            return time.time() > (exp - 300)
        return False
    except Exception:
        return True

def get_db() -> Client:
    """
    Get a thread-safe, request-scoped Supabase client.
    Authenticated with user access token if logged in.
    """
    if 'db_client' not in g:
        url = os.environ.get('SUPABASE_URL')
        # Standard client runs with the public/anon key to respect Row Level Security (RLS)
        key = os.environ.get('SUPABASE_KEY')
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
        
        # Use httpx with proper timeout and limits
        http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
        options = ClientOptions(httpx_client=http_client)
        client = create_client(url, key, options=options)
        
        # If user has an active session, set their session so database queries respect RLS
        access_token = session.get('access_token')
        refresh_token = session.get('refresh_token', '')
        if access_token:
            # Check for token expiry and auto-refresh dynamically
            if is_jwt_expired(access_token) and refresh_token:
                try:
                    refresh_resp = client.auth.refresh_session(refresh_token)
                    if refresh_resp and refresh_resp.session:
                        new_access = refresh_resp.session.access_token
                        new_refresh = refresh_resp.session.refresh_token
                        # Update Flask session dynamically
                        session['access_token'] = new_access
                        session['refresh_token'] = new_refresh
                        access_token = new_access
                        refresh_token = new_refresh
                except Exception as refresh_err:
                    current_app.logger.error(f"[get_db] Supabase JWT session refresh failed: {refresh_err}")

            try:
                client.auth.set_session(access_token, refresh_token)
            except Exception as e:
                # Log but don't crash standard requests; fallback to anon access if session restore fails
                current_app.logger.warning(f"Failed to set user session context in get_db: {e}")
                
        g.db_client = client
    return g.db_client

def get_admin_db() -> Client:
    """
    Get an admin/service-role scoped Supabase client that bypasses Row Level Security.
    Used ONLY for administrative tasks.
    """
    if 'admin_db_client' not in g:
        url = os.environ.get('SUPABASE_URL')
        # Admin client runs with the service role key to bypass RLS
        key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SERVICE_ROLE_KEY must be set in environment variables.")
            
        http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
        options = ClientOptions(httpx_client=http_client)
        g.admin_db_client = create_client(url, key, options=options)
        
    return g.admin_db_client

def log_audit_action(action: str, target: str, details: dict = None, raise_on_error: bool = False):
    """
    Log administrative or critical actions to the database for audit trail.
    Safe to call with or without active Flask request context.
    """
    from flask import has_request_context, request
    db = get_admin_db()
    
    actor_id = session.get('user_id') if has_request_context() else None
    ip_address = request.remote_addr if has_request_context() else None
    
    try:
        db.table('audit_logs').insert({
            'actor_id': actor_id,
            'action': action,
            'target_resource': target,
            'details': details or {},
            'ip_address': ip_address
        }).execute()
    except Exception as e:
        current_app.logger.error(f"[log_audit_action] Failed to write audit log: {e}")
        if raise_on_error:
            raise RuntimeError(f"Audit log write failed. Action cancelled for security compliance. Error: {e}")


