from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase

def get_db():
    return supabase_admin or supabase


superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

@superadmin_bp.route('/dashboard')
@require_role('superadmin')
def dashboard():
    return render_template('superadmin/dashboard.html')

@superadmin_bp.route('/facilities')
@require_role('superadmin')
def facilities():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select('*, profiles!owner_id(first_name, last_name)').order('created_at', desc=True).execute()
        facilities = resp.data or []
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
    return render_template('superadmin/facilities.html', facilities=facilities)

@superadmin_bp.route('/facilities/<facility_id>/status', methods=['POST'])
@require_role('superadmin')
def update_kyc_status(facility_id):
    status = request.form.get('status')
    if status not in ['verified', 'rejected', 'unverified']:
        flash('Invalid status.', 'error')
        return redirect(url_for('superadmin.facilities'))
        
    db = get_db()
    try:
        db.table('facilities').update({'kyc_status': status}).eq('id', facility_id).execute()
        flash(f'Facility KYC status updated to {status}.', 'success')
    except Exception as e:
        flash(f'Error updating status: {e}', 'error')
    return redirect(url_for('superadmin.facilities'))

@superadmin_bp.route('/users')
@require_role('superadmin')
def users():
    db = get_db()
    adminstaff_list = []
    try:
        resp = db.table('profiles').select('*').eq('role', 'adminstaff').order('created_at', desc=True).execute()
        adminstaff_list = resp.data or []
    except Exception as e:
        flash(f'Error loading users: {e}', 'error')
    return render_template('superadmin/users.html', adminstaff=adminstaff_list)

@superadmin_bp.route('/users/add_adminstaff', methods=['POST'])
@require_role('superadmin')
def add_adminstaff():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    if not all([first_name, email, password]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('superadmin.users'))
        
    db = get_db()
    try:
        from app import supabase_admin
        if not supabase_admin:
            flash("Admin client not available.", "error")
            return redirect(url_for('superadmin.users'))
            
        new_user = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "adminstaff"
            }
        })
        
        staff_id = new_user.user.id
        
        supabase_admin.table('profiles').upsert({
            'id': staff_id,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'adminstaff'
        }, on_conflict='id').execute()
        
        flash(f'Admin Staff account for {first_name} created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating admin staff: {e}', 'error')
        
    return redirect(url_for('superadmin.users'))

@superadmin_bp.route('/reports')
@require_role('superadmin')
def reports():
    return render_template('superadmin/reports.html')

@superadmin_bp.route('/settings')
@require_role('superadmin')
def settings():
    return render_template('superadmin/settings.html')

@superadmin_bp.route('/profile', methods=['GET', 'POST'])
@require_role('superadmin')
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
        return redirect(url_for('superadmin.profile'))
    return render_template('superadmin/profile.html')

@superadmin_bp.route('/notifications')
@require_role('superadmin')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('superadmin/notifications.html', notifications=notifs)

@superadmin_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('superadmin')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@superadmin_bp.route('/messages')
@require_role('superadmin')
def messages():
    return render_template('superadmin/messages.html')

@superadmin_bp.route('/community')
@require_role('superadmin')
def community():
    return render_template('superadmin/community.html')

@superadmin_bp.route('/tutorials')
@require_role('superadmin')
def tutorials():
    return render_template('superadmin/tutorials.html')

