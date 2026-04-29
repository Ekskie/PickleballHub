from flask import Blueprint, render_template
from app.decorators import require_role

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

@superadmin_bp.route('/dashboard')
@require_role('superadmin')
def dashboard():
    return render_template('superadmin/dashboard.html')

@superadmin_bp.route('/facilities')
@require_role('superadmin')
def facilities():
    return render_template('superadmin/facilities.html')

@superadmin_bp.route('/users')
@require_role('superadmin')
def users():
    return render_template('superadmin/users.html')

@superadmin_bp.route('/reports')
@require_role('superadmin')
def reports():
    return render_template('superadmin/reports.html')

@superadmin_bp.route('/settings')
@require_role('superadmin')
def settings():
    return render_template('superadmin/settings.html')

@superadmin_bp.route('/profile')
@require_role('superadmin')
def profile():
    return render_template('superadmin/profile.html')

@superadmin_bp.route('/notifications')
@require_role('superadmin')
def notifications():
    return render_template('superadmin/notifications.html')

@superadmin_bp.route('/messages')
@require_role('superadmin')
def messages():
    return render_template('superadmin/messages.html')

@superadmin_bp.route('/community')
@require_role('superadmin')
def community():
    return render_template('superadmin/community.html')

@superadmin_bp.route('/tutorials')
@require_role('superadmin')
def tutorials():
    return render_template('superadmin/tutorials.html')

