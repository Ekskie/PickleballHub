-- 024_fix_tournament_matches_delete_cascade.sql
-- Ensure tournament_matches references to player profiles are ON DELETE SET NULL
-- so player deletion cascades cleanly without foreign key constraint violations.

DO $$
BEGIN
    -- Player 1 foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'tournament_matches_player1_id_fkey'
    ) THEN
        ALTER TABLE public.tournament_matches DROP CONSTRAINT tournament_matches_player1_id_fkey;
    END IF;
    ALTER TABLE public.tournament_matches 
        ADD CONSTRAINT tournament_matches_player1_id_fkey 
        FOREIGN KEY (player1_id) REFERENCES public.profiles(id) ON DELETE SET NULL;

    -- Player 2 foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'tournament_matches_player2_id_fkey'
    ) THEN
        ALTER TABLE public.tournament_matches DROP CONSTRAINT tournament_matches_player2_id_fkey;
    END IF;
    ALTER TABLE public.tournament_matches 
        ADD CONSTRAINT tournament_matches_player2_id_fkey 
        FOREIGN KEY (player2_id) REFERENCES public.profiles(id) ON DELETE SET NULL;

    -- Winner foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'tournament_matches_winner_id_fkey'
    ) THEN
        ALTER TABLE public.tournament_matches DROP CONSTRAINT tournament_matches_winner_id_fkey;
    END IF;
    ALTER TABLE public.tournament_matches 
        ADD CONSTRAINT tournament_matches_winner_id_fkey 
        FOREIGN KEY (winner_id) REFERENCES public.profiles(id) ON DELETE SET NULL;
END $$;
