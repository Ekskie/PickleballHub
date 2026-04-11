from flask import Blueprint, render_template

player_bp = Blueprint('player', __name__, url_prefix='/player')

@player_bp.route('/')
def dashboard():
    return render_template('player/dashboard.html')

@player_bp.route('/profile')
def profile():
    return render_template('player/profile.html')

@player_bp.route('/reservation')
def reservation():
    return render_template('player/court_reservation.html')

@player_bp.route('/queue')
def queue():
    return render_template('player/queue_monitoring.html')

@player_bp.route('/events')
def events():
    return render_template('player/events.html')

@player_bp.route('/community')
def community():
    return render_template('player/community.html')

@player_bp.route('/messages')
def messages():
    return render_template('player/messages.html')

@player_bp.route('/notifications')
def notifications():
    return render_template('player/notifications.html')
