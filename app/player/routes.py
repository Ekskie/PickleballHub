from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app import limiter
from datetime import datetime, timedelta, timezone
from app.db import get_db, get_admin_db
from app.player import player_bp

PH_TZ = timezone(timedelta(hours=8))


def format_time_12h(time_str):
    if not time_str:
        return ''
    try:
        parts = str(time_str).split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        ap = 'PM' if h >= 12 else 'AM'
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{m:02d} {ap}"
    except Exception:
        return str(time_str)[:5]


def format_date_friendly(date_str):
    if not date_str:
        return ''
    try:
        d = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
        return d.strftime('%a, %b %d, %Y')
    except Exception:
        return str(date_str)


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


def compute_player_sports_data(db, player_id, player_stats):
    """Compute level, XP, achievements, and leaderboard for sports platform experience."""
    wins = player_stats.get('wins', 0)
    played = player_stats.get('total_played', 0)
    
    # Calculate progression
    total_xp = (played * 95) + (wins * 140) + 420
    level = max(1, total_xp // 250)
    current_xp = total_xp % 250
    next_xp = 250
    xp_percent = min(100, max(5, int((current_xp / next_xp) * 100)))
    
    progression = {
        'level': level,
        'current_xp': current_xp,
        'next_xp': next_xp,
        'xp_remaining': next_xp - current_xp,
        'percent': xp_percent,
        'total_xp': total_xp
    }
    
    # Achievements with real/prototype conditions
    achievements = [
        {
            'id': 'first_match',
            'title': 'First Match',
            'desc': 'Complete your first court match',
            'icon': 'ph-tennis-ball',
            'unlocked': played >= 1,
            'meta': 'Unlocked' if played >= 1 else 'Play 1 match'
        },
        {
            'id': 'win_streak',
            'title': 'Hot Streak',
            'desc': 'Secure 3 match victories in a row',
            'icon': 'ph-fire',
            'unlocked': wins >= 3,
            'meta': 'Unlocked' if wins >= 3 else f'{min(wins, 3)}/3 Wins'
        },
        {
            'id': 'century_club',
            'title': '100 Points Won',
            'desc': 'Score over 100 competitive match points',
            'icon': 'ph-target',
            'unlocked': (played * 12 + wins * 11) >= 100,
            'meta': 'Unlocked' if (played * 12 + wins * 11) >= 100 else f'{min((played * 12 + wins * 11), 100)}/100 Pts'
        },
        {
            'id': 'season_veteran',
            'title': 'Season Veteran',
            'desc': 'Participate in 10 court matches or lobbies',
            'icon': 'ph-lightning',
            'unlocked': played >= 10,
            'meta': 'Unlocked' if played >= 10 else f'{played}/10 Games'
        },
        {
            'id': 'top_ten',
            'title': 'Top 10 Contender',
            'desc': 'Climb into top 10 regional leaderboard',
            'icon': 'ph-medal',
            'unlocked': True if wins >= 5 else False,
            'meta': 'Unlocked' if wins >= 5 else 'Rank #14'
        }
    ]
    
    # Leaderboard snippet (from real profiles)
    leaderboard = []
    user_rank = 14
    try:
        prof_res = db.table('profiles').select(
            'id, first_name, last_name, dupr, elo, avatar_url, wins, losses'
        ).eq('role', 'player').order('dupr', desc=True).limit(6).execute()
        
        rank = 1
        for p in (prof_res.data or []):
            p_wins = p.get('wins') or 0
            p_xp = (p_wins * 140) + 850
            is_me = p['id'] == player_id
            if is_me:
                user_rank = rank
            first = p.get('first_name') or 'Player'
            last = p.get('last_name') or ''
            name = f"{first} {last}".strip()
            initials = (first[0] + (last[0] if last else '')).upper()
            leaderboard.append({
                'rank': rank,
                'id': p['id'],
                'name': name,
                'initials': initials,
                'dupr': float(p.get('dupr') if p.get('dupr') is not None else 3.0),
                'elo': p.get('elo') or 1200,
                'xp': p_xp,
                'avatar_url': p.get('avatar_url'),
                'is_current': is_me
            })
            rank += 1
    except Exception as le:
        print(f"Error fetching leaderboard snippet: {le}")
        
    return progression, achievements, leaderboard, user_rank


@player_bp.route('/dashboard')
@require_role('player')
def dashboard():
    player_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db()
    next_reservation = None
    available_courts = []
    upcoming_events = []
    recent_activities = []
    pending_reservations = []

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
        res_resp = admin_db.table('court_reservations').select(
            'id, date, start_time, end_time, status, courts(name, image_url), facilities(name, location)'
        ).eq('player_id', player_id).in_('status', ['confirmed']).order('date').order('start_time').limit(1).execute()
        if res_resp.data:
            next_reservation = res_resp.data[0]

        # Fetch pending reservations to display on dashboard so the user immediately knows their status
        pending_resp = admin_db.table('court_reservations').select(
            'id, date, start_time, end_time, total_hours, hourly_rate, total_amount, '
            'status, gcash_ref, created_at, '
            'courts(id, name, type, image_url), facilities(id, name, location)'
        ).eq('player_id', player_id).in_('status', ['pending_payment', 'pending']).order('date').order('start_time').execute()
        
        for r in (pending_resp.data or []):
            st = r.get('status')
            if st == 'pending_payment' and r.get('gcash_ref'):
                r['display_status'] = 'pending_verification'
                r['status_label'] = 'Awaiting Staff Approval'
                r['status_badge_class'] = 'pending-verif'
            elif st == 'pending_payment':
                r['display_status'] = 'pending_payment'
                r['status_label'] = 'Payment Proof Required'
                r['status_badge_class'] = 'pending-pay'
            else:
                r['display_status'] = 'pending'
                r['status_label'] = 'Pending Review'
                r['status_badge_class'] = 'pending-review'
                
            r['start_time_12'] = format_time_12h(r.get('start_time'))
            r['end_time_12'] = format_time_12h(r.get('end_time'))
            r['date_friendly'] = format_date_friendly(r.get('date'))
            pending_reservations.append(r)

        # Fetch available courts with facility_id and facility name for instant booking
        court_resp = admin_db.table('courts').select(
            'id, facility_id, name, type, hourly_rate, status, facilities(id, name, location)'
        ).eq('status', 'active').limit(4).execute()
        available_courts = court_resp.data or []

        # Fetch upcoming events (including details)
        ev_resp = admin_db.table('events').select(
            'id, title, event_date, type, location_label'
        ).in_('status', ['upcoming', 'registration_open']).order('event_date').limit(3).execute()
        upcoming_events = ev_resp.data or []

        # Fetch recent activities (notifications)
        act_resp = admin_db.table('notifications').select('id, title, created_at').eq('user_id', player_id).order('created_at', desc=True).limit(4).execute()
        recent_activities = act_resp.data or []

    except Exception as e:
        print(f"[dashboard] query error: {e}")
        flash('An error occurred. Please try again.', 'error')

    # Fetch active queue position for the live queue tracker widget
    my_queue = None
    try:
        from app.player.queue_routes import get_processed_queues
        _, my_queue, _ = get_processed_queues(db, player_id)
    except Exception as q_err:
        print(f"Error fetching active queue for dashboard: {q_err}")

    # Compute sports platform progression, achievements, and leaderboard
    progression, achievements, leaderboard_snippet, user_rank = compute_player_sports_data(db, player_id, player_stats)

    # Format upcoming matches (faceoff cards)
    upcoming_matches = []
    if next_reservation:
        c_info = next_reservation.get('courts') or {}
        f_info = next_reservation.get('facilities') or {}
        upcoming_matches.append({
            'opponent_name': 'Open Play Roster',
            'opponent_initials': 'OP',
            'opponent_sub': 'Reserved Court Session',
            'match_type': 'Court Booking',
            'date': format_date_friendly(next_reservation.get('date')),
            'time': f"{format_time_12h(next_reservation.get('start_time'))} - {format_time_12h(next_reservation.get('end_time'))}",
            'venue': f"{c_info.get('name', 'Court')} · {f_info.get('name', 'Facility')}",
            'status': 'Confirmed',
            'link': url_for('player.reservation')
        })
    elif pending_reservations:
        pr = pending_reservations[0]
        c_info = pr.get('courts') or {}
        f_info = pr.get('facilities') or {}
        upcoming_matches.append({
            'opponent_name': 'Court Booking',
            'opponent_initials': 'PB',
            'opponent_sub': pr.get('status_label', 'Pending Booking'),
            'match_type': 'Pending Booking',
            'date': pr.get('date_friendly'),
            'time': f"{pr.get('start_time_12')} - {pr.get('end_time_12')}",
            'venue': f"{c_info.get('name', 'Court')} · {f_info.get('name', 'Facility')}",
            'status': pr.get('status_label', 'Pending'),
            'link': url_for('player.reservation_payment', res_id=pr['id']) if (pr.get('display_status') == 'pending_payment' and not pr.get('gcash_ref')) else url_for('player.reservation')
        })

    if upcoming_events:
        for ev in upcoming_events[:1]:
            upcoming_matches.append({
                'opponent_name': ev.get('title', 'Tournament Match'),
                'opponent_initials': 'TB',
                'opponent_sub': f"Event Category: {ev.get('type', 'Tournament').capitalize()}",
                'match_type': (ev.get('type') or 'Tournament').capitalize(),
                'date': format_date_friendly(ev.get('event_date', 'Upcoming')),
                'time': '7:00 PM',
                'venue': ev.get('location_label') or 'Main Facility',
                'status': 'Registration Open',
                'link': url_for('player.events')
            })

    if not upcoming_matches:
        upcoming_matches.append({
            'opponent_name': 'Ralph David',
            'opponent_initials': 'RD',
            'opponent_sub': 'Intermediate (DUPR 3.35)',
            'match_type': 'Singles Open Play',
            'date': 'Saturday',
            'time': '7:00 PM',
            'venue': 'Paete Indoor Court 1',
            'status': 'Scheduled',
            'link': url_for('player.matchmaker')
        })

    # Real Community Activity Feed from community_posts table
    social_feed = []
    try:
        posts_resp = admin_db.table('community_posts').select(
            'id, author_id, content, image_url, created_at, '
            'author:profiles!community_posts_author_id_fkey(id, first_name, last_name, avatar_url, role, dupr)'
        ).order('created_at', desc=True).limit(6).execute()
        raw_posts = posts_resp.data or []
        post_ids = [p['id'] for p in raw_posts if p.get('id')]

        like_counts = {}
        comment_counts = {}
        user_liked_posts = set()

        if post_ids:
            try:
                likes_resp = admin_db.table('post_likes').select('post_id, profile_id').in_('post_id', post_ids).execute()
                for l in (likes_resp.data or []):
                    pid = l.get('post_id')
                    like_counts[pid] = like_counts.get(pid, 0) + 1
                    if l.get('profile_id') == player_id:
                        user_liked_posts.add(pid)
            except Exception as le:
                print(f"[dashboard] error fetching likes: {le}")

            try:
                comments_resp = admin_db.table('community_comments').select('post_id').in_('post_id', post_ids).execute()
                for c in (comments_resp.data or []):
                    pid = c.get('post_id')
                    comment_counts[pid] = comment_counts.get(pid, 0) + 1
            except Exception as ce:
                print(f"[dashboard] error fetching comments: {ce}")

        for p in raw_posts:
            auth = p.get('author') or {}
            f_name = auth.get('first_name', '')
            l_name = auth.get('last_name', '')
            is_me = (auth.get('id') == player_id) or (p.get('author_id') == player_id)
            user_display = f"{f_name} {l_name}".strip() or "Pickleball Player"
            if is_me:
                user_display = f"{f_name} (You)" if f_name else "You"

            initials = ((f_name[0] if f_name else '') + (l_name[0] if l_name else '')).upper() or 'PB'
            avatar = auth.get('avatar_url')
            
            created_str = p.get('created_at')
            time_ago = 'Recently'
            if created_str:
                try:
                    dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    now_utc = datetime.now(dt.tzinfo)
                    diff = now_utc - dt
                    secs = int(diff.total_seconds())
                    if secs < 60:
                        time_ago = 'Just now'
                    elif secs < 3600:
                        time_ago = f"{secs // 60}m ago"
                    elif secs < 86400:
                        time_ago = f"{secs // 3600}h ago"
                    elif secs < 172800:
                        time_ago = 'Yesterday'
                    else:
                        time_ago = f"{secs // 86400}d ago"
                except Exception:
                    time_ago = str(created_str)[:10]

            content_text = p.get('content') or ''
            lower_content = content_text.lower()
            if 'won' in lower_content or 'win' in lower_content or 'champion' in lower_content or 'score' in lower_content:
                act_type = 'win'
            elif 'booked' in lower_content or 'court' in lower_content or 'session' in lower_content:
                act_type = 'booking'
            elif 'tournament' in lower_content or 'clinic' in lower_content or 'event' in lower_content:
                act_type = 'event'
            else:
                act_type = 'community'

            social_feed.append({
                'id': p['id'],
                'user': user_display,
                'avatar': avatar,
                'initials': initials,
                'action': content_text,
                'image_url': p.get('image_url'),
                'time': time_ago,
                'type': act_type,
                'kudos': like_counts.get(p['id'], 0),
                'comments_count': comment_counts.get(p['id'], 0),
                'is_liked': p['id'] in user_liked_posts,
                'author_role': auth.get('role', 'player')
            })
    except Exception as fe:
        print(f"[dashboard] error loading social feed from community_posts: {fe}")

    player_streak = max(player_stats.get('wins', 0), 1) if player_stats.get('wins', 0) > 0 else 0

    return render_template(
        'player/dashboard.html',
        next_reservation=next_reservation,
        pending_reservations=pending_reservations,
        available_courts=available_courts,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities,
        player_stats=player_stats,
        my_queue=my_queue,
        progression=progression,
        achievements=achievements,
        leaderboard=leaderboard_snippet,
        user_rank=user_rank,
        social_feed=social_feed,
        upcoming_matches=upcoming_matches,
        player_streak=player_streak
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


@player_bp.route('/delete-account', methods=['POST'])
@limiter.limit("3/minute")
@require_role('player')
def delete_account():
    player_id = session.get('user_id')
    email = session.get('email', '')
    password = request.form.get('password', '').strip()
    confirmation_text = request.form.get('confirmation_text', '').strip()

    if not password:
        flash("Current password is required to delete your account.", "error")
        return redirect(url_for('player.profile') + '?tab=settings')

    if confirmation_text.strip().upper() != "DELETE":
        flash("Please type 'DELETE' to confirm account deletion.", "error")
        return redirect(url_for('player.profile') + '?tab=settings')

    # Verify password against Supabase Auth before deleting
    try:
        db = get_db()
        db.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        flash("Incorrect password. Account deletion cancelled.", "error")
        return redirect(url_for('player.profile') + '?tab=settings')

    try:
        admin_db = get_admin_db()

        # 1. Disassociate tournament matches (player1, player2, winner)
        try:
            admin_db.table('tournament_matches').update({'player1_id': None}).eq('player1_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('tournament_matches').update({'player2_id': None}).eq('player2_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('tournament_matches').update({'winner_id': None}).eq('winner_id', player_id).execute()
        except Exception:
            pass

        # 2. Clean up matchmaker lobbies & participants
        try:
            admin_db.table('lobby_participants').delete().eq('player_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('matchmaker_lobbies').update({'winner_id': None}).eq('winner_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('matchmaker_lobbies').update({'reported_winner_id': None}).eq('reported_winner_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('matchmaker_lobbies').update({'reporter_id': None}).eq('reporter_id', player_id).execute()
        except Exception:
            pass
        try:
            admin_db.table('matchmaker_lobbies').delete().eq('creator_id', player_id).eq('status', 'open').execute()
        except Exception:
            pass

        # 3. Clean up active court queues
        try:
            admin_db.table('court_queues').delete().eq('player_id', player_id).execute()
        except Exception:
            pass

        # 4. Disassociate tickets
        try:
            admin_db.table('tickets').update({'user_id': None}).eq('user_id', player_id).execute()
        except Exception:
            pass

        # 5. Delete profile record directly to ensure all profile cascades take place
        try:
            admin_db.table('profiles').delete().eq('id', player_id).execute()
        except Exception as prof_err:
            import sys
            print(f"[delete_account] profiles delete note: {prof_err}", file=sys.stderr)

        # 6. Delete user in Supabase auth (cleans auth.users)
        try:
            admin_db.auth.admin.delete_user(player_id)
        except Exception as auth_err:
            import sys
            print(f"[delete_account] admin.delete_user note: {auth_err}", file=sys.stderr)

        # Clear session completely
        session.clear()
        flash("Your account and associated profile data have been permanently deleted.", "success")
        return redirect(url_for('main.index'))
    except Exception as e:
        import sys
        print(f"[delete_account] Error deleting player {player_id}: {e}", file=sys.stderr)
        flash("Could not delete account. Please try again or contact platform support.", "error")
        return redirect(url_for('player.profile') + '?tab=settings')


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
                admin_db = get_admin_db() or db
                ensure_initial_history(admin_db, player_id, elo, dupr, created_at)
                
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

    player_stats = {'total_played': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
    try:
        prof_resp = db.table('profiles').select('wins, losses').eq('id', player_id).single().execute()
        if prof_resp.data:
            player_stats['wins'] = prof_resp.data.get('wins') or 0
            player_stats['losses'] = prof_resp.data.get('losses') or 0
            player_stats['total_played'] = player_stats['wins'] + player_stats['losses']
            if player_stats['total_played'] > 0:
                player_stats['win_rate'] = round((player_stats['wins'] / player_stats['total_played']) * 100)
    except Exception as e:
        print(f"Error loading player stats for profile: {e}")

    progression, achievements, _, _ = compute_player_sports_data(db, player_id, player_stats)
    player_streak = max(player_stats['wins'], 1) if player_stats['wins'] > 0 else 0

    return render_template(
        'player/profile.html',
        stats=stats,
        rating_history=rating_history,
        player_matches=player_matches,
        player_stats=player_stats,
        progression=progression,
        achievements=achievements,
        player_streak=player_streak
    )
