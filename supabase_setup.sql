-- 1. Create a table for public profiles mapped securely to Auth instances
create table public.profiles (
  id uuid not null references auth.users on delete cascade,
  first_name text,
  last_name text,
  role text,
  proficiency text,
  phone text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  primary key (id)
);

-- 2. Activate Row Level Security (RLS) on profiles
alter table public.profiles enable row level security;

-- 3. Setup standard accessibility policies
create policy "Public profiles are viewable by everyone."
  on profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on profiles for insert
  with check ( auth.uid() = id );

create policy "Users can update own profile."
  on profiles for update
  using ( auth.uid() = id );

-- 4. Create an automated trigger function to harvest sign up payload metadata
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, first_name, last_name, role, proficiency, phone)
  values (
    new.id,
    new.raw_user_meta_data->>'first_name',
    new.raw_user_meta_data->>'last_name',
    new.raw_user_meta_data->>'role',
    new.raw_user_meta_data->>'proficiency',
    new.raw_user_meta_data->>'phone'
  );
  return new;
end;
$$;

-- 5. Attach the trigger natively to auth.users framework
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
