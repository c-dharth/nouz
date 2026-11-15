-- VOUZ backend schema, part 1: private data.
-- Not deployed anywhere. Apply with `supabase db push` only after review.
-- Rule of the whole schema: a row is readable and writable only by the user it belongs to.
-- Nothing is granted to `anon`. Row-level security is on for every table.

create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  handle      text unique check (handle is null or char_length(handle) between 2 and 24),
  is_private  boolean not null default true,
  social_on   boolean not null default false,      -- off by default, per person
  created_at  timestamptz not null default now()
);

create table public.user_settings (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  data        jsonb not null default '{}'::jsonb check (pg_column_size(data) < 16384),
  updated_at  timestamptz not null default now()
);

-- One row per session. `id` is the client's id, so a retried upload updates instead of duplicating.
create table public.sessions (
  user_id           uuid not null references auth.users (id) on delete cascade,
  id                text not null check (char_length(id) between 1 and 64),
  started_at        timestamptz not null,
  duration_sec      integer not null check (duration_sec between 1 and 86400),
  segments          jsonb,
  category          text check (category in ('solo','duo','trio','group','partnered')),
  group_size        smallint check (group_size between 4 and 99),
  title             text not null default '' check (char_length(title) <= 60),
  tags              text[] not null default '{}' check (cardinality(tags) <= 8),
  mood              text check (char_length(mood) <= 24),
  hr_avg            smallint check (hr_avg between 30 and 240),
  hr_peak           smallint check (hr_peak between 30 and 240),
  client_updated_at bigint not null,                -- ms; newer wins on conflict
  deleted_at        timestamptz,                    -- tombstone so deletions reach other devices
  created_at        timestamptz not null default now(),
  primary key (user_id, id),
  check (group_size is null or category = 'group')
);
create index sessions_user_started on public.sessions (user_id, started_at desc);

-- Notes and reflections live apart from session rows so that no query, view or future feature
-- that reads sessions can pick them up by accident.
-- DECISION PENDING: store these as client-side ciphertext (`enc = true`) so the server never holds readable notes.
create table public.session_notes (
  user_id     uuid not null,
  session_id  text not null,
  notes       text not null default '' check (char_length(notes) <= 8000),
  reflection  text not null default '' check (char_length(reflection) <= 4000),
  enc         boolean not null default false,
  updated_at  timestamptz not null default now(),
  primary key (user_id, session_id),
  foreign key (user_id, session_id) references public.sessions (user_id, id) on delete cascade
);

create table public.achievements (
  user_id    uuid not null references auth.users (id) on delete cascade,
  key        text not null check (char_length(key) <= 40),
  earned_at  timestamptz not null default now(),
  primary key (user_id, key)
);

-- Written only by the server after it has verified a receipt with Apple or Google. Clients can read their own row.
create table public.entitlements (
  user_id                  uuid primary key references auth.users (id) on delete cascade,
  product_id               text not null check (product_id in ('vouz.plus.monthly','vouz.plus.annual')),
  status                   text not null check (status in ('active','grace','expired','revoked','refunded')),
  environment              text not null check (environment in ('production','sandbox','mock')),
  expires_at               timestamptz not null,
  grace_until              timestamptz,
  will_renew               boolean not null default true,
  original_transaction_id  text not null,
  verified_at              timestamptz not null default now()
);

alter table public.profiles       enable row level security;
alter table public.user_settings  enable row level security;
alter table public.sessions       enable row level security;
alter table public.session_notes  enable row level security;
alter table public.achievements   enable row level security;
alter table public.entitlements   enable row level security;

create policy own_profile_rw  on public.profiles      for all    to authenticated using (id = auth.uid())      with check (id = auth.uid());
create policy own_settings_rw on public.user_settings for all    to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_sessions_rw on public.sessions      for all    to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_notes_rw    on public.session_notes for all    to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_ach_rw      on public.achievements  for all    to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_ent_read    on public.entitlements  for select to authenticated using (user_id = auth.uid());
-- No insert/update/delete policy on entitlements: only the service role (which bypasses RLS) can write it.

revoke all on all tables in schema public from anon, authenticated;
grant select, insert, update, delete on public.profiles, public.user_settings, public.sessions, public.session_notes, public.achievements to authenticated;
grant select on public.entitlements to authenticated;

-- Conflict handling on the server: an upload never overwrites a newer copy.
create function public.upsert_session(s jsonb) returns boolean
language plpgsql security invoker set search_path = public as $$
declare n integer;
begin
  insert into sessions (user_id, id, started_at, duration_sec, segments, category, group_size, title, tags, mood, hr_avg, hr_peak, client_updated_at, deleted_at)
  values (auth.uid(), s->>'id', to_timestamp((s->>'start')::bigint / 1000.0), (s->>'durationSec')::int, s->'segments',
          s->>'category', (s->>'groupSize')::smallint, coalesce(s->>'title',''),
          coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(s->'tags','[]'::jsonb)) x), '{}'),
          nullif(s->>'mood',''), nullif(s->>'hrAvg','')::smallint, nullif(s->>'hrPeak','')::smallint,
          (s->>'updatedAt')::bigint, case when s ? 'deletedAt' then to_timestamp((s->>'deletedAt')::bigint / 1000.0) end)
  on conflict (user_id, id) do update set
    started_at = excluded.started_at, duration_sec = excluded.duration_sec, segments = excluded.segments, category = excluded.category,
    group_size = excluded.group_size, title = excluded.title, tags = excluded.tags, mood = excluded.mood, hr_avg = excluded.hr_avg,
    hr_peak = excluded.hr_peak, client_updated_at = excluded.client_updated_at, deleted_at = excluded.deleted_at
  where sessions.client_updated_at < excluded.client_updated_at;
  get diagnostics n = row_count;
  return n > 0;      -- false means the server already had a newer copy
end $$;

-- Everything VOUZ holds about the caller, in one document.
create function public.export_my_data() returns jsonb
language sql stable security invoker set search_path = public as $$
  select jsonb_build_object(
    'app', 'vouz', 'exportedAt', now(),
    'profile',      (select to_jsonb(p) from profiles p where p.id = auth.uid()),
    'settings',     (select data from user_settings where user_id = auth.uid()),
    'sessions',     coalesce((select jsonb_agg(to_jsonb(s) - 'user_id' order by s.started_at) from sessions s where s.user_id = auth.uid() and s.deleted_at is null), '[]'::jsonb),
    'notes',        coalesce((select jsonb_agg(to_jsonb(n) - 'user_id') from session_notes n where n.user_id = auth.uid()), '[]'::jsonb),
    'achievements', coalesce((select jsonb_agg(to_jsonb(a) - 'user_id') from achievements a where a.user_id = auth.uid()), '[]'::jsonb),
    'entitlement',  (select to_jsonb(e) - 'user_id' - 'original_transaction_id' from entitlements e where e.user_id = auth.uid()))
$$;

-- Erases every row the caller owns. Removing the login itself (auth.users) needs the service role
-- and is done by the `delete-account` edge function right after this returns.
create function public.delete_my_data() returns void
language plpgsql security invoker set search_path = public as $$
begin
  delete from sessions      where user_id = auth.uid();   -- notes go with them
  delete from achievements  where user_id = auth.uid();
  delete from user_settings where user_id = auth.uid();
  delete from profiles      where id = auth.uid();
end $$;

revoke all on function public.upsert_session(jsonb), public.export_my_data(), public.delete_my_data() from public, anon;
grant execute on function public.upsert_session(jsonb), public.export_my_data(), public.delete_my_data() to authenticated;
