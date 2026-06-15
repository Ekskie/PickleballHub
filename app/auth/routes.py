from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask import g
from app.db import get_db, get_admin_db

auth_bp = Blueprint('auth', __name__, url_prefix='')

# Valid roles and their dashboard endpoints
_ROLE_DASHBOARD_MAP = {
    'player':       'player.dashboard',
    'superadmin':   'superadmin.dashboard',
    'owner':        'owner.dashboard',
    'clubadmin':    'clubadmin.dashboard',
    'facilitystaff':'facilitystaff.dashboard',
    'adminstaff':   'adminstaff.dashboard',
}

def _redirect_by_role(role: str):
    """Return the correct dashboard redirect for a given role string.
    Unknown/legacy role strings redirect to login to avoid infinite loops.
    """
    role = (role or '').strip().lower()
    endpoint = _ROLE_DASHBOARD_MAP.get(role)
    if endpoint:
        return redirect(url_for(endpoint))
    # Unknown role — clear session and send to login
    session.clear()
    flash('Your account role is not recognised. Please contact support.', 'error')
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect already-authenticated users
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    # ── Handle Supabase email-verification callback ──────────────────────────
    # Supabase appends ?token_hash=xxx&type=email when user clicks the link.
    if request.method == 'GET':
        token_hash = request.args.get('token_hash')
        token_type = request.args.get('type')        # 'email', 'signup', etc.

        if token_hash and token_type in ['email', 'signup']:
            try:
                if get_db():
                    resp = get_db().auth.verify_otp({
                        "token_hash": token_hash,
                        "type": token_type
                    })
                    if resp and resp.user:
                        # Verification succeeded → redirect with ?verified=1
                        return redirect(url_for('auth.login', verified='1'))
                    else:
                        flash('Verification failed. The link may have expired.', 'error')
                        return redirect(url_for('auth.login'))
            except Exception as e:
                flash(f'Verification error: {str(e)}', 'error')
                return redirect(url_for('auth.login'))

    # ── POST: sign in ────────────────────────────────────────────────────────
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        try:
            if get_db():
                response = get_db().auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                if response.user:
                    user = response.user
                    meta = user.user_metadata or {}

                    session['user_id']    = user.id
                    session['email']      = user.email or email or ''
                    session['first_name'] = meta.get('first_name', '')
                    session['last_name']  = meta.get('last_name',  '')
                    session['phone']      = meta.get('phone', '')
                    session['role']       = meta.get('role', 'player') or 'player'
                    session['access_token'] = response.session.access_token
                    session['refresh_token'] = response.session.refresh_token

                    # Always prefer the DB profiles.role over user_metadata
                    # (DB is the source of truth; metadata may contain old/incorrect values)
                    try:
                        profile_resp = get_db().table('profiles').select(
                            'role, first_name, last_name, phone'
                        ).eq('id', user.id).single().execute()
                        if profile_resp.data:
                            db_role = (profile_resp.data.get('role') or '').strip().lower()
                            if db_role and db_role in _ROLE_DASHBOARD_MAP:
                                session['role'] = db_role
                            # Also sync name/phone from profile
                            session['first_name'] = profile_resp.data.get('first_name') or session['first_name']
                            session['last_name']  = profile_resp.data.get('last_name')  or session['last_name']
                            session['phone']      = profile_resp.data.get('phone')      or session['phone']
                    except Exception as profile_err:
                        print(f'[login] profile fetch error: {profile_err}')
                        # Keep whatever role came from user_metadata

                    return _redirect_by_role(session['role'])

                flash('Login failed: no user returned.', 'error')
                return render_template('landings/login.html')
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('landings/login.html')

        except Exception as e:
            flash(f"Login Failed: {str(e)}", 'error')
            return render_template('landings/login.html')

    return render_template('landings/login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    if request.method == 'POST':
        email       = request.form.get('email')
        password    = request.form.get('password')
        first_name  = request.form.get('first_name')
        last_name   = request.form.get('last_name')
        role        = request.form.get('role')
        phone       = request.form.get('phone')
        proficiency = request.form.get('proficiency') if role == 'player' else None

        try:
            if get_db():
                sign_up_resp = get_db().auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "email_redirect_to": url_for('auth.login', _external=True),
                        "data": {
                            "first_name":  first_name,
                            "last_name":   last_name,
                            "role":        role,
                            "proficiency": proficiency,
                            "phone":       phone
                        }
                    }
                })

                # Upsert the role into profiles so DB is always the source of truth.
                # The Supabase trigger may create the profile with a default role;
                # we overwrite it here to ensure the chosen role is persisted.
                if sign_up_resp and sign_up_resp.user:
                    try:
                        admin_client = get_admin_db()
                        admin_client.table('profiles').upsert({
                            'id':         sign_up_resp.user.id,
                            'first_name': first_name,
                            'last_name':  last_name,
                            'role':       role,
                            'phone':      phone,
                        }, on_conflict='id').execute()
                    except Exception as upsert_err:
                        print(f'[signup] profile upsert error: {upsert_err}')

                # Store email so the login page can pre-fill the resend form
                session['pending_email'] = email
                return redirect(url_for('auth.login', pending_verification='1'))
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('landings/signup.html')

        except Exception as e:
            flash(f"Signup Failed: {str(e)}", 'error')
            return render_template('landings/signup.html')

    return render_template('landings/signup.html')


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend the email verification link to the given address."""
    email = request.form.get('email', '').strip()
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('auth.login', pending_verification='1'))

    try:
        if get_db():
            get_db().auth.resend({
                "type": "signup",
                "email": email,
                "options": {
                    "email_redirect_to": url_for('auth.login', _external=True)
                }
            })
            session['pending_email'] = email
            flash(f'Verification email resent to {email}. Please check your inbox.', 'success')
        else:
            flash('Supabase not configured locally.', 'error')
    except Exception as e:
        flash(f'Could not resend email: {str(e)}', 'error')

    return redirect(url_for('auth.login', pending_verification='1'))


# ── Forgot / Reset Password ────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Step 1: user enters email → Supabase sends reset link."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('landings/forgot_password.html')

        try:
            if get_db():
                get_db().auth.reset_password_for_email(
                    email,
                    options={
                        "email_redirect_to": url_for('auth.reset_password', _external=True)
                    }
                )
            # Always show the "sent" state — don't leak whether email exists
            return redirect(url_for('auth.forgot_password', sent='1', email=email))
        except Exception as e:
            flash(f'Could not send reset email: {str(e)}', 'error')
            return render_template('landings/forgot_password.html')

    return render_template('landings/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Step 2: user lands here from the email link, sets a new password."""

    # ── GET: handle both token styles from Supabase ──────────────────────────
    if request.method == 'GET':
        token_hash    = request.args.get('token_hash')
        access_token  = request.args.get('access_token')
        refresh_token = request.args.get('refresh_token', '')
        token_type    = request.args.get('type', '')

        # ── Path A: PKCE flow — ?token_hash=xxx&type=recovery ────────────────
        if token_hash and token_type == 'recovery':
            try:
                if get_db():
                    resp = get_db().auth.verify_otp({
                        "token_hash": token_hash,
                        "type": "recovery"
                    })
                    if resp and resp.session:
                        session['reset_access_token']  = resp.session.access_token
                        session['reset_refresh_token'] = resp.session.refresh_token or ''
                        return render_template('landings/reset_password.html',
                                               token_valid=True,
                                               access_token=resp.session.access_token,
                                               refresh_token=resp.session.refresh_token or '')
            except Exception as e:
                flash(f'Reset link error: {str(e)}', 'error')
            return render_template('landings/reset_password.html', token_valid=False)

        # ── Path B: Implicit/hash flow — ?access_token=xxx&type=recovery ─────
        # (tokens were in the URL hash; JS extracted and forwarded them here)
        if access_token and token_type == 'recovery':
            try:
                if get_db():
                    # Authenticate the client with the token so update_user will work
                    get_db().auth.set_session(access_token, refresh_token)
                    session['reset_access_token']  = access_token
                    session['reset_refresh_token'] = refresh_token
                    return render_template('landings/reset_password.html',
                                           token_valid=True,
                                           access_token=access_token,
                                           refresh_token=refresh_token)
            except Exception as e:
                flash(f'Reset link error: {str(e)}', 'error')
            return render_template('landings/reset_password.html', token_valid=False)

        # ── No token at all ───────────────────────────────────────────────────
        if not session.get('reset_access_token'):
            return redirect(url_for('auth.forgot_password'))

        # Already verified in a previous request — show the form again
        return render_template('landings/reset_password.html',
                               token_valid=True,
                               access_token=session.get('reset_access_token'),
                               refresh_token=session.get('reset_refresh_token', ''))


    # ── POST: apply the new password ─────────────────────────────────────────
    password         = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    access_token     = request.form.get('access_token')  or session.get('reset_access_token', '')
    refresh_token    = request.form.get('refresh_token') or session.get('reset_refresh_token', '')

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return render_template('landings/reset_password.html',
                               token_valid=True,
                               access_token=access_token,
                               refresh_token=refresh_token)

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return render_template('landings/reset_password.html',
                               token_valid=True,
                               access_token=access_token,
                               refresh_token=refresh_token)

    try:
        if get_db():
            # Restore the authenticated session then update the password
            get_db().auth.set_session(access_token, refresh_token)
            get_db().auth.update_user({"password": password})

            # Clear the reset tokens from session
            session.pop('reset_access_token', None)
            session.pop('reset_refresh_token', None)

            return render_template('landings/reset_password.html',
                                   token_valid=False,
                                   reset_success=True)
        else:
            flash('Supabase not configured locally.', 'error')
            return render_template('landings/reset_password.html',
                                   token_valid=True,
                                   access_token=access_token)

    except Exception as e:
        flash(f'Could not update password: {str(e)}', 'error')
        return render_template('landings/reset_password.html',
                               token_valid=True,
                               access_token=access_token)


@auth_bp.route('/logout')
def logout():
    session.clear()
    if get_db():
        try:
            get_db().auth.sign_out()
        except Exception:
            pass
    return redirect(url_for('auth.login'))

