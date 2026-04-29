from flask import Blueprint, render_template
from app.decorators import require_role

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

@owner_bp.route('/dashboard')
@require_role('owner')
def dashboard():
    return render_template('owner/dashboard.html')

@owner_bp.route('/facilities')
@require_role('owner')
def facilities():
    return render_template('owner/facilities.html')

@owner_bp.route('/courts')
@require_role('owner')
def courts():
    return render_template('owner/courts.html')

@owner_bp.route('/staff')
@require_role('owner')
def staff():
    return render_template('owner/staff.html')

@owner_bp.route('/earnings')
@require_role('owner')
def earnings():
    return render_template('owner/earnings.html')
