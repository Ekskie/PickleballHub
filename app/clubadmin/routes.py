from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase

def get_db():
    return supabase_admin or supabase


clubadmin_bp = Blueprint('clubadmin', __name__, url_prefix='/clubadmin')

@clubadmin_bp.route('/dashboard')
@require_role('clubadmin')
def dashboard():
    return render_template('clubadmin/dashboard.html')

@clubadmin_bp.route('/members')
@require_role('clubadmin')
def members():
    return render_template('clubadmin/members.html')

@clubadmin_bp.route('/events')
@require_role('clubadmin')
def events():
    clubadmin_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        ev_resp = db.table('events').select(
            'id, title, type, event_date, start_time, end_time, max_players, status, location_label, facilities(name)'
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
                'id, status, registered_at, profiles!player_id(first_name, last_name, email, phone)'
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
    return render_template('clubadmin/tournaments.html')

@clubadmin_bp.route('/leaderboard')
@require_role('clubadmin')
def leaderboard():
    return render_template('clubadmin/leaderboard.html')

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
