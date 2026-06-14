from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from flask import g
import os
from supabase import create_client

_cached_db = None

def get_db():
    global _cached_db
    if _cached_db is None:
        import os
        import httpx
        from supabase import create_client, ClientOptions
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        if url and key:
            http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
            options = ClientOptions(httpx_client=http_client)
            _cached_db = create_client(url, key, options=options)
    return _cached_db


superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

@superadmin_bp.route('/dashboard')
@require_role('superadmin')
def dashboard():
    db = get_db()
    stats = {'total_players': 0, 'total_facilities': 0, 'total_revenue': 0, 'pending_kyc': 0}
    recent_facilities = []
    user_role_chart = {'labels': [], 'data': []}

    try:
        # Total players
        p_resp = db.table('profiles').select('id', count='exact').eq('role', 'player').execute()
        stats['total_players'] = p_resp.count or 0

        # Active facilities
        f_resp = db.table('facilities').select('id', count='exact').eq('status', 'active').execute()
        stats['total_facilities'] = f_resp.count or 0

        # Total platform revenue
        rev_resp = db.table('court_reservations').select('total_amount').in_('status', ['confirmed', 'completed']).execute()
        stats['total_revenue'] = sum((r.get('total_amount') or 0) for r in (rev_resp.data or []))

        # Pending KYC
        kyc_resp = db.table('facilities').select('id', count='exact').eq('kyc_status', 'pending_approval').execute()
        stats['pending_kyc'] = kyc_resp.count or 0

        # Recent facility registrations
        rf_resp = db.table('facilities').select(
            'id, name, location, status, kyc_status, created_at, profiles!owner_id(first_name, last_name), courts(*)'
        ).order('created_at', desc=True).limit(6).execute()
        recent_facilities = rf_resp.data or []

        # User distribution by role
        all_prof = db.table('profiles').select('role').execute()
        role_counts = {}
        for p in (all_prof.data or []):
            r = (p.get('role') or 'unknown').strip()
            role_counts[r] = role_counts.get(r, 0) + 1
        user_role_chart = {'labels': list(role_counts.keys()), 'data': list(role_counts.values())}

    except Exception as e:
        print(f"Superadmin dashboard error: {e}")

    return render_template('superadmin/dashboard.html',
                           stats=stats,
                           recent_facilities=recent_facilities,
                           user_role_chart=user_role_chart)

@superadmin_bp.route('/facilities')
@require_role('superadmin')
def facilities():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name), courts(*)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
    return render_template('superadmin/facilities.html', facilities=facilities)

@superadmin_bp.route('/facilities/<facility_id>/status', methods=['POST'])
@require_role('superadmin')
def update_kyc_status(facility_id):
    status = request.form.get('status')
    if status not in ['verified', 'rejected', 'unverified']:
        flash('Invalid status.', 'error')
        return redirect(url_for('superadmin.facilities'))
    db = get_db()
    try:
        db.table('facilities').update({'kyc_status': status}).eq('id', facility_id).execute()
        flash(f'Facility KYC status updated to {status}.', 'success')
    except Exception as e:
        flash(f'Error updating status: {e}', 'error')
    return redirect(url_for('superadmin.facilities'))

@superadmin_bp.route('/facilities/<facility_id>/platform_status', methods=['POST'])
@require_role('superadmin')
def update_platform_status(facility_id):
    status = request.form.get('status')
    if status not in ['active', 'suspended', 'pending']:
        flash('Invalid status.', 'error')
        return redirect(url_for('superadmin.facilities'))
    db = get_db()
    try:
        db.table('facilities').update({'status': status}).eq('id', facility_id).execute()
        flash(f'Facility platform status updated to {status}.', 'success')
    except Exception as e:
        flash(f'Error updating platform status: {e}', 'error')
    return redirect(url_for('superadmin.facilities'))


@superadmin_bp.route('/users')
@require_role('superadmin')
def users():
    db = get_db()
    adminstaff_list = []
    try:
        resp = db.table('profiles').select('*').eq('role', 'adminstaff').order('created_at', desc=True).execute()
        adminstaff_list = resp.data or []
    except Exception as e:
        flash(f'Error loading users: {e}', 'error')
    return render_template('superadmin/users.html', adminstaff=adminstaff_list)

@superadmin_bp.route('/users/add_adminstaff', methods=['POST'])
@require_role('superadmin')
def add_adminstaff():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not all([first_name, email, password]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('superadmin.users'))
    db = get_db()
    try:
        from app import supabase_admin
        if not supabase_admin:
            flash("Admin client not available.", "error")
            return redirect(url_for('superadmin.users'))
        new_user = supabase_admin.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"first_name": first_name, "last_name": last_name, "role": "adminstaff"}
        })
        staff_id = new_user.user.id
        supabase_admin.table('profiles').upsert({
            'id': staff_id, 'first_name': first_name, 'last_name': last_name, 'role': 'adminstaff'
        }, on_conflict='id').execute()
        flash(f'Admin Staff account for {first_name} created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating admin staff: {e}', 'error')
    return redirect(url_for('superadmin.users'))

# ── Reports with real data ──────────────────────────────────────────────────────
@superadmin_bp.route('/reports')
@require_role('superadmin')
def reports():
    db = get_db()
    stats = {'total_revenue': 0, 'total_bookings': 0, 'total_events': 0, 'total_users': 0}
    revenue_chart = {'labels': [], 'data': []}
    booking_chart = {'labels': [], 'data': []}
    role_chart = {'labels': [], 'data': []}
    kyc_chart = {'labels': [], 'data': []}

    try:
        now = datetime.now(PH_TZ)

        # Build last-6-month buckets
        month_buckets = {}
        for i in range(5, -1, -1):
            month_dt = now - timedelta(days=i * 30)
            key = month_dt.strftime('%Y-%m')
            month_buckets[key] = {'label': month_dt.strftime('%b %Y'), 'revenue': 0.0, 'bookings': 0}

        # All confirmed/completed reservations
        rev_resp = db.table('court_reservations').select('total_amount, status, created_at').in_('status', ['confirmed', 'completed']).execute()
        reservations = rev_resp.data or []
        stats['total_revenue'] = sum((r.get('total_amount') or 0) for r in reservations)
        stats['total_bookings'] = len(reservations)

        for r in reservations:
            key = (r.get('created_at') or '')[:7]
            if key in month_buckets:
                month_buckets[key]['revenue'] += (r.get('total_amount') or 0)
                month_buckets[key]['bookings'] += 1

        revenue_chart = {'labels': [v['label'] for v in month_buckets.values()],
                         'data': [round(v['revenue'], 2) for v in month_buckets.values()]}
        booking_chart = {'labels': [v['label'] for v in month_buckets.values()],
                         'data': [v['bookings'] for v in month_buckets.values()]}

        # User distribution
        all_prof = db.table('profiles').select('role').execute()
        all_profiles = all_prof.data or []
        stats['total_users'] = len(all_profiles)
        role_counts = {}
        for p in all_profiles:
            rr = (p.get('role') or 'unknown').strip()
            role_counts[rr] = role_counts.get(rr, 0) + 1
        role_chart = {'labels': list(role_counts.keys()), 'data': list(role_counts.values())}

        # KYC distribution
        all_fac = db.table('facilities').select('kyc_status').execute()
        kyc_counts = {'verified': 0, 'pending_approval': 0, 'unverified': 0, 'rejected': 0}
        for f in (all_fac.data or []):
            s = (f.get('kyc_status') or 'unverified')
            kyc_counts[s] = kyc_counts.get(s, 0) + 1
        kyc_chart = {
            'labels': ['Verified', 'Pending', 'Unverified', 'Rejected'],
            'data': [kyc_counts['verified'], kyc_counts['pending_approval'],
                     kyc_counts['unverified'], kyc_counts['rejected']]
        }

        # Events total
        ev_resp = db.table('events').select('id', count='exact').execute()
        stats['total_events'] = ev_resp.count or 0

    except Exception as e:
        print(f"Reports error: {e}")
        flash(f'Error loading reports data: {e}', 'error')

    return render_template('superadmin/reports.html',
                           stats=stats,
                           revenue_chart=revenue_chart,
                           booking_chart=booking_chart,
                           role_chart=role_chart,
                           kyc_chart=kyc_chart)

# ── Settings (real save) ────────────────────────────────────────────────────────
@superadmin_bp.route('/settings', methods=['GET', 'POST'])
@require_role('superadmin')
def settings():
    db = get_db()
    current = {
        'platform_name': 'PickleballHub',
        'support_email': 'support@pickleballhub.com',
        'maintenance_mode': False,
        'require_2fa': False,
        'seo_meta_title': 'PickleballHub - Centralized Court & Tournament Management',
        'seo_meta_description': 'Discover and book pickleball courts, participate in tournaments, and connect with players.',
        'seo_meta_keywords': 'pickleball, courts, booking, tournament, matchmaker',
        'seo_og_image': '',
        'google_analytics_id': '',
        'facebook_pixel_id': '',
        'custom_head_scripts': '',
    }

    if request.method == 'POST':
        try:
            rows = [
                {'key': 'platform_name', 'value': request.form.get('platform_name', 'PickleballHub').strip()},
                {'key': 'support_email', 'value': request.form.get('support_email', '').strip()},
                {'key': 'maintenance_mode', 'value': '1' if request.form.get('maintenance_mode') else '0'},
                {'key': 'require_2fa', 'value': '1' if request.form.get('require_2fa') else '0'},
                {'key': 'seo_meta_title', 'value': request.form.get('seo_meta_title', '').strip()},
                {'key': 'seo_meta_description', 'value': request.form.get('seo_meta_description', '').strip()},
                {'key': 'seo_meta_keywords', 'value': request.form.get('seo_meta_keywords', '').strip()},
                {'key': 'seo_og_image', 'value': request.form.get('seo_og_image', '').strip()},
                {'key': 'google_analytics_id', 'value': request.form.get('google_analytics_id', '').strip()},
                {'key': 'facebook_pixel_id', 'value': request.form.get('facebook_pixel_id', '').strip()},
                {'key': 'custom_head_scripts', 'value': request.form.get('custom_head_scripts', '').strip()},
            ]
            for row in rows:
                db.table('platform_settings').upsert(row, on_conflict='key').execute()
            
            # Clear settings cache so it reloads immediately
            from app.settings_helper import clear_settings_cache
            clear_settings_cache()
            
            flash('Settings saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving settings: {e}', 'error')
        return redirect(url_for('superadmin.settings'))

    # GET — load from DB
    try:
        resp = db.table('platform_settings').select('*').execute()
        for row in (resp.data or []):
            k, v = row.get('key'), row.get('value')
            if k in ('maintenance_mode', 'require_2fa'):
                current[k] = (v == '1')
            elif k in current:
                current[k] = v
    except Exception as e:
        print(f"Settings load error: {e}")

    return render_template('superadmin/settings.html', settings=current)

@superadmin_bp.route('/profile', methods=['GET', 'POST'])
@require_role('superadmin')
def profile():
    user_id = session.get('user_id')
    db = get_db()
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        avatar_file = request.files.get('avatar')
        avatar_url = None
        if avatar_file and avatar_file.filename:
            try:
                from app.decorators import upload_avatar
                avatar_url = upload_avatar(db, user_id, avatar_file)
            except Exception as e:
                flash(f"Warning: Avatar upload failed - {e}", "warning")
                
        try:
            update_data = {
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }
            if avatar_url:
                update_data['avatar_url'] = avatar_url
                
            db.table('profiles').update(update_data).eq('id', user_id).execute()
            
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['phone'] = phone
            if avatar_url:
                session['avatar_url'] = avatar_url
                
            flash("Profile updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('superadmin.profile'))
    return render_template('superadmin/profile.html')

@superadmin_bp.route('/notifications')
@require_role('superadmin')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('superadmin/notifications.html', notifications=notifs)

@superadmin_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('superadmin')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@superadmin_bp.route('/messages')
@require_role('superadmin')
def messages():
    return render_template('superadmin/messages.html')

@superadmin_bp.route('/community')
@require_role('superadmin')
def community():
    return render_template('superadmin/community.html')

@superadmin_bp.route('/tutorials')
@require_role('superadmin')
def tutorials():
    return render_template('superadmin/tutorials.html')

