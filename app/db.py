"""
Thread-safe, request-scoped database helper for Supabase.
Provides separation between anon client (respecting RLS) and admin client (bypassing RLS).
"""

import os
from flask import g, session, current_app
import httpx
from supabase import create_client, ClientOptions, Client

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

def log_audit_action(action: str, target: str, details: dict = None):
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

