from flask import Blueprint, render_template

player_bp = Blueprint('player', __name__, url_prefix='/player')

@player_bp.route('/')
def dashboard():
    return render_template('player/dashboard.html')
