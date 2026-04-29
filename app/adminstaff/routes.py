from flask import Blueprint, render_template

adminstaff_bp = Blueprint('adminstaff', __name__, url_prefix='/adminstaff')

@adminstaff_bp.route('/dashboard')
def dashboard():
    return render_template('adminstaff/dashboard.html')

@adminstaff_bp.route('/support')
def support():
    return render_template('adminstaff/support.html')

@adminstaff_bp.route('/verifications')
def verifications():
    return render_template('adminstaff/verifications.html')

@adminstaff_bp.route('/disputes')
def disputes():
    return render_template('adminstaff/disputes.html')
