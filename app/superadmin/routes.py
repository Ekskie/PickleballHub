from flask import Blueprint, render_template

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

@superadmin_bp.route('/dashboard')
def dashboard():
    return render_template('superadmin/dashboard.html')

@superadmin_bp.route('/facilities')
def facilities():
    return render_template('superadmin/facilities.html')

@superadmin_bp.route('/users')
def users():
    return render_template('superadmin/users.html')

@superadmin_bp.route('/reports')
def reports():
    return render_template('superadmin/reports.html')

@superadmin_bp.route('/settings')
def settings():
    return render_template('superadmin/settings.html')
