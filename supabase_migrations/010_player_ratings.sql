-- ============================================================
-- PickleballHub: Player Elo & DUPR Rating System Migration
-- Run this in your Supabase SQL Editor
-- ============================================================

-- 1. Add Elo and DUPR columns to the profiles table
ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS elo integer DEFAULT 1200,
    ADD COLUMN IF NOT EXISTS dupr numeric(3,2) DEFAULT 3.00;

-- 2. Create rating_history table to track player rating progression
CREATE TABLE IF NOT EXISTS public.rating_history (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id   uuid REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    match_id    uuid REFERENCES public.tournament_matches(id) ON DELETE CASCADE, -- Nullable for manual/initial seeding
    elo         integer NOT NULL,
    dupr        numeric(3,2) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE public.rating_history ENABLE ROW LEVEL SECURITY;

-- 4. Create Policies for rating_history
-- Authenticated users can view any player's rating history (used for charts and profiles)
CREATE POLICY "Authenticated users can view rating history"
    ON public.rating_history FOR SELECT
    USING (auth.role() = 'authenticated');

-- 5. Add index for quick queries on player_id
CREATE INDEX IF NOT EXISTS idx_rating_history_player ON public.rating_history(player_id);
CREATE INDEX IF NOT EXISTS idx_rating_history_recorded_at ON public.rating_history(recorded_at);
