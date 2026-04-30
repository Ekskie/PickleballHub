from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase

player_bp = Blueprint('player', __name__, url_prefix='/player')

def get_db():
    return supabase_admin or supabase


@player_bp.route('/dashboard')
@require_role('player')
def dashboard():
    return render_template('player/dashboard.html')


@player_bp.route('/profile')
@require_role('player')
def profile():
    return render_template('player/profile.html')


@player_bp.route('/reservation')
@require_role('player')
def reservation():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, open_time, close_time, slot_duration_minutes'
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
        reservations = resp.data or []
    except Exception as e:
        flash(f'Error loading reservations: {e}', 'error')
    return render_template('player/my_reservations.html', reservations=reservations)


@player_bp.route('/reservation/cancel/<reservation_id>', methods=['POST'])
@require_role('player')
def cancel_reservation(reservation_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('court_reservations').update({'status': 'cancelled'}).eq(
            'id', reservation_id).eq('player_id', player_id).in_(
            'status', ['pending_payment', 'confirmed']).execute()
        flash('Reservation cancelled.', 'success')
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
        db.table('court_reservations').update({
            'status': 'confirmed',
            'gcash_ref': gcash_ref,
        }).eq('id', reservation_id).eq('player_id', player_id).eq(
            'status', 'pending_payment').execute()
        flash('Payment confirmed! Your court is booked.', 'success')
    except Exception as e:
        flash(f'Payment error: {e}', 'error')
    return redirect(url_for('player.my_reservations'))

@player_bp.route('/queue')
@require_role('player')
def queue():
    return render_template('player/queue_monitoring.html')


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
            'id, title, type, event_date, start_time, end_time, max_players, entry_fee, location_label, status, '
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
        # Check event capacity
        ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
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
            status = 'waitlisted' if count >= ev['max_players'] else 'registered'
            if count >= ev['max_players']:
                flash(f'Event is full! You have been waitlisted for "{ev["title"]}".', 'warning')
                # Mark event as full
                db.table('events').update({'status': 'full'}).eq('id', event_id).execute()

        db.table('event_registrations').upsert({
            'event_id': event_id,
            'player_id': player_id,
            'status': status,
        }, on_conflict='event_id,player_id').execute()

        if status == 'registered':
            flash(f'Successfully registered for "{ev["title"]}"!', 'success')

    except Exception as e:
        flash(f'Error registering: {e}', 'error')

    return redirect(url_for('player.events'))


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
            'id, title, type, description, event_date, start_time, end_time, max_players, entry_fee, '
            'location_label, status, created_at, facilities(name, location), profiles!organizer_id(first_name, last_name)'
        ).eq('id', event_id).single().execute()
        ev = ev_resp.data

        reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
        reg_count = reg_count_resp.count or 0

        if player_id:
            my_resp = db.table('event_registrations').select('status').eq('event_id', event_id).eq('player_id', player_id).execute()
            is_registered = bool(my_resp.data and my_resp.data[0]['status'] == 'registered')

    except Exception as e:
        flash(f'Error: {e}', 'error')
        return redirect(url_for('player.events'))

    if not ev:
        flash('Event not found.', 'error')
        return redirect(url_for('player.events'))

    return render_template('player/event_detail.html', ev=ev, is_registered=is_registered, reg_count=reg_count)


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
    return render_template('player/notifications.html')


@player_bp.route('/tutorials')
@require_role('player')
def tutorials():
    return render_template('player/tutorials.html')
