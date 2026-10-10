-- 029_clubadmin_tutorial_visibility.sql
-- Enables ClubAdmins to designate tutorials as Public or Club-Exclusive (visible only to active club members).

-- 1. Add visibility and club_id columns to public.tutorials
ALTER TABLE public.tutorials
    ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'public',
    ADD COLUMN IF NOT EXISTS club_id UUID REFERENCES public.clubs(id) ON DELETE SET NULL;

-- 2. Add CHECK constraint on visibility
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'tutorials_visibility_check'
    ) THEN
        ALTER TABLE public.tutorials 
        ADD CONSTRAINT tutorials_visibility_check 
        CHECK (visibility IN ('public', 'club_members'));
    END IF;
END $$;

-- 3. Add performance indexes   
CREATE INDEX IF NOT EXISTS idx_tutorials_visibility ON public.tutorials(visibility);
CREATE INDEX IF NOT EXISTS idx_tutorials_club_id ON public.tutorials(club_id);

-- 4. Update Row Level Security (RLS) on public.tutorials for SELECT
-- Allows:
--  - All public tutorials to be viewed by anyone
--  - Club-exclusive tutorials to be viewed by:
--      a) The author/uploader
--      b) Superadmin, AdminStaff, and Facility/Club Owners
--      c) The clubadmin managing the club
--      d) Active members of that club (club_memberships status = 'active')
DROP POLICY IF EXISTS "Anyone can view tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Public tutorials and club members view" ON public.tutorials;

CREATE POLICY "Public tutorials and club members view"
ON public.tutorials
FOR SELECT
USING (
    visibility = 'public'
    OR visibility IS NULL
    OR auth.uid() = uploaded_by
    OR EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role IN ('superadmin', 'adminstaff', 'owner')
    )
    OR EXISTS (
        SELECT 1 FROM public.clubs
        WHERE id = tutorials.club_id AND admin_id = auth.uid()
    )
    OR EXISTS (
        SELECT 1 FROM public.club_memberships
        WHERE club_id = tutorials.club_id 
          AND player_id = auth.uid() 
          AND status = 'active'
    )
);
