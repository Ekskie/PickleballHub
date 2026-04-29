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
    from app.superadmin.routes import superadmin_bp
    from app.adminstaff.routes import adminstaff_bp
    from app.owner.routes import owner_bp
    from app.facilitystaff.routes import facilitystaff_bp
    from app.clubadmin.routes import clubadmin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(adminstaff_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(facilitystaff_bp)
    app.register_blueprint(clubadmin_bp)

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
            return dict(
                current_user=guest,
                supabase_url=supabase_url,
                supabase_anon_key=supabase_key
            )

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
                        'access_token': session.get('access_token', ''),
                    }, supabase_url=supabase_url, supabase_anon_key=supabase_key)
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
            'access_token': session.get('access_token', ''),
        }, supabase_url=supabase_url, supabase_anon_key=supabase_key)

    # ── Template Filters ──────────────────────────────────────────────────────
    @app.template_filter('community_timeago')
    def community_timeago(iso_str):
        """Convert an ISO timestamp to a human-readable relative time string."""
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            diff = now - dt
            seconds = int(diff.total_seconds())
            if seconds < 60:
                return 'just now'
            minutes = seconds // 60
            if minutes < 60:
                return f'{minutes}m ago'
            hours = minutes // 60
            if hours < 24:
                return f'{hours}h ago'
            days = hours // 24
            if days < 7:
                return f'{days}d ago'
            return dt.strftime('%b ') + str(dt.day)
        except Exception:
            return ''

    return app

