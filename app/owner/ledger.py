from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp
from app.owner.routes import PH_TZ

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
                'id, date, start_time, end_time, total_amount, status, gcash_ref, receipt_url, created_at, player_id, facility_id, '
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
        from flask import current_app
        current_app.logger.error(f"Error loading payment ledger for owner {owner_id}: {e}")
        flash('An error occurred loading ledger. Please try again.', 'error')
        
    return render_template('owner/ledger.html', transactions=transactions)


@owner_bp.route('/ledger/<reservation_id>/approve', methods=['POST'])
@require_role('owner')
def approve_payment(reservation_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    
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
            from flask import current_app
            current_app.logger.error(f"Error triggering autochats: {chat_err}")
            
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
            from flask import current_app
            current_app.logger.error(f"Error inserting approval notification: {n_err}")
            
        flash("Payment approved successfully.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error approving payment {reservation_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.payment_ledger'))


@owner_bp.route('/ledger/<reservation_id>/decline', methods=['POST'])
@require_role('owner')
def decline_payment(reservation_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    
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
            from flask import current_app
            current_app.logger.error(f"Error inserting decline notification: {n_err}")
            
        flash("Payment declined and reservation cancelled.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error declining payment {reservation_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.payment_ledger'))
