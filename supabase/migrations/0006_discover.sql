-- VOUZ 0.8: AI Discover. Saved places, recommendation feedback and history, shared taste for planning together,
-- and a server-side cache for provider results. Provider calls (Yelp etc.) belong in an Edge Function that holds the
-- API key; the app never sees it. Nothing here reads sessions, notes or health data.

-- A place as the provider described it, with when it was fetched. VOUZ never edits these facts.
create table public.saved_places (
  user_id    uuid not null references public.profiles (id) on delete cascade,
  place_id   text not null check (char_length(place_id) <= 160),
  source     text not null check (source in ('yelp','demo')),
  snapshot   jsonb not null check (jsonb_typeof(snapshot) = 'object' and pg_column_size(snapshot) < 4096
                                   and (snapshot - array['name','kind','categories','address','rating','review_count','price','photo','url','fetched_at']) = '{}'::jsonb),
  saved_at   timestamptz not null default now(),
  primary key (user_id, place_id)
);

-- Likes and "not for us". Private to the person.
create table public.rec_feedback (
  user_id   uuid not null references public.profiles (id) on delete cascade,
  place_id  text not null check (char_length(place_id) <= 160),
  kind      text not null check (char_length(kind) <= 24),
  value     smallint not null check (value in (-1, 1)),
  at        timestamptz not null default now(),
  primary key (user_id, place_id)
);

-- Searches, kept so the person can see and delete them. Free text is capped; no location coordinates are stored.
create table public.rec_history (
  id        bigint generated always as identity primary key,
  user_id   uuid not null references public.profiles (id) on delete cascade,
  query     text not null check (char_length(query) <= 200),
  area      text check (area is null or char_length(area) <= 60),
  results   int not null default 0,
  at        timestamptz not null default now()
);

-- What I share with one connection for planning together: interest weights, usual price level, distance. Nothing else.
create table public.shared_taste (
  owner    uuid not null references public.profiles (id) on delete cascade,
  viewer   uuid not null references public.profiles (id) on delete cascade,
  weights  jsonb not null check (jsonb_typeof(weights) = 'object' and pg_column_size(weights) < 1024
                                 and (weights - array['food','outdoors','culture','home','adventure','romance','learning','wellness','music']) = '{}'::jsonb),
  price    smallint check (price between 1 and 4),
  max_km   numeric check (max_km between 0 and 100),
  updated_at timestamptz not null default now(),
  primary key (owner, viewer), check (owner <> viewer)
);

-- Provider results cached by the Edge Function (service role only), so repeated searches don't hit the provider.
create table public.provider_cache (
  key        text primary key,
  source     text not null,
  payload    jsonb not null,
  fetched_at timestamptz not null default now(),
  expires_at timestamptz not null
);

alter table public.saved_places   enable row level security;
alter table public.rec_feedback   enable row level security;
alter table public.rec_history    enable row level security;
alter table public.shared_taste   enable row level security;
alter table public.provider_cache enable row level security;   -- no policies: clients can't read or write it

create policy saved_places_own on public.saved_places for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy rec_feedback_own on public.rec_feedback for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy rec_history_own  on public.rec_history  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
-- Taste is shared only with an accepted connection, and only the owner writes it.
create policy taste_write on public.shared_taste for all to authenticated using (owner = auth.uid()) with check (owner = auth.uid() and connected(owner, viewer));
create policy taste_read  on public.shared_taste for select to authenticated using (viewer = auth.uid() and connected(owner, viewer) and not is_blocked(owner, viewer));

grant select, insert, update, delete on public.saved_places, public.rec_feedback, public.rec_history, public.shared_taste to authenticated;

-- One call wipes personalization; another wipes history. Saved places stay unless asked.
create function public.reset_personalization() returns void language sql security invoker as $$ delete from rec_feedback where user_id = auth.uid() $$;
create function public.delete_rec_history() returns void language sql security invoker as $$ delete from rec_history where user_id = auth.uid() $$;
grant execute on function public.reset_personalization(), public.delete_rec_history() to authenticated;
