from flask import Blueprint, render_template

# Create a new blueprint for public-facing pages
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the public landing page."""
    return render_template('landing.html')