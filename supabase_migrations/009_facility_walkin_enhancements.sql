-- ============================================================
-- PickleballHub: Facility, Walk-in, and Map Enhancements
-- Run this in your Supabase SQL Editor
-- ============================================================

-- 1. FACILITIES TABLE
-- ============================================================
ALTER TABLE public.facilities
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS latitude NUMERIC,
    ADD COLUMN IF NOT EXISTS longitude NUMERIC;

-- 2. COURT_RESERVATIONS TABLE
-- ============================================================
-- Allow player_id to be NULL for walk-ins
ALTER TABLE public.court_reservations
    ALTER COLUMN player_id DROP NOT NULL;

ALTER TABLE public.court_reservations
    ADD COLUMN IF NOT EXISTS guest_name TEXT,
    ADD COLUMN IF NOT EXISTS guest_phone TEXT,
    ADD COLUMN IF NOT EXISTS party_size INTEGER NOT NULL DEFAULT 1;

-- 3. COURT_QUEUES TABLE
-- ============================================================
-- Allow player_id to be NULL for walk-ins
ALTER TABLE public.court_queues
    ALTER COLUMN player_id DROP NOT NULL;

ALTER TABLE public.court_queues
    ADD COLUMN IF NOT EXISTS guest_name TEXT,
    ADD COLUMN IF NOT EXISTS party_size INTEGER NOT NULL DEFAULT 1;
