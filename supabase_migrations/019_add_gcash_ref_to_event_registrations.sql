-- ============================================================
-- PickleballHub: Add GCash Reference to Event Registrations
-- ============================================================

ALTER TABLE public.event_registrations 
    ADD COLUMN IF NOT EXISTS gcash_ref TEXT;
