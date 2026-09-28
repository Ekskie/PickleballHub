-- supabase_migrations/023_add_banner_url_to_clubs.sql
-- Add banner_url column for club cover photo / banner background

ALTER TABLE public.clubs
    ADD COLUMN IF NOT EXISTS banner_url TEXT;
