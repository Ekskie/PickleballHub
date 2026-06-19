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
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    court_status_list = []
    disputed_lobbies = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Get courts
            c_resp = db.table('courts').select('*').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # Get active queues
            queues = get_staff_processed_queues(db, fac_ids)
            
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
            
            # Calculate live court status
            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            
            # Fetch today's reservations for these courts
            res_resp = db.table('court_reservations').select('*').in_('court_id', [c['id'] for c in courts]).eq('date', today_str).in_('status', ['confirmed', 'completed']).execute()
            reservations = res_resp.data or []
            
            # For each court, determine if it is currently in use
            for c in courts:
                status = 'Available'
                status_color = 'positive'
                sub_text = 'Ready'
                
                if c['status'] == 'maintenance':
                    status = 'Maintenance'
                    status_color = 'warning'
                    sub_text = 'Unavailable'
                else:
                    # Check reservations
                    for r in reservations:
                        if r['court_id'] == c['id'] and r['status'] == 'confirmed':
                            start_time_str = f"{today_str} {r['start_time']}"
                            end_time_str = f"{today_str} {r['end_time']}"
                            try:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            except ValueError:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            
                            if start_dt <= now <= end_dt:
                                status = 'In Use'
                                status_color = 'negative'
                                rem_mins = int((end_dt - now).total_seconds() / 60)
                                sub_text = f"Ends in {rem_mins}m"
                                break
                            elif start_dt > now:
                                # Next upcoming
                                diff_mins = int((start_dt - now).total_seconds() / 60)
                                if status == 'Available' and diff_mins < 60:
                                    sub_text = f"Next in {diff_mins}m"
                                    
                court_status_list.append({
                    'name': c['name'],
                    'status': status,
                    'color': status_color,
                    'sub_text': sub_text
                })
                
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('facilitystaff/dashboard.html', court_status_list=court_status_list, queues=queues, disputed_lobbies=disputed_lobbies)

def get_staff_processed_queues(db, fac_ids):
    if not fac_ids:
        return []
    try:
        resp = db.table('court_queues').select(
            'id, facility_id, court_id, status, estimated_wait_mins, joined_at, player_id, profiles(first_name, last_name, avatar_url), court_reservations!inner(date, start_time, end_time)'
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
            
        queues.append(q)

    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), x.get('court_reservations', {}).get('start_time', '')))
    return queues


@facilitystaff_bp.route('/queue')
@require_role('facilitystaff')
def queue():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        # 1. Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # 2. Get courts for these facilities
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # 3. Get active queue items
            queues = get_staff_processed_queues(db, fac_ids)
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('facilitystaff/queue.html', facilities=assigned_facilities, courts=courts, queues=queues)

@facilitystaff_bp.route('/queue/partial')
@require_role('facilitystaff')
def queue_partial():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            queues = get_staff_processed_queues(db, fac_ids)
            
    except Exception as e:
        pass
        
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
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'playing', 'completed', 'cancelled']:
            q_resp = db.table('court_queues').select('player_id').eq('id', queue_id).single().execute()
            player_id = q_resp.data['player_id'] if q_resp.data else None
            
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            
            # Send notification if 'next'
            if new_status == 'next' and player_id:
                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': 'You are up next!',
                    'message': 'Your turn is up next. Please head to your assigned court.',
                    'type': 'success',
                    'link': '/player/queue'
                }).execute()
                
            msg = 'Queue status updated!'
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
@require_role('facilitystaff')
def nudge_player(player_id):
    db = get_db()
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

@facilitystaff_bp.route('/schedule')
@require_role('facilitystaff')
def schedule():
    staff_id = session.get('user_id')
    db = get_db()
    
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
        
    courts = []
    reservations = []
    assigned_facilities = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name, open_time, close_time)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Get courts
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # Get reservations for this date
            r_resp = db.table('court_reservations').select(
                'id, court_id, start_time, end_time, status, profiles(first_name, last_name)'
            ).in_('facility_id', fac_ids).eq('date', date_str).in_('status', ['confirmed', 'completed']).order('start_time').execute()
            reservations = r_resp.data or []
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('facilitystaff/schedule.html', 
                           date=date_str, 
                           facilities=assigned_facilities, 
                           courts=courts, 
                           reservations=reservations)

@facilitystaff_bp.route('/walkin', methods=['GET', 'POST'])
@require_role('facilitystaff')
def walkin():
    staff_id = session.get('user_id')
    db = get_db()

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        guest_phone = request.form.get('guest_phone', '').strip()
        court_id = request.form.get('court_id')
        duration = float(request.form.get('duration', 1))
        party_size = int(request.form.get('party_size', 1))
        payment_method = request.form.get('payment_method', 'cash')
        gcash_ref = request.form.get('gcash_ref', '').strip() or None

        if not guest_name or not court_id:
            flash("Guest Name and Court are required.", "error")
            return redirect(url_for('facilitystaff.walkin'))

        try:
            # 1. Get Court Info
            c_resp = db.table('courts').select('facility_id, hourly_rate, name').eq('id', court_id).single().execute()
            court_info = c_resp.data
            total_amount = court_info['hourly_rate'] * duration

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
                flash('This court is already reserved during the selected walk-in slot.', 'error')
                return redirect(url_for('facilitystaff.walkin'))

            # 2. Create Reservation (include gcash_ref for payment reference)
            res_data = {
                'court_id': court_id,
                'facility_id': court_info['facility_id'],
                'date': today_str,
                'start_time': start_time,
                'end_time': end_time,
                'total_hours': duration,
                'hourly_rate': court_info['hourly_rate'],
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
            db.table('court_queues').insert({
                'facility_id': court_info['facility_id'],
                'court_id': court_id,
                'status': q_status,
                'guest_name': guest_name,
                'party_size': party_size,
                'reservation_id': new_res['id'],
            }).execute()

            # 5. Store receipt data in session
            session['walkin_receipt'] = {
                'reservation_id': new_res['id'],
                'guest_name': guest_name,
                'guest_phone': guest_phone or '—',
                'court_name': court_info['name'],
                'date': today_str,
                'start_time': start_time[:5],
                'end_time': end_time[:5],
                'duration': duration,
                'party_size': party_size,
                'hourly_rate': court_info['hourly_rate'],
                'total_amount': total_amount,
                'payment_method': payment_method,
                'gcash_ref': gcash_ref or '—',
                'queue_status': q_status,
            }

            return redirect(url_for('facilitystaff.walkin_receipt'))

        except Exception as e:
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

