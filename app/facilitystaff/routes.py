from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))
from datetime import datetime, timedelta, timezone

from flask import g
import os
from supabase import create_client

_cached_db = None

def get_db():
    global _cached_db
    if _cached_db is None:
        import os
        import httpx
        from supabase import create_client, ClientOptions
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        if url and key:
            http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
            options = ClientOptions(httpx_client=http_client)
            _cached_db = create_client(url, key, options=options)
    return _cached_db


facilitystaff_bp = Blueprint('facilitystaff', __name__, url_prefix='/facilitystaff')

@facilitystaff_bp.route('/dashboard')
@require_role('facilitystaff')
def dashboard():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    court_status_list = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Get courts
            c_resp = db.table('courts').select('*').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # Get active queues
            queues = get_staff_processed_queues(db, fac_ids)
            
            # Calculate live court status
            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            
            # Fetch today's reservations for these courts
            res_resp = db.table('court_reservations').select('*').in_('court_id', [c['id'] for c in courts]).eq('date', today_str).in_('status', ['confirmed', 'completed']).execute()
            reservations = res_resp.data or []
            
            # For each court, determine if it is currently in use
            for c in courts:
                status = 'Available'
                status_color = 'positive'
                sub_text = 'Ready'
                
                if c['status'] == 'maintenance':
                    status = 'Maintenance'
                    status_color = 'warning'
                    sub_text = 'Unavailable'
                else:
                    # Check reservations
                    for r in reservations:
                        if r['court_id'] == c['id'] and r['status'] == 'confirmed':
                            start_time_str = f"{today_str} {r['start_time']}"
                            end_time_str = f"{today_str} {r['end_time']}"
                            try:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            except ValueError:
                                start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                                end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            
                            if start_dt <= now <= end_dt:
                                status = 'In Use'
                                status_color = 'negative'
                                rem_mins = int((end_dt - now).total_seconds() / 60)
                                sub_text = f"Ends in {rem_mins}m"
                                break
                            elif start_dt > now:
                                # Next upcoming
                                diff_mins = int((start_dt - now).total_seconds() / 60)
                                if status == 'Available' and diff_mins < 60:
                                    sub_text = f"Next in {diff_mins}m"
                                    
                court_status_list.append({
                    'name': c['name'],
                    'status': status,
                    'color': status_color,
                    'sub_text': sub_text
                })
                
    except Exception as e:
        flash(f'Error loading dashboard: {e}', 'error')
        
    return render_template('facilitystaff/dashboard.html', court_status_list=court_status_list, queues=queues)

def get_staff_processed_queues(db, fac_ids):
    if not fac_ids:
        return []
    try:
        resp = db.table('court_queues').select(
            'id, facility_id, court_id, status, estimated_wait_mins, joined_at, player_id, profiles(first_name, last_name), court_reservations!inner(date, start_time, end_time)'
        ).in_('facility_id', fac_ids).in_('status', ['waiting', 'next', 'playing']).order('joined_at').execute()
        raw_queues = resp.data or []
    except Exception as e:
        print("Error fetching queues:", e)
        return []
        
    today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
    now = datetime.now(PH_TZ)
    queues = []
    
    for q in raw_queues:
        res = q.get('court_reservations')
        if not res or res.get('date') != today_str:
            continue
            
        start_time_str = f"{today_str} {res.get('start_time')}"
        end_time_str = f"{today_str} {res.get('end_time')}"
        try:
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
        except ValueError:
            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)

        if q['status'] == 'playing' and now > (end_dt + timedelta(minutes=15)):
            try:
                db.table('court_queues').update({'status': 'completed'}).eq('id', q['id']).execute()
            except Exception:
                pass
            continue
            
        if q['status'] in ['waiting', 'next']:
            wait_mins = int((start_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, wait_mins)
            q['time_type'] = 'Wait'
            q['target_time'] = start_dt.isoformat()
        elif q['status'] == 'playing':
            rem_mins = int((end_dt - now).total_seconds() / 60)
            q['estimated_wait_mins'] = max(0, rem_mins)
            q['time_type'] = 'Remaining'
            q['target_time'] = end_dt.isoformat()
            
        queues.append(q)

    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), x.get('court_reservations', {}).get('start_time', '')))
    return queues


@facilitystaff_bp.route('/queue')
@require_role('facilitystaff')
def queue():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        # 1. Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # 2. Get courts for these facilities
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # 3. Get active queue items
            queues = get_staff_processed_queues(db, fac_ids)
            
    except Exception as e:
        flash(f'Error loading queues: {e}', 'error')
        
    return render_template('facilitystaff/queue.html', facilities=assigned_facilities, courts=courts, queues=queues)

@facilitystaff_bp.route('/queue/partial')
@require_role('facilitystaff')
def queue_partial():
    staff_id = session.get('user_id')
    db = get_db()
    
    assigned_facilities = []
    courts = []
    queues = []
    
    try:
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            queues = get_staff_processed_queues(db, fac_ids)
            
    except Exception as e:
        pass
        
    return render_template('facilitystaff/partials/queue_content.html', facilities=assigned_facilities, courts=courts, queues=queues)


@facilitystaff_bp.route('/queue/update', methods=['POST'])
@require_role('facilitystaff')
def update_queue():
    queue_id = request.form.get('queue_id')
    new_status = request.form.get('status')
    
    db = get_db()
    try:
        if new_status in ['waiting', 'next', 'playing', 'completed', 'cancelled']:
            q_resp = db.table('court_queues').select('player_id').eq('id', queue_id).single().execute()
            player_id = q_resp.data['player_id'] if q_resp.data else None
            
            db.table('court_queues').update({'status': new_status}).eq('id', queue_id).execute()
            
            # Send notification if 'next'
            if new_status == 'next' and player_id:
                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': 'You are up next!',
                    'message': 'Your turn is up next. Please head to your assigned court.',
                    'type': 'success',
                    'link': '/player/queue'
                }).execute()
                
            flash('Queue status updated!', 'success')
        else:
            flash('Invalid status.', 'error')
    except Exception as e:
        flash(f'Error updating queue: {e}', 'error')
        
    return redirect(request.referrer or url_for('facilitystaff.queue'))

@facilitystaff_bp.route('/schedule')
@require_role('facilitystaff')
def schedule():
    staff_id = session.get('user_id')
    db = get_db()
    
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
        
    courts = []
    reservations = []
    assigned_facilities = []
    
    try:
        # Get facilities assigned to this staff
        fs_resp = db.table('facility_staff').select('facility_id, facilities(name, open_time, close_time)').eq('staff_id', staff_id).execute()
        assigned_facilities = fs_resp.data or []
        fac_ids = [f['facility_id'] for f in assigned_facilities]
        
        if fac_ids:
            # Get courts
            c_resp = db.table('courts').select('id, name, facility_id').in_('facility_id', fac_ids).execute()
            courts = c_resp.data or []
            
            # Get reservations for this date
            r_resp = db.table('court_reservations').select(
                'id, court_id, start_time, end_time, status, profiles(first_name, last_name)'
            ).in_('facility_id', fac_ids).eq('date', date_str).in_('status', ['confirmed', 'completed']).order('start_time').execute()
            reservations = r_resp.data or []
            
    except Exception as e:
        flash(f'Error loading schedule: {e}', 'error')
        
    return render_template('facilitystaff/schedule.html', 
                           date=date_str, 
                           facilities=assigned_facilities, 
                           courts=courts, 
                           reservations=reservations)

@facilitystaff_bp.route('/walkin', methods=['GET', 'POST'])
@require_role('facilitystaff')
def walkin():
    staff_id = session.get('user_id')
    db = get_db()

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        guest_phone = request.form.get('guest_phone', '').strip()
        court_id = request.form.get('court_id')
        duration = float(request.form.get('duration', 1))
        party_size = int(request.form.get('party_size', 1))
        payment_method = request.form.get('payment_method', 'cash')
        gcash_ref = request.form.get('gcash_ref', '').strip() or None

        if not guest_name or not court_id:
            flash("Guest Name and Court are required.", "error")
            return redirect(url_for('facilitystaff.walkin'))

        try:
            # 1. Get Court Info
            c_resp = db.table('courts').select('facility_id, hourly_rate, name').eq('id', court_id).single().execute()
            court_info = c_resp.data
            total_amount = court_info['hourly_rate'] * duration

            now = datetime.now(PH_TZ)
            today_str = now.strftime('%Y-%m-%d')
            start_time = now.strftime('%H:%M:%S')
            end_time = (now + timedelta(hours=duration)).strftime('%H:%M:%S')

            # 2. Create Reservation (include gcash_ref for payment reference)
            res_data = {
                'court_id': court_id,
                'facility_id': court_info['facility_id'],
                'date': today_str,
                'start_time': start_time,
                'end_time': end_time,
                'total_hours': duration,
                'hourly_rate': court_info['hourly_rate'],
                'total_amount': total_amount,
                'status': 'confirmed',
                'guest_name': guest_name,
                'guest_phone': guest_phone,
                'party_size': party_size,
            }
            if gcash_ref:
                res_data['gcash_ref'] = gcash_ref

            res_resp = db.table('court_reservations').insert(res_data).execute()
            new_res = res_resp.data[0]

            # 3. Queue status
            q_resp = db.table('court_queues').select('id').eq('court_id', court_id).eq('status', 'playing').execute()
            q_status = 'waiting' if q_resp.data else 'playing'

            # 4. Create Queue Entry
            db.table('court_queues').insert({
                'facility_id': court_info['facility_id'],
                'court_id': court_id,
                'status': q_status,
                'guest_name': guest_name,
                'party_size': party_size,
                'reservation_id': new_res['id'],
            }).execute()

            # 5. Store receipt data in session
            session['walkin_receipt'] = {
                'reservation_id': new_res['id'],
                'guest_name': guest_name,
                'guest_phone': guest_phone or '—',
                'court_name': court_info['name'],
                'date': today_str,
                'start_time': start_time[:5],
                'end_time': end_time[:5],
                'duration': duration,
                'party_size': party_size,
                'hourly_rate': court_info['hourly_rate'],
                'total_amount': total_amount,
                'payment_method': payment_method,
                'gcash_ref': gcash_ref or '—',
                'queue_status': q_status,
            }

            return redirect(url_for('facilitystaff.walkin_receipt'))

        except Exception as e:
            flash(f"Error registering walk-in: {e}", "error")
            return redirect(url_for('facilitystaff.walkin'))

    # GET: Fetch available courts
    courts = []
    try:
        fs_resp = db.table('facility_staff').select('facility_id').eq('staff_id', staff_id).execute()
        fac_ids = [f['facility_id'] for f in fs_resp.data or []]
        if fac_ids:
            c_resp = db.table('courts').select('id, name, hourly_rate').in_('facility_id', fac_ids).eq('status', 'active').execute()
            courts = c_resp.data or []
    except Exception as e:
        flash(f"Error loading courts: {e}", "error")

    return render_template('facilitystaff/walkin.html', courts=courts)


@facilitystaff_bp.route('/walkin/receipt')
@require_role('facilitystaff')
def walkin_receipt():
    receipt = session.pop('walkin_receipt', None)
    if not receipt:
        flash("No recent walk-in found.", "warning")
        return redirect(url_for('facilitystaff.walkin'))
    return render_template('facilitystaff/walkin_receipt.html', receipt=receipt)

@facilitystaff_bp.route('/profile', methods=['GET', 'POST'])
@require_role('facilitystaff')
def profile():
    user_id = session.get('user_id')
    db = get_db()
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        avatar_file = request.files.get('avatar')
        avatar_url = None
        if avatar_file and avatar_file.filename:
            try:
                from app.decorators import upload_avatar
                avatar_url = upload_avatar(db, user_id, avatar_file)
            except Exception as e:
                flash(f"Warning: Avatar upload failed - {e}", "warning")
                
        try:
            update_data = {
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }
            if avatar_url:
                update_data['avatar_url'] = avatar_url
                
            db.table('profiles').update(update_data).eq('id', user_id).execute()
            
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['phone'] = phone
            if avatar_url:
                session['avatar_url'] = avatar_url
                
            flash("Profile updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('facilitystaff.profile'))
    return render_template('facilitystaff/profile.html')

@facilitystaff_bp.route('/notifications')
@require_role('facilitystaff')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('facilitystaff/notifications.html', notifications=notifs)

@facilitystaff_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('facilitystaff')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@facilitystaff_bp.route('/messages')
@require_role('facilitystaff')
def messages():
    return render_template('facilitystaff/messages.html')

@facilitystaff_bp.route('/community')
@require_role('facilitystaff')
def community():
    return render_template('facilitystaff/community.html')

