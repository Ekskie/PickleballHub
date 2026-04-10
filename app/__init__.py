import os
from flask import Flask
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# We can store the supabase client globally if we want, or attach it to app config
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

supabase: Client | None = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "super_secret_fallback")

    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.player.routes import player_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    
    return app
