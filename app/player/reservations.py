from flask import render_template, request, redirect, url_for, session, flash, jsonify, g
from app.decorators import require_role
from datetime import datetime, timezone, timedelta
from app.db import get_db, get_admin_db
from app.player import player_bp
from app.player.routes import PH_TZ

def format_time_12h(time_val):
    if not time_val:
        return ''
    s = str(time_val).strip()
    try:
        parts = s.split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        ampm = 'AM' if (h < 12 or h == 24) else 'PM'
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        min_str = f":{m:02d}" if m > 0 else ":00"
        return f"{h12}{min_str} {ampm}"
    except Exception:
        return s


@player_bp.route('/reservation')
@require_role('player')
def reservation():
    admin_db = get_admin_db()
    facilities = []
    preselected_facility_id = request.args.get('facility_id', '').strip()
    preselected_court_id = request.args.get('court_id', '').strip()
    try:
        resp = admin_db.table('facilities').select(
            'id, name, location, description, open_time, close_time, slot_duration_minutes, kyc_status, image_url, latitude, longitude, owner_id, owner:profiles!owner_id(id, first_name, last_name, avatar_url, phone, role)'
        ).eq('status', 'active').order('name').execute()
        facilities = resp.data or []

        # Fallback to direct profiles query if PostgREST join is missing or null
        owner_ids = list({f['owner_id'] for f in facilities if f.get('owner_id')})
        prof_map = {}
        if owner_ids:
            try:
                prof_resp = admin_db.table('profiles').select('id, first_name, last_name, avatar_url, phone, role').in_('id', owner_ids).execute()
                prof_map = {p['id']: p for p in (prof_resp.data or []) if p.get('id')}
            except Exception as pe:
                print(f"[reservation] error fetching fallback owner profiles: {pe}")

        fac_ids = [f['id'] for f in facilities if f.get('id')]
        staff_by_fac = {}
        courts_by_fac = {}
        if fac_ids:
            try:
                staff_resp = admin_db.table('facility_staff').select(
                    'facility_id, staff_id, staff:profiles!staff_id(id, first_name, last_name, avatar_url, phone, role)'
                ).in_('facility_id', fac_ids).execute()

                for item in (staff_resp.data or []):
                    fid = item.get('facility_id')
                    st = item.get('staff')
                    if fid and st:
                        st_first = st.get('first_name') or 'Staff'
                        st_last = st.get('last_name') or ''
                        st['full_name'] = f"{st_first} {st_last}".strip()
                        st['initials'] = ((st_first[0] if st_first else '') + (st_last[0] if st_last else '')).upper() or 'ST'
                        staff_by_fac.setdefault(fid, []).append(st)
            except Exception as se:
                print(f"[reservation] error fetching staff: {se}")

            try:
                courts_resp = admin_db.table('courts').select('id, facility_id, name, type, hourly_rate').in_('facility_id', fac_ids).eq('status', 'active').execute()
                for c in (courts_resp.data or []):
                    fid = c.get('facility_id')
                    if fid:
                        courts_by_fac.setdefault(fid, []).append(c)
            except Exception as ce:
                print(f"[reservation] error fetching courts: {ce}")

        for f in facilities:
            # Format times to friendly 12h
            f['open_time_12'] = format_time_12h(f.get('open_time') or '08:00')
            close_raw = f.get('close_time') or '21:00'
            if str(close_raw).startswith('00:00'):
                f['close_time_12'] = '12:00 AM (Midnight)'
            else:
                f['close_time_12'] = format_time_12h(close_raw)

            # Courts summary for card tags
            f_courts = courts_by_fac.get(f['id'], [])
            f['courts_count'] = len(f_courts)
            types = sorted(list({(c.get('type') or 'outdoor').capitalize() for c in f_courts}))
            f['court_types_str'] = " & ".join(types) if types else "Outdoor"
            rates = [float(c.get('hourly_rate') or 0) for c in f_courts if c.get('hourly_rate') is not None]
            if rates:
                min_rate = min(rates)
                max_rate = max(rates)
                if min_rate == max_rate:
                    f['rate_display'] = f"₱{min_rate:.0f}/hr"
                else:
                    f['rate_display'] = f"₱{min_rate:.0f} – ₱{max_rate:.0f}/hr"
            else:
                f['rate_display'] = None

            # If owner is missing from join or lacks id, resolve from prof_map
            owner = f.get('owner')
            if not owner or not isinstance(owner, dict) or not owner.get('id'):
                oid = f.get('owner_id')
                if oid and oid in prof_map:
                    owner = dict(prof_map[oid])
                else:
                    owner = {}

            if owner and owner.get('id'):
                o_first = owner.get('first_name') or 'Facility'
                o_last = owner.get('last_name') or 'Owner'
                owner['full_name'] = f"{o_first} {o_last}".strip()
                owner['initials'] = ((o_first[0] if o_first else '') + (o_last[0] if o_last else '')).upper() or 'OW'
                f['owner'] = owner
            else:
                f['owner'] = None

            f['staff_members'] = staff_by_fac.get(f['id'], [])

    except Exception as e:
        print(f"[reservation] error: {e}")
        flash('An error occurred. Please try again.', 'error')

    # Fetch player's active and recent reservations for the floating status cart
    player_id = session.get('user_id')
    user_reservations = []
    if player_id:
        try:
            now = datetime.now(PH_TZ)
            r_resp = admin_db.table('court_reservations').select(
                'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
                'status, gcash_ref, created_at, '
                'courts(id, name, type, image_url), facilities(id, name, location)'
            ).eq('player_id', player_id).order('created_at', desc=True).limit(20).execute()
            
            raw_res = r_resp.data or []
            for r in raw_res:
                r['can_cancel'] = False
                status = r.get('status')
                
                # Derive display_status
                if status == 'pending_payment' and r.get('gcash_ref'):
                    r['display_status'] = 'pending_verification'
                elif status == 'pending_payment':
                    r['display_status'] = 'pending_payment'
                elif status == 'confirmed':
                    r['display_status'] = 'confirmed'
                elif status in ['cancelled', 'declined']:
                    r['display_status'] = 'cancelled'
                else:
                    r['display_status'] = status

                # Completion and cancellation check
                if status in ['pending_payment', 'confirmed']:
                    try:
                        start_time_str = f"{r['date']} {r['start_time']}"
                        end_time_str = f"{r['date']} {r['end_time']}"
                        try:
                            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                        except ValueError:
                            start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                            
                        if now >= end_dt:
                            admin_db.table('court_reservations').update({'status': 'completed'}).eq('id', r['id']).execute()
                            r['status'] = 'completed'
                            r['display_status'] = 'completed'
                        elif now < start_dt:
                            r['can_cancel'] = True
                    except Exception as e:
                        r['can_cancel'] = True

                r['start_time_12'] = format_time_12h(r.get('start_time'))
                r['end_time_12'] = format_time_12h(r.get('end_time'))
                user_reservations.append(r)
        except Exception as re:
            print(f"[reservation] error fetching user reservations: {re}")

    return render_template(
        'player/court_reservation.html',
        facilities=facilities,
        user_reservations=user_reservations,
        preselected_facility_id=preselected_facility_id,
        preselected_court_id=preselected_court_id,
        today_date=datetime.now(PH_TZ).strftime('%Y-%m-%d')
    )


@player_bp.route('/reservation/api/my-bookings')
@require_role('player')
def api_my_bookings():
    """Return JSON list of player's recent reservations for live floating cart drawer."""
    player_id = session.get('user_id')
    if not player_id:
        return jsonify([])
    admin_db = get_admin_db()
    try:
        r_resp = admin_db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
            'status, gcash_ref, created_at, '
            'courts(id, name, type, image_url), facilities(id, name, location)'
        ).eq('player_id', player_id).order('created_at', desc=True).limit(20).execute()
        
        raw = r_resp.data or []
        now = datetime.now(PH_TZ)
        for r in raw:
            r['can_cancel'] = False
            status = r.get('status')
            if status == 'pending_payment' and r.get('gcash_ref'):
                r['display_status'] = 'pending_verification'
            elif status == 'pending_payment':
                r['display_status'] = 'pending_payment'
            elif status == 'confirmed':
                r['display_status'] = 'confirmed'
            elif status in ['cancelled', 'declined']:
                r['display_status'] = 'cancelled'
            else:
                r['display_status'] = status

            if status in ['pending_payment', 'confirmed']:
                try:
                    start_time_str = f"{r['date']} {r['start_time']}"
                    end_time_str = f"{r['date']} {r['end_time']}"
                    try:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                    except ValueError:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                    if now >= end_dt:
                        admin_db.table('court_reservations').update({'status': 'completed'}).eq('id', r['id']).execute()
                        r['status'] = 'completed'
                        r['display_status'] = 'completed'
                    elif now < start_dt:
                        r['can_cancel'] = True
                except Exception:
                    r['can_cancel'] = True

            r['start_time_12'] = format_time_12h(r.get('start_time'))
            r['end_time_12'] = format_time_12h(r.get('end_time'))
        return jsonify(raw)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/api/courts')
@require_role('player')
def api_reservation_courts():
    facility_id = request.args.get('facility_id')
    if not facility_id:
        return jsonify([])
    db = get_db()
    try:
        resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, image_url'
        ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/api/slots')
@require_role('player')
def api_reservation_slots():
    """Return booked start_time values for a court on a given date."""
    court_id = request.args.get('court_id')
    date     = request.args.get('date')
    if not court_id or not date:
        return jsonify([])
    db = get_db()
    try:
        resp = db.table('court_reservations').select(
            'start_time, end_time'
        ).eq('court_id', court_id).eq('date', date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/api/facility_occupancy')
@require_role('player')
def api_facility_occupancy():
    """Return all active courts and their bookings for a facility on a given date."""
    facility_id = request.args.get('facility_id')
    date        = request.args.get('date')
    if not facility_id or not date:
        return jsonify({'courts': [], 'reservations': []})
    db = get_db()
    try:
        # Fetch active courts
        courts_resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, image_url'
        ).eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        courts = courts_resp.data or []
        
        court_ids = [c['id'] for c in courts]
        if not court_ids:
            return jsonify({'courts': [], 'reservations': []})
            
        # Fetch confirmed or pending bookings
        res_resp = db.table('court_reservations').select(
            'court_id, start_time, end_time'
        ).in_('court_id', court_ids).eq('date', date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        
        return jsonify({
            'courts': courts,
            'reservations': res_resp.data or []
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/api/facility_month_availability')
@require_role('player')
def api_facility_month_availability():
    """Return aggregated daily availability for an entire month for the custom interactive calendar."""
    facility_id = request.args.get('facility_id')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not facility_id or not year or not month:
        return jsonify({'error': 'Missing parameters'}), 400

    admin_db = get_admin_db()
    try:
        import calendar
        num_days = calendar.monthrange(year, month)[1]
        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{num_days:02d}"

        # Fetch facility info
        fac_resp = admin_db.table('facilities').select('id, name, open_time, close_time').eq('id', facility_id).single().execute()
        fac = fac_resp.data or {}
        
        open_time = str(fac.get('open_time') or '08:00')[:5]
        close_time = str(fac.get('close_time') or '21:00')[:5]
        
        open_h = int(open_time.split(':')[0])
        close_h = int(close_time.split(':')[0])
        if close_h == 0:
            close_h = 24
        operating_hours = max(1, close_h - open_h)

        # Fetch active courts
        courts_resp = admin_db.table('courts').select('id, name').eq('facility_id', facility_id).eq('status', 'active').execute()
        court_ids = [c['id'] for c in (courts_resp.data or [])]
        total_courts = len(court_ids)

        if total_courts == 0:
            days = {}
            for d in range(1, num_days + 1):
                d_str = f"{year:04d}-{month:02d}-{d:02d}"
                days[d_str] = {'status': 'full', 'remaining_slots': 0, 'total_slots': 0, 'booked_slots': 0}
            return jsonify({
                'success': True,
                'total_courts': 0,
                'days': days,
                'open_time_12': format_time_12h(open_time),
                'close_time_12': '12:00 AM (Midnight)' if close_time == '00:00' else format_time_12h(close_time)
            })

        total_court_slots_per_day = operating_hours * total_courts

        # Query all reservations in this month
        res_resp = admin_db.table('court_reservations').select(
            'court_id, date, start_time, end_time, total_hours'
        ).in_('court_id', court_ids).gte('date', start_date).lte('date', end_date).in_(
            'status', ['confirmed', 'pending_payment']
        ).execute()
        reservations = res_resp.data or []

        # Group bookings by date
        bookings_by_date = {}
        for r in reservations:
            d = r.get('date')
            if d:
                hrs = float(r.get('total_hours') or 1)
                bookings_by_date[d] = bookings_by_date.get(d, 0) + hrs

        days = {}
        for d in range(1, num_days + 1):
            d_str = f"{year:04d}-{month:02d}-{d:02d}"
            booked_slots = bookings_by_date.get(d_str, 0)
            remaining_slots = max(0, total_court_slots_per_day - booked_slots)
            
            if booked_slots == 0:
                status = 'available'
            elif remaining_slots == 0:
                status = 'full'
            elif remaining_slots <= total_court_slots_per_day * 0.35:
                status = 'limited'
            else:
                status = 'available'

            days[d_str] = {
                'status': status,
                'remaining_slots': int(remaining_slots),
                'total_slots': total_court_slots_per_day,
                'booked_slots': int(booked_slots)
            }

        return jsonify({
            'success': True,
            'year': year,
            'month': month,
            'total_courts': total_courts,
            'open_hour': open_h,
            'close_hour': close_h,
            'open_time_12': format_time_12h(open_time),
            'close_time_12': '12:00 AM (Midnight)' if close_time == '00:00' else format_time_12h(close_time),
            'days': days
        })
    except Exception as e:
        print(f"[facility_month_availability] error: {e}")
        return jsonify({'error': str(e)}), 500


@player_bp.route('/reservation/book', methods=['POST'])
@require_role('player')
def book_reservation():
    player_id   = session.get('user_id')
    court_id    = request.form.get('court_id')
    facility_id = request.form.get('facility_id')
    date        = request.form.get('date')
    start_time  = request.form.get('start_time')
    end_time    = request.form.get('end_time')
    total_hours = request.form.get('total_hours', 1)
    hourly_rate = request.form.get('hourly_rate', 0)
    total_amount = request.form.get('total_amount', 0)
    party_size  = request.form.get('party_size', 1)

    if not all([court_id, facility_id, date, start_time, end_time]):
        flash('Missing reservation details. Please try again.', 'error')
        return redirect(url_for('player.reservation'))

    db = get_db()
    try:
        # Check advance booking window limit based on player subscription tier
        from app.billing.tiers import check_feature_limit
        adv_check = check_feature_limit(player_id, 'player', 'advance_booking_days', target_date=date, db=db)
        if not adv_check['allowed']:
            flash(adv_check['message'], 'warning')
            return redirect(url_for('player.reservation'))

        # Check max active upcoming bookings limit
        try:
            active_bookings_res = db.table('court_reservations').select('id', count='exact')\
                .eq('player_id', player_id)\
                .gte('date', datetime.now(PH_TZ).strftime('%Y-%m-%d'))\
                .in_('status', ['confirmed', 'pending_payment'])\
                .execute()
            active_count = active_bookings_res.count if active_bookings_res and active_bookings_res.count is not None else 0
            active_check = check_feature_limit(player_id, 'player', 'max_active_bookings', current_count=active_count, db=db)
            if not active_check['allowed']:
                flash(active_check['message'], 'warning')
                return redirect(url_for('player.reservation'))
        except Exception as lim_e:
            pass

        # Check for overlapping reservation on this court
        overlap_resp = db.table('court_reservations').select('id')\
            .eq('court_id', court_id)\
            .eq('date', date)\
            .in_('status', ['confirmed', 'pending_payment'])\
            .lt('start_time', end_time)\
            .gt('end_time', start_time)\
            .execute()
            
        if overlap_resp.data:
            flash('This court is already reserved during the selected time slot. Please choose another time or court.', 'error')
            return redirect(url_for('player.reservation'))

        # Check if player already has another overlapping reservation (prevent double-booking)
        player_overlap = db.table('court_reservations').select('id')\
            .eq('player_id', player_id)\
            .eq('date', date)\
            .in_('status', ['confirmed', 'pending_payment'])\
            .lt('start_time', end_time)\
            .gt('end_time', start_time)\
            .execute()
            
        if player_overlap.data:
            flash('You already have another court reservation during this time slot.', 'error')
            return redirect(url_for('player.reservation'))

        resp = db.table('court_reservations').insert({
            'player_id':    player_id,
            'court_id':     court_id,
            'facility_id':  facility_id,
            'date':         date,
            'start_time':   start_time,
            'end_time':     end_time,
            'total_hours':  float(total_hours),
            'hourly_rate':  float(hourly_rate),
            'total_amount': float(total_amount),
            'party_size':   int(party_size),
            'status':       'pending_payment',
        }).execute()

        if resp.data:
            reservation_id = resp.data[0]['id']
            flash('Reservation created! Complete payment to confirm.', 'success')
            return redirect(url_for('player.payment', reservation_id=reservation_id))
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('player.reservation'))


@player_bp.route('/my-reservations')
@require_role('player')
def my_reservations():
    player_id = session.get('user_id')
    admin_db = get_admin_db()
    reservations = []
    try:
        resp = admin_db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
            'status, gcash_ref, created_at, '
            'courts(name, type, image_url), facilities(id, name, location, owner_id, owner:profiles!owner_id(id, first_name, last_name, avatar_url, phone))'
        ).eq('player_id', player_id).order('created_at', desc=True).execute()
        raw_reservations = resp.data or []
        
        # Fallback owner lookup
        missing_owner_ids = list({r.get('facilities', {}).get('owner_id') for r in raw_reservations if r.get('facilities') and r['facilities'].get('owner_id') and (not r['facilities'].get('owner') or not r['facilities']['owner'].get('id'))})
        if missing_owner_ids:
            try:
                prof_resp = admin_db.table('profiles').select('id, first_name, last_name, avatar_url, phone, role').in_('id', missing_owner_ids).execute()
                prof_map = {p['id']: p for p in (prof_resp.data or []) if p.get('id')}
                for r in raw_reservations:
                    fac = r.get('facilities') or {}
                    if (not fac.get('owner') or not fac['owner'].get('id')) and fac.get('owner_id') in prof_map:
                        fac['owner'] = dict(prof_map[fac['owner_id']])
            except Exception as pe:
                print(f"[my_reservations] error fetching fallback owner profiles: {pe}")

        now = datetime.now(PH_TZ)
        for r in raw_reservations:
            r['can_cancel'] = False

            # Format facility owner info if present
            fac = r.get('facilities') or {}
            owner = fac.get('owner') or {}
            if owner and owner.get('id'):
                o_first = owner.get('first_name') or 'Facility'
                o_last = owner.get('last_name') or 'Owner'
                owner['full_name'] = f"{o_first} {o_last}".strip()
                owner['initials'] = f"{o_first[0]}{o_last[0]}".upper()

            if r['status'] in ['pending_payment', 'confirmed']:
                try:
                    start_time_str = f"{r['date']} {r['start_time']}"
                    end_time_str = f"{r['date']} {r['end_time']}"
                    
                    try:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
                    except ValueError:
                        start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                        end_dt = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
                        
                    if now >= end_dt:
                        db.table('court_reservations').update({'status': 'completed'}).eq('id', r['id']).execute()
                        r['status'] = 'completed'
                    elif now < start_dt:
                        r['can_cancel'] = True
                        
                except Exception as e:
                    print("Error processing reservation dates:", e)
                    r['can_cancel'] = True
            
            r['start_time_12'] = format_time_12h(r.get('start_time'))
            r['end_time_12'] = format_time_12h(r.get('end_time'))
            reservations.append(r)
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return render_template('player/my_reservations.html', reservations=reservations)


@player_bp.route('/reservation/cancel/<reservation_id>', methods=['POST'])
@require_role('player')
def cancel_reservation(reservation_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('court_reservations').update({'status': 'cancelled'}).eq(
            'id', reservation_id).eq('player_id', player_id).in_(
            'status', ['pending_payment', 'confirmed']).execute()
            
        if resp.data:
            db.table('court_queues').update({'status': 'cancelled'}).eq('reservation_id', reservation_id).execute()
            flash('Reservation cancelled.', 'success')
        else:
            flash('Could not cancel reservation. It may have already started.', 'error')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.my_reservations'))


@player_bp.route('/reservation/payment/<reservation_id>', methods=['GET'])
@require_role('player')
def payment(reservation_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, status, '
            'courts(name, type), facilities(name, location)'
        ).eq('id', reservation_id).eq('player_id', player_id).single().execute()
        reservation = resp.data
        if not reservation:
            flash('Reservation not found.', 'error')
            return redirect(url_for('player.my_reservations'))
        if reservation['status'] == 'confirmed':
            flash('This reservation is already paid.', 'info')
            return redirect(url_for('player.my_reservations'))
        reservation['start_time_12'] = format_time_12h(reservation.get('start_time'))
        reservation['end_time_12'] = format_time_12h(reservation.get('end_time'))
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.my_reservations'))
    return render_template('player/payment.html', reservation=reservation)


@player_bp.route('/reservation/payment/<reservation_id>', methods=['POST'])
@require_role('player')
def confirm_payment(reservation_id):
    player_id  = session.get('user_id')
    gcash_ref  = request.form.get('gcash_ref', '').strip()
    if not gcash_ref:
        flash('Please enter your GCash reference number.', 'error')
        return redirect(url_for('player.payment', reservation_id=reservation_id))
        
    import re
    if not re.match(r'^\d{13}$', gcash_ref):
        flash('Invalid GCash reference number format. Must be a 13-digit number.', 'error')
        return redirect(url_for('player.payment', reservation_id=reservation_id))

    db = get_db()
    try:
        # Check duplicate reference number
        dup_resp = db.table('court_reservations').select('id').eq('gcash_ref', gcash_ref).neq('id', reservation_id).execute()
        if dup_resp.data:
            flash('This GCash reference number has already been used for another booking.', 'error')
            return redirect(url_for('player.payment', reservation_id=reservation_id))

        # Get reservation details for queue insertion
        res_resp = db.table('court_reservations').select('facility_id, court_id').eq('id', reservation_id).single().execute()
        res_data = res_resp.data

        receipt_file = request.files.get('receipt')
        receipt_url = None
        if receipt_file and receipt_file.filename:
            from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE
            receipt_url, upload_err = validate_and_upload(
                db,
                receipt_file,
                bucket='kyc-documents',
                prefix='court_receipt',
                owner_id=player_id,
                allowed_exts=ALLOWED_DOC_EXTENSIONS,
                max_size=MAX_DOC_SIZE
            )
            if upload_err:
                flash(f"Receipt upload failed: {upload_err}", "error")
                return redirect(url_for('player.payment', reservation_id=reservation_id))
        
        if not receipt_url:
            flash("Receipt screenshot is required for court booking verification.", "error")
            return redirect(url_for('player.payment', reservation_id=reservation_id))

        db.table('court_reservations').update({
            'gcash_ref': gcash_ref,
            'receipt_url': receipt_url,
        }).eq('id', reservation_id).eq('player_id', player_id).eq(
            'status', 'pending_payment').execute()

        flash('Payment reference submitted successfully! Your booking is pending verification by the facility owner.', 'success')
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.my_reservations'))


@player_bp.route('/reservation/api/upgrade-pro', methods=['POST'])
@require_role('player')
def api_upgrade_pro():
    """Allow logged in players to upgrade directly to Pro Player Pass."""
    player_id = session.get('user_id')
    if not player_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    admin_db = get_admin_db()
    try:
        now_utc = datetime.now(timezone.utc)
        expires_at = (now_utc + timedelta(days=30)).isoformat()
        
        # 1. Update profiles table
        admin_db.table('profiles').update({
            'subscription_tier': 'pro',
            'subscription_status': 'active',
            'subscription_expires_at': expires_at,
        }).eq('id', player_id).execute()
        
        # 2. Record in subscriptions table
        try:
            admin_db.table('subscriptions').insert({
                'user_id': player_id,
                'tier': 'pro',
                'role': 'player',
                'billing_cycle': 'monthly',
                'amount': 199.00,
                'status': 'active',
                'payment_method': 'card_or_gcash',
                'starts_at': now_utc.isoformat(),
                'expires_at': expires_at,
            }).execute()
        except Exception as se:
            print(f"[api_upgrade_pro] Subscriptions log notice: {se}")

        # 3. Update session & cached profile
        session['subscription_tier'] = 'pro'
        session['subscription_status'] = 'active'
        session['subscription_expires_at'] = expires_at
        session.pop('last_integrity_check', None)
        if session.get('cached_profile'):
            session['cached_profile']['subscription_tier'] = 'pro'
            session['cached_profile']['subscription_status'] = 'active'
            session['cached_profile']['subscription_expires_at'] = expires_at
        if hasattr(g, 'current_profile') and g.current_profile:
            g.current_profile['subscription_tier'] = 'pro'
            g.current_profile['subscription_status'] = 'active'
            g.current_profile['subscription_expires_at'] = expires_at

        return jsonify({
            'success': True,
            'message': 'Congratulations! You are now upgraded to Pickleball Pro Pass. 14-day early access booking is now active!'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

