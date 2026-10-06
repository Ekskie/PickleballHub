from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.decorators import require_role
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from app.owner import owner_bp
from app.db import get_db, get_admin_db

# ── Dashboard ──────────────────────────────────────────────────────────────────
@owner_bp.route('/dashboard')
@require_role('owner')
def dashboard():
    owner_id = session.get('user_id')
    db = get_admin_db()

    total_earnings = 0       # all-time
    today_earnings = 0
    total_bookings = 0
    active_staff = 0
    recent_bookings = []
    revenue_chart = {'labels': [], 'data': []}
    facility_revenue = []

    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        facilities_data = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_data]

        if fac_ids:
            from datetime import date
            today_str = date.today().isoformat()

            # All confirmed/completed reservations with rich profiles, courts, and facilities
            res_resp = db.table('court_reservations').select(
                'id, facility_id, court_id, total_amount, date, start_time, end_time, status, gcash_ref, receipt_url, guest_name, guest_phone, '
                'profiles(id, first_name, last_name, avatar_url, phone, email), '
                'courts(id, name, type), '
                'facilities(id, name, location)'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            reservations = res_resp.data or []

            paid = [r for r in reservations if r['status'] in ['confirmed', 'completed']]
            total_bookings = len(reservations)
            total_earnings = sum((r.get('total_amount') or 0) for r in paid)
            today_earnings = sum((r.get('total_amount') or 0) for r in paid if r.get('date') == today_str)

            # Process recent bookings (top 6)
            recent_bookings = []
            for r in reservations[:6]:
                prof = r.get('profiles') or {}
                first = (prof.get('first_name') or '').strip()
                last = (prof.get('last_name') or '').strip()
                full_name = f"{first} {last}".strip()

                if full_name:
                    r['player_name'] = full_name.title()
                    r['player_initials'] = ((first[:1] if first else '') + (last[:1] if last else '')).upper() or 'P'
                    r['is_guest'] = False
                elif r.get('guest_name'):
                    r['player_name'] = r['guest_name'].title()
                    r['player_initials'] = (r['guest_name'][:2]).upper()
                    r['is_guest'] = True
                else:
                    r['player_name'] = "Guest Player"
                    r['player_initials'] = "GP"
                    r['is_guest'] = True

                r['player_avatar'] = prof.get('avatar_url')
                r['player_phone'] = prof.get('phone') or r.get('guest_phone') or ''
                r['player_email'] = prof.get('email') or ''
                
                # Format friendly 12h times
                st = r.get('start_time') or ''
                et = r.get('end_time') or ''
                try:
                    parts = st.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ampm = 'AM' if hh < 12 else 'PM'
                    d_hh = hh % 12 or 12
                    r['start_time_fmt'] = f"{d_hh}:{mm:02d} {ampm}"
                except Exception:
                    r['start_time_fmt'] = st[:5]

                try:
                    parts = et.split(':')
                    hh, mm = int(parts[0]), int(parts[1])
                    ampm = 'AM' if hh < 12 else 'PM'
                    d_hh = hh % 12 or 12
                    r['end_time_fmt'] = f"{d_hh}:{mm:02d} {ampm}"
                except Exception:
                    r['end_time_fmt'] = et[:5]

                recent_bookings.append(r)

            # 7-day daily revenue trend
            now = datetime.now(PH_TZ)
            labels, daily_data = [], []
            for i in range(6, -1, -1):
                day = now - timedelta(days=i)
                day_str = day.strftime('%Y-%m-%d')
                labels.append(day.strftime('%b %d'))
                day_rev = sum((r.get('total_amount') or 0) for r in paid if r.get('date') == day_str)
                daily_data.append(round(day_rev, 2))
            revenue_chart = {'labels': labels, 'data': daily_data}

            # Current month strings for monthly breakdown
            current_month_str = now.strftime('%Y-%m')
            current_month_name = now.strftime('%B %Y')

            # Revenue per facility (All-Time and Monthly)
            for f in facilities_data:
                f_paid = [r for r in paid if r.get('facility_id') == f['id']]
                f_all_rev = sum((r.get('total_amount') or 0) for r in f_paid)
                f_all_bookings = sum(1 for r in reservations if r.get('facility_id') == f['id'])

                f_month_paid = [r for r in f_paid if (r.get('date') or '').startswith(current_month_str)]
                f_month_rev = sum((r.get('total_amount') or 0) for r in f_month_paid)
                f_month_bookings = sum(1 for r in reservations if r.get('facility_id') == f['id'] and (r.get('date') or '').startswith(current_month_str))

                facility_revenue.append({
                    'id': f['id'],
                    'name': f['name'],
                    'revenue': round(f_all_rev, 2),
                    'bookings': f_all_bookings,
                    'all_time_revenue': round(f_all_rev, 2),
                    'all_time_bookings': f_all_bookings,
                    'month_revenue': round(f_month_rev, 2),
                    'month_bookings': f_month_bookings,
                })

            # Staff count
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            active_staff = staff_resp.count or 0

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Owner dashboard error: {e}")

    now = datetime.now(PH_TZ)
    today_str = now.strftime('%Y-%m-%d')
    current_month_name = now.strftime('%B %Y')

    return render_template(
        'owner/dashboard.html',
        total_earnings=total_earnings,
        today_earnings=today_earnings,
        total_bookings=total_bookings,
        active_staff=active_staff,
        recent_bookings=recent_bookings,
        revenue_chart=revenue_chart,
        facility_revenue=facility_revenue,
        today_str=today_str,
        current_month_name=current_month_name,
    )


# ── Profile ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/profile', methods=['GET', 'POST'])
@require_role('owner')
def profile():
    user_id = session.get('user_id')
    db = get_admin_db() or get_db()
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
        return redirect(url_for('owner.profile'))

    stats = {
        'facilities': 0,
        'courts': 0,
        'staff': 0,
        'total_revenue': 0.0,
        'total_bookings': 0,
        'member_since': ''
    }
    facilities_list = []
    recent_activity = []

    try:
        # 1. Fetch owner profile info
        prof_resp = db.table('profiles').select('created_at, phone').eq('id', user_id).single().execute()
        if prof_resp.data and prof_resp.data.get('created_at'):
            try:
                dt = datetime.fromisoformat(prof_resp.data['created_at'].replace('Z', '+00:00'))
                stats['member_since'] = dt.strftime('%B %Y')
            except Exception:
                stats['member_since'] = prof_resp.data['created_at'][:10]

        # 2. Fetch facilities
        fac_resp = db.table('facilities').select('id, name, location, status, created_at').eq('owner_id', user_id).order('created_at', desc=True).execute()
        facilities_list = fac_resp.data or []
        stats['facilities'] = len(facilities_list)
        fac_ids = [f['id'] for f in facilities_list]

        if fac_ids:
            # Courts
            court_resp = db.table('courts').select('id, facility_id, name, type, status').in_('facility_id', fac_ids).execute()
            courts_data = court_resp.data or []
            stats['courts'] = len(courts_data)

            # Map court count to facilities
            for f in facilities_list:
                f['court_count'] = sum(1 for c in courts_data if c.get('facility_id') == f['id'])

            # Staff count
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            stats['staff'] = staff_resp.count or 0

            # Revenue and bookings count
            res_resp = db.table('court_reservations').select(
                'id, date, start_time, total_amount, status, created_at, profiles(first_name, last_name, avatar_url), facilities(name)'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).limit(10).execute()
            
            all_res = res_resp.data or []
            stats['total_bookings'] = len(all_res)
            stats['total_revenue'] = sum(float(r.get('total_amount') or 0) for r in all_res if r.get('status') in ['confirmed', 'completed'])

            # Recent activity items
            for r in all_res[:6]:
                p = r.get('profiles') or {}
                player_name = f"{p.get('first_name', 'Player')} {p.get('last_name', '')}".strip()
                fac_name = r.get('facilities', {}).get('name', 'Facility')
                recent_activity.append({
                    'title': f"Booking by {player_name}",
                    'subtitle': f"{fac_name} • ₱{float(r.get('total_amount') or 0):.2f}",
                    'status': r.get('status', 'confirmed'),
                    'date': r.get('date', ''),
                    'time': r.get('start_time', '')[:5] if r.get('start_time') else '',
                    'avatar_url': p.get('avatar_url')
                })

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading owner profile data: {e}")

    return render_template(
        'owner/profile.html',
        stats=stats,
        facilities=facilities_list,
        recent_activity=recent_activity
    )


@owner_bp.route('/change-password', methods=['POST'])
@require_role('owner')
def change_password():
    user_id = session.get('user_id')
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match or are empty.", "error")
        return redirect(url_for('owner.profile'))
    
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for('owner.profile'))
    
    if not old_password:
        flash("Current password is required to set a new password.", "error")
        return redirect(url_for('owner.profile'))
    
    try:
        email = session.get('email', '')
        db = get_db()
        db.auth.sign_in_with_password({"email": email, "password": old_password})
    except Exception:
        flash("Current password is incorrect.", "error")
        return redirect(url_for('owner.profile'))
        
    try:
        admin_db = get_admin_db()
        admin_db.auth.admin.update_user_by_id(user_id, {"password": new_password})
        flash("Password updated successfully.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating password for owner {user_id}: {e}")
        flash("Could not update password. Please try again.", "error")
        
    return redirect(url_for('owner.profile'))


# ── Notifications ───────────────────────────────────────────────────────────────
@owner_bp.route('/notifications')
@require_role('owner')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('owner/notifications.html', notifications=notifs)


@owner_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('owner')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Messages ────────────────────────────────────────────────────────────────────
@owner_bp.route('/messages')
@require_role('owner')
def messages():
    return render_template('owner/messages.html')


# ── Community ───────────────────────────────────────────────────────────────────
@owner_bp.route('/community')
@require_role('owner')
def community():
    return render_template('owner/community.html')


# ── Support ──────────────────────────────────────────────────────────────────────
@owner_bp.route('/support')
@require_role('owner')
def support():
    return render_template('owner/support.html')


# ── Tutorials ────────────────────────────────────────────────────────────────────
@owner_bp.route('/tutorials')
@require_role('owner')
def tutorials():
    return render_template('owner/tutorials.html')

