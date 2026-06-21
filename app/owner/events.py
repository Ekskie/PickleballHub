import time
import random
from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash, jsonify, current_app
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp
from app.owner.routes import PH_TZ

# ── Events (on owner's courts) ─────────────────────────────────────────────────
@owner_bp.route('/events')
@require_role('owner')
def events():
    owner_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        # Get facilities owned by this owner
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]

        if fac_ids:
            ev_resp = db.table('events').select(
                'id, title, type, event_date, start_time, end_time, max_players, status, location_label, organizer_id, '
                'facilities(name), profiles!organizer_id(first_name, last_name)'
            ).in_('facility_id', fac_ids).order('event_date', desc=False).execute()
            events_list = ev_resp.data or []

            # Attach registration count (optimized batch query)
            if events_list:
                ev_ids = [ev['id'] for ev in events_list]
                reg_resp = db.table('event_registrations').select('event_id').in_('event_id', ev_ids).eq('status', 'registered').execute()
                reg_data = reg_resp.data or []
                
                from collections import Counter
                reg_counts = Counter(r['event_id'] for r in reg_data)
                
                for ev in events_list:
                    ev['registered_count'] = reg_counts[ev['id']]
    except Exception as e:
        current_app.logger.error(f"Error loading events for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return render_template('owner/events.html', events=events_list)


@owner_bp.route('/events/<event_id>/participants')
@require_role('owner')
def event_participants(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    event_details = None
    participants = []
    try:
        # Verify event belongs to one of owner's facilities
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        
        if fac_ids:
            ev_resp = db.table('events').select('id, title, event_date, entry_fee, prize_pool').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
            event_details = ev_resp.data
            
            if event_details:
                # Fetch participants with joined profiles (email is fetched directly from database)
                reg_resp = db.table('event_registrations').select(
                    'id, status, registered_at, player_id, check_in_status, checked_in_at, profiles!player_id(first_name, last_name, phone, avatar_url, email)'
                ).eq('event_id', event_id).execute()
                participants = reg_resp.data or []
            else:
                flash("Event not found or unauthorized.", "error")
                return redirect(url_for('owner.events'))
                
    except Exception as e:
        current_app.logger.error(f"Error fetching participants for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('owner/event_participants.html', event=event_details, participants=participants)

@owner_bp.route('/events/<event_id>/registrations/<reg_id>/checkin', methods=['POST'])
@require_role('owner')
def event_check_in(event_id, reg_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    status = request.form.get('status', 'pending')
    if status not in ['pending', 'checked_in', 'no_show']:
        status = 'pending'
        
    checked_in_at = datetime.now(PH_TZ).isoformat() if status == 'checked_in' else None
    
    try:
        # Verify event belongs to one of owner's facilities
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        db.table('event_registrations').update({
            'check_in_status': status,
            'checked_in_at': checked_in_at
        }).eq('id', reg_id).eq('event_id', event_id).execute()
        
        flash("Participant attendance updated.", "success")
    except Exception as e:
        current_app.logger.error(f"Error checking in participant {reg_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.event_participants', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/manage')
@require_role('owner')
def tournament_manage(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('*').eq('id', event_id).in_('facility_id', fac_ids).eq('type', 'tournament').single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('owner.events'))
            
        # Get all tournaments for dropdown
        all_t_resp = db.table('events').select('id, title').in_('facility_id', fac_ids).eq('type', 'tournament').execute()
        all_tournaments = all_t_resp.data or []
        
        # Get participants
        reg_resp = db.table('event_registrations').select(
            'player_id, profiles!player_id(first_name, last_name)'
        ).eq('event_id', event_id).eq('status', 'registered').execute()
        participants = reg_resp.data or []
        
        # Get matches
        matches_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, court_id, court_name, referee_name, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = matches_resp.data or []
        
        # Get booked courts for this event
        court_resp = db.table('event_courts').select(
            'court_id, courts(id, name)'
        ).eq('event_id', event_id).execute()
        booked_courts = court_resp.data or []
        
        has_bracket = len(matches) > 0
        
        return render_template('owner/tournament_manage.html', 
                               event=event, 
                               all_tournaments=all_tournaments,
                               participants=participants,
                               matches=matches,
                               has_bracket=has_bracket,
                               booked_courts=booked_courts)
                               
    except Exception as e:
        current_app.logger.error(f"Error managing tournament {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('owner.events'))

@owner_bp.route('/tournaments/<event_id>/bracket/generate', methods=['POST'])
@require_role('owner')
def bracket_generate(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        
        # Get participants
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
        players = [r['player_id'] for r in (reg_resp.data or [])]
        
        if len(players) < 2:
            flash("Not enough players to generate a bracket.", "warning")
            return redirect(url_for('owner.tournament_manage', event_id=event_id))
            
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
        current_app.logger.error(f"Error generating bracket for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.tournament_manage', event_id=event_id))

def _advance_bracket(db, event_id):
    """Check current round completion and auto-generate next round or declare champion."""
    try:
        all_m = db.table('tournament_matches').select(
            'id, round_number, status, winner_id'
        ).eq('event_id', event_id).order('round_number').execute()
        matches = all_m.data or []
        if not matches:
            return

        max_round = max(m['round_number'] for m in matches)
        round_matches = [m for m in matches if m['round_number'] == max_round]

        if any(m['status'] != 'completed' for m in round_matches):
            return  # Round not finished yet

        winners = [m['winner_id'] for m in round_matches if m['winner_id']]

        if len(winners) == 1:
            # 🏆 Champion decided
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

        # Pair winners → next round
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
                'winner_id': p1 if not p2 else None,
            })
            match_num += 1
        if next_matches:
            db.table('tournament_matches').insert(next_matches).execute()
            if len(next_matches) == 1 and next_matches[0]['status'] == 'completed':
                _advance_bracket(db, event_id)
    except Exception as e:
        current_app.logger.error(f"Owner bracket advancement error: {e}")


@owner_bp.route('/tournaments/<event_id>/matches/<match_id>/score', methods=['POST'])
@require_role('owner')
def match_score(event_id, match_id):
    owner_id = session.get('user_id')
    db = get_db()

    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    winner_id = request.form.get('winner_id') or None

    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()

        # Get match before updating to pass to ratings logic
        prev_match = None
        try:
            m_resp = db.table('tournament_matches').select('*').eq('id', match_id).single().execute()
            prev_match = m_resp.data
        except Exception:
            pass

        db.table('tournament_matches').update({
            'player1_score': p1_score,
            'player2_score': p2_score,
            'winner_id': winner_id,
            'status': 'completed',
            'played_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', match_id).eq('event_id', event_id).execute()

        # Calculate and update player ratings
        from app.ratings import update_match_ratings
        update_match_ratings(db, match_id, prev_match=prev_match)

        _advance_bracket(db, event_id)
        flash("Score recorded! Bracket and ratings updated.", "success")

    except Exception as e:
        current_app.logger.error(f"Error submitting match score: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.tournament_manage', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/matches/<match_id>/assign', methods=['POST'])
@require_role('owner')
def match_assign(event_id, match_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    court_id = request.form.get('court_id') or None
    court_name = request.form.get('court_name') or None
    referee_name = request.form.get('referee_name') or None
    
    if court_id and not court_name:
        try:
            c_resp = db.table('courts').select('name').eq('id', court_id).single().execute()
            if c_resp.data:
                court_name = c_resp.data['name']
        except Exception as ce:
            current_app.logger.error(f"Failed to resolve court name for owner: {ce}")

    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        
        db.table('tournament_matches').update({
            'court_id': court_id,
            'court_name': court_name,
            'referee_name': referee_name
        }).eq('id', match_id).eq('event_id', event_id).execute()
        
        flash("Match assignment updated.", "success")
    except Exception as e:
        current_app.logger.error(f"Error assigning match: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.tournament_manage', event_id=event_id))

# ── Create Event ───────────────────────────────────────────────────────────────
@owner_bp.route('/events/create', methods=['GET'])
@require_role('owner')
def create_event_page():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).eq('status', 'active').execute()
        facilities_list = fac_resp.data or []
    except Exception as e:
        current_app.logger.error(f"Error loading create event page for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return render_template('owner/create_event.html', facilities=facilities_list)


@owner_bp.route('/events/create', methods=['POST'])
@require_role('owner')
def create_event():
    owner_id      = session.get('user_id')
    facility_id   = request.form.get('facility_id')
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

    if not all([title, facility_id, event_date, start_time, end_time]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('owner.create_event_page'))

    db = get_db()
    
    # Handle Image Upload
    image_file = request.files.get('image')
    image_url = None
    if image_file and image_file.filename:
        try:
            filename = f"events/{owner_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
            file_bytes = image_file.read()
            db.storage.from_('community-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('community-images').get_public_url(filename)
        except Exception as e:
            current_app.logger.error(f"Image upload error: {e}")
            flash(f'Warning: Image could not be uploaded.', 'error')

    try:
        ev_resp = db.table('events').insert({
            'organizer_id': owner_id,
            'facility_id': facility_id,
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
            'status': 'registration_open',
        }).execute()

        if ev_resp.data and court_ids:
            event_id = ev_resp.data[0]['id']
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()

        flash(f'Event "{title}" created successfully!', 'success')
    except Exception as e:
        current_app.logger.error(f"Error creating event: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.events'))

@owner_bp.route('/events/<event_id>/edit', methods=['GET', 'POST'])
@require_role('owner')
def edit_event(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized or event not found.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('*').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        event = ev_resp.data
        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('owner.events'))
            
        if request.method == 'GET':
            fac_full_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).eq('status', 'active').execute()
            facilities_list = fac_full_resp.data or []
            return render_template('owner/edit_event.html', event=event, facilities=facilities_list)
            
        # POST logic
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
            
        if not all([title, facility_id, event_date, start_time, end_time]):
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('owner.edit_event', event_id=event_id))
            
        update_data = {
            'facility_id': facility_id,
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
        
        # Handle Image Upload
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            try:
                filename = f"events/{owner_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
                file_bytes = image_file.read()
                db.storage.from_('community-images').upload(
                    file=file_bytes,
                    path=filename,
                    file_options={"content-type": image_file.content_type}
                )
                update_data['image_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                current_app.logger.error(f"Image edit upload error: {e}")
                flash(f'Warning: Image could not be uploaded.', 'warning')
                
        db.table('events').update(update_data).eq('id', event_id).execute()
        
        # Also update courts if needed
        court_ids = request.form.getlist('court_ids')
        if court_ids:
            # delete existing courts and re-insert
            db.table('event_courts').delete().eq('event_id', event_id).execute()
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()
            
        flash('Event updated successfully!', 'success')
        return redirect(url_for('owner.event_participants', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error editing event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('owner.events'))

@owner_bp.route('/events/<event_id>/delete', methods=['POST'])
@require_role('owner')
def delete_event(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        # Check if event exists and belongs to owner
        ev_resp = db.table('events').select('title').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        title = ev_resp.data['title']
        
        # Notify registered players before deleting (batch insert)
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).execute()
        if reg_resp.data:
            notifs = [
                {
                    'user_id': r['player_id'],
                    'title': f'Event Cancelled: {title}',
                    'message': f'The event "{title}" you registered for has been cancelled and removed.',
                    'type': 'system'
                } for r in reg_resp.data
            ]
            db.table('notifications').insert(notifs).execute()
            
        # Delete event (registrations deleted automatically due to cascade)
        db.table('events').delete().eq('id', event_id).execute()
        flash(f'Event "{title}" deleted successfully.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error deleting event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.events'))


# ── API: Courts by Facility (for JS fetch in create_event) ────────────────────
@owner_bp.route('/api/courts_by_facility/<facility_id>')
@require_role('owner')
def api_courts_by_facility(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('courts').select('id, name, type, hourly_rate').eq('facility_id', facility_id).eq('owner_id', owner_id).eq('status', 'active').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Event Status Lifecycle ────────────────────────────────────────────────────
@owner_bp.route('/events/<event_id>/status', methods=['POST'])
@require_role('owner')
def change_event_status(event_id):
    owner_id = session.get('user_id')
    new_status = request.form.get('status', '').strip()
    allowed = ['upcoming', 'registration_open', 'full', 'in_progress', 'completed', 'cancelled']
    if new_status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for('owner.events'))

    db = get_db()
    try:
        ev_resp = db.table('events').select('id, title, organizer_id').eq('id', event_id).single().execute()
        ev = ev_resp.data
        if not ev or ev['organizer_id'] != owner_id:
            flash("Access denied.", "error")
            return redirect(url_for('owner.events'))

        db.table('events').update({'status': new_status}).eq('id', event_id).execute()
        flash(f"Event status changed to '{new_status.replace('_', ' ').title()}'.", "success")

        # Optimized batch insert for cancellations
        if new_status == 'cancelled':
            reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
            notifs = [
                {
                    'user_id': reg['player_id'],
                    'title': f'Event Cancelled: {ev["title"]}',
                    'message': f'"{ev["title"]}" has been cancelled by the organizer.',
                    'type': 'warning'
                } for reg in (reg_resp.data or [])
            ]
            if notifs:
                db.table('notifications').insert(notifs).execute()
    except Exception as e:
        current_app.logger.error(f"Error changing status for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.events'))
