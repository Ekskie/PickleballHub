-- 027_tutorial_video_uploads.sql
-- Enables video file uploads for tutorials alongside YouTube links
-- and allows all management roles (superadmin, adminstaff, clubadmin, owner, facilitystaff) to upload.

-- 1. Modify public.tutorials table to support direct video uploads
ALTER TABLE IF EXISTS public.tutorials ALTER COLUMN youtube_url DROP NOT NULL;

ALTER TABLE IF EXISTS public.tutorials
    ADD COLUMN IF NOT EXISTS video_url TEXT,
    ADD COLUMN IF NOT EXISTS video_type TEXT DEFAULT 'youtube',
    ADD COLUMN IF NOT EXISTS thumbnail_url TEXT,
    ADD COLUMN IF NOT EXISTS duration TEXT;

-- Add check constraint for video_type if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tutorials_video_type_check'
    ) THEN
        ALTER TABLE public.tutorials
            ADD CONSTRAINT tutorials_video_type_check
            CHECK (video_type IN ('youtube', 'upload', 'direct'));
    END IF;
END $$;

-- 2. Update Row Level Security (RLS) on public.tutorials
ALTER TABLE public.tutorials ENABLE ROW LEVEL SECURITY;

-- Drop old policies to update with expanded roles
DROP POLICY IF EXISTS "Tutorials are publicly viewable" ON public.tutorials;
DROP POLICY IF EXISTS "Admins can insert tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Staff and Admins can insert tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Admins can delete tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Staff and Admins can delete tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Admins can update tutorials" ON public.tutorials;
DROP POLICY IF EXISTS "Staff and Admins can update tutorials" ON public.tutorials;

-- Anyone (even unauthenticated) can view tutorials
CREATE POLICY "Tutorials are publicly viewable" ON public.tutorials
    FOR SELECT USING (true);

-- Superadmin, AdminStaff, ClubAdmin, Owner, and FacilityStaff can insert tutorials
CREATE POLICY "Staff and Admins can insert tutorials" ON public.tutorials
    FOR INSERT WITH CHECK (
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff', 'clubadmin', 'owner', 'facilitystaff')
    );

-- Creator or Superadmin/AdminStaff can delete tutorials
CREATE POLICY "Staff and Admins can delete tutorials" ON public.tutorials
    FOR DELETE USING (
        uploaded_by = auth.uid() OR
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff')
    );

-- Creator or allowed staff/admins can update tutorials
CREATE POLICY "Staff and Admins can update tutorials" ON public.tutorials
    FOR UPDATE USING (
        uploaded_by = auth.uid() OR
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff', 'clubadmin', 'owner', 'facilitystaff')
    );

-- 3. Ensure storage bucket for tutorial videos exists
INSERT INTO storage.buckets (id, name, public)
VALUES ('tutorial-videos', 'tutorial-videos', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for tutorial-videos bucket
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public can view tutorial videos'
    ) THEN
        CREATE POLICY "Public can view tutorial videos"
        ON storage.objects FOR SELECT TO public USING (
            bucket_id = 'tutorial-videos'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated staff can upload tutorial videos'
    ) THEN
        CREATE POLICY "Authenticated staff can upload tutorial videos"
        ON storage.objects FOR INSERT TO authenticated WITH CHECK (
            bucket_id = 'tutorial-videos'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated staff can update tutorial videos'
    ) THEN
        CREATE POLICY "Authenticated staff can update tutorial videos"
        ON storage.objects FOR UPDATE TO authenticated USING (
            bucket_id = 'tutorial-videos'
        );
    END IF;
END $$;
