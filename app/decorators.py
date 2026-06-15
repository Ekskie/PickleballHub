"""
Role-based access control decorators for protecting routes.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, current_app
from app.db import get_db

ROLE_HIERARCHY = {
    'player': 1,
    'facilitystaff': 2,
    'owner': 3,
    'clubadmin': 4,
    'adminstaff': 5,
    'superadmin': 6
}

def has_role_permission(user_role, allowed_roles):
    """
    Returns True if user_role is in allowed_roles, or if the user's role
    has a higher priority in the hierarchy than any of the allowed_roles.
    """
    user_role = (user_role or 'player').strip().lower()
    allowed_roles_lower = [r.strip().lower() for r in allowed_roles]
    
    # Direct match is always allowed
    if user_role in allowed_roles_lower:
        return True
        
    user_priority = ROLE_HIERARCHY.get(user_role, 1)
    
    # If the user has a higher priority than at least one of the allowed roles, permit them.
    for allowed in allowed_roles_lower:
        allowed_priority = ROLE_HIERARCHY.get(allowed, 1)
        if user_priority >= allowed_priority:
            return True
            
    return False


def _get_dashboard_for_role(role):
    """Return the dashboard URL for a given role."""
    role = (role or 'player').strip().lower()
    role_map = {
        'player':        'player.dashboard',
        'superadmin':    'superadmin.dashboard',
        'owner':         'owner.dashboard',
        'clubadmin':     'clubadmin.dashboard',
        'facilitystaff': 'facilitystaff.dashboard',
        'adminstaff':    'adminstaff.dashboard',
    }
    # If the role is unknown, go to login to avoid infinite redirect loops
    endpoint = role_map.get(role)
    if endpoint:
        return url_for(endpoint)
    return url_for('auth.login')


def require_role(*allowed_roles):
    """
    Decorator to protect routes by role, supporting role hierarchies.
    Usage: @require_role('superadmin', 'owner')

    Redirects unauthorized users to their respective dashboard with a warning.
    Stale roles or suspended accounts are checked dynamically against the DB.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in
            user_id = session.get('user_id')
            if not user_id:
                flash('Please login first.', 'error')
                return redirect(url_for('auth.login'))

            # Get fresh user record from the database to check role and suspension
            db = get_db()
            user_role = session.get('role', 'player')
            try:
                resp = db.table('profiles').select('role, is_suspended').eq('id', user_id).single().execute()
                if resp.data:
                    profile = resp.data
                    
                    # 1. Force logout if suspended
                    if profile.get('is_suspended'):
                        session.clear()
                        flash('Your account has been suspended. Please contact support.', 'error')
                        return redirect(url_for('auth.login'))
                        
                    # 2. Sync role dynamically to session
                    user_role = (profile.get('role') or 'player').strip().lower()
                    session['role'] = user_role
            except Exception as e:
                # Log the issue but fall back to cached session key to fail-safe if DB is temporarily down
                current_app.logger.error(f"[require_role] Integrity check failed: {e}")

            # Check if role is allowed (direct match or hierarchy match)
            if not has_role_permission(user_role, allowed_roles):
                flash(f'Access denied. Only {", ".join(allowed_roles)} (or higher) can access this page.', 'error')
                return redirect(_get_dashboard_for_role(user_role))

            # Role is authorized, proceed
            return f(*args, **kwargs)

        return decorated_function
    return decorator



def upload_avatar(db, user_id, avatar_file):
    """Uploads an avatar file to Supabase storage and returns public URL, or None."""
    if avatar_file and avatar_file.filename:
        try:
            import time
            ext = avatar_file.filename.split('.')[-1]
            filename = f"avatar_{user_id}_{int(time.time())}.{ext}"
            db.storage.from_('profile-images').upload(
                file=avatar_file.read(),
                path=filename,
                file_options={"content-type": avatar_file.content_type}
            )
            return db.storage.from_('profile-images').get_public_url(filename)
        except Exception as e:
            print(f"[upload_avatar] Failed: {e}")
            raise e
    return None
