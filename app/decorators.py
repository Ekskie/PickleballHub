"""
Role-based access control decorators for protecting routes.
"""

from functools import wraps
from flask import session, redirect, url_for, flash


def require_role(*allowed_roles):
    """
    Decorator to protect routes by role.
    Usage: @require_role('superadmin', 'owner')
    
    Redirects unauthorized users to player dashboard with a warning.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in
            user_id = session.get('user_id')
            if not user_id:
                flash('Please login first.', 'error')
                return redirect(url_for('auth.login'))
            
            # Get user's role from session
            user_role = session.get('role', 'player')
            
            # Check if role is allowed
            if user_role not in allowed_roles:
                flash(f'Access denied. Only {", ".join(allowed_roles)} can access this page.', 'error')
                return redirect(url_for('player.dashboard'))
            
            # Role is authorized, proceed
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
