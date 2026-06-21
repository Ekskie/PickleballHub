import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g, current_app
from app.decorators import require_role
from datetime import datetime, timedelta, timezone

PH_TZ = timezone(timedelta(hours=8))

from app.clubadmin import clubadmin_bp
from app.db import get_db, get_admin_db

@clubadmin_bp.before_request
@require_role('clubadmin')
def load_club():
    if request.endpoint == 'auth.logout':
        return
        
    admin_id = session.get('user_id')
    if not admin_id:
        return
        
    db = get_db()
    try:
        resp = db.table('clubs').select('*').eq('admin_id', admin_id).single().execute()
        g.club = resp.data
    except Exception:
        g.club = None

    # Dynamic expiration check for this club (throttled to once every 30 minutes per session)
    if g.club:
        now = time.time()
        last_check = session.get('last_membership_check')
        if not last_check or (now - last_check > 1800):
            try:
                now_str = datetime.now(timezone.utc).isoformat()
                
                # 1. Process expired memberships (batch update + batch insert)
                expired_res = db.table('club_memberships')\
                    .select('id, player_id')\
                    .eq('club_id', g.club['id'])\
                    .eq('status', 'active')\
                    .lt('expires_at', now_str)\
                    .execute()
                
                expired_members = expired_res.data or []
                if expired_members:
                    expired_ids = [em['id'] for em in expired_members]
                    db.table('club_memberships').update({'status': 'expired'}).in_('id', expired_ids).execute()
                    
                    notifs = [
                        {
                            'user_id': em['player_id'],
                            'title': '⚠️ Membership Expired',
                            'message': f"Your membership at {g.club['name']} has expired. Please renew to continue participating in events.",
                            'type': 'warning',
                            'link': f"/player/clubs/{g.club['id']}"
                        } for em in expired_members
                    ]
                    db.table('notifications').insert(notifs).execute()
                        
                # 2. Process expiring warning notifications (expiring within 3 days, optimized batch query)
                warning_threshold = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
                expiring_res = db.table('club_memberships')\
                    .select('id, player_id, expires_at')\
                    .eq('club_id', g.club['id'])\
                    .eq('status', 'active')\
                    .lt('expires_at', warning_threshold)\
                    .gt('expires_at', now_str)\
                    .execute()
                    
                expiring_members = expiring_res.data or []
                if expiring_members:
                    player_ids = [em['player_id'] for em in expiring_members]
                    
                    # Batch check already warned users
                    warned_resp = db.table('notifications')\
                        .select('user_id')\
                        .in_('user_id', player_ids)\
                        .eq('title', '⚠️ Membership Expiring Soon')\
                        .execute()
                    warned_users = {w['user_id'] for w in (warned_resp.data or [])}
                    
                    notifs_to_insert = []
                    for em in expiring_members:
                        if em['player_id'] not in warned_users:
                            expires_dt = datetime.fromisoformat(em['expires_at'].replace('Z', '+00:00'))
                            exp_date_str = expires_dt.strftime('%b %d, %Y')
                            notifs_to_insert.append({
                                'user_id': em['player_id'],
                                'title': '⚠️ Membership Expiring Soon',
                                'message': f"Your membership at {g.club['name']} is expiring soon on {exp_date_str}. Please renew your membership to avoid interruption.",
                                'type': 'warning',
                                'link': f"/player/clubs/{g.club['id']}"
                            })
                            
                    if notifs_to_insert:
                        db.table('notifications').insert(notifs_to_insert).execute()
                
                # Set last check timestamp in session
                session['last_membership_check'] = now
                            
            except Exception as ee:
                current_app.logger.error(f"Failed to auto-expire memberships: {ee}")

    # Redirect to setup if no club exists and not already on setup page
    if not g.club and request.endpoint and request.endpoint not in ['clubadmin.club_setup', 'clubadmin.profile', 'auth.logout']:
        flash("Please set up your club profile first.", "info")
        return redirect(url_for('clubadmin.club_setup'))

@clubadmin_bp.route('/club-setup', methods=['GET', 'POST'])
@require_role('clubadmin')
def club_setup():
    admin_id = session.get('user_id')
    db = get_db()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        membership_type = request.form.get('membership_type', 'free')
        membership_fee = request.form.get('membership_fee', 0)
        membership_duration = request.form.get('membership_duration', 'lifetime')
        
        if not name:
            flash("Club name is required.", "error")
            return redirect(url_for('clubadmin.club_setup'))
            
        update_data = {
            'admin_id': admin_id,
            'name': name,
            'description': description,
            'location': location,
            'membership_type': membership_type,
            'membership_fee': float(membership_fee) if membership_type == 'paid' else 0,
            'membership_duration': membership_duration if membership_type == 'paid' else 'lifetime',
            'status': 'active'
        }
        
        # Handle logo upload
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            try:
                from app.upload_utils import validate_and_upload
                logo_url, err = validate_and_upload(db, logo_file, bucket='community-images', prefix='club', owner_id=admin_id)
                if err:
                    flash(f"Warning: {err}", "warning")
                else:
                    update_data['logo_url'] = logo_url
            except Exception as e:
                flash("Warning: Logo upload failed.", "warning")
                
        try:
            if g.club:
                db.table('clubs').update(update_data).eq('id', g.club['id']).execute()
                flash("Club profile updated.", "success")
            else:
                db.table('clubs').insert(update_data).execute()
                flash("Club created successfully!", "success")
            return redirect(url_for('clubadmin.dashboard'))
        except Exception as e:
            flash('An error occurred. Please try again.', 'error')
            
    return render_template('clubadmin/club_setup.html')

@clubadmin_bp.route('/dashboard')
@require_role('clubadmin')
def dashboard():
    db = get_db()
    stats = {'members': 0, 'events': 0, 'top_player': None, 'recent_members': [], 'activity': []}
    active_members = []
    
    if g.club:
        try:
            # Members count
            mem_resp = db.table('club_memberships').select('id, player_id', count='exact').eq('club_id', g.club['id']).eq('status', 'active').execute()
            stats['members'] = mem_resp.count or 0
            
            # Upcoming Events count
            admin_id = session.get('user_id')
            ev_resp = db.table('events').select('id, organizer_id', count='exact').eq('organizer_id', admin_id).in_('status', ['registration_open', 'upcoming', 'full']).execute()
            stats['events'] = ev_resp.count or 0
            
            # Recent members
            recent_resp = db.table('club_memberships').select(
                'id, player_id, status, joined_at, profiles!player_id(first_name, last_name, proficiency)'
            ).eq('club_id', g.club['id']).order('joined_at', desc=True).limit(5).execute()
            stats['recent_members'] = recent_resp.data or []
            
            # Activity feed
            act_resp = db.table('notifications').select('*').eq('user_id', admin_id).order('created_at', desc=True).limit(5).execute()
            stats['activity'] = act_resp.data or []

            # Fetch active members for casual match logger dropdowns and top player stats
            members_resp = db.table('club_memberships').select(
                'player_id, profiles!player_id(first_name, last_name, elo, dupr, proficiency)'
            ).eq('club_id', g.club['id']).eq('status', 'active').execute()
            
            # Find the top rated player (highest elo) from active members
            top_player = None
            highest_elo = -1
            from app.ratings import get_initial_rating
            for m in (members_resp.data or []):
                prof = m.get('profiles') or {}
                if prof:
                    elo = prof.get('elo')
                    dupr = prof.get('dupr')
                    if elo is None or dupr is None:
                        elo_def, dupr_def = get_initial_rating(prof.get('proficiency'))
                        if elo is None: elo = elo_def
                        if dupr is None: dupr = dupr_def
                    try:
                        dupr_val = float(dupr) if dupr is not None else 0.0
                    except ValueError:
                        dupr_val = 0.0
                    
                    if elo > highest_elo:
                        highest_elo = elo
                        top_player = {
                            'id': m['player_id'],
                            'name': f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip(),
                            'score': f"DUPR: {dupr_val:.2f} | ELO: {elo}"
                        }
                    
                    active_members.append({
                        'id': m['player_id'],
                        'name': f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
                    })
            stats['top_player'] = top_player
            active_members.sort(key=lambda x: x['name'])
            
        except Exception as e:
            current_app.logger.error(f"Dashboard error: {e}")
            
    return render_template('clubadmin/dashboard.html', stats=stats, active_members=active_members)

@clubadmin_bp.route('/log-casual-match', methods=['POST'])
@require_role('clubadmin')
def log_casual_match():
    db = get_db()
    if not g.club:
        flash("Club profile required.", "error")
        return redirect(url_for('clubadmin.dashboard'))
        
    match_type = request.form.get('match_type', 'singles')
    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    
    if p1_score is None or p2_score is None:
        flash("Scores must be valid integers.", "error")
        return redirect(url_for('clubadmin.dashboard'))

    try:
        if match_type == 'singles':
            p1_id = request.form.get('player1_id')
            p2_id = request.form.get('player2_id')
            
            if not p1_id or not p2_id or p1_id == p2_id:
                flash("Please select two distinct players.", "error")
                return redirect(url_for('clubadmin.dashboard'))
                
            winner_id = p1_id if p1_score > p2_score else (p2_id if p2_score > p1_score else None)
            if not winner_id:
                flash("Ties are not currently supported; a winner must be declared by score.", "error")
                return redirect(url_for('clubadmin.dashboard'))
                
            match_resp = db.table('tournament_matches').insert({
                'event_id': None,
                'round_number': None,
                'match_number': None,
                'player1_id': p1_id,
                'player2_id': p2_id,
                'player1_score': p1_score,
                'player2_score': p2_score,
                'winner_id': winner_id,
                'status': 'completed',
                'played_at': datetime.now(PH_TZ).isoformat()
            }).execute()
            
            if match_resp.data:
                match_id = match_resp.data[0]['id']
                from app.ratings import update_match_ratings
                update_match_ratings(db, match_id)
                
            flash("Singles casual match logged. Ratings updated!", "success")
            
        else: # doubles
            p1a_id = request.form.get('player1a_id')
            p1b_id = request.form.get('player1b_id')
            p2a_id = request.form.get('player2a_id')
            p2b_id = request.form.get('player2b_id')
            
            all_pids = [p1a_id, p1b_id, p2a_id, p2b_id]
            if not all(all_pids) or len(set(all_pids)) != 4:
                flash("Please select four distinct players for doubles.", "error")
                return redirect(url_for('clubadmin.dashboard'))
                
            prof_resp = db.table('profiles').select('id, elo, dupr, proficiency').in_('id', all_pids).execute()
            profiles = {p['id']: p for p in (prof_resp.data or [])}
            
            from app.ratings import init_player_rating, elo_to_dupr, adjust_profile_stats, ensure_initial_history
            for pid in all_pids:
                if pid not in profiles:
                    continue
                p = profiles[pid]
                if p.get('elo') is None or p.get('dupr') is None:
                    elo, dupr = init_player_rating(db, pid, p.get('proficiency'))
                    p['elo'] = elo
                    p['dupr'] = dupr
                    
            t1_ids = [p1a_id, p1b_id]
            t2_ids = [p2a_id, p2b_id]
            
            avg_elo1 = sum(profiles[pid]['elo'] for pid in t1_ids) / 2
            avg_elo2 = sum(profiles[pid]['elo'] for pid in t2_ids) / 2
            
            expected1 = 1.0 / (1.0 + 10.0 ** ((avg_elo2 - avg_elo1) / 400.0))
            expected2 = 1.0 - expected1
            
            team1_won = p1_score > p2_score
            actual1 = 1.0 if team1_won else 0.0
            actual2 = 1.0 - actual1
            
            played_at = datetime.now(PH_TZ).isoformat()
            
            # Apply Team 1 updates
            for pid in t1_ids:
                p = profiles[pid]
                old_elo = p['elo']
                old_dupr = p['dupr']
                new_elo = round(old_elo + 32 * (actual1 - expected1))
                new_dupr = elo_to_dupr(new_elo)
                
                db.table('profiles').update({'elo': new_elo, 'dupr': new_dupr}).eq('id', pid).execute()
                ensure_initial_history(db, pid, old_elo, old_dupr, played_at)
                db.table('rating_history').insert({
                    'player_id': pid,
                    'match_id': None,
                    'elo': new_elo,
                    'dupr': new_dupr,
                    'recorded_at': played_at
                }).execute()
                adjust_profile_stats(db, pid, 1 if team1_won else 0, 0 if team1_won else 1)
                
            # Apply Team 2 updates
            for pid in t2_ids:
                p = profiles[pid]
                old_elo = p['elo']
                old_dupr = p['dupr']
                new_elo = round(old_elo + 32 * (actual2 - expected2))
                new_dupr = elo_to_dupr(new_elo)
                
                db.table('profiles').update({'elo': new_elo, 'dupr': new_dupr}).eq('id', pid).execute()
                ensure_initial_history(db, pid, old_elo, old_dupr, played_at)
                db.table('rating_history').insert({
                    'player_id': pid,
                    'match_id': None,
                    'elo': new_elo,
                    'dupr': new_dupr,
                    'recorded_at': played_at
                }).execute()
                adjust_profile_stats(db, pid, 0 if team1_won else 1, 1 if team1_won else 0)
                
            flash("Doubles casual match logged. Ratings updated!", "success")
            
    except Exception as e:
        current_app.logger.error(f"Error logging casual match: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('clubadmin.dashboard'))

@clubadmin_bp.route('/profile', methods=['GET', 'POST'])
@require_role('clubadmin')
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
            flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('clubadmin.profile'))
    return render_template('clubadmin/profile.html')

@clubadmin_bp.route('/notifications')
@require_role('clubadmin')
def notifications():
    user_id = session.get('user_id')
    db = get_db()
    notifs = []
    try:
        resp = db.table('notifications').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
    return render_template('clubadmin/notifications.html', notifications=notifs)

@clubadmin_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('clubadmin')
def mark_notifications_read():
    user_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', user_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@clubadmin_bp.route('/messages')
@require_role('clubadmin')
def messages():
    return render_template('clubadmin/messages.html')

@clubadmin_bp.route('/community')
@require_role('clubadmin')
def community():
    return render_template('clubadmin/community.html')

@clubadmin_bp.route('/tutorials')
@require_role('clubadmin')
def tutorials():
    return render_template('clubadmin/tutorials.html')

@clubadmin_bp.route('/support')
@require_role('clubadmin')
def support():
    return render_template('clubadmin/support.html')

# ── API: Courts by Facility (for JS fetch in create_event) ────────────────────
@clubadmin_bp.route('/api/courts_by_facility/<facility_id>')
@require_role('clubadmin')
def api_courts_by_facility(facility_id):
    db = get_db()
    try:
        resp = db.table('courts').select('id, name, type, hourly_rate').eq('facility_id', facility_id).eq('status', 'active').order('name').execute()
        return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
