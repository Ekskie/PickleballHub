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

@adminstaff_bp.route('/profile')
@require_role('adminstaff')
def profile():
    return render_template('adminstaff/profile.html')

@adminstaff_bp.route('/notifications')
@require_role('adminstaff')
def notifications():
    return render_template('adminstaff/notifications.html')

@adminstaff_bp.route('/messages')
@require_role('adminstaff')
def messages():
    return render_template('adminstaff/messages.html')

@adminstaff_bp.route('/community')
@require_role('adminstaff')
def community():
    return render_template('adminstaff/community.html')

@adminstaff_bp.route('/tutorials')
@require_role('adminstaff')
def tutorials():
    return render_template('adminstaff/tutorials.html')

