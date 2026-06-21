from flask import render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app.db import get_db
from app.player import player_bp

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
        flash('An error occurred. Please try again.', 'error')

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
        flash('An error occurred. Please try again.', 'error')
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
        flash('An error occurred. Please try again.', 'error')
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
