-- 1. Add dispute_count column
ALTER TABLE public.matchmaker_lobbies 
    ADD COLUMN IF NOT EXISTS dispute_count INT DEFAULT 0;

-- 2. Drop old status check constraint
ALTER TABLE public.matchmaker_lobbies 
    DROP CONSTRAINT IF EXISTS matchmaker_lobbies_status_check;

-- 3. Add updated status check constraint supporting 'staff_mediation'
ALTER TABLE public.matchmaker_lobbies 
    ADD CONSTRAINT matchmaker_lobbies_status_check 
    CHECK (status IN ('open', 'full', 'pending_verification', 'completed', 'cancelled', 'staff_mediation'));
