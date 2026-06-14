-- supabase_migrations/017_tournament_bracket_court_attendance.sql
-- Run this in your Supabase SQL Editor to support tournament bracket court assignments and check-in attendance.

-- 1. Alter event_registrations table for attendance tracking
ALTER TABLE public.event_registrations 
    ADD COLUMN IF NOT EXISTS check_in_status TEXT DEFAULT 'pending' CHECK (check_in_status IN ('pending', 'checked_in', 'no_show')),
    ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ DEFAULT NULL;

-- 2. Alter tournament_matches table for referee and custom court name details
ALTER TABLE public.tournament_matches
    ADD COLUMN IF NOT EXISTS court_name TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS referee_name TEXT DEFAULT NULL;
