import time
from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db
from app.owner import owner_bp

# ── Facilities ─────────────────────────────────────────────────────────────────
@owner_bp.route('/facilities')
@require_role('owner')
def facilities():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, status, open_time, close_time, created_at, kyc_status, latitude, longitude, image_url'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        facilities_data = resp.data or []

        # Optimized N+1 court counts
        if facilities_data:
            fac_ids = [f['id'] for f in facilities_data]
            court_resp = db.table('courts').select('id, facility_id').in_('facility_id', fac_ids).execute()
            courts_data = court_resp.data or []
            
            from collections import Counter
            court_counts = Counter(c['facility_id'] for c in courts_data)
            
            for f in facilities_data:
                f['court_count'] = court_counts[f['id']]
                facilities_list.append(f)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading facilities for owner {owner_id}: {e}")
        flash('An error occurred loading facilities. Please try again.', 'error')

    return render_template('owner/facilities.html', facilities=facilities_list)


@owner_bp.route('/facilities/add', methods=['POST'])
@require_role('owner')
def add_facility():
    owner_id  = session.get('user_id')
    name      = request.form.get('name', '').strip()
    location  = request.form.get('location', '').strip()
    desc      = request.form.get('description', '').strip()
    status    = request.form.get('status', 'active')
    open_time = request.form.get('open_time', '08:00')
    close_time = request.form.get('close_time', '21:00')
    latitude  = request.form.get('latitude')
    longitude = request.form.get('longitude')

    if not name:
        flash('Facility name is required.', 'error')
        return redirect(url_for('owner.facilities'))

    db = get_db()

    # Handle image upload
    image_url = None
    image_file = request.files.get('facility_image')
    if image_file and image_file.filename:
        from app.upload_utils import validate_and_upload
        url, err = validate_and_upload(db, image_file, bucket='facility-images', prefix='facility', owner_id=owner_id)
        if err:
            flash(f'Warning: {err}', 'warning')
        else:
            image_url = url

    try:
        db.table('facilities').insert({
            'owner_id': owner_id,
            'name': name,
            'location': location,
            'description': desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
            'image_url': image_url,
        }).execute()
        flash(f'Facility "{name}" added successfully!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error adding facility for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.facilities'))


@owner_bp.route('/facilities/<facility_id>/edit', methods=['POST'])
@require_role('owner')
def edit_facility(facility_id):
    owner_id   = session.get('user_id')
    name       = request.form.get('name', '').strip()
    location   = request.form.get('location', '').strip()
    desc       = request.form.get('description', '').strip()
    status     = request.form.get('status', 'active')
    open_time  = request.form.get('open_time', '08:00')
    close_time = request.form.get('close_time', '21:00')
    latitude   = request.form.get('latitude')
    longitude  = request.form.get('longitude')

    db = get_db()

    update_data = {
        'name': name,
        'location': location,
        'description': desc,
        'status': status,
        'open_time': open_time,
        'close_time': close_time,
        'latitude': float(latitude) if latitude else None,
        'longitude': float(longitude) if longitude else None,
    }

    # Handle image upload
    image_file = request.files.get('facility_image')
    if image_file and image_file.filename:
        try:
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            filename = f"facility_{facility_id}_{int(time.time())}.{ext}"
            file_bytes = image_file.read()
            db.storage.from_('facility-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            update_data['image_url'] = db.storage.from_('facility-images').get_public_url(filename)
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Facility image upload error for facility {facility_id}: {e}")
            flash('Warning: Image could not be uploaded.', 'warning')

    try:
        db.table('facilities').update(update_data).eq('id', facility_id).eq('owner_id', owner_id).execute()
        flash(f'Facility updated successfully!', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating facility {facility_id} for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.facilities'))


@owner_bp.route('/facilities/<facility_id>/delete', methods=['POST'])
@require_role('owner')
def delete_facility(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        db.table('facilities').delete().eq('id', facility_id).eq('owner_id', owner_id).execute()
        flash('Facility deleted.', 'success')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error deleting facility {facility_id} for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('owner.facilities'))


@owner_bp.route('/facilities/<facility_id>/kyc', methods=['POST'])
@require_role('owner')
def kyc_upload(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    # Check if facility belongs to owner
    fac_resp = db.table('facilities').select('id').eq('id', facility_id).eq('owner_id', owner_id).single().execute()
    if not fac_resp.data:
        flash("Facility not found or unauthorized.", "error")
        return redirect(url_for('owner.facilities'))
        
    doc_file = request.files.get('kyc_document')
    if not doc_file or not doc_file.filename:
        flash("Please select a document to upload.", "error")
        return redirect(url_for('owner.facilities'))
        
    try:
        ext = doc_file.filename.split('.')[-1]
        filename = f"{facility_id}_{int(time.time())}.{ext}"
        file_bytes = doc_file.read()
        
        # Upload to kyc-documents bucket
        db.storage.from_('kyc-documents').upload(
            file=file_bytes,
            path=filename,
            file_options={"content-type": doc_file.content_type}
        )
        
        doc_url = db.storage.from_('kyc-documents').get_public_url(filename)
        
        db.table('facilities').update({
            'kyc_status': 'pending_approval',
            'kyc_document_url': doc_url
        }).eq('id', facility_id).execute()
        
        flash("KYC document uploaded successfully. Status is now pending approval.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"KYC upload error for facility {facility_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.facilities'))
