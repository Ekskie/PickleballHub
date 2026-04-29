from flask import Blueprint, render_template
from app.decorators import require_role

adminstaff_bp = Blueprint('adminstaff', __name__, url_prefix='/adminstaff')

@adminstaff_bp.route('/dashboard')
@require_role('adminstaff')
def dashboard():
    return render_template('adminstaff/dashboard.html')

@adminstaff_bp.route('/support')
@require_role('adminstaff')
def support():
    return render_template('adminstaff/support.html')

@adminstaff_bp.route('/verifications')
@require_role('adminstaff')
def verifications():
    return render_template('adminstaff/verifications.html')

@adminstaff_bp.route('/disputes')
@require_role('adminstaff')
def disputes():
    return render_template('adminstaff/disputes.html')
