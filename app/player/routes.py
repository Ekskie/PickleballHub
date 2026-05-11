from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from app import supabase_admin, supabase

player_bp = Blueprint('player', __name__, url_prefix='/player')

def get_db():
    return supabase_admin or supabase


@player_bp.route('/dashboard')
@require_role('player')
def dashboard():
    player_id = session.get('user_id')
    db = get_db()
    next_reservation = None
    available_courts = []
    upcoming_events = []
    recent_activities = []
    
    try:
        # Fetch next confirmed reservation
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, status, courts(name), facilities(name, location)'
        ).eq('player_id', player_id).in_('status', ['confirmed']).order('date').order('start_time').limit(1).execute()
        if res_resp.data:
            next_reservation = res_resp.data[0]

        # Fetch some available courts (mock query)
        court_resp = db.table('courts').select('id, name, type, hourly_rate, status').eq('status', 'active').limit(4).execute()
        available_courts = court_resp.data or []

        # Fetch upcoming events
        ev_resp = db.table('events').select('id, title, event_date').in_('status', ['upcoming', 'registration_open']).order('event_date').limit(3).execute()
        upcoming_events = ev_resp.data or []

        # Fetch recent activities (notifications)
        act_resp = db.table('notifications').select('id, title, created_at').eq('user_id', player_id).order('created_at', desc=True).limit(4).execute()
        recent_activities = act_resp.data or []

    except Exception as e:
        flash(f"Error loading dashboard data: {e}", "error")

    return render_template(
        'player/dashboard.html',
        next_reservation=next_reservation,
        available_courts=available_courts,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities
    )


@player_bp.route('/profile', methods=['GET', 'POST'])
@require_role('player')
def profile():
    player_id = session.get('user_id')
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
            }).eq('id', player_id).execute()
            
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['phone'] = phone
            
            flash("Profile updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('player.profile'))

    stats = {'courts': 0, 'events': 0, 'tournaments': 0}
    try:
        r_resp = db.table('court_reservations').select('id', count='exact').eq('player_id', player_id).execute()
        stats['courts'] = r_resp.count or 0
        
        e_resp = db.table('event_registrations').select('id', count='exact').eq('player_id', player_id).execute()
        stats['events'] = e_resp.count or 0
    except Exception:
        pass
        
    return render_template('player/profile.html', stats=stats)


@player_bp.route('/reservation')
@require_role('player')
def reservation():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, open_time, close_time, slot_duration_minutes, kyc_status'
        ).eq('status', 'active').order('name').execute()
        facilities = resp.data or []
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
    return render_template('player/court_reservation.html', facilities=facilities)


@player_bp.route('/reservation/api/courts')
@require_role('player')
def api_reservation_courts():
    facility_id = request.args.get('facility_id')
    if not facility_id:
        return jsonify([])
    db = get_db()
    try:
        resp = db.table('courts').select(
            'id, name, type, hourly_rate, status'
        ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/api/slots')
@require_role('player')
def api_reservation_slots():
    """Return booked start_time values for a court on a given date."""
    court_id = request.args.get('court_id')
    date     = request.args.get('date')
    if not court_id or not date:
        return jsonify([])
    db = get_db()
    try:
        resp = db.table('court_reservations').select(
            'start_time, end_time'
        ).eq('court_id', court_id).eq('date', date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/book', methods=['POST'])
@require_role('player')
def book_reservation():
    player_id   = session.get('user_id')
    court_id    = request.form.get('court_id')
    facility_id = request.form.get('facility_id')
    date        = request.form.get('date')
    start_time  = request.form.get('start_time')
    end_time    = request.form.get('end_time')
    total_hours = request.form.get('total_hours', 1)
    hourly_rate = request.form.get('hourly_rate', 0)
    total_amount = request.form.get('total_amount', 0)
    party_size  = request.form.get('party_size', 1)

    if not all([court_id, facility_id, date, start_time, end_time]):
        flash('Missing reservation details. Please try again.', 'error')
        return redirect(url_for('player.reservation'))

    db = get_db()
    try:
        resp = db.table('court_reservations').insert({
            'player_id':    player_id,
            'court_id':     court_id,
            'facility_id':  facility_id,
            'date':         date,
            'start_time':   start_time,
            'end_time':     end_time,
            'total_hours':  float(total_hours),
            'hourly_rate':  float(hourly_rate),
            'total_amount': float(total_amount),
            'party_size':   int(party_size),
            'status':       'pending_payment',
        }).execute()

        if resp.data:
            reservation_id = resp.data[0]['id']
            flash('Reservation created! Complete payment to confirm.', 'success')
            return redirect(url_for('player.payment', reservation_id=reservation_id))
    except Exception as e:
        flash(f'Error creating reservation: {e}', 'error')

    return redirect(url_for('player.reservation'))


@player_bp.route('/my-reservations')
@require_role('player')
def my_reservations():
    player_id = session.get('user_id')
    db = get_db()
    reservations = []
    try:
        resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
            'status, gcash_ref, created_at, '
            'courts(name, type), facilities(name, location)'
        ).eq('player_id', player_id).order('created_at', desc=True).execute()
        raw_reservations = resp.data or []
        
        now = datetime.now(PH_TZ)
        for r in raw_reservations:
            r['can_cancel'] = False
            if r['status'] in ['pending_payment', 'confirmed']:
                try:
                    start_time_str = f"{r['date']} {r['start_time']}"
                    end_time_str = f"{r['date']} {r['end_time']}"
                    
                    try:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                    except ValueError:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                        
                    if now >= end_dt:
                        db.table('court_reservations').update({'status': 'completed'}).eq('id', r['id']).execute()
                        r['status'] = 'completed'
                    elif now < start_dt:
                        r['can_cancel'] = True
                        
                except Exception as e:
                    print("Error processing reservation dates:", e)
                    r['can_cancel'] = True
            
            reservations.append(r)
            
    except Exception as e:
        flash(f'Error loading reservations: {e}', 'error')
    return render_template('player/my_reservations.html', reservations=reservations)


@player_bp.route('/reservation/cancel/<reservation_id>', methods=['POST'])
@require_role('player')
def cancel_reservation(reservation_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('court_reservations').update({'status': 'cancelled'}).eq(
            'id', reservation_id).eq('player_id', player_id).in_(
            'status', ['pending_payment', 'confirmed']).execute()
            
        if resp.data:
            db.table('court_queues').update({'status': 'cancelled'}).eq('reservation_id', reservation_id).execute()
            flash('Reservation cancelled.', 'success')
        else:
            flash('Could not cancel reservation. It may have already started.', 'error')
    except Exception as e:
        flash(f'Error cancelling: {e}', 'error')
    return redirect(url_for('player.my_reservations'))


@player_bp.route('/reservation/payment/<reservation_id>', methods=['GET'])
@require_role('player')
def payment(reservation_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, status, '
            'courts(name, type), facilities(name, location)'
        ).eq('id', reservation_id).eq('player_id', player_id).single().execute()
        reservation = resp.data
        if not reservation:
            flash('Reservation not found.', 'error')
            return redirect(url_for('player.my_reservations'))
        if reservation['status'] == 'confirmed':
            flash('This reservation is already paid.', 'info')
            return redirect(url_for('player.my_reservations'))
    except Exception as e:
        flash(f'Error: {e}', 'error')
        return redirect(url_for('player.my_reservations'))
    return render_template('player/payment.html', reservation=reservation)


@player_bp.route('/reservation/payment/<reservation_id>', methods=['POST'])
@require_role('player')
def confirm_payment(reservation_id):
    player_id  = session.get('user_id')
    gcash_ref  = request.form.get('gcash_ref', '').strip()
    if not gcash_ref:
        flash('Please enter your GCash reference number.', 'error')
        return redirect(url_for('player.payment', reservation_id=reservation_id))
    db = get_db()
    try:
        # Get reservation details for queue insertion
        res_resp = db.table('court_reservations').select('facility_id, court_id').eq('id', reservation_id).single().execute()
        res_data = res_resp.data

        db.table('court_reservations').update({
            'status': 'confirmed',
            'gcash_ref': gcash_ref,
        }).eq('id', reservation_id).eq('player_id', player_id).eq(
            'status', 'pending_payment').execute()

        if res_data:
            # Insert into court_queues
            db.table('court_queues').insert({
                'player_id': player_id,
                'facility_id': res_data['facility_id'],
                'court_id': res_data['court_id'],
                'reservation_id': reservation_id,
                'status': 'waiting',
                'estimated_wait_mins': 0
            }).execute()

        flash('Payment confirmed! Your court is booked and you are added to the queue.', 'success')
    except Exception as e:
        flash(f'Payment error: {e}', 'error')
    return redirect(url_for('player.my_reservations'))

def get_processed_queues(db, player_id=None):
    """Fetch queues for today, process wait times, and auto-complete games 15 mins past end time."""
    try:
        resp = db.table('court_queues').select(
            'id, status, estimated_wait_mins, joined_at, player_id, courts(name), profiles(first_name, last_name), court_reservations!inner(date, start_time, end_time)'
        ).in_('status', ['waiting', 'next', 'playing']).order('joined_at').execute()
        raw_queues = resp.data or []
    except Exception as e:
        print("Error fetching queues:", e)
        return [], None
        
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
            # Handle cases where time might not have seconds
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)

        # Auto-complete if they are 'playing' and 15 mins past end time
        if q['status'] == 'playing' and now > (end_dt + timedelta(minutes=15)):
            try:
                db.table('court_queues').update({'status': 'completed'}).eq('id', q['id']).execute()
            except Exception:
                pass
            continue # Skip rendering this one as it's completed
            
        # Calculate dynamic wait time or time remaining
        if q['status'] in ['waiting', 'next']:
            wait_mins = int((start_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, wait_mins)
            q['time_type'] = 'Wait'
            # Update the absolute time for the JS countdown
            q['target_time'] = start_dt.isoformat()
        elif q['status'] == 'playing':
            rem_mins = int((end_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, rem_mins)
            q['time_type'] = 'Remaining'
            q['target_time'] = end_dt.isoformat()
            
        queues.append(q)

    # Sort queues: Playing first, then Next, then Waiting
    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), x.get('court_reservations', {}).get('start_time', '')))

    # Assign positions (only for waiting/next)
    pos = 1
    for q in queues:
        if q['status'] != 'playing':
            q['position'] = pos
            pos += 1
        else:
            q['position'] = '-'
            
        if q['player_id'] == player_id:
            my_queue = q
            
    return queues, my_queue


@player_bp.route('/queue')
@require_role('player')
def queue():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue = get_processed_queues(db, player_id)
    return render_template('player/queue_monitoring.html', queues=queues, my_queue=my_queue)


@player_bp.route('/queue/partial')
@require_role('player')
def queue_partial():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue = get_processed_queues(db, player_id)
    return render_template('player/partials/queue_content.html', queues=queues, my_queue=my_queue)


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
        for ev in events_list:
            reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', ev['id']).eq('status', 'registered').execute()
            ev['registered_count'] = reg_resp.count if reg_resp.count is not None else 0

        # Fetch this player's registrations
        if player_id:
            my_resp = db.table('event_registrations').select('event_id').eq('player_id', player_id).eq('status', 'registered').execute()
            registered_ids = {r['event_id'] for r in (my_resp.data or [])}
            joined_count = len(registered_ids)

    except Exception as e:
        flash(f'Error loading events: {e}', 'error')

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
        flash(f'Error registering: {e}', 'error')

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
            
        try:
            # Check capacity again before confirming payment
            ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
            ev = ev_resp.data
            
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            count = reg_count_resp.count or 0
            
            if count >= ev['max_players']:
                # Full! Put them on waitlist
                db.table('event_registrations').update({
                    'status': 'waitlisted'
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('We received your payment, but the event just filled up! You are now on the waitlist and will be contacted.', 'warning')
            else:
                # Secure their spot
                db.table('event_registrations').update({
                    'status': 'registered'
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('Payment confirmed! You are now officially registered.', 'success')
                
        except Exception as e:
            flash(f'Payment error: {e}', 'error')
            
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
        flash(f'Error: {e}', 'error')
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
    except Exception as e:
        flash(f'Error unregistering: {e}', 'error')
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
        flash(f'Error: {e}', 'error')
        return redirect(url_for('player.events'))

    if not ev:
        flash('Event not found.', 'error')
        return redirect(url_for('player.events'))

    return render_template('player/event_detail.html', ev=ev, is_registered=is_registered, reg_count=reg_count, player_status=player_status)


@player_bp.route('/community')
@require_role('player')
def community():
    return render_template('player/community.html')


@player_bp.route('/messages')
# @require_role('player')
def messages():
    return render_template('player/messages.html')


@player_bp.route('/notifications')
@require_role('player')
def notifications():
    player_id = session.get('user_id')
    db = get_db()
    notifs = []
    
    try:
        resp = db.table('notifications').select('*').eq('user_id', player_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
        
    return render_template('player/notifications.html', notifications=notifs)

@player_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('player')
def mark_notifications_read():
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', player_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@player_bp.route('/tutorials')
@require_role('player')
def tutorials():
    return render_template('player/tutorials.html')
