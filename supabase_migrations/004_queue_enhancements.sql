-- 004_queue_enhancements.sql
-- Add reservation_id to court_queues to link queue entries with specific bookings

ALTER TABLE public.court_queues
ADD COLUMN IF NOT EXISTS reservation_id UUID REFERENCES public.court_reservations(id) ON DELETE CASCADE;

-- Also add an index to speed up lookups
CREATE INDEX IF NOT EXISTS idx_court_queues_reservation ON public.court_queues(reservation_id);
