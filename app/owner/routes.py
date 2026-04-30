from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from app.decorators import require_role
from app import supabase_admin, supabase

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

def get_db():
    return supabase_admin or supabase

# ── Dashboard ──────────────────────────────────────────────────────────────────
@owner_bp.route('/dashboard')
# @require_role('owner')
def dashboard():
    return render_template('owner/dashboard.html')

# ── Facilities ─────────────────────────────────────────────────────────────────
@owner_bp.route('/facilities')
@require_role('owner')
def facilities():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, status, open_time, close_time, created_at'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        facilities_data = resp.data or []

        # For each facility, count its courts
        for f in facilities_data:
            court_resp = db.table('courts').select('id', count='exact').eq('facility_id', f['id']).execute()
            f['court_count'] = court_resp.count if court_resp.count is not None else 0
            facilities_list.append(f)
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')

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

    if not name:
        flash('Facility name is required.', 'error')
        return redirect(url_for('owner.facilities'))

    db = get_db()
    try:
        db.table('facilities').insert({
            'owner_id': owner_id,
            'name': name,
            'location': location,
            'description': desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
        }).execute()
        flash(f'Facility "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding facility: {e}', 'error')

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

    db = get_db()
    try:
        db.table('facilities').update({
            'name': name,
            'location': location,
            'description': desc,
            'status': status,
            'open_time': open_time,
            'close_time': close_time,
        }).eq('id', facility_id).eq('owner_id', owner_id).execute()
        flash(f'Facility updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating facility: {e}', 'error')

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
        flash(f'Error deleting facility: {e}', 'error')
    return redirect(url_for('owner.facilities'))


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
            'id, name, type, hourly_rate, status, facility_id, facilities(name)'
        ).eq('owner_id', owner_id).order('created_at', desc=True).execute()
        courts_list = court_resp.data or []
    except Exception as e:
        flash(f'Error loading courts: {e}', 'error')

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
    try:
        db.table('courts').insert({
            'owner_id': owner_id,
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
        }).execute()
        flash(f'Court "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding court: {e}', 'error')

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
    try:
        db.table('courts').update({
            'facility_id': facility_id,
            'name': name,
            'type': court_type,
            'hourly_rate': float(hourly_rate),
            'status': status,
        }).eq('id', court_id).eq('owner_id', owner_id).execute()
        flash('Court updated!', 'success')
    except Exception as e:
        flash(f'Error updating court: {e}', 'error')

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
        flash(f'Error deleting court: {e}', 'error')
    return redirect(url_for('owner.courts'))


# ── Events (on owner's courts) ─────────────────────────────────────────────────
@owner_bp.route('/events')
@require_role('owner')
def events():
    owner_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        # Get facilities owned by this owner
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]

        if fac_ids:
            ev_resp = db.table('events').select(
                'id, title, type, event_date, start_time, end_time, max_players, status, location_label, '
                'facilities(name), profiles!organizer_id(first_name, last_name)'
            ).in_('facility_id', fac_ids).order('event_date', desc=False).execute()
            events_list = ev_resp.data or []

            # Attach registration count
            for ev in events_list:
                reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', ev['id']).eq('status', 'registered').execute()
                ev['registered_count'] = reg_resp.count if reg_resp.count is not None else 0
    except Exception as e:
        flash(f'Error loading events: {e}', 'error')

    return render_template('owner/events.html', events=events_list)


# ── Create Event ───────────────────────────────────────────────────────────────
@owner_bp.route('/events/create', methods=['GET'])
@require_role('owner')
def create_event_page():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).eq('status', 'active').execute()
        facilities_list = fac_resp.data or []
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
    return render_template('owner/create_event.html', facilities=facilities_list)


@owner_bp.route('/events/create', methods=['POST'])
@require_role('owner')
def create_event():
    owner_id      = session.get('user_id')
    facility_id   = request.form.get('facility_id')
    court_ids     = request.form.getlist('court_ids')
    title         = request.form.get('title', '').strip()
    event_type    = request.form.get('type', 'social')
    description   = request.form.get('description', '').strip()
    event_date    = request.form.get('event_date')
    start_time    = request.form.get('start_time')
    end_time      = request.form.get('end_time')
    max_players   = request.form.get('max_players', 16)
    entry_fee     = request.form.get('entry_fee', 0)
    location_label = request.form.get('location_label', '').strip()

    if not all([title, facility_id, event_date, start_time, end_time]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('owner.create_event_page'))

    db = get_db()
    try:
        ev_resp = db.table('events').insert({
            'organizer_id': owner_id,
            'facility_id': facility_id,
            'title': title,
            'type': event_type,
            'description': description,
            'event_date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'max_players': int(max_players),
            'entry_fee': float(entry_fee),
            'location_label': location_label,
            'status': 'registration_open',
        }).execute()

        if ev_resp.data and court_ids:
            event_id = ev_resp.data[0]['id']
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()

        flash(f'Event "{title}" created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating event: {e}', 'error')

    return redirect(url_for('owner.events'))


# ── API: Courts by Facility (for JS fetch in create_event) ────────────────────
@owner_bp.route('/api/courts_by_facility/<facility_id>')
@require_role('owner')
def api_courts_by_facility(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('courts').select('id, name, type, hourly_rate').eq('facility_id', facility_id).eq('owner_id', owner_id).eq('status', 'active').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Staff ───────────────────────────────────────────────────────────────────────
@owner_bp.route('/staff')
@require_role('owner')
def staff():
    return render_template('owner/staff.html')

# ── Profile ─────────────────────────────────────────────────────────────────────
@owner_bp.route('/profile')
@require_role('owner')
def profile():
    return render_template('owner/profile.html')

# ── Notifications ───────────────────────────────────────────────────────────────
@owner_bp.route('/notifications')
@require_role('owner')
def notifications():
    return render_template('owner/notifications.html')

# ── Messages ────────────────────────────────────────────────────────────────────
@owner_bp.route('/messages')
@require_role('owner')
def messages():
    return render_template('owner/messages.html')

# ── Community ───────────────────────────────────────────────────────────────────
@owner_bp.route('/community')
@require_role('owner')
def community():
    return render_template('owner/community.html')
