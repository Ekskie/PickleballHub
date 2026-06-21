from flask import Blueprint

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

# Import sub-modules to register their routes on owner_bp
from app.owner import routes
from app.owner import facilities
from app.owner import courts
from app.owner import events
from app.owner import staff
from app.owner import ledger
from app.owner import queue
