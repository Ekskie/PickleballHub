-- messages_schema.sql
-- Run this in your Supabase SQL Editor

-- 1. conversations table
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

-- 2. conversation_participants table
CREATE TABLE IF NOT EXISTS public.conversation_participants (
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    PRIMARY KEY (conversation_id, profile_id)
);
ALTER TABLE public.conversation_participants ENABLE ROW LEVEL SECURITY;

-- RLS: A user can see conversations they are part of
CREATE POLICY "Users can view their conversations" ON public.conversations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.conversation_participants
            WHERE conversation_participants.conversation_id = conversations.id
            AND conversation_participants.profile_id = auth.uid()
        )
    );

-- RLS: Users can view participants if they share a conversation
CREATE POLICY "Users can view participants of their conversations" ON public.conversation_participants
    FOR SELECT USING (
        conversation_id IN (
            SELECT conversation_id FROM public.conversation_participants WHERE profile_id = auth.uid()
        )
    );

-- 3. messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE
);
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

-- RLS: User can read messages in their conversations
CREATE POLICY "Users can read messages in their conversations" ON public.messages
    FOR SELECT USING (
        conversation_id IN (
            SELECT conversation_id FROM public.conversation_participants WHERE profile_id = auth.uid()
        )
    );

-- RLS: User can insert messages into their conversations, and sender_id MUST be their own uid
CREATE POLICY "Users can send messages to their conversations" ON public.messages
    FOR INSERT WITH CHECK (
        sender_id = auth.uid() AND
        conversation_id IN (
            SELECT conversation_id FROM public.conversation_participants WHERE profile_id = auth.uid()
        )
    );

-- RLS: User can mark messages as read (update read_at) in conversations they belong to
-- This lets recipients set read_at = NOW() on messages they received
CREATE POLICY "Users can mark messages as read in their conversations" ON public.messages
    FOR UPDATE USING (
        conversation_id IN (
            SELECT conversation_id FROM public.conversation_participants WHERE profile_id = auth.uid()
        )
    ) WITH CHECK (
        conversation_id IN (
            SELECT conversation_id FROM public.conversation_participants WHERE profile_id = auth.uid()
        )
    );

-- Also allow conversation participants to insert themselves
CREATE POLICY "Users can join conversations" ON public.conversation_participants
    FOR INSERT WITH CHECK (profile_id = auth.uid());

-- Realtime: Enable realtime for messages table so we can listen to it
alter publication supabase_realtime add table public.messages;

