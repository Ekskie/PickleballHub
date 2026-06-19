from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from datetime import datetime, timedelta, timezone, date

PH_TZ = timezone(timedelta(hours=8))

from app.db import get_db, get_admin_db, log_audit_action



adminstaff_bp = Blueprint('adminstaff', __name__, url_prefix='/adminstaff')

@adminstaff_bp.route('/dashboard')
@require_role('adminstaff')
def dashboard():
    db = get_db()
    stats = {'open_tickets': 0, 'pending_kyc': 0, 'open_disputes': 0, 'total_resolved': 0}
    recent_tickets = []
    ticket_chart = {'labels': [], 'opened': [], 'closed': []}

    try:
        # Open tickets
        t_open = db.table('tickets').select('id', count='exact').eq('status', 'open').execute()
        stats['open_tickets'] = t_open.count or 0

        # Pending KYC verifications
        kyc_resp = db.table('facilities').select('id', count='exact').eq('kyc_status', 'pending_approval').execute()
        stats['pending_kyc'] = kyc_resp.count or 0

        # Open disputes
        try:
            d_resp = db.table('disputes').select('id', count='exact').eq('status', 'open').execute()
            stats['open_disputes'] = d_resp.count or 0
        except Exception:
            stats['open_disputes'] = 0

        # Total resolved tickets
        t_closed = db.table('tickets').select('id', count='exact').eq('status', 'closed').execute()
        stats['total_resolved'] = t_closed.count or 0

        # Recent open tickets
        tkt_resp = db.table('tickets').select(
            '*, profiles!user_id(first_name, last_name, role)'
        ).eq('status', 'open').order('created_at', desc=True).limit(6).execute()
        recent_tickets = tkt_resp.data or []

        # Ticket chart: last 7 days open vs closed
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

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return render_template('adminstaff/dashboard.html',
                           stats=stats,
                           recent_tickets=recent_tickets,
                           ticket_chart=ticket_chart)


@adminstaff_bp.route('/support')
@require_role('adminstaff')
def support():
    db = get_db()
    tickets = []
    try:
        resp = db.table('tickets').select('*, profiles!user_id(first_name, last_name, role)').order('created_at', desc=True).execute()
        tickets = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('adminstaff/support.html', tickets=tickets)

@adminstaff_bp.route('/support/<ticket_id>/resolve', methods=['POST'])
@require_role('adminstaff')
def resolve_ticket(ticket_id):
    response = request.form.get('response', '').strip()
    db = get_db()
    try:
        db.table('tickets').update({'status': 'closed', 'response': response}).eq('id', ticket_id).execute()
        log_audit_action('resolve_ticket', ticket_id, {'response': response}, raise_on_error=True)
        flash('Ticket resolved successfully.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('adminstaff.support'))

@adminstaff_bp.route('/verifications')
@require_role('adminstaff')
def verifications():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name), courts(*)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('adminstaff/verifications.html', facilities=facilities)

@adminstaff_bp.route('/verifications/<facility_id>/status', methods=['POST'])
@require_role('adminstaff')
def update_kyc_status(facility_id):
    status = request.form.get('status')
    if status not in ['verified', 'rejected', 'unverified']:
        flash('Invalid status.', 'error')
        return redirect(url_for('adminstaff.verifications'))
    db = get_db()
    try:
        db.table('facilities').update({'kyc_status': status}).eq('id', facility_id).execute()
        log_audit_action('update_facility_kyc', facility_id, {'status': status}, raise_on_error=True)
        flash(f'Facility KYC status updated to {status}.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('adminstaff.verifications'))

# ── Disputes ────────────────────────────────────────────────────────────────────
@adminstaff_bp.route('/disputes')
@require_role('adminstaff')
def disputes():
    db = get_db()
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
    new_status = request.form.get('status')
    resolution = request.form.get('resolution', '').strip()
    allowed = ['open', 'investigating', 'resolved', 'dismissed']
    if new_status not in allowed:
        flash('Invalid status.', 'error')
        return redirect(url_for('adminstaff.disputes'))
    db = get_db()
    try:
        db.table('disputes').update({
            'status': new_status,
            'resolution': resolution,
            'updated_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', dispute_id).execute()
        log_audit_action('update_dispute', dispute_id, {'status': new_status, 'resolution': resolution}, raise_on_error=True)
        flash(f'Dispute marked as {new_status}.', 'success')
    except Exception as e:
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
    except Exception as e:
        print(f"Error fetching stats for profile: {e}")
    return render_template('adminstaff/profile.html', stats=stats)

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

