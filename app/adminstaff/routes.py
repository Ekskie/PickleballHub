from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime, timedelta, timezone, date

PH_TZ = timezone(timedelta(hours=8))

from app.db import get_db, get_admin_db, log_audit_action



adminstaff_bp = Blueprint('adminstaff', __name__, url_prefix='/adminstaff')

@adminstaff_bp.route('/dashboard')
@require_role('adminstaff')
def dashboard():
    db = get_admin_db()
    stats = {
        'open_tickets': 0,
        'pending_kyc': 0,
        'open_disputes': 0,
        'total_resolved': 0,
        'total_facilities': 0,
        'verified_kyc': 0,
        'rejected_kyc': 0,
        'unverified_kyc': 0,
        'verification_rate': 0.0,
        'subscription_revenue': 0.0,
        'pending_subscriptions': 0,
        'active_subscribers': 0,
    }
    recent_tickets = []
    pending_facilities = []
    recent_disputes = []
    recent_audit_logs = []
    ticket_chart = {'labels': [], 'opened': [], 'closed': []}
    kyc_chart = {'verified': 0, 'pending': 0, 'unverified': 0, 'rejected': 0, 'total': 0}

    try:
        # 1. Open tickets & resolved tickets
        t_open = db.table('tickets').select('id', count='exact').eq('status', 'open').execute()
        stats['open_tickets'] = t_open.count or 0

        t_closed = db.table('tickets').select('id', count='exact').eq('status', 'closed').execute()
        stats['total_resolved'] = t_closed.count or 0

        # 2. Facility KYC breakdown & pending facilities
        fac_resp = db.table('facilities').select(
            'id, name, location, kyc_status, created_at, kyc_document_url, image_url, owner_id, profiles!owner_id(first_name, last_name, email, phone)'
        ).order('created_at', desc=True).execute()
        all_facs = fac_resp.data or []
        
        stats['total_facilities'] = len(all_facs)
        for f in all_facs:
            k_stat = f.get('kyc_status') or 'unverified'
            if k_stat == 'verified':
                stats['verified_kyc'] += 1
            elif k_stat == 'pending_approval':
                stats['pending_kyc'] += 1
                pending_facilities.append(f)
            elif k_stat == 'rejected':
                stats['rejected_kyc'] += 1
            else:
                stats['unverified_kyc'] += 1
                
        if stats['total_facilities'] > 0:
            stats['verification_rate'] = round((stats['verified_kyc'] / stats['total_facilities']) * 100, 1)

        kyc_chart = {
            'verified': stats['verified_kyc'],
            'pending': stats['pending_kyc'],
            'unverified': stats['unverified_kyc'],
            'rejected': stats['rejected_kyc'],
            'total': stats['total_facilities']
        }

        # 3. Open disputes
        try:
            d_resp = db.table('disputes').select(
                'id, status, created_at, reporter:profiles!reporter_id(first_name, last_name), reported:profiles!reported_user_id(first_name, last_name)'
            ).order('created_at', desc=True).execute()
            all_disputes = d_resp.data or []
            stats['open_disputes'] = sum(1 for d in all_disputes if d.get('status') in ['open', 'investigating'])
            recent_disputes = [d for d in all_disputes if d.get('status') in ['open', 'investigating']][:6]
        except Exception as d_err:
            print(f"Error fetching disputes: {d_err}")
            stats['open_disputes'] = 0
            recent_disputes = []

        # 4. Recent open & in-progress tickets
        tkt_resp = db.table('tickets').select(
            '*, profiles!user_id(first_name, last_name, role)'
        ).order('created_at', desc=True).limit(6).execute()
        recent_tickets = tkt_resp.data or []

        # 5. Ticket chart: last 7 days open vs closed
        all_t = db.table('tickets').select('status, created_at').execute()
        all_tickets = all_t.data or []
        now = datetime.now(PH_TZ)
        labels, opened_data, closed_data = [], [], []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            labels.append(day.strftime('%b %d'))
            opened_data.append(sum(1 for t in all_tickets if (t.get('created_at') or '').startswith(day_str)))
            closed_data.append(sum(1 for t in all_tickets if t.get('status') == 'closed' and (t.get('created_at') or '').startswith(day_str)))
        ticket_chart = {'labels': labels, 'opened': opened_data, 'closed': closed_data}

        # 6. Recent Audit Logs
        try:
            audit_resp = db.table('audit_logs').select(
                'id, actor_id, action, target_resource, details, created_at, profiles!actor_id(first_name, last_name, role)'
            ).order('created_at', desc=True).limit(6).execute()
            recent_audit_logs = audit_resp.data or []
        except Exception as a_err:
            recent_audit_logs = []

        # 7. Subscriptions Ledger Metrics
        try:
            subs_resp = db.table('subscriptions').select('amount, status').execute()
            all_subs = subs_resp.data or []
            stats['subscription_revenue'] = sum(float(s.get('amount') or 0) for s in all_subs if s.get('status') == 'active')
            stats['pending_subscriptions'] = sum(1 for s in all_subs if s.get('status') == 'pending_approval')
            stats['active_subscribers'] = sum(1 for s in all_subs if s.get('status') == 'active')
        except Exception as sub_err:
            print(f"Adminstaff subscription metrics error: {sub_err}")

    except Exception as e:
        flash(f'An error occurred: {e}', 'error')

    return render_template('adminstaff/dashboard.html',
                           stats=stats,
                           recent_tickets=recent_tickets,
                           pending_facilities=pending_facilities,
                           recent_disputes=recent_disputes,
                           recent_audit_logs=recent_audit_logs,
                           ticket_chart=ticket_chart,
                           kyc_chart=kyc_chart)


@adminstaff_bp.route('/support')
@require_role('adminstaff')
def support():
    db = get_admin_db()
    tickets = []
    try:
        resp = db.table('tickets').select('*, profiles!user_id(id, first_name, last_name, email, phone, role, avatar_url)').order('created_at', desc=True).execute()
        tickets = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('adminstaff/support.html', tickets=tickets)

@adminstaff_bp.route('/support/<ticket_id>/resolve', methods=['POST'])
@adminstaff_bp.route('/support/<ticket_id>/update', methods=['POST'])
@require_role('adminstaff')
def resolve_ticket(ticket_id):
    req_json = request.get_json(silent=True) or {}
    response = (request.form.get('response') or req_json.get('response') or '').strip()
    status = (request.form.get('status') or req_json.get('status') or '').strip().lower()

    # notify_user flag: True by default unless explicitly disabled
    raw_notify = request.form.get('notify_user') if 'notify_user' in request.form else req_json.get('notify_user')
    if raw_notify is None:
        notify_user = True
    elif isinstance(raw_notify, bool):
        notify_user = raw_notify
    else:
        notify_user = str(raw_notify).lower() in ('1', 'true', 'on', 'yes')

    # Allowed statuses: 'open', 'in_progress', 'closed'
    allowed_statuses = ['open', 'in_progress', 'closed']
    if not status or status not in allowed_statuses:
        status = 'closed'

    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

    db = get_admin_db()
    try:
        # Fetch current ticket details for user notification and audit
        tkt_query = db.table('tickets').select('id, user_id, subject, status, response').eq('id', ticket_id).execute()
        ticket_data = tkt_query.data[0] if (tkt_query and tkt_query.data) else {}
        user_id = ticket_data.get('user_id')
        subject = ticket_data.get('subject', 'Ticket Inquiry')

        update_payload = {'status': status}
        if response:
            update_payload['response'] = response
        elif 'response' in request.form or 'response' in req_json:
            update_payload['response'] = response

        db.table('tickets').update(update_payload).eq('id', ticket_id).execute()

        # In-app notification to the ticket submitter
        if notify_user and user_id:
            status_label = 'Resolved' if status == 'closed' else ('In Progress' if status == 'in_progress' else 'Reopened')
            notif_title = f"Support Ticket #{ticket_id[:6].upper()}: {status_label}"
            notif_msg = response[:180] if response else f"Your support ticket '{subject}' status has been updated to {status_label}."
            try:
                db.table('notifications').insert({
                    'user_id': user_id,
                    'title': notif_title,
                    'message': notif_msg,
                    'type': 'success' if status == 'closed' else 'info',
                    'link': ''
                }).execute()
            except Exception as notif_err:
                print(f"Warning: Could not create ticket update notification: {notif_err}")

        audit_action = 'resolve_ticket' if status == 'closed' else 'update_ticket'
        log_audit_action(audit_action, ticket_id, {
            'status': status,
            'response': response,
            'notified_user': notify_user
        }, raise_on_error=True)

        msg = f"Ticket successfully marked as {status.replace('_', ' ').title()}."
        if is_ajax:
            return jsonify({
                'success': True,
                'message': msg,
                'status': status,
                'response': response
            })
        flash(msg, 'success')
    except Exception as e:
        if is_ajax:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('adminstaff.support'))

@adminstaff_bp.route('/verifications')
@require_role('adminstaff')
def verifications():
    db = get_admin_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name, email, phone, avatar_url), courts(*)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('adminstaff/verifications.html', facilities=facilities)

@adminstaff_bp.route('/verifications/<facility_id>/status', methods=['POST'])
@require_role('adminstaff')
def update_kyc_status(facility_id):
    req_json = request.get_json(silent=True) or {}
    status = request.form.get('status') or req_json.get('status')
    reason = (request.form.get('reason') or req_json.get('reason') or '').strip()
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

    if status not in ['verified', 'rejected', 'unverified', 'pending_approval']:
        msg = 'Invalid status.'
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('adminstaff.verifications'))
    db = get_admin_db()
    try:
        # Fetch facility info to notify the facility owner
        fac_resp = db.table('facilities').select('id, name, owner_id').eq('id', facility_id).single().execute()
        fac_data = fac_resp.data or {}
        owner_id = fac_data.get('owner_id')
        fac_name = fac_data.get('name', 'Facility')

        db.table('facilities').update({'kyc_status': status}).eq('id', facility_id).execute()
        log_audit_action('update_facility_kyc', facility_id, {'status': status, 'reason': reason}, raise_on_error=False)

        # Send in-app notification to facility owner
        if owner_id:
            try:
                if status == 'verified':
                    db.table('notifications').insert({
                        'user_id': owner_id,
                        'title': 'Facility KYC Approved',
                        'message': f'Great news! Your facility "{fac_name}" KYC has been verified. You can now accept public reservations.',
                        'type': 'success',
                        'link': '/owner/facilities'
                    }).execute()
                elif status == 'rejected':
                    rej_msg = f'Your KYC verification for "{fac_name}" was rejected.'
                    if reason:
                        rej_msg += f' Reason: {reason}.'
                    rej_msg += ' Please update your documents and resubmit.'
                    db.table('notifications').insert({
                        'user_id': owner_id,
                        'title': 'Facility KYC Rejected',
                        'message': rej_msg,
                        'type': 'warning',
                        'link': '/owner/facilities'
                    }).execute()
            except Exception as notif_err:
                from flask import current_app
                current_app.logger.warning(f"Failed to insert KYC notification for owner {owner_id}: {notif_err}")

        msg = f'Facility KYC status updated to {status.replace("_", " ").title()}.'
        if is_ajax:
            return jsonify({'success': True, 'message': msg, 'status': status})
        flash(msg, 'success')
    except Exception as e:
        msg = f'An error occurred: {e}'
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'error')
    return redirect(url_for('adminstaff.verifications'))

# ── Disputes ────────────────────────────────────────────────────────────────────
@adminstaff_bp.route('/disputes')
@require_role('adminstaff')
def disputes():
    db = get_admin_db()
    disputes_list = []
    try:
        resp = db.table('disputes').select(
            '*, reporter:profiles!reporter_id(first_name, last_name), '
            'reported:profiles!reported_user_id(first_name, last_name)'
        ).order('created_at', desc=True).execute()
        disputes_list = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('adminstaff/disputes.html', disputes=disputes_list)

@adminstaff_bp.route('/disputes/<dispute_id>/update', methods=['POST'])
@require_role('adminstaff')
def update_dispute(dispute_id):
    req_json = request.get_json(silent=True) or {}
    new_status = request.form.get('status') or req_json.get('status')
    resolution = (request.form.get('resolution') or req_json.get('resolution') or '').strip()
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

    allowed = ['open', 'investigating', 'resolved', 'dismissed']
    if new_status not in allowed:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid status.'}), 400
        flash('Invalid status.', 'error')
        return redirect(url_for('adminstaff.disputes'))
    db = get_admin_db()
    try:
        db.table('disputes').update({
            'status': new_status,
            'resolution': resolution,
            'updated_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', dispute_id).execute()
        log_audit_action('update_dispute', dispute_id, {'status': new_status, 'resolution': resolution}, raise_on_error=True)
        msg = f'Dispute marked as {new_status}.'
        if is_ajax:
            return jsonify({'success': True, 'message': msg, 'status': new_status})
        flash(msg, 'success')
    except Exception as e:
        if is_ajax:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('adminstaff.disputes'))

@adminstaff_bp.route('/profile', methods=['GET', 'POST'])
@require_role('adminstaff')
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
            flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('adminstaff.profile'))
    
    # GET — load stats and render
    stats = {'open_tickets': 0, 'pending_kyc': 0, 'open_disputes': 0, 'total_facilities': 0, 'resolved_tickets': 0, 'total_tickets': 0}
    recent_logs = []
    try:
        stats['open_tickets'] = db.table('tickets').select('id', count='exact').eq('status', 'open').execute().count or 0
        stats['resolved_tickets'] = db.table('tickets').select('id', count='exact').eq('status', 'closed').execute().count or 0
        stats['total_tickets'] = stats['open_tickets'] + stats['resolved_tickets']
        
        stats['pending_kyc'] = db.table('facilities').select('id', count='exact').eq('kyc_status', 'pending_approval').execute().count or 0
        try:
            stats['open_disputes'] = db.table('disputes').select('id', count='exact').eq('status', 'open').execute().count or 0
        except Exception:
            stats['open_disputes'] = 0
        stats['total_facilities'] = db.table('facilities').select('id', count='exact').execute().count or 0

        admin_db = get_admin_db()
        audit_resp = admin_db.table('audit_logs').select('*').order('created_at', desc=True).limit(6).execute()
        recent_logs = audit_resp.data or []
    except Exception as e:
        print(f"Error fetching stats for profile: {e}")
    return render_template('adminstaff/profile.html', stats=stats, recent_logs=recent_logs)

@adminstaff_bp.route('/change-password', methods=['POST'])
@require_role('adminstaff')
def change_password():
    user_id = session.get('user_id')
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not new_password or new_password != confirm_password:
        flash("Passwords do not match or are empty.", "error")
        return redirect(url_for('adminstaff.profile'))

    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for('adminstaff.profile'))

    if not old_password:
        flash("Current password is required to set a new password.", "error")
        return redirect(url_for('adminstaff.profile'))

    try:
        email = session.get('email', '')
        db = get_db()
        db.auth.sign_in_with_password({"email": email, "password": old_password})
    except Exception:
        flash("Current password is incorrect.", "error")
        return redirect(url_for('adminstaff.profile'))

    try:
        admin_db = get_admin_db()
        admin_db.auth.admin.update_user_by_id(user_id, {"password": new_password})
        log_audit_action('change_password', user_id, {'type': 'self_update'}, raise_on_error=False)
        flash("Password updated successfully.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating password for adminstaff {user_id}: {e}")
        flash("Could not update password. Please try again.", "error")

    return redirect(url_for('adminstaff.profile'))

@adminstaff_bp.route('/notifications')
@require_role('adminstaff')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('adminstaff/notifications.html', notifications=notifs)

@adminstaff_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('adminstaff')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@adminstaff_bp.route('/messages')
@require_role('adminstaff')
def messages():
    return render_template('adminstaff/messages.html')

@adminstaff_bp.route('/community')
@require_role('adminstaff')
def community():
    return render_template('adminstaff/community.html')

@adminstaff_bp.route('/tutorials')
@require_role('adminstaff')
def tutorials():
    return render_template('adminstaff/tutorials.html')


@adminstaff_bp.route('/subscriptions', methods=['GET', 'POST'])
@require_role('adminstaff')
def subscriptions():
    """Subscriptions & Billing ledger for Admin Staff: verify GCash receipts, track members, approve/reject."""
    db = get_admin_db()

    if request.method == 'POST':
        action = request.form.get('action')
        sub_id = request.form.get('sub_id')

        if not sub_id:
            flash('Invalid subscription record specified.', 'error')
            return redirect(url_for('adminstaff.subscriptions'))

        try:
            sub_res = db.table('subscriptions').select('*, profiles!user_id(id, first_name, last_name, email)').eq('id', sub_id).single().execute()
            sub_data = sub_res.data
            if not sub_data:
                flash('Subscription record not found.', 'error')
                return redirect(url_for('adminstaff.subscriptions'))

            user_id = sub_data.get('user_id')
            user_prof = sub_data.get('profiles') or {}
            user_name = f"{user_prof.get('first_name', '')} {user_prof.get('last_name', '')}".strip() or "User"
            reviewer_id = session.get('user_id')
            now_utc = datetime.now(timezone.utc)
            now_iso = now_utc.isoformat()

            if action == 'approve':
                cycle = sub_data.get('billing_cycle', 'monthly')
                plan = sub_data.get('tier', 'pro')
                amount = float(sub_data.get('amount') or 0.0)
                duration_days = 365 if cycle == 'annual' else 30
                expires_at_iso = (now_utc + timedelta(days=duration_days)).isoformat()

                # Update subscription record
                db.table('subscriptions').update({
                    'status': 'active',
                    'reviewed_by': reviewer_id,
                    'reviewed_at': now_iso,
                    'starts_at': now_iso,
                    'expires_at': expires_at_iso
                }).eq('id', sub_id).execute()

                # Update user profile
                db.table('profiles').update({
                    'subscription_tier': plan,
                    'subscription_status': 'active',
                    'subscription_billing_cycle': cycle,
                    'subscription_expires_at': expires_at_iso
                }).eq('id', user_id).execute()

                log_audit_action('approve_subscription', str(sub_id), {
                    'user_id': user_id,
                    'tier': plan,
                    'cycle': cycle,
                    'amount': amount
                })

                # Send in-app notification to the user
                try:
                    plan_label = 'Pickleball Pro Pass' if plan == 'pro' else f"{plan.capitalize()} Membership"
                    db.table('notifications').insert({
                        'user_id': user_id,
                        'title': '🎉 Subscription Approved!',
                        'message': f"Your {plan_label} payment of ₱{amount:,.2f} has been verified and approved! You now enjoy full {plan.capitalize()} privileges and perks.",
                        'type': 'success',
                        'link': url_for('billing.subscription_page')
                    }).execute()
                except Exception as notif_err:
                    current_app.logger.warning(f"Error sending subscription approval notification: {notif_err}")

                flash(f'Subscription payment of ₱{amount:,.2f} for {user_name} approved successfully!', 'success')

            elif action == 'reject':
                notes = request.form.get('notes', '').strip() or 'Payment proof rejected by admin staff'

                # Update subscription record
                db.table('subscriptions').update({
                    'status': 'rejected',
                    'reviewed_by': reviewer_id,
                    'reviewed_at': now_iso,
                    'notes': notes
                }).eq('id', sub_id).execute()

                # Revert user profile to free tier
                db.table('profiles').update({
                    'subscription_tier': 'free',
                    'subscription_status': 'rejected'
                }).eq('id', user_id).execute()

                log_audit_action('reject_subscription', str(sub_id), {
                    'user_id': user_id,
                    'notes': notes
                })

                # Send in-app notification to the user
                try:
                    db.table('notifications').insert({
                        'user_id': user_id,
                        'title': '⚠️ Subscription Payment Needs Attention',
                        'message': f"Your subscription payment proof could not be verified. Note from admin: '{notes}'. Click to review and resubmit.",
                        'type': 'warning',
                        'link': url_for('billing.subscription_page')
                    }).execute()
                except Exception as notif_err:
                    current_app.logger.warning(f"Error sending subscription rejection notification: {notif_err}")

                flash(f'Subscription payment for {user_name} has been rejected. Account reverted to free tier.', 'warning')

        except Exception as e:
            flash(f'Failed to process subscription action: {e}', 'error')

        return redirect(url_for('adminstaff.subscriptions'))

    # GET Request
    filter_status = request.args.get('status', 'pending_approval').strip()
    analytics = {
        'total_cash': 0.0,
        'pending_cash': 0.0,
        'active_subscribers': 0,
        'pending_count': 0,
        'rejected_count': 0,
        'pro_count': 0,
        'elite_count': 0,
        'total_count': 0
    }
    subscriptions_list = []

    try:
        sub_query = db.table('subscriptions').select(
            '*, profiles!user_id(id, first_name, last_name, email, phone, avatar_url, role)'
        ).order('created_at', desc=True).execute()
        all_subs = sub_query.data or []

        analytics['total_count'] = len(all_subs)
        for s in all_subs:
            st = s.get('status')
            amt = float(s.get('amount') or 0.0)
            tier = (s.get('tier') or '').lower()

            if st == 'active':
                analytics['total_cash'] += amt
                analytics['active_subscribers'] += 1
                if tier == 'pro':
                    analytics['pro_count'] += 1
                elif tier == 'elite':
                    analytics['elite_count'] += 1
            elif st == 'pending_approval':
                analytics['pending_cash'] += amt
                analytics['pending_count'] += 1
            elif st == 'rejected':
                analytics['rejected_count'] += 1

        if filter_status == 'all':
            subscriptions_list = all_subs
        else:
            subscriptions_list = [s for s in all_subs if s.get('status') == filter_status]

    except Exception as e:
        flash(f'Error retrieving subscriptions ledger: {e}', 'error')

    return render_template('adminstaff/subscriptions.html',
                           subscriptions=subscriptions_list,
                           analytics=analytics,
                           current_filter=filter_status)


