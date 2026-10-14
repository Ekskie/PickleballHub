-- ============================================================
-- 031_tournament_walkins_and_ranked_settings.sql
-- PickleballHub: Tournament Walk-in Players, Ranked Settings & Single Player Rating RPC
-- ============================================================

-- 1. Add ranked setting to events table
ALTER TABLE public.events
    ADD COLUMN IF NOT EXISTS is_ranked BOOLEAN NOT NULL DEFAULT true;

-- 2. Allow walk-in players in event_registrations (player_id nullable for walk-ins)
ALTER TABLE public.event_registrations
    ALTER COLUMN player_id DROP NOT NULL;

ALTER TABLE public.event_registrations
    ADD COLUMN IF NOT EXISTS is_walkin BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS guest_name TEXT,
    ADD COLUMN IF NOT EXISTS skill_level TEXT DEFAULT 'intermediate',
    ADD COLUMN IF NOT EXISTS estimated_elo INTEGER DEFAULT 1400;

-- 3. Add walk-in and registration tracking to tournament_matches
ALTER TABLE public.tournament_matches
    ADD COLUMN IF NOT EXISTS player1_guest_name TEXT,
    ADD COLUMN IF NOT EXISTS player2_guest_name TEXT,
    ADD COLUMN IF NOT EXISTS winner_guest_name TEXT,
    ADD COLUMN IF NOT EXISTS player1_reg_id UUID REFERENCES public.event_registrations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS player2_reg_id UUID REFERENCES public.event_registrations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS winner_reg_id UUID REFERENCES public.event_registrations(id) ON DELETE SET NULL;

-- 4. Create RPC to apply match rating updates for a single registered player (e.g. against a walk-in)
CREATE OR REPLACE FUNCTION public.apply_single_player_match_rating_rpc(
    p_match_id UUID,
    p_player_id UUID,
    p_elo INTEGER,
    p_dupr NUMERIC,
    p_wins_change INTEGER,
    p_losses_change INTEGER,
    p_played_at TIMESTAMPTZ,
    p_initial_elo INTEGER,
    p_initial_dupr NUMERIC
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Ensure initial history exists if player has no history
    IF NOT EXISTS (SELECT 1 FROM public.rating_history WHERE player_id = p_player_id) THEN
        INSERT INTO public.rating_history (player_id, match_id, elo, dupr, recorded_at)
        VALUES (p_player_id, NULL, p_initial_elo, p_initial_dupr, p_played_at - INTERVAL '1 minute');
    END IF;

    -- Update player's profile
    UPDATE public.profiles
    SET 
        elo = p_elo,
        dupr = p_dupr,
        wins = GREATEST(0, COALESCE(wins, 0) + p_wins_change),
        losses = GREATEST(0, COALESCE(losses, 0) + p_losses_change)
    WHERE id = p_player_id;

    -- Record rating history entry
    INSERT INTO public.rating_history (player_id, match_id, elo, dupr, recorded_at)
    VALUES (p_player_id, p_match_id, p_elo, p_dupr, p_played_at);

    -- Mark match stats as applied
    UPDATE public.tournament_matches
    SET stats_applied = TRUE
    WHERE id = p_match_id;
END;
$$;

-- 5. Add RLS policies for Organizers to manage registrations and matches for their own events
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'event_registrations' AND policyname = 'Organizers can manage registrations for own events'
    ) THEN
        CREATE POLICY "Organizers can manage registrations for own events"
            ON public.event_registrations FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM public.events e
                    WHERE e.id = event_registrations.event_id AND e.organizer_id = auth.uid()
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM public.events e
                    WHERE e.id = event_registrations.event_id AND e.organizer_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'tournament_matches' AND policyname = 'Organizers can manage matches for own events'
    ) THEN
        CREATE POLICY "Organizers can manage matches for own events"
            ON public.tournament_matches FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM public.events e
                    WHERE e.id = tournament_matches.event_id AND e.organizer_id = auth.uid()
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM public.events e
                    WHERE e.id = tournament_matches.event_id AND e.organizer_id = auth.uid()
                )
            );
    END IF;
END $$;

