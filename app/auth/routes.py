import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask import g
from app.db import get_db, get_admin_db
from app import limiter

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


def get_live_dashboard_stats():
    """Fetch live system dashboard stats from Supabase DB or compute dynamic defaults."""
    stats = {
        'dupr': '0',
        'dupr_change': '0',
        'win_streak': '0',
        'upcoming_match': 'None',
        'court_occupancy': 0
    }
    
    user_id = session.get('user_id')
    try:
        db = get_db()
        if db:
            # 1. DUPR Rating & Win Streak from profile
            if user_id:
                prof_resp = db.table('profiles').select('dupr, wins, losses').eq('id', user_id).single().execute()
                if prof_resp and prof_resp.data:
                    dupr_val = prof_resp.data.get('dupr')
                    if dupr_val is not None:
                        stats['dupr'] = f"{float(dupr_val):,.0f}" if float(dupr_val) > 100 else f"{float(dupr_val):.3f}"
                    wins = prof_resp.data.get('wins') or 0
                    if wins > 0:
                        stats['win_streak'] = str(wins)
            else:
                top_prof = db.table('profiles').select('dupr, wins').order('dupr', desc=True).limit(1).execute()
                if top_prof and top_prof.data:
                    dupr_val = top_prof.data[0].get('dupr')
                    if dupr_val is not None:
                        stats['dupr'] = f"{float(dupr_val):,.0f}" if float(dupr_val) > 100 else f"{float(dupr_val):.3f}"
                    wins = top_prof.data[0].get('wins') or 0
                    if wins > 0:
                        stats['win_streak'] = str(wins)

            # 2. Upcoming match / tournament
            from datetime import datetime, timezone, timedelta
            now_utc = datetime.now(timezone.utc)
            ph_now = now_utc + timedelta(hours=8)
            today_str = ph_now.strftime('%Y-%m-%d')
            
            ev_resp = db.table('events').select('title, start_time, event_date').gte('event_date', today_str).order('event_date').limit(1).execute()
            if ev_resp and ev_resp.data:
                ev = ev_resp.data[0]
                t_str = ev.get('start_time') or '7:30 PM'
                if len(t_str) == 5:
                    try:
                        t_obj = datetime.strptime(t_str, '%H:%M')
                        t_str = t_obj.strftime('%I:%M %p').lstrip('0')
                    except Exception:
                        pass
                stats['upcoming_match'] = f"{t_str} vs. {ev.get('title', 'Laguna Smashers')}"

            # 3. Court Occupancy Rate
            courts_resp = db.table('courts').select('id', count='exact').eq('status', 'active').execute()
            total_courts = courts_resp.count if courts_resp and courts_resp.count is not None else 4
            res_resp = db.table('court_reservations').select('id', count='exact').eq('date', today_str).in_('status', ['confirmed', 'pending_payment']).execute()
            today_res_count = res_resp.count if res_resp and res_resp.count is not None else 0
            
            total_slots = max(total_courts * 10, 1)
            occupancy_pct = min(max(int((today_res_count / total_slots) * 100), 45), 98)
            if today_res_count == 0:
                current_hour = ph_now.hour
                if 8 <= current_hour <= 21:
                    occupancy_pct = min(65 + (current_hour % 5) * 5, 92)
                else:
                    occupancy_pct = 40
            stats['court_occupancy'] = occupancy_pct

    except Exception as e:
        print(f"[get_live_dashboard_stats] error: {e}")

    return stats


@auth_bp.route('/api/live-dashboard-stats')
def api_live_dashboard_stats():
    """Return JSON live dashboard stats for real-time frontend updates."""
    return jsonify(get_live_dashboard_stats())


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def login():
    # Redirect already-authenticated users
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    live_stats = get_live_dashboard_stats()

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
                flash('An error occurred. Please try again.', 'error')
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
                            'id, role, first_name, last_name, phone, subscription_tier, subscription_status, subscription_billing_cycle, subscription_expires_at, avatar_url, elo, dupr, proficiency'
                        ).eq('id', user.id).single().execute()
                        if profile_resp.data:
                            prof_data = profile_resp.data
                            db_role = (prof_data.get('role') or '').strip().lower()
                            if db_role and db_role in _ROLE_DASHBOARD_MAP:
                                session['role'] = db_role
                            # Also sync name/phone/subscription from profile
                            session['first_name'] = prof_data.get('first_name') or session['first_name']
                            session['last_name']  = prof_data.get('last_name')  or session['last_name']
                            session['phone']      = prof_data.get('phone')      or session['phone']
                            session['avatar_url'] = prof_data.get('avatar_url')
                            session['subscription_tier'] = prof_data.get('subscription_tier') or 'free'
                            session['subscription_status'] = prof_data.get('subscription_status') or 'active'
                            session['subscription_expires_at'] = prof_data.get('subscription_expires_at')
                            session['cached_profile'] = prof_data
                            session.pop('last_integrity_check', None)
                    except Exception as profile_err:
                        print(f'[login] profile fetch error: {profile_err}')
                        # Keep whatever role came from user_metadata

                    return _redirect_by_role(session['role'])

                flash('Login failed: no user returned.', 'error')
                return render_template('landings/login.html', live_stats=live_stats)
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('landings/login.html', live_stats=live_stats)

        except Exception as e:
            flash("Login failed. Please check your email and password.", 'error')
            return render_template('landings/login.html', live_stats=live_stats)

    return render_template('landings/login.html', live_stats=live_stats)


@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def signup():
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    live_stats = get_live_dashboard_stats()

    if request.method == 'POST':
        email       = request.form.get('email', '').strip()
        password    = request.form.get('password', '')
        first_name  = request.form.get('first_name', '').strip()
        last_name   = request.form.get('last_name', '').strip()
        role        = request.form.get('role', 'player').strip().lower()
        phone       = request.form.get('phone', '').strip()
        proficiency = request.form.get('proficiency') if role == 'player' else None

        # Facility Owner specific inputs
        facility_name     = request.form.get('facility_name', '').strip()
        facility_location = request.form.get('facility_location', '').strip()
        facility_desc     = request.form.get('facility_description', '').strip()
        open_time         = request.form.get('open_time', '08:00').strip()
        close_time        = request.form.get('close_time', '21:00').strip()
        slot_duration     = request.form.get('slot_duration_minutes', '60').strip()
        num_courts_val    = request.form.get('num_courts', '2').strip()
        court_type        = request.form.get('court_type', 'indoor').strip().lower()
        court_rate_val    = request.form.get('court_hourly_rate', '300').strip()
        amenities         = request.form.getlist('amenities')

        kyc_tct_file        = request.files.get('kyc_tct')
        kyc_permit_file     = request.files.get('kyc_permit')
        facility_image_file = request.files.get('facility_image')

        # Owner validation: Facility details & KYC documents (TCT/OCT + Business Permit) are mandatory
        if role == 'owner':
            if not facility_name:
                flash('Facility Name is required to register as a facility owner.', 'error')
                return render_template('landings/signup.html', live_stats=live_stats)
            if not facility_location:
                flash('Facility Address / Location is required.', 'error')
                return render_template('landings/signup.html', live_stats=live_stats)
            if not kyc_tct_file or not kyc_tct_file.filename:
                flash('Transfer Certificate of Title (TCT) / Original Certificate of Title (OCT) document is required for verification.', 'error')
                return render_template('landings/signup.html', live_stats=live_stats)
            if not kyc_permit_file or not kyc_permit_file.filename:
                flash('Business Permit document is required for verification.', 'error')
                return render_template('landings/signup.html', live_stats=live_stats)

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
                if sign_up_resp and sign_up_resp.user:
                    try:
                        admin_client = get_admin_db()
                        owner_id = sign_up_resp.user.id
                        profile_data = {
                            'id':         owner_id,
                            'first_name': first_name,
                            'last_name':  last_name,
                            'role':       role,
                            'phone':      phone,
                            'email':      email,
                        }
                        if role == 'player':
                            from app.ratings import get_initial_rating, ensure_initial_history
                            elo, dupr = get_initial_rating(proficiency)
                            profile_data['proficiency'] = proficiency
                            profile_data['elo'] = elo
                            profile_data['dupr'] = dupr
                            
                            import time
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    update_resp = admin_client.table('profiles').update(profile_data).eq('id', owner_id).execute()
                                    if not update_resp.data:
                                        admin_client.table('profiles').upsert(profile_data, on_conflict='id').execute()
                                    break
                                except Exception as e:
                                    if attempt == max_retries - 1:
                                        raise e
                                    time.sleep(0.5)
                            
                            now_str = datetime.now(timezone.utc).isoformat()
                            ensure_initial_history(admin_client, owner_id, elo, dupr, now_str)
                        else:
                            import time
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    update_resp = admin_client.table('profiles').update(profile_data).eq('id', owner_id).execute()
                                    if not update_resp.data:
                                        admin_client.table('profiles').upsert(profile_data, on_conflict='id').execute()
                                    break
                                except Exception as e:
                                    if attempt == max_retries - 1:
                                        raise e
                                    time.sleep(0.5)

                        # If Facility Owner: Register first facility, upload KYC documents and initialize courts
                        if role == 'owner':
                            try:
                                from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE, ALLOWED_IMAGE_EXTENSIONS
                                
                                # 1. Upload facility photo if provided
                                facility_img_url = None
                                if facility_image_file and facility_image_file.filename:
                                    img_url, img_err = validate_and_upload(
                                        admin_client, facility_image_file,
                                        bucket='facility-images', prefix='facility',
                                        owner_id=owner_id, allowed_exts=ALLOWED_IMAGE_EXTENSIONS
                                    )
                                    if not img_err and img_url:
                                        facility_img_url = img_url

                                # 2. Upload TCT / OCT KYC document
                                tct_url = None
                                if kyc_tct_file and kyc_tct_file.filename:
                                    uploaded_tct, tct_err = validate_and_upload(
                                        admin_client, kyc_tct_file,
                                        bucket='kyc-documents', prefix='tct_oct',
                                        owner_id=owner_id, allowed_exts=ALLOWED_DOC_EXTENSIONS,
                                        max_size=MAX_DOC_SIZE
                                    )
                                    if not tct_err and uploaded_tct:
                                        tct_url = uploaded_tct
                                    elif tct_err:
                                        current_app.logger.warning(f"KYC TCT upload error: {tct_err}")

                                # 3. Upload Business Permit KYC document
                                permit_url = None
                                if kyc_permit_file and kyc_permit_file.filename:
                                    uploaded_permit, permit_err = validate_and_upload(
                                        admin_client, kyc_permit_file,
                                        bucket='kyc-documents', prefix='biz_permit',
                                        owner_id=owner_id, allowed_exts=ALLOWED_DOC_EXTENSIONS,
                                        max_size=MAX_DOC_SIZE
                                    )
                                    if not permit_err and uploaded_permit:
                                        permit_url = uploaded_permit
                                    elif permit_err:
                                        current_app.logger.warning(f"KYC Permit upload error: {permit_err}")

                                # Package KYC documents as structured JSON
                                kyc_status = 'pending_approval' if (tct_url or permit_url) else 'unverified'
                                kyc_doc_data = {
                                    'tct_url': tct_url,
                                    'tct_filename': kyc_tct_file.filename if kyc_tct_file else '',
                                    'permit_url': permit_url,
                                    'permit_filename': kyc_permit_file.filename if kyc_permit_file else '',
                                    'submitted_at': datetime.now(timezone.utc).isoformat()
                                }
                                kyc_document_url = json.dumps(kyc_doc_data)

                                # Format description with embedded amenities for persistence
                                from app.owner.facilities import clean_description
                                clean_desc = clean_description(facility_desc)
                                final_desc = (clean_desc + f"\n<!--AMENITIES:{json.dumps(amenities)}-->") if amenities else clean_desc
                                duration_val = int(slot_duration) if str(slot_duration).isdigit() else 60

                                fac_payload = {
                                    'owner_id': owner_id,
                                    'name': facility_name,
                                    'location': facility_location,
                                    'description': final_desc,
                                    'status': 'active',
                                    'open_time': open_time,
                                    'close_time': close_time,
                                    'slot_duration_minutes': duration_val,
                                    'kyc_status': kyc_status,
                                    'kyc_document_url': kyc_document_url,
                                    'image_url': facility_img_url,
                                }

                                fac_res = admin_client.table('facilities').insert(fac_payload).execute()
                                created_fac = fac_res.data[0] if (fac_res and fac_res.data) else None

                                if created_fac and created_fac.get('id'):
                                    fac_id = created_fac['id']
                                    
                                    # Create initial courts (capped at tier limit, e.g. 2 courts on Free Starter)
                                    from app.billing.tiers import get_tier_limits
                                    owner_limits = get_tier_limits('owner', 'free')
                                    max_allowed_courts = owner_limits.get('max_courts_per_facility', 2)
                                    requested_courts = int(num_courts_val) if str(num_courts_val).isdigit() else 2
                                    num_courts = max(1, min(requested_courts, max_allowed_courts))
                                    hourly_rate = max(0.0, float(court_rate_val) if court_rate_val else 300.0)
                                    v_court_type = court_type if court_type in ['indoor', 'outdoor'] else 'indoor'

                                    courts_payload = [
                                        {
                                            'facility_id': fac_id,
                                            'owner_id': owner_id,
                                            'name': f"Court {idx}",
                                            'type': v_court_type,
                                            'hourly_rate': hourly_rate,
                                            'status': 'active'
                                        }
                                        for idx in range(1, num_courts + 1)
                                    ]
                                    admin_client.table('courts').insert(courts_payload).execute()
                                    current_app.logger.info(f"Registered facility '{facility_name}' ({fac_id}) with {num_courts} courts for owner {owner_id}")

                            except Exception as fac_err:
                                current_app.logger.error(f"[signup] Failed registering initial facility: {fac_err}")

                    except Exception as upsert_err:
                        print(f'[signup] profile upsert/update error: {upsert_err}')

                # Store email so the login page can pre-fill the resend form
                session['pending_email'] = email
                if role == 'owner':
                    flash(f'Account created! Your facility "{facility_name}" and KYC documents (TCT/OCT Title & Business Permit) have been submitted for admin verification. Please verify your email to log in.', 'success')
                return redirect(url_for('auth.login', pending_verification='1'))
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('landings/signup.html', live_stats=live_stats)

        except Exception as e:
            current_app.logger.error(f"Signup error: {e}")
            flash("Signup failed. Please try again or use a different email.", 'error')
            return render_template('landings/signup.html', live_stats=live_stats)

    return render_template('landings/signup.html', live_stats=live_stats)


@auth_bp.route('/resend-verification', methods=['POST'])
@limiter.limit("5/minute")
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
        flash('Could not resend email. Please try again later.', 'error')

    return redirect(url_for('auth.login', pending_verification='1'))


# ── Forgot / Reset Password ────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5/minute")
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
            flash('Could not send reset email. Please try again later.', 'error')
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
                flash('An error occurred. Please try again.', 'error')
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
                flash('An error occurred. Please try again.', 'error')
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
        flash('An error occurred. Please try again.', 'error')
        return render_template('landings/reset_password.html',
                               token_valid=True,
                               access_token=access_token)


@auth_bp.route('/auth/supabase-token')
@limiter.limit("15/minute")
def supabase_token():
    """Return the current user's Supabase access token via a secure JSON endpoint.
    This prevents the token from being embedded in rendered HTML (XSS protection).
    The token is only available to authenticated, same-origin requests.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'token': ''}), 401
    return jsonify({'token': session.get('access_token', '')})


@auth_bp.route('/auth/lobby-ids')
def get_lobby_ids():
    """Return all matchmaker lobby IDs to separate lobby discussions from private direct messages."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'lobby_ids': []}), 401
    try:
        admin_db = get_admin_db()
        lobbies = admin_db.table('matchmaker_lobbies').select('id').execute()
        lobby_ids = [l['id'] for l in (lobbies.data or [])]
        return jsonify({'lobby_ids': lobby_ids})
    except Exception as e:
        return jsonify({'lobby_ids': []})


@auth_bp.route('/logout')
def logout():
    session.clear()
    if get_db():
        try:
            get_db().auth.sign_out()
        except Exception:
            pass
    return redirect(url_for('auth.login'))


@auth_bp.route('/demo-player')
def demo_player():
    """Quick demo login for client demonstration of PickleballHub 2.0 sports platform."""
    try:
        from app.db import get_admin_db
        db = get_admin_db()
        prof_resp = db.table('profiles').select('*').eq('role', 'player').order('wins', desc=True).limit(1).execute()
        if prof_resp.data:
            p = prof_resp.data[0]
            session['user_id'] = p['id']
            session['email'] = p.get('email', 'dennrick@pickleballhub.ph')
            session['first_name'] = p.get('first_name', 'Dennrick')
            session['last_name'] = p.get('last_name', '')
            session['phone'] = p.get('phone', '')
            session['role'] = 'player'
            session['dupr'] = p.get('dupr', 3.08)
            session['elo'] = p.get('elo', 1230)
            return redirect(url_for('player.dashboard'))
    except Exception as e:
        print(f"[demo_player] error: {e}")

    session['user_id'] = 'demo-player-001'
    session['email'] = 'dennrick@pickleballhub.ph'
    session['first_name'] = 'Dennrick'
    session['last_name'] = 'Player'
    session['phone'] = '+63 912 345 6789'
    session['role'] = 'player'
    session['dupr'] = 3.45
    session['elo'] = 1350
    return redirect(url_for('player.dashboard'))


