-- 025_facility_kyc_dual_docs.sql
-- PickleballHub: Support for dual KYC verification documents
-- Required for Facility Owners:
-- 1. Transfer Certificate of Title (TCT) / Original Certificate of Title (OCT)
-- 2. Business Permit (Mayor's / LGU Business Permit)
--
-- The kyc_document_url column in public.facilities supports both legacy single URLs
-- and structured JSON objects with the format:
-- {
--   "tct_url": "https://.../tct_oct_...",
--   "tct_filename": "TCT-Title.pdf",
--   "permit_url": "https://.../biz_permit_...",
--   "permit_filename": "Mayors-Permit.pdf",
--   "submitted_at": "2026-09-27T12:00:00Z"
-- }

-- Ensure facilities table has the required KYC columns
ALTER TABLE public.facilities 
    ADD COLUMN IF NOT EXISTS kyc_status TEXT DEFAULT 'unverified',
    ADD COLUMN IF NOT EXISTS kyc_document_url TEXT;

-- Ensure storage bucket 'kyc-documents' is configured
INSERT INTO storage.buckets (id, name, public) 
VALUES ('kyc-documents', 'kyc-documents', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies: Authenticated users can upload, Staff and Owners can view
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated users can upload kyc documents'
    ) THEN
        CREATE POLICY "Authenticated users can upload kyc documents"
        ON storage.objects FOR INSERT TO authenticated WITH CHECK (
            bucket_id = 'kyc-documents'
        );
    END IF;
END $$;
