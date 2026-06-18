from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

from app.db import get_db, get_admin_db


# ── Dashboard ──────────────────────────────────────────────────────────────────
@owner_bp.route('/dashboard')
@require_role('owner')
def dashboard():
    owner_id = session.get('user_id')
    db = get_db()

    total_earnings = 0       # all-time
    today_earnings = 0
    total_bookings = 0
    active_staff = 0
    recent_bookings = []
    revenue_chart = {'labels': [], 'data': []}
    facility_revenue = []

    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        facilities_data = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_data]

        if fac_ids:
            from datetime import date
            today_str = date.today().isoformat()

            # All confirmed/completed reservations
            res_resp = db.table('court_reservations').select(
                'id, total_amount, date, start_time, end_time, status, '
                'profiles(first_name, last_name), courts(name, type), facility_id'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            reservations = res_resp.data or []

            paid = [r for r in reservations if r['status'] in ['confirmed', 'completed']]
            total_bookings = len(reservations)
            total_earnings = sum((r.get('total_amount') or 0) for r in paid)
            today_earnings = sum((r.get('total_amount') or 0) for r in paid if r.get('date') == today_str)

            # Recent bookings (top 6)
            recent_bookings = reservations[:6]

            # 7-day daily revenue trend
            now = datetime.now(PH_TZ)
            labels, daily_data = [], []
            for i in range(6, -1, -1):
                day = now - timedelta(days=i)
                day_str = day.strftime('%Y-%m-%d')
                labels.append(day.strftime('%b %d'))
                day_rev = sum((r.get('total_amount') or 0) for r in paid if r.get('date') == day_str)
                daily_data.append(round(day_rev, 2))
            revenue_chart = {'labels': labels, 'data': daily_data}

            # Revenue per facility
            for f in facilities_data:
                frev = sum((r.get('total_amount') or 0) for r in paid if r.get('facility_id') == f['id'])
                fbookings = sum(1 for r in reservations if r.get('facility_id') == f['id'])
                facility_revenue.append({'name': f['name'], 'revenue': round(frev, 2), 'bookings': fbookings})

            # Staff count
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            active_staff = staff_resp.count or 0

    except Exception as e:
        print(f"Owner dashboard error: {e}")

    return render_template(
        'owner/dashboard.html',
        total_earnings=total_earnings,
        today_earnings=today_earnings,
        total_bookings=total_bookings,
        active_staff=active_staff,
        recent_bookings=recent_bookings,
        revenue_chart=revenue_chart,
        facility_revenue=facility_revenue,
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

    if not name:
        flash('Facility name is required.', 'error')
        return redirect(url_for('owner.facilities'))

    db = get_db()

    # Handle image upload
    image_url = None
    image_file = request.files.get('facility_image')
    if image_file and image_file.filename:
        try:
            import time
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"facility_{owner_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('facility-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('facility-images').get_public_url(filename)
        except Exception as e:
            print(f"Facility image upload error: {e}")
            flash('Warning: Image could not be uploaded.', 'warning')

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
            'image_url': image_url,
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

    db = get_db()

    update_data = {
        'name': name,
        'location': location,
        'description': desc,
        'status': status,
        'open_time': open_time,
        'close_time': close_time,
        'latitude': float(latitude) if latitude else None,
        'longitude': float(longitude) if longitude else None,
    }

    # Handle image upload
    image_file = request.files.get('facility_image')
    if image_file and image_file.filename:
        try:
            import time
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"facility_{facility_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('facility-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            update_data['image_url'] = db.storage.from_('facility-images').get_public_url(filename)
        except Exception as e:
            print(f"Facility image upload error: {e}")
            flash('Warning: Image could not be uploaded.', 'warning')

    try:
        db.table('facilities').update(update_data).eq('id', facility_id).eq('owner_id', owner_id).execute()
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
            'id, name, type, hourly_rate, status, facility_id, image_url, facilities(name)'
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

    # Handle court image upload
    image_url = None
    image_file = request.files.get('court_image')
    if image_file and image_file.filename:
        try:
            import time
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"court_{owner_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('court-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('court-images').get_public_url(filename)
        except Exception as e:
            print(f"Court image upload error: {e}")
            flash('Warning: Court image could not be uploaded.', 'warning')

    try:
        db.table('courts').insert({
            'owner_id': owner_id,
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
            'image_url': image_url,
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

    update_data = {
        'facility_id': facility_id,
        'name': name,
        'type': court_type,
        'hourly_rate': float(hourly_rate),
        'status': status,
    }

    # Handle court image upload
    image_file = request.files.get('court_image')
    if image_file and image_file.filename:
        try:
            import time
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"court_{court_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('court-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            update_data['image_url'] = db.storage.from_('court-images').get_public_url(filename)
        except Exception as e:
            print(f"Court image upload error: {e}")
            flash('Warning: Court image could not be uploaded.', 'warning')

    try:
        db.table('courts').update(update_data).eq('id', court_id).eq('owner_id', owner_id).execute()
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
    # Support both AJAX JSON and Form submissions
    if request.is_json:
        data = request.get_json() or {}
        queue_id = data.get('queue_id')
        new_status = data.get('status')
        is_ajax = True
    else:
        queue_id = request.form.get('queue_id')
        new_status = request.form.get('status')
        is_ajax = False
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'completed', 'cancelled']:
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            if is_ajax:
                return jsonify({'success': True, 'message': 'Queue status updated successfully!'})
            flash('Queue status updated!', 'success')
        else:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Invalid status.'}), 400
    except Exception as e:
        if is_ajax:
            return jsonify({'success': False, 'message': str(e)}), 500
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
                'id, title, type, event_date, start_time, end_time, max_players, status, location_label, organizer_id, '
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
                    'id, status, registered_at, player_id, check_in_status, checked_in_at, profiles!player_id(first_name, last_name, phone, avatar_url)'
                ).eq('event_id', event_id).execute()
                participants = reg_resp.data or []
                
                # Fetch emails dynamically (batch)
                try:
                    from app import supabase_admin
                    auth_users = supabase_admin.auth.admin.list_users()
                    email_map = {u.id: u.email for u in auth_users}
                    for p in participants:
                        p_id = p.get('player_id')
                        if p_id and p.get('profiles'):
                            p['profiles']['email'] = email_map.get(p_id, 'N/A')
                except Exception as ae:
                    print("Failed to map auth emails for owner:", ae)
            else:
                flash("Event not found or unauthorized.", "error")
                return redirect(url_for('owner.events'))
                
    except Exception as e:
        flash(f'Error loading participants: {e}', 'error')
        
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
        flash(f"Error updating attendance: {e}", "error")
        
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
        flash(f"Error loading tournament manage: {e}", "error")
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
        print(f"Owner bracket advancement error: {e}")


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
        flash(f"Error recording score: {e}", "error")

    return redirect(url_for('owner.tournament_manage', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/matches/<match_id>/assign', methods=['POST'])
@require_role('owner')
def match_assign(event_id, match_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    court_id = request.form.get('court_id') or None
    court_name = request.form.get('court_name') or None
    referee_name = request.form.get('referee_name') or None
    
    # If court_id is provided, try to resolve court name from database as a default/override if custom name isn't set
    if court_id and not court_name:
        try:
            c_resp = db.table('courts').select('name').eq('id', court_id).single().execute()
            if c_resp.data:
                court_name = c_resp.data['name']
        except Exception as ce:
            print("Failed to resolve court name for owner:", ce)

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
        flash(f"Error updating assignment: {e}", "error")
        
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
            
            # Fetch emails dynamically (batch)
            try:
                from app import supabase_admin
                if supabase_admin:
                    auth_users = supabase_admin.auth.admin.list_users()
                    email_map = {u.id: u.email for u in auth_users}
                    for s in staff_list:
                        p_id = s.get('profiles', {}).get('id') if s.get('profiles') else None
                        if p_id:
                            s['profiles']['email'] = email_map.get(p_id, 'N/A')
            except Exception as ae:
                print("Failed to map auth emails for staff:", ae)
            
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

@owner_bp.route('/staff/<fs_id>/edit', methods=['POST'])
@require_role('owner')
def edit_staff_assignment(fs_id):
    owner_id = session.get('user_id')
    facility_id = request.form.get('facility_id')
    
    if not facility_id:
        flash('Please select a facility.', 'error')
        return redirect(url_for('owner.staff'))
        
    db = get_db()
    try:
        # Verify ownership of target facility
        target_fac = db.table('facilities').select('owner_id').eq('id', facility_id).single().execute()
        if not target_fac.data or target_fac.data['owner_id'] != owner_id:
            flash('Unauthorized facility selection.', 'error')
            return redirect(url_for('owner.staff'))
            
        # Verify ownership of the current staff assignment's facility
        fs_resp = db.table('facility_staff').select('facility_id').eq('id', fs_id).single().execute()
        if fs_resp.data:
            current_fac_id = fs_resp.data['facility_id']
            current_fac = db.table('facilities').select('owner_id').eq('id', current_fac_id).single().execute()
            if current_fac.data and current_fac.data['owner_id'] == owner_id:
                # Update assignment
                db.table('facility_staff').update({'facility_id': facility_id}).eq('id', fs_id).execute()
                flash('Staff assignment updated successfully.', 'success')
            else:
                flash('Unauthorized to edit this staff assignment.', 'error')
        else:
            flash('Staff assignment not found.', 'error')
    except Exception as e:
        flash(f'Error updating staff assignment: {e}', 'error')
        
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
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('owner.profile'))

    stats = {'facilities': 0, 'courts': 0, 'staff': 0}
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', user_id).execute()
        fac_data = fac_resp.data or []
        stats['facilities'] = len(fac_data)
        
        court_resp = db.table('courts').select('id').eq('owner_id', user_id).execute()
        stats['courts'] = len(court_resp.data or [])
        
        fac_ids = [f['id'] for f in fac_data]
        if fac_ids:
            staff_resp = db.table('facility_staff').select('id', count='exact').in_('facility_id', fac_ids).execute()
            stats['staff'] = staff_resp.count or 0
    except Exception as e:
        print(f"Error getting owner profile stats: {e}")

    return render_template('owner/profile.html', stats=stats)

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

# ── Support ──────────────────────────────────────────────────────────────────────
@owner_bp.route('/support')
@require_role('owner')
def support():
    return render_template('owner/support.html')


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

    return redirect(url_for('owner.events'))


# ── Court Quick Status Toggle ─────────────────────────────────────────────────
@owner_bp.route('/courts/<court_id>/status', methods=['POST'])
@require_role('owner')
def toggle_court_status(court_id):
    owner_id = session.get('user_id')
    new_status = request.form.get('status', 'active')
    if new_status not in ['active', 'maintenance', 'closed']:
        flash("Invalid court status.", "error")
        return redirect(url_for('owner.courts'))

    db = get_db()
    try:
        # Verify ownership via facility
        c_resp = db.table('courts').select('id, facility_id').eq('id', court_id).single().execute()
        court = c_resp.data
        if not court:
            flash("Court not found.", "error")
            return redirect(url_for('owner.courts'))

        fac_resp = db.table('facilities').select('id').eq('id', court['facility_id']).eq('owner_id', owner_id).execute()
        if not fac_resp.data:
            flash("Access denied.", "error")
            return redirect(url_for('owner.courts'))

        db.table('courts').update({'status': new_status}).eq('id', court_id).execute()
        flash(f"Court status set to '{new_status.title()}'.", "success")
    except Exception as e:
        flash(f"Error updating court status: {e}", "error")

    return redirect(url_for('owner.courts'))


# ── Payment Ledger ─────────────────────────────────────────────────────────────
@owner_bp.route('/ledger')
@require_role('owner')
def payment_ledger():
    owner_id = session.get('user_id')
    db = get_db()
    transactions = []
    
    try:
        # Fetch facilities owned by this owner
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        facilities_data = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_data]
        
        if fac_ids:
            # Query court_reservations where gcash_ref is not null/empty
            resp = db.table('court_reservations').select(
                'id, date, start_time, end_time, total_amount, status, gcash_ref, created_at, player_id, facility_id, '
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
        flash(f"Error loading payment ledger: {e}", "error")
        
    return render_template('owner/ledger.html', transactions=transactions)


@owner_bp.route('/ledger/<reservation_id>/approve', methods=['POST'])
@require_role('owner')
def approve_payment(reservation_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        # Fetch reservation details to verify ownership and get necessary ids
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, total_amount, player_id, facility_id, court_id, status, '
            'facilities(name, owner_id)'
        ).eq('id', reservation_id).single().execute()
        
        res = res_resp.data
        if not res or res.get('facilities', {}).get('owner_id') != owner_id:
            flash("Reservation not found or unauthorized.", "error")
            return redirect(url_for('owner.payment_ledger'))
            
        if res['status'] == 'confirmed':
            flash("Payment already confirmed.", "info")
            return redirect(url_for('owner.payment_ledger'))
            
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
            print(f"Error triggering autochats: {chat_err}")
            
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
            print(f"Error inserting approval notification: {n_err}")
            
        flash("Payment approved successfully.", "success")
    except Exception as e:
        flash(f"Error approving payment: {e}", "error")
        
    return redirect(url_for('owner.payment_ledger'))


@owner_bp.route('/ledger/<reservation_id>/decline', methods=['POST'])
@require_role('owner')
def decline_payment(reservation_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        # Fetch reservation details to verify ownership and get player_id
        res_resp = db.table('court_reservations').select(
            'id, date, player_id, status, '
            'facilities(name, owner_id)'
        ).eq('id', reservation_id).single().execute()
        
        res = res_resp.data
        if not res or res.get('facilities', {}).get('owner_id') != owner_id:
            flash("Reservation not found or unauthorized.", "error")
            return redirect(url_for('owner.payment_ledger'))
            
        if res['status'] == 'cancelled':
            flash("Reservation is already cancelled.", "info")
            return redirect(url_for('owner.payment_ledger'))
            
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
            print(f"Error inserting decline notification: {n_err}")
            
        flash("Payment declined and reservation cancelled.", "success")
    except Exception as e:
        flash(f"Error declining payment: {e}", "error")
        
    return redirect(url_for('owner.payment_ledger'))

