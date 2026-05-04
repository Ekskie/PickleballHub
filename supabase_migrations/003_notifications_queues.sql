-- 003_notifications_queues.sql
-- Create notifications and court_queues tables

-- 1. Notifications Table
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT, -- e.g., 'info', 'warning', 'success', 'error'
    link TEXT, -- optional URL to redirect to
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Enable RLS for notifications
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own notifications"
    ON public.notifications
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own notifications"
    ON public.notifications
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert notifications"
    ON public.notifications
    FOR INSERT
    WITH CHECK (true); -- Usually bypassed by service role anyway, but just in case.


-- 2. Court Queues Table
CREATE TABLE IF NOT EXISTS public.court_queues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES public.facilities(id) ON DELETE CASCADE,
    court_id UUID REFERENCES public.courts(id) ON DELETE CASCADE,
    player_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'waiting', -- 'waiting', 'next', 'completed', 'cancelled'
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    estimated_wait_mins INTEGER DEFAULT 0
);

-- Enable RLS for court_queues
ALTER TABLE public.court_queues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view queues"
    ON public.court_queues
    FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage queues"
    ON public.court_queues
    FOR ALL
    USING (true);

CREATE POLICY "Users can cancel their own queue"
    ON public.court_queues
    FOR UPDATE
    USING (auth.uid() = player_id);
