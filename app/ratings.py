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

def update_match_ratings(db, match_id):
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
        
        # 7. Update profiles
        db.table('profiles').update({'elo': new_elo1, 'dupr': new_dupr1}).eq('id', p1_id).execute()
        db.table('profiles').update({'elo': new_elo2, 'dupr': new_dupr2}).eq('id', p2_id).execute()
        
        # 8. Record history
        match_created = match.get('created_at') or datetime.now(timezone.utc).isoformat()
        ensure_initial_history(db, p1_id, r1_elo, r1_dupr, match_created)
        ensure_initial_history(db, p2_id, r2_elo, r2_dupr, match_created)
        
        played_at = match.get('played_at') or datetime.now(timezone.utc).isoformat()
        
        db.table('rating_history').insert({
            'player_id': p1_id,
            'match_id': match_id,
            'elo': new_elo1,
            'dupr': new_dupr1,
            'recorded_at': played_at
        }).execute()
        
        db.table('rating_history').insert({
            'player_id': p2_id,
            'match_id': match_id,
            'elo': new_elo2,
            'dupr': new_dupr2,
            'recorded_at': played_at
        }).execute()
        
    except Exception as e:
        print(f"[update_match_ratings] Failed to update match ratings for match {match_id}: {e}")
