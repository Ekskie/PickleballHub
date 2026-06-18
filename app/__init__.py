import os
import sys
from flask import Flask, session, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from supabase import create_client, Client
from flask_wtf.csrf import CSRFProtect

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

csrf = CSRFProtect()



def create_app():
    app = Flask(__name__)
    
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if os.environ.get("FLASK_ENV") == "production" or os.environ.get("VERCEL") == "1":
            raise RuntimeError("CRITICAL CONFIGURATION ERROR: SECRET_KEY environment variable is required in production.")
        app.secret_key = "super_secret_fallback_development_only"
    else:
        app.secret_key = secret_key
        
    csrf.init_app(app)
   
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.player.routes import player_bp
    from app.superadmin.routes import superadmin_bp
    from app.adminstaff.routes import adminstaff_bp
    from app.owner.routes import owner_bp
    from app.facilitystaff.routes import facilitystaff_bp
    from app.clubadmin.routes import clubadmin_bp
    from app.support.routes import support_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(adminstaff_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(facilitystaff_bp)
    app.register_blueprint(clubadmin_bp)
    app.register_blueprint(support_bp)

    @app.before_request
    def verify_session_integrity():
        """Verify session integrity, sync roles dynamically, and check suspension."""
        if request.endpoint and (request.endpoint.startswith('static') or request.endpoint == 'auth.logout'):
            return
            
        user_id = session.get('user_id')
        if not user_id:
            return
            
        import time
        now = time.time()
        last_check = session.get('last_integrity_check')
        if last_check and (now - last_check < 60):
            return
            
        from app.db import get_admin_db
        try:
            db = get_admin_db()
            resp = db.table('profiles').select('role, is_suspended').eq('id', user_id).single().execute()
            if resp.data:
                profile = resp.data
                
                # 1. Force logout if suspended
                if profile.get('is_suspended'):
                    session.clear()
                    flash('Your account has been suspended. Please contact support.', 'error')
                    return redirect(url_for('auth.login'))
                    
                # 2. Sync role dynamically
                db_role = (profile.get('role') or 'player').strip().lower()
                if session.get('role') != db_role:
                    session['role'] = db_role
                
                session['last_integrity_check'] = now
        except Exception as e:
            app.logger.error(f"[before_request] Integrity check failed: {e}")

    @app.after_request
    def inject_csrf_token(response):
        """Automatically inject CSRF token hidden fields into HTML POST forms."""
        if response.status_code == 200 and response.content_type and "text/html" in response.content_type:
            try:
                html = response.get_data(as_text=True)
                import re
                from flask_wtf.csrf import generate_csrf
                pattern = re.compile(r'<form\b[^>]*method=\s*["\']post["\'][^>]*>', re.IGNORECASE)
                
                def add_csrf_field(match):
                    form_tag = match.group(0)
                    
                    # Prevent injecting hidden inputs inside JavaScript strings
                    start_pos = match.start()
                    last_script_open = html.rfind('<script', 0, start_pos)
                    last_script_close = html.rfind('</script', 0, start_pos)
                    if last_script_open > last_script_close:
                        return form_tag

                    if 'name="csrf_token"' in form_tag or 'name="csrf_token"' in html[match.end():match.end()+150]:
                        return form_tag
                    csrf_token = generate_csrf()
                    csrf_input = f'<input type="hidden" name="csrf_token" value="{csrf_token}"/>'
                    return f'{form_tag}\n{csrf_input}'
                    
                html_with_csrf = pattern.sub(add_csrf_field, html)
                response.set_data(html_with_csrf)
            except Exception:
                pass
        return response

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

        # --- 1. Try Supabase request-scoped admin client ---
        from app.db import get_admin_db
        client = get_admin_db()
        if client:
            try:
                resp = client.table('profiles').select(
                    'first_name, last_name, phone, role, elo, dupr, proficiency, avatar_url'
                ).eq('id', user_id).single().execute()

                if resp.data:
                    d        = resp.data
                    first    = (d.get('first_name') or '').strip() or 'Player'
                    last     = (d.get('last_name')  or '').strip()
                    full     = f"{first} {last}".strip()
                    initials = (first[0] + (last[0] if last else '')).upper()
                    role     = (d.get('role') or 'player').strip().lower()

                    # Retrieve elo/dupr with proficiency fallback
                    elo = d.get('elo')
                    dupr = d.get('dupr')
                    if elo is None or dupr is None:
                        from app.ratings import get_initial_rating
                        elo_def, dupr_def = get_initial_rating(d.get('proficiency'))
                        if elo is None: elo = elo_def
                        if dupr is None: dupr = dupr_def

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
                        'elo':          elo,
                        'dupr':         dupr,
                        'proficiency':  d.get('proficiency'),
                        'avatar_url':   d.get('avatar_url'),
                    }, supabase_url=supabase_url, supabase_anon_key=supabase_key)
            except Exception as exc:
                print(f"[context_processor] Supabase error: {exc}", file=sys.stderr)

        # --- 2. Fall back to whatever was stored in session at login ---
        first    = session.get('first_name', 'Player')
        last     = session.get('last_name',  '')
        full     = f"{first} {last}".strip()
        initials = (first[0] + (last[0] if last else '')).upper()
        role     = session.get('role', 'player').lower()

        from app.ratings import get_initial_rating
        elo_def, dupr_def = get_initial_rating(session.get('proficiency'))

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
            'elo':          session.get('elo', elo_def),
            'dupr':         session.get('dupr', dupr_def),
            'proficiency':  session.get('proficiency'),
            'avatar_url':   session.get('avatar_url'),
        }, supabase_url=supabase_url, supabase_anon_key=supabase_key)

    @app.context_processor
    def inject_platform_settings():
        """Inject platform settings (SEO, tracking, name, email) into all templates."""
        from app.settings_helper import load_platform_settings
        settings = load_platform_settings()
        return dict(platform_settings=settings)


    # ── Template Filters ──────────────────────────────────────────────────────
    @app.template_filter('community_timeago')
    def community_timeago(iso_str):
        """Convert an ISO timestamp to a human-readable relative time string."""
        import datetime
        try:
            if not iso_str:
                return ''
            if isinstance(iso_str, datetime.datetime):
                dt = iso_str
            else:
                dt = datetime.datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
            
            # Ensure timezone awareness
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                
            now = datetime.datetime.now(datetime.timezone.utc)
            diff = now - dt
            seconds = int(diff.total_seconds())
            
            if seconds < 0:
                seconds = 0
                
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
            return dt.strftime('%b %d')
        except Exception:
            return str(iso_str)[:16] if iso_str else ''

    # ── Error Handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    return app

