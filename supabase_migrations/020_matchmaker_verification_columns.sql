-- ============================================================
-- PickleballHub: Matchmaker Score Verification Schema Updates
-- ============================================================

-- 1. Drop old status check constraint if it exists
ALTER TABLE public.matchmaker_lobbies 
    DROP CONSTRAINT IF EXISTS matchmaker_lobbies_status_check;

-- 2. Add updated status check constraint supporting 'pending_verification'
ALTER TABLE public.matchmaker_lobbies 
    ADD CONSTRAINT matchmaker_lobbies_status_check 
    CHECK (status IN ('open', 'full', 'pending_verification', 'completed', 'cancelled'));

-- 3. Add reported metrics columns
ALTER TABLE public.matchmaker_lobbies 
    ADD COLUMN IF NOT EXISTS reported_score TEXT,
    ADD COLUMN IF NOT EXISTS reported_winner_id UUID REFERENCES public.profiles(id),
    ADD COLUMN IF NOT EXISTS reporter_id UUID REFERENCES public.profiles(id),
    ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'pending' 
        CHECK (verification_status IN ('pending', 'verified', 'disputed'));
