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
    db = get_db()

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

            # All confirmed/completed reservations
            res_resp = db.table('court_reservations').select(
                'id, total_amount, date, start_time, end_time, status, '
                'profiles(first_name, last_name), courts(name, type), facility_id'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            reservations = res_resp.data or []

            paid = [r for r in reservations if r['status'] in ['confirmed', 'completed']]
            total_bookings = len(reservations)
            total_earnings = sum((r.get('total_amount') or 0) for r in paid)
            today_earnings = sum((r.get('total_amount') or 0) for r in paid if r.get('date') == today_str)

            # Recent bookings (top 6)
            recent_bookings = reservations[:6]

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

            # Revenue per facility
            for f in facilities_data:
                frev = sum((r.get('total_amount') or 0) for r in paid if r.get('facility_id') == f['id'])
                fbookings = sum(1 for r in reservations if r.get('facility_id') == f['id'])
                facility_revenue.append({'name': f['name'], 'revenue': round(frev, 2), 'bookings': fbookings})

            # Staff count
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            active_staff = staff_resp.count or 0

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Owner dashboard error: {e}")

    return render_template(
        'owner/dashboard.html',
        total_earnings=total_earnings,
        today_earnings=today_earnings,
        total_bookings=total_bookings,
        active_staff=active_staff,
        recent_bookings=recent_bookings,
        revenue_chart=revenue_chart,
        facility_revenue=facility_revenue,
    )


# ── Profile ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/profile', methods=['GET', 'POST'])
@require_role('owner')
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
        return redirect(url_for('owner.profile'))

    stats = {'facilities': 0, 'courts': 0, 'staff': 0}
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', user_id).execute()
        fac_data = fac_resp.data or []
        stats['facilities'] = len(fac_data)
        
        court_resp = db.table('courts').select('id').eq('owner_id', user_id).execute()
        stats['courts'] = len(court_resp.data or [])
        
        fac_ids = [f['id'] for f in fac_data]
        if fac_ids:
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            stats['staff'] = staff_resp.count or 0
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error getting owner profile stats: {e}")

    return render_template('owner/profile.html', stats=stats)


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
