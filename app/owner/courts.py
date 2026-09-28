import time
from flask import request, redirect, url_for, session, render_template, flash, jsonify
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

# ── Courts ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/courts')
@require_role('owner')
def courts():
    owner_id = session.get('user_id')
    db = get_admin_db()
    courts_list = []
    facilities_list = []
    try:
        # Owner's facilities for the dropdown
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).eq('status', 'active').execute()
        facilities_list = fac_resp.data or []

        # Courts with facility name joined
        court_resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, facility_id, image_url, facilities(name)'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        courts_list = court_resp.data or []
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading courts for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    # Computed Executive KPI Stats for Owner Dashboard
    total_courts = len(courts_list)
    active_courts = sum(1 for c in courts_list if c.get('status') == 'active')
    maint_courts = sum(1 for c in courts_list if c.get('status') == 'maintenance')
    indoor_courts = sum(1 for c in courts_list if c.get('type') == 'indoor')
    outdoor_courts = sum(1 for c in courts_list if c.get('type') == 'outdoor')
    rates = [float(c.get('hourly_rate') or 0) for c in courts_list if c.get('hourly_rate') is not None]
    avg_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
    min_rate = min(rates) if rates else 0.0
    max_rate = max(rates) if rates else 0.0

    stats = {
        'total': total_courts,
        'active': active_courts,
        'maintenance': maint_courts,
        'indoor': indoor_courts,
        'outdoor': outdoor_courts,
        'avg_rate': avg_rate,
        'min_rate': min_rate,
        'max_rate': max_rate,
        'facilities_count': len(facilities_list)
    }

    return render_template('owner/courts.html', courts=courts_list, facilities=facilities_list, stats=stats)


@owner_bp.route('/courts/add', methods=['POST'])
@require_role('owner')
def add_court():
    owner_id    = session.get('user_id')
    facility_id = request.form.get('facility_id')
    name        = request.form.get('name', '').strip()
    court_type  = request.form.get('type', 'indoor')
    hourly_rate = request.form.get('hourly_rate', 0)
    status      = request.form.get('status', 'active')

    if not name or not facility_id:
        flash('Court name and facility are required.', 'error')
        return redirect(url_for('owner.courts'))

    db = get_admin_db()

    # Check court capacity limit based on subscription tier
    from app.billing.tiers import check_feature_limit
    try:
        courts_count_res = db.table('courts').select('id', count='exact').eq('facility_id', facility_id).execute()
        current_courts_count = courts_count_res.count if courts_count_res and courts_count_res.count is not None else 0
        limit_check = check_feature_limit(owner_id, 'owner', 'max_courts_per_facility', current_count=current_courts_count, db=db)
        if not limit_check['allowed']:
            flash(limit_check['message'], 'warning')
            return redirect(url_for('owner.courts'))
    except Exception as lim_err:
        from flask import current_app
        current_app.logger.warning(f"[add_court] Error checking court limit: {lim_err}")

    # Handle court image upload
    image_url = None
    image_file = request.files.get('court_image')
    if image_file and image_file.filename:
        try:
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"court_{owner_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('court-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('court-images').get_public_url(filename)
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Court image upload error: {e}")
            flash('Warning: Court image could not be uploaded.', 'warning')

    try:
        db.table('courts').insert({
            'owner_id': owner_id,
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
            'image_url': image_url,
        }).execute()
        flash(f'Court "{name}" added successfully!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error adding court for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.courts'))


@owner_bp.route('/courts/<court_id>/edit', methods=['POST'])
@require_role('owner')
def edit_court(court_id):
    owner_id    = session.get('user_id')
    facility_id = request.form.get('facility_id')
    name        = request.form.get('name', '').strip()
    court_type  = request.form.get('type', 'indoor')
    hourly_rate = request.form.get('hourly_rate', 0)
    status      = request.form.get('status', 'active')

    db = get_admin_db()

    update_data = {
        'facility_id': facility_id,
        'name': name,
        'type': court_type,
        'hourly_rate': float(hourly_rate),
        'status': status,
    }

    # Handle court image upload
    image_file = request.files.get('court_image')
    if image_file and image_file.filename:
        try:
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"court_{court_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('court-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            update_data['image_url'] = db.storage.from_('court-images').get_public_url(filename)
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Court edit image upload error for court {court_id}: {e}")
            flash('Warning: Court image could not be uploaded.', 'warning')

    try:
        db.table('courts').update(update_data).eq('id', court_id).eq('owner_id', owner_id).execute()
        flash('Court updated!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error editing court {court_id} for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.courts'))


@owner_bp.route('/courts/<court_id>/delete', methods=['POST'])
@require_role('owner')
def delete_court(court_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    try:
        db.table('courts').delete().eq('id', court_id).eq('owner_id', owner_id).execute()
        flash('Court deleted.', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deleting court {court_id} for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('owner.courts'))


# ── Court Quick Status Toggle ─────────────────────────────────────────────────
@owner_bp.route('/courts/<court_id>/status', methods=['POST'])
@require_role('owner')
def toggle_court_status(court_id):
    owner_id = session.get('user_id')
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1

    if request.is_json:
        data = request.get_json() or {}
        new_status = data.get('status', 'active')
    else:
        new_status = request.form.get('status', 'active')

    if new_status not in ['active', 'maintenance', 'closed']:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid court status.'}), 400
        flash("Invalid court status.", "error")
        return redirect(url_for('owner.courts'))

    db = get_admin_db()
    try:
        # Verify ownership via facility
        c_resp = db.table('courts').select('id, name, facility_id').eq('id', court_id).single().execute()
        court = c_resp.data
        if not court:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Court not found.'}), 404
            flash("Court not found.", "error")
            return redirect(url_for('owner.courts'))

        fac_resp = db.table('facilities').select('id').eq('id', court['facility_id']).eq('owner_id', owner_id).execute()
        if not fac_resp.data:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Access denied.'}), 403
            flash("Access denied.", "error")
            return redirect(url_for('owner.courts'))

        db.table('courts').update({'status': new_status}).eq('id', court_id).execute()
        msg = f"Court \"{court.get('name', 'Court')}\" is now {new_status.title()}."
        if is_ajax:
            return jsonify({'success': True, 'message': msg, 'status': new_status, 'court_id': court_id})
        flash(msg, "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error toggling court status for court {court_id}: {e}")
        if is_ajax:
            return jsonify({'success': False, 'message': 'An error occurred updating status.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.courts'))
