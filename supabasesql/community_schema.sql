-- community_schema.sql
-- Run this in your Supabase SQL Editor

-- 1. community_posts
CREATE TABLE IF NOT EXISTS public.community_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    author_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.community_posts ENABLE ROW LEVEL SECURITY;

-- RLS: Anyone logged in can read posts
CREATE POLICY "Anyone can read posts" ON public.community_posts
    FOR SELECT USING (auth.role() = 'authenticated');

-- RLS: Users can insert their own posts
CREATE POLICY "Users can create posts" ON public.community_posts
    FOR INSERT WITH CHECK (author_id = auth.uid());

-- RLS: Users can delete their own posts, or specific admin roles can delete any post.
CREATE POLICY "Users can delete their own posts or admin can delete" ON public.community_posts
    FOR DELETE USING (
        author_id = auth.uid() OR 
        (SELECT role FROM public.profiles WHERE id = auth.uid()) IN ('superadmin', 'adminstaff', 'clubadmin', 'owner')
    );

-- 2. post_likes
CREATE TABLE IF NOT EXISTS public.post_likes (
    post_id UUID REFERENCES public.community_posts(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (post_id, profile_id)
);
ALTER TABLE public.post_likes ENABLE ROW LEVEL SECURITY;

-- RLS: Anyone can read likes
CREATE POLICY "Anyone can read likes" ON public.post_likes
    FOR SELECT USING (auth.role() = 'authenticated');

-- RLS: User can only like/unlike as themselves
CREATE POLICY "Users can toggle their likes" ON public.post_likes
    FOR ALL USING (profile_id = auth.uid()) WITH CHECK (profile_id = auth.uid());

-- 3. community_comments
CREATE TABLE IF NOT EXISTS public.community_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID REFERENCES public.community_posts(id) ON DELETE CASCADE,
    author_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.community_comments ENABLE ROW LEVEL SECURITY;

-- RLS: Anyone can read comments
CREATE POLICY "Anyone can read comments" ON public.community_comments
    FOR SELECT USING (auth.role() = 'authenticated');

-- RLS: Users can create comments as themselves
CREATE POLICY "Users can create comments" ON public.community_comments
    FOR INSERT WITH CHECK (author_id = auth.uid());

-- RLS: Users can delete their own comments or admins can delete
CREATE POLICY "Users can delete their own comments or admin can delete" ON public.community_comments
    FOR DELETE USING (
        author_id = auth.uid() OR 
        (SELECT role FROM public.profiles WHERE id = auth.uid()) IN ('superadmin', 'adminstaff', 'clubadmin', 'owner')
    );

-- Realtime: Enable realtime for posts, likes, and comments
alter publication supabase_realtime add table public.community_posts;
alter publication supabase_realtime add table public.post_likes;
alter publication supabase_realtime add table public.community_comments;
