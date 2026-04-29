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
