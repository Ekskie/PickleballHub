from flask import request, redirect, url_for, session, render_template, flash, jsonify, current_app
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp

VALID_QUEUE_STATUSES = {'waiting', 'next', 'playing', 'completed', 'cancelled'}


def _get_queue_db():
    """Prefer admin client so RLS does not hide staff-created walk-in queue rows."""
    try:
        return get_admin_db() or get_db()
    except Exception:
        return get_db()


# ── Queue Management ────────────────────────────────────────────────────────────
@owner_bp.route('/queue')
@require_role('owner')
def queue():
    owner_id = session.get('user_id')
    db = _get_queue_db()

    assigned_facilities = []
    courts = []
    queues = []
    stats = {
        'waiting_count': 0,
        'next_count': 0,
        'playing_count': 0,
        'total_active': 0,
    }

    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        raw_facs = fac_resp.data or []
        assigned_facilities = [{'facility_id': f['id'], 'facilities': {'name': f['name']}} for f in raw_facs]
        fac_ids = [f['id'] for f in raw_facs]

        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []

            q_resp = db.table('court_queues').select(
                'id, facility_id, court_id, status, joined_at, estimated_wait_mins, '
                'player_id, guest_name, party_size, '
                'profiles(first_name, last_name, phone, avatar_url), courts(id, name)'
            ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next', 'playing']).order('joined_at', desc=False).execute()
            queues = q_resp.data or []

            status_order = {'playing': 0, 'next': 1, 'waiting': 2}
            queues.sort(key=lambda x: status_order.get(x.get('status'), 3))

            stats = {
                'waiting_count': sum(1 for q in queues if q.get('status') == 'waiting'),
                'next_count': sum(1 for q in queues if q.get('status') == 'next'),
                'playing_count': sum(1 for q in queues if q.get('status') == 'playing'),
                'total_active': len(queues),
            }

    except Exception as e:
        current_app.logger.error(f"Error loading queue for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return render_template(
        'owner/queue.html',
        facilities=assigned_facilities,
        courts=courts,
        queues=queues,
        stats=stats,
    )


@owner_bp.route('/queue/update', methods=['POST'])
@require_role('owner')
def update_queue():
    owner_id = session.get('user_id')

    # Support both AJAX JSON and Form submissions
    if request.is_json:
        data = request.get_json(silent=True) or {}
        queue_id = data.get('queue_id')
        new_status = data.get('status')
        has_court_key = 'court_id' in data
        court_id = data.get('court_id') or None
        is_ajax = True
    else:
        queue_id = request.form.get('queue_id')
        new_status = request.form.get('status')
        has_court_key = 'court_id' in request.form
        court_id = request.form.get('court_id') or None
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not queue_id:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Queue ID is required.'}), 400
        flash('Queue ID is required.', 'error')
        return redirect(url_for('owner.queue'))

    if new_status is not None and new_status != '' and new_status not in VALID_QUEUE_STATUSES:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid status.'}), 400
        flash('Invalid status.', 'error')
        return redirect(url_for('owner.queue'))

    if not new_status and not has_court_key:
        if is_ajax:
            return jsonify({'success': False, 'message': 'No update parameters provided.'}), 400
        flash('No update parameters provided.', 'error')
        return redirect(url_for('owner.queue'))

    db = _get_queue_db()
    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        fac_map = {str(f['id']): f.get('name') for f in (fac_resp.data or [])}
        if not fac_map:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Unauthorized.'}), 403
            flash('Unauthorized.', 'error')
            return redirect(url_for('owner.queue'))

        q_resp = db.table('court_queues').select(
            'id, facility_id, court_id, status, player_id, guest_name, reservation_id'
        ).eq('id', queue_id).limit(1).execute()
        q_row = q_resp.data[0] if (q_resp and q_resp.data) else None

        if not q_row or str(q_row.get('facility_id')) not in fac_map:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Queue entry not found or unauthorized.'}), 404
            flash('Queue entry not found or unauthorized.', 'error')
            return redirect(url_for('owner.queue'))

        update_payload = {}
        if new_status:
            update_payload['status'] = new_status

        assigned_court_name = None
        if has_court_key:
            if court_id:
                c_resp = db.table('courts').select('id, name, facility_id').eq('id', court_id).limit(1).execute()
                c_row = c_resp.data[0] if (c_resp and c_resp.data) else None
                if not c_row or str(c_row.get('facility_id')) != str(q_row.get('facility_id')):
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Invalid court selected for this facility.'}), 400
                    flash('Invalid court selected for this facility.', 'error')
                    return redirect(url_for('owner.queue'))
                assigned_court_name = c_row.get('name')
                update_payload['court_id'] = court_id
            else:
                update_payload['court_id'] = None

        db.table('court_queues').update(update_payload).eq('id', queue_id).execute()

        # Sync linked court reservation status when completed or cancelled
        reservation_id = q_row.get('reservation_id')
        if reservation_id and new_status in ('completed', 'cancelled'):
            try:
                db.table('court_reservations').update({'status': new_status}).eq('id', reservation_id).execute()
            except Exception:
                pass

        # Notify registered player when called next or placed on court
        player_id = q_row.get('player_id')
        if new_status in ('next', 'playing') and player_id:
            try:
                fac_name = fac_map.get(str(q_row.get('facility_id'))) or 'the facility'
                effective_court_id = update_payload.get('court_id', q_row.get('court_id'))
                if not assigned_court_name and effective_court_id:
                    c_lookup = db.table('courts').select('name').eq('id', effective_court_id).limit(1).execute()
                    if c_lookup and c_lookup.data:
                        assigned_court_name = c_lookup.data[0].get('name')

                court_suffix = f" ({assigned_court_name})" if assigned_court_name else ""
                if new_status == 'next':
                    notif_title = 'You are Up Next!'
                    notif_msg = f"Get ready! You are up next at {fac_name}{court_suffix}. Please head near the court."
                    notif_type = 'warning'
                else:
                    notif_title = 'Court Ready - Now Playing!'
                    notif_msg = f"Your court is ready at {fac_name}{court_suffix}. Please proceed to the court now!"
                    notif_type = 'success'

                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': notif_title,
                    'message': notif_msg,
                    'type': notif_type,
                    'link': url_for('player.queue'),
                }).execute()
            except Exception as notif_err:
                current_app.logger.warning(f"Failed to insert queue notification for {queue_id}: {notif_err}")

        if new_status:
            msg = 'Queue status updated successfully!'
        else:
            msg = f"Court assigned to {assigned_court_name}." if assigned_court_name else 'Court assignment cleared.'

        if is_ajax:
            return jsonify({
                'success': True,
                'message': msg,
                'status': new_status or q_row.get('status'),
                'court_id': update_payload.get('court_id', q_row.get('court_id')),
                'court_name': assigned_court_name,
            })
        flash(msg, 'success')
    except Exception as e:
        current_app.logger.error(f"Error updating queue status for {queue_id}: {e}")
        if is_ajax:
            return jsonify({'success': False, 'message': 'An error occurred updating status.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.queue'))
