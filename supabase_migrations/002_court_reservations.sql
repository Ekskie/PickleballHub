-- ============================================================
-- PickleballHub: Court Reservations + Facility Operating Hours
-- Run this in your Supabase SQL Editor
-- ============================================================

-- 1. Add operating hours columns to facilities
-- ============================================================
alter table public.facilities
    add column if not exists open_time  time not null default '08:00:00',
    add column if not exists close_time time not null default '21:00:00',
    add column if not exists slot_duration_minutes integer not null default 60;

-- 2. COURT_RESERVATIONS TABLE
-- ============================================================
create table if not exists public.court_reservations (
    id            uuid primary key default gen_random_uuid(),
    player_id     uuid references public.profiles(id)  on delete cascade not null,
    court_id      uuid references public.courts(id)    on delete cascade not null,
    facility_id   uuid references public.facilities(id) on delete cascade not null,
    date          date not null,
    start_time    time not null,
    end_time      time not null,
    total_hours   numeric(4,1) not null default 1,
    hourly_rate   numeric(10,2) not null default 0,
    total_amount  numeric(10,2) not null default 0,
    status        text not null default 'pending_payment'
                  check (status in ('pending_payment','confirmed','cancelled','completed')),
    gcash_ref     text,                  -- GCash reference number
    created_at    timestamptz not null default now()
);

alter table public.court_reservations enable row level security;

-- Player can manage their own reservations
create policy "Player can manage own reservations"
    on public.court_reservations for all
    using (auth.uid() = player_id)
    with check (auth.uid() = player_id);

-- Facility owner can view reservations for their courts
create policy "Owner can view reservations for their courts"
    on public.court_reservations for select
    using (
        exists (
            select 1 from public.courts c
            join public.facilities f on f.id = c.facility_id
            where c.id = court_id and f.owner_id = auth.uid()
        )
    );

-- Anyone authenticated can read confirmed reservations (for slot availability check)
create policy "Authenticated users can check slot availability"
    on public.court_reservations for select
    using (auth.role() = 'authenticated');

-- ============================================================
-- INDEXES
-- ============================================================
create index if not exists idx_reservations_player  on public.court_reservations(player_id);
create index if not exists idx_reservations_court   on public.court_reservations(court_id);
create index if not exists idx_reservations_date    on public.court_reservations(date);
create index if not exists idx_reservations_status  on public.court_reservations(status);
