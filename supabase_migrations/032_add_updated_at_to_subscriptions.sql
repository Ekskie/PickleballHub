-- 032_add_updated_at_to_subscriptions.sql
-- PickleballHub: Add updated_at column to public.subscriptions
-- Ensures database schema parity if updated_at is ever queried or updated.

ALTER TABLE public.subscriptions 
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now());
