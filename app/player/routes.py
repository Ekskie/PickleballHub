from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import limiter
from datetime import datetime, timedelta, timezone
from app.db import get_db, get_admin_db
from app.player import player_bp

PH_TZ = timezone(timedelta(hours=8))


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

    # Calculate player stats (Wins, Played, Win Rate) from profile table
    player_stats = {'total_played': 0, 'wins': 0, 'win_rate': 0}
    try:
        prof_resp = db.table('profiles').select('wins, losses').eq('id', player_id).single().execute()
        if prof_resp.data:
            player_stats['wins'] = prof_resp.data.get('wins') or 0
            losses = prof_resp.data.get('losses') or 0
            player_stats['total_played'] = player_stats['wins'] + losses
            if player_stats['total_played'] > 0:
                player_stats['win_rate'] = round((player_stats['wins'] / player_stats['total_played']) * 100)
    except Exception as e:
        print(f"Error loading player stats from profile: {e}")

    try:
        # Fetch next confirmed reservation
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, status, courts(name, image_url), facilities(name, location)'
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
        flash('An error occurred. Please try again.', 'error')

    # Fetch active queue position for the live queue tracker widget
    my_queue = None
    try:
        from app.player.queue_routes import get_processed_queues
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
@limiter.limit("5/minute")
@require_role('player')
def change_password():
    player_id = session.get('user_id')
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match or are empty.", "error")
        return redirect(url_for('player.profile'))
    
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for('player.profile'))
    
    # Verify old password before allowing change
    if not old_password:
        flash("Current password is required to set a new password.", "error")
        return redirect(url_for('player.profile'))
    
    try:
        # Verify old password by attempting sign-in
        email = session.get('email', '')
        db = get_db()
        db.auth.sign_in_with_password({"email": email, "password": old_password})
    except Exception:
        flash("Current password is incorrect.", "error")
        return redirect(url_for('player.profile'))
        
    try:
        admin_db = get_admin_db()
        admin_db.auth.admin.update_user_by_id(player_id, {"password": new_password})
        flash("Password updated successfully.", "success")
    except Exception as e:
        import sys
        print(f"[change_password] Error: {e}", file=sys.stderr)
        flash("Could not update password. Please try again.", "error")
        
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
            flash('An error occurred. Please try again.', 'error')
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
