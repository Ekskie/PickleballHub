-- tutorials_schema.sql
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.tutorials (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title        TEXT NOT NULL,
    description  TEXT,
    youtube_url  TEXT NOT NULL,
    level        TEXT DEFAULT 'Beginner' CHECK (level IN ('Beginner', 'Intermediate', 'Advanced')),
    uploaded_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.tutorials ENABLE ROW LEVEL SECURITY;

-- Anyone (even public) can read tutorials
CREATE POLICY "Tutorials are publicly viewable" ON public.tutorials
    FOR SELECT USING (true);

-- Only allowed roles can insert tutorials
CREATE POLICY "Admins can insert tutorials" ON public.tutorials
    FOR INSERT WITH CHECK (
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff', 'clubadmin')
    );

-- Only the uploader or superadmin/adminstaff can delete
CREATE POLICY "Admins can delete tutorials" ON public.tutorials
    FOR DELETE USING (
        uploaded_by = auth.uid() OR
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff')
    );

-- Only the uploader or superadmin/adminstaff/clubadmin can update
CREATE POLICY "Admins can update tutorials" ON public.tutorials
    FOR UPDATE USING (
        uploaded_by = auth.uid() OR
        (SELECT role FROM public.profiles WHERE id = auth.uid())
        IN ('superadmin', 'adminstaff', 'clubadmin')
    );

-- Realtime for live updates (optional)
ALTER PUBLICATION supabase_realtime ADD TABLE public.tutorials;

-- Seed the 5 starter YouTube tutorials
INSERT INTO public.tutorials (title, description, youtube_url, level) VALUES
    ('Pickleball Basics for Beginners', 'Everything you need to know to get started playing pickleball.', 'https://www.youtube.com/watch?v=A0F4QXh3DsE', 'Beginner'),
    ('Dinking Drills & Soft Game Mastery', 'Master the soft game at the kitchen line with these essential dinking drills.', 'https://www.youtube.com/watch?v=xVimRyghMp0', 'Beginner'),
    ('Pickleball Serving Techniques', 'Learn the fundamentals of a powerful and consistent pickleball serve.', 'https://www.youtube.com/watch?v=5MR0o45n8s8', 'Intermediate'),
    ('Advanced Strategy: Stacking & Poaching', 'Take your doubles game to the next level with advanced positioning tactics.', 'https://www.youtube.com/watch?v=3uKPsEe6bhA', 'Advanced'),
    ('The Third Shot Drop Explained', 'The single most important shot in pickleball — broken down step by step.', 'https://www.youtube.com/watch?v=C74BJJZsAd4', 'Intermediate')
ON CONFLICT DO NOTHING;
