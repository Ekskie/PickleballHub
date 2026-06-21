from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

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
            # Fetch staff assigned to these facilities with profiles(email) joined
            staff_resp = db.table('facility_staff').select(
                'id, facility_id, facilities(name), profiles!staff_id(id, first_name, last_name, phone, email)'
            ).in_('facility_id', fac_ids).execute()
            staff_list = staff_resp.data or []
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading staff list for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
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
        admin_db = get_admin_db()
        if not admin_db:
            flash("Admin client not available.", "error")
            return redirect(url_for('owner.staff'))
            
        # 1. Create User in Supabase Auth
        new_user = admin_db.auth.admin.create_user({
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
        
        # 2. Add to profiles table (including email column)
        admin_db.table('profiles').upsert({
            'id': staff_id,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'facilitystaff',
            'email': email
        }, on_conflict='id').execute()
        
        # 3. Assign to facility
        db.table('facility_staff').insert({
            'facility_id': facility_id,
            'staff_id': staff_id
        }).execute()
        
        flash(f'Staff account for {first_name} created and assigned!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error creating staff account by owner {owner_id}: {e}")
        flash('An error occurred creating staff account. Please try again.', 'error')
        
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
        from flask import current_app
        current_app.logger.error(f"Error removing staff assignment {fs_id} by owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
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
        from flask import current_app
        current_app.logger.error(f"Error editing staff assignment {fs_id} by owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.staff'))
