-- 028_tutorial_hierarchy_permissions.sql
-- Updates Row Level Security (RLS) policies on public.tutorials
-- to reflect ownership and role-hierarchy permissions:
-- 1. Uploader can delete their own tutorial.
-- 2. Users with higher role ranking can delete tutorials uploaded by lower-ranked roles.
-- 3. Superadmin can delete any tutorial.

-- Define numeric rank helper function if desired in Postgres
CREATE OR REPLACE FUNCTION public.get_role_rank(r TEXT)
RETURNS INT LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE LOWER(COALESCE(r, 'player'))
        WHEN 'superadmin'   THEN 100
        WHEN 'adminstaff'   THEN 80
        WHEN 'owner'        THEN 60
        WHEN 'clubadmin'    THEN 40
        WHEN 'facilitystaff'THEN 20
        ELSE 10
    END;
$$;

-- Drop old delete policy
DROP POLICY IF EXISTS "Staff and Admins can delete tutorials" ON public.tutorials;

-- Recreate delete policy with role hierarchy
CREATE POLICY "Hierarchy and Author can delete tutorials" ON public.tutorials
    FOR DELETE USING (
        -- 1. Uploader can delete their own
        uploaded_by = auth.uid()
        OR
        -- 2. Superadmin can delete anything
        (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'superadmin'
        OR
        -- 3. Higher rank than uploader
        (
            uploaded_by IS NOT NULL AND
            public.get_role_rank((SELECT role FROM public.profiles WHERE id = auth.uid())) >
            public.get_role_rank((SELECT role FROM public.profiles WHERE id = tutorials.uploaded_by))
        )
        OR
        -- 4. Platform starter guides (uploaded_by IS NULL)
        (
            uploaded_by IS NULL AND
            (SELECT role FROM public.profiles WHERE id = auth.uid()) IN ('superadmin', 'adminstaff')
        )
    );
