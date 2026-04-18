from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for

player_bp = Blueprint('player', __name__, url_prefix='/player')


def login_required(f):
    """Redirect to /auth if the user has no active session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@player_bp.route('/')
@login_required
def dashboard():
    return render_template('player/dashboard.html')

@player_bp.route('/profile')
@login_required
def profile():
    return render_template('player/profile.html')

@player_bp.route('/reservation')
@login_required
def reservation():
    return render_template('player/court_reservation.html')

@player_bp.route('/queue')
@login_required
def queue():
    return render_template('player/queue_monitoring.html')

@player_bp.route('/events')
@login_required
def events():
    return render_template('player/events.html')

@player_bp.route('/community')
@login_required
def community():
    return render_template('player/community.html')

@player_bp.route('/messages')
@login_required
def messages():
    return render_template('player/messages.html')

@player_bp.route('/notifications')
@login_required
def notifications():
    return render_template('player/notifications.html')

