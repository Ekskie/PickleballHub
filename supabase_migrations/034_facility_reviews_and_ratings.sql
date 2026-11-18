-- ============================================================
-- 034_facility_reviews_and_ratings.sql
-- PickleballHub: Verified Player Facility Reviews & Star Ratings
-- ============================================================

-- 1. Create table for Facility & Court Reviews
CREATE TABLE IF NOT EXISTS public.facility_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES public.facilities(id) ON DELETE CASCADE,
    court_id UUID REFERENCES public.courts(id) ON DELETE SET NULL,
    player_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    reservation_id UUID REFERENCES public.court_reservations(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    lighting_rating INTEGER CHECK (lighting_rating >= 1 AND lighting_rating <= 5),
    surface_rating INTEGER CHECK (surface_rating >= 1 AND surface_rating <= 5),
    cleanliness_rating INTEGER CHECK (cleanliness_rating >= 1 AND cleanliness_rating <= 5),
    review_text TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    UNIQUE(facility_id, player_id, reservation_id)
);

-- 2. Indexes for fast retrieval and aggregation
CREATE INDEX IF NOT EXISTS idx_reviews_facility_id ON public.facility_reviews(facility_id);
CREATE INDEX IF NOT EXISTS idx_reviews_player_id ON public.facility_reviews(player_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON public.facility_reviews(rating);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON public.facility_reviews(created_at DESC);

-- 3. Enable Row Level Security
ALTER TABLE public.facility_reviews ENABLE ROW LEVEL SECURITY;

-- 4. Policies
-- Service role full access
CREATE POLICY "Service role full access on facility_reviews"
    ON public.facility_reviews
    FOR ALL
    USING (true);

-- Anyone can read reviews (public display on facility and court cards)
CREATE POLICY "Public read facility_reviews"
    ON public.facility_reviews
    FOR SELECT
    USING (true);

-- Authenticated players can insert reviews
CREATE POLICY "Player insert facility_reviews"
    ON public.facility_reviews
    FOR INSERT
    WITH CHECK (auth.uid() = player_id);

-- Player can update their own review
CREATE POLICY "Player update own facility_reviews"
    ON public.facility_reviews
    FOR UPDATE
    USING (auth.uid() = player_id);
