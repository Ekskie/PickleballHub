import random
from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash, g, current_app
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.clubadmin import clubadmin_bp
from app.owner.routes import PH_TZ

@clubadmin_bp.route('/tournaments')
@require_role('clubadmin')
def tournaments():
    admin_id = session.get('user_id')
    db = get_db()
    tournaments_list = []
    try:
        resp = db.table('events').select(
            'id, title, event_date, status'
        ).eq('organizer_id', admin_id).eq('type', 'tournament').order('event_date', desc=False).execute()
        tournaments_list = resp.data or []
        
        # Optimized N+1 registration counts query
        if tournaments_list:
            t_ids = [t['id'] for t in tournaments_list]
            reg_resp = db.table('event_registrations').select('event_id').in_('event_id', t_ids).eq('status', 'registered').execute()
            reg_data = reg_resp.data or []
            
            from collections import Counter
            reg_counts = Counter(r['event_id'] for r in reg_data)
            
            for t in tournaments_list:
                t['registered_count'] = reg_counts[t['id']]
    except Exception as e:
        current_app.logger.error(f"Error loading tournaments list: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('clubadmin/tournaments.html', tournaments=tournaments_list)

def generate_seed_order(n):
    """Generate official single-elimination tournament seed pairing order for bracket size n (power of 2)."""
    order = [1, 2]
    while len(order) < n:
        next_order = []
        target = len(order) * 2 + 1
        for s in order:
            next_order.append(s)
            next_order.append(target - s)
        order = next_order
    return order

@clubadmin_bp.route('/tournaments/<event_id>/manage')
@require_role('clubadmin')
def tournament_manage(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    
    try:
        # Verify ownership
        ev_resp = admin_db.table('events').select('*').eq('id', event_id).eq('organizer_id', admin_id).eq('type', 'tournament').single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('clubadmin.tournaments'))
            
        # Get all tournaments for dropdown
        all_t_resp = admin_db.table('events').select('id, title').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        all_tournaments = all_t_resp.data or []
        
        # Get participants (both registered users and walk-ins)
        reg_resp = admin_db.table('event_registrations').select(
            'id, player_id, is_walkin, guest_name, skill_level, estimated_elo, status, registered_at, profiles!player_id(first_name, last_name, avatar_url, elo, dupr, proficiency)'
        ).eq('event_id', event_id).eq('status', 'registered').order('registered_at').execute()
        participants = reg_resp.data or []
        
        # Get matches
        matches_resp = admin_db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, court_id, court_name, referee_name, '
            'player1_guest_name, player2_guest_name, winner_guest_name, player1_reg_id, player2_reg_id, winner_reg_id, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = matches_resp.data or []
        
        # Get booked courts for this event
        court_resp = admin_db.table('event_courts').select(
            'court_id, courts(id, name)'
        ).eq('event_id', event_id).execute()
        booked_courts = court_resp.data or []
        
        has_bracket = len(matches) > 0
        can_reset = has_bracket and not any(m.get('player1_score') is not None for m in matches)
        
        return render_template('clubadmin/tournament_manage.html', 
                               event=event, 
                               all_tournaments=all_tournaments,
                               participants=participants,
                               matches=matches,
                               has_bracket=has_bracket,
                               can_reset=can_reset,
                               booked_courts=booked_courts)
                               
    except Exception as e:
        current_app.logger.error(f"Error managing tournament {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('clubadmin.tournaments'))

@clubadmin_bp.route('/tournaments/<event_id>/walkins/add', methods=['POST'])
@require_role('clubadmin')
def walkins_add(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    try:
        # Verify ownership
        ev_resp = admin_db.table('events').select('id, max_players').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        if not ev_resp.data:
            flash("Tournament not found.", "error")
            return redirect(url_for('clubadmin.tournaments'))

        # Check if bracket already exists
        m_chk = admin_db.table('tournament_matches').select('id').eq('event_id', event_id).limit(1).execute()
        if m_chk.data:
            flash("Cannot add walk-in players while a bracket is active. Please reset the bracket first.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

        names = request.form.getlist('guest_name[]')
        skills = request.form.getlist('skill_level[]')

        skill_map = {
            'novice': 800,
            'beginner': 1000,
            'intermediate': 1400,
            'advanced': 1800,
            'pro': 2200
        }

        walkins_to_insert = []
        for name, skill in zip(names, skills):
            name_clean = (name or '').strip()
            if not name_clean:
                continue
            sk_clean = (skill or 'intermediate').lower().strip()
            est_elo = skill_map.get(sk_clean, 1400)
            walkins_to_insert.append({
                'event_id': event_id,
                'player_id': None,
                'is_walkin': True,
                'guest_name': name_clean,
                'skill_level': sk_clean,
                'estimated_elo': est_elo,
                'status': 'registered'
            })

        if not walkins_to_insert:
            flash("No valid player names entered.", "warning")
        else:
            admin_db.table('event_registrations').insert(walkins_to_insert).execute()
            flash(f"Successfully added {len(walkins_to_insert)} walk-in player(s)!", "success")

    except Exception as e:
        current_app.logger.error(f"Error adding walkins: {e}")
        flash('An error occurred while adding walk-in players.', 'error')

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/tournaments/<event_id>/registrations/<reg_id>/remove', methods=['POST'])
@require_role('clubadmin')
def registration_remove(event_id, reg_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    try:
        admin_db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        m_chk = admin_db.table('tournament_matches').select('id').eq('event_id', event_id).limit(1).execute()
        if m_chk.data:
            flash("Cannot remove players while a bracket is active. Please reset the bracket first.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

        admin_db.table('event_registrations').delete().eq('id', reg_id).eq('event_id', event_id).execute()
        flash("Player removed from tournament roster.", "success")
    except Exception as e:
        current_app.logger.error(f"Error removing registration: {e}")
        flash('An error occurred while removing player.', 'error')

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/tournaments/<event_id>/ranked-toggle', methods=['POST'])
@require_role('clubadmin')
def tournament_ranked_toggle(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    try:
        ev_resp = admin_db.table('events').select('id, is_ranked').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('clubadmin.tournaments'))

        current_val = event.get('is_ranked', True)
        new_val = not current_val
        if 'is_ranked' in request.form:
            new_val = request.form.get('is_ranked') in ['1', 'true', 'True', 'on']

        admin_db.table('events').update({'is_ranked': new_val}).eq('id', event_id).execute()
        status_label = "Ranked (ELO Affected)" if new_val else "Casual / Unranked (ELO Unaffected)"
        flash(f"Tournament setting updated: {status_label}", "success")
    except Exception as e:
        current_app.logger.error(f"Error toggling ranked status: {e}")
        flash('Failed to update tournament ranked setting.', 'error')

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/tournaments/<event_id>/bracket/reset', methods=['POST'])
@require_role('clubadmin')
def bracket_reset(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    try:
        admin_db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()

        comp_chk = admin_db.table('tournament_matches').select('id, player1_score').eq('event_id', event_id).execute()
        matches = comp_chk.data or []
        if any(m.get('player1_score') is not None for m in matches):
            flash("Cannot reset bracket because one or more matches have already been scored.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

        admin_db.table('tournament_matches').delete().eq('event_id', event_id).execute()
        admin_db.table('events').update({'status': 'registration_open'}).eq('id', event_id).execute()
        flash("Bracket has been reset. You can now adjust players and re-generate.", "success")
    except Exception as e:
        current_app.logger.error(f"Error resetting bracket: {e}")
        flash('Failed to reset bracket.', 'error')

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/tournaments/<event_id>/bracket/generate', methods=['POST'])
@require_role('clubadmin')
def bracket_generate(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    seed_mode = request.form.get('seed_mode', 'fair')
    
    try:
        # Verify ownership
        admin_db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        # Get participants with profiles
        reg_resp = admin_db.table('event_registrations').select(
            'id, player_id, is_walkin, guest_name, skill_level, estimated_elo, profiles!player_id(first_name, last_name, elo, dupr, proficiency)'
        ).eq('event_id', event_id).eq('status', 'registered').execute()
        raw_regs = reg_resp.data or []
        
        if len(raw_regs) < 2:
            flash("At least 2 players are required to generate a tournament bracket.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))
            
        from app.billing.tiers import check_feature_limit
        brack_chk = check_feature_limit(admin_id, 'clubadmin', 'max_tournament_bracket', current_count=len(raw_regs), db=admin_db)
        if not brack_chk['allowed']:
            flash(brack_chk['message'], 'warning')
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

        from app.ratings import get_initial_rating
        players = []
        for r in raw_regs:
            prof = r.get('profiles')
            if r.get('is_walkin') or not r.get('player_id'):
                p_name = (r.get('guest_name') or 'Guest Walk-in').strip()
                p_elo = r.get('estimated_elo') or get_initial_rating(r.get('skill_level'))[0]
                players.append({
                    'player_id': None,
                    'guest_name': p_name,
                    'reg_id': r['id'],
                    'elo': p_elo,
                    'is_walkin': True
                })
            else:
                p_first = prof.get('first_name') if prof else ''
                p_last = prof.get('last_name') if prof else ''
                p_name = f"{p_first} {p_last}".strip() or 'Player'
                p_elo = prof.get('elo') if prof and prof.get('elo') is not None else get_initial_rating(prof.get('proficiency') if prof else 'beginner')[0]
                players.append({
                    'player_id': r['player_id'],
                    'guest_name': None,
                    'reg_id': r['id'],
                    'elo': p_elo,
                    'is_walkin': False
                })

        # Calculate next power of 2 bracket size
        N = len(players)
        P = 2
        while P < N:
            P *= 2

        if seed_mode == 'fair':
            # Sort players descending by ELO rating
            players.sort(key=lambda p: -p['elo'])
            seed_order = generate_seed_order(P)
            # Map seeds 1..N to sorted players, remaining are None (Byes)
            seed_map = {}
            for idx, p in enumerate(players):
                seed_map[idx + 1] = p
            for s in range(N + 1, P + 1):
                seed_map[s] = None
        else:
            # Random draw
            random.shuffle(players)
            seed_order = generate_seed_order(P)
            seed_map = {}
            for idx, p in enumerate(players):
                seed_map[idx + 1] = p
            for s in range(N + 1, P + 1):
                seed_map[s] = None

        matches_to_insert = []
        match_num = 1
        for i in range(0, P, 2):
            s1 = seed_order[i]
            s2 = seed_order[i + 1]
            p1 = seed_map[s1]
            p2 = seed_map[s2]

            # If p1 is None but p2 has a player, swap so p1 holds the player
            if not p1 and p2:
                p1, p2 = p2, p1

            if not p1 and not p2:
                continue

            is_bye = (p2 is None)
            matches_to_insert.append({
                'event_id': event_id,
                'round_number': 1,
                'match_number': match_num,
                'player1_id': p1['player_id'] if p1 else None,
                'player1_guest_name': p1['guest_name'] if p1 else None,
                'player1_reg_id': p1['reg_id'] if p1 else None,
                'player2_id': p2['player_id'] if p2 else None,
                'player2_guest_name': p2['guest_name'] if p2 else None,
                'player2_reg_id': p2['reg_id'] if p2 else None,
                'status': 'completed' if is_bye else 'pending',
                'winner_id': p1['player_id'] if is_bye else None,
                'winner_guest_name': p1['guest_name'] if is_bye else None,
                'winner_reg_id': p1['reg_id'] if is_bye else None
            })
            match_num += 1
            
        if matches_to_insert:
            admin_db.table('tournament_matches').insert(matches_to_insert).execute()
            try:
                admin_db.table('events').update({'status': 'in_progress'}).eq('id', event_id).execute()
            except Exception:
                pass
            
        flash(f"Bracket generated successfully ({'Fair Seeding by ELO' if seed_mode == 'fair' else 'Random Draw'})!", "success")
        
    except Exception as e:
        current_app.logger.error(f"Error generating tournament bracket {event_id}: {e}")
        flash('An error occurred while generating the bracket.', 'error')
        
    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

def _advance_bracket(db, event_id):
    """Check current round completion and auto-generate next round or declare champion."""
    try:
        all_m = db.table('tournament_matches').select(
            'id, round_number, status, winner_id, winner_guest_name, winner_reg_id'
        ).eq('event_id', event_id).order('round_number').execute()
        matches = all_m.data or []
        if not matches:
            return

        max_round = max(m['round_number'] for m in matches)
        round_matches = [m for m in matches if m['round_number'] == max_round]

        if any(m['status'] != 'completed' for m in round_matches):
            return

        winners = []
        for m in round_matches:
            winners.append({
                'id': m.get('winner_id'),
                'guest_name': m.get('winner_guest_name'),
                'reg_id': m.get('winner_reg_id')
            })

        if len(winners) == 1:
            db.table('events').update({'status': 'completed'}).eq('id', event_id).execute()
            if winners[0]['id']:
                try:
                    db.table('notifications').insert({
                        'user_id': winners[0]['id'],
                        'title': '🏆 Tournament Champion!',
                        'message': 'Congratulations! You have won the tournament!',
                        'type': 'success'
                    }).execute()
                except Exception:
                    pass
            return

        next_round = max_round + 1
        match_num = 1
        next_matches = []
        for i in range(0, len(winners), 2):
            w1 = winners[i]
            w2 = winners[i + 1] if i + 1 < len(winners) else None
            is_bye = (w2 is None)
            next_matches.append({
                'event_id': event_id,
                'round_number': next_round,
                'match_number': match_num,
                'player1_id': w1['id'],
                'player1_guest_name': w1['guest_name'],
                'player1_reg_id': w1['reg_id'],
                'player2_id': w2['id'] if w2 else None,
                'player2_guest_name': w2['guest_name'] if w2 else None,
                'player2_reg_id': w2['reg_id'] if w2 else None,
                'status': 'completed' if is_bye else 'pending',
                'winner_id': w1['id'] if is_bye else None,
                'winner_guest_name': w1['guest_name'] if is_bye else None,
                'winner_reg_id': w1['reg_id'] if is_bye else None
            })
            match_num += 1

        if next_matches:
            db.table('tournament_matches').insert(next_matches).execute()
            if len(next_matches) == 1 and next_matches[0]['status'] == 'completed':
                _advance_bracket(db, event_id)
    except Exception as e:
        current_app.logger.error(f"Bracket advancement error: {e}")

@clubadmin_bp.route('/tournaments/<event_id>/matches/<match_id>/score', methods=['POST'])
@require_role('clubadmin')
def match_score(event_id, match_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db

    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    winner_side = request.form.get('winner_side') # 'player1' or 'player2'
    winner_id_param = request.form.get('winner_id')

    try:
        # Verify ownership
        admin_db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()

        # Get match before updating to pass to ratings logic
        m_resp = admin_db.table('tournament_matches').select('*').eq('id', match_id).single().execute()
        prev_match = m_resp.data
        if not prev_match:
            flash("Match not found.", "error")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

        is_p1_winner = False
        if winner_side == 'player1' or winner_id_param == 'player1' or (winner_id_param and winner_id_param == prev_match.get('player1_id')):
            is_p1_winner = True
        elif winner_side == 'player2' or winner_id_param == 'player2' or (winner_id_param and winner_id_param == prev_match.get('player2_id')):
            is_p1_winner = False
        else:
            is_p1_winner = (p1_score or 0) >= (p2_score or 0)

        winner_id = prev_match.get('player1_id') if is_p1_winner else prev_match.get('player2_id')
        winner_guest_name = prev_match.get('player1_guest_name') if is_p1_winner else prev_match.get('player2_guest_name')
        winner_reg_id = prev_match.get('player1_reg_id') if is_p1_winner else prev_match.get('player2_reg_id')

        admin_db.table('tournament_matches').update({
            'player1_score': p1_score,
            'player2_score': p2_score,
            'winner_id': winner_id,
            'winner_guest_name': winner_guest_name,
            'winner_reg_id': winner_reg_id,
            'status': 'completed',
            'played_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', match_id).eq('event_id', event_id).execute()

        # Calculate and update player ratings
        from app.ratings import update_match_ratings
        update_match_ratings(admin_db, match_id, prev_match=prev_match)

        _advance_bracket(admin_db, event_id)
        flash("Score recorded! Bracket and ratings updated.", "success")

    except Exception as e:
        current_app.logger.error(f"Error submitting match score: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/tournaments/<event_id>/matches/<match_id>/assign', methods=['POST'])
@require_role('clubadmin')
def match_assign(event_id, match_id):
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    
    court_id = request.form.get('court_id') or None
    court_name = request.form.get('court_name') or None
    referee_name = request.form.get('referee_name') or None
    
    if court_id and not court_name:
        try:
            c_resp = admin_db.table('courts').select('name').eq('id', court_id).single().execute()
            if c_resp.data:
                court_name = c_resp.data['name']
        except Exception as ce:
            current_app.logger.error(f"Failed to resolve court name: {ce}")

    try:
        # Verify ownership
        admin_db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        admin_db.table('tournament_matches').update({
            'court_id': court_id,
            'court_name': court_name,
            'referee_name': referee_name
        }).eq('id', match_id).eq('event_id', event_id).execute()
        
        flash("Match assignment updated.", "success")
    except Exception as e:
        current_app.logger.error(f"Error assigning match: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

@clubadmin_bp.route('/leaderboard')
@require_role('clubadmin')
def leaderboard():
    admin_id = session.get('user_id')
    db = get_db()
    admin_db = get_admin_db() or db
    rankings = []

    try:
        # Get all tournaments run by this admin
        ev_resp = admin_db.table('events').select('id').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        event_ids = [e['id'] for e in (ev_resp.data or [])]

        if event_ids:
            # Fetch all completed matches for these tournaments
            matches_resp = admin_db.table('tournament_matches').select(
                'player1_id, player2_id, winner_id, status'
            ).in_('event_id', event_ids).eq('status', 'completed').execute()
            matches = matches_resp.data or []

            # Aggregate per player
            stats = {}
            for m in matches:
                for pid in [m['player1_id'], m['player2_id']]:
                    if pid is None:
                        continue
                    if pid not in stats:
                        stats[pid] = {'wins': 0, 'losses': 0, 'played': 0}
                    stats[pid]['played'] += 1
                    if m['winner_id'] == pid:
                        stats[pid]['wins'] += 1
                    else:
                        stats[pid]['losses'] += 1

            if stats:
                player_ids = list(stats.keys())
                prof_resp = admin_db.table('profiles').select('id, first_name, last_name, elo, dupr, proficiency, avatar_url').in_('id', player_ids).execute()
                profiles_map = {p['id']: p for p in (prof_resp.data or [])}

                from app.ratings import get_initial_rating

                for pid, s in stats.items():
                    prof = profiles_map.get(pid, {})
                    
                    elo = prof.get('elo')
                    dupr = prof.get('dupr')
                    if elo is None or dupr is None:
                        elo_def, dupr_def = get_initial_rating(prof.get('proficiency'))
                        if elo is None: elo = elo_def
                        if dupr is None: dupr = dupr_def

                    win_rate = round((s['wins'] / s['played']) * 100) if s['played'] > 0 else 0
                    rankings.append({
                        'id': pid,
                        'name': f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip(),
                        'initials': ((prof.get('first_name') or ' ')[0] + (prof.get('last_name') or ' ')[0]).upper(),
                        'avatar_url': prof.get('avatar_url') or None,
                        'played': s['played'],
                        'wins': s['wins'],
                        'losses': s['losses'],
                        'win_rate': win_rate,
                        'elo': elo,
                        'dupr': dupr,
                    })

                rankings.sort(key=lambda x: (-x['elo'], -x['wins']))

    except Exception as e:
        current_app.logger.error(f"Error loading leaderboard: {e}")
        flash('An error occurred. Please try again.', 'error')

    return render_template('clubadmin/leaderboard.html', rankings=rankings)
