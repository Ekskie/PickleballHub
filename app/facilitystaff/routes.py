from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))
from datetime import datetime, timedelta, timezone

from app.db import get_db, get_admin_db



facilitystaff_bp = Blueprint('facilitystaff', __name__, url_prefix='/facilitystaff')

@facilitystaff_bp.route('/dashboard')
@require_role('facilitystaff')
def dashboard():
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    court_status_list = []
    disputed_lobbies = []
    facility_name = "Siniloan Multi-Purpose Sports Hub"
    
    stats = {
        'total_courts': 0,
        'available_courts': 0,
        'in_use_courts': 0,
        'maintenance_courts': 0,
        'waiting_count': 0,
        'next_count': 0,
        'queue_total': 0
    }
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(id, name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if assigned_facilities:
            fac_obj = assigned_facilities[0].get('facilities')
            if fac_obj and isinstance(fac_obj, dict):
                facility_name = fac_obj.get('name') or facility_name
        
        if fac_ids:
            # Get courts
            c_resp = db.table('courts').select('*').in_('facility_id', fac_ids).order('name').execute()
            courts = c_resp.data or []
            
            # Get active queues
            queues = get_staff_processed_queues(db, fac_ids)
            
            # Get matchmaker lobbies in staff mediation for these facilities
            try:
                lob_resp = db.table('matchmaker_lobbies').select(
                    'id, title, status, reported_score, creator_id, created_at, reservation_id, '
                    'creator:profiles!creator_id(first_name, last_name), '
                    'court_reservations!reservation_id(facility_id, date, start_time, end_time, courts(name), facilities(name))'
                ).eq('status', 'staff_mediation').execute()
                
                raw_disputed = lob_resp.data or []
                for lob in raw_disputed:
                    res = lob.get('court_reservations') or {}
                    if res.get('facility_id') in fac_ids:
                        creator = lob.get('creator') or {}
                        court = res.get('courts') or {}
                        fac = res.get('facilities') or {}
                        disputed_lobbies.append({
                            'id': lob['id'],
                            'title': lob['title'],
                            'reported_score': lob.get('reported_score') or '—',
                            'creator_name': f"{creator.get('first_name','')} {creator.get('last_name','')}".strip() or "Host",
                            'facility_name': fac.get('name', 'Facility'),
                            'court_name': court.get('name', 'Court'),
                            'date': res.get('date') or '',
                            'time': f"{res.get('start_time')[:5]} - {res.get('end_time')[:5]}" if res.get('start_time') else ''
                        })
            except Exception as lob_err:
                print(f"Error fetching disputed lobbies: {lob_err}")
            
            # Calculate live court status
            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            
            # Fetch today's reservations for these courts
            res_resp = db.table('court_reservations').select(
                'id, court_id, date, start_time, end_time, status, player_id, guest_name, profiles(first_name, last_name, avatar_url)'
            ).in_('court_id', [c['id'] for c in courts]).eq('date', today_str).in_('status', ['confirmed', 'completed']).execute()
            reservations = res_resp.data or []
            
            # For each court, determine if it is currently in use
            for c in courts:
                status = 'Available'
                status_color = 'positive'
                sub_text = 'Ready'
                current_player = None
                current_player_avatar = None
                start_time_fmt = None
                end_time_fmt = None
                next_booking_fmt = None
                rem_mins = 0
                
                if c.get('status') == 'maintenance':
                    status = 'Maintenance'
                    status_color = 'warning'
                    sub_text = 'Unavailable'
                else:
                    # Check reservations
                    for r in reservations:
                        if r['court_id'] == c['id'] and r['status'] == 'confirmed':
                            s_raw = r.get('start_time') or '00:00:00'
                            e_raw = r.get('end_time') or '00:00:00'
                            start_time_str = f"{today_str} {s_raw}"
                            end_time_str = f"{today_str} {e_raw}"
                            try:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            except ValueError:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            
                            if start_dt <= now <= end_dt:
                                status = 'In Use'
                                status_color = 'negative'
                                rem_mins = max(0, int((end_dt - now).total_seconds() / 60))
                                sub_text = f"Ends in {rem_mins}m"
                                prof = r.get('profiles') or {}
                                if prof and (prof.get('first_name') or prof.get('last_name')):
                                    current_player = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
                                    current_player_avatar = prof.get('avatar_url')
                                else:
                                    current_player = r.get('guest_name') or 'Walk-in Guest'
                                start_time_fmt = s_raw[:5]
                                end_time_fmt = e_raw[:5]
                                break
                            elif start_dt > now:
                                diff_mins = int((start_dt - now).total_seconds() / 60)
                                if not next_booking_fmt:
                                    next_booking_fmt = f"{s_raw[:5]} - {e_raw[:5]}"
                                if status == 'Available' and diff_mins < 60:
                                    sub_text = f"Next in {diff_mins}m"
                                    
                court_status_list.append({
                    'id': c['id'],
                    'name': c['name'],
                    'type': c.get('type') or 'Pickleball',
                    'hourly_rate': float(c.get('hourly_rate') or 0.0),
                    'status': status,
                    'color': status_color,
                    'sub_text': sub_text,
                    'current_player': current_player or 'Match in Progress',
                    'current_player_avatar': current_player_avatar,
                    'start_time': start_time_fmt,
                    'end_time': end_time_fmt,
                    'remaining_mins': rem_mins,
                    'next_booking': next_booking_fmt
                })
                
            stats = {
                'total_courts': len(courts),
                'available_courts': sum(1 for c in court_status_list if c['status'] == 'Available'),
                'in_use_courts': sum(1 for c in court_status_list if c['status'] == 'In Use'),
                'maintenance_courts': sum(1 for c in court_status_list if c['status'] == 'Maintenance'),
                'waiting_count': sum(1 for q in queues if q['status'] == 'waiting'),
                'next_count': sum(1 for q in queues if q['status'] == 'next'),
                'queue_total': len(queues)
            }
                
    except Exception as e:
        flash(f'An error occurred. Please try again: {e}', 'error')
        
    return render_template('facilitystaff/dashboard.html', 
                           facility_name=facility_name,
                           facilities=assigned_facilities,
                           courts=courts,
                           court_status_list=court_status_list, 
                           queues=queues, 
                           disputed_lobbies=disputed_lobbies,
                           stats=stats)

def get_staff_processed_queues(db, fac_ids):
    if not fac_ids:
        return []
    try:
        resp = db.table('court_queues').select(
            'id, facility_id, court_id, status, estimated_wait_mins, joined_at, player_id, guest_name, party_size, reservation_id, profiles(first_name, last_name, avatar_url, phone), court_reservations(date, start_time, end_time), courts(id, name)'
        ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next', 'playing']).order('joined_at').execute()
        raw_queues = resp.data or []
    except Exception as e:
        print("Error fetching queues:", e)
        return []
        
    today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
    now = datetime.now(PH_TZ)
    queues = []
    
    for q in raw_queues:
        res = q.get('court_reservations')
        if isinstance(res, list):
            res = res[0] if res else None
            
        if res and res.get('date') == today_str:
            start_time_str = f"{today_str} {res.get('start_time')}"
            end_time_str = f"{today_str} {res.get('end_time')}"
            try:
                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            except ValueError:
                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
        else:
            joined_at_str = q.get('joined_at') or ''
            if not joined_at_str.startswith(today_str) and not joined_at_str.startswith(today_str.replace('-', '')):
                continue
            start_dt = now
            end_dt = now + timedelta(hours=1)

        if q['status'] == 'playing' and now > (end_dt + timedelta(minutes=15)):
            try:
                db.table('court_queues').update({'status': 'completed'}).eq('id', q['id']).execute()
            except Exception:
                pass
            continue
            
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

        # Compute display attributes
        prof = q.get('profiles') or {}
        full_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
        guest_name = q.get('guest_name') or ''
        if full_name:
            q['display_name'] = full_name
            q['is_walkin'] = False
        elif guest_name:
            q['display_name'] = guest_name
            q['is_walkin'] = True
        else:
            q['display_name'] = 'Walk-in Guest' if not q.get('player_id') else 'Player'
            q['is_walkin'] = not bool(q.get('player_id'))

        court_obj = q.get('courts') or {}
        q['assigned_court_name'] = court_obj.get('name') or 'Auto / Unassigned'
        q['party_size'] = q.get('party_size') or 1
            
        queues.append(q)

    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), (x.get('court_reservations') or {}).get('start_time', '')))
    return queues


@facilitystaff_bp.route('/queue')
@require_role('facilitystaff')
def queue():
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    court_status_list = []
    facility_name = "Siniloan Multi-Purpose Sports Hub"
    
    try:
        # 1. Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(id, name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if assigned_facilities:
            fac_obj = assigned_facilities[0].get('facilities')
            if fac_obj and isinstance(fac_obj, dict):
                facility_name = fac_obj.get('name') or facility_name
        
        if fac_ids:
            # 2. Get courts for these facilities
            c_resp = db.table('courts').select('id, name, facility_id, hourly_rate, status, type').in_('facility_id', fac_ids).order('name').execute()
            courts = c_resp.data or []
            
            # 3. Get active queue items
            queues = get_staff_processed_queues(db, fac_ids)
            
            # 4. Court status for the quick availability strip
            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            res_resp = db.table('court_reservations').select('court_id, start_time, end_time, status').in_('court_id', [c['id'] for c in courts]).eq('date', today_str).in_('status', ['confirmed', 'completed']).execute()
            reservations = res_resp.data or []
            
            for c in courts:
                c_status = 'Available'
                c_color = 'positive'
                c_sub = 'Ready'
                if c.get('status') == 'maintenance':
                    c_status = 'Maintenance'
                    c_color = 'warning'
                    c_sub = 'Unavailable'
                else:
                    for r in reservations:
                        if r['court_id'] == c['id'] and r['status'] == 'confirmed':
                            s_raw = r.get('start_time') or '00:00:00'
                            e_raw = r.get('end_time') or '00:00:00'
                            try:
                                s_dt = datetime.strptime(f"{today_str} {s_raw}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                                e_dt = datetime.strptime(f"{today_str} {e_raw}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            except ValueError:
                                s_dt = datetime.strptime(f"{today_str} {s_raw}", '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                                e_dt = datetime.strptime(f"{today_str} {e_raw}", '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            if s_dt <= now <= e_dt:
                                c_status = 'In Use'
                                c_color = 'negative'
                                rem = max(0, int((e_dt - now).total_seconds() / 60))
                                c_sub = f"Ends in {rem}m"
                                break
                court_status_list.append({
                    'id': c['id'],
                    'name': c['name'],
                    'status': c_status,
                    'color': c_color,
                    'sub_text': c_sub,
                    'hourly_rate': float(c.get('hourly_rate') or 0.0)
                })
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    queue_stats = {
        'total_waiting': sum(1 for q in queues if q['status'] == 'waiting'),
        'total_next': sum(1 for q in queues if q['status'] == 'next'),
        'total_playing': sum(1 for q in queues if q['status'] == 'playing'),
        'total_active': len(queues),
        'available_courts': sum(1 for c in court_status_list if c['status'] == 'Available')
    }
        
    return render_template('facilitystaff/queue.html', 
                           facilities=assigned_facilities, 
                           facility_name=facility_name,
                           courts=courts, 
                           court_status_list=court_status_list,
                           queues=queues,
                           queue_stats=queue_stats)

@facilitystaff_bp.route('/queue/partial')
@require_role('facilitystaff')
def queue_partial():
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    court_status_list = []
    
    try:
        fs_resp = db.table('facility_staff').select('facility_id, facilities(id, name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id, hourly_rate, status, type').in_('facility_id', fac_ids).order('name').execute()
            courts = c_resp.data or []
            queues = get_staff_processed_queues(db, fac_ids)
            
            # Court status for strip
            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            res_resp = db.table('court_reservations').select('court_id, start_time, end_time, status').in_('court_id', [c['id'] for c in courts]).eq('date', today_str).in_('status', ['confirmed', 'completed']).execute()
            reservations = res_resp.data or []
            
            for c in courts:
                c_status = 'Available'
                c_color = 'positive'
                c_sub = 'Ready'
                if c.get('status') == 'maintenance':
                    c_status = 'Maintenance'
                    c_color = 'warning'
                    c_sub = 'Unavailable'
                else:
                    for r in reservations:
                        if r['court_id'] == c['id'] and r['status'] == 'confirmed':
                            s_raw = r.get('start_time') or '00:00:00'
                            e_raw = r.get('end_time') or '00:00:00'
                            try:
                                s_dt = datetime.strptime(f"{today_str} {s_raw}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                                e_dt = datetime.strptime(f"{today_str} {e_raw}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            except ValueError:
                                s_dt = datetime.strptime(f"{today_str} {s_raw}", '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                                e_dt = datetime.strptime(f"{today_str} {e_raw}", '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            if s_dt <= now <= e_dt:
                                c_status = 'In Use'
                                c_color = 'negative'
                                rem = max(0, int((e_dt - now).total_seconds() / 60))
                                c_sub = f"Ends in {rem}m"
                                break
                court_status_list.append({
                    'id': c['id'],
                    'name': c['name'],
                    'status': c_status,
                    'color': c_color,
                    'sub_text': c_sub,
                    'hourly_rate': float(c.get('hourly_rate') or 0.0)
                })
    except Exception as e:
        print("Error in queue_partial:", e)
        
    queue_stats = {
        'total_waiting': sum(1 for q in queues if q['status'] == 'waiting'),
        'total_next': sum(1 for q in queues if q['status'] == 'next'),
        'total_playing': sum(1 for q in queues if q['status'] == 'playing'),
        'total_active': len(queues),
        'available_courts': sum(1 for c in court_status_list if c['status'] == 'Available')
    }

    if request.args.get('format') == 'json':
        table_html = render_template('facilitystaff/partials/queue_content.html', facilities=assigned_facilities, courts=courts, queues=queues)
        return jsonify({
            'success': True,
            'html': table_html,
            'stats': queue_stats,
            'court_status_list': court_status_list
        })
        
    return render_template('facilitystaff/partials/queue_content.html', facilities=assigned_facilities, courts=courts, queues=queues)


@facilitystaff_bp.route('/player/<player_id>/details')
@require_role('facilitystaff')
def player_details(player_id):
    db = get_db()
    try:
        # Fetch profile details
        prof_resp = db.table('profiles').select('*').eq('id', player_id).single().execute()
        profile = prof_resp.data
        if not profile:
            return "<div style='text-align:center; padding: 30px; color: var(--text-muted);'><p>Player profile not found.</p></div>", 404
        
        # Calculate stats
        wins = profile.get('wins') or 0
        losses = profile.get('losses') or 0
        total_played = wins + losses
        win_rate = round((wins / total_played) * 100) if total_played > 0 else 0
        stats = {
            'wins': wins,
            'losses': losses,
            'total_played': total_played,
            'win_rate': win_rate
        }

        # Fetch matches (up to 5)
        player_matches = []
        try:
            # 1. Completed tournament matches
            matches_resp = db.table('tournament_matches').select(
                'id, event_id, player1_score, player2_score, winner_id, status, played_at, player1_id, player2_id, '
                'player1:profiles!player1_id(id, first_name, last_name), '
                'player2:profiles!player2_id(id, first_name, last_name), '
                'events(title)'
            ).or_(f"player1_id.eq.{player_id},player2_id.eq.{player_id}").eq('status', 'completed').order('played_at', desc=True).limit(5).execute()
            
            raw_matches = matches_resp.data or []
            for m in raw_matches:
                is_p1 = m.get('player1_id') == player_id
                opponent = m.get('player2') if is_p1 else m.get('player1')
                opp_name = f"{opponent.get('first_name', '')} {opponent.get('last_name', '')}".strip() if opponent else "Unknown Opponent"
                
                my_score = m.get('player1_score') if is_p1 else m.get('player2_score')
                opp_score = m.get('player2_score') if is_p1 else m.get('player1_score')
                
                result = "WIN" if m.get('winner_id') == player_id else "LOSS"
                if m.get('winner_id') is None:
                    result = "DRAW"
                    
                player_matches.append({
                    'event_title': m.get('events', {}).get('title', 'Tournament Match') if m.get('events') else 'Tournament Match',
                    'opponent_name': opp_name,
                    'score': f"{my_score} - {opp_score}" if my_score is not None and opp_score is not None else "N/A",
                    'result': result,
                    'played_at': m.get('played_at')
                })

            # 2. Completed matchmaking lobbies
            raw_lobbies = []
            creator_lobbies = db.table('matchmaker_lobbies').select(
                'id, title, score, winner_id, creator_id, created_at, '
                'creator:profiles!creator_id(id, first_name, last_name)'
            ).eq('creator_id', player_id).eq('status', 'completed').limit(5).execute()
            if creator_lobbies.data:
                raw_lobbies.extend(creator_lobbies.data)

            joined_lobbies = db.table('lobby_participants').select(
                'lobby_id, lobby:matchmaker_lobbies!lobby_id(id, title, score, winner_id, creator_id, created_at, creator:profiles!creator_id(id, first_name, last_name))'
            ).eq('player_id', player_id).eq('status', 'joined').execute()
            
            if joined_lobbies.data:
                for item in joined_lobbies.data:
                    lobby_data = item.get('lobby')
                    if lobby_data and lobby_data.get('status') == 'completed':
                        if not any(x['id'] == lobby_data['id'] for x in raw_lobbies):
                            raw_lobbies.append(lobby_data)

            for lob in raw_lobbies[:5]:
                lob_id = lob['id']
                opponent_name = "Unknown Player"
                
                if lob.get('creator_id') == player_id:
                    part_resp = db.table('lobby_participants').select(
                        'player_id, profiles!player_id(first_name, last_name)'
                    ).eq('lobby_id', lob_id).eq('status', 'joined').execute()
                    
                    if part_resp.data:
                        opp_profile = None
                        for p in part_resp.data:
                            if p.get('player_id') != player_id:
                                opp_profile = p.get('profiles') or {}
                                break
                        if opp_profile:
                            opponent_name = f"{opp_profile.get('first_name', '')} {opp_profile.get('last_name', '')}".strip() or "Unknown Player"
                else:
                    opp_profile = lob.get('creator') or {}
                    opponent_name = f"{opp_profile.get('first_name', '')} {opp_profile.get('last_name', '')}".strip() or "Unknown Player"

                result = "DRAW"
                if lob.get('winner_id') == player_id:
                    result = "WIN"
                elif lob.get('winner_id') is not None:
                    result = "LOSS"

                player_matches.append({
                    'event_title': 'Matchmaker: ' + lob['title'],
                    'opponent_name': opponent_name,
                    'score': lob.get('score') or "N/A",
                    'result': result,
                    'played_at': lob.get('created_at')
                })

            # Sort chronologically descending
            def parse_time(dt_str):
                if not dt_str:
                    return datetime.min.replace(tzinfo=PH_TZ)
                try:
                    if dt_str.endswith('Z'):
                        dt_str = dt_str[:-1] + '+00:00'
                    return datetime.fromisoformat(dt_str)
                except Exception:
                    return datetime.min.replace(tzinfo=PH_TZ)

            player_matches.sort(key=lambda x: parse_time(x.get('played_at')), reverse=True)
            player_matches = player_matches[:5]

        except Exception as match_err:
            print("Error fetching matches in modal:", match_err)

        return render_template(
            'facilitystaff/partials/player_details.html',
            profile=profile,
            stats=stats,
            player_matches=player_matches
        )
    except Exception as e:
        return f"<div style='text-align:center; padding: 30px; color: #ef4444;'><p>Error loading player details: {e}</p></div>", 500


@facilitystaff_bp.route('/queue/update', methods=['POST'])
@require_role('facilitystaff')
def update_queue():
    is_json = False
    if request.is_json:
        is_json = True
        data = request.get_json()
        queue_id = data.get('queue_id')
        new_status = data.get('status')
    else:
        queue_id = request.form.get('queue_id')
        new_status = request.form.get('status')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            is_json = True
    
    db = get_admin_db()
    try:
        if new_status in ['waiting', 'next', 'playing', 'completed', 'cancelled']:
            q_resp = db.table('court_queues').select('player_id, reservation_id, court_id').eq('id', queue_id).single().execute()
            q_data = q_resp.data or {}
            player_id = q_data.get('player_id')
            reservation_id = q_data.get('reservation_id')
            
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            
            # Send notifications
            if new_status == 'next' and player_id:
                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': 'You are up next!',
                    'message': 'Your turn is up next. Please head to your assigned court.',
                    'type': 'success',
                    'link': '/player/queue'
                }).execute()
            elif new_status == 'playing' and player_id:
                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': 'Match Started!',
                    'message': 'Your match is now active. Please proceed to the court.',
                    'type': 'info',
                    'link': '/player/queue'
                }).execute()

            # Synchronize court reservation status
            if reservation_id:
                if new_status == 'completed':
                    try:
                        db.table('court_reservations').update({'status': 'completed'}).eq('id', reservation_id).execute()
                    except Exception:
                        pass
                elif new_status == 'cancelled':
                    try:
                        db.table('court_reservations').update({'status': 'cancelled'}).eq('id', reservation_id).execute()
                    except Exception:
                        pass
                
            msg = f'Queue status updated to {new_status.title()}!'
            if is_json:
                return jsonify({'success': True, 'message': msg})
            flash(msg, 'success')
        else:
            msg = 'Invalid status.'
            if is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error')
    except Exception as e:
        msg = f'Error updating queue: {e}'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'error')
        
    return redirect(request.referrer or url_for('facilitystaff.queue'))

@facilitystaff_bp.route('/nudge/<player_id>', methods=['POST'])
@facilitystaff_bp.route('/player/<player_id>/nudge', methods=['POST'])
@require_role('facilitystaff')
def nudge_player(player_id):
    db = get_admin_db()
    try:
        p_resp = db.table('profiles').select('first_name').eq('id', player_id).single().execute()
        if p_resp.data:
            db.table('notifications').insert({
                'user_id': player_id,
                'title': 'Operations Desk Nudge',
                'message': 'Your court is ready! Please proceed to your assigned court immediately.',
                'type': 'warning',
                'link': '/player/queue'
            }).execute()
            return jsonify({'success': True, 'message': 'Player nudged successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Player not found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error nudging player: {e}'}), 500

@facilitystaff_bp.route('/queue/reassign-court', methods=['POST'])
@require_role('facilitystaff')
def reassign_queue_court():
    data = request.get_json(silent=True) or {}
    queue_id = data.get('queue_id')
    court_id = data.get('court_id')
    if not queue_id or not court_id:
        return jsonify({'success': False, 'message': 'Queue ID and Court ID required.'}), 400
    db = get_admin_db()
    try:
        c_resp = db.table('courts').select('name').eq('id', court_id).single().execute()
        court_name = c_resp.data.get('name') if c_resp.data else 'court'
        db.table('court_queues').update({'court_id': court_id}).eq('id', queue_id).execute()
        return jsonify({'success': True, 'message': f'Player reassigned to {court_name} successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Reassignment failed: {e}'}), 500

@facilitystaff_bp.route('/court/<court_id>/toggle-status', methods=['POST'])
@require_role('facilitystaff')
def toggle_court_status(court_id):
    db = get_admin_db()
    try:
        c_resp = db.table('courts').select('status, name').eq('id', court_id).single().execute()
        if not c_resp.data:
            return jsonify({'success': False, 'message': 'Court not found.'}), 404
        current_status = c_resp.data.get('status')
        new_status = 'maintenance' if current_status != 'maintenance' else 'active'
        db.table('courts').update({'status': new_status}).eq('id', court_id).execute()
        status_label = 'Maintenance' if new_status == 'maintenance' else 'Ready'
        return jsonify({'success': True, 'status': new_status, 'message': f"{c_resp.data['name']} is now marked {status_label}."})
    except Exception as e:
        return jsonify({'success': False, 'message': f"Error: {e}"}), 500

@facilitystaff_bp.route('/schedule')
@require_role('facilitystaff')
def schedule():
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    date_str = request.args.get('date')
    today_dt = datetime.now(PH_TZ)
    today_str = today_dt.strftime('%Y-%m-%d')
    today_date = today_dt.date()
    
    if not date_str:
        date_str = today_str
        
    try:
        current_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        current_date_obj = today_date
        date_str = today_str
        
    prev_date = (current_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    is_today = (current_date_obj == today_date)
    is_past = (current_date_obj < today_date)
    is_future = (current_date_obj > today_date)
    formatted_date = current_date_obj.strftime('%A, %B %d, %Y')
    
    date_presets = [
        {'label': 'Yesterday', 'date': (today_date - timedelta(days=1)).strftime('%Y-%m-%d')},
        {'label': 'Today', 'date': today_str},
        {'label': 'Tomorrow', 'date': (today_date + timedelta(days=1)).strftime('%Y-%m-%d')},
        {'label': '+2 Days', 'date': (today_date + timedelta(days=2)).strftime('%Y-%m-%d')},
        {'label': '+3 Days', 'date': (today_date + timedelta(days=3)).strftime('%Y-%m-%d')},
    ]
    
    courts = []
    reservations = []
    assigned_facilities = []
    court_schedules = []
    stats = {
        'total_bookings': 0,
        'confirmed_count': 0,
        'completed_count': 0,
        'total_hours_booked': 0.0,
        'total_revenue': 0.0,
        'occupancy_rate': 0.0,
        'available_slots': 0
    }
    
    # Hourly slots: 6 AM to 10 PM (hours 6 through 21 for 16 one-hour blocks: 6-7, 7-8, ..., 21-22)
    timeline_hours = []
    for h in range(6, 22):
        dt_start = datetime.strptime(f"{h:02d}:00", "%H:%M")
        dt_end = datetime.strptime(f"{(h+1):02d}:00", "%H:%M")
        timeline_hours.append({
            'hour': h,
            'time_start': f"{h:02d}:00",
            'time_end': f"{(h+1):02d}:00",
            'display_label': dt_start.strftime("%I:%M %p").lstrip("0"),
            'display_range': f"{dt_start.strftime('%I %p').lstrip('0')} - {dt_end.strftime('%I %p').lstrip('0')}"
        })
        
    try:
        # 1. Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(id, name, open_time, close_time)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # 2. Get courts
            c_resp = db.table('courts').select('id, name, facility_id, hourly_rate, status').in_('facility_id', fac_ids).order('name').execute()
            courts = c_resp.data or []
            
            # 3. Get reservations for this date
            r_resp = db.table('court_reservations').select(
                'id, court_id, facility_id, player_id, guest_name, guest_phone, date, start_time, end_time, '
                'status, total_amount, hourly_rate, total_hours, party_size, gcash_ref, created_at, '
                'profiles(first_name, last_name, avatar_url, phone), courts(name)'
            ).in_('facility_id', fac_ids).eq('date', date_str).in_('status', ['confirmed', 'completed']).order('start_time').execute()
            raw_res = r_resp.data or []
            
            now_time_str = today_dt.strftime('%H:%M:%S')
            
            for r in raw_res:
                s_raw = r.get('start_time') or '00:00:00'
                e_raw = r.get('end_time') or '00:00:00'
                s_str = s_raw[:5]
                e_str = e_raw[:5]
                
                try:
                    s_12 = datetime.strptime(s_str, '%H:%M').strftime('%I:%M %p').lstrip('0')
                except Exception:
                    s_12 = s_str
                try:
                    e_12 = datetime.strptime(e_str, '%H:%M').strftime('%I:%M %p').lstrip('0')
                except Exception:
                    e_12 = e_str
                    
                prof = r.get('profiles') or {}
                if prof and (prof.get('first_name') or prof.get('last_name')):
                    disp_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
                    is_walkin = False
                    initials = f"{(prof.get('first_name') or 'P')[0]}{(prof.get('last_name') or '')[:1]}".upper()
                    phone = prof.get('phone') or r.get('guest_phone') or '—'
                else:
                    disp_name = r.get('guest_name') or 'Walk-in Guest'
                    is_walkin = True
                    initials = 'W'
                    phone = r.get('guest_phone') or '—'
                    
                try:
                    s_hr = int(s_raw.split(':')[0])
                except Exception:
                    s_hr = 6
                try:
                    e_hr = int(e_raw.split(':')[0])
                except Exception:
                    e_hr = s_hr + 1
                    
                dur = float(r.get('total_hours') or max(1.0, e_hr - s_hr))
                
                # Check live playing state
                is_live_now = False
                if is_today and r.get('status') == 'confirmed' and s_raw <= now_time_str <= e_raw:
                    is_live_now = True
                    
                r['start_display'] = s_12
                r['end_display'] = e_12
                r['start_str'] = s_str
                r['end_str'] = e_str
                r['start_hour'] = s_hr
                r['end_hour'] = e_hr
                r['duration_hours'] = dur
                r['display_name'] = disp_name
                r['is_walkin'] = is_walkin
                r['initials'] = initials
                r['phone_display'] = phone
                r['is_live_now'] = is_live_now
                
                reservations.append(r)
                
            # Build court schedule mapping for each court
            for court in courts:
                court_res = [r for r in reservations if r.get('court_id') == court['id']]
                hour_map = {}
                for r in court_res:
                    s_hr = r.get('start_hour', 6)
                    e_hr = r.get('end_hour', s_hr + 1)
                    span = max(1, e_hr - s_hr)
                    for h in range(s_hr, max(s_hr + 1, e_hr)):
                        if h not in hour_map:
                            hour_map[h] = {
                                'reservation': r,
                                'is_first_hour': (h == s_hr),
                                'span_hours': span
                            }
                court_schedules.append({
                    'court': court,
                    'reservations': court_res,
                    'hour_map': hour_map
                })
                
            # Compute KPI Stats
            total_b = len(reservations)
            conf_c = sum(1 for r in reservations if r.get('status') == 'confirmed')
            comp_c = sum(1 for r in reservations if r.get('status') == 'completed')
            tot_hrs = sum(r['duration_hours'] for r in reservations)
            tot_rev = sum(float(r.get('total_amount') or 0.0) for r in reservations)
            
            operating_hours_per_court = 16  # 6 AM to 10 PM
            total_court_capacity_hours = len(courts) * operating_hours_per_court
            occ_rate = round((tot_hrs / total_court_capacity_hours * 100), 1) if total_court_capacity_hours > 0 else 0.0
            avail_slots = max(0, int(total_court_capacity_hours - tot_hrs))
            
            stats = {
                'total_bookings': total_b,
                'confirmed_count': conf_c,
                'completed_count': comp_c,
                'total_hours_booked': round(tot_hrs, 1),
                'total_revenue': tot_rev,
                'occupancy_rate': occ_rate,
                'available_slots': avail_slots
            }

            # 4. Fetch all dates with bookings across past & future for facility calendar
            booked_dates_summary = {}
            try:
                all_b_resp = db.table('court_reservations').select(
                    'id, court_id, date, start_time, end_time, status, total_amount, guest_name, profiles(first_name, last_name), courts(name)'
                ).in_('facility_id', fac_ids).in_('status', ['confirmed', 'completed']).order('date', desc=True).execute()
                
                for b in (all_b_resp.data or []):
                    b_date = b.get('date')
                    if not b_date:
                        continue
                    if b_date not in booked_dates_summary:
                        booked_dates_summary[b_date] = {
                            'date': b_date,
                            'count': 0,
                            'confirmed': 0,
                            'completed': 0,
                            'revenue': 0.0,
                            'courts': set(),
                            'items': []
                        }
                    entry = booked_dates_summary[b_date]
                    entry['count'] += 1
                    if b.get('status') == 'confirmed':
                        entry['confirmed'] += 1
                    elif b.get('status') == 'completed':
                        entry['completed'] += 1
                    entry['revenue'] += float(b.get('total_amount') or 0.0)
                    court_name = (b.get('courts') or {}).get('name') or 'Court'
                    entry['courts'].add(court_name)
                    
                    prof = b.get('profiles') or {}
                    p_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip() or b.get('guest_name') or 'Player'
                    s_str = (b.get('start_time') or '')[:5]
                    e_str = (b.get('end_time') or '')[:5]
                    entry['items'].append({
                        'id': b.get('id'),
                        'player': p_name,
                        'court': court_name,
                        'time': f"{s_str} - {e_str}",
                        'status': b.get('status')
                    })
                    
                for d, data in booked_dates_summary.items():
                    data['courts'] = sorted(list(data['courts']))
            except Exception as b_err:
                print(f"Error fetching booked dates summary: {b_err}")
            
    except Exception as e:
        flash(f'An error occurred loading schedule: {e}', 'error')
        
    return render_template('facilitystaff/schedule.html', 
                           date=date_str,
                           date_obj=current_date_obj,
                           formatted_date=formatted_date,
                           prev_date=prev_date,
                           next_date=next_date,
                           is_today=is_today,
                           is_past=is_past,
                           is_future=is_future,
                           date_presets=date_presets,
                           timeline_hours=timeline_hours,
                           court_schedules=court_schedules,
                           stats=stats,
                           facilities=assigned_facilities, 
                           courts=courts, 
                           reservations=reservations,
                           booked_dates=booked_dates_summary,
                           booked_dates_count=len(booked_dates_summary))

@facilitystaff_bp.route('/schedule/booked-dates')
@require_role('facilitystaff')
def schedule_booked_dates():
    staff_id = session.get('user_id')
    db = get_admin_db()
    try:
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in (fs_resp.data or [])]
        if not fac_ids:
            return jsonify({'success': True, 'dates': {}, 'count': 0})
            
        all_b_resp = db.table('court_reservations').select(
            'id, court_id, date, start_time, end_time, status, total_amount, guest_name, profiles(first_name, last_name), courts(name)'
        ).in_('facility_id', fac_ids).in_('status', ['confirmed', 'completed']).order('date', desc=True).execute()
        
        booked_dates_summary = {}
        for b in (all_b_resp.data or []):
            b_date = b.get('date')
            if not b_date:
                continue
            if b_date not in booked_dates_summary:
                booked_dates_summary[b_date] = {
                    'date': b_date,
                    'count': 0,
                    'confirmed': 0,
                    'completed': 0,
                    'revenue': 0.0,
                    'courts': set(),
                    'items': []
                }
            entry = booked_dates_summary[b_date]
            entry['count'] += 1
            if b.get('status') == 'confirmed':
                entry['confirmed'] += 1
            elif b.get('status') == 'completed':
                entry['completed'] += 1
            entry['revenue'] += float(b.get('total_amount') or 0.0)
            court_name = (b.get('courts') or {}).get('name') or 'Court'
            entry['courts'].add(court_name)
            
            prof = b.get('profiles') or {}
            p_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip() or b.get('guest_name') or 'Player'
            s_str = (b.get('start_time') or '')[:5]
            e_str = (b.get('end_time') or '')[:5]
            entry['items'].append({
                'id': b.get('id'),
                'player': p_name,
                'court': court_name,
                'time': f"{s_str} - {e_str}",
                'status': b.get('status')
            })
            
        for d, data in booked_dates_summary.items():
            data['courts'] = sorted(list(data['courts']))
            
        return jsonify({'success': True, 'dates': booked_dates_summary, 'count': len(booked_dates_summary)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@facilitystaff_bp.route('/walkin', methods=['GET', 'POST'])
@require_role('facilitystaff')
def walkin():
    staff_id = session.get('user_id')
    db = get_admin_db()

    if request.method == 'POST':
        is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

        req_data = request.get_json(silent=True) if request.is_json else request.form
        guest_name = (req_data.get('guest_name') or '').strip()
        guest_phone = (req_data.get('guest_phone') or '').strip()
        court_id = req_data.get('court_id')
        try:
            duration = float(req_data.get('duration') or 1)
        except (ValueError, TypeError):
            duration = 1.0
        try:
            party_size = int(req_data.get('party_size') or 1)
        except (ValueError, TypeError):
            party_size = 1
        payment_method = req_data.get('payment_method') or 'cash'
        gcash_ref = (req_data.get('gcash_ref') or '').strip() or None

        if not guest_name or not court_id:
            msg = "Guest Name and Court are required."
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, "error")
            return redirect(url_for('facilitystaff.walkin'))

        try:
            # 1. Get Court Info
            c_resp = db.table('courts').select('facility_id, hourly_rate, name').eq('id', court_id).single().execute()
            court_info = c_resp.data
            if not court_info:
                msg = "Selected court not found."
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 404
                flash(msg, "error")
                return redirect(url_for('facilitystaff.walkin'))

            hourly_rate = float(court_info.get('hourly_rate') or 0.0)
            total_amount = hourly_rate * duration

            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            start_time = now.strftime('%H:%M:%S')
            end_time = (now + timedelta(hours=duration)).strftime('%H:%M:%S')

            # Check for overlapping reservation
            overlap_resp = db.table('court_reservations').select('id')\
                .eq('court_id', court_id)\
                .eq('date', today_str)\
                .in_('status', ['confirmed', 'pending_payment'])\
                .lt('start_time', end_time)\
                .gt('end_time', start_time)\
                .execute()
                
            if overlap_resp.data:
                msg = 'This court is already reserved during the selected walk-in slot.'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'error')
                return redirect(url_for('facilitystaff.walkin'))

            # 2. Create Reservation (include gcash_ref for payment reference)
            res_data = {
                'court_id': court_id,
                'facility_id': court_info['facility_id'],
                'date': today_str,
                'start_time': start_time,
                'end_time': end_time,
                'total_hours': duration,
                'hourly_rate': hourly_rate,
                'total_amount': total_amount,
                'status': 'confirmed',
                'guest_name': guest_name,
                'guest_phone': guest_phone,
                'party_size': party_size,
            }
            if gcash_ref:
                res_data['gcash_ref'] = gcash_ref

            res_resp = db.table('court_reservations').insert(res_data).execute()
            new_res = res_resp.data[0]

            # 3. Queue status
            q_resp = db.table('court_queues').select('id').eq('court_id', court_id).eq('status', 'playing').execute()
            q_status = 'waiting' if q_resp.data else 'playing'

            # 4. Create Queue Entry
            q_ins = db.table('court_queues').insert({
                'facility_id': court_info['facility_id'],
                'court_id': court_id,
                'status': q_status,
                'guest_name': guest_name,
                'party_size': party_size,
                'reservation_id': new_res['id'],
            }).execute()
            new_queue_id = q_ins.data[0]['id'] if (q_ins.data and len(q_ins.data) > 0) else None

            # 5. Store receipt data in session
            receipt_data = {
                'reservation_id': new_res['id'],
                'queue_id': new_queue_id,
                'guest_name': guest_name,
                'guest_phone': guest_phone or '—',
                'court_name': court_info['name'],
                'date': today_str,
                'start_time': start_time[:5],
                'end_time': end_time[:5],
                'duration': duration,
                'party_size': party_size,
                'hourly_rate': hourly_rate,
                'total_amount': total_amount,
                'payment_method': payment_method,
                'gcash_ref': gcash_ref or '—',
                'queue_status': q_status,
            }
            session['walkin_receipt'] = receipt_data

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': f"Walk-in registered for {guest_name} on {court_info['name']}!",
                    'queue_id': new_queue_id,
                    'receipt': receipt_data,
                    'redirect_to': request.form.get('redirect_to') or 'queue'
                })

            return redirect(url_for('facilitystaff.walkin_receipt'))

        except Exception as e:
            msg = f'An error occurred: {e}'
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 500
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('facilitystaff.walkin'))

    # GET: Fetch available courts
    courts = []
    try:
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in fs_resp.data or []]
        if fac_ids:
            c_resp = db.table('courts').select('id, name, hourly_rate').in_('facility_id', fac_ids).eq('status', 'active').execute()
            courts = c_resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return render_template('facilitystaff/walkin.html', courts=courts)


@facilitystaff_bp.route('/walkin/receipt')
@require_role('facilitystaff')
def walkin_receipt():
    receipt = session.pop('walkin_receipt', None)
    if not receipt:
        flash("No recent walk-in found.", "warning")
        return redirect(url_for('facilitystaff.walkin'))
    return render_template('facilitystaff/walkin_receipt.html', receipt=receipt)

@facilitystaff_bp.route('/profile', methods=['GET', 'POST'])
@require_role('facilitystaff')
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
        return redirect(url_for('facilitystaff.profile'))
    return render_template('facilitystaff/profile.html')

@facilitystaff_bp.route('/notifications')
@require_role('facilitystaff')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('facilitystaff/notifications.html', notifications=notifs)

@facilitystaff_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('facilitystaff')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@facilitystaff_bp.route('/messages')
@require_role('facilitystaff')
def messages():
    return render_template('facilitystaff/messages.html')

@facilitystaff_bp.route('/community')
@require_role('facilitystaff')
def community():
    return render_template('facilitystaff/community.html')


@facilitystaff_bp.route('/matchmaker/<lobby_id>')
@require_role('facilitystaff')
def matchmaker_detail(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    lobby = None
    participants = []
    is_joined = False
    winner_name = ""
    lobby_messages = []

    try:
        admin_db = get_admin_db()
        lob_resp = admin_db.table('matchmaker_lobbies').select(
            'id, creator_id, reservation_id, title, description, min_dupr, max_dupr, slots_total, slots_filled, status, score, winner_id, match_type, '
            'reported_score, reported_winner_id, reporter_id, verification_status, dispute_count, '
            'creator:profiles!creator_id(first_name, last_name, elo, dupr, proficiency, avatar_url), '
            'reservation:court_reservations!reservation_id(date, start_time, end_time, courts(name), facilities(name))'
        ).eq('id', lobby_id).single().execute()

        if not lob_resp.data:
            flash("Lobby not found.", "error")
            return redirect(url_for('facilitystaff.dashboard'))

        raw_lob = lob_resp.data
        creator = raw_lob.get('creator') or {}
        res = raw_lob.get('reservation') or {}
        court = res.get('courts') or {}
        facility = res.get('facilities') or {}

        from app.player.routes import get_lobby_display_status
        lobby = {
            'id': raw_lob['id'],
            'creator_id': raw_lob['creator_id'],
            'reservation_id': raw_lob['reservation_id'],
            'title': raw_lob['title'],
            'description': raw_lob['description'],
            'min_dupr': float(raw_lob['min_dupr']),
            'max_dupr': float(raw_lob['max_dupr']),
            'slots_total': raw_lob['slots_total'],
            'slots_filled': raw_lob['slots_filled'],
            'status': raw_lob['status'],
            'score': raw_lob.get('score'),
            'winner_id': raw_lob.get('winner_id'),
            'reported_score': raw_lob.get('reported_score'),
            'reported_winner_id': raw_lob.get('reported_winner_id'),
            'reporter_id': raw_lob.get('reporter_id'),
            'verification_status': raw_lob.get('verification_status') or 'pending',
            'dispute_count': raw_lob.get('dispute_count') or 0,
            'match_type': raw_lob.get('match_type') or 'ranked',
            'creator_name': f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip() or "Anonymous Player",
            'creator_dupr': creator.get('dupr') if creator.get('dupr') is not None else 3.00,
            'creator_avatar_url': creator.get('avatar_url') or None,
            'facility_name': facility.get('name', 'Unknown Facility'),
            'court_name': court.get('name', 'Court'),
            'date': res.get('date') or datetime.now(PH_TZ).strftime('%Y-%m-%d'),
            'start_time': res.get('start_time') or '00:00',
            'end_time': res.get('end_time') or '00:00',
        }
        lobby['display_status'] = get_lobby_display_status(
            lobby['status'], lobby['date'], lobby['start_time'], lobby['end_time']
        )

        creator_first = creator.get('first_name') or 'H'
        creator_last = creator.get('last_name') or ''
        creator_initials = (creator_first[0] + (creator_last[0] if creator_last else '')).upper()

        # Fetch participants (including team and slot)
        part_resp = admin_db.table('lobby_participants').select(
            'id, player_id, status, team, slot, profiles!player_id(first_name, last_name, elo, dupr, avatar_url)'
        ).eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        
        raw_participants = part_resp.data or []
        
        # Build Team slots grid
        slots_grid = {
            'team1': [
                {'slot': 1, 'player': {
                    'id': lobby['creator_id'],
                    'name': lobby['creator_name'],
                    'dupr': lobby['creator_dupr'],
                    'initials': creator_initials,
                    'avatar_url': lobby.get('creator_avatar_url'),
                    'is_host': True
                }}
            ],
            'team2': []
        }
        
        if lobby['slots_total'] == 3: # Doubles
            slots_grid['team1'].append({'slot': 2, 'player': None})
            slots_grid['team2'].append({'slot': 1, 'player': None})
            slots_grid['team2'].append({'slot': 2, 'player': None})
        elif lobby['slots_total'] == 1: # Singles
            slots_grid['team2'].append({'slot': 1, 'player': None})
        else:
            for s in range(1, lobby['slots_total'] + 1):
                slots_grid['team2'].append({'slot': s, 'player': None})

        participants = []
        occupied_slots = {(1, 1): True}
        unmapped_participants = []

        for p in raw_participants:
            p_profile = p.get('profiles') or {}
            first = p_profile.get('first_name') or 'P'
            last = p_profile.get('last_name') or ''
            p['initials'] = (first[0] + (last[0] if last else '')).upper()
            p['name'] = f"{first} {last}".strip() or "Anonymous Player"
            p['avatar_url'] = p_profile.get('avatar_url') or None
            participants.append(p)
            
            if p['player_id'] == player_id:
                is_joined = True
                
            player_info = {
                'id': p['player_id'],
                'name': p['name'],
                'dupr': p_profile.get('dupr') if p_profile.get('dupr') is not None else 3.00,
                'initials': p['initials'],
                'avatar_url': p_profile.get('avatar_url') or None,
                'is_host': False,
                'participant_id': p['id']
            }
            
            t = p.get('team')
            s = p.get('slot')
            if t in [1, 2] and s is not None:
                if (t, s) not in occupied_slots:
                    team_key = f"team{t}"
                    slot_idx = s - 1
                    if team_key in slots_grid and 0 <= slot_idx < len(slots_grid[team_key]):
                        slots_grid[team_key][slot_idx]['player'] = player_info
                        occupied_slots[(t, s)] = True
                        continue
            unmapped_participants.append((p['id'], player_info))

        for part_id, player_info in unmapped_participants:
            found = False
            for team_key in ['team2', 'team1']:
                if found:
                    break
                for cell in slots_grid[team_key]:
                    if cell['player'] is None:
                        cell['player'] = player_info
                        found = True
                        t_val = 1 if team_key == 'team1' else 2
                        s_val = cell['slot']
                        occupied_slots[(t_val, s_val)] = True
                        try:
                            admin_db.table('lobby_participants').update({
                                'team': t_val,
                                'slot': s_val
                            }).eq('id', part_id).execute()
                            p_in_list = next((x for x in participants if x['id'] == part_id), None)
                            if p_in_list:
                                p_in_list['team'] = t_val
                                p_in_list['slot'] = s_val
                        except Exception as auto_heal_err:
                            print(f"[auto_heal] Failed to update slot: {auto_heal_err}")
                        break

        winner_name = None
        target_winner_id = lobby.get('winner_id') or lobby.get('reported_winner_id')
        if target_winner_id:
            is_winner_team1 = False
            if target_winner_id == lobby['creator_id']:
                is_winner_team1 = True
            else:
                for p in participants:
                    if p['player_id'] == target_winner_id and p.get('team') == 1:
                        is_winner_team1 = True
                        break
            winner_name = "Team 1" if is_winner_team1 else "Team 2"

        # Fetch lobby chat messages
        try:
            msg_resp = admin_db.table('messages').select(
                'id, sender_id, content, created_at, profiles!sender_id(first_name, last_name)'
            ).eq('conversation_id', lobby_id).order('created_at', desc=False).execute()
            
            for m in (msg_resp.data or []):
                if m.get('sender_id') is None:
                    m['sender_name'] = 'System'
                    m['sender_initials'] = 'SYS'
                else:
                    m_prof = m.get('profiles') or {}
                    m_first = m_prof.get('first_name') or 'Player'
                    m_last = m_prof.get('last_name') or ''
                    m['sender_name'] = f"{m_first} {m_last}".strip()
                    m['sender_initials'] = (m_first[0] + (m_last[0] if m_last else '')).upper()
                
                try:
                    dt = datetime.fromisoformat(m['created_at'].replace('Z', '+00:00'))
                    m['formatted_time'] = dt.astimezone(PH_TZ).strftime('%I:%M %p')
                except Exception:
                    m['formatted_time'] = ''
                lobby_messages.append(m)
        except Exception as msg_err:
            print(f"Error fetching lobby messages: {msg_err}")

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('facilitystaff.dashboard'))

    # Staff check logic
    current_user_team = None
    reporter_team = None
    is_assigned_staff = False
    if lobby and lobby.get('reservation_id'):
        try:
            res_resp = admin_db.table('court_reservations').select('facility_id').eq('id', lobby['reservation_id']).single().execute()
            if res_resp.data:
                fac_id = res_resp.data['facility_id']
                staff_check = admin_db.table('facility_staff').select('id').eq('facility_id', fac_id).eq('staff_id', player_id).execute()
                if staff_check.data:
                    is_assigned_staff = True
        except Exception as staff_err:
            print(f"Error checking assigned staff: {staff_err}")

    return render_template(
        'player/matchmaker_detail.html',
        lobby=lobby,
        participants=participants,
        slots_grid=slots_grid,
        creator_initials=creator_initials,
        is_joined=is_joined,
        winner_name=winner_name,
        messages=lobby_messages,
        current_user_team=current_user_team,
        reporter_team=reporter_team,
        is_assigned_staff=is_assigned_staff,
        base_template="facilitystaff/base_facilitystaff.html"
    )


@facilitystaff_bp.route('/mediation')
@require_role('facilitystaff')
def mediation_desk():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    disputed_lobbies = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Get matchmaker lobbies in staff mediation for these facilities
            try:
                admin_db = get_admin_db()
                lob_resp = admin_db.table('matchmaker_lobbies').select(
                    'id, title, status, reported_score, creator_id, created_at, reservation_id, '
                    'creator:profiles!creator_id(first_name, last_name), '
                    'court_reservations!reservation_id(facility_id, date, start_time, end_time, courts(name), facilities(name))'
                ).eq('status', 'staff_mediation').execute()
                
                raw_disputed = lob_resp.data or []
                for lob in raw_disputed:
                    res = lob.get('court_reservations') or {}
                    if res.get('facility_id') in fac_ids:
                        creator = lob.get('creator') or {}
                        court = res.get('courts') or {}
                        fac = res.get('facilities') or {}
                        disputed_lobbies.append({
                            'id': lob['id'],
                            'title': lob['title'],
                            'reported_score': lob.get('reported_score') or '—',
                            'creator_name': f"{creator.get('first_name','')} {creator.get('last_name','')}".strip() or "Host",
                            'facility_name': fac.get('name', 'Facility'),
                            'court_name': court.get('name', 'Court'),
                            'date': res.get('date') or '',
                            'time': f"{res.get('start_time')[:5]} - {res.get('end_time')[:5]}" if res.get('start_time') else ''
                        })
            except Exception as lob_err:
                print(f"Error fetching disputed lobbies: {lob_err}")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('facilitystaff/mediation_desk.html', disputed_lobbies=disputed_lobbies)


@facilitystaff_bp.route('/ledger')
@require_role('facilitystaff')
def payment_ledger():
    staff_id = session.get('user_id')
    db = get_db()
    transactions = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Query court_reservations where gcash_ref is not null/empty
            resp = db.table('court_reservations').select(
                'id, date, start_time, end_time, total_amount, status, gcash_ref, receipt_url, created_at, player_id, facility_id, '
                'profiles(first_name, last_name, phone, avatar_url), '
                'courts(name, type), '
                'facilities(name)'
            ).in_('facility_id', fac_ids).neq('gcash_ref', None).neq('gcash_ref', '').order('created_at', desc=True).execute()
            
            transactions = resp.data or []
            
            # Post-process user initials
            for t in transactions:
                prof = t.get('profiles') or {}
                first = (prof.get('first_name') or ' ')[0]
                last = (prof.get('last_name') or ' ')[0]
                prof['initials'] = (first + last).upper().strip() or '?'
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading payment ledger for staff {staff_id}: {e}")
        flash('An error occurred loading ledger. Please try again.', 'error')
        
    return render_template('facilitystaff/ledger.html', transactions=transactions)


@facilitystaff_bp.route('/ledger/<reservation_id>/approve', methods=['POST'])
@require_role('facilitystaff')
def approve_payment(reservation_id):
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in fs_resp.data or []]
        
        # Fetch reservation details
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, total_amount, player_id, facility_id, court_id, status, '
            'facilities(name)'
        ).eq('id', reservation_id).single().execute()
        
        res = res_resp.data
        if not res or res.get('facility_id') not in fac_ids:
            flash("Reservation not found or unauthorized.", "error")
            return redirect(url_for('facilitystaff.payment_ledger'))
            
        if res['status'] == 'confirmed':
            flash("Payment already confirmed.", "info")
            return redirect(url_for('facilitystaff.payment_ledger'))
            
        # Update reservation status to confirmed
        db.table('court_reservations').update({
            'status': 'confirmed'
        }).eq('id', reservation_id).execute()
        
        # Insert player into court_queues
        db.table('court_queues').insert({
            'player_id': res['player_id'],
            'facility_id': res['facility_id'],
            'court_id': res['court_id'],
            'reservation_id': reservation_id,
            'status': 'waiting',
            'estimated_wait_mins': 0
        }).execute()
        
        # Trigger autochat messages
        try:
            from app.chats import trigger_booking_autochat
            trigger_booking_autochat(db, reservation_id, res['player_id'])
        except Exception as chat_err:
            from flask import current_app
            current_app.logger.error(f"Error triggering autochats: {chat_err}")
            
        # Notify the player
        try:
            facility_name = res.get('facilities', {}).get('name') or "the facility"
            db.table('notifications').insert({
                'user_id': res['player_id'],
                'title': '✅ Booking Payment Approved',
                'message': f"Your payment reference for the court booking at {facility_name} on {res['date']} has been approved. Your booking is now confirmed!",
                'type': 'success',
                'link': '/player/my-reservations'
            }).execute()
        except Exception as n_err:
            from flask import current_app
            current_app.logger.error(f"Error inserting approval notification: {n_err}")
            
        flash("Payment approved successfully.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error approving payment {reservation_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('facilitystaff.payment_ledger'))


@facilitystaff_bp.route('/ledger/<reservation_id>/decline', methods=['POST'])
@require_role('facilitystaff')
def decline_payment(reservation_id):
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in fs_resp.data or []]
        
        # Fetch reservation details
        res_resp = db.table('court_reservations').select(
            'id, date, player_id, status, facility_id, '
            'facilities(name)'
        ).eq('id', reservation_id).single().execute()
        
        res = res_resp.data
        if not res or res.get('facility_id') not in fac_ids:
            flash("Reservation not found or unauthorized.", "error")
            return redirect(url_for('facilitystaff.payment_ledger'))
            
        if res['status'] == 'cancelled':
            flash("Reservation is already cancelled.", "info")
            return redirect(url_for('facilitystaff.payment_ledger'))
            
        # Update reservation status to cancelled/declined
        db.table('court_reservations').update({
            'status': 'cancelled'
        }).eq('id', reservation_id).execute()
        
        # Notify the player
        try:
            facility_name = res.get('facilities', {}).get('name') or "the facility"
            db.table('notifications').insert({
                'user_id': res['player_id'],
                'title': '❌ Booking Payment Declined',
                'message': f"Your payment reference for the court booking at {facility_name} on {res['date']} was declined. Please verify your reference number.",
                'type': 'error',
                'link': '/player/my-reservations'
            }).execute()
        except Exception as n_err:
            from flask import current_app
            current_app.logger.error(f"Error inserting decline notification: {n_err}")
            
        flash("Payment declined and reservation cancelled.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error declining payment {reservation_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('facilitystaff.payment_ledger'))



@facilitystaff_bp.route('/verify-pass', methods=['POST'])
@require_role('facilitystaff')
def verify_pass():
    staff_id = session.get('user_id')
    db = get_admin_db()
    
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or data.get('pass_code') or request.form.get('code') or request.form.get('pass_code') or '').strip()
    
    if not code:
        return jsonify({'success': False, 'message': 'Please provide a pass code or booking reference.'}), 400
        
    try:
        now = datetime.now(PH_TZ)
        today_str = now.strftime('%Y-%m-%d')
        
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in (fs_resp.data or [])]
        
        # 1. Search today's reservations first
        res_resp = db.table('court_reservations').select(
            'id, court_id, date, start_time, end_time, status, player_id, guest_name, profiles(first_name, last_name), courts(id, name)'
        ).in_('facility_id', fac_ids).eq('date', today_str).execute()
        
        matches = []
        for r in (res_resp.data or []):
            p = r.get('profiles') or {}
            full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            guest_name = r.get('guest_name') or ''
            rid = str(r.get('id') or '')
            
            if code.lower() in rid.lower() or code.lower() in full_name.lower() or code.lower() in guest_name.lower():
                matches.append(r)
                
        # 2. If not found today, search recent reservations
        if not matches:
            res_all = db.table('court_reservations').select(
                'id, court_id, date, start_time, end_time, status, player_id, guest_name, profiles(first_name, last_name), courts(id, name)'
            ).in_('facility_id', fac_ids).order('date', desc=True).limit(30).execute()
            for r in (res_all.data or []):
                p = r.get('profiles') or {}
                full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                guest_name = r.get('guest_name') or ''
                rid = str(r.get('id') or '')
                if code.lower() in rid.lower() or code.lower() in full_name.lower() or code.lower() in guest_name.lower():
                    matches.append(r)
                
        if matches:
            match = matches[0]
            p = match.get('profiles') or {}
            player_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or match.get('guest_name') or 'Player'
            court_data = match.get('courts') or {}
            court_name = court_data.get('name') or 'Assigned Court'
            court_id = match.get('court_id') or court_data.get('id')
            s_time = (match.get('start_time') or '00:00')[:5]
            e_time = (match.get('end_time') or '00:00')[:5]
            res_date = match.get('date') or today_str
            return jsonify({
                'success': True,
                'found': True,
                'player_name': player_name,
                'court_name': court_name,
                'court_id': court_id,
                'reservation_id': match.get('id'),
                'time_slot': f"{res_date} {s_time} - {e_time}",
                'status': match.get('status', 'confirmed'),
                'message': f"Valid pass verified for {player_name} on {court_name} ({res_date} {s_time} - {e_time}).",
                'reservation': match
            })
            
        return jsonify({'success': False, 'message': f"No matching reservation or pass found for code '{code}'."}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f"Verification error: {e}"}), 500

@facilitystaff_bp.route('/checkin-reservation', methods=['POST'])
@require_role('facilitystaff')
def checkin_reservation():
    db = get_admin_db()
    data = request.get_json(silent=True) or {}
    reservation_id = data.get('reservation_id')
    if not reservation_id:
        return jsonify({'success': False, 'message': 'Reservation ID is required.'}), 400
    try:
        res_resp = db.table('court_reservations').select('*').eq('id', reservation_id).single().execute()
        res = res_resp.data
        if not res:
            return jsonify({'success': False, 'message': 'Reservation not found.'}), 404

        # Check if already in queue
        q_check = db.table('court_queues').select('id, status').eq('reservation_id', reservation_id).in_('status', ['waiting', 'next', 'playing']).execute()
        if q_check.data:
            return jsonify({'success': True, 'message': f"Player is already checked in to the queue ({q_check.data[0]['status'].title()}).", 'already_in_queue': True})

        # Insert into court_queues
        q_resp = db.table('court_queues').select('id').eq('court_id', res['court_id']).eq('status', 'playing').execute()
        q_status = 'waiting' if q_resp.data else 'next'
        
        insert_data = {
            'facility_id': res['facility_id'],
            'court_id': res['court_id'],
            'status': q_status,
            'reservation_id': reservation_id,
            'party_size': res.get('party_size') or 1
        }
        if res.get('player_id'):
            insert_data['player_id'] = res['player_id']
        if res.get('guest_name'):
            insert_data['guest_name'] = res['guest_name']
            
        db.table('court_queues').insert(insert_data).execute()
        
        # Send notification to player if player_id exists
        if res.get('player_id'):
            db.table('notifications').insert({
                'user_id': res['player_id'],
                'title': 'Checked In at Front Desk',
                'message': f"You're checked in for your court session! Current status: {q_status.title()}.",
                'type': 'success',
                'link': '/player/queue'
            }).execute()

        return jsonify({'success': True, 'message': 'Check-in successful! Player added to live waitlist.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Check-in failed: {e}'}), 500
