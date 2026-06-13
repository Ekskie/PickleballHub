-- supabase_migrations/015_profile_wins_losses.sql
-- Run this in your Supabase SQL Editor to support persistent profiles wins and losses.

-- 1. Add wins and losses columns to public.profiles table
ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS wins INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS losses INTEGER DEFAULT 0;

-- 2. Add stats_applied column to matches and lobbies
ALTER TABLE public.tournament_matches
    ADD COLUMN IF NOT EXISTS stats_applied BOOLEAN DEFAULT FALSE;

ALTER TABLE public.matchmaker_lobbies
    ADD COLUMN IF NOT EXISTS stats_applied BOOLEAN DEFAULT FALSE;

-- 3. Populate initial wins and losses for existing completed matches/lobbies and mark them as applied
-- Reset everyone to 0 first
UPDATE public.profiles SET wins = 0, losses = 0 WHERE role = 'player';

-- Calculate tournament wins
WITH tournament_wins AS (
    SELECT winner_id, COUNT(*) as win_count
    FROM public.tournament_matches
    WHERE status = 'completed' AND winner_id IS NOT NULL
    GROUP BY winner_id
)
UPDATE public.profiles p
SET wins = wins + tw.win_count
FROM tournament_wins tw
WHERE p.id = tw.winner_id;

-- Calculate tournament losses
WITH tournament_losses AS (
    SELECT pid, COUNT(*) as loss_count
    FROM (
        SELECT player1_id AS pid FROM public.tournament_matches WHERE status = 'completed' AND winner_id != player1_id AND player1_id IS NOT NULL
        UNION ALL
        SELECT player2_id AS pid FROM public.tournament_matches WHERE status = 'completed' AND winner_id != player2_id AND player2_id IS NOT NULL
    ) sub
    GROUP BY pid
)
UPDATE public.profiles p
SET losses = losses + tl.loss_count
FROM tournament_losses tl
WHERE p.id = tl.pid;

-- Calculate matchmaker wins (host and teammates)
WITH matchmaker_wins AS (
    SELECT pid, COUNT(*) as win_count
    FROM (
        -- Host won (winner is host)
        SELECT l.creator_id AS pid 
        FROM public.matchmaker_lobbies l
        WHERE l.status = 'completed' AND l.winner_id = l.creator_id
        
        UNION ALL
        
        -- Participant on Team 1 won (same team as host)
        SELECT p.player_id AS pid
        FROM public.lobby_participants p
        JOIN public.matchmaker_lobbies l ON p.lobby_id = l.id
        WHERE l.status = 'completed' AND p.status = 'joined' AND l.winner_id = l.creator_id AND p.team = 1
        
        UNION ALL
        
        -- Participant on Team 2 won (winner is on Team 2)
        SELECT p.player_id AS pid
        FROM public.lobby_participants p
        JOIN public.matchmaker_lobbies l ON p.lobby_id = l.id
        WHERE l.status = 'completed' AND p.status = 'joined' AND l.winner_id != l.creator_id AND p.team = 2
    ) sub
    GROUP BY pid
)
UPDATE public.profiles p
SET wins = wins + mw.win_count
FROM matchmaker_wins mw
WHERE p.id = mw.pid;

-- Calculate matchmaker losses
WITH matchmaker_losses AS (
    SELECT pid, COUNT(*) as loss_count
    FROM (
        -- Host lost
        SELECT l.creator_id AS pid 
        FROM public.matchmaker_lobbies l
        WHERE l.status = 'completed' AND l.winner_id != l.creator_id
        
        UNION ALL
        
        -- Participant on Team 1 lost (winner is Team 2)
        SELECT p.player_id AS pid
        FROM public.lobby_participants p
        JOIN public.matchmaker_lobbies l ON p.lobby_id = l.id
        WHERE l.status = 'completed' AND p.status = 'joined' AND l.winner_id != l.creator_id AND p.team = 1
        
        UNION ALL
        
        -- Participant on Team 2 lost (winner is Team 1)
        SELECT p.player_id AS pid
        FROM public.lobby_participants p
        JOIN public.matchmaker_lobbies l ON p.lobby_id = l.id
        WHERE l.status = 'completed' AND p.status = 'joined' AND l.winner_id = l.creator_id AND p.team = 2
    ) sub
    GROUP BY pid
)
UPDATE public.profiles p
SET losses = losses + ml.loss_count
FROM matchmaker_losses ml
WHERE p.id = ml.pid;

-- Mark existing completed matches/lobbies as applied
UPDATE public.tournament_matches SET stats_applied = TRUE WHERE status = 'completed';
UPDATE public.matchmaker_lobbies SET stats_applied = TRUE WHERE status = 'completed';
