import logging
from datetime import datetime
from app.db import get_admin_db

logger = logging.getLogger(__name__)

def normalize_time_str(t_str):
    """Normalize time string to HH:MM:SS for safe lexical and logical comparison."""
    if not t_str:
        return '00:00:00'
    parts = str(t_str).strip().split(':')
    if len(parts) == 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
    elif len(parts) >= 3:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2][:2].zfill(2)}"
    return '00:00:00'

def times_overlap(s1, e1, s2, e2):
    """Check if interval [s1, e1) overlaps interval [s2, e2)."""
    norm_s1 = normalize_time_str(s1)
    norm_e1 = normalize_time_str(e1)
    norm_s2 = normalize_time_str(s2)
    norm_e2 = normalize_time_str(e2)
    return norm_s1 < norm_e2 and norm_e1 > norm_s2

def check_court_conflict(db, court_id, date, start_time, end_time, exclude_reservation_id=None, exclude_event_id=None):
    """
    Check if a court is already booked or reserved on the given date and time range.
    Checks BOTH:
      1. Individual player court_reservations (confirmed, pending_payment)
      2. Event court bookings (registration_open, upcoming, full, pending_approval, pending_payment)

    Returns:
      (has_conflict, conflict_info)
      where conflict_info is a dict with details if conflict found, else None.
    """
    # Use provided db if passed, otherwise fall back to admin db
    query_db = db
    if not query_db:
        try:
            query_db = get_admin_db()
        except Exception:
            query_db = None
    if not query_db:
        try:
            query_db = get_db()
        except Exception:
            pass

    target_start = normalize_time_str(start_time)
    target_end   = normalize_time_str(end_time)

    # 1. Check court_reservations
    try:
        res_query = query_db.table('court_reservations').select(
            'id, date, start_time, end_time, status, player_id, profiles(first_name, last_name)'
        ).eq('court_id', court_id).eq('date', date).in_('status', ['confirmed', 'pending_payment'])
        
        if exclude_reservation_id:
            res_query = res_query.neq('id', exclude_reservation_id)

        res_resp = res_query.execute()
        for r in (res_resp.data or []):
            if times_overlap(target_start, target_end, r['start_time'], r['end_time']):
                prof = r.get('profiles') or {}
                player_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip() or 'Player'
                title_lbl = f"Court Reservation ({player_name})"
                return True, {
                    'type': 'reservation',
                    'id': r['id'],
                    'label': title_lbl,
                    'title': title_lbl,
                    'start_time': r['start_time'][:5],
                    'end_time': r['end_time'][:5],
                    'status': r['status']
                }
    except Exception as e:
        logger.error(f"Error checking reservation conflicts for court {court_id}: {e}")

    # 2. Check event_courts + events
    try:
        ec_resp = query_db.table('event_courts').select(
            'event_id, events!inner(id, title, event_date, start_time, end_time, status)'
        ).eq('court_id', court_id).execute()

        for ec in (ec_resp.data or []):
            ev = ec.get('events') or {}
            if not ev:
                continue
            if exclude_event_id and ev.get('id') == exclude_event_id:
                continue
            if ev.get('event_date') != date:
                continue
            if ev.get('status') not in ['upcoming', 'registration_open', 'full', 'pending_approval', 'pending_payment']:
                continue

            if times_overlap(target_start, target_end, ev['start_time'], ev['end_time']):
                title_lbl = f"Event: {ev.get('title', 'Event')}"
                return True, {
                    'type': 'event',
                    'id': ev['id'],
                    'label': title_lbl,
                    'title': title_lbl,
                    'start_time': ev['start_time'][:5],
                    'end_time': ev['end_time'][:5],
                    'status': ev.get('status')
                }
    except Exception as e:
        logger.error(f"Error checking event conflicts for court {court_id}: {e}")

    return False, None


def get_facility_court_timeline(db, facility_id, date, start_time=None, end_time=None, exclude_event_id=None, exclude_reservation_id=None):
    """
    Get all courts in facility along with their occupied time blocks on the specified date.
    Also evaluates availability against target start_time and end_time if provided.
    """
    admin_db = db
    if not admin_db:
        try:
            admin_db = get_admin_db()
        except Exception:
            admin_db = None
    if not admin_db:
        try:
            admin_db = get_db()
        except Exception:
            pass

    courts_resp = admin_db.table('courts').select(
        'id, name, type, hourly_rate, status'
    ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
    courts = courts_resp.data or []

    if not courts:
        return []

    court_ids = [c['id'] for c in courts]

    # Fetch reservations on this date
    reservations_resp = admin_db.table('court_reservations').select(
        'id, court_id, start_time, end_time, status, profiles(first_name, last_name)'
    ).in_('court_id', court_ids).eq('date', date).in_('status', ['confirmed', 'pending_payment']).execute()
    reservations = reservations_resp.data or []

    # Fetch events on this date
    event_courts_resp = admin_db.table('event_courts').select(
        'court_id, event_id, events!inner(id, title, event_date, start_time, end_time, status)'
    ).in_('court_id', court_ids).execute()
    event_courts = event_courts_resp.data or []

    # Filter event courts for date and active statuses
    active_ev_courts = []
    for ec in event_courts:
        ev = ec.get('events') or {}
        if exclude_event_id and ev.get('id') == exclude_event_id:
            continue
        if ev.get('event_date') == date and ev.get('status') in ['upcoming', 'registration_open', 'full', 'pending_approval', 'pending_payment']:
            active_ev_courts.append({
                'court_id': ec['court_id'],
                'event_id': ev['id'],
                'title': ev.get('title', 'Event'),
                'start_time': ev.get('start_time'),
                'end_time': ev.get('end_time'),
                'status': ev.get('status')
            })

    result = []
    for court in courts:
        cid = court['id']
        occupied_blocks = []

        # Add reservation blocks
        for r in reservations:
            if r['court_id'] == cid:
                if exclude_reservation_id and r['id'] == exclude_reservation_id:
                    continue
                prof = r.get('profiles') or {}
                pname = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip() or 'Player'
                title_lbl = f"Reserved ({pname})"
                occupied_blocks.append({
                    'type': 'reservation',
                    'title': title_lbl,
                    'label': title_lbl,
                    'start_time': (r['start_time'] or '')[:5],
                    'end_time': (r['end_time'] or '')[:5],
                    'status': r['status']
                })

        # Add event blocks
        for aec in active_ev_courts:
            if aec['court_id'] == cid:
                title_lbl = f"Event: {aec['title']}"
                occupied_blocks.append({
                    'type': 'event',
                    'title': title_lbl,
                    'label': title_lbl,
                    'start_time': (aec['start_time'] or '')[:5],
                    'end_time': (aec['end_time'] or '')[:5],
                    'status': aec['status']
                })

        # Sort blocks chronologically
        occupied_blocks.sort(key=lambda b: b['start_time'])

        # Check target conflict if start_time & end_time are given
        is_available = True
        conflict_detail = None
        if start_time and end_time:
            for b in occupied_blocks:
                if times_overlap(start_time, end_time, b['start_time'], b['end_time']):
                    is_available = False
                    conflict_detail = b
                    break

        result.append({
            'id': court['id'],
            'name': court['name'],
            'type': court['type'],
            'hourly_rate': float(court.get('hourly_rate') or 0),
            'occupied_blocks': occupied_blocks,
            'is_available': is_available,
            'conflict': conflict_detail
        })

    return result


def notify_facility_staff_and_owner(db, facility_id, title, message, link=None, notif_type='info'):
    """
    Sends in-app notifications to the facility owner and all assigned facility staff.
    """
    if not db:
        db = get_admin_db()

    user_ids = set()
    try:
        # 1. Facility Owner
        fac_resp = db.table('facilities').select('owner_id').eq('id', facility_id).single().execute()
        if fac_resp.data and fac_resp.data.get('owner_id'):
            user_ids.add(fac_resp.data['owner_id'])

        # 2. Facility Staff
        staff_resp = db.table('facility_staff').select('staff_id').eq('facility_id', facility_id).execute()
        for s in (staff_resp.data or []):
            if s.get('staff_id'):
                user_ids.add(s['staff_id'])

        if user_ids:
            notifs = [
                {
                    'user_id': uid,
                    'title': title,
                    'message': message,
                    'type': notif_type,
                    'link': link
                } for uid in user_ids
            ]
            db.table('notifications').insert(notifs).execute()
            logger.info(f"Sent notification to {len(user_ids)} owner/staff users for facility {facility_id}")
    except Exception as e:
        logger.error(f"Failed to notify facility owner and staff for facility {facility_id}: {e}")
