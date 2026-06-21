from flask import render_template, request, redirect, url_for, session, flash
from app.decorators import require_role
from app.db import get_db
from app.player import player_bp

@player_bp.route('/events')
@require_role('player')
def events():
    player_id = session.get('user_id')
    db = get_db()
    events_list = []
    registered_ids = set()
    joined_count = 0
    try:
        # Fetch upcoming + open events with facility info
        ev_resp = db.table('events').select(
            'id, title, type, format, prize_pool, image_url, event_date, start_time, end_time, max_players, entry_fee, location_label, status, '
            'facilities(name, location)'
        ).in_('status', ['registration_open', 'upcoming', 'full']).order('event_date', desc=False).execute()
        events_list = ev_resp.data or []

        # Attach registration count to each event
        if events_list:
            event_ids = [ev['id'] for ev in events_list]
            reg_resp = db.table('event_registrations').select('event_id').in_('event_id', event_ids).eq('status', 'registered').execute()
            reg_counts = {}
            for r in (reg_resp.data or []):
                reg_counts[r['event_id']] = reg_counts.get(r['event_id'], 0) + 1
            for ev in events_list:
                ev['registered_count'] = reg_counts.get(ev['id'], 0)

        # Fetch this player's registrations
        if player_id:
            my_resp = db.table('event_registrations').select('event_id').eq('player_id', player_id).eq('status', 'registered').execute()
            registered_ids = {r['event_id'] for r in (my_resp.data or [])}
            joined_count = len(registered_ids)

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return render_template(
        'player/events.html',
        events=events_list,
        registered_ids=registered_ids,
        joined_count=joined_count
    )


@player_bp.route('/events/<event_id>/register', methods=['POST'])
@require_role('player')
def register_event(event_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        # Check event capacity and fee
        ev_resp = db.table('events').select('max_players, title, status, entry_fee').eq('id', event_id).single().execute()
        if not ev_resp.data:
            flash('Event not found.', 'error')
            return redirect(url_for('player.events'))

        ev = ev_resp.data
        if ev['status'] == 'full':
            flash('This event is full. You have been added to the waitlist.', 'warning')
            status = 'waitlisted'
        else:
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            count = reg_count_resp.count or 0
            
            if count >= ev['max_players']:
                flash(f'Event is full! You have been waitlisted for "{ev["title"]}".', 'warning')
                # Mark event as full
                db.table('events').update({'status': 'full'}).eq('id', event_id).execute()
                status = 'waitlisted'
            else:
                # Room available! Check if it's a paid event.
                if ev.get('entry_fee') and ev['entry_fee'] > 0:
                    status = 'pending_payment'
                else:
                    status = 'registered'

        db.table('event_registrations').upsert({
            'event_id': event_id,
            'player_id': player_id,
            'status': status,
        }, on_conflict='event_id,player_id').execute()

        if status == 'pending_payment':
            flash(f'Please complete your payment to secure your spot for "{ev["title"]}".', 'info')
            return redirect(url_for('player.tournament_payment', event_id=event_id))
        elif status == 'registered':
            flash(f'Successfully registered for "{ev["title"]}"!', 'success')

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('player.events'))


@player_bp.route('/events/<event_id>/payment', methods=['GET', 'POST'])
@require_role('player')
def tournament_payment(event_id):
    player_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'POST':
        gcash_ref = request.form.get('gcash_ref', '').strip()
        if not gcash_ref:
            flash('Please enter your GCash reference number.', 'error')
            return redirect(url_for('player.tournament_payment', event_id=event_id))
            
        import re
        if not re.match(r'^\d{13}$', gcash_ref):
            flash('Invalid GCash reference number format. Must be a 13-digit number.', 'error')
            return redirect(url_for('player.tournament_payment', event_id=event_id))

        try:
            # Check duplicate reference number
            dup_resp = db.table('event_registrations').select('id').eq('gcash_ref', gcash_ref).execute()
            if dup_resp.data:
                flash('This GCash reference number has already been used for another event registration.', 'error')
                return redirect(url_for('player.tournament_payment', event_id=event_id))

            # Check capacity again before confirming payment
            ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
            ev = ev_resp.data
            
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            count = reg_count_resp.count or 0
            
            if count >= ev['max_players']:
                # Full! Put them on waitlist
                db.table('event_registrations').update({
                    'status': 'waitlisted',
                    'gcash_ref': gcash_ref
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('We received your payment, but the event just filled up! You are now on the waitlist and will be contacted.', 'warning')
            else:
                # Secure their spot
                db.table('event_registrations').update({
                    'status': 'registered',
                    'gcash_ref': gcash_ref
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('Payment confirmed! You are now officially registered.', 'success')
                
        except Exception as e:
            flash('An error occurred. Please try again.', 'error')
            
        return redirect(url_for('player.event_detail', event_id=event_id))
        
    # GET method
    try:
        ev_resp = db.table('events').select('title, entry_fee').eq('id', event_id).single().execute()
        event = ev_resp.data
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('player.events'))
            
        # Check their current status
        my_reg = db.table('event_registrations').select('status').eq('event_id', event_id).eq('player_id', player_id).single().execute()
        if not my_reg.data or my_reg.data['status'] != 'pending_payment':
            flash('No pending payment found for this event.', 'info')
            return redirect(url_for('player.event_detail', event_id=event_id))
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.events'))
        
    return render_template('player/tournament_payment.html', event=event, event_id=event_id)


@player_bp.route('/events/<event_id>/unregister', methods=['POST'])
@require_role('player')
def unregister_event(event_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('event_registrations').update({'status': 'cancelled'}).eq('event_id', event_id).eq('player_id', player_id).execute()
        flash('You have unregistered from the event.', 'success')

        # ── Waitlist Promotion ──────────────────────────────────────────────────
        try:
            ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
            ev = ev_resp.data
            if not ev:
                return redirect(url_for('player.events'))

            # Count remaining registered players
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            reg_count = reg_count_resp.count or 0

            # If there's now a free spot and the event was marked full, open it
            if ev['status'] == 'full' and reg_count < ev['max_players']:
                db.table('events').update({'status': 'registration_open'}).eq('id', event_id).execute()

            # Promote the oldest waitlisted player
            if reg_count < ev['max_players']:
                waitlist_resp = db.table('event_registrations').select('id, player_id').eq('event_id', event_id).eq('status', 'waitlisted').order('created_at').limit(1).execute()
                if waitlist_resp.data:
                    promoted = waitlist_resp.data[0]
                    db.table('event_registrations').update({'status': 'registered'}).eq('id', promoted['id']).execute()
                    # Notify the promoted player
                    db.table('notifications').insert({
                        'user_id': promoted['player_id'],
                        'title': f'🎉 Spot Available: {ev["title"]}',
                        'message': f'A spot opened up for "{ev["title"]}" and you have been automatically registered. Check your events!',
                        'type': 'success'
                    }).execute()
        except Exception as promotion_err:
            print(f"Waitlist promotion error: {promotion_err}")
        # ───────────────────────────────────────────────────────────────────────

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.events'))


@player_bp.route('/events/<event_id>')
@require_role('player')
def event_detail(event_id):
    player_id = session.get('user_id')
    db = get_db()
    ev = None
    is_registered = False
    reg_count = 0
    try:
        ev_resp = db.table('events').select(
            'id, title, type, format, prize_pool, image_url, description, event_date, start_time, end_time, max_players, entry_fee, '
            'location_label, status, created_at, facilities(name, location), profiles!organizer_id(first_name, last_name)'
        ).eq('id', event_id).single().execute()
        ev = ev_resp.data

        reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
        reg_count = reg_count_resp.count or 0

        player_status = None
        if player_id:
            my_resp = db.table('event_registrations').select('status').eq('event_id', event_id).eq('player_id', player_id).execute()
            if my_resp.data:
                player_status = my_resp.data[0]['status']
                is_registered = (player_status == 'registered')

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.events'))

    if not ev:
        flash('Event not found.', 'error')
        return redirect(url_for('player.events'))

    return render_template('player/event_detail.html', ev=ev, is_registered=is_registered, reg_count=reg_count, player_status=player_status)


@player_bp.route('/tournaments')
@require_role('player')
def my_tournaments():
    player_id = session.get('user_id')
    db = get_db()
    tournaments = []
    try:
        reg_resp = db.table('event_registrations').select(
            'status, events!inner(id, title, event_date, status, type, '
            'facilities(name, location))'
        ).eq('player_id', player_id).eq('status', 'registered').execute()
        for r in (reg_resp.data or []):
            ev = r.get('events')
            if ev and ev.get('type') == 'tournament':
                ev['my_registration_status'] = r['status']
                tournaments.append(ev)
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('player/my_tournaments.html', tournaments=tournaments)


@player_bp.route('/tournaments/<event_id>')
@require_role('player')
def tournament_bracket(event_id):
    player_id = session.get('user_id')
    db = get_db()
    event = None
    matches = []
    max_round = 0
    champion = None

    try:
        ev_resp = db.table('events').select(
            'id, title, event_date, status, max_players, '
            'facilities(name, location)'
        ).eq('id', event_id).single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('player.my_tournaments'))

        match_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, '
            'player1_score, player2_score, status, court_id, court_name, referee_name, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = match_resp.data or []

        if matches:
            max_round = max(m['round_number'] for m in matches)
            if event.get('status') == 'completed':
                final_ms = [m for m in matches if m['round_number'] == max_round and m['status'] == 'completed']
                if final_ms and final_ms[0].get('winner'):
                    champion = final_ms[0]['winner']

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.my_tournaments'))

    return render_template('player/tournament_bracket.html',
                           event=event,
                           matches=matches,
                           max_round=max_round,
                           champion=champion,
                           player_id=player_id)
