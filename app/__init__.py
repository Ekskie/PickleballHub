import os
import sys
from flask import Flask, session
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")           # anon key
service_role_key = os.environ.get("SERVICE_ROLE_KEY")   # service role (bypasses RLS)

supabase: Client | None = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

# Separate admin client that bypasses Row Level Security
supabase_admin: Client | None = None
if supabase_url and service_role_key:
    supabase_admin = create_client(supabase_url, service_role_key)


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "super_secret_fallback")
   
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.player.routes import player_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)

    @app.context_processor
    def inject_current_user():
        """Inject logged-in user info into every template as `current_user`."""
        user_id = session.get('user_id')

        # Build the guest/fallback user
        guest = {
            'first_name': 'Guest',
            'last_name':  '',
            'full_name':  'Guest',
            'initials':   'G',
            'email':      '',
            'phone':      '',
            'role':       'Player',
            'id':         None,
            'is_logged_in': False,
        }

        if not user_id:
            return dict(current_user=guest)

        # --- 1. Try Supabase (admin client, bypasses RLS) ---
        client = supabase_admin or supabase
        if client:
            try:
                resp = client.table('profiles').select(
                    'first_name, last_name, phone, role'
                ).eq('id', user_id).single().execute()

                if resp.data:
                    d        = resp.data
                    first    = (d.get('first_name') or '').strip() or 'Player'
                    last     = (d.get('last_name')  or '').strip()
                    full     = f"{first} {last}".strip()
                    initials = (first[0] + (last[0] if last else '')).upper()
                    role     = (d.get('role') or 'player').strip().lower()

                    return dict(current_user={
                        'first_name':   first,
                        'last_name':    last,
                        'full_name':    full,
                        'initials':     initials,
                        'email':        (d.get('email') or session.get('email', '')),
                        'phone':        (d.get('phone') or ''),
                        'role':         role.capitalize(),
                        'role_raw':     role,
                        'id':           user_id,
                        'is_logged_in': True,
                    })
            except Exception as exc:
                print(f"[context_processor] Supabase error: {exc}", file=sys.stderr)

        # --- 2. Fall back to whatever was stored in session at login ---
        first    = session.get('first_name', 'Player')
        last     = session.get('last_name',  '')
        full     = f"{first} {last}".strip()
        initials = (first[0] + (last[0] if last else '')).upper()
        role     = session.get('role', 'player').lower()

        return dict(current_user={
            'first_name':   first,
            'last_name':    last,
            'full_name':    full,
            'initials':     initials,
            'email':        session.get('email', ''),
            'phone':        session.get('phone', ''),
            'role':         role.capitalize(),
            'role_raw':     role,
            'id':           user_id,
            'is_logged_in': True,
        })

    return app
