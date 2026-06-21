from flask import Blueprint

clubadmin_bp = Blueprint('clubadmin', __name__, url_prefix='/clubadmin')

# Import sub-modules to register their routes on clubadmin_bp
from app.clubadmin import routes
from app.clubadmin import members
from app.clubadmin import events
from app.clubadmin import tournaments
from app.clubadmin import ledger
