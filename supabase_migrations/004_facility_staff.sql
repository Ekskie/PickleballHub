-- 004_facility_staff.sql
-- Create facility_staff junction table to assign facility staff to facilities

CREATE TABLE IF NOT EXISTS public.facility_staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES public.facilities(id) ON DELETE CASCADE,
    staff_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    UNIQUE(facility_id, staff_id)
);

-- Enable RLS
ALTER TABLE public.facility_staff ENABLE ROW LEVEL SECURITY;

-- Owner can manage staff assignments for their facilities
CREATE POLICY "Owner can manage facility staff"
    ON public.facility_staff
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.facilities f
            WHERE f.id = facility_id AND f.owner_id = auth.uid()
        )
    );

-- Facility staff can see their own assignments
CREATE POLICY "Staff can view their assignments"
    ON public.facility_staff
    FOR SELECT
    USING (auth.uid() = staff_id);

-- System can view everything
CREATE POLICY "Service role can view everything"
    ON public.facility_staff
    FOR ALL
    USING (true);
