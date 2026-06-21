from datetime import datetime, timedelta, timezone
from flask import request, redirect, url_for, session, render_template, flash, jsonify, g
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.clubadmin import clubadmin_bp

@clubadmin_bp.route('/members')
@require_role('clubadmin')
def members():
    db = get_db()
    members_list = []
    
    if g.club:
        try:
            resp = db.table('club_memberships').select(
                'id, status, joined_at, gcash_ref, player_id, profiles!player_id(first_name, last_name, phone, elo, dupr, proficiency, avatar_url, email)'
            ).eq('club_id', g.club['id']).order('joined_at', desc=True).execute()
            members_list = resp.data or []
            
            # Post-process to calculate fallbacks/initials
            from app.ratings import get_initial_rating
            for m in members_list:
                prof = m.get('profiles') or {}
                if prof:
                    first = (prof.get('first_name') or ' ')[0]
                    last = (prof.get('last_name') or ' ')[0]
                    prof['initials'] = (first + last).upper().strip() or '?'
                    
                    elo = prof.get('elo')
                    dupr = prof.get('dupr')
                    if elo is None or dupr is None:
                        elo_def, dupr_def = get_initial_rating(prof.get('proficiency'))
                        if elo is None: prof['elo'] = elo_def
                        if dupr is None: prof['dupr'] = dupr_def
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error listing members for club {g.club['id']}: {e}")
            flash('An error occurred. Please try again.', 'error')
            
    return render_template('clubadmin/members.html', members=members_list)

@clubadmin_bp.route('/members/<player_id>/details')
@require_role('clubadmin')
def member_details(player_id):
    db = get_db()
    if not g.club:
        return jsonify({'error': 'Club not found'}), 404
        
    try:
        # 1. Fetch membership & profile (email is selected directly from joined profiles table)
        mem_resp = db.table('club_memberships').select(
            'joined_at, status, expires_at, gcash_ref, receipt_url, player_id, profiles!player_id(first_name, last_name, phone, elo, dupr, proficiency, avatar_url, email)'
        ).eq('club_id', g.club['id']).eq('player_id', player_id).single().execute()
        
        if not mem_resp.data:
            return jsonify({'error': 'Member not found'}), 404
            
        mem_data = mem_resp.data
        profile = mem_data.get('profiles') or {}
        
        # 2. Fetch rating history
        hist_resp = db.table('rating_history').select('elo, dupr, recorded_at').eq('player_id', player_id).order('recorded_at', desc=True).limit(10).execute()
        rating_hist = hist_resp.data or []
        
        # 3. Fetch active registrations
        reg_resp = db.table('event_registrations').select(
            'status, registered_at, events(title, event_date, type, status)'
        ).eq('player_id', player_id).execute()
        
        registrations = []
        for r in (reg_resp.data or []):
            ev = r.get('events') or {}
            registrations.append({
                'title': ev.get('title'),
                'date': ev.get('event_date'),
                'type': ev.get('type'),
                'status': r.get('status')
            })
            
        # 4. Fetch tournament matches (history)
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
            
        # Build the final dict
        data = {
            'first_name': profile.get('first_name'),
            'last_name': profile.get('last_name'),
            'phone': profile.get('phone') or '—',
            'email': profile.get('email') or '—',
            'elo': profile.get('elo'),
            'dupr': profile.get('dupr'),
            'proficiency': (profile.get('proficiency') or 'beginner').title(),
            'avatar_url': profile.get('avatar_url'),
            'status': mem_data['status'],
            'joined_at': mem_data['joined_at'].split('T')[0] if mem_data['joined_at'] else '—',
            'expires_at': mem_data['expires_at'].split('T')[0] if mem_data['expires_at'] else 'Lifetime',
            'gcash_ref': mem_data['gcash_ref'],
            'receipt_url': mem_data['receipt_url'],
            'membership_fee': g.club.get('membership_fee', 0),
            'rating_history': rating_hist,
            'registrations': registrations,
            'matches': matches
        }
        return jsonify(data)
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error getting member details for player {player_id}: {e}")
        return jsonify({'error': 'An error occurred loading details.'}), 500

@clubadmin_bp.route('/members/<membership_id>/approve', methods=['POST'])
@require_role('clubadmin')
def approve_member(membership_id):
    db = get_db()
    if not g.club:
        return redirect(url_for('clubadmin.dashboard'))
        
    try:
        # Calculate expires_at
        expires_at = None
        duration = g.club.get('membership_duration', 'lifetime')
        if duration == 'monthly':
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        elif duration == 'quarterly':
            expires_at = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        elif duration == 'annually':
            expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
            
        update_data = {
            'status': 'active',
            'joined_at': datetime.now(timezone.utc).isoformat()
        }
        if expires_at:
            update_data['expires_at'] = expires_at
            
        db.table('club_memberships').update(update_data).eq('id', membership_id).eq('club_id', g.club['id']).execute()
        flash("Member approved successfully.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error approving membership {membership_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('clubadmin.members'))

@clubadmin_bp.route('/members/<membership_id>/remove', methods=['POST'])
@require_role('clubadmin')
def remove_member(membership_id):
    db = get_db()
    if not g.club:
        return redirect(url_for('clubadmin.dashboard'))
        
    try:
        db.table('club_memberships').delete().eq('id', membership_id).eq('club_id', g.club['id']).execute()
        flash("Member removed.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error removing membership {membership_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('clubadmin.members'))
