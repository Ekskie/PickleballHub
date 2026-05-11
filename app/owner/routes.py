from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.decorators import require_role
from app import supabase_admin, supabase

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

def get_db():
    return supabase_admin or supabase

# ── Dashboard ──────────────────────────────────────────────────────────────────
@owner_bp.route('/dashboard')
@require_role('owner')
def dashboard():
    owner_id = session.get('user_id')
    db = get_db()
    
    # Defaults
    total_earnings = 0
    total_bookings = 0
    active_staff = 0
    recent_bookings = []
    
    try:
        # Get facilities owned by this user
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        
        if fac_ids:
            # 1. Today's Earnings & Total Bookings
            from datetime import date
            today_str = date.today().isoformat()
            
            # Fetch reservations for the owner's facilities
            res_resp = db.table('court_reservations').select(
                'id, total_amount, date, start_time, end_time, status, profiles(first_name, last_name), courts(name, type)'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            reservations = res_resp.data or []
            
            total_bookings = len(reservations)
            
            # Calculate today's earnings (only paid/completed)
            today_earnings = sum(
                r['total_amount'] for r in reservations 
                if r['date'] == today_str and r['status'] in ['confirmed', 'completed']
            )
            total_earnings = today_earnings
            
            # Recent Bookings (top 5)
            recent_bookings = reservations[:5]
            
            # 2. Active Staff Count
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            active_staff = staff_resp.count if staff_resp.count is not None else 0

    except Exception as e:
        print(f"Error loading owner dashboard: {e}")
        
    return render_template(
        'owner/dashboard.html',
        total_earnings=total_earnings,
        total_bookings=total_bookings,
        active_staff=active_staff,
        recent_bookings=recent_bookings
    )

# ── Facilities ─────────────────────────────────────────────────────────────────
@owner_bp.route('/facilities')
@require_role('owner')
def facilities():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, status, open_time, close_time, created_at, kyc_status, latitude, longitude, image_url'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        facilities_data = resp.data or []

        # For each facility, count its courts
        for f in facilities_data:
            court_resp = db.table('courts').select('id', count='exact').eq('facility_id', f['id']).execute()
            f['court_count'] = court_resp.count if court_resp.count is not None else 0
            facilities_list.append(f)
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')

    return render_template('owner/facilities.html', facilities=facilities_list)


@owner_bp.route('/facilities/add', methods=['POST'])
@require_role('owner')
def add_facility():
    owner_id  = session.get('user_id')
    name      = request.form.get('name', '').strip()
    location  = request.form.get('location', '').strip()
    desc      = request.form.get('description', '').strip()
    status    = request.form.get('status', 'active')
    open_time = request.form.get('open_time', '08:00')
    close_time = request.form.get('close_time', '21:00')
    latitude  = request.form.get('latitude')
    longitude = request.form.get('longitude')
    image_url = request.form.get('image_url', '').strip()

    if not name:
        flash('Facility name is required.', 'error')
        return redirect(url_for('owner.facilities'))

    db = get_db()
    try:
        db.table('facilities').insert({
            'owner_id': owner_id,
            'name': name,
            'location': location,
            'description': desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
            'image_url': image_url if image_url else None,
        }).execute()
        flash(f'Facility "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding facility: {e}', 'error')

    return redirect(url_for('owner.facilities'))


@owner_bp.route('/facilities/<facility_id>/edit', methods=['POST'])
@require_role('owner')
def edit_facility(facility_id):
    owner_id   = session.get('user_id')
    name       = request.form.get('name', '').strip()
    location   = request.form.get('location', '').strip()
    desc       = request.form.get('description', '').strip()
    status     = request.form.get('status', 'active')
    open_time  = request.form.get('open_time', '08:00')
    close_time = request.form.get('close_time', '21:00')
    latitude   = request.form.get('latitude')
    longitude  = request.form.get('longitude')
    image_url  = request.form.get('image_url', '').strip()

    db = get_db()
    try:
        db.table('facilities').update({
            'name': name,
            'location': location,
            'description': desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
            'image_url': image_url if image_url else None,
        }).eq('id', facility_id).eq('owner_id', owner_id).execute()
        flash(f'Facility updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating facility: {e}', 'error')

    return redirect(url_for('owner.facilities'))


@owner_bp.route('/facilities/<facility_id>/delete', methods=['POST'])
@require_role('owner')
def delete_facility(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        db.table('facilities').delete().eq('id', facility_id).eq('owner_id', owner_id).execute()
        flash('Facility deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting facility: {e}', 'error')
    return redirect(url_for('owner.facilities'))

@owner_bp.route('/facilities/<facility_id>/kyc', methods=['POST'])
@require_role('owner')
def kyc_upload(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    # Check if facility belongs to owner
    fac_resp = db.table('facilities').select('id').eq('id', facility_id).eq('owner_id', owner_id).single().execute()
    if not fac_resp.data:
        flash("Facility not found or unauthorized.", "error")
        return redirect(url_for('owner.facilities'))
        
    doc_file = request.files.get('kyc_document')
    if not doc_file or not doc_file.filename:
        flash("Please select a document to upload.", "error")
        return redirect(url_for('owner.facilities'))
        
    try:
        import time
        ext = doc_file.filename.split('.')[-1]
        filename = f"{facility_id}_{int(time.time())}.{ext}"
        file_bytes = doc_file.read()
        
        # Upload to kyc-documents bucket
        db.storage.from_('kyc-documents').upload(
            file=file_bytes,
            path=filename,
            file_options={"content-type": doc_file.content_type}
        )
        
        doc_url = db.storage.from_('kyc-documents').get_public_url(filename)
        
        db.table('facilities').update({
            'kyc_status': 'pending_approval',
            'kyc_document_url': doc_url
        }).eq('id', facility_id).execute()
        
        flash("KYC document uploaded successfully. Status is now pending approval.", "success")
    except Exception as e:
        print(f"Upload error: {e}")
        flash(f"Error uploading document: {e}", "error")
        
    return redirect(url_for('owner.facilities'))



# ── Courts ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/courts')
@require_role('owner')
def courts():
    owner_id = session.get('user_id')
    db = get_db()
    courts_list = []
    facilities_list = []
    try:
        # Owner's facilities for the dropdown
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).eq('status', 'active').execute()
        facilities_list = fac_resp.data or []

        # Courts with facility name joined
        court_resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, facility_id, facilities(name)'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        courts_list = court_resp.data or []
    except Exception as e:
        flash(f'Error loading courts: {e}', 'error')

    return render_template('owner/courts.html', courts=courts_list, facilities=facilities_list)


@owner_bp.route('/courts/add', methods=['POST'])
@require_role('owner')
def add_court():
    owner_id    = session.get('user_id')
    facility_id = request.form.get('facility_id')
    name        = request.form.get('name', '').strip()
    court_type  = request.form.get('type', 'indoor')
    hourly_rate = request.form.get('hourly_rate', 0)
    status      = request.form.get('status', 'active')

    if not name or not facility_id:
        flash('Court name and facility are required.', 'error')
        return redirect(url_for('owner.courts'))

    db = get_db()
    try:
        db.table('courts').insert({
            'owner_id': owner_id,
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
        }).execute()
        flash(f'Court "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding court: {e}', 'error')

    return redirect(url_for('owner.courts'))


@owner_bp.route('/courts/<court_id>/edit', methods=['POST'])
@require_role('owner')
def edit_court(court_id):
    owner_id    = session.get('user_id')
    facility_id = request.form.get('facility_id')
    name        = request.form.get('name', '').strip()
    court_type  = request.form.get('type', 'indoor')
    hourly_rate = request.form.get('hourly_rate', 0)
    status      = request.form.get('status', 'active')

    db = get_db()
    try:
        db.table('courts').update({
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
        }).eq('id', court_id).eq('owner_id', owner_id).execute()
        flash('Court updated!', 'success')
    except Exception as e:
        flash(f'Error updating court: {e}', 'error')

    return redirect(url_for('owner.courts'))


@owner_bp.route('/courts/<court_id>/delete', methods=['POST'])
@require_role('owner')
def delete_court(court_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        db.table('courts').delete().eq('id', court_id).eq('owner_id', owner_id).execute()
        flash('Court deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting court: {e}', 'error')
    return redirect(url_for('owner.courts'))


# ── Queue Management ────────────────────────────────────────────────────────────
@owner_bp.route('/queue')
@require_role('owner')
def queue():
    owner_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        raw_facs = fac_resp.data or []
        # format like facility_staff response so the same template logic works
        assigned_facilities = [{'facility_id': f['id'], 'facilities': {'name': f['name']}} for f in raw_facs]
        fac_ids = [f['id'] for f in raw_facs]
        
        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            q_resp = db.table('court_queues').select(
                'id, facility_id, court_id, status, joined_at, estimated_wait_mins, profiles(first_name, last_name)'
            ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next']).order('joined_at', desc=False).execute()
            queues = q_resp.data or []
            
    except Exception as e:
        flash(f'Error loading queues: {e}', 'error')
        
    return render_template('owner/queue.html', facilities=assigned_facilities, courts=courts, queues=queues)

@owner_bp.route('/queue/update', methods=['POST'])
@require_role('owner')
def update_queue():
    queue_id = request.form.get('queue_id')
    new_status = request.form.get('status')
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'completed', 'cancelled']:
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            flash('Queue status updated!', 'success')
    except Exception as e:
        flash(f'Error updating queue: {e}', 'error')
        
    return redirect(url_for('owner.queue'))

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
                'id, title, type, event_date, start_time, end_time, max_players, status, location_label, '
                'facilities(name), profiles!organizer_id(first_name, last_name)'
            ).in_('facility_id', fac_ids).order('event_date', desc=False).execute()
            events_list = ev_resp.data or []

            # Attach registration count
            for ev in events_list:
                reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', ev['id']).eq('status', 'registered').execute()
                ev['registered_count'] = reg_resp.count if reg_resp.count is not None else 0
    except Exception as e:
        flash(f'Error loading events: {e}', 'error')

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
                # Fetch participants
                reg_resp = db.table('event_registrations').select(
                    'id, status, registered_at, player_id, profiles!player_id(first_name, last_name, phone)'
                ).eq('event_id', event_id).execute()
                participants = reg_resp.data or []
                
                # Fetch emails from auth.users
                for p in participants:
                    if p.get('player_id'):
                        try:
                            # Using supabase_admin to bypass RLS and fetch auth user details
                            from app import supabase_admin
                            user_data = supabase_admin.auth.admin.get_user_by_id(p['player_id'])
                            if p.get('profiles'):
                                p['profiles']['email'] = user_data.user.email
                        except Exception as e:
                            print(f"Failed to fetch auth user {p['player_id']}: {e}")
            else:
                flash("Event not found or unauthorized.", "error")
                return redirect(url_for('owner.events'))
                
    except Exception as e:
        flash(f'Error loading participants: {e}', 'error')
        
    return render_template('owner/event_participants.html', event=event_details, participants=participants)

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
        flash(f'Error loading facilities: {e}', 'error')
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
    
    # New fields
    event_format  = request.form.get('format', 'Doubles').strip()
    prize_pool    = request.form.get('prize_pool', 0)
    reg_type      = request.form.get('registration_type', 'paid')
    
    # If registration is free, set entry_fee to 0
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
            import time
            ext = image_file.filename.split('.')[-1]
            filename = f"events/{owner_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('community-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('community-images').get_public_url(filename)
        except Exception as e:
            print(f"Image upload error: {e}")
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
        flash(f'Error creating event: {e}', 'error')

    return redirect(url_for('owner.events'))

@owner_bp.route('/events/<event_id>/edit', methods=['GET', 'POST'])
@require_role('owner')
def edit_event(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    # Verify owner has access to this event
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
                import time
                ext = image_file.filename.split('.')[-1]
                filename = f"events/{owner_id}_{int(time.time())}.{ext}"
                file_bytes = image_file.read()
                db.storage.from_('community-images').upload(
                    file=file_bytes,
                    path=filename,
                    file_options={"content-type": image_file.content_type}
                )
                update_data['image_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                print(f"Image upload error: {e}")
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
        flash(f"Error updating event: {e}", "error")
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
        
        # Notify registered players before deleting
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).execute()
        if reg_resp.data:
            notifs = []
            for r in reg_resp.data:
                notifs.append({
                    'user_id': r['player_id'],
                    'title': f'Event Cancelled: {title}',
                    'message': f'The event "{title}" you registered for has been cancelled and removed.',
                    'type': 'system'
                })
            db.table('notifications').insert(notifs).execute()
            
        # Delete event (registrations deleted automatically due to cascade)
        db.table('events').delete().eq('id', event_id).execute()
        flash(f'Event "{title}" deleted successfully.', 'success')
        
    except Exception as e:
        flash(f'Error deleting event: {e}', 'error')
        
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


# ── Staff ───────────────────────────────────────────────────────────────────────
@owner_bp.route('/staff')
@require_role('owner')
def staff():
    owner_id = session.get('user_id')
    db = get_db()
    staff_list = []
    facilities_list = []
    
    try:
        # Get owner's facilities
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        facilities_list = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_list]
        
        if fac_ids:
            # Fetch staff assigned to these facilities
            staff_resp = db.table('facility_staff').select(
                'id, facility_id, facilities(name), profiles!staff_id(id, first_name, last_name, phone)'
            ).in_('facility_id', fac_ids).execute()
            staff_list = staff_resp.data or []
            
    except Exception as e:
        flash(f'Error loading staff: {e}', 'error')
        
    return render_template('owner/staff.html', staff=staff_list, facilities=facilities_list)

@owner_bp.route('/staff/add', methods=['POST'])
@require_role('owner')
def add_staff():
    owner_id = session.get('user_id')
    facility_id = request.form.get('facility_id')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    if not all([facility_id, first_name, email, password]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('owner.staff'))
        
    db = get_db()
    try:
        from app import supabase_admin
        if not supabase_admin:
            flash("Admin client not available.", "error")
            return redirect(url_for('owner.staff'))
            
        # 1. Create User in Supabase Auth
        new_user = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "facilitystaff"
            }
        })
        
        staff_id = new_user.user.id
        
        # 2. Add to profiles table
        supabase_admin.table('profiles').upsert({
            'id': staff_id,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'facilitystaff'
        }, on_conflict='id').execute()
        
        # 3. Assign to facility
        db.table('facility_staff').insert({
            'facility_id': facility_id,
            'staff_id': staff_id
        }).execute()
        
        flash(f'Staff account for {first_name} created and assigned!', 'success')
    except Exception as e:
        flash(f'Error creating staff: {e}', 'error')
        
    return redirect(url_for('owner.staff'))

@owner_bp.route('/staff/<fs_id>/delete', methods=['POST'])
@require_role('owner')
def remove_staff_assignment(fs_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        # We need to ensure the owner owns the facility this staff is assigned to.
        # Simple approach: verify ownership by facility_id
        fs_resp = db.table('facility_staff').select('facility_id, staff_id').eq('id', fs_id).single().execute()
        if fs_resp.data:
            fac_id = fs_resp.data['facility_id']
            fac_resp = db.table('facilities').select('owner_id').eq('id', fac_id).single().execute()
            if fac_resp.data and fac_resp.data['owner_id'] == owner_id:
                # Remove assignment (the user account will remain, but they have no access)
                db.table('facility_staff').delete().eq('id', fs_id).execute()
                flash('Staff assignment removed.', 'success')
            else:
                flash('Unauthorized to remove this staff.', 'error')
    except Exception as e:
        flash(f'Error removing staff: {e}', 'error')
    return redirect(url_for('owner.staff'))

# ── Profile ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/profile', methods=['GET', 'POST'])
@require_role('owner')
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
        return redirect(url_for('owner.profile'))
    return render_template('owner/profile.html')

# ── Notifications ───────────────────────────────────────────────────────────────
@owner_bp.route('/notifications')
@require_role('owner')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('owner/notifications.html', notifications=notifs)

@owner_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('owner')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Messages ────────────────────────────────────────────────────────────────────
@owner_bp.route('/messages')
@require_role('owner')
def messages():
    return render_template('owner/messages.html')

# ── Community ───────────────────────────────────────────────────────────────────
@owner_bp.route('/community')
@require_role('owner')
def community():
    return render_template('owner/community.html')
