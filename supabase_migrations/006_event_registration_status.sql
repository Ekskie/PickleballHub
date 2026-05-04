-- supabase_migrations/006_event_registration_status.sql

-- Drop the existing check constraint on status
ALTER TABLE public.event_registrations DROP CONSTRAINT IF EXISTS event_registrations_status_check;

-- Add the new check constraint to include 'pending_payment'
ALTER TABLE public.event_registrations ADD CONSTRAINT event_registrations_status_check 
CHECK (status IN ('registered', 'waitlisted', 'cancelled', 'pending_payment'));
