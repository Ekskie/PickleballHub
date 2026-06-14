from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import supabase_admin, supabase
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from app import supabase_admin, supabase

player_bp = Blueprint('player', __name__, url_prefix='/player')

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


def check_player_memberships_expiry(db, player_id):
    """Check if any of the player's active memberships has expired and update status."""
    if not player_id:
        return
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        resp = db.table('club_memberships')\
            .select('id, club_id, expires_at, clubs(name)')\
            .eq('player_id', player_id)\
            .eq('status', 'active')\
            .lt('expires_at', now_str)\
            .execute()
        
        for em in (resp.data or []):
            db.table('club_memberships').update({'status': 'expired'}).eq('id', em['id']).execute()
            club_name = em.get('clubs', {}).get('name', 'the club')
            try:
                db.table('notifications').insert({
                    'user_id': player_id,
                    'title': '⚠️ Membership Expired',
                    'message': f"Your membership for {club_name} has expired. Please renew your membership to continue enjoying member benefits.",
                    'type': 'warning',
                    'link': f"/player/clubs/{em['club_id']}"
                }).execute()
            except Exception as ne:
                print("Failed to insert notification:", ne)
    except Exception as e:
        print("Error checking player membership expiry:", e)


@player_bp.route('/dashboard')
@require_role('player')
def dashboard():
    player_id = session.get('user_id')
    db = get_db()
    next_reservation = None
    available_courts = []
    upcoming_events = []
    recent_activities = []

    # Calculate player stats (Wins, Played, Win Rate)
    player_stats = {'total_played': 0, 'wins': 0, 'win_rate': 0}
    try:
        # Check if wins and losses columns exist in profiles
        prof_resp = db.table('profiles').select('wins, losses').eq('id', player_id).single().execute()
        if prof_resp.data and 'wins' in prof_resp.data and 'losses' in prof_resp.data:
            player_stats['wins'] = prof_resp.data.get('wins') or 0
            losses = prof_resp.data.get('losses') or 0
            player_stats['total_played'] = player_stats['wins'] + losses
            if player_stats['total_played'] > 0:
                player_stats['win_rate'] = round((player_stats['wins'] / player_stats['total_played']) * 100)
        else:
            raise KeyError("wins/losses columns not found in profiles")
    except Exception:
        # Fallback to dynamic calculation if wins/losses columns don't exist yet
        try:
            # 1. Tournament matches
            t_matches = db.table('tournament_matches').select('winner_id').or_(f"player1_id.eq.{player_id},player2_id.eq.{player_id}").eq('status', 'completed').execute()
            t_data = t_matches.data or []
            player_stats['total_played'] += len(t_data)
            player_stats['wins'] += sum(1 for m in t_data if m.get('winner_id') == player_id)

            # 2. Matchmaker lobbies (creator)
            c_lobbies = db.table('matchmaker_lobbies').select('winner_id').eq('creator_id', player_id).eq('status', 'completed').execute()
            c_data = c_lobbies.data or []
            player_stats['total_played'] += len(c_data)
            player_stats['wins'] += sum(1 for m in c_data if m.get('winner_id') == player_id)

            # 3. Matchmaker lobbies (joined) - Only count completed lobbies
            g_lobbies = db.table('lobby_participants').select(
                'lobby:matchmaker_lobbies!lobby_id(winner_id, status)'
            ).eq('player_id', player_id).eq('status', 'joined').execute()

            for item in (g_lobbies.data or []):
                lobby_data = item.get('lobby')
                if lobby_data and lobby_data.get('status') == 'completed':
                    player_stats['total_played'] += 1
                    if lobby_data.get('winner_id') == player_id:
                        player_stats['wins'] += 1

            if player_stats['total_played'] > 0:
                player_stats['win_rate'] = round((player_stats['wins'] / player_stats['total_played']) * 100)
        except Exception as stat_err:
            print(f"Error loading player stats for dashboard fallback: {stat_err}")

    try:
        # Fetch next confirmed reservation
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, status, courts(name), facilities(name, location)'
        ).eq('player_id', player_id).in_('status', ['confirmed']).order('date').order('start_time').limit(1).execute()
        if res_resp.data:
            next_reservation = res_resp.data[0]

        # Fetch some available courts (including facility details)
        court_resp = db.table('courts').select(
            'id, name, type, hourly_rate, status, facilities(name)'
        ).eq('status', 'active').limit(4).execute()
        available_courts = court_resp.data or []

        # Fetch upcoming events (including details)
        ev_resp = db.table('events').select(
            'id, title, event_date, type, location_label'
        ).in_('status', ['upcoming', 'registration_open']).order('event_date').limit(3).execute()
        upcoming_events = ev_resp.data or []

        # Fetch recent activities (notifications)
        act_resp = db.table('notifications').select('id, title, created_at').eq('user_id', player_id).order('created_at', desc=True).limit(4).execute()
        recent_activities = act_resp.data or []

    except Exception as e:
        flash(f"Error loading dashboard data: {e}", "error")

    # Fetch active queue position for the live queue tracker widget
    my_queue = None
    try:
        _, my_queue, _ = get_processed_queues(db, player_id)
    except Exception as q_err:
        print(f"Error fetching active queue for dashboard: {q_err}")

    return render_template(
        'player/dashboard.html',
        next_reservation=next_reservation,
        available_courts=available_courts,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities,
        player_stats=player_stats,
        my_queue=my_queue
    )


@player_bp.route('/support')
@require_role('player')
def support():
    return render_template('player/support.html')


@player_bp.route('/change-password', methods=['POST'])
@require_role('player')
def change_password():
    player_id = session.get('user_id')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match or are empty.", "error")
        return redirect(url_for('player.profile'))
        
    try:
        supabase_admin.auth.admin.update_user_by_id(player_id, {"password": new_password})
        flash("Password updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating password: {e}", "error")
        
    return redirect(url_for('player.profile'))


@player_bp.route('/profile', methods=['GET', 'POST'])
@require_role('player')
def profile():
    player_id = session.get('user_id')
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
                avatar_url = upload_avatar(db, player_id, avatar_file)
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
                
            db.table('profiles').update(update_data).eq('id', player_id).execute()
            
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['phone'] = phone
            if avatar_url:
                session['avatar_url'] = avatar_url
            
            flash("Profile updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
        return redirect(url_for('player.profile'))

    stats = {'courts': 0, 'events': 0, 'tournaments': 0}
    try:
        r_resp = db.table('court_reservations').select('id', count='exact').eq('player_id', player_id).execute()
        stats['courts'] = r_resp.count or 0

        e_resp = db.table('event_registrations').select('id', count='exact').eq('player_id', player_id).execute()
        stats['events'] = e_resp.count or 0

        # Count tournaments specifically (events with type='tournament')
        t_resp = db.table('event_registrations').select(
            'id, events!inner(type)'
        ).eq('player_id', player_id).eq('events.type', 'tournament').execute()
        stats['tournaments'] = len(t_resp.data or [])
    except Exception:
        pass

    # Fetch rating history for charts
    rating_history = []
    try:
        hist_resp = db.table('rating_history').select('*').eq('player_id', player_id).order('recorded_at', desc=False).execute()
        rating_history = hist_resp.data or []
        
        if not rating_history:
            # Player has no rating history yet, let's initialize it!
            prof_resp = db.table('profiles').select('elo, dupr, proficiency, created_at').eq('id', player_id).single().execute()
            prof = prof_resp.data
            if prof:
                elo = prof.get('elo')
                dupr = prof.get('dupr')
                if elo is None or dupr is None:
                    from app.ratings import init_player_rating
                    elo, dupr = init_player_rating(db, player_id, prof.get('proficiency'))
                
                # Insert baseline history slightly older than now
                created_at = prof.get('created_at') or datetime.now(PH_TZ).isoformat()
                from app.ratings import ensure_initial_history
                ensure_initial_history(db, player_id, elo, dupr, created_at)
                
                # Fetch again
                hist_resp = db.table('rating_history').select('*').eq('player_id', player_id).order('recorded_at', desc=False).execute()
                rating_history = hist_resp.data or []
    except Exception as e:
        print(f"[profile_route] Error fetching rating history: {e}")

    # Fetch player's completed matches (tournaments + matchmaker lobbies)
    player_matches = []
    try:
        # 1. Fetch completed tournament matches
        matches_resp = db.table('tournament_matches').select(
            'id, event_id, round_number, match_number, player1_score, player2_score, winner_id, status, played_at, '
            'player1:profiles!player1_id(id, first_name, last_name), '
            'player2:profiles!player2_id(id, first_name, last_name), '
            'events(title)'
        ).or_(f"player1_id.eq.{player_id},player2_id.eq.{player_id}").eq('status', 'completed').order('played_at', desc=True).execute()
        
        raw_matches = matches_resp.data or []
        for m in raw_matches:
            is_p1 = m.get('player1_id') == player_id
            opponent = m.get('player2') if is_p1 else m.get('player1')
            opp_name = f"{opponent.get('first_name', '')} {opponent.get('last_name', '')}".strip() if opponent else "Unknown Opponent"
            
            my_score = m.get('player1_score') if is_p1 else m.get('player2_score')
            opp_score = m.get('player2_score') if is_p1 else m.get('player1_score')
            
            result = "WIN" if m.get('winner_id') == player_id else "LOSS"
            if m.get('winner_id') is None:
                result = "DRAW"
                
            player_matches.append({
                'id': m['id'],
                'event_title': m.get('events', {}).get('title', 'Unknown Tournament') if m.get('events') else 'Tournament Match',
                'opponent_name': opp_name,
                'score': f"{my_score} - {opp_score}" if my_score is not None and opp_score is not None else "N/A",
                'result': result,
                'played_at': m.get('played_at')
            })

        # 2. Fetch completed matchmaking lobbies
        raw_lobbies = []
        creator_lobbies = db.table('matchmaker_lobbies').select(
            'id, title, score, winner_id, creator_id, created_at, '
            'creator:profiles!creator_id(id, first_name, last_name)'
        ).eq('creator_id', player_id).eq('status', 'completed').execute()
        if creator_lobbies.data:
            raw_lobbies.extend(creator_lobbies.data)

        joined_lobbies = db.table('lobby_participants').select(
            'lobby_id, lobby:matchmaker_lobbies!lobby_id(id, title, score, winner_id, creator_id, created_at, creator:profiles!creator_id(id, first_name, last_name))'
        ).eq('player_id', player_id).eq('status', 'joined').execute()
        
        if joined_lobbies.data:
            for item in joined_lobbies.data:
                lobby_data = item.get('lobby')
                if lobby_data and lobby_data.get('status') == 'completed':
                    if not any(x['id'] == lobby_data['id'] for x in raw_lobbies):
                        raw_lobbies.append(lobby_data)

        # Format matchmaking lobbies and append to list
        for lob in raw_lobbies:
            lob_id = lob['id']
            opponent_name = "Unknown Player"
            
            if lob.get('creator_id') == player_id:
                # Fetch participants to find opponent
                part_resp = db.table('lobby_participants').select(
                    'player_id, profiles!player_id(first_name, last_name)'
                ).eq('lobby_id', lob_id).eq('status', 'joined').execute()
                
                if part_resp.data:
                    opp_profile = None
                    for p in part_resp.data:
                        if p.get('player_id') != player_id:
                            opp_profile = p.get('profiles') or {}
                            break
                    if opp_profile:
                        opponent_name = f"{opp_profile.get('first_name', '')} {opp_profile.get('last_name', '')}".strip() or "Unknown Player"
            else:
                opp_profile = lob.get('creator') or {}
                opponent_name = f"{opp_profile.get('first_name', '')} {opp_profile.get('last_name', '')}".strip() or "Unknown Player"

            result = "DRAW"
            if lob.get('winner_id') == player_id:
                result = "WIN"
            elif lob.get('winner_id') is not None:
                result = "LOSS"

            player_matches.append({
                'id': lob['id'],
                'event_title': 'Matchmaker: ' + lob['title'],
                'opponent_name': opponent_name,
                'score': lob.get('score') or "N/A",
                'result': result,
                'played_at': lob.get('created_at')
            })

        # 3. Sort chronologically by date descending
        def get_match_time(m):
            t = m.get('played_at')
            if not t:
                return datetime.min.replace(tzinfo=PH_TZ)
            try:
                # Strip timezone suffix to parse safely
                t_str = str(t)
                if t_str.endswith('Z'):
                    t_str = t_str[:-1] + '+00:00'
                elif '+' not in t_str and '-' not in t_str[10:]:
                    # Append default offset
                    t_str = t_str + '+00:00'
                return datetime.fromisoformat(t_str)
            except Exception:
                return datetime.min.replace(tzinfo=PH_TZ)
                
        player_matches.sort(key=get_match_time, reverse=True)

    except Exception as e:
        print(f"[profile_route] Error fetching player matches: {e}")

    return render_template(
        'player/profile.html',
        stats=stats,
        rating_history=rating_history,
        player_matches=player_matches
    )



@player_bp.route('/reservation')
@require_role('player')
def reservation():
    db = get_db()
    facilities = []
    try:
        resp = db.table('facilities').select(
            'id, name, location, description, open_time, close_time, slot_duration_minutes, kyc_status, image_url, latitude, longitude'
        ).eq('status', 'active').order('name').execute()
        facilities = resp.data or []
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
    return render_template('player/court_reservation.html', facilities=facilities)


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
        flash(f'Error creating reservation: {e}', 'error')

    return redirect(url_for('player.reservation'))


@player_bp.route('/my-reservations')
@require_role('player')
def my_reservations():
    player_id = session.get('user_id')
    db = get_db()
    reservations = []
    try:
        resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
            'status, gcash_ref, created_at, '
            'courts(name, type, image_url), facilities(name, location)'
        ).eq('player_id', player_id).order('created_at', desc=True).execute()
        raw_reservations = resp.data or []
        
        now = datetime.now(PH_TZ)
        for r in raw_reservations:
            r['can_cancel'] = False
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
            
            reservations.append(r)
            
    except Exception as e:
        flash(f'Error loading reservations: {e}', 'error')
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
        flash(f'Error cancelling: {e}', 'error')
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
    except Exception as e:
        flash(f'Error: {e}', 'error')
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
    db = get_db()
    try:
        # Get reservation details for queue insertion
        res_resp = db.table('court_reservations').select('facility_id, court_id').eq('id', reservation_id).single().execute()
        res_data = res_resp.data

        db.table('court_reservations').update({
            'status': 'confirmed',
            'gcash_ref': gcash_ref,
        }).eq('id', reservation_id).eq('player_id', player_id).eq(
            'status', 'pending_payment').execute()

        if res_data:
            # Insert into court_queues
            db.table('court_queues').insert({
                'player_id': player_id,
                'facility_id': res_data['facility_id'],
                'court_id': res_data['court_id'],
                'reservation_id': reservation_id,
                'status': 'waiting',
                'estimated_wait_mins': 0
            }).execute()

            # Trigger automated chat messages from owner and staff
            try:
                from app.chats import trigger_booking_autochat
                trigger_booking_autochat(db, reservation_id, player_id)
            except Exception as chat_err:
                print(f"Error triggering autochats: {chat_err}")

        flash('Payment confirmed! Your court is booked and you are added to the queue.', 'success')
    except Exception as e:
        flash(f'Payment error: {e}', 'error')
    return redirect(url_for('player.my_reservations'))

def get_processed_queues(db, player_id=None):
    """Fetch queues for today, process wait times, and auto-complete games 15 mins past end time."""
    try:
        resp = db.table('court_queues').select(
            'id, status, estimated_wait_mins, joined_at, player_id, facility_id, '
            'courts(name), profiles(first_name, last_name), '
            'facilities(id, name), '
            'court_reservations!inner(date, start_time, end_time)'
        ).in_('status', ['waiting', 'next', 'playing']).order('joined_at').execute()
        raw_queues = resp.data or []
    except Exception as e:
        print("Error fetching queues:", e)
        return [], None, {}
        
    today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
    now = datetime.now(PH_TZ)
    queues = []
    my_queue = None
    
    # Process each queue item
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

        # Auto-complete if they are 'playing' and 15 mins past end time
        if q['status'] == 'playing' and now > (end_dt + timedelta(minutes=15)):
            try:
                db.table('court_queues').update({'status': 'completed'}).eq('id', q['id']).execute()
            except Exception:
                pass
            continue
            
        # Calculate dynamic wait time or time remaining
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

    # Sort queues: Playing first, then Next, then Waiting
    status_order = {'playing': 0, 'next': 1, 'waiting': 2}
    queues.sort(key=lambda x: (status_order.get(x['status'], 3), x.get('court_reservations', {}).get('start_time', '')))

    # Group by facility and assign per-facility positions
    facilities_queues = {}  # {facility_name: {'facility': {...}, 'queues': [...], 'my_queue': None}}
    
    pos_by_facility = {}
    for q in queues:
        fac = q.get('facilities') or {}
        fac_id = q.get('facility_id') or fac.get('id') or 'unknown'
        fac_name = fac.get('name') or 'Unknown Facility'
        
        if fac_id not in facilities_queues:
            facilities_queues[fac_id] = {
                'facility_id': fac_id,
                'facility_name': fac_name,
                'queues': [],
                'my_queue': None
            }
            pos_by_facility[fac_id] = 1
        
        # Assign per-facility position
        if q['status'] != 'playing':
            q['position'] = pos_by_facility[fac_id]
            pos_by_facility[fac_id] += 1
        else:
            q['position'] = '-'
        
        if q['player_id'] == player_id:
            my_queue = q
            facilities_queues[fac_id]['my_queue'] = q
        
        facilities_queues[fac_id]['queues'].append(q)

    # Also build flat list with global positions for backwards compat
    pos = 1
    for q in queues:
        if q['status'] != 'playing':
            q['global_position'] = pos
            pos += 1
        else:
            q['global_position'] = '-'
            
    return queues, my_queue, facilities_queues


@player_bp.route('/queue')
@require_role('player')
def queue():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue, facilities_queues = get_processed_queues(db, player_id)
    return render_template('player/queue_monitoring.html', queues=queues, my_queue=my_queue, facilities_queues=facilities_queues)


@player_bp.route('/queue/partial')
@require_role('player')
def queue_partial():
    player_id = session.get('user_id')
    db = get_db()
    queues, my_queue, facilities_queues = get_processed_queues(db, player_id)
    return render_template('player/partials/queue_content.html', queues=queues, my_queue=my_queue, facilities_queues=facilities_queues)


@player_bp.route('/events')
@require_role('player')
def events():
    player_id = session.get('user_id')
    db = get_db()
    events_list = []
    registered_ids = set()
    joined_count = 0
    try:
        # Fetch upcoming + open events with facility info
        ev_resp = db.table('events').select(
            'id, title, type, format, prize_pool, image_url, event_date, start_time, end_time, max_players, entry_fee, location_label, status, '
            'facilities(name, location)'
        ).in_('status', ['registration_open', 'upcoming', 'full']).order('event_date', desc=False).execute()
        events_list = ev_resp.data or []

        # Attach registration count to each event
        for ev in events_list:
            reg_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', ev['id']).eq('status', 'registered').execute()
            ev['registered_count'] = reg_resp.count if reg_resp.count is not None else 0

        # Fetch this player's registrations
        if player_id:
            my_resp = db.table('event_registrations').select('event_id').eq('player_id', player_id).eq('status', 'registered').execute()
            registered_ids = {r['event_id'] for r in (my_resp.data or [])}
            joined_count = len(registered_ids)

    except Exception as e:
        flash(f'Error loading events: {e}', 'error')

    return render_template(
        'player/events.html',
        events=events_list,
        registered_ids=registered_ids,
        joined_count=joined_count
    )


@player_bp.route('/events/<event_id>/register', methods=['POST'])
@require_role('player')
def register_event(event_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        # Check event capacity and fee
        ev_resp = db.table('events').select('max_players, title, status, entry_fee').eq('id', event_id).single().execute()
        if not ev_resp.data:
            flash('Event not found.', 'error')
            return redirect(url_for('player.events'))

        ev = ev_resp.data
        if ev['status'] == 'full':
            flash('This event is full. You have been added to the waitlist.', 'warning')
            status = 'waitlisted'
        else:
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            count = reg_count_resp.count or 0
            
            if count >= ev['max_players']:
                flash(f'Event is full! You have been waitlisted for "{ev["title"]}".', 'warning')
                # Mark event as full
                db.table('events').update({'status': 'full'}).eq('id', event_id).execute()
                status = 'waitlisted'
            else:
                # Room available! Check if it's a paid event.
                if ev.get('entry_fee') and ev['entry_fee'] > 0:
                    status = 'pending_payment'
                else:
                    status = 'registered'

        db.table('event_registrations').upsert({
            'event_id': event_id,
            'player_id': player_id,
            'status': status,
        }, on_conflict='event_id,player_id').execute()

        if status == 'pending_payment':
            flash(f'Please complete your payment to secure your spot for "{ev["title"]}".', 'info')
            return redirect(url_for('player.tournament_payment', event_id=event_id))
        elif status == 'registered':
            flash(f'Successfully registered for "{ev["title"]}"!', 'success')

    except Exception as e:
        flash(f'Error registering: {e}', 'error')

    return redirect(url_for('player.events'))


@player_bp.route('/events/<event_id>/payment', methods=['GET', 'POST'])
@require_role('player')
def tournament_payment(event_id):
    player_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'POST':
        gcash_ref = request.form.get('gcash_ref', '').strip()
        if not gcash_ref:
            flash('Please enter your GCash reference number.', 'error')
            return redirect(url_for('player.tournament_payment', event_id=event_id))
            
        try:
            # Check capacity again before confirming payment
            ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
            ev = ev_resp.data
            
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            count = reg_count_resp.count or 0
            
            if count >= ev['max_players']:
                # Full! Put them on waitlist
                db.table('event_registrations').update({
                    'status': 'waitlisted'
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('We received your payment, but the event just filled up! You are now on the waitlist and will be contacted.', 'warning')
            else:
                # Secure their spot
                db.table('event_registrations').update({
                    'status': 'registered'
                }).eq('event_id', event_id).eq('player_id', player_id).execute()
                flash('Payment confirmed! You are now officially registered.', 'success')
                
        except Exception as e:
            flash(f'Payment error: {e}', 'error')
            
        return redirect(url_for('player.event_detail', event_id=event_id))
        
    # GET method
    try:
        ev_resp = db.table('events').select('title, entry_fee').eq('id', event_id).single().execute()
        event = ev_resp.data
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('player.events'))
            
        # Check their current status
        my_reg = db.table('event_registrations').select('status').eq('event_id', event_id).eq('player_id', player_id).single().execute()
        if not my_reg.data or my_reg.data['status'] != 'pending_payment':
            flash('No pending payment found for this event.', 'info')
            return redirect(url_for('player.event_detail', event_id=event_id))
            
    except Exception as e:
        flash(f'Error: {e}', 'error')
        return redirect(url_for('player.events'))
        
    return render_template('player/tournament_payment.html', event=event, event_id=event_id)


@player_bp.route('/events/<event_id>/unregister', methods=['POST'])
@require_role('player')
def unregister_event(event_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('event_registrations').update({'status': 'cancelled'}).eq('event_id', event_id).eq('player_id', player_id).execute()
        flash('You have unregistered from the event.', 'success')

        # ── Waitlist Promotion ──────────────────────────────────────────────────
        try:
            ev_resp = db.table('events').select('max_players, title, status').eq('id', event_id).single().execute()
            ev = ev_resp.data
            if not ev:
                return redirect(url_for('player.events'))

            # Count remaining registered players
            reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
            reg_count = reg_count_resp.count or 0

            # If there's now a free spot and the event was marked full, open it
            if ev['status'] == 'full' and reg_count < ev['max_players']:
                db.table('events').update({'status': 'registration_open'}).eq('id', event_id).execute()

            # Promote the oldest waitlisted player
            if reg_count < ev['max_players']:
                waitlist_resp = db.table('event_registrations').select('id, player_id').eq('event_id', event_id).eq('status', 'waitlisted').order('created_at').limit(1).execute()
                if waitlist_resp.data:
                    promoted = waitlist_resp.data[0]
                    db.table('event_registrations').update({'status': 'registered'}).eq('id', promoted['id']).execute()
                    # Notify the promoted player
                    db.table('notifications').insert({
                        'user_id': promoted['player_id'],
                        'title': f'🎉 Spot Available: {ev["title"]}',
                        'message': f'A spot opened up for "{ev["title"]}" and you have been automatically registered. Check your events!',
                        'type': 'success'
                    }).execute()
        except Exception as promotion_err:
            print(f"Waitlist promotion error: {promotion_err}")
        # ───────────────────────────────────────────────────────────────────────

    except Exception as e:
        flash(f'Error unregistering: {e}', 'error')
    return redirect(url_for('player.events'))


@player_bp.route('/events/<event_id>')
@require_role('player')
def event_detail(event_id):
    player_id = session.get('user_id')
    db = get_db()
    ev = None
    is_registered = False
    reg_count = 0
    try:
        ev_resp = db.table('events').select(
            'id, title, type, format, prize_pool, image_url, description, event_date, start_time, end_time, max_players, entry_fee, '
            'location_label, status, created_at, facilities(name, location), profiles!organizer_id(first_name, last_name)'
        ).eq('id', event_id).single().execute()
        ev = ev_resp.data

        reg_count_resp = db.table('event_registrations').select('id', count='exact').eq('event_id', event_id).eq('status', 'registered').execute()
        reg_count = reg_count_resp.count or 0

        player_status = None
        if player_id:
            my_resp = db.table('event_registrations').select('status').eq('event_id', event_id).eq('player_id', player_id).execute()
            if my_resp.data:
                player_status = my_resp.data[0]['status']
                is_registered = (player_status == 'registered')

    except Exception as e:
        flash(f'Error: {e}', 'error')
        return redirect(url_for('player.events'))

    if not ev:
        flash('Event not found.', 'error')
        return redirect(url_for('player.events'))

    return render_template('player/event_detail.html', ev=ev, is_registered=is_registered, reg_count=reg_count, player_status=player_status)


@player_bp.route('/community')
@require_role('player')
def community():
    return render_template('player/community.html')


@player_bp.route('/messages')
@require_role('player')
def messages():
    return render_template('player/messages.html')


@player_bp.route('/notifications')
@require_role('player')
def notifications():
    player_id = session.get('user_id')
    db = get_db()
    notifs = []
    
    try:
        resp = db.table('notifications').select('*').eq('user_id', player_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
        
    return render_template('player/notifications.html', notifications=notifs)

@player_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('player')
def mark_notifications_read():
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', player_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@player_bp.route('/notifications/delete/<notif_id>', methods=['POST'])
@require_role('player')
def delete_notification(notif_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').delete().eq('id', notif_id).eq('user_id', player_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@player_bp.route('/tutorials')
@require_role('player')
def tutorials():
    return render_template('player/tutorials.html')

# ── Clubs ───────────────────────────────────────────────────────────────────────
@player_bp.route('/clubs')
@require_role('player')
def clubs():
    player_id = session.get('user_id')
    db = get_db()
    clubs_list = []
    try:
        # Fetch all active clubs
        resp = db.table('clubs').select(
            'id, name, description, logo_url, location, membership_type, membership_fee, profiles!admin_id(first_name, last_name)'
        ).eq('status', 'active').order('created_at', desc=True).execute()
        clubs_list = resp.data or []
        
        # Attach member count and player's status
        for c in clubs_list:
            # count
            count_resp = db.table('club_memberships').select('id', count='exact').eq('club_id', c['id']).eq('status', 'active').execute()
            c['member_count'] = count_resp.count or 0
            
            # my status
            my_resp = db.table('club_memberships').select('status').eq('club_id', c['id']).eq('player_id', player_id).execute()
            c['my_status'] = my_resp.data[0]['status'] if my_resp.data else None

    except Exception as e:
        flash(f"Error loading clubs: {e}", "error")
        
    return render_template('player/clubs.html', clubs=clubs_list)


@player_bp.route('/clubs/<club_id>')
@require_role('player')
def club_detail(club_id):
    player_id = session.get('user_id')
    db = get_db()
    check_player_memberships_expiry(db, player_id)
    club = None
    members = []
    events_list = []
    my_membership = None
    
    try:
        # 1. Fetch club details and admin profile
        club_resp = db.table('clubs').select(
            'id, name, description, logo_url, location, membership_type, membership_fee, admin_id, '
            'profiles!admin_id(id, first_name, last_name, dupr, elo, avatar_url)'
        ).eq('id', club_id).eq('status', 'active').single().execute()
        club = club_resp.data
        if not club:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))
            
        # 2. Fetch fellow members (active memberships)
        members_resp = db.table('club_memberships').select(
            'id, joined_at, status, profiles!player_id(id, first_name, last_name, dupr, elo, avatar_url)'
        ).eq('club_id', club_id).eq('status', 'active').order('joined_at', desc=True).execute()
        
        # Attach initials to members
        members = []
        for m in (members_resp.data or []):
            prof = m.get('profiles') or {}
            first = prof.get('first_name') or 'P'
            last = prof.get('last_name') or ''
            initials = (first[0] + (last[0] if last else '')).upper()
            m['initials'] = initials
            m['name'] = f"{first} {last}".strip()
            m['avatar_url'] = prof.get('avatar_url') or None
            members.append(m)
        
        # 3. Fetch current user's membership details
        my_mem_resp = db.table('club_memberships').select('*').eq('club_id', club_id).eq('player_id', player_id).execute()
        if my_mem_resp.data:
            my_membership = my_mem_resp.data[0]
            
        # 4. Fetch club events (events where organizer_id = club's admin_id)
        events_resp = db.table('events').select(
            'id, title, event_date, type, location_label, status'
        ).eq('organizer_id', club['admin_id']).in_('status', ['registration_open', 'upcoming']).order('event_date').limit(4).execute()
        events_list = events_resp.data or []
        
    except Exception as e:
        flash(f"Error loading club details: {e}", "error")
        return redirect(url_for('player.clubs'))
        
    return render_template(
        'player/club_detail.html',
        club=club,
        members=members,
        my_membership=my_membership,
        events=events_list
    )


@player_bp.route('/my-clubs')
@require_role('player')
def my_clubs():
    player_id = session.get('user_id')
    db = get_db()
    check_player_memberships_expiry(db, player_id)
    my_clubs_list = []
    try:
        resp = db.table('club_memberships').select(
            'status, joined_at, clubs(id, name, description, logo_url, membership_type)'
        ).eq('player_id', player_id).neq('status', 'rejected').order('joined_at', desc=True).execute()
        my_clubs_list = resp.data or []
    except Exception as e:
        flash(f"Error loading my clubs: {e}", "error")
        
    return render_template('player/my_clubs.html', my_clubs=my_clubs_list)

@player_bp.route('/clubs/<club_id>/join', methods=['POST'])
@require_role('player')
def join_club(club_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        club_resp = db.table('clubs').select('membership_type').eq('id', club_id).single().execute()
        if not club_resp.data:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))
            
        mem_type = club_resp.data['membership_type']
        
        # If paid, redirect to payment page
        if mem_type == 'paid':
            return redirect(url_for('player.club_payment', club_id=club_id))
            
        # If free, join instantly
        db.table('club_memberships').upsert({
            'club_id': club_id,
            'player_id': player_id,
            'status': 'active'
        }, on_conflict='club_id,player_id').execute()
        
        flash("You have successfully joined the club!", "success")
        
    except Exception as e:
        flash(f"Error joining club: {e}", "error")
        
    return redirect(url_for('player.my_clubs'))

@player_bp.route('/clubs/<club_id>/payment', methods=['GET', 'POST'])
@require_role('player')
def club_payment(club_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        club_resp = db.table('clubs').select('id, name, membership_fee').eq('id', club_id).single().execute()
        club = club_resp.data
        if not club:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))
            
        if request.method == 'POST':
            gcash_ref = request.form.get('gcash_ref', '').strip()
            if not gcash_ref:
                flash("GCash Reference Number is required.", "error")
                return redirect(url_for('player.club_payment', club_id=club_id))
                
            receipt_file = request.files.get('receipt')
            receipt_url = None
            if receipt_file and receipt_file.filename:
                try:
                    import time
                    ext = receipt_file.filename.split('.')[-1]
                    filename = f"club_receipt_{player_id}_{int(time.time())}.{ext}"
                    db.storage.from_('kyc-documents').upload(
                        file=receipt_file.read(),
                        path=filename,
                        file_options={"content-type": receipt_file.content_type}
                    )
                    receipt_url = db.storage.from_('kyc-documents').get_public_url(filename)
                except Exception as upload_err:
                    flash(f"Warning: Receipt upload failed - {upload_err}", "warning")
                    
            if not receipt_url:
                flash("Receipt screenshot is required for paid memberships.", "error")
                return redirect(url_for('player.club_payment', club_id=club_id))
                
            db.table('club_memberships').upsert({
                'club_id': club_id,
                'player_id': player_id,
                'status': 'pending',
                'gcash_ref': gcash_ref,
                'receipt_url': receipt_url,
                'joined_at': datetime.now(timezone.utc).isoformat()
            }, on_conflict='club_id,player_id').execute()
            
            flash("Payment submitted! Waiting for admin approval.", "success")
            return redirect(url_for('player.my_clubs'))
            
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for('player.clubs'))
        
    return render_template('player/club_payment.html', club=club)

@player_bp.route('/clubs/<club_id>/leave', methods=['POST'])
@require_role('player')
def leave_club(club_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('club_memberships').delete().eq('club_id', club_id).eq('player_id', player_id).execute()
        flash("You have left the club.", "success")
    except Exception as e:
        flash(f"Error leaving club: {e}", "error")
    return redirect(url_for('player.my_clubs'))


# ── Player Tournament Bracket View ─────────────────────────────────────────────
@player_bp.route('/tournaments')
@require_role('player')
def my_tournaments():
    player_id = session.get('user_id')
    db = get_db()
    tournaments = []
    try:
        reg_resp = db.table('event_registrations').select(
            'status, events!inner(id, title, event_date, status, type, '
            'facilities(name, location))'
        ).eq('player_id', player_id).eq('status', 'registered').execute()
        for r in (reg_resp.data or []):
            ev = r.get('events')
            if ev and ev.get('type') == 'tournament':
                ev['my_registration_status'] = r['status']
                tournaments.append(ev)
    except Exception as e:
        flash(f"Error loading tournaments: {e}", "error")
    return render_template('player/my_tournaments.html', tournaments=tournaments)


@player_bp.route('/tournaments/<event_id>')
@require_role('player')
def tournament_bracket(event_id):
    player_id = session.get('user_id')
    db = get_db()
    event = None
    matches = []
    max_round = 0
    champion = None

    try:
        ev_resp = db.table('events').select(
            'id, title, event_date, status, max_players, '
            'facilities(name, location)'
        ).eq('id', event_id).single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('player.my_tournaments'))

        match_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, '
            'player1_score, player2_score, status, court_id, court_name, referee_name, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = match_resp.data or []

        if matches:
            max_round = max(m['round_number'] for m in matches)
            if event.get('status') == 'completed':
                final_ms = [m for m in matches if m['round_number'] == max_round and m['status'] == 'completed']
                if final_ms and final_ms[0].get('winner'):
                    champion = final_ms[0]['winner']

    except Exception as e:
        flash(f"Error loading bracket: {e}", "error")
        return redirect(url_for('player.my_tournaments'))

    return render_template('player/tournament_bracket.html',
                           event=event,
                           matches=matches,
                           max_round=max_round,
                           champion=champion,
                           player_id=player_id)


# ── Open Play Matchmaker Routes ───────────────────────────────────────────────

def get_lobby_display_status(lobby_status, res_date, res_start, res_end):
    if lobby_status == 'completed':
        return 'completed'
    
    try:
        start_str = f"{res_date} {res_start}"
        end_str = f"{res_date} {res_end}"
        
        if len(res_start) == 5:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
        else:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            
        if len(res_end) == 5:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M').replace(tzinfo=PH_TZ)
        else:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=PH_TZ)
            
        now = datetime.now(PH_TZ)
        if now > end_dt:
            return 'completed'
        elif start_dt <= now <= end_dt:
            return 'ongoing'
        elif lobby_status == 'full':
            return 'full'
        else:
            return 'open'
    except Exception as e:
        print(f"Error computing lobby display status: {e}")
        return lobby_status


@player_bp.route('/matchmaker')
@require_role('player')
def matchmaker():
    player_id = session.get('user_id')
    db = get_db()
    lobbies = []
    reservations = []
    search_query = request.args.get('search', '').strip()
    dupr_level = request.args.get('dupr_level', '').strip()
    selected_tab = request.args.get('tab', 'all').strip()

    try:
        # Fetch active court reservations that belong to this player to populate the dropdown
        today_str = datetime.now(PH_TZ).strftime('%Y-%m-%d')
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, facilities(name), courts(name)'
        ).eq('player_id', player_id).eq('status', 'confirmed').gte('date', today_str).execute()
        reservations = res_resp.data or []

        # Filter out reservations already listed in matchmaker_lobbies
        already_listed = db.table('matchmaker_lobbies').select('reservation_id').eq('creator_id', player_id).neq('status', 'cancelled').execute()
        listed_ids = {r['reservation_id'] for r in (already_listed.data or [])}
        reservations = [r for r in reservations if r['id'] not in listed_ids]

        # Fetch joined matchmaking lobby IDs for tab filtering
        joined_lobby_ids = set()
        if player_id:
            my_joined = db.table('lobby_participants').select('lobby_id').eq('player_id', player_id).eq('status', 'joined').execute()
            joined_lobby_ids = {p['lobby_id'] for p in (my_joined.data or [])}

        # Fetch active lobbies (status: open, full, completed)
        lob_resp = db.table('matchmaker_lobbies').select(
            'id, creator_id, reservation_id, title, description, min_dupr, max_dupr, slots_total, slots_filled, status, created_at, match_type, '
            'creator:profiles!creator_id(first_name, last_name, elo, dupr, proficiency), '
            'reservation:court_reservations!reservation_id(date, start_time, end_time, courts(name), facilities(name))'
        ).neq('status', 'cancelled').order('created_at', desc=True).execute()

        raw_lobbies = lob_resp.data or []
        for lobby in raw_lobbies:
            creator = lobby.get('creator') or {}
            res = lobby.get('reservation') or {}
            court = res.get('courts') or {}
            facility = res.get('facilities') or {}

            lobby_item = {
                'id': lobby['id'],
                'creator_id': lobby['creator_id'],
                'title': lobby['title'],
                'description': lobby['description'],
                'min_dupr': float(lobby['min_dupr']),
                'max_dupr': float(lobby['max_dupr']),
                'slots_total': lobby['slots_total'],
                'slots_filled': lobby['slots_filled'],
                'status': lobby['status'],
                'match_type': lobby.get('match_type') or 'ranked',
                'creator_name': f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip() or "Anonymous Player",
                'creator_dupr': creator.get('dupr') if creator.get('dupr') is not None else 3.00,
                'facility_name': facility.get('name', 'Unknown Facility'),
                'court_name': court.get('name', 'Court'),
                'date': res.get('date') or today_str,
                'start_time': res.get('start_time') or '00:00',
                'end_time': res.get('end_time') or '00:00',
            }
            lobby_item['display_status'] = get_lobby_display_status(
                lobby_item['status'], lobby_item['date'], lobby_item['start_time'], lobby_item['end_time']
            )
            
            # Apply tab filters
            if selected_tab == 'hosted':
                if lobby_item['creator_id'] != player_id:
                    continue
            elif selected_tab == 'joined':
                if lobby_item['id'] not in joined_lobby_ids:
                    continue

            # Apply search filter
            if search_query:
                sq = search_query.lower()
                if (sq not in lobby_item['title'].lower() and 
                    sq not in lobby_item['creator_name'].lower() and
                    sq not in lobby_item['facility_name'].lower()):
                    continue

            # Apply DUPR category filters
            if dupr_level:
                if dupr_level == 'beginner' and not (2.0 <= lobby_item['min_dupr'] <= 3.24):
                    continue
                elif dupr_level == 'intermediate' and not (3.25 <= lobby_item['min_dupr'] <= 4.49):
                    continue
                elif dupr_level == 'advanced' and not (4.50 <= lobby_item['min_dupr'] <= 8.00):
                    continue

            lobbies.append(lobby_item)

    except Exception as e:
        flash(f"Error loading Matchmaker: {e}", "error")

    return render_template(
        'player/matchmaker.html',
        lobbies=lobbies,
        reservations=reservations,
        search_query=search_query,
        selected_level=dupr_level,
        selected_tab=selected_tab
    )


@player_bp.route('/matchmaker/create', methods=['POST'])
@require_role('player')
def matchmaker_create():
    player_id = session.get('user_id')
    reservation_id = request.form.get('reservation_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    min_dupr = float(request.form.get('min_dupr', 2.00))
    max_dupr = float(request.form.get('max_dupr', 8.00))
    slots_total = int(request.form.get('slots_total', 3))
    match_type = request.form.get('match_type', 'ranked').strip()

    if not all([reservation_id, title]):
        flash("Missing lobby creation fields.", "error")
        return redirect(url_for('player.matchmaker'))

    db = get_db()
    try:
        # Verify reservation belongs to player and is confirmed
        res = db.table('court_reservations').select('id, status').eq('id', reservation_id).eq('player_id', player_id).single().execute()
        if not res.data or res.data['status'] != 'confirmed':
            flash("Invalid or unconfirmed court booking.", "error")
            return redirect(url_for('player.matchmaker'))

        lobby_resp = db.table('matchmaker_lobbies').insert({
            'creator_id': player_id,
            'reservation_id': reservation_id,
            'title': title,
            'description': description,
            'min_dupr': min_dupr,
            'max_dupr': max_dupr,
            'slots_total': slots_total,
            'slots_filled': 0,
            'status': 'open',
            'match_type': match_type
        }).execute()

        if lobby_resp.data:
            lobby_id = lobby_resp.data[0]['id']
            try:
                # Initialize conversation for the lobby
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add creator as participant
                db.table('conversation_participants').insert({
                    'conversation_id': lobby_id,
                    'profile_id': player_id
                }).execute()
            except Exception as convo_err:
                print(f"Error creating lobby conversation: {convo_err}")

        flash("Matchmaking lobby published successfully!", "success")
    except Exception as e:
        flash(f"Error publishing lobby: {e}", "error")

    return redirect(url_for('player.matchmaker'))


@player_bp.route('/matchmaker/<lobby_id>')
@require_role('player')
def matchmaker_detail(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    lobby = None
    participants = []
    is_joined = False
    winner_name = ""
    lobby_messages = []

    try:
        lob_resp = db.table('matchmaker_lobbies').select(
            'id, creator_id, reservation_id, title, description, min_dupr, max_dupr, slots_total, slots_filled, status, score, winner_id, match_type, '
            'creator:profiles!creator_id(first_name, last_name, elo, dupr, proficiency, avatar_url), '
            'reservation:court_reservations!reservation_id(date, start_time, end_time, courts(name), facilities(name))'
        ).eq('id', lobby_id).single().execute()

        if not lob_resp.data:
            flash("Lobby not found.", "error")
            return redirect(url_for('player.matchmaker'))

        raw_lob = lob_resp.data
        creator = raw_lob.get('creator') or {}
        res = raw_lob.get('reservation') or {}
        court = res.get('courts') or {}
        facility = res.get('facilities') or {}

        lobby = {
            'id': raw_lob['id'],
            'creator_id': raw_lob['creator_id'],
            'title': raw_lob['title'],
            'description': raw_lob['description'],
            'min_dupr': float(raw_lob['min_dupr']),
            'max_dupr': float(raw_lob['max_dupr']),
            'slots_total': raw_lob['slots_total'],
            'slots_filled': raw_lob['slots_filled'],
            'status': raw_lob['status'],
            'score': raw_lob.get('score'),
            'winner_id': raw_lob.get('winner_id'),
            'match_type': raw_lob.get('match_type') or 'ranked',
            'creator_name': f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip() or "Anonymous Player",
            'creator_dupr': creator.get('dupr') if creator.get('dupr') is not None else 3.00,
            'creator_avatar_url': creator.get('avatar_url') or None,
            'facility_name': facility.get('name', 'Unknown Facility'),
            'court_name': court.get('name', 'Court'),
            'date': res.get('date') or datetime.now(PH_TZ).strftime('%Y-%m-%d'),
            'start_time': res.get('start_time') or '00:00',
            'end_time': res.get('end_time') or '00:00',
        }
        lobby['display_status'] = get_lobby_display_status(
            lobby['status'], lobby['date'], lobby['start_time'], lobby['end_time']
        )

        creator_first = creator.get('first_name') or 'H'
        creator_last = creator.get('last_name') or ''
        creator_initials = (creator_first[0] + (creator_last[0] if creator_last else '')).upper()

        # Fetch participants (including team and slot)
        part_resp = db.table('lobby_participants').select(
            'id, player_id, status, team, slot, profiles!player_id(first_name, last_name, elo, dupr, avatar_url)'
        ).eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        
        raw_participants = part_resp.data or []
        
        # Build Team slots grid
        # Team 1 Slot 1 is always the Creator/Host
        slots_grid = {
            'team1': [
                {'slot': 1, 'player': {
                    'id': lobby['creator_id'],
                    'name': lobby['creator_name'],
                    'dupr': lobby['creator_dupr'],
                    'initials': creator_initials,
                    'avatar_url': lobby.get('creator_avatar_url'),
                    'is_host': True
                }}
            ],
            'team2': []
        }
        
        if lobby['slots_total'] == 3: # Doubles
            slots_grid['team1'].append({'slot': 2, 'player': None})
            slots_grid['team2'].append({'slot': 1, 'player': None})
            slots_grid['team2'].append({'slot': 2, 'player': None})
        elif lobby['slots_total'] == 1: # Singles
            slots_grid['team2'].append({'slot': 1, 'player': None})
        else: # Fallback slots
            for s in range(1, lobby['slots_total'] + 1):
                slots_grid['team2'].append({'slot': s, 'player': None})

        participants = []
        occupied_slots = {
            (1, 1): True # Host is always Team 1, Slot 1
        }
        unmapped_participants = []

        for p in raw_participants:
            p_profile = p.get('profiles') or {}
            first = p_profile.get('first_name') or 'P'
            last = p_profile.get('last_name') or ''
            p['initials'] = (first[0] + (last[0] if last else '')).upper()
            p['name'] = f"{first} {last}".strip() or "Anonymous Player"
            p['avatar_url'] = p_profile.get('avatar_url') or None
            participants.append(p)
            
            if p['player_id'] == player_id:
                is_joined = True
                
            player_info = {
                'id': p['player_id'],
                'name': p['name'],
                'dupr': p_profile.get('dupr') if p_profile.get('dupr') is not None else 3.00,
                'initials': p['initials'],
                'avatar_url': p_profile.get('avatar_url') or None,
                'is_host': False,
                'participant_id': p['id']
            }
            
            t = p.get('team')
            s = p.get('slot')
            
            # First pass: map valid, non-conflicting slots
            if t in [1, 2] and s is not None:
                if (t, s) not in occupied_slots:
                    team_key = f"team{t}"
                    slot_idx = s - 1
                    if team_key in slots_grid and 0 <= slot_idx < len(slots_grid[team_key]):
                        slots_grid[team_key][slot_idx]['player'] = player_info
                        occupied_slots[(t, s)] = True
                        continue
            
            # Otherwise, map in the second pass
            unmapped_participants.append((p['id'], player_info))

        # Second pass: auto-heal conflicting/missing slot assignments
        for part_id, player_info in unmapped_participants:
            found = False
            # Find first empty slot, prioritizing Team 2, then Team 1
            for team_key in ['team2', 'team1']:
                if found:
                    break
                for cell in slots_grid[team_key]:
                    if cell['player'] is None:
                        cell['player'] = player_info
                        found = True
                        t_val = 1 if team_key == 'team1' else 2
                        s_val = cell['slot']
                        occupied_slots[(t_val, s_val)] = True
                        # Update DB to persist the heal
                        try:
                            db.table('lobby_participants').update({
                                'team': t_val,
                                'slot': s_val
                            }).eq('id', part_id).execute()
                            
                            # Also update the local list data
                            p_in_list = next((x for x in participants if x['id'] == part_id), None)
                            if p_in_list:
                                p_in_list['team'] = t_val
                                p_in_list['slot'] = s_val
                        except Exception as auto_heal_err:
                            print(f"[auto_heal] Failed to update slot for participant {part_id}: {auto_heal_err}")
                        break

        if lobby['status'] == 'completed' and lobby['winner_id']:
            # Find winner team name
            # Check if winner is Host or on Team 1
            is_winner_team1 = False
            if lobby['winner_id'] == lobby['creator_id']:
                is_winner_team1 = True
            else:
                for p in participants:
                    if p['player_id'] == lobby['winner_id'] and p.get('team') == 1:
                        is_winner_team1 = True
                        break
            
            if is_winner_team1:
                winner_name = "Team 1"
            else:
                winner_name = "Team 2"

        # Lazy initialize chat conversation for existing lobbies
        convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
        if not convo_check.data:
            try:
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add host
                db.table('conversation_participants').upsert({
                    'conversation_id': lobby_id,
                    'profile_id': lobby['creator_id']
                }, on_conflict='conversation_id,profile_id').execute()
                # Add current participants
                for p in participants:
                    db.table('conversation_participants').upsert({
                        'conversation_id': lobby_id,
                        'profile_id': p['player_id']
                    }, on_conflict='conversation_id,profile_id').execute()
            except Exception as lazy_err:
                print(f"Lazy conversation creation warning: {lazy_err}")

        # Fetch lobby chat messages
        try:
            msg_resp = db.table('messages').select(
                'id, sender_id, content, created_at, profiles!sender_id(first_name, last_name)'
            ).eq('conversation_id', lobby_id).order('created_at', desc=False).execute()
            
            for m in (msg_resp.data or []):
                m_prof = m.get('profiles') or {}
                m_first = m_prof.get('first_name') or 'Player'
                m_last = m_prof.get('last_name') or ''
                m['sender_name'] = f"{m_first} {m_last}".strip()
                m['sender_initials'] = (m_first[0] + (m_last[0] if m_last else '')).upper()
                
                # Format time nicely (e.g. 02:30 PM)
                try:
                    dt = datetime.fromisoformat(m['created_at'].replace('Z', '+00:00'))
                    m['formatted_time'] = dt.astimezone(PH_TZ).strftime('%I:%M %p')
                except Exception:
                    m['formatted_time'] = ''
                
                lobby_messages.append(m)
        except Exception as msg_err:
            print(f"Error fetching lobby messages: {msg_err}")

    except Exception as e:
        flash(f"Error loading lobby: {e}", "error")
        return redirect(url_for('player.matchmaker'))

    return render_template(
        'player/matchmaker_detail.html',
        lobby=lobby,
        participants=participants,
        slots_grid=slots_grid,
        creator_initials=creator_initials,
        is_joined=is_joined,
        winner_name=winner_name,
        messages=lobby_messages
    )


@player_bp.route('/matchmaker/<lobby_id>/join', methods=['POST'])
@require_role('player')
def matchmaker_join(lobby_id):
    player_id = session.get('user_id')
    team = request.form.get('team', type=int)
    slot = request.form.get('slot', type=int)
    db = get_db()
    
    try:
        # Get lobby details
        lob_resp = db.table('matchmaker_lobbies').select('status, slots_total, slots_filled, creator_id, min_dupr, max_dupr').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['status'] != 'open':
            flash("Lobby is not open.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
        if lobby['creator_id'] == player_id:
            flash("You cannot join your own lobby.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Verify rating
        prof_resp = db.table('profiles').select('dupr').eq('id', player_id).single().execute()
        player_dupr = float(prof_resp.data.get('dupr') or 3.00)
        if not (float(lobby['min_dupr']) <= player_dupr <= float(lobby['max_dupr'])):
            flash("Your DUPR rating does not meet lobby requirements.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Check availability
        if lobby['slots_filled'] >= lobby['slots_total']:
            flash("Lobby is already full.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Resolve or validate empty slot choice
        if not team or not slot:
            # Auto-assign empty slot
            occupied = {}
            part_resp = db.table('lobby_participants').select('team, slot').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
            for p in (part_resp.data or []):
                occupied[(p['team'], p['slot'])] = True
                
            found = False
            if lobby['slots_total'] == 3: # Doubles
                for t, s in [(1, 2), (2, 1), (2, 2)]:
                    if (t, s) not in occupied:
                        team, slot = t, s
                        found = True
                        break
            else: # Singles / others
                for s in range(1, lobby['slots_total'] + 1):
                    if (2, s) not in occupied:
                        team, slot = 2, s
                        found = True
                        break
            if not found:
                flash("No empty slots available.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        else:
            # Validate slot is empty
            if team == 1 and slot == 1:
                flash("Host slot is occupied.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
                
            check_occ = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('team', team).eq('slot', slot).eq('status', 'joined').execute()
            if check_occ.data:
                flash("The requested slot is already occupied.", "error")
                return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Insert participant
        db.table('lobby_participants').upsert({
            'lobby_id': lobby_id,
            'player_id': player_id,
            'status': 'joined',
            'team': team,
            'slot': slot
        }, on_conflict='lobby_id,player_id').execute()

        # Update slots count & status
        new_filled = lobby['slots_filled'] + 1
        status = 'full' if new_filled >= lobby['slots_total'] else 'open'
        db.table('matchmaker_lobbies').update({
            'slots_filled': new_filled,
            'status': status
        }).eq('id', lobby_id).execute()

        try:
            # Ensure conversation exists
            convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
            if not convo_check.data:
                db.table('conversations').insert({'id': lobby_id}).execute()
                # Add creator too
                db.table('conversation_participants').upsert({
                    'conversation_id': lobby_id,
                    'profile_id': lobby['creator_id']
                }, on_conflict='conversation_id,profile_id').execute()

            # Add to conversation participants
            db.table('conversation_participants').upsert({
                'conversation_id': lobby_id,
                'profile_id': player_id
            }, on_conflict='conversation_id,profile_id').execute()
        except Exception as convo_err:
            print(f"Error adding player to conversation: {convo_err}")

        flash("Joined open play match lobby!", "success")
    except Exception as e:
        flash(f"Error joining lobby: {e}", "error")
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/switch', methods=['POST'])
@require_role('player')
def matchmaker_switch(lobby_id):
    player_id = session.get('user_id')
    team = request.form.get('team', type=int)
    slot = request.form.get('slot', type=int)
    
    if not team or not slot:
        flash("Invalid slot selection.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    if team == 1 and slot == 1:
        flash("Cannot switch to host slot.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    db = get_db()
    try:
        # Verify lobby status
        lob_resp = db.table('matchmaker_lobbies').select('status').eq('id', lobby_id).single().execute()
        if not lob_resp.data or lob_resp.data['status'] not in ['open', 'full']:
            flash("Lobby is not editable.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Check if target slot is occupied
        occ_check = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('team', team).eq('slot', slot).eq('status', 'joined').execute()
        if occ_check.data:
            flash("Target slot is occupied.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Verify player is already joined
        my_part = db.table('lobby_participants').select('id').eq('lobby_id', lobby_id).eq('player_id', player_id).eq('status', 'joined').execute()
        if not my_part.data:
            flash("You must be joined to switch slots.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Update slot
        db.table('lobby_participants').update({
            'team': team,
            'slot': slot
        }).eq('id', my_part.data[0]['id']).execute()
        
        flash("Switched slot successfully!", "success")
    except Exception as e:
        flash(f"Error switching slot: {e}", "error")
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/leave', methods=['POST'])
@require_role('player')
def matchmaker_leave(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        lob_resp = db.table('matchmaker_lobbies').select('slots_filled, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby:
            flash("Lobby not found.", "error")
            return redirect(url_for('player.matchmaker'))

        db.table('lobby_participants').delete().eq('lobby_id', lobby_id).eq('player_id', player_id).execute()

        # Update slots count & status
        new_filled = max(0, lobby['slots_filled'] - 1)
        db.table('matchmaker_lobbies').update({
            'slots_filled': new_filled,
            'status': 'open'
        }).eq('id', lobby_id).execute()

        try:
            # Remove from conversation participants
            db.table('conversation_participants').delete().eq('conversation_id', lobby_id).eq('profile_id', player_id).execute()
        except Exception as convo_err:
            print(f"Error removing player from conversation: {convo_err}")

        flash("Left open play match lobby.", "success")
    except Exception as e:
        flash(f"Error leaving lobby: {e}", "error")
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/message', methods=['POST'])
@require_role('player')
def matchmaker_message(lobby_id):
    player_id = session.get('user_id')
    content = request.form.get('content', '').strip()
    if not content:
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    db = get_db()
    try:
        # Check if conversation exists
        convo_check = db.table('conversations').select('id').eq('id', lobby_id).execute()
        if not convo_check.data:
            flash("Lobby chat is not initialized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Verify user is a participant of the conversation
        part_check = db.table('conversation_participants').select('profile_id').eq('conversation_id', lobby_id).eq('profile_id', player_id).execute()
        if not part_check.data:
            flash("You must join the lobby first to send messages.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Send message
        db.table('messages').insert({
            'conversation_id': lobby_id,
            'sender_id': player_id,
            'content': content
        }).execute()
        
    except Exception as e:
        flash(f"Error sending message: {e}", "error")
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/edit', methods=['POST'])
@require_role('player')
def matchmaker_edit(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    min_dupr = float(request.form.get('min_dupr', 2.00))
    max_dupr = float(request.form.get('max_dupr', 8.00))
    slots_total = int(request.form.get('slots_total', 3))
    match_type = request.form.get('match_type', 'ranked').strip()
    
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    try:
        # Fetch lobby
        lob_resp = db.table('matchmaker_lobbies').select('creator_id, slots_filled, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['creator_id'] != player_id:
            flash("Unauthorized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if lobby['status'] == 'completed':
            flash("Cannot edit a completed match.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if slots_total < lobby['slots_filled']:
            flash(f"Cannot set slots total below the number of currently joined players ({lobby['slots_filled']}).", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Update lobby details
        status = 'full' if lobby['slots_filled'] >= slots_total else 'open'
        db.table('matchmaker_lobbies').update({
            'title': title,
            'description': description,
            'min_dupr': min_dupr,
            'max_dupr': max_dupr,
            'slots_total': slots_total,
            'status': status,
            'match_type': match_type
        }).eq('id', lobby_id).execute()
        
        flash("Match lobby updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating lobby: {e}", "error")
        
    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


@player_bp.route('/matchmaker/<lobby_id>/delete', methods=['POST'])
@require_role('player')
def matchmaker_delete(lobby_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        # Fetch lobby
        lob_resp = db.table('matchmaker_lobbies').select('creator_id, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['creator_id'] != player_id:
            flash("Unauthorized.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        if lobby['status'] == 'completed':
            flash("Cannot delete a completed match.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
            
        # Delete lobby (cascades to participants)
        db.table('matchmaker_lobbies').delete().eq('id', lobby_id).execute()
        
        # Also clean up conversation
        try:
            db.table('conversations').delete().eq('id', lobby_id).execute()
        except Exception as convo_err:
            print(f"Error deleting lobby conversation: {convo_err}")
            
        flash("Matchmaking lobby deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting lobby: {e}", "error")
        return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))
        
    return redirect(url_for('player.matchmaker'))


@player_bp.route('/matchmaker/<lobby_id>/report', methods=['POST'])
@require_role('player')
def matchmaker_report(lobby_id):
    player_id = session.get('user_id')
    winner_team = request.form.get('winner_team', 'team1') # 'team1' or 'team2'
    score = request.form.get('score', '').strip()
    host_score = request.form.get('host_score', type=int)
    opp_score = request.form.get('opp_score', type=int)

    db = get_db()
    try:
        # Fetch lobby details
        lob_resp = db.table('matchmaker_lobbies').select('creator_id, status').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or lobby['creator_id'] != player_id or lobby['status'] == 'completed':
            flash("Unauthorized or match already reported.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Fetch guests
        part_resp = db.table('lobby_participants').select('player_id, team').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        joined = part_resp.data or []
        
        if not joined:
            flash("Lobby needs at least 1 guest player to report score.", "error")
            return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))

        # Map winner team to a player ID to satisfy winner_id schema constraint
        if winner_team == 'team1':
            winner_id = lobby['creator_id'] # Host represents Team 1
        else:
            # Find a guest player on Team 2
            team2_players = [p['player_id'] for p in joined if p.get('team') == 2]
            if team2_players:
                winner_id = team2_players[0]
            else:
                winner_id = joined[0]['player_id'] # fallback

        # 1. Mark lobby as completed
        db.table('matchmaker_lobbies').update({
            'status': 'completed',
            'score': score,
            'winner_id': winner_id
        }).eq('id', lobby_id).execute()

        # 2. Call update_matchmaker_ratings to update ratings in profiles + rating_history
        from app.ratings import update_matchmaker_ratings
        update_matchmaker_ratings(db, lobby_id)

        flash("Match score reported and player ratings updated!", "success")
    except Exception as e:
        flash(f"Error reporting score: {e}", "error")

    return redirect(url_for('player.matchmaker_detail', lobby_id=lobby_id))


# ── Public Leaderboard & Directory Routes ──────────────────────────────────────

@player_bp.route('/leaderboard')
@require_role('player')
def leaderboard():
    player_id = session.get('user_id')
    db = get_db()
    rankings = []
    search_query = request.args.get('search', '').strip()
    proficiency_filter = request.args.get('proficiency', '').strip()

    try:
        # Fetch all players, including wins and losses if they exist
        p_query = db.table('profiles').select('id, first_name, last_name, elo, dupr, proficiency, avatar_url, wins, losses').eq('role', 'player')
        if proficiency_filter:
            p_query = p_query.eq('proficiency', proficiency_filter)
        
        prof_resp = p_query.execute()
        players = prof_resp.data or []

        # Check if wins and losses columns exist in the retrieved profiles
        has_wins_losses = len(players) > 0 and 'wins' in players[0] and 'losses' in players[0]

        if has_wins_losses:
            # Persistent mode: Read wins and losses directly from the profiles table
            for p in players:
                name = f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip() or "Anonymous Player"
                if search_query and search_query.lower() not in name.lower():
                    continue

                first = p.get('first_name') or 'P'
                last = p.get('last_name') or ''
                initials = (first[0] + (last[0] if last else '')).upper()

                wins = p.get('wins') or 0
                losses = p.get('losses') or 0
                played = wins + losses
                win_rate = round((wins / played) * 100) if played > 0 else 0

                rankings.append({
                    'id': p['id'],
                    'name': name,
                    'initials': initials,
                    'avatar_url': p.get('avatar_url') or None,
                    'dupr': float(p.get('dupr') if p.get('dupr') is not None else 3.00),
                    'elo': p.get('elo') or 1200,
                    'proficiency': p.get('proficiency') or 'beginner',
                    'wins': wins,
                    'losses': losses,
                    'win_rate': win_rate
                })
        else:
            # Fallback dynamic mode: Count tournament matches
            matches_resp = db.table('tournament_matches').select('player1_id, player2_id, winner_id, status').eq('status', 'completed').execute()
            matches = matches_resp.data or []

            stats = {}
            for p in players:
                stats[p['id']] = {'wins': 0, 'losses': 0, 'played': 0}

            for m in matches:
                for pid in [m['player1_id'], m['player2_id']]:
                    if pid in stats:
                        stats[pid]['played'] += 1
                        if m['winner_id'] == pid:
                            stats[pid]['wins'] += 1
                        else:
                            stats[pid]['losses'] += 1

            for p in players:
                name = f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip() or "Anonymous Player"
                if search_query and search_query.lower() not in name.lower():
                    continue

                first = p.get('first_name') or 'P'
                last = p.get('last_name') or ''
                initials = (first[0] + (last[0] if last else '')).upper()

                s = stats.get(p['id'], {'wins': 0, 'losses': 0, 'played': 0})
                win_rate = round((s['wins'] / s['played']) * 100) if s['played'] > 0 else 0

                rankings.append({
                    'id': p['id'],
                    'name': name,
                    'initials': initials,
                    'avatar_url': p.get('avatar_url') or None,
                    'dupr': float(p.get('dupr') if p.get('dupr') is not None else 3.00),
                    'elo': p.get('elo') or 1200,
                    'proficiency': p.get('proficiency') or 'beginner',
                    'wins': s['wins'],
                    'losses': s['losses'],
                    'win_rate': win_rate
                })

        # Sort by DUPR rating descending, then Elo descending
        rankings.sort(key=lambda x: (-x['dupr'], -x['elo']))

        for i, r in enumerate(rankings):
            r['rank'] = i + 1

    except Exception as e:
        flash(f"Error loading leaderboard: {e}", "error")

    return render_template(
        'player/leaderboard.html',
        rankings=rankings,
        search_query=search_query,
        selected_prof=proficiency_filter
    )


@player_bp.route('/leaderboard/challenge/<target_id>')
@require_role('player')
def leaderboard_challenge(target_id):
    player_id = session.get('user_id')
    if player_id == target_id:
        return redirect(url_for('player.leaderboard'))
    
    db = get_db()
    try:
        # Check if conversation already exists
        mine = db.table('conversation_participants').select('conversation_id').eq('profile_id', player_id).execute()
        my_ids = [r['conversation_id'] for r in (mine.data or [])]

        convo_id = None
        if my_ids:
            shared = db.table('conversation_participants').select('conversation_id').eq('profile_id', target_id).in_('conversation_id', my_ids).execute()
            if shared.data:
                convo_id = shared.data[0]['conversation_id']

        if not convo_id:
            # Create conversation
            new_convo = db.table('conversations').insert({}).execute()
            convo_id = new_convo.data[0]['id']

            # Add participants
            db.table('conversation_participants').insert([
                {'conversation_id': convo_id, 'profile_id': player_id},
                {'conversation_id': convo_id, 'profile_id': target_id}
            ]).execute()

            # Send automated message
            msg_content = f"Hi! I saw you on the Leaderboard rankings. I'd love to challenge you to an Open Play Match! 🏓"
            db.table('messages').insert({
                'conversation_id': convo_id,
                'sender_id': player_id,
                'content': msg_content
            }).execute()

        return redirect(url_for('player.messages') + f"#convo-{convo_id}")
    except Exception as e:
        flash(f"Error starting challenge: {e}", "error")
        return redirect(url_for('player.leaderboard'))


@player_bp.route('/chat/<target_id>')
@require_role('player')
def player_chat(target_id):
    player_id = session.get('user_id')
    if player_id == target_id:
        return redirect(url_for('player.messages'))
    
    db = get_db()
    try:
        # Check if conversation already exists
        mine = db.table('conversation_participants').select('conversation_id').eq('profile_id', player_id).execute()
        my_ids = [r['conversation_id'] for r in (mine.data or [])]

        convo_id = None
        if my_ids:
            shared = db.table('conversation_participants').select('conversation_id').eq('profile_id', target_id).in_('conversation_id', my_ids).execute()
            if shared.data:
                convo_id = shared.data[0]['conversation_id']

        if not convo_id:
            # Create conversation
            new_convo = db.table('conversations').insert({}).execute()
            convo_id = new_convo.data[0]['id']

            # Add participants
            db.table('conversation_participants').insert([
                {'conversation_id': convo_id, 'profile_id': player_id},
                {'conversation_id': convo_id, 'profile_id': target_id}
            ]).execute()

        return redirect(url_for('player.messages') + f"#convo-{convo_id}")
    except Exception as e:
        flash(f"Error starting chat: {e}", "error")
        return redirect(url_for('player.dashboard'))


@player_bp.route('/leaderboard/<player_id>/details')
@require_role('player')
def player_details(player_id):
    db = get_db()
    try:
        # Fetch profile
        prof_resp = db.table('profiles').select('first_name, last_name, phone, elo, dupr, proficiency, avatar_url, wins, losses').eq('id', player_id).single().execute()
        if not prof_resp.data:
            return jsonify({'error': 'Player not found'}), 404
        profile = prof_resp.data
        
        # Calculate win rate
        wins = profile.get('wins') or 0
        losses = profile.get('losses') or 0
        played = wins + losses
        win_rate = round((wins / played) * 100) if played > 0 else 0
        
        # Fetch ratings history
        hist_resp = db.table('rating_history').select('elo, dupr, recorded_at').eq('player_id', player_id).order('recorded_at', desc=True).limit(10).execute()
        rating_hist = hist_resp.data or []
        
        # Fetch recent tournament matches
        matches_resp = db.table('tournament_matches').select(
            'round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, '
            'events(title), '
            'player1:profiles!player1_id(first_name, last_name), '
            'player2:profiles!player2_id(first_name, last_name)'
        ).or_(f"player1_id.eq.{player_id},player2_id.eq.{player_id}").order('played_at', desc=True).limit(10).execute()
        
        matches = []
        for m in (matches_resp.data or []):
            ev = m.get('events') or {}
            p1 = m.get('player1') or {}
            p2 = m.get('player2') or {}
            
            p1_name = f"{p1.get('first_name','')} {p1.get('last_name','')}".strip()
            p2_name = f"{p2.get('first_name','')} {p2.get('last_name','')}".strip()
            
            opponent = p2_name if m['player1_id'] == player_id else p1_name
            
            result = 'Pending'
            if m['status'] == 'completed':
                if m['winner_id'] == player_id:
                    result = 'Win'
                else:
                    result = 'Loss'
            
            score_str = f"{m.get('player1_score') or 0} - {m.get('player2_score') or 0}"
            
            matches.append({
                'event_title': ev.get('title') or 'Casual Match',
                'opponent': opponent,
                'round': m['round_number'],
                'score': score_str,
                'result': result,
                'date': m.get('played_at','').split('T')[0] if m.get('played_at') else ''
            })
            
        data = {
            'first_name': profile.get('first_name'),
            'last_name': profile.get('last_name'),
            'phone': profile.get('phone') or '—',
            'elo': profile.get('elo') or 1200,
            'dupr': profile.get('dupr') or 3.00,
            'proficiency': (profile.get('proficiency') or 'beginner').title(),
            'avatar_url': profile.get('avatar_url'),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'rating_history': rating_hist,
            'matches': matches
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


