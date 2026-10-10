-- ============================================================
-- 030_event_approvals_and_gcash.sql
-- PickleballHub: Event Approvals, GCash Payment Reference,
-- and Enhanced Double-Booking Indexes
-- ============================================================

-- 1. Update events status check constraint to support 'pending_approval' and 'rejected'
ALTER TABLE public.events DROP CONSTRAINT IF EXISTS events_status_check;

ALTER TABLE public.events ADD CONSTRAINT events_status_check 
CHECK (status IN (
    'upcoming', 
    'registration_open', 
    'full', 
    'completed', 
    'cancelled', 
    'pending_payment', 
    'pending_approval', 
    'rejected'
));

-- 2. Add approval, rejection, and payment columns to events
ALTER TABLE public.events 
    ADD COLUMN IF NOT EXISTS gcash_ref TEXT,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

-- 3. Indexes for double booking queries and timeline performance
CREATE INDEX IF NOT EXISTS idx_events_date_status ON public.events(event_date, status);
CREATE INDEX IF NOT EXISTS idx_events_facility_date ON public.events(facility_id, event_date);
CREATE INDEX IF NOT EXISTS idx_event_courts_court_id ON public.event_courts(court_id);
CREATE INDEX IF NOT EXISTS idx_event_courts_event_id ON public.event_courts(event_id);
CREATE INDEX IF NOT EXISTS idx_court_reservations_court_date_status ON public.court_reservations(court_id, date, status);
