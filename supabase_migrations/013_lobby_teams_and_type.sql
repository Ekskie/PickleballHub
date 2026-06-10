-- supabase_migrations/013_lobby_teams_and_type.sql
-- Run this in your Supabase SQL Editor to support matchmaking teams and casual/ranked play.

-- 1. Add match_type to matchmaker_lobbies (default is 'ranked')
ALTER TABLE public.matchmaker_lobbies 
    ADD COLUMN IF NOT EXISTS match_type TEXT DEFAULT 'ranked' CHECK (match_type IN ('ranked', 'casual'));

-- 2. Add team and slot columns to lobby_participants
-- team can be 1 (Team 1) or 2 (Team 2)
-- slot can be 1 (Slot 1) or 2 (Slot 2)
ALTER TABLE public.lobby_participants 
    ADD COLUMN IF NOT EXISTS team INTEGER DEFAULT 2 CHECK (team IN (1, 2)),
    ADD COLUMN IF NOT EXISTS slot INTEGER DEFAULT 1 CHECK (slot IN (1, 2));
