-- supabase_migrations/007_event_status_pending.sql

ALTER TABLE public.events DROP CONSTRAINT IF EXISTS events_status_check;

ALTER TABLE public.events ADD CONSTRAINT events_status_check 
CHECK (status IN ('upcoming', 'registration_open', 'full', 'completed', 'cancelled', 'pending_payment'));
