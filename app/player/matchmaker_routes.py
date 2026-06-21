from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime
from app.db import get_db, get_admin_db
from app.player import player_bp
from app.player.routes import PH_TZ
from app.ratings import update_matchmaker_ratings

def get_lobby_display_status(lobby_status, res_date, res_start, res_end):
    if lobby_status in ['completed', 'pending_verification', 'staff_mediation', 'cancelled']:
        return lobby_status
    
    try:
        start_str = f"{res_date} {res_start}"
        end_str = f"{res_date} {res_end}"
        
        if len(res_start) == 5:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
        else:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            
        if len(res_end) == 5:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
        else:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            
        now = datetime.now(PH_TZ)
        if now > end_dt:
            return 'completed'
        elif start_dt <= now <= end_dt:
            return 'ongoing'
        elif lobby_status == 'full':
            return 'full'
        else:
            return 'open'
    except Exception as e:
        print(f"Error computing lobby display status: {e}")
        return lobby_status


@player_bp.route('/matchmaker')
@require_role('player')
def matchmaker():
    player_id = session.get('user_id')
    db = get_db()
    lobbies = []
    reservations = []
    search_query = request.args.get('search', '').strip()
    dupr_level = request.args.get('dupr_level', '').strip()
    selected_tab = request.args.get('tab', 'all').strip()

    try:
        # Fetch active court reservations that belong to this player to populate the dropdown
        today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, facilities(name), courts(name)'
        ).eq('player_id', player_id).eq('status', 'confirmed').gte('date', today_str).execute()
        reservations = res_resp.data or []

        # Filter out reservations already listed in matchmaker_lobbies
        already_listed = db.table('matchmaker_lobbies').select('reservation_id').eq('creator_id', player_id).neq('status', 'cancelled').execute()
        listed_ids = {r['reservation_id'] for r in (already_listed.data or [])}
        reservations = [r for r in reservations if r['id'] not in listed_ids]

        # Fetch joined matchmaking lobby IDs for tab filtering
        joined_lobby_ids = set()
        if player_id:
            my_joined = db.table('lobby_participants').select('lobby_id').eq('player_id', player_id).eq('status', 'joined').execute()
            joined_lobby_ids = {p['lobby_id'] for p in (my_joined.data or [])}

        # Fetch active lobbies (status: open, full, completed)
        lob_resp = db.table('matchmaker_lobbies').select(
            'id, creator_id, reservation_id, title, description, min_dupr, max_dupr, slots_total, slots_filled, status, created_at, match_type, '
            'creator:profiles!creator_id(first_name, last_name, elo, dupr, proficiency), '
            'reservation:court_reservations!reservation_id(date, start_time, end_time, courts(name), facilities(name))'
        ).neq('status', 'cancelled').order('created_at', desc=True).execute()

        raw_lobbies = lob_resp.data or []
        for lobby in raw_lobbies:
            creator = lobby.get('creator') or {}
            res = lobby.get('reservation') or {}
            court = res.get('courts') or {}
            facility = res.get('facilities') or {}

            lobby_item = {
                'id': lobby['id'],
                'creator_id': lobby['creator_id'],
                'title': lobby['title'],
                'description': lobby['description'],
                'min_dupr': float(lobby['min_dupr']),
                'max_dupr': float(lobby['max_dupr']),
                'slots_total': lobby['slots_total'],
                'slots_filled': lobby['slots_filled'],
                'status': lobby['status'],
                'match_type': lobby.get('match_type') or 'ranked',
                'creator_name': f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip() or "Anonymous Player",
                'creator_dupr': creator.get('dupr') if creator.get('dupr') is not None else 3.00,
                'facility_name': facility.get('name', 'Unknown Facility'),
                'court_name': court.get('name', 'Court'),
                'date': res.get('date') or today_str,
                'start_time': res.get('start_time') or '00:00',
                'end_time': res.get('end_time') or '00:00',
            }
            lobby_item['display_status'] = get_lobby_display_status(
                lobby_item['status'], lobby_item['date'], lobby_item['start_time'], lobby_item['end_time']
            )
            
            # Apply tab filters
            if selected_tab == 'hosted':
                if lobby_item['creator_id'] != player_id:
                    continue
            elif selected_tab == 'joined':
                if lobby_item['id'] not in joined_lobby_ids:
                    continue

            # Apply search filter
            if search_query:
                sq = search_query.lower()
                if (sq not in lobby_item['title'].lower() and 
                    sq not in lobby_item['creator_name'].lower() and
                    sq not in lobby_item['facility_name'].lower()):
                    continue

            # Apply DUPR category filters
            if dupr_level:
                if dupr_level == 'beginner' and not (2.0 <= lobby_item['min_dupr'] <= 3.24):
                    continue
                elif dupr_level == 'intermediate' and not (3.25 <= lobby_item['min_dupr'] <= 4.49):
                    continue
                elif dupr_level == 'advanced' and not (4.50 <= lobby_item['min_dupr'] <= 8.00):
                    continue

            lobbies.append(lobby_item)

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return render_template(
        'player/matchmaker.html',
        lobbies=lobbies,
        reservations=reservations,
        search_query=search_query,
        selected_level=dupr_level,
        selected_tab=selected_tab
    )


@player_bp.route('/matchmaker/create', methods=['POST'])
@require_role('player')
def matchmaker_create():
    player_id = session.get('user_id')
    reservation_id = request.form.get('reservation_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    min_dupr = float(request.form.get('min_dupr', 2.00))
    max_dupr = float(request.form.get('max_dupr', 8.00))
    slots_total = int(request.form.get('slots_total', 3))
    match_type = request.form.get('match_type', 'ranked').strip()

    if not all([reservation_id, title]):
        flash("Missing lobby creation fields.", "error")
        return redirect(url_for('player.matchmaker'))

    db = get_db()
    try:
        # Verify reservation belongs to player and is confirmed
        res = db.table('court_reservations').select('id, status').eq('id', reservation_id).eq('player_id', player_id).single().execute()
        if not res.data or res.data['status'] != 'confirmed':
            flash("Invalid or unconfirmed court booking.", "error")
            return redirect(url_for('player.matchmaker'))

        lobby_resp = db.table('matchmaker_lobbies').insert({
            'creator_id': player_id,
            'reservation_id': reservation_id,
            'title': title,
            'description': description,
            'min_dupr': min_dupr,
            'max_dupr': max_dupr,
            'slots_total': slots_total,
            'slots_filled': 0,
            'status': 'open',
            'match_type': match_type
        }).execute()

        if lobby_resp.data:
            lobby_id = lobby_resp.data[0]['id']
            try:
                # Initialize conversation for the lobby
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add creator as participant
                db.table('conversation_participants').insert({
                    'conversation_id': lobby_id,
                    'profile_id': player_id
                }).execute()
            except Exception as convo_err:
                print(f"Error creating lobby conversation: {convo_err}")

        flash("Matchmaking lobby published successfully!", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('player.matchmaker'))


@player_bp.route('/matchmaker/<lobby_id>')
@require_role('player', 'facilitystaff')
def matchmaker_detail(lobby_id):
    if session.get('role') == 'facilitystaff':
        return redirect(url_for('facilitystaff.matchmaker_detail', lobby_id=lobby_id))
    player_id = session.get('user_id')
    db = get_db()
    lobby = None
    participants = []
    is_joined = False
    winner_name = ""
    lobby_messages = []

    try:
        lob_resp = db.table('matchmaker_lobbies').select(
            'id, creator_id, reservation_id, title, description, min_dupr, max_dupr, slots_total, slots_filled, status, score, winner_id, match_type, '
            'reported_score, reported_winner_id, reporter_id, verification_status, dispute_count, '
            'creator:profiles!creator_id(first_name, last_name, elo, dupr, proficiency, avatar_url), '
            'reservation:court_reservations!reservation_id(date, start_time, end_time, courts(name), facilities(name))'
        ).eq('id', lobby_id).single().execute()

        if not lob_resp.data:
            flash("Lobby not found.", "error")
            return redirect(url_for('player.matchmaker'))

        raw_lob = lob_resp.data
        creator = raw_lob.get('creator') or {}
        res = raw_lob.get('reservation') or {}
        court = res.get('courts') or {}
        facility = res.get('facilities') or {}

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
        part_resp = db.table('lobby_participants').select(
            'id, player_id, status, team, slot, profiles!player_id(first_name, last_name, elo, dupr, avatar_url)'
        ).eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        
        raw_participants = part_resp.data or []
        
        # Build Team slots grid
        # Team 1 Slot 1 is always the Creator/Host
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
        else: # Fallback slots
            for s in range(1, lobby['slots_total'] + 1):
                slots_grid['team2'].append({'slot': s, 'player': None})

        participants = []
        occupied_slots = {
            (1, 1): True # Host is always Team 1, Slot 1
        }
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
            
            # First pass: map valid, non-conflicting slots
            if t in [1, 2] and s is not None:
                if (t, s) not in occupied_slots:
                    team_key = f"team{t}"
                    slot_idx = s - 1
                    if team_key in slots_grid and 0 <= slot_idx < len(slots_grid[team_key]):
                        slots_grid[team_key][slot_idx]['player'] = player_info
                        occupied_slots[(t, s)] = True
                        continue
            
            # Otherwise, map in the second pass
            unmapped_participants.append((p['id'], player_info))

        # Second pass: auto-heal conflicting/missing slot assignments
        for part_id, player_info in unmapped_participants:
            found = False
            # Find first empty slot, prioritizing Team 2, then Team 1
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
                        # Update DB to persist the heal
                        try:
                            db.table('lobby_participants').update({
                                'team': t_val,
                                'slot': s_val
                            }).eq('id', part_id).execute()
                            
                            # Also update the local list data
                            p_in_list = next((x for x in participants if x['id'] == part_id), None)
                            if p_in_list:
                                p_in_list['team'] = t_val
                                p_in_list['slot'] = s_val
                        except Exception as auto_heal_err:
                            print(f"[auto_heal] Failed to update slot for participant {part_id}: {auto_heal_err}")
                        break

        winner_name = None
        target_winner_id = lobby.get('winner_id') or lobby.get('reported_winner_id')
        if target_winner_id:
            # Find winner team name
            # Check if winner is Host or on Team 1
            is_winner_team1 = False
            if target_winner_id == lobby['creator_id']:
                is_winner_team1 = True
            else:
                for p in participants:
                    if p['player_id'] == target_winner_id and p.get('team') == 1:
                        is_winner_team1 = True
                        break
            
            if is_winner_team1:
                winner_name = "Team 1"
            else:
                winner_name = "Team 2"

        # Lazy initialize chat conversation for existing lobbies
        convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
        if not convo_check.data:
            try:
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add host
                db.table('conversation_participants').upsert({
                    'conversation_id': lobby_id,
                    'profile_id': lobby['creator_id']
                }, on_conflict='conversation_id,profile_id').execute()
                # Add current participants
                for p in participants:
                    db.table('conversation_participants').upsert({
                        'conversation_id': lobby_id,
                        'profile_id': p['player_id']
                    }, on_conflict='conversation_id,profile_id').execute()
            except Exception as lazy_err:
                print(f"Lazy conversation creation warning: {lazy_err}")

        # Fetch lobby chat messages
        try:
            msg_resp = db.table('messages').select(
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
                
                # Format time nicely (e.g. 02:30 PM)
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
        return redirect(url_for('player.matchmaker'))

    # Calculate teams for current user and reporter, and check if user is assigned staff
    current_user_team = None
    reporter_team = None
    is_assigned_staff = False
    if lobby:
        if session.get('role') == 'facilitystaff' and lobby.get('reservation_id'):
            try:
                admin_db = get_admin_db()
                res_resp = admin_db.table('court_reservations').select('facility_id').eq('id', lobby['reservation_id']).single().execute()
                if res_resp.data:
                    fac_id = res_resp.data['facility_id']
                    staff_check = admin_db.table('facility_staff').select('id').eq('facility_id', fac_id).eq('staff_id', player_id).execute()
                    if staff_check.data:
                        is_assigned_staff = True
            except Exception as staff_err:
                print(f"Error checking assigned staff: {staff_err}")

        if player_id == lobby['creator_id']:
            current_user_team = 1
        else:
            for p in participants:
                if p['player_id'] == player_id:
                    current_user_team = p.get('team')
                    break

        if lobby.get('reporter_id') == lobby['creator_id']:
            reporter_team = 1
        else:
            for p in participants:
                if p['player_id'] == lobby.get('reporter_id'):
                    reporter_team = p.get('team')
                    break

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
        is_assigned_staff=is_assigned_staff
    )


@player_bp.route('/matchmaker/<lobby_id>/join', methods=['POST'])
@require_role('player')
def matchmaker_join(lobby_id):
    player_id = session.get('user_id')
    team = request.form.get('team', type=int)
    slot = request.form.get('slot', type=int)
    db = get_db()
    
    try:
        # Get lobby details with court reservation info
        lob_resp = db.table('matchmaker_lobbies').select(
            'status, slots_total, slots_filled, creator_id, min_dupr, max_dupr, reservation_id, '
            'court_reservations(date, start_time, end_time)'
        ).eq('id', lobby_id).single().execute()
        
        lobby = lob_resp.data
        if not lobby or lobby['status'] != 'open':
            flash("Lobby is not open.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
        if lobby['creator_id'] == player_id:
            flash("You cannot join your own lobby.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Check for scheduling conflicts (prevent double-booking)
        res = lobby.get('court_reservations')
        if res:
            res_date = res.get('date')
            res_start = res.get('start_time')
            res_end = res.get('end_time')
            
            player_overlap = db.table('court_reservations').select('id')\
                .eq('player_id', player_id)\
                .eq('date', res_date)\
                .in_('status', ['confirmed', 'pending_payment'])\
                .lt('start_time', res_end)\
                .gt('end_time', res_start)\
                .execute()
                
            if player_overlap.data:
                flash("You already have another court reservation during this lobby's time slot.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Verify rating
        prof_resp = db.table('profiles').select('dupr').eq('id', player_id).single().execute()
        player_dupr = float(prof_resp.data.get('dupr') or 3.00)
        if not (float(lobby['min_dupr']) <= player_dupr <= float(lobby['max_dupr'])):
            flash("Your DUPR rating does not meet lobby requirements.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Check availability
        if lobby['slots_filled'] >= lobby['slots_total']:
            flash("Lobby is already full.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Resolve or validate empty slot choice
        if not team or not slot:
            # Auto-assign empty slot
            occupied = {}
            part_resp = db.table('lobby_participants').select('team, slot').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
            for p in (part_resp.data or []):
                occupied[(p['team'], p['slot'])] = True
                
            found = False
            if lobby['slots_total'] == 3: # Doubles
                for t, s in [(1, 2), (2, 1), (2, 2)]:
                    if (t, s) not in occupied:
                        team, slot = t, s
                        found = True
                        break
            else: # Singles / others
                for s in range(1, lobby['slots_total'] + 1):
                    if (2, s) not in occupied:
                        team, slot = 2, s
                        found = True
                        break
            if not found:
                flash("No empty slots available.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        else:
            # Validate slot is empty
            if team == 1 and slot == 1:
                flash("Host slot is occupied.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
                
            check_occ = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('team', team).eq('slot', slot).eq('status', 'joined').execute()
            if check_occ.data:
                flash("The requested slot is already occupied.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Insert participant
        db.table('lobby_participants').upsert({
            'lobby_id': lobby_id,
            'player_id': player_id,
            'status': 'joined',
            'team': team,
            'slot': slot
        }, on_conflict='lobby_id,player_id').execute()

        # Update slots count & status
        new_filled = lobby['slots_filled'] + 1
        status = 'full' if new_filled >= lobby['slots_total'] else 'open'
        admin_db = get_admin_db()
        admin_db.table('matchmaker_lobbies').update({
            'slots_filled': new_filled,
            'status': status
        }).eq('id', lobby_id).execute()

        try:
            # Ensure conversation exists
            convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
            if not convo_check.data:
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add creator too
                db.table('conversation_participants').upsert({
                    'conversation_id': lobby_id,
                    'profile_id': lobby['creator_id']
                }, on_conflict='conversation_id,profile_id').execute()

            # Add to conversation participants
            db.table('conversation_participants').upsert({
                'conversation_id': lobby_id,
                'profile_id': player_id
            }, on_conflict='conversation_id,profile_id').execute()
        except Exception as convo_err:
            print(f"Error adding player to conversation: {convo_err}")

        flash("Joined open play match lobby!", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/switch', methods=['POST'])
@require_role('player')
def matchmaker_switch(lobby_id):
    player_id = session.get('user_id')
    team = request.form.get('team', type=int)
    slot = request.form.get('slot', type=int)
    
    if not team or not slot:
        flash("Invalid slot selection.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    if team == 1 and slot == 1:
        flash("Cannot switch to host slot.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    db = get_db()
    try:
        # Verify lobby status
        lob_resp = db.table('matchmaker_lobbies').select('status').eq('id', lobby_id).single().execute()
        if not lob_resp.data or lob_resp.data['status'] not in ['open', 'full']:
            flash("Lobby is not editable.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Check if target slot is occupied
        occ_check = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('team', team).eq('slot', slot).eq('status', 'joined').execute()
        if occ_check.data:
            flash("Target slot is occupied.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Verify player is already joined
        my_part = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('player_id', player_id).eq('status', 'joined').execute()
        if not my_part.data:
            flash("You must be joined to switch slots.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Update slot
        db.table('lobby_participants').update({
            'team': team,
            'slot': slot
        }).eq('id', my_part.data[0]['id']).execute()
        
        flash("Switched slot successfully!", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/leave', methods=['POST'])
@require_role('player')
def matchmaker_leave(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        lob_resp = db.table('matchmaker_lobbies').select('slots_filled, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby:
            flash("Lobby not found.", "error")
            return redirect(url_for('player.matchmaker'))

        db.table('lobby_participants').delete().eq('lobby_id', lobby_id).eq('player_id', player_id).execute()

        # Update slots count & status
        new_filled = max(0, lobby['slots_filled'] - 1)
        admin_db = get_admin_db()
        admin_db.table('matchmaker_lobbies').update({
            'slots_filled': new_filled,
            'status': 'open'
        }).eq('id', lobby_id).execute()

        try:
            # Remove from conversation participants
            db.table('conversation_participants').delete().eq('conversation_id', lobby_id).eq('profile_id', player_id).execute()
        except Exception as convo_err:
            print(f"Error removing player from conversation: {convo_err}")

        flash("Left open play match lobby.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/message', methods=['POST'])
@require_role('player', 'facilitystaff')
def matchmaker_message(lobby_id):
    player_id = session.get('user_id')
    content = request.form.get('content', '').strip()
    if not content:
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    db = get_db()
    try:
        # Check if conversation exists
        convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
        if not convo_check.data:
            flash("Lobby chat is not initialized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Verify user is a participant of the conversation (or assigned facility staff mediating the match)
        is_assigned_staff = False
        if session.get('role') == 'facilitystaff':
            try:
                admin_db = get_admin_db()
                lob_resp = admin_db.table('matchmaker_lobbies').select('reservation_id').eq('id', lobby_id).single().execute()
                if lob_resp.data and lob_resp.data.get('reservation_id'):
                    res_resp = admin_db.table('court_reservations').select('facility_id').eq('id', lob_resp.data['reservation_id']).single().execute()
                    if res_resp.data:
                        fac_id = res_resp.data['facility_id']
                        staff_check = admin_db.table('facility_staff').select('id').eq('facility_id', fac_id).eq('staff_id', player_id).execute()
                        if staff_check.data:
                            is_assigned_staff = True
                            # Auto-upsert staff into conversation participants to grant select/insert permissions
                            admin_db.table('conversation_participants').upsert({
                                'conversation_id': lobby_id,
                                'profile_id': player_id
                            }, on_conflict='conversation_id,profile_id').execute()
            except Exception as staff_convo_err:
                print(f"Error checking and adding staff to conversation: {staff_convo_err}")

        if not is_assigned_staff:
            part_check = db.table('conversation_participants').select('profile_id').eq('conversation_id', lobby_id).eq('profile_id', player_id).execute()
            if not part_check.data:
                flash("You must join the lobby first to send messages.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Send message
        db.table('messages').insert({
            'conversation_id': lobby_id,
            'sender_id': player_id,
            'content': content
        }).execute()
        
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/edit', methods=['POST'])
@require_role('player')
def matchmaker_edit(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    min_dupr = float(request.form.get('min_dupr', 2.00))
    max_dupr = float(request.form.get('max_dupr', 8.00))
    slots_total = int(request.form.get('slots_total', 3))
    match_type = request.form.get('match_type', 'ranked').strip()
    
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    try:
        # Fetch lobby
        lob_resp = db.table('matchmaker_lobbies').select('creator_id, slots_filled, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['creator_id'] != player_id:
            flash("Unauthorized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if lobby['status'] == 'completed':
            flash("Cannot edit a completed match.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if slots_total < lobby['slots_filled']:
            flash(f"Cannot set slots total below the number of currently joined players ({lobby['slots_filled']}).", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Update lobby details
        status = 'full' if lobby['slots_filled'] >= slots_total else 'open'
        db.table('matchmaker_lobbies').update({
            'title': title,
            'description': description,
            'min_dupr': min_dupr,
            'max_dupr': max_dupr,
            'slots_total': slots_total,
            'status': status,
            'match_type': match_type
        }).eq('id', lobby_id).execute()
        
        flash("Match lobby updated successfully!", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/delete', methods=['POST'])
@require_role('player')
def matchmaker_delete(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        # Fetch lobby
        lob_resp = db.table('matchmaker_lobbies').select('creator_id, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['creator_id'] != player_id:
            flash("Unauthorized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if lobby['status'] == 'completed':
            flash("Cannot delete a completed match.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Delete lobby (cascades to participants)
        db.table('matchmaker_lobbies').delete().eq('id', lobby_id).execute()
        
        # Also clean up conversation
        try:
            db.table('conversations').delete().eq('id', lobby_id).execute()
        except Exception as convo_err:
            print(f"Error deleting lobby conversation: {convo_err}")
            
        flash("Matchmaking lobby deleted successfully.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    return redirect(url_for('player.matchmaker'))


@player_bp.route('/matchmaker/<lobby_id>/report', methods=['POST'])
@require_role('player', 'facilitystaff')
def matchmaker_report(lobby_id):
    player_id = session.get('user_id')
    winner_team = request.form.get('winner_team', 'team1') # 'team1' or 'team2'
    score = request.form.get('score', '').strip()
    host_score = request.form.get('host_score', type=int)
    opp_score = request.form.get('opp_score', type=int)

    admin_db = get_admin_db()
    try:
        # Fetch lobby details
        lob_resp = admin_db.table('matchmaker_lobbies').select('creator_id, status, reservation_id, dispute_count, reported_score, reported_winner_id, reporter_id, verification_status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby:
            flash("Lobby not found.", "error")
            return redirect(url_for('player.matchmaker'))

        # Fetch guests
        part_resp = admin_db.table('lobby_participants').select('player_id, team').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        joined = part_resp.data or []
        
        joined_player_ids = [p['player_id'] for p in joined] + [lobby['creator_id']]

        # Check if current user is assigned staff
        is_assigned_staff = False
        if session.get('role') == 'facilitystaff' and lobby.get('reservation_id'):
            res_resp = admin_db.table('court_reservations').select('facility_id').eq('id', lobby['reservation_id']).single().execute()
            if res_resp.data:
                fac_id = res_resp.data['facility_id']
                staff_check = admin_db.table('facility_staff').select('id').eq('facility_id', fac_id).eq('staff_id', player_id).execute()
                if staff_check.data:
                    is_assigned_staff = True

        # Check authorization based on lobby status
        if lobby['status'] == 'staff_mediation':
            if not is_assigned_staff:
                flash("Only the assigned facility staff member on duty can submit the final score.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
            # Staff submits the final score
            if winner_team == 'team1':
                winner_id = lobby['creator_id']
            else:
                team2_players = [p['player_id'] for p in joined if p.get('team') == 2]
                winner_id = team2_players[0] if team2_players else (joined[0]['player_id'] if joined else lobby['creator_id'])
            
            admin_db = get_admin_db()
            admin_db.table('matchmaker_lobbies').update({
                'status': 'completed',
                'score': score,
                'winner_id': winner_id,
                'verification_status': 'verified',
                'reported_score': score,
                'reported_winner_id': winner_id,
                'reporter_id': player_id
            }).eq('id', lobby_id).execute()

            # Trigger rating updates
            update_matchmaker_ratings(admin_db, lobby_id)
            
            flash("Match score finalized and ratings updated by staff!", "success")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # For normal players reporting:
        if lobby['status'] == 'completed':
            flash("Match already completed.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        if player_id not in joined_player_ids:
            flash("You are not authorized to report scores for this lobby.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Check if already pending verification (unless disputed)
        if lobby['status'] == 'pending_verification' and lobby.get('verification_status') != 'disputed':
            flash("Match score is already pending verification.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Map winner team to a player ID
        if winner_team == 'team1':
            winner_id = lobby['creator_id']
        else:
            team2_players = [p['player_id'] for p in joined if p.get('team') == 2]
            winner_id = team2_players[0] if team2_players else (joined[0]['player_id'] if joined else lobby['creator_id'])

        # Update lobby details to pending_verification and reset verification_status
        admin_db = get_admin_db()
        admin_db.table('matchmaker_lobbies').update({
            'status': 'pending_verification',
            'reported_score': score,
            'reported_winner_id': winner_id,
            'reporter_id': player_id,
            'verification_status': 'pending'
        }).eq('id', lobby_id).execute()

        # Send notifications to all other joined players
        for p in joined_player_ids:
            if p != player_id:
                try:
                    admin_db.table('notifications').insert({
                        'user_id': p,
                        'title': 'Match Score Reported',
                        'message': f'A score of "{score}" has been reported. Please verify or dispute it.',
                        'type': 'info',
                        'link': f'/player/matchmaker/{lobby_id}'
                    }).execute()
                except Exception as notif_err:
                    print(f"Failed to insert notification: {notif_err}")

        flash("Match score reported! Opponents must confirm before ratings update.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/verify', methods=['POST'])
@require_role('player', 'facilitystaff')
def matchmaker_verify(lobby_id):
    player_id = session.get('user_id')
    action = request.form.get('action') # 'confirm' or 'dispute'
    admin_db = get_admin_db()
    
    try:
        # 1. Fetch lobby details
        lob_resp = admin_db.table('matchmaker_lobbies').select('*').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['status'] != 'pending_verification':
            flash("Lobby not found or not pending verification.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # 2. Fetch joined participants to verify permissions and opposing team
        part_resp = admin_db.table('lobby_participants').select('player_id, team').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        participants = part_resp.data or []
        
        # Verify the user is part of the lobby
        joined_player_ids = [p['player_id'] for p in participants] + [lobby['creator_id']]
        if player_id not in joined_player_ids:
            flash("You are not a member of this match lobby.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Verify the user is not the one who reported the score
        if lobby['reporter_id'] == player_id:
            flash("You cannot verify or dispute the score you reported yourself.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Check teams to ensure opponent verification (not colluding teammate)
        reporter_team = None
        user_team = None
        
        # Creator (host) is always Team 1
        if lobby['creator_id'] == lobby['reporter_id']:
            reporter_team = 1
        else:
            for p in participants:
                if p['player_id'] == lobby['reporter_id']:
                    reporter_team = p.get('team') or 1
                    break
                    
        if player_id == lobby['creator_id']:
            user_team = 1
        else:
            for p in participants:
                if p['player_id'] == player_id:
                    user_team = p.get('team') or 1
                    break
                    
        if reporter_team == user_team:
            flash("A player from the opposing team must verify or dispute the score.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        if action == 'confirm':
            # 1. Mark lobby as completed and set verified status
            admin_db.table('matchmaker_lobbies').update({
                'status': 'completed',
                'score': lobby['reported_score'],
                'winner_id': lobby['reported_winner_id'],
                'verification_status': 'verified'
            }).eq('id', lobby_id).execute()
            
            # 2. Trigger rating updates
            update_matchmaker_ratings(admin_db, lobby_id)
            
            flash("Match score verified and ratings updated successfully!", "success")
            
        elif action == 'dispute':
            # Increment dispute count
            new_dispute_count = (lobby.get('dispute_count') or 0) + 1
            
            if new_dispute_count >= 3:
                # Escalation to staff mediation!
                # 1. Get facility ID
                res_resp = admin_db.table('court_reservations').select('facility_id').eq('id', lobby['reservation_id']).single().execute()
                if res_resp.data:
                    fac_id = res_resp.data['facility_id']
                    
                    # 2. Get all staff members for this facility
                    staff_resp = admin_db.table('facility_staff').select('staff_id, profiles(first_name, last_name)').eq('facility_id', fac_id).execute()
                    staff_list = staff_resp.data or []
                    
                    # 3. Add staff to the lobby's chat (conversation_participants)
                    staff_added_names = []
                    for s in staff_list:
                        s_id = s.get('staff_id')
                        if s_id:
                            admin_db.table('conversation_participants').upsert({
                                'conversation_id': lobby_id,
                                'profile_id': s_id
                            }, on_conflict='conversation_id,profile_id').execute()
                            
                            prof = s.get('profiles') or {}
                            staff_added_names.append(f"{prof.get('first_name', 'Staff')} {prof.get('last_name', '')}".strip())
                    
                    # 4. Insert auto message in chat
                    staff_names_str = ", ".join(staff_added_names) or "Facility Staff"
                    med_message = f"⚠️ [SYSTEM] This match result has been disputed 3 times. The lobby is now in Staff Mediation. Staff member(s) ({staff_names_str}) have joined the chat to resolve this. Only staff can now submit the final score."
                    admin_db.table('messages').insert({
                        'conversation_id': lobby_id,
                        'sender_id': None,
                        'content': med_message
                    }).execute()
                    
                # Update lobby status to staff_mediation
                admin_db.table('matchmaker_lobbies').update({
                    'status': 'staff_mediation',
                    'dispute_count': new_dispute_count,
                    'verification_status': 'disputed'
                }).eq('id', lobby_id).execute()
                
                flash("Match has been disputed 3 times. Escalated to Facility Staff Mediation.", "warning")
                
            else:
                # Set verification status to disputed
                admin_db.table('matchmaker_lobbies').update({
                    'verification_status': 'disputed',
                    'dispute_count': new_dispute_count
                }).eq('id', lobby_id).execute()
                
                # Send notification to the reporter
                try:
                    admin_db.table('notifications').insert({
                        'user_id': lobby['reporter_id'],
                        'title': 'Match Score Disputed',
                        'message': f'Your reported score has been disputed (Dispute count: {new_dispute_count}/3). Please coordinate resubmission.',
                        'type': 'warning',
                        'link': f'/player/matchmaker/{lobby_id}'
                    }).execute()
                except Exception as notif_err:
                    print(f"Failed to insert dispute notification: {notif_err}")
                    
                flash(f"Match score has been marked as disputed (Dispute count: {new_dispute_count}/3). Either team can resubmit.", "warning")
        else:
            flash("Invalid verification action.", "error")
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
