-- ── Disputes Table ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.disputes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    reporter_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    reported_user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    reservation_id UUID REFERENCES public.court_reservations(id) ON DELETE SET NULL,
    type TEXT NOT NULL DEFAULT 'other'
        CHECK (type IN ('booking_conflict','payment_dispute','misconduct','facility_issue','other')),
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','investigating','resolved','dismissed')),
    resolution TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.disputes ENABLE ROW LEVEL SECURITY;

-- Allow service_role (supabase_admin) full access
CREATE POLICY "Admin full access on disputes"
    ON public.disputes FOR ALL
    USING (true)
    WITH CHECK (true);

-- Allow authenticated users to insert their own disputes
CREATE POLICY "Users can report disputes"
    ON public.disputes FOR INSERT
    WITH CHECK (auth.uid() = reporter_id);

-- Allow users to view their own disputes
CREATE POLICY "Users can view own disputes"
    ON public.disputes FOR SELECT
    USING (auth.uid() = reporter_id);

-- ── Platform Settings Table ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.platform_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admin full access on settings"
    ON public.platform_settings FOR ALL
    USING (true)
    WITH CHECK (true);

-- ── Seed default settings ───────────────────────────────────────
INSERT INTO public.platform_settings (key, value) VALUES
    ('platform_name', 'PickleballHub'),
    ('support_email', 'support@pickleballhub.com'),
    ('maintenance_mode', '0'),
    ('require_2fa', '0')
ON CONFLICT (key) DO NOTHING;
