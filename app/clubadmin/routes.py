from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from flask import g
import os
from supabase import create_client

_cached_db = None

def get_db():
    global _cached_db
    if _cached_db is None:
        import os
        import httpx
        from supabase import create_client, ClientOptions
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        if url and key:
            http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
            options = ClientOptions(httpx_client=http_client)
            _cached_db = create_client(url, key, options=options)
    return _cached_db

clubadmin_bp = Blueprint('clubadmin', __name__, url_prefix='/clubadmin')

@clubadmin_bp.before_request
@require_role('clubadmin')
def load_club():
    if request.endpoint == 'auth.logout':
        return
        
    admin_id = session.get('user_id')
    if not admin_id:
        return
        
    db = get_db()
    try:
        resp = db.table('clubs').select('*').eq('admin_id', admin_id).single().execute()
        g.club = resp.data
    except Exception:
        g.club = None

    # Redirect to setup if no club exists and not already on setup page
    if not g.club and request.endpoint and request.endpoint not in ['clubadmin.club_setup', 'clubadmin.profile', 'auth.logout']:
        flash("Please set up your club profile first.", "info")
        return redirect(url_for('clubadmin.club_setup'))

@clubadmin_bp.route('/club-setup', methods=['GET', 'POST'])
@require_role('clubadmin')
def club_setup():
    admin_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        membership_type = request.form.get('membership_type', 'free')
        membership_fee = request.form.get('membership_fee', 0)
        
        if not name:
            flash("Club name is required.", "error")
            return redirect(url_for('clubadmin.club_setup'))
            
        update_data = {
            'admin_id': admin_id,
            'name': name,
            'description': description,
            'location': location,
            'membership_type': membership_type,
            'membership_fee': float(membership_fee) if membership_type == 'paid' else 0,
            'status': 'active'
        }
        
        # Handle logo upload
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            try:
                import time
                ext = logo_file.filename.split('.')[-1]
                filename = f"club_{admin_id}_{int(time.time())}.{ext}"
                db.storage.from_('community-images').upload(
                    file=logo_file.read(),
                    path=filename,
                    file_options={"content-type": logo_file.content_type}
                )
                update_data['logo_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                flash(f"Warning: Logo upload failed - {e}", "warning")
                
        try:
            if g.club:
                db.table('clubs').update(update_data).eq('id', g.club['id']).execute()
                flash("Club profile updated.", "success")
            else:
                db.table('clubs').insert(update_data).execute()
                flash("Club created successfully!", "success")
            return redirect(url_for('clubadmin.dashboard'))
        except Exception as e:
            flash(f"Error saving club: {e}", "error")
            
    return render_template('clubadmin/club_setup.html')

@clubadmin_bp.route('/dashboard')
@require_role('clubadmin')
def dashboard():
    db = get_db()
    stats = {'members': 0, 'events': 0, 'top_player': None, 'recent_members': [], 'activity': []}
    
    if g.club:
        try:
            # Members count
            mem_resp = db.table('club_memberships').select('id', count='exact').eq('club_id', g.club['id']).eq('status', 'active').execute()
            stats['members'] = mem_resp.count or 0
            
            # Upcoming Events count
            admin_id = session.get('user_id')
            ev_resp = db.table('events').select('id', count='exact').eq('organizer_id', admin_id).in_('status', ['registration_open', 'upcoming', 'full']).execute()
            stats['events'] = ev_resp.count or 0
            
            # Recent members
            recent_resp = db.table('club_memberships').select(
                'id, status, joined_at, profiles!player_id(first_name, last_name)'
            ).eq('club_id', g.club['id']).order('joined_at', desc=True).limit(5).execute()
            stats['recent_members'] = recent_resp.data or []
            
            # Activity feed
            act_resp = db.table('notifications').select('*').eq('user_id', admin_id).order('created_at', desc=True).limit(5).execute()
            stats['activity'] = act_resp.data or []
            
        except Exception as e:
            print("Dashboard error:", e)
            
    return render_template('clubadmin/dashboard.html', stats=stats)

@clubadmin_bp.route('/members')
@require_role('clubadmin')
def members():
    db = get_db()
    members_list = []
    
    if g.club:
        try:
            resp = db.table('club_memberships').select(
                'id, status, joined_at, gcash_ref, player_id, profiles!player_id(first_name, last_name, phone)'
            ).eq('club_id', g.club['id']).order('joined_at', desc=True).execute()
            members_list = resp.data or []
        except Exception as e:
            flash(f"Error loading members: {e}", "error")
            
    return render_template('clubadmin/members.html', members=members_list)

@clubadmin_bp.route('/members/<membership_id>/approve', methods=['POST'])
@require_role('clubadmin')
def approve_member(membership_id):
    db = get_db()
    if not g.club:
        return redirect(url_for('clubadmin.dashboard'))
        
    try:
        db.table('club_memberships').update({'status': 'active'}).eq('id', membership_id).eq('club_id', g.club['id']).execute()
        flash("Member approved successfully.", "success")
    except Exception as e:
        flash(f"Error approving member: {e}", "error")
    return redirect(url_for('clubadmin.members'))

@clubadmin_bp.route('/members/<membership_id>/remove', methods=['POST'])
@require_role('clubadmin')
def remove_member(membership_id):
    db = get_db()
    if not g.club:
        return redirect(url_for('clubadmin.dashboard'))
        
    try:
        db.table('club_memberships').delete().eq('id', membership_id).eq('club_id', g.club['id']).execute()
        flash("Member removed.", "success")
    except Exception as e:
        flash(f"Error removing member: {e}", "error")
    return redirect(url_for('clubadmin.members'))

@clubadmin_bp.route('/events')
@require_role('clubadmin')
def events():
    clubadmin_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        ev_resp = db.table('events').select(
            'id, title, type, event_date, start_time, end_time, max_players, status, location_label, organizer_id, facilities(name)'
        ).eq('organizer_id', clubadmin_id).order('event_date', desc=False).execute()
        events_list = ev_resp.data or []
        
        for ev in events_list:
            reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', ev['id']).eq('status', 'registered').execute()
            ev['registered_count'] = reg_resp.count if reg_resp.count is not None else 0
            
    except Exception as e:
        flash(f'Error loading events: {e}', 'error')
        
    return render_template('clubadmin/events.html', events=events_list)

@clubadmin_bp.route('/events/<event_id>/participants')
@require_role('clubadmin')
def event_participants(event_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    event_details = None
    participants = []
    
    try:
        # Verify event belongs to this clubadmin
        ev_resp = db.table('events').select('id, title, event_date').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        event_details = ev_resp.data
        
        if event_details:
            # Fetch participants
            reg_resp = db.table('event_registrations').select(
                'id, status, registered_at, profiles!player_id(first_name, last_name, phone)'
            ).eq('event_id', event_id).execute()
            participants = reg_resp.data or []
        else:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('clubadmin.events'))
            
    except Exception as e:
        flash(f'Error loading participants: {e}', 'error')
        
    return render_template('clubadmin/event_participants.html', event=event_details, participants=participants)

@clubadmin_bp.route('/tournaments')
@require_role('clubadmin')
def tournaments():
    admin_id = session.get('user_id')
    db = get_db()
    tournaments_list = []
    try:
        resp = db.table('events').select(
            'id, title, event_date, status'
        ).eq('organizer_id', admin_id).eq('type', 'tournament').order('event_date', desc=False).execute()
        tournaments_list = resp.data or []
        
        for t in tournaments_list:
            reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', t['id']).eq('status', 'registered').execute()
            t['registered_count'] = reg_resp.count or 0
    except Exception as e:
        flash(f"Error loading tournaments: {e}", "error")
        
    return render_template('clubadmin/tournaments.html', tournaments=tournaments_list)

@clubadmin_bp.route('/tournaments/<event_id>/manage')
@require_role('clubadmin')
def tournament_manage(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        ev_resp = db.table('events').select('*').eq('id', event_id).eq('organizer_id', admin_id).eq('type', 'tournament').single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('clubadmin.tournaments'))
            
        # Get all tournaments for dropdown
        all_t_resp = db.table('events').select('id, title').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        all_tournaments = all_t_resp.data or []
        
        # Get participants
        reg_resp = db.table('event_registrations').select(
            'player_id, profiles!player_id(first_name, last_name)'
        ).eq('event_id', event_id).eq('status', 'registered').execute()
        participants = reg_resp.data or []
        
        # Get matches
        matches_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, '
            'player1:profiles!player1_id(id, first_name, last_name), '
            'player2:profiles!player2_id(id, first_name, last_name), '
            'winner:profiles!winner_id(id, first_name, last_name)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = matches_resp.data or []
        
        # Bracket Generation logic check
        has_bracket = len(matches) > 0
        
        return render_template('clubadmin/tournament_manage.html', 
                               event=event, 
                               all_tournaments=all_tournaments,
                               participants=participants,
                               matches=matches,
                               has_bracket=has_bracket)
                               
    except Exception as e:
        flash(f"Error loading tournament manage: {e}", "error")
        return redirect(url_for('clubadmin.tournaments'))

@clubadmin_bp.route('/tournaments/<event_id>/bracket/generate', methods=['POST'])
@require_role('clubadmin')
def bracket_generate(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        # Get participants
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
        players = [r['player_id'] for r in (reg_resp.data or [])]
        
        if len(players) < 2:
            flash("Not enough players to generate a bracket.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))
            
        # Very simple bracket generation (pairs players up)
        # In a real app, you'd calculate powers of 2 and byes.
        import random
        random.shuffle(players)
        
        matches_to_insert = []
        match_num = 1
        for i in range(0, len(players), 2):
            p1 = players[i]
            p2 = players[i+1] if i+1 < len(players) else None
            
            matches_to_insert.append({
                'event_id': event_id,
                'round_number': 1,
                'match_number': match_num,
                'player1_id': p1,
                'player2_id': p2,
                'status': 'pending' if p2 else 'completed',
                'winner_id': p1 if not p2 else None # Bye
            })
            match_num += 1
            
        if matches_to_insert:
            db.table('tournament_matches').insert(matches_to_insert).execute()
            
        flash("Bracket generated successfully!", "success")
        
    except Exception as e:
        flash(f"Error generating bracket: {e}", "error")
        
    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

def _advance_bracket(db, event_id):
    """Check current round completion and auto-generate next round or declare champion."""
    try:
        # Get all matches grouped by round
        all_m = db.table('tournament_matches').select(
            'id, round_number, status, winner_id'
        ).eq('event_id', event_id).order('round_number').execute()
        matches = all_m.data or []
        if not matches:
            return

        max_round = max(m['round_number'] for m in matches)
        round_matches = [m for m in matches if m['round_number'] == max_round]

        # Only proceed if ALL matches in the current round are completed
        if any(m['status'] != 'completed' for m in round_matches):
            return

        winners = [m['winner_id'] for m in round_matches if m['winner_id']]

        if len(winners) == 1:
            # 🏆 Tournament champion decided
            db.table('events').update({'status': 'completed'}).eq('id', event_id).execute()
            try:
                db.table('notifications').insert({
                    'user_id': winners[0],
                    'title': '🏆 Tournament Champion!',
                    'message': 'Congratulations! You have won the tournament!',
                    'type': 'success'
                }).execute()
            except Exception:
                pass
            return

        # Generate next round — pair winners sequentially
        next_round = max_round + 1
        match_num = 1
        next_matches = []
        for i in range(0, len(winners), 2):
            p1 = winners[i]
            p2 = winners[i + 1] if i + 1 < len(winners) else None
            next_matches.append({
                'event_id': event_id,
                'round_number': next_round,
                'match_number': match_num,
                'player1_id': p1,
                'player2_id': p2,
                'status': 'completed' if not p2 else 'pending',
                'winner_id': p1 if not p2 else None,  # BYE auto-wins
            })
            match_num += 1
        if next_matches:
            db.table('tournament_matches').insert(next_matches).execute()
            # If the only new match was a BYE, recurse to check again
            if len(next_matches) == 1 and next_matches[0]['status'] == 'completed':
                _advance_bracket(db, event_id)
    except Exception as e:
        print(f"Bracket advancement error: {e}")


@clubadmin_bp.route('/tournaments/<event_id>/matches/<match_id>/score', methods=['POST'])
@require_role('clubadmin')
def match_score(event_id, match_id):
    admin_id = session.get('user_id')
    db = get_db()

    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    winner_id = request.form.get('winner_id') or None

    try:
        # Verify ownership
        db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()

        db.table('tournament_matches').update({
            'player1_score': p1_score,
            'player2_score': p2_score,
            'winner_id': winner_id,
            'status': 'completed',
            'played_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', match_id).eq('event_id', event_id).execute()

        # Calculate and update player ratings
        from app.ratings import update_match_ratings
        update_match_ratings(db, match_id)

        # Auto-advance bracket
        _advance_bracket(db, event_id)
        flash("Score recorded! Bracket and ratings updated.", "success")

    except Exception as e:
        flash(f"Error recording score: {e}", "error")

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/leaderboard')
@require_role('clubadmin')
def leaderboard():
    admin_id = session.get('user_id')
    db = get_db()
    rankings = []

    try:
        # Get all tournaments run by this admin
        ev_resp = db.table('events').select('id').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        event_ids = [e['id'] for e in (ev_resp.data or [])]

        if event_ids:
            # Fetch all completed matches for these tournaments
            matches_resp = db.table('tournament_matches').select(
                'player1_id, player2_id, winner_id, status'
            ).in_('event_id', event_ids).eq('status', 'completed').execute()
            matches = matches_resp.data or []

            # Aggregate per player
            stats = {}
            for m in matches:
                for pid in [m['player1_id'], m['player2_id']]:
                    if pid is None:
                        continue
                    if pid not in stats:
                        stats[pid] = {'wins': 0, 'losses': 0, 'played': 0}
                    stats[pid]['played'] += 1
                    if m['winner_id'] == pid:
                        stats[pid]['wins'] += 1
                    else:
                        stats[pid]['losses'] += 1

            if stats:
                # Fetch player profiles
                player_ids = list(stats.keys())
                prof_resp = db.table('profiles').select('id, first_name, last_name, elo, dupr, proficiency').in_('id', player_ids).execute()
                profiles_map = {p['id']: p for p in (prof_resp.data or [])}

                from app.ratings import get_initial_rating

                for pid, s in stats.items():
                    prof = profiles_map.get(pid, {})
                    
                    elo = prof.get('elo')
                    dupr = prof.get('dupr')
                    if elo is None or dupr is None:
                        elo_def, dupr_def = get_initial_rating(prof.get('proficiency'))
                        if elo is None: elo = elo_def
                        if dupr is None: dupr = dupr_def

                    win_rate = round((s['wins'] / s['played']) * 100) if s['played'] > 0 else 0
                    rankings.append({
                        'id': pid,
                        'name': f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip(),
                        'initials': ((prof.get('first_name') or ' ')[0] + (prof.get('last_name') or ' ')[0]).upper(),
                        'played': s['played'],
                        'wins': s['wins'],
                        'losses': s['losses'],
                        'win_rate': win_rate,
                        'elo': elo,
                        'dupr': dupr,
                    })

                # Sort by Elo desc, then wins desc
                rankings.sort(key=lambda x: (-x['elo'], -x['wins']))

    except Exception as e:
        flash(f"Error loading leaderboard: {e}", "error")

    return render_template('clubadmin/leaderboard.html', rankings=rankings)

@clubadmin_bp.route('/profile', methods=['GET', 'POST'])
@require_role('clubadmin')
def profile():
    user_id = session.get('user_id')
    db = get_db()
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        try:
            db.table('profiles').update({
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }).eq('id', user_id).execute()
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['phone'] = phone
            flash("Profile updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('clubadmin.profile'))
    return render_template('clubadmin/profile.html')

@clubadmin_bp.route('/notifications')
@require_role('clubadmin')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('clubadmin/notifications.html', notifications=notifs)

@clubadmin_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('clubadmin')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@clubadmin_bp.route('/messages')
@require_role('clubadmin')
def messages():
    return render_template('clubadmin/messages.html')

@clubadmin_bp.route('/community')
@require_role('clubadmin')
def community():
    return render_template('clubadmin/community.html')

@clubadmin_bp.route('/tutorials')
@require_role('clubadmin')
def tutorials():
    return render_template('clubadmin/tutorials.html')

# --- Club Admin Event CRUD ---

@clubadmin_bp.route('/events/create', methods=['GET', 'POST'])
@require_role('clubadmin')
def create_event():
    clubadmin_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'GET':
        # Fetch all active facilities
        facilities_list = []
        try:
            fac_resp = db.table('facilities').select('id, name, location').eq('status', 'active').execute()
            facilities_list = fac_resp.data or []
        except Exception as e:
            flash(f'Error loading facilities: {e}', 'error')
        return render_template('clubadmin/create_event.html', facilities=facilities_list)
        
    # POST
    facility_id   = request.form.get('facility_id') # Could be empty
    court_ids     = request.form.getlist('court_ids')
    title         = request.form.get('title', '').strip()
    event_type    = request.form.get('type', 'social')
    description   = request.form.get('description', '').strip()
    event_date    = request.form.get('event_date')
    start_time    = request.form.get('start_time')
    end_time      = request.form.get('end_time')
    max_players   = request.form.get('max_players', 16)
    entry_fee     = request.form.get('entry_fee', 0)
    location_label = request.form.get('location_label', '').strip()
    event_format  = request.form.get('format', 'Doubles').strip()
    prize_pool    = request.form.get('prize_pool', 0)
    reg_type      = request.form.get('registration_type', 'paid')
    
    if reg_type == 'free':
        entry_fee = 0

    if not all([title, event_date, start_time, end_time]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('clubadmin.create_event'))

    # Handle Image Upload
    image_file = request.files.get('image')
    image_url = None
    if image_file and image_file.filename:
        try:
            import time
            ext = image_file.filename.split('.')[-1]
            filename = f"events/{clubadmin_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('community-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('community-images').get_public_url(filename)
        except Exception as e:
            flash(f'Warning: Image could not be uploaded.', 'error')

    # Calculate status: if facility is chosen, assume pending payment to facility
    event_status = 'pending_payment' if facility_id else 'registration_open'

    try:
        insert_data = {
            'organizer_id': clubadmin_id,
            'title': title,
            'type': event_type,
            'format': event_format,
            'description': description,
            'event_date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'max_players': int(max_players),
            'entry_fee': float(entry_fee),
            'prize_pool': float(prize_pool) if prize_pool else 0,
            'location_label': location_label,
            'image_url': image_url,
            'status': event_status,
        }
        if facility_id:
            insert_data['facility_id'] = facility_id
            
        ev_resp = db.table('events').insert(insert_data).execute()

        if ev_resp.data:
            event_id = ev_resp.data[0]['id']
            if facility_id and court_ids:
                court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
                db.table('event_courts').insert(court_rows).execute()
                
            if facility_id:
                flash(f'Event "{title}" saved. Please complete facility payment to publish.', 'success')
                return redirect(url_for('clubadmin.facility_payment', event_id=event_id))
            else:
                flash(f'Event "{title}" published successfully!', 'success')
                return redirect(url_for('clubadmin.events'))
                
    except Exception as e:
        flash(f'Error creating event: {e}', 'error')

    return redirect(url_for('clubadmin.events'))

@clubadmin_bp.route('/events/<event_id>/facility_payment', methods=['GET', 'POST'])
@require_role('clubadmin')
def facility_payment(event_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    try:
        ev_resp = db.table('events').select('*, facilities(name)').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        event = ev_resp.data
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('clubadmin.events'))
            
        if request.method == 'GET':
            # Calculate mock price
            court_resp = db.table('event_courts').select('court_id, courts(hourly_rate)').eq('event_id', event_id).execute()
            courts = court_resp.data or []
            total_rate = sum([c['courts']['hourly_rate'] for c in courts if c.get('courts')])
            
            # Very basic hour diff (assuming HH:MM formatted within same day)
            sh = float(event['start_time'][:2]) + float(event['start_time'][3:5])/60.0
            eh = float(event['end_time'][:2]) + float(event['end_time'][3:5])/60.0
            hours = eh - sh if eh > sh else 1
            total_price = total_rate * hours
            
            return render_template('clubadmin/facility_payment.html', event=event, total_price=total_price, courts_count=len(courts), hours=round(hours,1))
            
        # POST: Payment complete
        db.table('events').update({'status': 'registration_open'}).eq('id', event_id).execute()
        flash('Facility payment confirmed. Event published!', 'success')
        return redirect(url_for('clubadmin.events'))
        
    except Exception as e:
        flash(f'Error processing payment: {e}', 'error')
        return redirect(url_for('clubadmin.events'))

@clubadmin_bp.route('/events/<event_id>/edit', methods=['GET', 'POST'])
@require_role('clubadmin')
def edit_event(event_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    
    try:
        ev_resp = db.table('events').select('*').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        event = ev_resp.data
        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('clubadmin.events'))
            
        if request.method == 'GET':
            fac_full_resp = db.table('facilities').select('id, name, location').eq('status', 'active').execute()
            facilities_list = fac_full_resp.data or []
            return render_template('clubadmin/edit_event.html', event=event, facilities=facilities_list)
            
        # POST
        facility_id   = request.form.get('facility_id')
        title         = request.form.get('title', '').strip()
        event_type    = request.form.get('type', 'social')
        description   = request.form.get('description', '').strip()
        event_date    = request.form.get('event_date')
        start_time    = request.form.get('start_time')
        end_time      = request.form.get('end_time')
        max_players   = request.form.get('max_players', 16)
        entry_fee     = request.form.get('entry_fee', 0)
        location_label = request.form.get('location_label', '').strip()
        event_format  = request.form.get('format', 'Doubles').strip()
        prize_pool    = request.form.get('prize_pool', 0)
        reg_type      = request.form.get('registration_type', 'paid')
        
        if reg_type == 'free':
            entry_fee = 0
            
        if not all([title, event_date, start_time, end_time]):
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('clubadmin.edit_event', event_id=event_id))
            
        update_data = {
            'title': title,
            'type': event_type,
            'format': event_format,
            'description': description,
            'event_date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'max_players': int(max_players),
            'entry_fee': float(entry_fee),
            'prize_pool': float(prize_pool) if prize_pool else 0,
            'location_label': location_label,
        }
        if facility_id:
            update_data['facility_id'] = facility_id
        else:
            update_data['facility_id'] = None
            
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            try:
                import time
                ext = image_file.filename.split('.')[-1]
                filename = f"events/{clubadmin_id}_{int(time.time())}.{ext}"
                file_bytes = image_file.read()
                db.storage.from_('community-images').upload(
                    file=file_bytes,
                    path=filename,
                    file_options={"content-type": image_file.content_type}
                )
                update_data['image_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                flash(f'Warning: Image could not be uploaded.', 'warning')
                
        db.table('events').update(update_data).eq('id', event_id).execute()
        
        court_ids = request.form.getlist('court_ids')
        db.table('event_courts').delete().eq('event_id', event_id).execute()
        if facility_id and court_ids:
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()
            
        flash('Event updated successfully!', 'success')
        return redirect(url_for('clubadmin.event_participants', event_id=event_id))
        
    except Exception as e:
        flash(f"Error updating event: {e}", "error")
        return redirect(url_for('clubadmin.events'))

@clubadmin_bp.route('/events/<event_id>/delete', methods=['POST'])
@require_role('clubadmin')
def delete_event(event_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    try:
        ev_resp = db.table('events').select('title').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('clubadmin.events'))
            
        title = ev_resp.data['title']
        
        # Notify
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).execute()
        if reg_resp.data:
            notifs = []
            for r in reg_resp.data:
                notifs.append({
                    'user_id': r['player_id'],
                    'title': f'Event Cancelled: {title}',
                    'message': f'The event "{title}" has been cancelled and removed.',
                    'type': 'system'
                })
            db.table('notifications').insert(notifs).execute()
            
        db.table('events').delete().eq('id', event_id).execute()
        flash(f'Event "{title}" deleted successfully.', 'success')
        
    except Exception as e:
        flash(f'Error deleting event: {e}', 'error')
        
    return redirect(url_for('clubadmin.events'))

# ── API: Courts by Facility (for JS fetch in create_event) ────────────────────
@clubadmin_bp.route('/api/courts_by_facility/<facility_id>')
@require_role('clubadmin')
def api_courts_by_facility(facility_id):
    db = get_db()
    try:
        resp = db.table('courts').select('id, name, type, hourly_rate').eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Support ───────────────────────────────────────────────────────────────────
@clubadmin_bp.route('/support')
@require_role('clubadmin')
def support():
    return render_template('clubadmin/support.html')


# ── Event Status Lifecycle ────────────────────────────────────────────────────
@clubadmin_bp.route('/events/<event_id>/status', methods=['POST'])
@require_role('clubadmin')
def change_event_status(event_id):
    admin_id = session.get('user_id')
    new_status = request.form.get('status', '').strip()
    allowed = ['upcoming', 'registration_open', 'full', 'in_progress', 'completed', 'cancelled']
    if new_status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for('clubadmin.events'))

    db = get_db()
    try:
        # Verify organizer ownership
        ev_resp = db.table('events').select('id, title, organizer_id').eq('id', event_id).single().execute()
        ev = ev_resp.data
        if not ev or ev['organizer_id'] != admin_id:
            flash("Access denied.", "error")
            return redirect(url_for('clubadmin.events'))

        db.table('events').update({'status': new_status}).eq('id', event_id).execute()
        label = new_status.replace('_', ' ').title()
        flash(f"Event status changed to '{label}'.", "success")

        # If cancelled, notify all registered players
        if new_status == 'cancelled':
            reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
            for reg in (reg_resp.data or []):
                db.table('notifications').insert({
                    'user_id': reg['player_id'],
                    'title': f'Event Cancelled: {ev["title"]}',
                    'message': f'"{ev["title"]}" has been cancelled by the organizer.',
                    'type': 'warning'
                }).execute()
    except Exception as e:
        flash(f"Error updating status: {e}", "error")

    return redirect(url_for('clubadmin.events'))

