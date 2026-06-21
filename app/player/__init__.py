from flask import Blueprint

player_bp = Blueprint('player', __name__, url_prefix='/player')

# Import all sub-modules to register their routes on player_bp
from app.player import routes
from app.player import reservations
from app.player import queue_routes
from app.player import events_routes
from app.player import social_routes
from app.player import clubs_routes
from app.player import matchmaker_routes
from app.player import leaderboard_routes
