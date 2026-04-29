from flask import Blueprint, render_template
from app.decorators import require_role

clubadmin_bp = Blueprint('clubadmin', __name__, url_prefix='/clubadmin')

@clubadmin_bp.route('/dashboard')
@require_role('clubadmin')
def dashboard():
    return render_template('clubadmin/dashboard.html')

@clubadmin_bp.route('/members')
@require_role('clubadmin')
def members():
    return render_template('clubadmin/members.html')

@clubadmin_bp.route('/events')
@require_role('clubadmin')
def events():
    return render_template('clubadmin/events.html')

@clubadmin_bp.route('/tournaments')
@require_role('clubadmin')
def tournaments():
    return render_template('clubadmin/tournaments.html')

@clubadmin_bp.route('/leaderboard')
@require_role('clubadmin')
def leaderboard():
    return render_template('clubadmin/leaderboard.html')
