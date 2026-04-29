"""
Role-based access control decorators for protecting routes.
"""

from functools import wraps
from flask import session, redirect, url_for, flash


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
    Decorator to protect routes by role.
    Usage: @require_role('superadmin', 'owner')

    Redirects unauthorized users to their respective dashboard with a warning.
    Legacy role strings (e.g. 'administrator') are normalised before the check.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in
            user_id = session.get('user_id')
            if not user_id:
                flash('Please login first.', 'error')
                return redirect(url_for('auth.login'))

            # Get user's role from session, normalise legacy aliases
            user_role = session.get('role', 'player')

            # Check if role is allowed
            if user_role not in allowed_roles:
                flash(f'Access denied. Only {", ".join(allowed_roles)} can access this page.', 'error')
                # Redirect to the user's own dashboard based on their role
                return redirect(_get_dashboard_for_role(user_role))

            # Role is authorized, proceed
            return f(*args, **kwargs)

        return decorated_function
    return decorator
