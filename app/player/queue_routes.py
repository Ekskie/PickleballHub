from flask import render_template, session
from app.decorators import require_role
from datetime import datetime, timedelta
from app.db import get_db
from app.player import player_bp
from app.player.routes import PH_TZ

def get_processed_queues(db, player_id=None):
    """Fetch queues for today, process wait times, and auto-complete games 15 mins past end time."""
    try:
        resp = db.table('court_queues').select(
            'id, status, estimated_wait_mins, joined_at, player_id, facility_id, '
            'courts(name), profiles(first_name, last_name, avatar_url), '
            'facilities(id, name), '
            'court_reservations!inner(id, date, start_time, end_time)'
        ).in_('status', ['waiting', 'next', 'playing']).order('joined_at').execute()
        raw_queues = resp.data or []
    except Exception as e:
        print("Error fetching queues:", e)
        return [], None, {}
        
    today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
    now = datetime.now(PH_TZ)
    queues = []
    my_queue = None
    
    # Process each queue item
    for q in raw_queues:
        res = q.get('court_reservations')
        if not res or res.get('date') != today_str:
            continue
            
        start_time_str = f"{today_str} {res.get('start_time')}"
        end_time_str = f"{today_str} {res.get('end_time')}"
        try:
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
        except ValueError:
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)

        # Auto-complete if they are 'playing' and 15 mins past end time
        if q['status'] == 'playing' and now > (end_dt + timedelta(minutes=15)):
            try:
                db.table('court_queues').update({'status': 'completed'}).eq('id', q['id']).execute()
            except Exception:
                pass
            continue
            
        # Calculate dynamic wait time or time remaining
        if q['status'] in ['waiting', 'next']:
            wait_mins = int((start_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, wait_mins)
            q['time_type'] = 'Wait'
            q['target_time'] = start_dt.isoformat()
        elif q['status'] == 'playing':
            rem_mins = int((end_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, rem_mins)
            q['time_type'] = 'Remaining'
            q['target_time'] = end_dt.isoformat()

        # Human-friendly formatted relative time (e.g., ~6h 48m instead of raw 408 min)
        mins = q.get('estimated_wait_mins', 0)
        if mins >= 60:
            h = mins // 60
            m = mins % 60
            q['formatted_wait'] = f"~{h}h {m}m" if m > 0 else f"~{h}h"
        elif mins > 0:
            q['formatted_wait'] = f"~{mins} min"
        else:
            q['formatted_wait'] = "Ready now" if q['status'] != 'playing' else "< 1 min left"

        try:
            q['start_time_fmt'] = start_dt.strftime('%I:%M %p').lstrip('0')
            q['end_time_fmt'] = end_dt.strftime('%I:%M %p').lstrip('0')
            q['slot_time_str'] = f"{q['start_time_fmt']} - {q['end_time_fmt']}"
        except Exception:
            q['start_time_fmt'] = str(res.get('start_time', ''))
            q['end_time_fmt'] = str(res.get('end_time', ''))
            q['slot_time_str'] = q['start_time_fmt']
            
        queues.append(q)

    # Sort queues: Playing first, then Next, then Waiting
    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), x.get('court_reservations', {}).get('start_time', '')))

    # Group by facility and assign per-facility positions
    facilities_queues = {}  # {facility_id: {'facility_id': ..., 'facility_name': ..., 'queues': [...], 'my_queue': None}}
    
    pos_by_facility = {}
    for q in queues:
        fac = q.get('facilities') or {}
        fac_id = q.get('facility_id') or fac.get('id') or 'unknown'
        fac_name = fac.get('name') or 'Unknown Facility'
        
        if fac_id not in facilities_queues:
            facilities_queues[fac_id] = {
                'facility_id': fac_id,
                'facility_name': fac_name,
                'queues': [],
                'my_queue': None,
                'waiting_count': 0,
                'next_count': 0,
                'playing_count': 0,
                'courts_set': set(),
            }
            pos_by_facility[fac_id] = 1
        
        # Track facility stats
        if q['status'] == 'playing':
            facilities_queues[fac_id]['playing_count'] += 1
        elif q['status'] == 'next':
            facilities_queues[fac_id]['next_count'] += 1
        else:
            facilities_queues[fac_id]['waiting_count'] += 1

        if q.get('courts') and q['courts'].get('name'):
            facilities_queues[fac_id]['courts_set'].add(q['courts']['name'])

        # Assign per-facility position
        if q['status'] != 'playing':
            q['position'] = pos_by_facility[fac_id]
            pos_by_facility[fac_id] += 1
        else:
            q['position'] = '-'
        
        if q['player_id'] == player_id:
            my_queue = q
            facilities_queues[fac_id]['my_queue'] = q
        
        facilities_queues[fac_id]['queues'].append(q)

    # Post-process facility sets to counts for template safety
    for fac_id, f_data in facilities_queues.items():
        f_data['courts_count'] = len(f_data.get('courts_set', set())) or 1

    # Also build flat list with global positions for backwards compat
    pos = 1
    for q in queues:
        if q['status'] != 'playing':
            q['global_position'] = pos
            pos += 1
        else:
            q['global_position'] = '-'
            
    return queues, my_queue, facilities_queues


@player_bp.route('/queue')
@require_role('player')
def queue():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue, facilities_queues = get_processed_queues(db, player_id)
    return render_template('player/queue_monitoring.html', queues=queues, my_queue=my_queue, facilities_queues=facilities_queues)


@player_bp.route('/queue/partial')
@require_role('player')
def queue_partial():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue, facilities_queues = get_processed_queues(db, player_id)
    return render_template('player/partials/queue_content.html', queues=queues, my_queue=my_queue, facilities_queues=facilities_queues)
