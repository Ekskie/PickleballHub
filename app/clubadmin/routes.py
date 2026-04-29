from flask import Blueprint, render_template

clubadmin_bp = Blueprint('clubadmin', __name__, url_prefix='/clubadmin')

@clubadmin_bp.route('/dashboard')
def dashboard():
    return render_template('clubadmin/dashboard.html')

@clubadmin_bp.route('/members')
def members():
    return render_template('clubadmin/members.html')

@clubadmin_bp.route('/events')
def events():
    return render_template('clubadmin/events.html')

@clubadmin_bp.route('/tournaments')
def tournaments():
    return render_template('clubadmin/tournaments.html')

@clubadmin_bp.route('/leaderboard')
def leaderboard():
    return render_template('clubadmin/leaderboard.html')
