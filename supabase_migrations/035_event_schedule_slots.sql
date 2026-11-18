-- 035_event_schedule_slots.sql
-- Adds schedule_slots JSONB column to public.events to support per-court non-contiguous sessions with gaps

ALTER TABLE public.events 
ADD COLUMN IF NOT EXISTS schedule_slots JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.events.schedule_slots IS 'Array of per-court booked hourly sessions: [{"court_id": uuid, "court_name": text, "slots": [int], "time_ranges": [text], "total_hours": float}]';
