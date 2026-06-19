"""
Role-based access control decorators for protecting routes.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, current_app, g
from app.db import get_db

def has_role_permission(user_role, allowed_roles):
    """
    Returns True if user_role is in allowed_roles, or if authorized via logical security checks.
    """
    user_role = (user_role or 'player').strip().lower()
    allowed_roles_lower = [r.strip().lower() for r in allowed_roles]
    
    # 1. Superadmin has global permissions
    if user_role == 'superadmin':
        return True
        
    # 2. Direct role matches are always allowed
    if user_role in allowed_roles_lower:
        return True
        
    # 3. Any logged-in staff/owner can view player views (common monitors, feed, profile checks)
    if 'player' in allowed_roles_lower:
        return True
        
    # 4. Platform Admin Staff can manage and access Club Admin and Facility Staff actions
    if user_role == 'adminstaff' and any(r in ['clubadmin', 'facilitystaff'] for r in allowed_roles_lower):
        return True

    # Note: Club admins, facility staff, and admin staff CANNOT access facility owner financial dashboards
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

            # Get fresh user record from the database to check role and suspension.
            # Prefer the cached profile from flask.g (set by verify_session_integrity)
            # to avoid a redundant DB round-trip.
            db = get_db()
            user_role = session.get('role', 'player')
            cached = getattr(g, 'current_profile', None)
            if cached:
                # Reuse the profile already fetched by before_request
                profile = cached
                if profile.get('is_suspended'):
                    session.clear()
                    flash('Your account has been suspended. Please contact support.', 'error')
                    return redirect(url_for('auth.login'))
                user_role = (profile.get('role') or 'player').strip().lower()
                session['role'] = user_role
            else:
                try:
                    resp = db.table('profiles').select('role, is_suspended').eq('id', user_id).single().execute()
                    if resp.data:
                        profile = resp.data
                        if profile.get('is_suspended'):
                            session.clear()
                            flash('Your account has been suspended. Please contact support.', 'error')
                            return redirect(url_for('auth.login'))
                        user_role = (profile.get('role') or 'player').strip().lower()
                        session['role'] = user_role
                except Exception as e:
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
    """Uploads an avatar file to Supabase storage and returns public URL, or None.
    Uses centralized validation for extension, MIME type, and file size checks.
    """
    from app.upload_utils import validate_and_upload, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE
    
    if not avatar_file or not avatar_file.filename:
        return None
    
    url, error = validate_and_upload(
        db, avatar_file,
        bucket='profile-images',
        prefix='avatar',
        owner_id=user_id,
        allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
        max_size=MAX_IMAGE_SIZE
    )
    if error:
        raise ValueError(error)
    return url
