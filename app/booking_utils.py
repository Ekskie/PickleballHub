import logging
import json
import re
from datetime import datetime
from app.db import get_admin_db

logger = logging.getLogger(__name__)

def group_slots_to_ranges(slots):
    """Group list of slot hour integers (e.g. [7, 8, 13, 14]) into contiguous HH:MM ranges."""
    if not slots:
        return []
    sorted_slots = sorted(set(safe_int(s) for s in slots))
    ranges = []
    start = sorted_slots[0]
    prev = sorted_slots[0]
    for s in sorted_slots[1:]:
        if s == prev + 1:
            prev = s
        else:
            ranges.append(f"{start:02d}:00-{prev+1:02d}:00")
            start = s
            prev = s
    ranges.append(f"{start:02d}:00-{prev+1:02d}:00")
    return ranges

def extract_schedule_slots(event):
    """Safely extract schedule_slots list from an event dict, checking column and description payload."""
    if not event:
        return None
    if isinstance(event, dict):
        if event.get('schedule_slots'):
            ss = event['schedule_slots']
            if isinstance(ss, str):
                try:
                    return json.loads(ss)
                except Exception:
                    pass
            elif isinstance(ss, list):
                return ss
        desc = event.get('description') or ''
    elif isinstance(event, str):
        desc = event
    else:
        desc = ''

    if '<!--SCHEDULE_SLOTS:' in desc:
        try:
            raw = desc.split('<!--SCHEDULE_SLOTS:')[1].split('-->')[0]
            return json.loads(raw)
        except Exception:
            return None
    return None

def clean_event_description(desc):
    """Remove embedded metadata from event description for clean UI rendering."""
    if not desc:
        return ''
    return re.sub(r'<!--SCHEDULE_SLOTS:.*?-->', '', str(desc), flags=re.DOTALL).strip()

def inject_schedule_slots_into_desc(desc, schedule_slots):
    """Embed schedule_slots payload into description as HTML comment for persistence without DDL."""
    base_desc = clean_event_description(desc)
    if not schedule_slots:
        return base_desc
    payload = f"<!--SCHEDULE_SLOTS:{json.dumps(schedule_slots)}-->"
    return f"{base_desc}\n\n{payload}".strip()

def safe_int(val, default=0):
    """Safely cast string or object to int, handling empty strings and invalid formats."""
    if val is None:
        return default
    try:
        s = str(val).strip()
        if not s:
            return default
        return int(s)
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    """Safely cast string or object to float, handling empty strings and invalid formats."""
    if val is None:
        return default
    try:
        s = str(val).strip()
        if not s:
            return default
        return float(s)
    except (ValueError, TypeError):
        return default

def safe_time_hours(t_str, default=0.0):
    """
    Safely convert HH:MM or HH:MM:SS string to a float hour representation (e.g. '09:30' or '9:30:00' -> 9.5).
    Immune to missing leading zeros, malformed strings, or NoneType.
    """
    if not t_str:
        return default
    try:
        parts = str(t_str).strip().split(':')
        h = float(parts[0]) if len(parts) > 0 else 0.0
        m = float(parts[1]) if len(parts) > 1 else 0.0
        return h + (m / 60.0)
    except (ValueError, IndexError, TypeError):
        return default

def safe_time_str(t_str, length=5, default="00:00"):
    """
    Safely format or slice time string (e.g. '09:00:00' -> '09:00').
    Immune to NoneType or short strings.
    """
    if not t_str:
        return default
    s = str(t_str).strip()
    return s[:length] if len(s) >= length else s

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

def format_time_12h(t_str):
    """Safely format HH:MM or HH:MM:SS to 12-hour string (e.g., '09:00 AM')."""
    if not t_str:
        return ''
    try:
        parts = str(t_str).strip().split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        ampm = 'AM' if h < 12 else 'PM'
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12:02d}:{m:02d} {ampm}"
    except Exception:
        return str(t_str)

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
                s_raw = safe_time_str(r.get('start_time'))
                e_raw = safe_time_str(r.get('end_time'))
                return True, {
                    'type': 'reservation',
                    'id': r['id'],
                    'label': title_lbl,
                    'title': title_lbl,
                    'start_time': s_raw,
                    'end_time': e_raw,
                    'time_range_12h': f"{format_time_12h(s_raw)} – {format_time_12h(e_raw)}",
                    'status': r['status']
                }
    except Exception as e:
        logger.error(f"Error checking reservation conflicts for court {court_id}: {e}")

    # 2. Check event_courts + events
    try:
        ec_resp = query_db.table('event_courts').select(
            'event_id, events!inner(id, title, event_date, start_time, end_time, status, description)'
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

            # Check if event has per-court schedule slots
            sched_slots = extract_schedule_slots(ev)
            court_sched = None
            if sched_slots:
                for cs in sched_slots:
                    if cs.get('court_id') == court_id:
                        court_sched = cs
                        break

            if court_sched:
                time_ranges = court_sched.get('time_ranges') or []
                if not time_ranges and court_sched.get('slots'):
                    time_ranges = group_slots_to_ranges(court_sched.get('slots'))

                for tr in time_ranges:
                    try:
                        s_part, e_part = tr.split('-')
                        if times_overlap(target_start, target_end, s_part.strip(), e_part.strip()):
                            title_lbl = f"Event: {ev.get('title', 'Event')}"
                            s_raw = safe_time_str(s_part.strip())
                            e_raw = safe_time_str(e_part.strip())
                            return True, {
                                'type': 'event',
                                'id': ev['id'],
                                'label': title_lbl,
                                'title': title_lbl,
                                'start_time': s_raw,
                                'end_time': e_raw,
                                'time_range_12h': f"{format_time_12h(s_raw)} – {format_time_12h(e_raw)}",
                                'status': ev.get('status')
                            }
                    except Exception:
                        continue
                # If this court has explicit schedule slots and none overlapped target, court is FREE during gaps!
                continue

            # Fallback for events with continuous time window
            if times_overlap(target_start, target_end, ev['start_time'], ev['end_time']):
                title_lbl = f"Event: {ev.get('title', 'Event')}"
                s_raw = safe_time_str(ev.get('start_time'))
                e_raw = safe_time_str(ev.get('end_time'))
                return True, {
                    'type': 'event',
                    'id': ev['id'],
                    'label': title_lbl,
                    'title': title_lbl,
                    'start_time': s_raw,
                    'end_time': e_raw,
                    'time_range_12h': f"{format_time_12h(s_raw)} – {format_time_12h(e_raw)}",
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
    admin_db = None
    try:
        from app.db import get_admin_db
        admin_db = get_admin_db()
    except Exception:
        admin_db = None
    if not admin_db:
        admin_db = db

    courts_resp = admin_db.table('courts').select(
        'id, name, type, hourly_rate, status'
    ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
    courts = courts_resp.data or []

    if not courts:
        return []

    fac_info = None
    try:
        fac_resp = admin_db.table('facilities').select('id, name, open_time, close_time, slot_duration_minutes').eq('id', facility_id).execute()
        fac_info = fac_resp.data[0] if (fac_resp and fac_resp.data) else None
    except Exception:
        fac_info = None

    court_ids = [c['id'] for c in courts]

    # Fetch reservations on this date
    reservations_resp = admin_db.table('court_reservations').select(
        'id, court_id, start_time, end_time, status, profiles(first_name, last_name)'
    ).in_('court_id', court_ids).eq('date', date).in_('status', ['confirmed', 'pending_payment']).execute()
    reservations = reservations_resp.data or []

    # Fetch events on this date
    event_courts_resp = admin_db.table('event_courts').select(
        'court_id, event_id, events!inner(id, title, event_date, start_time, end_time, status, description)'
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
                'status': ev.get('status'),
                'schedule_slots': extract_schedule_slots(ev)
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
                s_block = (r['start_time'] or '')[:5]
                e_block = (r['end_time'] or '')[:5]
                occupied_blocks.append({
                    'type': 'reservation',
                    'title': title_lbl,
                    'label': title_lbl,
                    'start_time': s_block,
                    'end_time': e_block,
                    'time_range_12h': f"{format_time_12h(s_block)} – {format_time_12h(e_block)}",
                    'status': r['status']
                })

        # Add event blocks
        for aec in active_ev_courts:
            if aec['court_id'] == cid:
                sched_slots = aec.get('schedule_slots')
                court_sched = None
                if sched_slots:
                    for cs in sched_slots:
                        if cs.get('court_id') == cid:
                            court_sched = cs
                            break

                if court_sched:
                    time_ranges = court_sched.get('time_ranges') or []
                    if not time_ranges and court_sched.get('slots'):
                        time_ranges = group_slots_to_ranges(court_sched.get('slots'))

                    for tr in time_ranges:
                        try:
                            s_p, e_p = tr.split('-')
                            s_block = s_p.strip()[:5]
                            e_block = e_p.strip()[:5]
                            title_lbl = f"Event: {aec['title']}"
                            occupied_blocks.append({
                                'type': 'event',
                                'title': title_lbl,
                                'label': title_lbl,
                                'start_time': s_block,
                                'end_time': e_block,
                                'time_range_12h': f"{format_time_12h(s_block)} – {format_time_12h(e_block)}",
                                'status': aec['status']
                            })
                        except Exception:
                            continue
                else:
                    title_lbl = f"Event: {aec['title']}"
                    s_block = (aec['start_time'] or '')[:5]
                    e_block = (aec['end_time'] or '')[:5]
                    occupied_blocks.append({
                        'type': 'event',
                        'title': title_lbl,
                        'label': title_lbl,
                        'start_time': s_block,
                        'end_time': e_block,
                        'time_range_12h': f"{format_time_12h(s_block)} – {format_time_12h(e_block)}",
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
            'conflict': conflict_detail,
            'facility_open': (fac_info.get('open_time') or '06:00')[:5] if fac_info else '06:00',
            'facility_close': (fac_info.get('close_time') or '22:00')[:5] if fac_info else '22:00',
        })

    return result


def get_facility_month_availability_data(db, facility_id, year, month, exclude_event_id=None):
    """
    Return daily aggregated availability (status, remaining_slots, total_slots) for a facility across a month.
    Used by interactive calendars in player reservation, owner event creation, and clubadmin event creation.
    """
    import calendar
    admin_db = None
    try:
        from app.db import get_admin_db
        admin_db = get_admin_db()
    except Exception:
        admin_db = None
    if not admin_db:
        admin_db = db

    if not facility_id or not year or not month:
        return {'success': False, 'error': 'Missing parameters'}

    try:
        num_days = calendar.monthrange(year, month)[1]
        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{num_days:02d}"

        fac_resp = admin_db.table('facilities').select('id, name, open_time, close_time').eq('id', facility_id).execute()
        fac = fac_resp.data[0] if (fac_resp and fac_resp.data) else {}

        open_time = str(fac.get('open_time') or '06:00')[:5]
        close_time = str(fac.get('close_time') or '22:00')[:5]

        open_h = int(open_time.split(':')[0]) if ':' in open_time else 6
        close_h = int(close_time.split(':')[0]) if ':' in close_time else 22
        if close_h == 0 or close_h <= open_h:
            close_h = 24
        operating_hours = max(1, close_h - open_h)

        courts_resp = admin_db.table('courts').select('id, name').eq('facility_id', facility_id).eq('status', 'active').execute()
        court_ids = [c['id'] for c in (courts_resp.data or [])]
        total_courts = len(court_ids)

        if total_courts == 0:
            days = {}
            for d in range(1, num_days + 1):
                d_str = f"{year:04d}-{month:02d}-{d:02d}"
                days[d_str] = {'status': 'full', 'remaining_slots': 0, 'total_slots': 0, 'booked_slots': 0}
            return {
                'success': True,
                'total_courts': 0,
                'days': days,
                'open_hour': open_h,
                'close_hour': close_h,
                'open_time': open_time,
                'close_time': close_time
            }

        total_court_slots_per_day = operating_hours * total_courts

        # Query all reservations in this month
        res_resp = admin_db.table('court_reservations').select(
            'court_id, date, start_time, end_time, total_hours'
        ).in_('court_id', court_ids).gte('date', start_date).lte('date', end_date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        reservations = res_resp.data or []

        bookings_by_date = {}
        for r in reservations:
            d = r.get('date')
            if d:
                hrs = float(r.get('total_hours') or 1)
                bookings_by_date[d] = bookings_by_date.get(d, 0) + hrs

        # Query all event court bookings in this month
        try:
            ec_resp = admin_db.table('event_courts').select(
                'court_id, events!inner(id, event_date, start_time, end_time, status, description)'
            ).in_('court_id', court_ids).execute()

            for ec in (ec_resp.data or []):
                ev = ec.get('events') or {}
                if exclude_event_id and ev.get('id') == exclude_event_id:
                    continue
                ed = ev.get('event_date')
                if ed and start_date <= ed <= end_date and ev.get('status') in ['upcoming', 'registration_open', 'full', 'pending_approval', 'pending_payment']:
                    cid = ec.get('court_id')
                    sched_slots = extract_schedule_slots(ev)
                    court_sched = None
                    if sched_slots:
                        for cs in sched_slots:
                            if cs.get('court_id') == cid:
                                court_sched = cs
                                break

                    if court_sched and court_sched.get('slots'):
                        hrs = float(len(court_sched['slots']))
                    else:
                        try:
                            st = ev.get('start_time') or '08:00'
                            et = ev.get('end_time') or '10:00'
                            sh = int(str(st)[:2]) + int(str(st)[3:5])/60.0
                            eh = int(str(et)[:2]) + int(str(et)[3:5])/60.0
                            hrs = max(1.0, eh - sh)
                        except Exception:
                            hrs = 2.0
                    bookings_by_date[ed] = bookings_by_date.get(ed, 0) + hrs
        except Exception as e_ev:
            logger.warning(f"[get_facility_month_availability_data] event query error: {e_ev}")

        days = {}
        for d in range(1, num_days + 1):
            d_str = f"{year:04d}-{month:02d}-{d:02d}"
            booked_slots = bookings_by_date.get(d_str, 0)
            remaining_slots = max(0, total_court_slots_per_day - booked_slots)

            if booked_slots == 0:
                status = 'available'
            elif remaining_slots == 0:
                status = 'full'
            elif remaining_slots <= total_court_slots_per_day * 0.35:
                status = 'limited'
            else:
                status = 'available'

            days[d_str] = {
                'status': status,
                'remaining_slots': int(remaining_slots),
                'total_slots': total_court_slots_per_day,
                'booked_slots': int(booked_slots)
            }

        return {
            'success': True,
            'year': year,
            'month': month,
            'total_courts': total_courts,
            'open_hour': open_h,
            'close_hour': close_h,
            'open_time': open_time,
            'close_time': close_time,
            'days': days
        }
    except Exception as e:
        logger.error(f"[get_facility_month_availability_data] error: {e}")
        return {'success': False, 'error': str(e)}


def notify_facility_staff_and_owner(db, facility_id, title, message, link=None, notif_type='info'):
    """
    Sends in-app notifications to the facility owner and all assigned facility staff.
    Uses admin_db to ensure delivery across Supabase Row-Level Security policies.
    """
    admin_db = get_admin_db() or db

    user_ids = set()
    try:
        # 1. Facility Owner
        fac_resp = admin_db.table('facilities').select('owner_id').eq('id', facility_id).single().execute()
        if fac_resp.data and fac_resp.data.get('owner_id'):
            user_ids.add(fac_resp.data['owner_id'])

        # 2. Facility Staff
        staff_resp = admin_db.table('facility_staff').select('staff_id').eq('facility_id', facility_id).execute()
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
            admin_db.table('notifications').insert(notifs).execute()
            logger.info(f"Sent notification to {len(user_ids)} owner/staff users for facility {facility_id}")
    except Exception as e:
        logger.error(f"Failed to notify facility owner and staff for facility {facility_id}: {e}")
