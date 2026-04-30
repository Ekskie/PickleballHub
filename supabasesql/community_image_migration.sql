-- community_image_migration.sql
-- Run this in your Supabase SQL Editor

-- 1. Add image_url column to community_posts
ALTER TABLE public.community_posts
    ADD COLUMN IF NOT EXISTS image_url TEXT;

-- 2. Create storage bucket for community images (run via Supabase dashboard or API)
-- INSERT INTO storage.buckets (id, name, public)
--   VALUES ('community-images', 'community-images', true)
--   ON CONFLICT (id) DO NOTHING;

-- 3. Storage RLS: Allow authenticated users to upload
-- CREATE POLICY "Authenticated users can upload community images"
--   ON storage.objects FOR INSERT
--   WITH CHECK (bucket_id = 'community-images' AND auth.role() = 'authenticated');

-- CREATE POLICY "Anyone can read community images"
--   ON storage.objects FOR SELECT
--   USING (bucket_id = 'community-images');

-- CREATE POLICY "Users can delete their own community images"
--   ON storage.objects FOR DELETE
--   USING (bucket_id = 'community-images' AND auth.uid()::text = (storage.foldername(name))[1]);
