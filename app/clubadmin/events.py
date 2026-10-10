import time
from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash, g
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.clubadmin import clubadmin_bp
from app.owner.routes import PH_TZ

@clubadmin_bp.route('/events')
@require_role('clubadmin')
def events():
    clubadmin_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        ev_resp = db.table('events').select(
            'id, title, type, format, event_date, start_time, end_time, max_players, entry_fee, prize_pool, status, location_label, organizer_id, gcash_ref, rejection_reason, facility_id, facilities(name)'
        ).eq('organizer_id', clubadmin_id).order('event_date', desc=False).execute()
        events_list = ev_resp.data or []
        
        # Optimized N+1 registration counts & court details
        if events_list:
            ev_ids = [ev['id'] for ev in events_list]
            reg_resp = db.table('event_registrations').select('event_id').in_('event_id', ev_ids).eq('status', 'registered').execute()
            reg_data = reg_resp.data or []
            
            from collections import Counter
            reg_counts = Counter(r['event_id'] for r in reg_data)

            # Fetch courts booked for each event
            court_resp = db.table('event_courts').select('event_id, court_id, courts(name, type, hourly_rate)').in_('event_id', ev_ids).execute()
            courts_by_ev = {}
            for c in (court_resp.data or []):
                eid = c['event_id']
                if eid not in courts_by_ev:
                    courts_by_ev[eid] = []
                if c.get('courts'):
                    courts_by_ev[eid].append(c['courts'])
            
            for ev in events_list:
                ev['registered_count'] = reg_counts[ev['id']]
                ev['courts'] = courts_by_ev.get(ev['id'], [])
                # Calculate duration in hours
                try:
                    sh = float(ev['start_time'][:2]) + float(ev['start_time'][3:5])/60.0
                    eh = float(ev['end_time'][:2]) + float(ev['end_time'][3:5])/60.0
                    hrs = max(0.5, eh - sh) if eh > sh else 1.0
                except Exception:
                    hrs = 1.0
                ev['duration_hours'] = round(hrs, 1)
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading events for clubadmin {clubadmin_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    # Compute KPI statistics
    total_events = len(events_list)
    active_count = sum(1 for e in events_list if e.get('status') in ['registration_open', 'upcoming'])
    pending_count = sum(1 for e in events_list if e.get('status') == 'pending_approval')
    total_players = sum(e.get('registered_count', 0) for e in events_list)
    kpis = {
        'total_events': total_events,
        'active_count': active_count,
        'pending_count': pending_count,
        'total_players': total_players
    }
        
    return render_template('clubadmin/events.html', events=events_list, kpis=kpis)

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
            # Fetch participants with joined profiles (email is fetched directly from database)
            reg_resp = db.table('event_registrations').select(
                'id, player_id, status, registered_at, check_in_status, checked_in_at, profiles!player_id(first_name, last_name, phone, avatar_url, email)'
            ).eq('event_id', event_id).execute()
            participants = reg_resp.data or []
        else:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('clubadmin.events'))
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error fetching participants for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('clubadmin/event_participants.html', event=event_details, participants=participants)

@clubadmin_bp.route('/events/<event_id>/registrations/<reg_id>/checkin', methods=['POST'])
@require_role('clubadmin')
def event_check_in(event_id, reg_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    
    status = request.form.get('status', 'pending')
    if status not in ['pending', 'checked_in', 'no_show']:
        status = 'pending'
        
    checked_in_at = datetime.now(PH_TZ).isoformat() if status == 'checked_in' else None
    
    try:
        # Verify event belongs to this clubadmin
        ev_resp = db.table('events').select('id').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('clubadmin.events'))
            
        db.table('event_registrations').update({
            'check_in_status': status,
            'checked_in_at': checked_in_at
        }).eq('id', reg_id).eq('event_id', event_id).execute()
        
        flash("Participant attendance updated.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error checking in participant {reg_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('clubadmin.event_participants', event_id=event_id))

@clubadmin_bp.route('/events/create', methods=['GET', 'POST'])
@require_role('clubadmin')
def create_event():
    clubadmin_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'GET':
        facilities_list = []
        try:
            fac_resp = db.table('facilities').select('id, name, location').eq('status', 'active').execute()
            facilities_list = fac_resp.data or []
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error loading create event facilities list: {e}")
            flash('An error occurred. Please try again.', 'error')
        return render_template('clubadmin/create_event.html', facilities=facilities_list)
        
    # POST
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

    if not all([title, event_date, start_time, end_time]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('clubadmin.create_event'))

    # Check court conflicts before inserting
    if facility_id and court_ids:
        from app.booking_utils import check_court_conflict
        for cid in court_ids:
            has_conf, conf_detail = check_court_conflict(db, cid, event_date, start_time, end_time)
            if has_conf:
                flash(f"Court conflict detected: {conf_detail['label']} is scheduled from {conf_detail['start_time']} to {conf_detail['end_time']}. Please select different courts or times.", 'error')
                return redirect(url_for('clubadmin.create_event'))

    # Handle Image Upload
    image_file = request.files.get('image')
    image_url = None
    if image_file and image_file.filename:
        try:
            filename = f"events/{clubadmin_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
            file_bytes = image_file.read()
            db.storage.from_('community-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('community-images').get_public_url(filename)
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Image upload error: {e}")
            flash(f'Warning: Image could not be uploaded.', 'error')

    # Calculate status: if facility is chosen, start with pending_payment to facility
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
                flash(f'Event "{title}" saved. Please submit facility payment to request approval.', 'info')
                return redirect(url_for('clubadmin.facility_payment', event_id=event_id))
            else:
                flash(f'Event "{title}" published successfully!', 'success')
                return redirect(url_for('clubadmin.events'))
                
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error creating event by clubadmin {clubadmin_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('clubadmin.events'))

@clubadmin_bp.route('/events/<event_id>/facility_payment', methods=['GET', 'POST'])
@require_role('clubadmin')
def facility_payment(event_id):
    clubadmin_id = session.get('user_id')
    db = get_db()
    try:
        ev_resp = db.table('events').select('*, facilities(id, name, location, owner_id)').eq('id', event_id).eq('organizer_id', clubadmin_id).single().execute()
        event = ev_resp.data
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('clubadmin.events'))
            
        if request.method == 'GET':
            # Calculate price and get court details
            court_resp = db.table('event_courts').select('court_id, courts(name, hourly_rate)').eq('event_id', event_id).execute()
            courts_data = [c['courts'] for c in (court_resp.data or []) if c.get('courts')]
            total_rate = sum([float(c.get('hourly_rate') or 0) for c in courts_data])
            
            # Hour diff
            sh = float(event['start_time'][:2]) + float(event['start_time'][3:5])/60.0
            eh = float(event['end_time'][:2]) + float(event['end_time'][3:5])/60.0
            hours = max(0.5, eh - sh) if eh > sh else 1.0
            total_price = total_rate * hours
            
            # Facility owner profile for payment phone info if available
            facility_owner = None
            if event.get('facilities') and event['facilities'].get('owner_id'):
                try:
                    fo_resp = db.table('profiles').select('first_name, last_name, phone').eq('id', event['facilities']['owner_id']).single().execute()
                    facility_owner = fo_resp.data
                except Exception:
                    pass

            return render_template(
                'clubadmin/facility_payment.html', 
                event=event, 
                total_price=total_price, 
                courts=courts_data,
                courts_count=len(courts_data), 
                hours=round(hours, 1),
                facility_owner=facility_owner
            )
            
        # POST: Process GCash Reference Number submission
        import re
        gcash_ref = request.form.get('gcash_ref', '').strip()
        if not gcash_ref:
            flash('Please enter your 13-digit GCash reference number.', 'error')
            return redirect(url_for('clubadmin.facility_payment', event_id=event_id))
            
        if not re.match(r'^\d{13}$', gcash_ref):
            flash('Invalid GCash reference number format. Must be exactly 13 digits.', 'error')
            return redirect(url_for('clubadmin.facility_payment', event_id=event_id))

        # Check duplicate reference number
        dup_ev = db.table('events').select('id').eq('gcash_ref', gcash_ref).neq('id', event_id).execute()
        dup_res = db.table('court_reservations').select('id').eq('gcash_ref', gcash_ref).execute()
        if dup_ev.data or dup_res.data:
            flash('This GCash reference number has already been submitted for another booking.', 'error')
            return redirect(url_for('clubadmin.facility_payment', event_id=event_id))

        # Re-check for any last-minute court conflicts
        from app.booking_utils import check_court_conflict, notify_facility_staff_and_owner
        court_resp = db.table('event_courts').select('court_id, courts(name)').eq('event_id', event_id).execute()
        for c in (court_resp.data or []):
            cid = c['court_id']
            has_conf, conf_detail = check_court_conflict(db, cid, event['event_date'], event['start_time'], event['end_time'], exclude_event_id=event_id)
            if has_conf:
                flash(f"Cannot submit booking: Court '{c.get('courts', {}).get('name', 'Court')}' now conflicts with {conf_detail['label']} ({conf_detail['start_time']}-{conf_detail['end_time']}).", 'error')
                return redirect(url_for('clubadmin.edit_event', event_id=event_id))

        # Update event status to pending_approval with GCash reference
        db.table('events').update({
            'status': 'pending_approval',
            'gcash_ref': gcash_ref
        }).eq('id', event_id).execute()

        # Notify Facility Owner and assigned Staff
        notify_facility_staff_and_owner(
            db=db,
            facility_id=event['facility_id'],
            title=f"New Event Booking Request: {event['title']}",
            message=f"Event booking for '{event['title']}' on {event['event_date']} ({event['start_time'][:5]}-{event['end_time'][:5]}) submitted with GCash Ref: {gcash_ref}. Awaiting your approval.",
            link=url_for('owner.events'),
            notif_type='info'
        )

        flash(f'Payment submitted! Your event booking is now pending approval from the facility owner/staff.', 'success')
        return redirect(url_for('clubadmin.events'))
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error processing facility payment: {e}")
        flash('An error occurred. Please try again.', 'error')
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

        court_ids = request.form.getlist('court_ids')
        if facility_id and court_ids:
            from app.booking_utils import check_court_conflict
            for cid in court_ids:
                has_conf, conf_detail = check_court_conflict(db, cid, event_date, start_time, end_time, exclude_event_id=event_id)
                if has_conf:
                    flash(f"Court conflict: {conf_detail['label']} ({conf_detail['start_time']}-{conf_detail['end_time']}) overlaps your selected time.", 'error')
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
                filename = f"events/{clubadmin_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
                file_bytes = image_file.read()
                db.storage.from_('community-images').upload(
                    file=file_bytes,
                    path=filename,
                    file_options={"content-type": image_file.content_type}
                )
                update_data['image_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                from flask import current_app
                current_app.logger.error(f"Image edit upload error: {e}")
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
        from flask import current_app
        current_app.logger.error(f"Error editing event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
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
        
        # Notify (batch insert)
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).execute()
        if reg_resp.data:
            notifs = [
                {
                    'user_id': r['player_id'],
                    'title': f'Event Cancelled: {title}',
                    'message': f'The event "{title}" has been cancelled and removed.',
                    'type': 'system'
                } for r in reg_resp.data
            ]
            db.table('notifications').insert(notifs).execute()
            
        db.table('events').delete().eq('id', event_id).execute()
        flash(f'Event "{title}" deleted successfully.', 'success')
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deleting event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('clubadmin.events'))


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

        # If cancelled, notify all registered players (batch insert)
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
        from flask import current_app
        current_app.logger.error(f"Error changing status for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('clubadmin.events'))
