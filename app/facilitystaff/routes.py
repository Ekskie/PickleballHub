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
