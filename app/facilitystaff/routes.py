from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase

def get_db():
    return supabase_admin or supabase


facilitystaff_bp = Blueprint('facilitystaff', __name__, url_prefix='/facilitystaff')

@facilitystaff_bp.route('/dashboard')
@require_role('facilitystaff')
def dashboard():
    return render_template('facilitystaff/dashboard.html')

@facilitystaff_bp.route('/queue')
@require_role('facilitystaff')
def queue():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        # 1. Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # 2. Get courts for these facilities
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # 3. Get active queue items
            q_resp = db.table('court_queues').select(
                'id, facility_id, court_id, status, joined_at, estimated_wait_mins, profiles(first_name, last_name)'
            ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next']).order('joined_at', desc=False).execute()
            queues = q_resp.data or []
            
    except Exception as e:
        flash(f'Error loading queues: {e}', 'error')
        
    return render_template('facilitystaff/queue.html', facilities=assigned_facilities, courts=courts, queues=queues)

@facilitystaff_bp.route('/queue/update', methods=['POST'])
@require_role('facilitystaff')
def update_queue():
    queue_id = request.form.get('queue_id')
    new_status = request.form.get('status')
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'completed', 'cancelled']:
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            flash('Queue status updated!', 'success')
        else:
            flash('Invalid status.', 'error')
    except Exception as e:
        flash(f'Error updating queue: {e}', 'error')
        
    return redirect(url_for('facilitystaff.queue'))

@facilitystaff_bp.route('/schedule')
@require_role('facilitystaff')
def schedule():
    return render_template('facilitystaff/schedule.html')

@facilitystaff_bp.route('/walkin')
@require_role('facilitystaff')
def walkin():
    return render_template('facilitystaff/walkin.html')

@facilitystaff_bp.route('/profile', methods=['GET', 'POST'])
@require_role('facilitystaff')
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
        return redirect(url_for('facilitystaff.profile'))
    return render_template('facilitystaff/profile.html')

@facilitystaff_bp.route('/notifications')
@require_role('facilitystaff')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('facilitystaff/notifications.html', notifications=notifs)

@facilitystaff_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('facilitystaff')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@facilitystaff_bp.route('/messages')
@require_role('facilitystaff')
def messages():
    return render_template('facilitystaff/messages.html')

@facilitystaff_bp.route('/community')
@require_role('facilitystaff')
def community():
    return render_template('facilitystaff/community.html')
