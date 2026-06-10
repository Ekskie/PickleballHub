-- supabase_migrations/011_matchmaker.sql

-- 1. SAFE CREATE TOURNAMENT MATCHES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tournament_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES public.events(id) ON DELETE CASCADE,
    round_number INTEGER,
    match_number INTEGER,
    player1_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    player2_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    winner_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    player1_score INTEGER,
    player2_score INTEGER,
    status TEXT DEFAULT 'pending',
    played_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS on tournament_matches if not already enabled
ALTER TABLE public.tournament_matches ENABLE ROW LEVEL SECURITY;

-- Add basic read policy if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'tournament_matches' AND policyname = 'Authenticated users can view tournament matches'
    ) THEN
        CREATE POLICY "Authenticated users can view tournament matches"
            ON public.tournament_matches FOR SELECT
            USING (auth.role() = 'authenticated');
    END IF;
END
$$;

-- 2. CREATE MATCHMAKER LOBBIES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.matchmaker_lobbies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    reservation_id UUID REFERENCES public.court_reservations(id) ON DELETE CASCADE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    min_dupr NUMERIC(3,2) NOT NULL DEFAULT 2.00,
    max_dupr NUMERIC(3,2) NOT NULL DEFAULT 8.00,
    slots_total INTEGER NOT NULL DEFAULT 3,
    slots_filled INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'full', 'completed', 'cancelled')),
    winner_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    score TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.matchmaker_lobbies ENABLE ROW LEVEL SECURITY;

-- Policies for matchmaker_lobbies
CREATE POLICY "Authenticated users can view matchmaker lobbies"
    ON public.matchmaker_lobbies FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Players can create matchmaker lobbies"
    ON public.matchmaker_lobbies FOR INSERT
    WITH CHECK (auth.uid() = creator_id);

CREATE POLICY "Creators can update own lobbies"
    ON public.matchmaker_lobbies FOR UPDATE
    USING (auth.uid() = creator_id)
    WITH CHECK (auth.uid() = creator_id);

CREATE POLICY "Creators can delete own lobbies"
    ON public.matchmaker_lobbies FOR DELETE
    USING (auth.uid() = creator_id);

-- 3. CREATE LOBBY PARTICIPANTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.lobby_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lobby_id UUID REFERENCES public.matchmaker_lobbies(id) ON DELETE CASCADE NOT NULL,
    player_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    status TEXT NOT NULL DEFAULT 'joined' CHECK (status IN ('joined', 'cancelled')),
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(lobby_id, player_id)
);

ALTER TABLE public.lobby_participants ENABLE ROW LEVEL SECURITY;

-- Policies for lobby_participants
CREATE POLICY "Authenticated users can view lobby participants"
    ON public.lobby_participants FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Players can join lobbies"
    ON public.lobby_participants FOR INSERT
    WITH CHECK (auth.uid() = player_id);

CREATE POLICY "Players can leave/update their own participation"
    ON public.lobby_participants FOR UPDATE
    USING (auth.uid() = player_id)
    WITH CHECK (auth.uid() = player_id);

CREATE POLICY "Players can remove their participation"
    ON public.lobby_participants FOR DELETE
    USING (auth.uid() = player_id);

CREATE POLICY "Lobby creators can manage participants"
    ON public.lobby_participants FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.matchmaker_lobbies l
            WHERE l.id = lobby_id AND l.creator_id = auth.uid()
        )
    );
