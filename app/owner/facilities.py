import time
from flask import request, redirect, url_for, session, render_template, flash
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

import json
import re

AMENITIES_REGEX = re.compile(r'<!--AMENITIES:(.*?)-->')

def extract_amenities(facility):
    """Extract list of amenities from JSON column or embedded HTML comment in description."""
    if facility.get('amenities') and isinstance(facility.get('amenities'), list):
        return facility['amenities']
    desc = facility.get('description') or ''
    match = AMENITIES_REGEX.search(desc)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return []

def clean_description(desc):
    """Return user-facing description stripped of internal meta comments."""
    if not desc:
        return ''
    return AMENITIES_REGEX.sub('', desc).strip()

# ── Facilities ─────────────────────────────────────────────────────────────────
@owner_bp.route('/facilities')
@require_role('owner')
def facilities():
    owner_id = session.get('user_id')
    db = get_admin_db()
    facilities_list = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, status, open_time, close_time, slot_duration_minutes, created_at, kyc_status, kyc_document_url, latitude, longitude, image_url'
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
                f['amenities'] = extract_amenities(f)
                f['display_description'] = clean_description(f.get('description'))
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
    slot_duration = request.form.get('slot_duration_minutes', '60')
    latitude  = request.form.get('latitude')
    longitude = request.form.get('longitude')
    amenities = request.form.getlist('amenities')

    if not name:
        flash('Facility name is required.', 'error')
        return redirect(url_for('owner.facilities'))

    db = get_admin_db()

    # Check facility limit based on subscription tier
    from app.billing.tiers import check_feature_limit
    try:
        fac_count_res = db.table('facilities').select('id', count='exact').eq('owner_id', owner_id).execute()
        current_fac_count = fac_count_res.count if fac_count_res and fac_count_res.count is not None else 0
        limit_check = check_feature_limit(owner_id, 'owner', 'max_facilities', current_count=current_fac_count, db=db)
        if not limit_check['allowed']:
            flash(limit_check['message'], 'warning')
            return redirect(url_for('owner.facilities'))
    except Exception as lim_err:
        current_app.logger.warning(f"[add_facility] Error checking tier limit: {lim_err}")

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

    # Handle direct KYC document upload during creation (TCT/OCT & Business Permit)
    kyc_status = 'unverified'
    kyc_document_url = None
    kyc_tct_file    = request.files.get('kyc_tct')
    kyc_permit_file = request.files.get('kyc_permit')
    legacy_kyc_file = request.files.get('kyc_document')

    tct_url, permit_url = None, None
    from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE
    from datetime import datetime, timezone

    if kyc_tct_file and kyc_tct_file.filename:
        t_url, t_err = validate_and_upload(
            db, kyc_tct_file, bucket='kyc-documents', prefix='tct_oct',
            owner_id=owner_id, allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not t_err and t_url:
            tct_url = t_url

    if kyc_permit_file and kyc_permit_file.filename:
        p_url, p_err = validate_and_upload(
            db, kyc_permit_file, bucket='kyc-documents', prefix='biz_permit',
            owner_id=owner_id, allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not p_err and p_url:
            permit_url = p_url

    if legacy_kyc_file and legacy_kyc_file.filename and not (tct_url or permit_url):
        l_url, l_err = validate_and_upload(
            db, legacy_kyc_file, bucket='kyc-documents', prefix='kyc',
            owner_id=owner_id, allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not l_err and l_url:
            permit_url = l_url

    if tct_url or permit_url:
        kyc_document_url = json.dumps({
            'tct_url': tct_url,
            'tct_filename': kyc_tct_file.filename if kyc_tct_file else '',
            'permit_url': permit_url,
            'permit_filename': kyc_permit_file.filename if kyc_permit_file else (legacy_kyc_file.filename if legacy_kyc_file else ''),
            'submitted_at': datetime.now(timezone.utc).isoformat()
        })
        kyc_status = 'pending_approval'

    # Embed amenities safely in description for seamless persistence
    clean_desc = clean_description(desc)
    final_desc = (clean_desc + f"\n<!--AMENITIES:{json.dumps(amenities)}-->") if amenities else clean_desc

    try:
        duration_val = int(slot_duration) if str(slot_duration).isdigit() else 60
        insert_payload = {
            'owner_id': owner_id,
            'name': name,
            'location': location,
            'description': final_desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
            'slot_duration_minutes': duration_val,
            'kyc_status': kyc_status,
            'kyc_document_url': kyc_document_url,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
            'image_url': image_url,
        }
        db.table('facilities').insert(insert_payload).execute()
        
        msg = f'Facility "{name}" registered successfully!'
        if kyc_status == 'pending_approval':
            msg += ' KYC verification document submitted for admin approval.'
        flash(msg, 'success')
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
    slot_duration = request.form.get('slot_duration_minutes', '60')
    latitude   = request.form.get('latitude')
    longitude  = request.form.get('longitude')
    amenities  = request.form.getlist('amenities')

    db = get_admin_db()

    duration_val = int(slot_duration) if str(slot_duration).isdigit() else 60
    clean_desc = clean_description(desc)
    final_desc = (clean_desc + f"\n<!--AMENITIES:{json.dumps(amenities)}-->") if amenities else clean_desc

    update_data = {
        'name': name,
        'location': location,
        'description': final_desc,
        'status': status,
        'open_time': open_time,
        'close_time': close_time,
        'slot_duration_minutes': duration_val,
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

    # Handle KYC document upload if provided
    kyc_file = request.files.get('kyc_document')
    if kyc_file and kyc_file.filename:
        try:
            ext = kyc_file.filename.split('.')[-1].lower()
            filename = f"kyc_{facility_id}_{int(time.time())}.{ext}"
            file_bytes = kyc_file.read()
            db.storage.from_('kyc-documents').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": kyc_file.content_type}
            )
            update_data['kyc_document_url'] = db.storage.from_('kyc-documents').get_public_url(filename)
            update_data['kyc_status'] = 'pending_approval'
        except Exception as kyc_err:
            from flask import current_app
            current_app.logger.error(f"KYC upload error on edit for facility {facility_id}: {kyc_err}")
            flash('Warning: KYC document could not be uploaded.', 'warning')

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
    db = get_admin_db()
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
    db = get_admin_db()
    
    # Check if facility belongs to owner
    fac_resp = db.table('facilities').select('id, kyc_document_url').eq('id', facility_id).eq('owner_id', owner_id).single().execute()
    if not fac_resp.data:
        flash("Facility not found or unauthorized.", "error")
        return redirect(url_for('owner.facilities'))

    current_kyc_data = {}
    existing_raw = fac_resp.data.get('kyc_document_url') or ''
    if existing_raw.startswith('{'):
        try:
            current_kyc_data = json.loads(existing_raw)
        except Exception:
            pass
    elif existing_raw:
        current_kyc_data = {'legacy_url': existing_raw}

    tct_file    = request.files.get('kyc_tct')
    permit_file = request.files.get('kyc_permit')
    legacy_file = request.files.get('kyc_document')

    if not (tct_file and tct_file.filename) and not (permit_file and permit_file.filename) and not (legacy_file and legacy_file.filename):
        flash("Please select at least one document (TCT/OCT or Business Permit) to upload.", "error")
        return redirect(url_for('owner.facilities'))

    from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE
    from datetime import datetime, timezone

    if tct_file and tct_file.filename:
        url, err = validate_and_upload(
            db, tct_file, bucket='kyc-documents',
            prefix=f'tct_oct_{facility_id}', owner_id=owner_id,
            allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not err and url:
            current_kyc_data['tct_url'] = url
            current_kyc_data['tct_filename'] = tct_file.filename
        elif err:
            flash(f"TCT/OCT upload warning: {err}", "warning")

    if permit_file and permit_file.filename:
        url, err = validate_and_upload(
            db, permit_file, bucket='kyc-documents',
            prefix=f'biz_permit_{facility_id}', owner_id=owner_id,
            allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not err and url:
            current_kyc_data['permit_url'] = url
            current_kyc_data['permit_filename'] = permit_file.filename
        elif err:
            flash(f"Business Permit upload warning: {err}", "warning")

    if legacy_file and legacy_file.filename and not (permit_file and permit_file.filename):
        url, err = validate_and_upload(
            db, legacy_file, bucket='kyc-documents',
            prefix=f'biz_permit_{facility_id}', owner_id=owner_id,
            allowed_exts=ALLOWED_DOC_EXTENSIONS, max_size=MAX_DOC_SIZE
        )
        if not err and url:
            current_kyc_data['permit_url'] = url
            current_kyc_data['permit_filename'] = legacy_file.filename

    current_kyc_data['submitted_at'] = datetime.now(timezone.utc).isoformat()
    try:
        db.table('facilities').update({
            'kyc_status': 'pending_approval',
            'kyc_document_url': json.dumps(current_kyc_data)
        }).eq('id', facility_id).execute()
        flash("KYC verification documents uploaded successfully. Status is now pending approval.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"KYC upload error for facility {facility_id}: {e}")
        flash('An error occurred updating KYC status. Please try again.', 'error')

    return redirect(url_for('owner.facilities'))
