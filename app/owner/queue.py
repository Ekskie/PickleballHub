from flask import request, redirect, url_for, session, render_template, flash, jsonify
from app.decorators import require_role
from app.db import get_db
from app.owner import owner_bp

# ── Queue Management ────────────────────────────────────────────────────────────
@owner_bp.route('/queue')
@require_role('owner')
def queue():
    owner_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        raw_facs = fac_resp.data or []
        # format like facility_staff response so the same template logic works
        assigned_facilities = [{'facility_id': f['id'], 'facilities': {'name': f['name']}} for f in raw_facs]
        fac_ids = [f['id'] for f in raw_facs]
        
        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            q_resp = db.table('court_queues').select(
                'id, facility_id, court_id, status, joined_at, estimated_wait_mins, profiles(first_name, last_name)'
            ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next']).order('joined_at', desc=False).execute()
            queues = q_resp.data or []
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading queue for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('owner/queue.html', facilities=assigned_facilities, courts=courts, queues=queues)

@owner_bp.route('/queue/update', methods=['POST'])
@require_role('owner')
def update_queue():
    # Support both AJAX JSON and Form submissions
    if request.is_json:
        data = request.get_json() or {}
        queue_id = data.get('queue_id')
        new_status = data.get('status')
        is_ajax = True
    else:
        queue_id = request.form.get('queue_id')
        new_status = request.form.get('status')
        is_ajax = False
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'completed', 'cancelled']:
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            if is_ajax:
                return jsonify({'success': True, 'message': 'Queue status updated successfully!'})
            flash('Queue status updated!', 'success')
        else:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Invalid status.'}), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error updating queue status for {queue_id}: {e}")
        if is_ajax:
            return jsonify({'success': False, 'message': 'An error occurred updating status.'}), 500
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.queue'))
