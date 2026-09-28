-- 026_subscriptions_and_tiers.sql
-- PickleballHub: Subscription monetization infrastructure & tier management
-- Adds subscription tier columns to profiles and creates a subscriptions ledger table.

-- 1. Add subscription columns to public.profiles
ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS subscription_billing_cycle TEXT DEFAULT 'monthly',
    ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP WITH TIME ZONE;

-- Add index on subscription_tier for performance
CREATE INDEX IF NOT EXISTS idx_profiles_subscription_tier ON public.profiles(subscription_tier);

-- 2. Create public.subscriptions audit & billing ledger table
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL, -- 'owner', 'clubadmin', 'player'
    tier TEXT NOT NULL, -- 'pro', 'elite'
    billing_cycle TEXT DEFAULT 'monthly', -- 'monthly', 'annual'
    amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    payment_method TEXT DEFAULT 'gcash',
    gcash_reference TEXT,
    receipt_url TEXT,
    status TEXT DEFAULT 'pending_approval', -- 'pending_approval', 'active', 'rejected', 'expired'
    starts_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    expires_at TIMESTAMP WITH TIME ZONE,
    reviewed_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Index for queries on subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON public.subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON public.subscriptions(status);

-- 3. Enable RLS on subscriptions
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'subscriptions' AND policyname = 'Users can view their own subscriptions'
    ) THEN
        CREATE POLICY "Users can view their own subscriptions"
            ON public.subscriptions FOR SELECT
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'subscriptions' AND policyname = 'Users can submit their own subscription'
    ) THEN
        CREATE POLICY "Users can submit their own subscription"
            ON public.subscriptions FOR INSERT
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'subscriptions' AND policyname = 'Admin Staff and Superadmin can manage all subscriptions'
    ) THEN
        CREATE POLICY "Admin Staff and Superadmin can manage all subscriptions"
            ON public.subscriptions FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM public.profiles
                    WHERE profiles.id = auth.uid() AND profiles.role IN ('adminstaff', 'superadmin')
                )
            );
    END IF;
END $$;

-- 4. Ensure storage bucket for subscription payment receipts exists
INSERT INTO storage.buckets (id, name, public) 
VALUES ('subscription-receipts', 'subscription-receipts', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for subscription receipts
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Authenticated users can upload subscription receipts'
    ) THEN
        CREATE POLICY "Authenticated users can upload subscription receipts"
        ON storage.objects FOR INSERT TO authenticated WITH CHECK (
            bucket_id = 'subscription-receipts'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Staff and Owners can view subscription receipts'
    ) THEN
        CREATE POLICY "Staff and Owners can view subscription receipts"
        ON storage.objects FOR SELECT TO authenticated USING (
            bucket_id = 'subscription-receipts' AND (
                EXISTS (
                    SELECT 1 FROM public.profiles 
                    WHERE profiles.id = auth.uid() AND profiles.role IN ('adminstaff', 'superadmin', 'owner', 'clubadmin', 'player')
                )
            )
        );
    END IF;
END $$;
