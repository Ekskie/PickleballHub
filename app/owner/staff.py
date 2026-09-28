from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

# ── Staff Management ─────────────────────────────────────────────────────────
@owner_bp.route('/staff')
@require_role('owner')
def staff():
    owner_id = session.get('user_id')
    db = get_admin_db() or get_db()
    staff_list = []
    facilities_list = []
    stats = {
        'total_staff': 0,
        'facilities_covered': 0,
        'total_facilities': 0,
        'coverage_pct': 0,
        'unassigned_facilities': []
    }
    
    try:
        # Get owner's facilities
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).order('name').execute()
        facilities_list = fac_resp.data or []
        fac_ids = [f['id'] for f in facilities_list]
        
        if fac_ids:
            # Fetch staff assigned to these facilities with profiles joined
            staff_resp = db.table('facility_staff').select(
                'id, facility_id, created_at, facilities(id, name, location), profiles!staff_id(id, first_name, last_name, phone, email, avatar_url, role)'
            ).in_('facility_id', fac_ids).order('created_at', desc=True).execute()
            staff_list = staff_resp.data or []
            
        # Compute staffing KPI metrics
        assigned_fac_ids = {s['facility_id'] for s in staff_list if s.get('facility_id')}
        total_facilities = len(facilities_list)
        facilities_covered = len(assigned_fac_ids)
        coverage_pct = round((facilities_covered / total_facilities * 100)) if total_facilities > 0 else 0
        unassigned_facs = [f for f in facilities_list if f['id'] not in assigned_fac_ids]
        
        # Attach staff count to each facility for filter display
        for fac in facilities_list:
            fac['staff_count'] = sum(1 for s in staff_list if s.get('facility_id') == fac['id'])
            
        stats = {
            'total_staff': len(staff_list),
            'facilities_covered': facilities_covered,
            'total_facilities': total_facilities,
            'coverage_pct': coverage_pct,
            'unassigned_facilities': unassigned_facs
        }
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading staff list for owner {owner_id}: {e}")
        flash('An error occurred loading staff members. Please try again.', 'error')
        
    return render_template('owner/staff.html', staff=staff_list, facilities=facilities_list, stats=stats)

@owner_bp.route('/staff/add', methods=['POST'])
@require_role('owner')
def add_staff():
    owner_id = session.get('user_id')
    facility_id = request.form.get('facility_id')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()
    
    if not all([facility_id, first_name, email, password]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('owner.staff'))
        
    admin_db = get_admin_db() or get_db()
    try:
        if not admin_db:
            flash("Admin client not available.", "error")
            return redirect(url_for('owner.staff'))
            
        # Verify ownership of target facility
        target_fac = admin_db.table('facilities').select('id, name, owner_id').eq('id', facility_id).single().execute()
        if not target_fac.data or target_fac.data['owner_id'] != owner_id:
            flash('Unauthorized facility selection.', 'error')
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
        
        # 2. Add to profiles table
        profile_data = {
            'id': staff_id,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'facilitystaff',
            'email': email,
            'phone': phone if phone else None
        }
        admin_db.table('profiles').upsert(profile_data, on_conflict='id').execute()
        
        # 3. Assign to facility
        admin_db.table('facility_staff').insert({
            'facility_id': facility_id,
            'staff_id': staff_id
        }).execute()
        
        fac_name = target_fac.data.get('name', 'Facility')
        flash(f'Staff account for {first_name} {last_name} created and assigned to {fac_name}!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error creating staff account by owner {owner_id}: {e}")
        err_msg = str(e)
        if 'already registered' in err_msg.lower() or 'email_exists' in err_msg.lower():
            flash('An account with this email address already exists.', 'error')
        else:
            flash('An error occurred creating the staff account. Please try again.', 'error')
        
    return redirect(url_for('owner.staff'))

@owner_bp.route('/staff/<fs_id>/delete', methods=['POST'])
@require_role('owner')
def remove_staff_assignment(fs_id):
    owner_id = session.get('user_id')
    admin_db = get_admin_db() or get_db()
    try:
        fs_resp = admin_db.table('facility_staff').select('facility_id, staff_id').eq('id', fs_id).single().execute()
        if fs_resp.data:
            fac_id = fs_resp.data['facility_id']
            fac_resp = admin_db.table('facilities').select('owner_id, name').eq('id', fac_id).single().execute()
            if fac_resp.data and fac_resp.data['owner_id'] == owner_id:
                admin_db.table('facility_staff').delete().eq('id', fs_id).execute()
                flash('Staff assignment removed successfully.', 'success')
            else:
                flash('Unauthorized to remove this staff assignment.', 'error')
        else:
            flash('Staff assignment not found.', 'error')
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
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if not facility_id:
        flash('Please select a facility.', 'error')
        return redirect(url_for('owner.staff'))
        
    admin_db = get_admin_db() or get_db()
    try:
        # Verify ownership of target facility
        target_fac = admin_db.table('facilities').select('owner_id, name').eq('id', facility_id).single().execute()
        if not target_fac.data or target_fac.data['owner_id'] != owner_id:
            flash('Unauthorized facility selection.', 'error')
            return redirect(url_for('owner.staff'))
            
        # Verify ownership of current assignment
        fs_resp = admin_db.table('facility_staff').select('facility_id, staff_id').eq('id', fs_id).single().execute()
        if fs_resp.data:
            current_fac_id = fs_resp.data['facility_id']
            staff_id = fs_resp.data['staff_id']
            current_fac = admin_db.table('facilities').select('owner_id').eq('id', current_fac_id).single().execute()
            if current_fac.data and current_fac.data['owner_id'] == owner_id:
                # Update assignment facility
                admin_db.table('facility_staff').update({'facility_id': facility_id}).eq('id', fs_id).execute()
                
                # Update staff profile details (name, phone)
                prof_updates = {}
                if first_name:
                    prof_updates['first_name'] = first_name
                if last_name:
                    prof_updates['last_name'] = last_name
                prof_updates['phone'] = phone if phone else None
                
                if prof_updates and staff_id:
                    admin_db.table('profiles').update(prof_updates).eq('id', staff_id).execute()
                    
                flash('Staff assignment and details updated successfully.', 'success')
            else:
                flash('Unauthorized to edit this staff assignment.', 'error')
        else:
            flash('Staff assignment not found.', 'error')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error editing staff assignment {fs_id} by owner {owner_id}: {e}")
        flash('An error occurred updating staff assignment. Please try again.', 'error')
        
    return redirect(url_for('owner.staff'))
