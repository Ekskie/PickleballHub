-- supabase_migrations/016_club_memberships_fields.sql
-- Add fields for receipt upload verification and membership expiration tracking

-- 1. Add columns to club_memberships
ALTER TABLE public.club_memberships
    ADD COLUMN IF NOT EXISTS receipt_url TEXT,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- 2. Add columns to clubs
ALTER TABLE public.clubs
    ADD COLUMN IF NOT EXISTS membership_duration TEXT DEFAULT 'lifetime';
