-- supabase_migrations/005_events_fields.sql

-- Add format column for event format (e.g., Singles, Doubles, Mixed Doubles)
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS format text;

-- Add prize_pool column (numeric for precise currency representation)
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS prize_pool numeric(10,2) DEFAULT 0;

-- Add image_url for the event banner
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS image_url text;
