from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db, get_admin_db, log_audit_action
from app.owner import owner_bp
from app.owner.routes import PH_TZ
from app.billing.tiers import get_user_tier, get_tier_limits

# ── Payment Ledger ─────────────────────────────────────────────────────────────
@owner_bp.route('/ledger')
@require_role('owner')
def payment_ledger():
    owner_id = session.get('user_id')
    db = get_admin_db() or get_db()
    transactions = []
    facilities_data = []

    # Get owner subscription tier and platform commission rate
    owner_tier = get_user_tier(owner_id, role='owner', db=db)
    limits = get_tier_limits('owner', owner_tier)
    commission_rate = limits.get('booking_commission_pct', 0.08)
    commission_rate_pct = int(round(commission_rate * 100))

    stats = {
        'total_verified_revenue': 0.0,
        'total_commission_fees': 0.0,
        'total_net_payout': 0.0,
        'tier_savings': 0.0,
        'commission_rate': commission_rate,
        'commission_rate_pct': commission_rate_pct,
        'owner_tier': owner_tier,
        'pending_revenue': 0.0,
        'pending_count': 0,
        'confirmed_count': 0,
        'completed_count': 0,
        'approved_count': 0,
        'declined_count': 0,
        'total_transactions': 0
    }
    
    try:
        # Fetch facilities owned by this owner
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).order('name').execute()
        facilities_data = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_data]
        
        if fac_ids:
            # Query court_reservations where gcash_ref is not null/empty
            resp = db.table('court_reservations').select(
                'id, date, start_time, end_time, total_amount, status, gcash_ref, receipt_url, created_at, player_id, facility_id, '
                'profiles(first_name, last_name, phone, avatar_url), '
                'courts(name, type), '
                'facilities(id, name)'
            ).in_('facility_id', fac_ids).neq('gcash_ref', None).neq('gcash_ref', '').order('created_at', desc=True).execute()
            
            transactions = resp.data or []
            
            # Post-process user initials & commission breakdown per transaction
            for t in transactions:
                prof = t.get('profiles') or {}
                first = (prof.get('first_name') or ' ')[0]
                last = (prof.get('last_name') or ' ')[0]
                prof['initials'] = (first + last).upper().strip() or '?'

                gross = float(t.get('total_amount') or 0)
                comm_fee = round(gross * commission_rate, 2)
                net_payout = round(gross - comm_fee, 2)
                t['gross_amount'] = gross
                t['commission_fee'] = comm_fee
                t['net_amount'] = net_payout

            # Fetch audit logs to see if reservations were approved by Front Desk staff
            res_ids = [t['id'] for t in transactions]
            approval_audits = {}
            if res_ids:
                try:
                    audit_resp = db.table('audit_logs').select(
                        'target_resource, actor_id, details, created_at, profiles:actor_id(first_name, last_name, role)'
                    ).in_('target_resource', res_ids).eq('action', 'approve_booking_payment').execute()
                    for a in (audit_resp.data or []):
                        rid = a.get('target_resource')
                        aprof = a.get('profiles') or {}
                        afirst = aprof.get('first_name') or ''
                        alast = aprof.get('last_name') or ''
                        actor_name = f"{afirst} {alast}".strip() or 'Staff'
                        adetails = a.get('details') or {}
                        arole = adetails.get('actor_role') or aprof.get('role') or 'staff'
                        is_staff = ('staff' in arole.lower())
                        approval_audits[rid] = {
                            'actor_name': actor_name,
                            'is_staff': is_staff,
                            'role_label': 'Staff' if is_staff else 'Owner'
                        }
                except Exception as a_err:
                    from flask import current_app
                    current_app.logger.warning(f"Error fetching approval audit logs: {a_err}")

            for t in transactions:
                t['approved_by'] = approval_audits.get(t['id'])

            # Compute rich financial and operational stats
            total_verified_revenue = sum(t['gross_amount'] for t in transactions if t.get('status') in ['confirmed', 'completed'])
            total_commission_fees = sum(t['commission_fee'] for t in transactions if t.get('status') in ['confirmed', 'completed'])
            total_net_payout = round(total_verified_revenue - total_commission_fees, 2)

            # Savings compared to Free Starter tier (8% fee)
            starter_commission = round(total_verified_revenue * 0.08, 2)
            tier_savings = max(0.0, round(starter_commission - total_commission_fees, 2))

            pending_revenue = sum(float(t.get('total_amount') or 0) for t in transactions if t.get('status') == 'pending_payment')
            pending_count = sum(1 for t in transactions if t.get('status') == 'pending_payment')
            confirmed_count = sum(1 for t in transactions if t.get('status') == 'confirmed')
            completed_count = sum(1 for t in transactions if t.get('status') == 'completed')
            approved_count = confirmed_count + completed_count
            declined_count = sum(1 for t in transactions if t.get('status') == 'cancelled')

            stats = {
                'total_verified_revenue': total_verified_revenue,
                'total_commission_fees': total_commission_fees,
                'total_net_payout': total_net_payout,
                'tier_savings': tier_savings,
                'commission_rate': commission_rate,
                'commission_rate_pct': commission_rate_pct,
                'owner_tier': owner_tier,
                'pending_revenue': pending_revenue,
                'pending_count': pending_count,
                'confirmed_count': confirmed_count,
                'completed_count': completed_count,
                'approved_count': approved_count,
                'declined_count': declined_count,
                'total_transactions': len(transactions)
            }

            # Attach transaction count to each facility for filter dropdown
            for f in facilities_data:
                f['tx_count'] = sum(1 for t in transactions if t.get('facility_id') == f['id'])

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading payment ledger for owner {owner_id}: {e}")
        flash('An error occurred loading ledger. Please try again.', 'error')
        
    return render_template(
        'owner/ledger.html', 
        transactions=transactions, 
        facilities=facilities_data, 
        stats=stats,
        owner_tier=owner_tier,
        commission_rate_pct=commission_rate_pct
    )


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

        log_audit_action('approve_booking_payment', reservation_id, {
            'actor_role': 'owner',
            'owner_id': owner_id,
            'player_id': res.get('player_id'),
            'total_amount': res.get('total_amount'),
            'facility_id': res.get('facility_id')
        })
        
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

        log_audit_action('decline_booking_payment', reservation_id, {
            'actor_role': 'owner',
            'owner_id': owner_id,
            'player_id': res.get('player_id'),
            'facility_id': res.get('facility_id')
        })
        
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


@owner_bp.route('/ledger/export-csv')
@require_role('owner')
def export_ledger_csv():
    owner_id = session.get('user_id')
    from app.billing.tiers import get_user_tier
    tier = get_user_tier(owner_id, role='owner')
    if tier not in ['pro', 'elite']:
        flash("Exporting payment ledger reports to CSV requires a Pro or Elite Facility subscription. Upgrade your plan to export financial reports.", "warning")
        return redirect(url_for('owner.payment_ledger'))

    db = get_admin_db() or get_db()
    try:
        import csv
        from io import StringIO
        from flask import Response

        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        facilities_data = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_data]

        transactions = []
        if fac_ids:
            resp = db.table('court_reservations').select(
                'id, date, start_time, end_time, total_amount, status, gcash_ref, created_at, '
                'profiles(first_name, last_name, email, phone), '
                'courts(name, type), '
                'facilities(name)'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            transactions = resp.data or []

        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['Reservation ID', 'Booking Date', 'Time Slot', 'Facility', 'Court', 'Customer Name', 'Phone', 'Total (PHP)', 'GCash Reference', 'Status', 'Timestamp'])

        for t in transactions:
            prof = t.get('profiles') or {}
            fac = t.get('facilities') or {}
            court = t.get('courts') or {}
            cust_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
            slot = f"{t.get('start_time', '')} - {t.get('end_time', '')}"
            writer.writerow([
                t.get('id', ''),
                t.get('date', ''),
                slot,
                fac.get('name', ''),
                court.get('name', ''),
                cust_name,
                prof.get('phone', ''),
                t.get('total_amount', 0),
                t.get('gcash_ref', ''),
                t.get('status', ''),
                t.get('created_at', '')[:19]
            ])

        output = si.getvalue()
        filename = f"facility_ledger_{datetime.now().strftime('%Y%m%d')}.csv"
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error exporting ledger CSV: {e}")
        flash('An error occurred generating ledger CSV export.', 'error')
        return redirect(url_for('owner.payment_ledger'))
