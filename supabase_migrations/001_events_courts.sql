-- ============================================================
-- PickleballHub: Events & Courts Migration
-- Run this in your Supabase SQL Editor
-- ============================================================

-- 1. FACILITIES TABLE
-- ============================================================
create table if not exists public.facilities (
    id          uuid primary key default gen_random_uuid(),
    owner_id    uuid references public.profiles(id) on delete cascade not null,
    name        text not null,
    location    text,
    description text,
    status      text not null default 'active' check (status in ('active', 'inactive')),
    created_at  timestamptz not null default now()
);
alter table public.facilities enable row level security;

-- Owner can see/manage their own facilities
create policy "Owner can manage own facilities"
    on public.facilities for all
    using (auth.uid() = owner_id)
    with check (auth.uid() = owner_id);

-- Anyone logged in can read facilities (for event creation)
create policy "Authenticated users can view active facilities"
    on public.facilities for select
    using (auth.role() = 'authenticated' and status = 'active');


-- 2. COURTS TABLE
-- ============================================================
create table if not exists public.courts (
    id            uuid primary key default gen_random_uuid(),
    facility_id   uuid references public.facilities(id) on delete cascade not null,
    owner_id      uuid references public.profiles(id) on delete cascade not null,
    name          text not null,
    type          text not null default 'indoor' check (type in ('indoor', 'outdoor')),
    hourly_rate   numeric(10,2) not null default 0,
    status        text not null default 'active' check (status in ('active', 'maintenance', 'closed')),
    created_at    timestamptz not null default now()
);
alter table public.courts enable row level security;

-- Owner can manage their own courts
create policy "Owner can manage own courts"
    on public.courts for all
    using (auth.uid() = owner_id)
    with check (auth.uid() = owner_id);

-- Anyone authenticated can read courts
create policy "Authenticated users can view courts"
    on public.courts for select
    using (auth.role() = 'authenticated');


-- 3. EVENTS TABLE
-- ============================================================
create table if not exists public.events (
    id             uuid primary key default gen_random_uuid(),
    organizer_id   uuid references public.profiles(id) on delete cascade not null,
    facility_id    uuid references public.facilities(id) on delete set null,
    title          text not null,
    type           text not null default 'social' check (type in ('tournament', 'social', 'training', 'league')),
    description    text,
    event_date     date not null,
    start_time     time not null,
    end_time       time not null,
    max_players    integer not null default 16,
    entry_fee      numeric(10,2) not null default 0,
    location_label text,           -- e.g. "Court 1 & 2" displayed on player card
    status         text not null default 'upcoming'
                   check (status in ('upcoming', 'registration_open', 'full', 'completed', 'cancelled')),
    created_at     timestamptz not null default now()
);
alter table public.events enable row level security;

-- Organizer can manage their events
create policy "Organizer can manage own events"
    on public.events for all
    using (auth.uid() = organizer_id)
    with check (auth.uid() = organizer_id);

-- All authenticated users can read upcoming/open events
create policy "Authenticated users can view events"
    on public.events for select
    using (auth.role() = 'authenticated');


-- 4. EVENT_COURTS (junction table – which courts are booked for an event)
-- ============================================================
create table if not exists public.event_courts (
    id         uuid primary key default gen_random_uuid(),
    event_id   uuid references public.events(id) on delete cascade not null,
    court_id   uuid references public.courts(id) on delete cascade not null,
    unique(event_id, court_id)
);
alter table public.event_courts enable row level security;

create policy "Authenticated can view event_courts"
    on public.event_courts for select
    using (auth.role() = 'authenticated');

create policy "Organizer can manage event_courts"
    on public.event_courts for all
    using (
        exists (
            select 1 from public.events e
            where e.id = event_id and e.organizer_id = auth.uid()
        )
    );


-- 5. EVENT_REGISTRATIONS TABLE
-- ============================================================
create table if not exists public.event_registrations (
    id            uuid primary key default gen_random_uuid(),
    event_id      uuid references public.events(id) on delete cascade not null,
    player_id     uuid references public.profiles(id) on delete cascade not null,
    registered_at timestamptz not null default now(),
    status        text not null default 'registered'
                  check (status in ('registered', 'waitlisted', 'cancelled')),
    unique(event_id, player_id)
);
alter table public.event_registrations enable row level security;

-- Players can manage their own registrations
create policy "Player can manage own registrations"
    on public.event_registrations for all
    using (auth.uid() = player_id)
    with check (auth.uid() = player_id);

-- Organizer can see registrations for their events
create policy "Organizer can view event registrations"
    on public.event_registrations for select
    using (
        exists (
            select 1 from public.events e
            where e.id = event_id and e.organizer_id = auth.uid()
        )
    );

-- ============================================================
-- INDEXES for performance
-- ============================================================
create index if not exists idx_courts_facility on public.courts(facility_id);
create index if not exists idx_courts_owner on public.courts(owner_id);
create index if not exists idx_events_facility on public.events(facility_id);
create index if not exists idx_events_organizer on public.events(organizer_id);
create index if not exists idx_events_date on public.events(event_date);
create index if not exists idx_event_regs_event on public.event_registrations(event_id);
create index if not exists idx_event_regs_player on public.event_registrations(player_id);
