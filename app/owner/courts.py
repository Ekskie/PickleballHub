import time
from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db
from app.owner import owner_bp

# ── Courts ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/courts')
@require_role('owner')
def courts():
    owner_id = session.get('user_id')
    db = get_db()
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

    return render_template('owner/courts.html', courts=courts_list, facilities=facilities_list)


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

    db = get_db()

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

    db = get_db()

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
    db = get_db()
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
    new_status = request.form.get('status', 'active')
    if new_status not in ['active', 'maintenance', 'closed']:
        flash("Invalid court status.", "error")
        return redirect(url_for('owner.courts'))

    db = get_db()
    try:
        # Verify ownership via facility
        c_resp = db.table('courts').select('id, facility_id').eq('id', court_id).single().execute()
        court = c_resp.data
        if not court:
            flash("Court not found.", "error")
            return redirect(url_for('owner.courts'))

        fac_resp = db.table('facilities').select('id').eq('id', court['facility_id']).eq('owner_id', owner_id).execute()
        if not fac_resp.data:
            flash("Access denied.", "error")
            return redirect(url_for('owner.courts'))

        db.table('courts').update({'status': new_status}).eq('id', court_id).execute()
        flash(f"Court status set to '{new_status.title()}'.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error toggling court status for court {court_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.courts'))
