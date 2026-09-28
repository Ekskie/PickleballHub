-- ============================================================
-- 022_add_amenities_to_facilities.sql
-- Add JSONB amenities column to facilities
-- Run this in your Supabase SQL Editor
-- ============================================================

ALTER TABLE public.facilities
    ADD COLUMN IF NOT EXISTS amenities JSONB DEFAULT '[]'::jsonb;
