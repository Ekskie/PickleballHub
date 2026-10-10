from flask import request, redirect, url_for, session, render_template, flash, jsonify
from datetime import datetime, timedelta, timezone
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

PH_TZ = timezone(timedelta(hours=8))


def _format_time_friendly(time_str):
    """Convert '14:00:00' or '14:00' to '2:00 PM'."""
    if not time_str:
        return ''
    try:
        parts = time_str.split(':')
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        ampm = 'AM' if hh < 12 else 'PM'
        display_hh = hh % 12
        if display_hh == 0:
            display_hh = 12
        return f"{display_hh}:{mm:02d} {ampm}"
    except Exception:
        return time_str[:5] if time_str else ''


def _serialize_reservation(r):
    """Normalize and format reservation record for template and JSON consumption."""
    prof = r.get('profiles') or {}
    first = (prof.get('first_name') or '').strip()
    last = (prof.get('last_name') or '').strip()
    full_name = f"{first} {last}".strip()

    if full_name:
        player_name = full_name
        initials = ((first[:1] if first else '') + (last[:1] if last else '')).upper() or 'P'
        is_guest = False
    elif r.get('guest_name'):
        player_name = r['guest_name']
        initials = (player_name[:2]).upper()
        is_guest = True
    else:
        player_name = "Guest Player"
        initials = "GP"
        is_guest = True

    court_info = r.get('courts') or {}
    fac_info = r.get('facilities') or {}

    raw_start = r.get('start_time') or ''
    raw_end = r.get('end_time') or ''

    return {
        'id': r.get('id'),
        'date': r.get('date') or '',
        'start_time': raw_start,
        'end_time': raw_end,
        'start_time_fmt': _format_time_friendly(raw_start),
        'end_time_fmt': _format_time_friendly(raw_end),
        'total_hours': r.get('total_hours') or 1,
        'hourly_rate': r.get('hourly_rate') or 0,
        'total_amount': r.get('total_amount') or 0,
        'status': r.get('status') or 'pending_payment',
        'gcash_ref': r.get('gcash_ref') or '',
        'receipt_url': r.get('receipt_url') or '',
        'created_at': r.get('created_at') or '',
        'player_id': r.get('player_id'),
        'player_name': player_name,
        'player_initials': initials,
        'player_avatar': prof.get('avatar_url'),
        'player_phone': prof.get('phone') or r.get('guest_phone') or '',
        'player_email': prof.get('email') or '',
        'is_guest': is_guest,
        'facility_id': r.get('facility_id'),
        'facility_name': fac_info.get('name') or 'Facility',
        'facility_location': fac_info.get('location') or '',
        'court_id': r.get('court_id'),
        'court_name': court_info.get('name') or 'Court',
        'court_type': court_info.get('type') or 'standard',
    }


# ── Court Schedule Main View ──────────────────────────────────────────────────
@owner_bp.route('/court-schedule')
@owner_bp.route('/schedule')
@require_role('owner')
def court_schedule():
    owner_id = session.get('user_id')
    db = get_admin_db()

    now = datetime.now(PH_TZ)
    today_str = now.strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today_str)

    facilities = []
    courts = []
    all_reservations = []
    bookings_by_date = {}

    stats = {
        'total_bookings': 0,
        'today_bookings': 0,
        'upcoming_bookings': 0,
        'past_bookings': 0,
        'completed_revenue': 0,
    }

    try:
        # 1. Fetch facilities owned by this user
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).order('name').execute()
        facilities = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities]

        if fac_ids:
            # 2. Fetch courts under these facilities
            court_resp = db.table('courts').select('id, name, type, hourly_rate, status, facility_id').in_('facility_id', fac_ids).order('name').execute()
            courts = court_resp.data or []

            # 3. Fetch all court reservations across all owned facilities (including past/historical ones)
            res_resp = db.table('court_reservations').select(
                'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, status, gcash_ref, receipt_url, created_at, '
                'player_id, facility_id, court_id, guest_name, guest_phone, party_size, '
                'profiles(id, first_name, last_name, phone, email, avatar_url), '
                'courts(id, name, type, hourly_rate), '
                'facilities(id, name, location)'
            ).in_('facility_id', fac_ids).order('date', desc=True).order('start_time', desc=False).execute()

            raw_res = res_resp.data or []

            # 4. Serialize and organize into days map
            for raw in raw_res:
                serialized = _serialize_reservation(raw)
                all_reservations.append(serialized)

                b_date = serialized['date']
                if b_date:
                    if b_date not in bookings_by_date:
                        bookings_by_date[b_date] = []
                    bookings_by_date[b_date].append(serialized)

            # 4b. Fetch active event court bookings and map into schedule
            try:
                ev_resp = db.table('events').select(
                    'id, title, type, event_date, start_time, end_time, status, facility_id, facilities(id, name), '
                    'event_courts(court_id, courts(id, name, type, hourly_rate))'
                ).in_('facility_id', fac_ids).in_('status', ['registration_open', 'upcoming', 'full']).execute()
                
                for ev in (ev_resp.data or []):
                    for ec in (ev.get('event_courts') or []):
                        c_info = ec.get('courts') or {}
                        raw_start = ev.get('start_time') or ''
                        raw_end = ev.get('end_time') or ''
                        serialized_ev = {
                            'id': ev['id'],
                            'date': ev.get('event_date') or '',
                            'start_time': raw_start,
                            'end_time': raw_end,
                            'start_time_fmt': _format_time_friendly(raw_start),
                            'end_time_fmt': _format_time_friendly(raw_end),
                            'total_hours': 1,
                            'hourly_rate': c_info.get('hourly_rate') or 0,
                            'total_amount': 0,
                            'status': 'confirmed',
                            'is_event': True,
                            'event_type': ev.get('type'),
                            'gcash_ref': None,
                            'receipt_url': None,
                            'created_at': '',
                            'player_name': f"🏆 {ev.get('title', 'Event')}",
                            'player_initials': 'EV',
                            'is_guest': False,
                            'phone': '',
                            'email': '',
                            'avatar_url': None,
                            'party_size': 16,
                            'court_id': ec.get('court_id'),
                            'court_name': c_info.get('name') or 'Court',
                            'court_type': c_info.get('type') or 'indoor',
                            'facility_id': ev.get('facility_id'),
                            'facility_name': (ev.get('facilities') or {}).get('name') or ''
                        }
                        all_reservations.append(serialized_ev)
                        b_date = serialized_ev['date']
                        if b_date:
                            if b_date not in bookings_by_date:
                                bookings_by_date[b_date] = []
                            bookings_by_date[b_date].append(serialized_ev)
            except Exception as ev_err:
                pass

            # 5. Compute stats
            stats['total_bookings'] = len(all_reservations)
            stats['today_bookings'] = sum(1 for r in all_reservations if r['date'] == today_str)
            stats['upcoming_bookings'] = sum(1 for r in all_reservations if r['date'] > today_str and r['status'] != 'cancelled')
            stats['past_bookings'] = sum(1 for r in all_reservations if r['date'] < today_str or (r['date'] == today_str and r['status'] == 'completed'))
            stats['completed_revenue'] = sum((r['total_amount'] or 0) for r in all_reservations if r['status'] in ['confirmed', 'completed'])

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading court schedule for owner {owner_id}: {e}")
        flash('An error occurred loading the schedule. Please try again.', 'error')

    # Selected date bookings (default to today or requested date)
    selected_date_bookings = bookings_by_date.get(selected_date, [])

    return render_template(
        'owner/court_schedule.html',
        facilities=facilities,
        courts=courts,
        all_reservations=all_reservations,
        bookings_by_date=bookings_by_date,
        selected_date=selected_date,
        selected_date_bookings=selected_date_bookings,
        today_str=today_str,
        stats=stats,
    )


# ── Court Schedule JSON API (for dynamic calendar month browsing & filters) ───
@owner_bp.route('/api/schedule')
@require_role('owner')
def api_schedule():
    owner_id = session.get('user_id')
    db = get_admin_db()

    facility_id = request.args.get('facility_id')
    court_id = request.args.get('court_id')
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    month_filter = request.args.get('month') # YYYY-MM

    try:
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).execute()
        facilities = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities]

        if not fac_ids:
            return jsonify({'success': True, 'bookings': [], 'bookings_by_date': {}, 'total': 0})

        target_fac_ids = [facility_id] if (facility_id and facility_id in fac_ids) else fac_ids

        query = db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, status, gcash_ref, receipt_url, created_at, '
            'player_id, facility_id, court_id, guest_name, guest_phone, party_size, '
            'profiles(id, first_name, last_name, phone, email, avatar_url), '
            'courts(id, name, type, hourly_rate), '
            'facilities(id, name, location)'
        ).in_('facility_id', target_fac_ids)

        if court_id:
            query = query.eq('court_id', court_id)
        if status_filter and status_filter != 'all':
            query = query.eq('status', status_filter)
        if date_filter:
            query = query.eq('date', date_filter)

        res_resp = query.order('date', desc=True).order('start_time', desc=False).execute()
        raw_res = res_resp.data or []

        bookings = []
        bookings_by_date = {}

        for raw in raw_res:
            serialized = _serialize_reservation(raw)
            # If month filter is specified, filter by YYYY-MM prefix
            if month_filter and not serialized['date'].startswith(month_filter):
                continue

            bookings.append(serialized)
            b_date = serialized['date']
            if b_date:
                if b_date not in bookings_by_date:
                    bookings_by_date[b_date] = []
                bookings_by_date[b_date].append(serialized)

        return jsonify({
            'success': True,
            'total': len(bookings),
            'bookings': bookings,
            'bookings_by_date': bookings_by_date,
        })

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error in api_schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
