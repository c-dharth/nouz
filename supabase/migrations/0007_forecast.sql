-- VOUZ 0.11: Daily Forecast. Private check-ins, opt-in sharing with one partner, and one forecast per pair per day.
-- The forecast text is made by the app (rules, optionally rewritten by Claude through an Edge Function); the database
-- only stores it and decides who may read it. Nothing here reads sessions.

create table public.daily_checkins (
  user_id  uuid not null references public.profiles (id) on delete cascade,
  day      date not null,
  energy   text not null check (energy in ('Playful','Tender','Restless','Reflective','Adventurous','Close','Tired','Distant','Curious','Calm')),
  close    smallint check (close between 1 and 5),
  wants    text[] not null default '{}' check (cardinality(wants) <= 3 and wants <@ array['talk','adventure','quiet','closeness','romance','fun']),
  at       timestamptz not null default now(),
  primary key (user_id, day)
);

-- Opting in to a forecast together. A pair is "together" only when both rows exist.
create table public.forecast_share (
  owner        uuid not null references public.profiles (id) on delete cascade,
  partner      uuid not null references public.profiles (id) on delete cascade,
  show_energy  boolean not null default false,   -- may the partner see my energy word, or only the combined result
  created_at   timestamptz not null default now(),
  primary key (owner), check (owner <> partner)
);
create function public.forecast_together(a uuid, b uuid) returns boolean language sql stable security definer set search_path = public as $$
  select connected(a, b) and exists (select 1 from forecast_share where owner = a and partner = b) and exists (select 1 from forecast_share where owner = b and partner = a)
$$;

-- One forecast per pair per day; the first one written wins, so both partners read the same words.
create table public.pair_forecasts (
  member_a  uuid not null references public.profiles (id) on delete cascade,
  member_b  uuid not null references public.profiles (id) on delete cascade,
  day       date not null,
  word      text not null check (word ~ '^[A-Z]{3,12}$'),
  body      jsonb not null check (pg_column_size(body) < 8192 and (body - array['line','dims','sections','move','observed','src','mismatch','hi','lo','v']) = '{}'::jsonb),
  made_by   uuid not null references public.profiles (id),
  created_at timestamptz not null default now(),
  primary key (member_a, member_b, day), check (member_a < member_b)
);

alter table public.daily_checkins  enable row level security;
alter table public.forecast_share  enable row level security;
alter table public.pair_forecasts  enable row level security;

create policy ck_own on public.daily_checkins for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
-- A partner may read check-ins only while both have opted in; the energy word itself only if shown.
create function public.partner_checkins(p_day date) returns table (energy text, close smallint, wants text[]) language sql stable security definer set search_path = public as $$
  select case when s.show_energy then c.energy else null end, c.close, c.wants
  from forecast_share mine join forecast_share s on s.owner = mine.partner and s.partner = auth.uid()
  join daily_checkins c on c.user_id = s.owner and c.day = p_day
  where mine.owner = auth.uid() and forecast_together(auth.uid(), s.owner)
$$;
create policy share_own on public.forecast_share for all to authenticated using (owner = auth.uid()) with check (owner = auth.uid() and connected(owner, partner));
create policy pf_read on public.pair_forecasts for select to authenticated using (auth.uid() in (member_a, member_b) and forecast_together(member_a, member_b));
create policy pf_write on public.pair_forecasts for insert to authenticated with check (made_by = auth.uid() and auth.uid() in (member_a, member_b) and forecast_together(member_a, member_b));

grant select, insert, update, delete on public.daily_checkins, public.forecast_share to authenticated;
grant select, insert on public.pair_forecasts to authenticated;
grant execute on function public.partner_checkins(date), public.forecast_together(uuid, uuid) to authenticated;
