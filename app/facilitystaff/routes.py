from flask import Blueprint, render_template

facilitystaff_bp = Blueprint('facilitystaff', __name__, url_prefix='/facilitystaff')

@facilitystaff_bp.route('/dashboard')
def dashboard():
    return render_template('facilitystaff/dashboard.html')

@facilitystaff_bp.route('/queue')
def queue():
    return render_template('facilitystaff/queue.html')

@facilitystaff_bp.route('/schedule')
def schedule():
    return render_template('facilitystaff/schedule.html')

@facilitystaff_bp.route('/walkin')
def walkin():
    return render_template('facilitystaff/walkin.html')
