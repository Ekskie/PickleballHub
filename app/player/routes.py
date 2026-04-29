from flask import Blueprint, render_template
from app.decorators import require_role

player_bp = Blueprint('player', __name__, url_prefix='/player')


@player_bp.route('/dashboard')
@require_role('player')
def dashboard():
    return render_template('player/dashboard.html')

@player_bp.route('/profile')
@require_role('player')
def profile():
    return render_template('player/profile.html')

@player_bp.route('/reservation')
@require_role('player')
def reservation():
    return render_template('player/court_reservation.html')

@player_bp.route('/queue')
@require_role('player')
def queue():
    return render_template('player/queue_monitoring.html')

@player_bp.route('/events')
@require_role('player')
def events():
    return render_template('player/events.html')

@player_bp.route('/community')
@require_role('player')
def community():
    return render_template('player/community.html')

@player_bp.route('/messages')
# @require_role('player')
def messages():
    return render_template('player/messages.html')

@player_bp.route('/notifications')
@require_role('player')
def notifications():
    return render_template('player/notifications.html')

@player_bp.route('/tutorials')
@require_role('player')
def tutorials():
    return render_template('player/tutorials.html')


