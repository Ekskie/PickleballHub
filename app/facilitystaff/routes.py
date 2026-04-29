from flask import Blueprint, render_template
from app.decorators import require_role

facilitystaff_bp = Blueprint('facilitystaff', __name__, url_prefix='/facilitystaff')

@facilitystaff_bp.route('/dashboard')
@require_role('facilitystaff')
def dashboard():
    return render_template('facilitystaff/dashboard.html')

@facilitystaff_bp.route('/queue')
@require_role('facilitystaff')
def queue():
    return render_template('facilitystaff/queue.html')

@facilitystaff_bp.route('/schedule')
@require_role('facilitystaff')
def schedule():
    return render_template('facilitystaff/schedule.html')

@facilitystaff_bp.route('/walkin')
@require_role('facilitystaff')
def walkin():
    return render_template('facilitystaff/walkin.html')

@facilitystaff_bp.route('/profile')
@require_role('facilitystaff')
def profile():
    return render_template('facilitystaff/profile.html')

@facilitystaff_bp.route('/notifications')
@require_role('facilitystaff')
def notifications():
    return render_template('facilitystaff/notifications.html')

@facilitystaff_bp.route('/messages')
@require_role('facilitystaff')
def messages():
    return render_template('facilitystaff/messages.html')

@facilitystaff_bp.route('/community')
@require_role('facilitystaff')
def community():
    return render_template('facilitystaff/community.html')
