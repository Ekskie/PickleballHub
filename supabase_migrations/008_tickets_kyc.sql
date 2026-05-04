-- 008_tickets_kyc.sql
-- 1. Create Tickets table for customer support
CREATE TABLE IF NOT EXISTS public.tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'open', -- 'open', 'closed'
    response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Enable RLS for tickets
ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can create their own tickets"
    ON public.tickets FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own tickets"
    ON public.tickets FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Admin Staff and Superadmin can view and manage all tickets"
    ON public.tickets FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE profiles.id = auth.uid() AND profiles.role IN ('adminstaff', 'superadmin')
        )
    );

-- 2. Add KYC columns to facilities
ALTER TABLE public.facilities 
    ADD COLUMN IF NOT EXISTS kyc_status TEXT DEFAULT 'unverified',
    ADD COLUMN IF NOT EXISTS kyc_document_url TEXT;

-- For storage, we assume a bucket 'kyc-documents' exists or will be created.
-- We can script it but it requires service role / postgres role.
INSERT INTO storage.buckets (id, name, public) 
VALUES ('kyc-documents', 'kyc-documents', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for kyc-documents (owner can insert, admin can select)
CREATE POLICY "Facility owners can upload kyc documents"
ON storage.objects FOR INSERT TO authenticated WITH CHECK (
  bucket_id = 'kyc-documents'
);

CREATE POLICY "Admin staff can view kyc documents"
ON storage.objects FOR SELECT TO authenticated USING (
  bucket_id = 'kyc-documents' AND (
    EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE profiles.id = auth.uid() AND profiles.role IN ('adminstaff', 'superadmin', 'owner')
    )
  )
);
