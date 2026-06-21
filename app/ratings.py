from datetime import datetime, timezone

def elo_to_dupr(elo):
    """Linearly map Elo rating to DUPR scale (2.00 to 8.00)."""
    dupr = 2.0 + (elo - 800) / 400.0
    return round(max(2.0, min(8.0, dupr)), 2)

def get_initial_rating(proficiency):
    """Get the baseline Elo and DUPR ratings based on registered proficiency."""
    prof = (proficiency or 'beginner').lower().strip()
    if prof == 'beginner':
        return 1000, 2.50
    elif prof == 'intermediate':
        return 1400, 3.50
    elif prof == 'advanced':
        return 1800, 4.50
    elif prof == 'pro':
        return 2200, 5.50
    else:
        return 1200, 3.00

def init_player_rating(db, player_id, proficiency):
    """Lazy initialization of a player's profile Elo/DUPR if columns are null."""
    elo, dupr = get_initial_rating(proficiency)
    try:
        db.table('profiles').update({'elo': elo, 'dupr': dupr}).eq('id', player_id).execute()
    except Exception as e:
        print(f"[init_player_rating] Failed to update profile rating for user {player_id}: {e}")
    return elo, dupr

def ensure_initial_history(db, player_id, elo, dupr, recorded_at):
    """Create a baseline history record if the player has no rating history logs."""
    try:
        resp = db.table('rating_history').select('id').eq('player_id', player_id).limit(1).execute()
        if not resp.data:
            # Set baseline slightly older than the first match
            db.table('rating_history').insert({
                'player_id': player_id,
                'match_id': None,
                'elo': elo,
                'dupr': dupr,
                'recorded_at': recorded_at
            }).execute()
    except Exception as e:
        print(f"[ensure_initial_history] Failed to ensure initial history for user {player_id}: {e}")

def adjust_profile_stats(db, player_id, wins_change, losses_change):
    """Increment/decrement wins and losses on the player profile safely."""
    if not player_id:
        return
    try:
        p_resp = db.table('profiles').select('wins, losses').eq('id', player_id).single().execute()
        if p_resp.data:
            # Support fallback if columns don't exist yet in the database
            if 'wins' in p_resp.data and 'losses' in p_resp.data:
                current_wins = p_resp.data.get('wins') or 0
                current_losses = p_resp.data.get('losses') or 0
                db.table('profiles').update({
                    'wins': max(0, current_wins + wins_change),
                    'losses': max(0, current_losses + losses_change)
                }).eq('id', player_id).execute()
    except Exception as e:
        print(f"[adjust_profile_stats] Failed to adjust wins/losses for {player_id}: {e}")

def update_match_ratings(db, match_id, prev_match=None):
    """Recalculate ratings for players of a match and write to profiles and history."""
    try:
        # 1. Fetch match record
        match_resp = db.table('tournament_matches').select('*').eq('id', match_id).single().execute()
        match = match_resp.data
        if not match or not match.get('winner_id') or match.get('status') != 'completed':
            return
            
        p1_id = match.get('player1_id')
        p2_id = match.get('player2_id')
        winner_id = match.get('winner_id')
        
        # If it's a bye (missing one player), no rating changes
        if not p1_id or not p2_id:
            return
            
        # 2. Fetch player profiles
        p1_resp = db.table('profiles').select('*').eq('id', p1_id).single().execute()
        p2_resp = db.table('profiles').select('*').eq('id', p2_id).single().execute()
        p1 = p1_resp.data
        p2 = p2_resp.data
        
        if not p1 or not p2:
            return
            
        # 3. Get current ratings, fallback if null
        r1_elo = p1.get('elo')
        r1_dupr = p1.get('dupr')
        if r1_elo is None or r1_dupr is None:
            r1_elo, r1_dupr = init_player_rating(db, p1_id, p1.get('proficiency'))
            
        r2_elo = p2.get('elo')
        r2_dupr = p2.get('dupr')
        if r2_elo is None or r2_dupr is None:
            r2_elo, r2_dupr = init_player_rating(db, p2_id, p2.get('proficiency'))
            
        # 4. Calculate expected outcomes (Elo formulas)
        expected1 = 1.0 / (1.0 + 10.0 ** ((r2_elo - r1_elo) / 400.0))
        expected2 = 1.0 - expected1
        
        # 5. Determine actual scores
        if winner_id == p1_id:
            actual1 = 1.0
            actual2 = 0.0
        elif winner_id == p2_id:
            actual1 = 0.0
            actual2 = 1.0
        else:
            actual1 = 0.5
            actual2 = 0.5
            
        # 6. Calculate new ratings (K = 32)
        new_elo1 = round(r1_elo + 32 * (actual1 - expected1))
        new_elo2 = round(r2_elo + 32 * (actual2 - expected2))
        
        # Convert to DUPR
        new_dupr1 = elo_to_dupr(new_elo1)
        new_dupr2 = elo_to_dupr(new_elo2)
        
        # 7. Calculate wins and losses changes (including prev_match rollback if needed)
        p1_wins, p1_losses = (1, 0) if winner_id == p1_id else ((0, 1) if winner_id == p2_id else (0, 0))
        p2_wins, p2_losses = (0, 1) if winner_id == p1_id else ((1, 0) if winner_id == p2_id else (0, 0))
        
        p1_wins_change = p1_wins
        p1_losses_change = p1_losses
        p2_wins_change = p2_wins
        p2_losses_change = p2_losses
        
        if prev_match and prev_match.get('stats_applied'):
            prev_winner = prev_match.get('winner_id')
            prev_loser = p2_id if prev_winner == p1_id else (p1_id if prev_winner == p2_id else None)
            
            if prev_winner == p1_id:
                p1_wins_change -= 1
            elif prev_winner == p2_id:
                p2_wins_change -= 1
                
            if prev_loser == p1_id:
                p1_losses_change -= 1
            elif prev_loser == p2_id:
                p2_losses_change -= 1

        match_created = match.get('created_at') or datetime.now(timezone.utc).isoformat()
        played_at = match.get('played_at') or datetime.now(timezone.utc).isoformat()

        # Get initial ELO values in case history is missing
        p1_init_elo, p1_init_dupr = get_initial_rating(p1.get('proficiency'))
        p2_init_elo, p2_init_dupr = get_initial_rating(p2.get('proficiency'))

        # 8. Execute Postgres transaction RPC
        db.rpc('apply_match_ratings_rpc', {
            'p_match_id': match_id,
            'p_p1_id': p1_id,
            'p_p2_id': p2_id,
            'p1_elo': new_elo1,
            'p1_dupr': new_dupr1,
            'p2_elo': new_elo2,
            'p2_dupr': new_dupr2,
            'p1_wins_change': p1_wins_change,
            'p1_losses_change': p1_losses_change,
            'p2_wins_change': p2_wins_change,
            'p2_losses_change': p2_losses_change,
            'p_played_at': played_at,
            'p_match_created': match_created,
            'p1_initial_elo': p1_init_elo,
            'p1_initial_dupr': p1_init_dupr,
            'p2_initial_elo': p2_init_elo,
            'p2_initial_dupr': p2_init_dupr
        }).execute()
        
    except Exception as e:
        print(f"[update_match_ratings] Failed to update match ratings for match {match_id}: {e}")

def update_matchmaker_ratings(db, lobby_id):
    """Recalculate ratings for players of a matchmaking lobby (Team 1 vs Team 2)."""
    try:
        # 1. Fetch lobby record
        lob_resp = db.table('matchmaker_lobbies').select('*').eq('id', lobby_id).single().execute()
        lobby = lob_resp.data
        if not lobby or not lobby.get('winner_id') or lobby.get('status') != 'completed':
            return
            
        # If casual play, do not update ratings!
        if lobby.get('match_type') == 'casual':
            print(f"[update_matchmaker_ratings] Skipping ratings update for casual lobby {lobby_id}")
            return
            
        host_id = lobby.get('creator_id')
        winner_id = lobby.get('winner_id')
        played_at = lobby.get('created_at') or datetime.now(timezone.utc).isoformat()
        
        # 2. Fetch joined participants with their team/slot info
        part_resp = db.table('lobby_participants').select('player_id, team, slot').eq('lobby_id', lobby_id).eq('status', 'joined').execute()
        participants = part_resp.data or []
        
        # 3. Group players into Team 1 and Team 2
        # Team 1: Host (always) + any participant on team 1
        team1_ids = [host_id]
        team2_ids = []
        for p in participants:
            if p.get('team') == 1:
                team1_ids.append(p['player_id'])
            elif p.get('team') == 2:
                team2_ids.append(p['player_id'])
                
        # Determine who won
        team1_won = winner_id in team1_ids
        
        # 4. Fetch profiles for all players
        all_player_ids = team1_ids + team2_ids
        prof_resp = db.table('profiles').select('id, elo, dupr, proficiency').in_('id', all_player_ids).execute()
        profiles = {p['id']: p for p in (prof_resp.data or [])}
        
        # Initialize ratings if null
        for pid in all_player_ids:
            if pid not in profiles:
                continue
            p = profiles[pid]
            if p.get('elo') is None or p.get('dupr') is None:
                elo, dupr = init_player_rating(db, pid, p.get('proficiency'))
                p['elo'] = elo
                p['dupr'] = dupr
                
        # 5. Calculate Team Average Elo
        t1_elos = [profiles[pid]['elo'] for pid in team1_ids if pid in profiles]
        t2_elos = [profiles[pid]['elo'] for pid in team2_ids if pid in profiles]
        
        if not t1_elos or not t2_elos:
            return
            
        avg_elo1 = sum(t1_elos) / len(t1_elos)
        avg_elo2 = sum(t2_elos) / len(t2_elos)
        
        # Calculate expected outcome
        expected1 = 1.0 / (1.0 + 10.0 ** ((avg_elo2 - avg_elo1) / 400.0))
        expected2 = 1.0 - expected1
        
        actual1 = 1.0 if team1_won else 0.0
        actual2 = 1.0 - actual1
        
        # 6. Build ELO update arrays
        player_ids = []
        new_elos = []
        new_duprs = []
        wins_changes = []
        losses_changes = []
        old_elos = []
        old_duprs = []
        
        for pid in team1_ids:
            if pid not in profiles:
                continue
            p = profiles[pid]
            old_elo = p['elo']
            old_dupr = p['dupr']
            
            new_elo = round(old_elo + 32 * (actual1 - expected1))
            new_dupr = elo_to_dupr(new_elo)
            
            player_ids.append(pid)
            new_elos.append(new_elo)
            new_duprs.append(new_dupr)
            old_elos.append(old_elo)
            old_duprs.append(old_dupr)
            
            if not lobby.get('stats_applied'):
                wins_changes.append(1 if team1_won else 0)
                losses_changes.append(0 if team1_won else 1)
            else:
                wins_changes.append(0)
                losses_changes.append(0)
                
        # 7. Apply updates for Team 2
        for pid in team2_ids:
            if pid not in profiles:
                continue
            p = profiles[pid]
            old_elo = p['elo']
            old_dupr = p['dupr']
            
            new_elo = round(old_elo + 32 * (actual2 - expected2))
            new_dupr = elo_to_dupr(new_elo)
            
            player_ids.append(pid)
            new_elos.append(new_elo)
            new_duprs.append(new_dupr)
            old_elos.append(old_elo)
            old_duprs.append(old_dupr)
            
            if not lobby.get('stats_applied'):
                wins_changes.append(0 if team1_won else 1)
                losses_changes.append(1 if team1_won else 0)
            else:
                wins_changes.append(0)
                losses_changes.append(0)
                
        # 8. Execute Postgres transaction RPC for matchmaking lobby ELO updates
        db.rpc('apply_matchmaker_ratings_rpc', {
            'p_lobby_id': lobby_id,
            'p_player_ids': player_ids,
            'p_new_elos': new_elos,
            'p_new_duprs': new_duprs,
            'p_wins_changes': wins_changes,
            'p_losses_changes': losses_changes,
            'p_played_at': played_at,
            'p_old_elos': old_elos,
            'p_old_duprs': old_duprs
        }).execute()
            
    except Exception as e:
        print(f"[update_matchmaker_ratings] Failed to update matchmaker ratings for lobby {lobby_id}: {e}")
