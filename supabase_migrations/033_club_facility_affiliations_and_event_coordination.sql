-- ============================================================
-- 033_club_facility_affiliations_and_event_coordination.sql
-- PickleballHub: Club-to-Facility Mutual Affiliations,
-- Event Coordination Auto-Chat, and Front-Desk Check-in Tracking
-- ============================================================

-- 1. Create table for Club-Facility Affiliations
CREATE TABLE IF NOT EXISTS public.club_facility_affiliations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id UUID NOT NULL REFERENCES public.clubs(id) ON DELETE CASCADE,
    facility_id UUID NOT NULL REFERENCES public.facilities(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'declined', 'revoked')),
    requested_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    request_notes TEXT,
    responded_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    response_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    UNIQUE(club_id, facility_id)
);

-- 2. Add checked_in_by column to event_registrations to record whether Club Admin or Facility Staff checked in the player
ALTER TABLE public.event_registrations 
    ADD COLUMN IF NOT EXISTS checked_in_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;

-- 3. Indexes for fast lookup of affiliations by club, facility, and status
CREATE INDEX IF NOT EXISTS idx_affiliations_club_id ON public.club_facility_affiliations(club_id);
CREATE INDEX IF NOT EXISTS idx_affiliations_facility_id ON public.club_facility_affiliations(facility_id);
CREATE INDEX IF NOT EXISTS idx_affiliations_status ON public.club_facility_affiliations(status);

-- 4. Enable RLS
ALTER TABLE public.club_facility_affiliations ENABLE ROW LEVEL SECURITY;

-- 5. Policies
-- Service role has full access
CREATE POLICY "Service role full access on club_facility_affiliations"
    ON public.club_facility_affiliations
    FOR ALL
    USING (true);

-- Anyone can read approved affiliations (public display of club home court)
CREATE POLICY "Public read approved affiliations"
    ON public.club_facility_affiliations
    FOR SELECT
    USING (status = 'approved');

-- Club admin can read and insert their own club affiliations
CREATE POLICY "Club admin manage affiliations"
    ON public.club_facility_affiliations
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.clubs c
            WHERE c.id = club_facility_affiliations.club_id AND c.admin_id = auth.uid()
        )
    );

-- Facility owner can manage affiliations for their facilities
CREATE POLICY "Facility owner manage affiliations"
    ON public.club_facility_affiliations
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.facilities f
            WHERE f.id = club_facility_affiliations.facility_id AND f.owner_id = auth.uid()
        )
    );
