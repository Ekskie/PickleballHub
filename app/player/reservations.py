from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime
from app.db import get_db
from app.player import player_bp
from app.player.routes import PH_TZ

@player_bp.route('/reservation')
@require_role('player')
def reservation():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, open_time, close_time, slot_duration_minutes, kyc_status, image_url, latitude, longitude'
        ).eq('status', 'active').order('name').execute()
        facilities = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
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
            'id, name, type, hourly_rate, status, image_url'
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


@player_bp.route('/reservation/api/facility_occupancy')
@require_role('player')
def api_facility_occupancy():
    """Return all active courts and their bookings for a facility on a given date."""
    facility_id = request.args.get('facility_id')
    date        = request.args.get('date')
    if not facility_id or not date:
        return jsonify({'courts': [], 'reservations': []})
    db = get_db()
    try:
        # Fetch active courts
        courts_resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, image_url'
        ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        courts = courts_resp.data or []
        
        court_ids = [c['id'] for c in courts]
        if not court_ids:
            return jsonify({'courts': [], 'reservations': []})
            
        # Fetch confirmed or pending bookings
        res_resp = db.table('court_reservations').select(
            'court_id, start_time, end_time'
        ).in_('court_id', court_ids).eq('date', date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        
        return jsonify({
            'courts': courts,
            'reservations': res_resp.data or []
        })
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
        # Check for overlapping reservation on this court
        overlap_resp = db.table('court_reservations').select('id')\
            .eq('court_id', court_id)\
            .eq('date', date)\
            .in_('status', ['confirmed', 'pending_payment'])\
            .lt('start_time', end_time)\
            .gt('end_time', start_time)\
            .execute()
            
        if overlap_resp.data:
            flash('This court is already reserved during the selected time slot. Please choose another time or court.', 'error')
            return redirect(url_for('player.reservation'))

        # Check if player already has another overlapping reservation (prevent double-booking)
        player_overlap = db.table('court_reservations').select('id')\
            .eq('player_id', player_id)\
            .eq('date', date)\
            .in_('status', ['confirmed', 'pending_payment'])\
            .lt('start_time', end_time)\
            .gt('end_time', start_time)\
            .execute()
            
        if player_overlap.data:
            flash('You already have another court reservation during this time slot.', 'error')
            return redirect(url_for('player.reservation'))

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
        flash('An error occurred. Please try again.', 'error')

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
            'courts(name, type, image_url), facilities(name, location)'
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
        flash('An error occurred. Please try again.', 'error')
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
        flash('An error occurred. Please try again.', 'error')
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
        flash('An error occurred. Please try again.', 'error')
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
        
    import re
    if not re.match(r'^\d{13}$', gcash_ref):
        flash('Invalid GCash reference number format. Must be a 13-digit number.', 'error')
        return redirect(url_for('player.payment', reservation_id=reservation_id))

    db = get_db()
    try:
        # Check duplicate reference number
        dup_resp = db.table('court_reservations').select('id').eq('gcash_ref', gcash_ref).neq('id', reservation_id).execute()
        if dup_resp.data:
            flash('This GCash reference number has already been used for another booking.', 'error')
            return redirect(url_for('player.payment', reservation_id=reservation_id))

        # Get reservation details for queue insertion
        res_resp = db.table('court_reservations').select('facility_id, court_id').eq('id', reservation_id).single().execute()
        res_data = res_resp.data

        receipt_file = request.files.get('receipt')
        receipt_url = None
        if receipt_file and receipt_file.filename:
            from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE
            receipt_url, upload_err = validate_and_upload(
                db,
                receipt_file,
                bucket='kyc-documents',
                prefix='court_receipt',
                owner_id=player_id,
                allowed_exts=ALLOWED_DOC_EXTENSIONS,
                max_size=MAX_DOC_SIZE
            )
            if upload_err:
                flash(f"Receipt upload failed: {upload_err}", "error")
                return redirect(url_for('player.payment', reservation_id=reservation_id))
        
        if not receipt_url:
            flash("Receipt screenshot is required for court booking verification.", "error")
            return redirect(url_for('player.payment', reservation_id=reservation_id))

        db.table('court_reservations').update({
            'gcash_ref': gcash_ref,
            'receipt_url': receipt_url,
        }).eq('id', reservation_id).eq('player_id', player_id).eq(
            'status', 'pending_payment').execute()

        flash('Payment reference submitted successfully! Your booking is pending verification by the facility owner.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.my_reservations'))
