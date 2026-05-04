from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase

def get_db():
    return supabase_admin or supabase


adminstaff_bp = Blueprint('adminstaff', __name__, url_prefix='/adminstaff')

@adminstaff_bp.route('/dashboard')
@require_role('adminstaff')
def dashboard():
    return render_template('adminstaff/dashboard.html')

@adminstaff_bp.route('/support')
@require_role('adminstaff')
def support():
    db = get_db()
    tickets = []
    try:
        resp = db.table('tickets').select('*, profiles!user_id(first_name, last_name, role)').order('created_at', desc=True).execute()
        tickets = resp.data or []
    except Exception as e:
        flash(f'Error loading tickets: {e}', 'error')
    return render_template('adminstaff/support.html', tickets=tickets)

@adminstaff_bp.route('/support/<ticket_id>/resolve', methods=['POST'])
@require_role('adminstaff')
def resolve_ticket(ticket_id):
    response = request.form.get('response', '').strip()
    db = get_db()
    try:
        db.table('tickets').update({
            'status': 'closed',
            'response': response
        }).eq('id', ticket_id).execute()
        flash('Ticket resolved successfully.', 'success')
    except Exception as e:
        flash(f'Error resolving ticket: {e}', 'error')
    return redirect(url_for('adminstaff.support'))

@adminstaff_bp.route('/verifications')
@require_role('adminstaff')
def verifications():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash(f'Error loading verifications: {e}', 'error')
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
        flash(f'Facility KYC status updated to {status}.', 'success')
    except Exception as e:
        flash(f'Error updating status: {e}', 'error')
    return redirect(url_for('adminstaff.verifications'))

@adminstaff_bp.route('/disputes')
@require_role('adminstaff')
def disputes():
    return render_template('adminstaff/disputes.html')

@adminstaff_bp.route('/profile', methods=['GET', 'POST'])
@require_role('adminstaff')
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
        return redirect(url_for('adminstaff.profile'))
    return render_template('adminstaff/profile.html')

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

