from flask import Blueprint, render_template

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

@owner_bp.route('/dashboard')
def dashboard():
    return render_template('owner/dashboard.html')

@owner_bp.route('/facilities')
def facilities():
    return render_template('owner/facilities.html')

@owner_bp.route('/courts')
def courts():
    return render_template('owner/courts.html')

@owner_bp.route('/staff')
def staff():
    return render_template('owner/staff.html')

@owner_bp.route('/earnings')
def earnings():
    return render_template('owner/earnings.html')
