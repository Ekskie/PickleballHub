from flask import Blueprint, render_template

# Create a new blueprint for public-facing pages
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the public landing page."""
    return render_template('landings/landing.html')

@main_bp.route('/clinics')
def clinics():
    """Render the public clinics and tutorials page."""
    return render_template('landings/clinics.html')

@main_bp.route('/tournaments')
def tournaments():
    """Render the public tournaments page."""
    return render_template('landings/tournaments.html')

@main_bp.route('/community')
def community():
    """Render the public community page."""
    return render_template('landings/community.html')