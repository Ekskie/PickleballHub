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

@clubadmin_bp.route('/tournaments/<event_id>/manage')
@require_role('clubadmin')
def tournament_manage(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        ev_resp = db.table('events').select('*').eq('id', event_id).eq('organizer_id', admin_id).eq('type', 'tournament').single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('clubadmin.tournaments'))
            
        # Get all tournaments for dropdown
        all_t_resp = db.table('events').select('id, title').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        all_tournaments = all_t_resp.data or []
        
        # Get participants
        reg_resp = db.table('event_registrations').select(
            'player_id, profiles!player_id(first_name, last_name)'
        ).eq('event_id', event_id).eq('status', 'registered').execute()
        participants = reg_resp.data or []
        
        # Get matches
        matches_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, court_id, court_name, referee_name, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = matches_resp.data or []
        
        # Get booked courts for this event
        court_resp = db.table('event_courts').select(
            'court_id, courts(id, name)'
        ).eq('event_id', event_id).execute()
        booked_courts = court_resp.data or []
        
        has_bracket = len(matches) > 0
        
        return render_template('clubadmin/tournament_manage.html', 
                               event=event, 
                               all_tournaments=all_tournaments,
                               participants=participants,
                               matches=matches,
                               has_bracket=has_bracket,
                               booked_courts=booked_courts)
                               
    except Exception as e:
        current_app.logger.error(f"Error managing tournament {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('clubadmin.tournaments'))

@clubadmin_bp.route('/tournaments/<event_id>/bracket/generate', methods=['POST'])
@require_role('clubadmin')
def bracket_generate(event_id):
    admin_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        # Get participants
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
        players = [r['player_id'] for r in (reg_resp.data or [])]
        
        if len(players) < 2:
            flash("Not enough players to generate a bracket.", "warning")
            return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))
            
        random.shuffle(players)
        
        matches_to_insert = []
        match_num = 1
        for i in range(0, len(players), 2):
            p1 = players[i]
            p2 = players[i+1] if i+1 < len(players) else None
            
            matches_to_insert.append({
                'event_id': event_id,
                'round_number': 1,
                'match_number': match_num,
                'player1_id': p1,
                'player2_id': p2,
                'status': 'pending' if p2 else 'completed',
                'winner_id': p1 if not p2 else None # Bye
            })
            match_num += 1
            
        if matches_to_insert:
            db.table('tournament_matches').insert(matches_to_insert).execute()
            
        flash("Bracket generated successfully!", "success")
        
    except Exception as e:
        current_app.logger.error(f"Error generating tournament bracket {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('clubadmin.tournament_manage', event_id=event_id))

def _advance_bracket(db, event_id):
    """Check current round completion and auto-generate next round or declare champion."""
    try:
        all_m = db.table('tournament_matches').select(
            'id, round_number, status, winner_id'
        ).eq('event_id', event_id).order('round_number').execute()
        matches = all_m.data or []
        if not matches:
            return

        max_round = max(m['round_number'] for m in matches)
        round_matches = [m for m in matches if m['round_number'] == max_round]

        if any(m['status'] != 'completed' for m in round_matches):
            return

        winners = [m['winner_id'] for m in round_matches if m['winner_id']]

        if len(winners) == 1:
            db.table('events').update({'status': 'completed'}).eq('id', event_id).execute()
            try:
                db.table('notifications').insert({
                    'user_id': winners[0],
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
            p1 = winners[i]
            p2 = winners[i + 1] if i + 1 < len(winners) else None
            next_matches.append({
                'event_id': event_id,
                'round_number': next_round,
                'match_number': match_num,
                'player1_id': p1,
                'player2_id': p2,
                'status': 'completed' if not p2 else 'pending',
                'winner_id': p1 if not p2 else None,
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

    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    winner_id = request.form.get('winner_id') or None

    try:
        # Verify ownership
        db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()

        # Get match before updating to pass to ratings logic
        prev_match = None
        try:
            m_resp = db.table('tournament_matches').select('*').eq('id', match_id).single().execute()
            prev_match = m_resp.data
        except Exception:
            pass

        db.table('tournament_matches').update({
            'player1_score': p1_score,
            'player2_score': p2_score,
            'winner_id': winner_id,
            'status': 'completed',
            'played_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', match_id).eq('event_id', event_id).execute()

        # Calculate and update player ratings
        from app.ratings import update_match_ratings
        update_match_ratings(db, match_id, prev_match=prev_match)

        _advance_bracket(db, event_id)
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
    
    court_id = request.form.get('court_id') or None
    court_name = request.form.get('court_name') or None
    referee_name = request.form.get('referee_name') or None
    
    if court_id and not court_name:
        try:
            c_resp = db.table('courts').select('name').eq('id', court_id).single().execute()
            if c_resp.data:
                court_name = c_resp.data['name']
        except Exception as ce:
            current_app.logger.error(f"Failed to resolve court name: {ce}")

    try:
        # Verify ownership
        db.table('events').select('id').eq('id', event_id).eq('organizer_id', admin_id).single().execute()
        
        db.table('tournament_matches').update({
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
    rankings = []

    try:
        # Get all tournaments run by this admin
        ev_resp = db.table('events').select('id').eq('organizer_id', admin_id).eq('type', 'tournament').execute()
        event_ids = [e['id'] for e in (ev_resp.data or [])]

        if event_ids:
            # Fetch all completed matches for these tournaments
            matches_resp = db.table('tournament_matches').select(
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
                prof_resp = db.table('profiles').select('id, first_name, last_name, elo, dupr, proficiency, avatar_url').in_('id', player_ids).execute()
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
