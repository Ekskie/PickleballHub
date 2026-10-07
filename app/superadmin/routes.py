from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from app.db import get_db, get_admin_db, log_audit_action



superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

@superadmin_bp.route('/dashboard')
@require_role('superadmin')
def dashboard():
    db = get_db()
    stats = {
        'total_players': 0,
        'total_users': 0,
        'total_facilities': 0,
        'total_courts': 0,
        'total_revenue': 0,
        'total_bookings': 0,
        'pending_kyc': 0,
        'open_tickets': 0,
        'open_disputes': 0,
    }
    recent_facilities = []
    user_role_chart = {'labels': [], 'data': []}
    revenue_trend_chart = {'labels': [], 'revenue': [], 'bookings': []}
    recent_audit_logs = []

    try:
        # 1. Total profiles & role breakdown
        all_prof = db.table('profiles').select('id, role').execute()
        all_profiles = all_prof.data or []
        stats['total_users'] = len(all_profiles)
        role_counts = {}
        for p in all_profiles:
            r = (p.get('role') or 'unknown').strip()
            role_counts[r] = role_counts.get(r, 0) + 1
        stats['total_players'] = role_counts.get('player', 0)
        user_role_chart = {'labels': list(role_counts.keys()), 'data': list(role_counts.values())}

        # 2. Active facilities & courts
        f_resp = db.table('facilities').select('id', count='exact').eq('status', 'active').execute()
        stats['total_facilities'] = f_resp.count or 0

        kyc_resp = db.table('facilities').select('id', count='exact').eq('kyc_status', 'pending_approval').execute()
        stats['pending_kyc'] = kyc_resp.count or 0

        c_resp = db.table('courts').select('id', count='exact').execute()
        stats['total_courts'] = c_resp.count or 0

        # 3. Reservations & platform revenue
        rev_resp = db.table('court_reservations').select('id, total_amount, status, created_at').in_('status', ['confirmed', 'completed']).execute()
        confirmed_reservations = rev_resp.data or []
        stats['total_revenue'] = sum((r.get('total_amount') or 0) for r in confirmed_reservations)
        stats['total_bookings'] = len(confirmed_reservations)

        # 4. Revenue & booking velocity trend (last 6 months)
        now = datetime.now(PH_TZ)
        month_buckets = {}
        for i in range(5, -1, -1):
            m_dt = now - timedelta(days=i * 30)
            key = m_dt.strftime('%Y-%m')
            month_buckets[key] = {'label': m_dt.strftime('%b %Y'), 'revenue': 0.0, 'bookings': 0}
        for r in confirmed_reservations:
            key = (r.get('created_at') or '')[:7]
            if key in month_buckets:
                month_buckets[key]['revenue'] += (r.get('total_amount') or 0)
                month_buckets[key]['bookings'] += 1

        revenue_trend_chart = {
            'labels': [v['label'] for v in month_buckets.values()],
            'revenue': [round(v['revenue'], 2) for v in month_buckets.values()],
            'bookings': [v['bookings'] for v in month_buckets.values()]
        }

        # 5. Open tickets & disputes
        try:
            tkt_resp = db.table('tickets').select('id', count='exact').eq('status', 'open').execute()
            stats['open_tickets'] = tkt_resp.count or 0
        except Exception:
            pass

        try:
            disp_resp = db.table('disputes').select('id', count='exact').eq('status', 'open').execute()
            stats['open_disputes'] = disp_resp.count or 0
        except Exception:
            pass

        # 6. Recent facility registrations (with courts, owner, and kyc_document_url)
        rf_resp = db.table('facilities').select(
            'id, name, location, status, kyc_status, kyc_document_url, created_at, profiles!owner_id(id, first_name, last_name, phone), courts(*)'
        ).order('created_at', desc=True).limit(8).execute()
        recent_facilities = rf_resp.data or []

        # 7. Recent platform audit activity
        try:
            al_resp = db.table('audit_logs').select(
                'id, action, target_resource, details, ip_address, created_at, actor:profiles!actor_id(first_name, last_name, role)'
            ).order('created_at', desc=True).limit(6).execute()
            recent_audit_logs = al_resp.data or []
        except Exception:
            recent_audit_logs = []

    except Exception as e:
        print(f"Superadmin dashboard error: {e}")

    return render_template('superadmin/dashboard.html',
                           stats=stats,
                           recent_facilities=recent_facilities,
                           user_role_chart=user_role_chart,
                           revenue_trend_chart=revenue_trend_chart,
                           recent_audit_logs=recent_audit_logs)

@superadmin_bp.route('/facilities')
@require_role('superadmin')
def facilities():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name), courts(*)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('superadmin/facilities.html', facilities=facilities)

@superadmin_bp.route('/facilities/<facility_id>/status', methods=['POST'])
@require_role('superadmin')
def update_kyc_status(facility_id):
    status = request.form.get('status')
    if status not in ['verified', 'rejected', 'unverified']:
        flash('Invalid status.', 'error')
        return redirect(request.referrer or url_for('superadmin.facilities'))
    db = get_db()
    try:
        db.table('facilities').update({'kyc_status': status}).eq('id', facility_id).execute()
        log_audit_action('update_facility_kyc', facility_id, {'status': status}, raise_on_error=True)
        flash(f'Facility KYC status updated to {status}.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(request.referrer or url_for('superadmin.facilities'))

@superadmin_bp.route('/facilities/<facility_id>/platform_status', methods=['POST'])
@require_role('superadmin')
def update_platform_status(facility_id):
    status = request.form.get('status')
    if status not in ['active', 'suspended', 'pending']:
        flash('Invalid status.', 'error')
        return redirect(request.referrer or url_for('superadmin.facilities'))
    db = get_db()
    try:
        db.table('facilities').update({'status': status}).eq('id', facility_id).execute()
        log_audit_action('update_facility_platform_status', facility_id, {'status': status}, raise_on_error=True)
        flash(f'Facility platform status updated to {status}.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(request.referrer or url_for('superadmin.facilities'))


@superadmin_bp.route('/users')
@require_role('superadmin')
def users():
    db = get_db()
    profiles_list = []
    try:
        resp = db.table('profiles').select('*').order('created_at', desc=True).execute()
        profiles_list = resp.data or []
        
        # Hydrate emails from Supabase auth
        try:
            admin_db = get_admin_db()
            auth_users = admin_db.auth.admin.list_users()
            email_map = {u.id: u.email for u in auth_users}
            for p in profiles_list:
                p['email'] = email_map.get(p['id'], 'N/A')
        except Exception as ae:
            print("Failed to map auth emails for superadmin:", ae)
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('superadmin/users.html', profiles=profiles_list)

@superadmin_bp.route('/users/add_adminstaff', methods=['POST'])
@require_role('superadmin')
def add_adminstaff():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not all([first_name, email, password]):
        flash('Please fill all required fields.', 'error')
        return redirect(request.referrer or url_for('superadmin.users'))
    db = get_db()
    try:
        admin_db = get_admin_db()
        if not admin_db:
            flash("Admin client not available.", "error")
            return redirect(request.referrer or url_for('superadmin.users'))
        new_user = admin_db.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"first_name": first_name, "last_name": last_name, "role": "adminstaff"}
        })
        staff_id = new_user.user.id
        admin_db.table('profiles').upsert({
            'id': staff_id, 'first_name': first_name, 'last_name': last_name, 'role': 'adminstaff'
        }, on_conflict='id').execute()
        log_audit_action('create_adminstaff', staff_id, {'email': email, 'first_name': first_name, 'last_name': last_name}, raise_on_error=True)
        flash(f'Admin Staff account for {first_name} created successfully!', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(request.referrer or url_for('superadmin.users'))

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
        flash('An error occurred. Please try again.', 'error')

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
            flash('An error occurred. Please try again.', 'error')
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
            flash('An error occurred. Please try again.', 'error')
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

@superadmin_bp.route('/users/<user_id>/toggle_suspend', methods=['POST'])
@require_role('superadmin')
def toggle_suspend_user(user_id):
    db = get_db()
    try:
        # Fetch current suspension status
        p_resp = db.table('profiles').select('first_name, role, is_suspended').eq('id', user_id).single().execute()
        if not p_resp.data:
            flash('User not found.', 'error')
            return redirect(url_for('superadmin.users'))
            
        current_status = p_resp.data.get('is_suspended', False)
        new_status = not current_status
        
        # Update in database
        db.table('profiles').update({'is_suspended': new_status}).eq('id', user_id).execute()
        
        action = 'suspend_user' if new_status else 'unsuspend_user'
        log_audit_action(action, user_id, {'role': p_resp.data.get('role'), 'name': p_resp.data.get('first_name')}, raise_on_error=True)
        
        msg = f"User has been {'suspended' if new_status else 'unsuspended'} successfully."
        flash(msg, 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('superadmin.users'))

@superadmin_bp.route('/logs')
@require_role('superadmin')
def audit_logs():
    db = get_db()
    logs_list = []
    try:
        # Fetch audit logs with actor name joined from profiles
        resp = db.table('audit_logs').select(
            'id, action, target_resource, details, ip_address, created_at, actor:profiles!actor_id(first_name, last_name, role)'
        ).order('created_at', desc=True).limit(150).execute()
        logs_list = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('superadmin/logs.html', logs=logs_list)


# ════════════════════════════════════════════════════════════════════════════════
# LANDING PAGE CMS & ARTICLES MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

@superadmin_bp.route('/landing-page', methods=['GET', 'POST'])
@require_role('superadmin')
def landing_page():
    """
    Comprehensive Landing Page CMS.
    Allows editing Hero banner, lead stories, bulletins, testimonials,
    FAQs, section headers, value proposition, and footer stats.
    """
    from app.landing_helper import (
        get_landing_content, get_articles_db,
        save_multiple_landing_settings, save_landing_setting,
        clear_landing_cache
    )
    from app.upload_utils import validate_and_upload

    db = get_db()
    admin_db = get_admin_db() or db

    if request.method == 'POST':
        action_type = request.form.get('action_type', 'all')
        settings_to_save = {}

        try:
            # 1. Masthead & Hero Slider
            if action_type in ('hero', 'all'):
                settings_to_save['masthead_location'] = request.form.get('masthead_location', 'LAGUNA, PHILIPPINES').strip()
                
                hero_slides = []
                slide_count = int(request.form.get('hero_slides_count', 3))
                for i in range(slide_count):
                    title = request.form.get(f'hero_title_{i}', '').strip()
                    subtitle = request.form.get(f'hero_subtitle_{i}', '').strip()
                    img_url = request.form.get(f'hero_image_{i}', '').strip()
                    
                    # Handle file upload if provided
                    slide_file = request.files.get(f'hero_file_{i}')
                    if slide_file and slide_file.filename:
                        uploaded_url, err = validate_and_upload(
                            admin_db, slide_file, bucket='platform-assets',
                            prefix=f'hero_slide_{i+1}', owner_id=session.get('user_id')
                        )
                        if uploaded_url:
                            img_url = uploaded_url

                    if title or img_url:
                        hero_slides.append({
                            'id': i + 1,
                            'title': title,
                            'subtitle': subtitle,
                            'image_url': img_url,
                            'alt': title or 'Hero Slide'
                        })
                if hero_slides:
                    settings_to_save['hero_slides'] = hero_slides

            # 2. Lead Stories Carousel
            if action_type in ('lead_stories', 'all'):
                lead_stories = []
                lead_count = int(request.form.get('lead_count', 3))
                for i in range(lead_count):
                    cat = request.form.get(f'lead_category_{i}', '').strip()
                    title = request.form.get(f'lead_title_{i}', '').strip()
                    desc = request.form.get(f'lead_desc_{i}', '').strip()
                    link = request.form.get(f'lead_link_{i}', '').strip()
                    link_text = request.form.get(f'lead_link_text_{i}', 'Read More').strip()
                    img_url = request.form.get(f'lead_image_{i}', '').strip()

                    lead_file = request.files.get(f'lead_file_{i}')
                    if lead_file and lead_file.filename:
                        uploaded_url, err = validate_and_upload(
                            admin_db, lead_file, bucket='platform-assets',
                            prefix=f'lead_story_{i+1}', owner_id=session.get('user_id')
                        )
                        if uploaded_url:
                            img_url = uploaded_url

                    if title or desc:
                        lead_stories.append({
                            'id': i + 1,
                            'category': cat,
                            'title': title,
                            'description': desc,
                            'link': link,
                            'link_text': link_text,
                            'image_url': img_url
                        })
                if lead_stories:
                    settings_to_save['lead_stories'] = lead_stories

            # 3. Sidebar Bulletins
            if action_type in ('bulletins', 'all'):
                bulletins = []
                bulletin_count = int(request.form.get('bulletin_count', 3))
                for i in range(bulletin_count):
                    b_time = request.form.get(f'bulletin_time_{i}', 'Just In').strip()
                    b_title = request.form.get(f'bulletin_title_{i}', '').strip()
                    b_desc = request.form.get(f'bulletin_desc_{i}', '').strip()
                    b_link = request.form.get(f'bulletin_link_{i}', '').strip()
                    if b_title:
                        bulletins.append({
                            'id': i + 1,
                            'time': b_time,
                            'title': b_title,
                            'description': b_desc,
                            'link': b_link
                        })
                if bulletins:
                    settings_to_save['bulletins'] = bulletins

            # 4. Value Proposition Banner
            if action_type in ('value_prop', 'all'):
                settings_to_save['value_prop_kicker'] = request.form.get('value_prop_kicker', '').strip()
                settings_to_save['value_prop_headline'] = request.form.get('value_prop_headline', '').strip()
                settings_to_save['value_prop_text'] = request.form.get('value_prop_text', '').strip()
                settings_to_save['value_prop_cta_text'] = request.form.get('value_prop_cta_text', 'Sign Up for Free').strip()
                settings_to_save['value_prop_cta_link'] = request.form.get('value_prop_cta_link', '/auth/signup').strip()

            # 5. Section Headers (Sections A, B, C)
            if action_type in ('section_headers', 'all'):
                settings_to_save['section_a_divider_1'] = request.form.get('section_a_divider_1', 'Section A').strip()
                settings_to_save['section_a_divider_2'] = request.form.get('section_a_divider_2', 'Court Reports').strip()
                settings_to_save['section_a_divider_3'] = request.form.get('section_a_divider_3', 'Metro Laguna Edition').strip()
                settings_to_save['section_a_title'] = request.form.get('section_a_title', 'Verified Facilities Available').strip()
                settings_to_save['section_a_subtitle'] = request.form.get('section_a_subtitle', '').strip()

                settings_to_save['section_b_divider_1'] = request.form.get('section_b_divider_1', 'Section B').strip()
                settings_to_save['section_b_divider_2'] = request.form.get('section_b_divider_2', 'Tournament Bulletins').strip()
                settings_to_save['section_b_divider_3'] = request.form.get('section_b_divider_3', 'Local Competitions').strip()
                settings_to_save['section_b_title'] = request.form.get('section_b_title', 'Laguna League Tournaments').strip()
                settings_to_save['section_b_subtitle'] = request.form.get('section_b_subtitle', '').strip()

                settings_to_save['section_c_divider_1'] = request.form.get('section_c_divider_1', 'Section C').strip()
                settings_to_save['section_c_divider_2'] = request.form.get('section_c_divider_2', 'Tutorials').strip()
                settings_to_save['section_c_divider_3'] = request.form.get('section_c_divider_3', 'Training & Clinics').strip()
                settings_to_save['section_c_title'] = request.form.get('section_c_title', 'Clinics & Tutorials').strip()
                settings_to_save['section_c_subtitle'] = request.form.get('section_c_subtitle', '').strip()

            # 6. Testimonials (Section E)
            if action_type in ('testimonials', 'all'):
                testimonials = []
                test_count = int(request.form.get('test_count', 0))
                for i in range(test_count):
                    t_author = request.form.get(f'test_author_{i}', '').strip()
                    t_role = request.form.get(f'test_role_{i}', '').strip()
                    t_quote = request.form.get(f'test_quote_{i}', '').strip()
                    t_rating = int(request.form.get(f'test_rating_{i}', 5))
                    if t_author and t_quote:
                        testimonials.append({
                            'id': i + 1,
                            'author': t_author,
                            'role': t_role,
                            'quote': t_quote,
                            'rating': min(max(t_rating, 1), 5)
                        })
                if testimonials or action_type == 'testimonials':
                    settings_to_save['testimonials'] = testimonials

            # 7. FAQs (Section F)
            if action_type in ('faqs', 'all'):
                faqs = []
                faq_count = int(request.form.get('faq_count', 0))
                for i in range(faq_count):
                    f_q = request.form.get(f'faq_q_{i}', '').strip()
                    f_a = request.form.get(f'faq_a_{i}', '').strip()
                    if f_q and f_a:
                        faqs.append({
                            'id': i + 1,
                            'question': f_q,
                            'answer': f_a
                        })
                if faqs or action_type == 'faqs':
                    settings_to_save['faqs'] = faqs

            # 8. Footer Stats & Final CTA
            if action_type in ('footer', 'all'):
                stats = [
                    {'num': request.form.get('stat_1_num', '500+').strip(), 'label': request.form.get('stat_1_label', 'Active Players').strip()},
                    {'num': request.form.get('stat_2_num', '12').strip(), 'label': request.form.get('stat_2_label', 'Connected Towns').strip()},
                    {'num': request.form.get('stat_3_num', '10k+').strip(), 'label': request.form.get('stat_3_label', 'Matches Played').strip()},
                    {'num': request.form.get('stat_4_num', '100%').strip(), 'label': request.form.get('stat_4_label', 'Automated Booking').strip()},
                ]
                settings_to_save['stats'] = stats
                settings_to_save['footer_cta_kicker'] = request.form.get('footer_cta_kicker', '').strip()
                settings_to_save['footer_cta_headline'] = request.form.get('footer_cta_headline', '').strip()
                settings_to_save['footer_cta_text'] = request.form.get('footer_cta_text', '').strip()
                settings_to_save['footer_cta_btn_text'] = request.form.get('footer_cta_btn_text', 'Sign Up for Free').strip()
                settings_to_save['footer_cta_btn_link'] = request.form.get('footer_cta_btn_link', '/auth/signup').strip()

            if settings_to_save:
                save_multiple_landing_settings(settings_to_save)
                log_audit_action('update_landing_page', 'landing_page', {'action_type': action_type})
                flash('Landing page content saved successfully!', 'success')
            else:
                flash('No settings were modified.', 'info')

        except Exception as e:
            flash(f'Error saving landing page settings: {e}', 'error')

        target_tab = request.form.get('active_tab', '')
        redirect_url = url_for('superadmin.landing_page')
        if target_tab:
            redirect_url += f'#{target_tab}'
        return redirect(redirect_url)

    # GET — load fresh content
    landing_content = get_landing_content(force_refresh=True)
    articles = get_articles_db(force_refresh=True)

    return render_template(
        'superadmin/landing_page.html',
        landing_content=landing_content,
        articles=articles
    )


@superadmin_bp.route('/landing-page/articles/new', methods=['GET', 'POST'])
@require_role('superadmin')
def new_article():
    """Create a new journalist / bulletin article."""
    from app.landing_helper import save_article
    from app.upload_utils import validate_and_upload

    db = get_db()
    admin_db = get_admin_db() or db

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'Bulletin').strip()
        author = request.form.get('author', 'Dev Team Bulletin').strip()
        date_str = request.form.get('date', '').strip() or datetime.now(PH_TZ).strftime('%A, %B %d, %Y')
        read_time = request.form.get('read_time', '3 min read').strip()
        image_url = request.form.get('image_url', '').strip()
        content = request.form.get('content', '').strip()

        # Handle image upload
        img_file = request.files.get('image_file')
        if img_file and img_file.filename:
            uploaded_url, err = validate_and_upload(
                admin_db, img_file, bucket='platform-assets',
                prefix='article_banner', owner_id=session.get('user_id')
            )
            if uploaded_url:
                image_url = uploaded_url

        if not title:
            flash('Article title is required.', 'error')
            return redirect(url_for('superadmin.new_article'))

        art_data = {
            'title': title,
            'category': category,
            'author': author,
            'date': date_str,
            'read_time': read_time,
            'image_url': image_url or '/static/images/court-hero.jpg',
            'image_filename': 'court-hero.jpg',
            'content': content
        }

        try:
            art_id = save_article(art_data)
            log_audit_action('create_article', str(art_id), {'title': title})
            flash(f'Article "{title}" published successfully!', 'success')
            return redirect(url_for('superadmin.landing_page') + '#tab-articles')
        except Exception as e:
            flash(f'Failed to publish article: {e}', 'error')
            return redirect(url_for('superadmin.new_article'))

    return render_template('superadmin/article_edit.html', article=None, mode='create')


@superadmin_bp.route('/landing-page/articles/<article_id>/edit', methods=['GET', 'POST'])
@require_role('superadmin')
def edit_article(article_id):
    """Edit an existing article."""
    from app.landing_helper import get_article_by_id, save_article
    from app.upload_utils import validate_and_upload

    db = get_db()
    admin_db = get_admin_db() or db

    article = get_article_by_id(article_id)
    if not article:
        flash('Article not found.', 'error')
        return redirect(url_for('superadmin.landing_page') + '#tab-articles')

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        author = request.form.get('author', '').strip()
        date_str = request.form.get('date', '').strip()
        read_time = request.form.get('read_time', '').strip()
        image_url = request.form.get('image_url', '').strip()
        content = request.form.get('content', '').strip()

        img_file = request.files.get('image_file')
        if img_file and img_file.filename:
            uploaded_url, err = validate_and_upload(
                admin_db, img_file, bucket='platform-assets',
                prefix=f'article_{article_id}', owner_id=session.get('user_id')
            )
            if uploaded_url:
                image_url = uploaded_url

        article['title'] = title or article['title']
        article['category'] = category or article['category']
        article['author'] = author or article['author']
        article['date'] = date_str or article['date']
        article['read_time'] = read_time or article['read_time']
        if image_url:
            article['image_url'] = image_url
        article['content'] = content

        try:
            save_article(article)
            log_audit_action('update_article', str(article_id), {'title': article['title']})
            flash(f'Article "{article["title"]}" updated successfully!', 'success')
            return redirect(url_for('superadmin.landing_page') + '#tab-articles')
        except Exception as e:
            flash(f'Failed to update article: {e}', 'error')

    return render_template('superadmin/article_edit.html', article=article, mode='edit')


@superadmin_bp.route('/landing-page/articles/<article_id>/delete', methods=['POST'])
@require_role('superadmin')
def delete_article_route(article_id):
    """Delete an article."""
    from app.landing_helper import delete_article
    try:
        delete_article(article_id)
        log_audit_action('delete_article', str(article_id), {})
        flash(f'Article #{article_id} deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete article: {e}', 'error')
    return redirect(url_for('superadmin.landing_page') + '#tab-articles')


@superadmin_bp.route('/landing-page/reset-defaults', methods=['POST'])
@require_role('superadmin')
def reset_landing_defaults():
    """Reset all landing page content to original system defaults."""
    db = get_db()
    try:
        # Delete all landing_ keys from platform_settings
        db.table('platform_settings').delete().like('key', 'landing_%').execute()
        from app.landing_helper import clear_landing_cache
        clear_landing_cache()
        log_audit_action('reset_landing_defaults', 'landing_page', {})
        flash('Landing page has been reset to system defaults.', 'success')
    except Exception as e:
        flash(f'Failed to reset defaults: {e}', 'error')
    return redirect(url_for('superadmin.landing_page'))



