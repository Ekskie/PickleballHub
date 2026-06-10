-- supabase_migrations/014_profile_avatar_url.sql
-- Run this in your Supabase SQL Editor to support profile avatars.

ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS avatar_url TEXT;
