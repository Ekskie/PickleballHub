-- Migration: 028_landing_page_cms.sql
-- Description: Platform Settings keys for Superadmin Landing Page CMS & Articles

-- Ensure platform_settings table exists
CREATE TABLE IF NOT EXISTS public.platform_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

-- Allow service_role and public read access on platform_settings
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'platform_settings' AND policyname = 'Admin full access on settings'
    ) THEN
        CREATE POLICY "Admin full access on settings"
            ON public.platform_settings FOR ALL
            USING (true)
            WITH CHECK (true);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'platform_settings' AND policyname = 'Public read access on settings'
    ) THEN
        CREATE POLICY "Public read access on settings"
            ON public.platform_settings FOR SELECT
            TO public
            USING (true);
    END IF;
END $$;

-- ============================================================================
-- 2. SUPABASE STORAGE BUCKET: platform-assets (FOR ONLINE MEDIA UPLOADS)
-- ============================================================================
-- Ensure public storage bucket 'platform-assets' exists so images are stored online
-- in Supabase Cloud Storage (accessible via https://<project>.supabase.co/storage/v1/object/public/platform-assets/...)
INSERT INTO storage.buckets (id, name, public)
VALUES ('platform-assets', 'platform-assets', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Storage policies for platform-assets bucket
DO $$
BEGIN
    -- Public can view/download platform assets online
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public can view platform assets'
    ) THEN
        CREATE POLICY "Public can view platform assets"
            ON storage.objects FOR SELECT TO public USING (
                bucket_id = 'platform-assets'
            );
    END IF;

    -- Authenticated staff and superadmin can upload platform assets
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated staff can upload platform assets'
    ) THEN
        CREATE POLICY "Authenticated staff can upload platform assets"
            ON storage.objects FOR INSERT TO authenticated WITH CHECK (
                bucket_id = 'platform-assets'
            );
    END IF;

    -- Authenticated staff can update platform assets
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated staff can update platform assets'
    ) THEN
        CREATE POLICY "Authenticated staff can update platform assets"
            ON storage.objects FOR UPDATE TO authenticated USING (
                bucket_id = 'platform-assets'
            );
    END IF;

    -- Authenticated staff can delete platform assets
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated staff can delete platform assets'
    ) THEN
        CREATE POLICY "Authenticated staff can delete platform assets"
            ON storage.objects FOR DELETE TO authenticated USING (
                bucket_id = 'platform-assets'
            );
    END IF;
END $$;

-- Notes on landing keys stored in platform_settings:
-- landing_masthead_location: string
-- landing_hero_slides: JSON array of slides [{id, title, subtitle, image_url, alt}]
-- landing_lead_stories: JSON array of lead stories [{id, category, title, description, link, link_text, image_url}]
-- landing_bulletins: JSON array of bulletins [{id, time, title, description, link}]
-- landing_articles_data: JSON object of published articles keyed by ID
-- landing_testimonials: JSON array of reader testimonials [{id, author, role, quote, rating}]
-- landing_faqs: JSON array of FAQs [{id, question, answer}]
-- landing_stats: JSON array of 4 stats counters [{num, label}]
-- landing_value_prop_*: strings for value proposition banner
-- landing_section_*: strings for Section A, B, C dividers and headings
-- landing_footer_cta_*: strings for final call to action banner
