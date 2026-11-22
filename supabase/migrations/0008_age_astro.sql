-- VOUZ 0.13: 18+ gate and astrology. The age check runs here, with the server's own date, so editing values in the
-- app cannot get round it. A self-entered birthday is an age gate, not proof of age.
-- Astrology lives in its own tables, apart from the age record, and never holds the birth date.

create table public.age_records (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  birth_date  date not null,
  checked_on  date not null default current_date,
  method      text not null default 'self_declared' check (method in ('self_declared')),
  updated_at  timestamptz not null default now()
);
-- Under-18 attempts: when it happened, nothing else. No birth date is kept.
create table public.age_blocks (user_id uuid primary key references auth.users (id) on delete cascade, at timestamptz not null default now());

create function public.age_years(d date, today date) returns int language sql immutable as $$ select extract(year from age(today, d))::int $$;

-- Every write to age_records, by any path, is checked against today's date on the server.
create function public.age_guard() returns trigger language plpgsql as $$
begin
  if new.birth_date > current_date or new.birth_date < date '1900-01-01' then raise exception 'birth date out of range'; end if;
  if age_years(new.birth_date, current_date) < 18 then raise exception 'VOUZ is for adults 18 and older'; end if;
  new.checked_on := current_date; new.updated_at := now(); new.method := 'self_declared';
  return new;
end $$;
create trigger age_guard before insert or update on public.age_records for each row execute function public.age_guard();

-- The only way in from the app. Under 18: nothing is stored but the time of the attempt.
create function public.declare_birth_date(d date) returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'sign in first'; end if;
  if exists (select 1 from age_blocks where user_id = auth.uid()) then return false; end if;
  if d is null or d > current_date or age_years(d, current_date) < 18 then
    insert into age_blocks (user_id) values (auth.uid()) on conflict do nothing;
    return false;
  end if;
  insert into age_records (user_id, birth_date) values (auth.uid(), d)
    on conflict (user_id) do update set birth_date = excluded.birth_date;
  return true;
end $$;

-- New profiles need a passed age check. Profiles made before 0.13 are left alone; the app asks them at next open.
create function public.profile_needs_age() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from age_records where user_id = new.id) then raise exception 'age check required'; end if;
  return new;
end $$;
create trigger profile_needs_age before insert on public.profiles for each row execute function public.profile_needs_age();

alter table public.age_records enable row level security;
alter table public.age_blocks  enable row level security;
-- Owner may read their own birth date, and nobody else. Writes only through declare_birth_date.
create policy age_own_read on public.age_records for select to authenticated using (user_id = auth.uid());
grant select on public.age_records to authenticated;
grant execute on function public.declare_birth_date(date) to authenticated;
revoke execute on function public.age_guard(), public.profile_needs_age() from public;

-- Astrology: optional, owner-only, deletable. Signs only, plus the optional birth time and place the owner chose to keep.
create table public.astro_profiles (
  user_id       uuid primary key references public.profiles (id) on delete cascade,
  enabled       boolean not null default true,
  sun           text check (sun in ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')),
  moon          text check (moon in ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')),
  moon_either   text[] check (moon_either is null or cardinality(moon_either) = 2),
  rising        text check (rising in ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')),
  venus         text check (venus in ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')),
  mars          text check (mars in ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')),
  birth_time    time,
  time_unknown  boolean not null default true,
  birth_place   text check (birth_place is null or char_length(birth_place) <= 120),
  updated_at    timestamptz not null default now(),
  -- Rising needs a birth time; without one it is never stored.
  check (rising is null or (birth_time is not null and not time_unknown)),
  check (moon is null or moon_either is null)
);

-- What one partner lets one other partner see. Pairwise, so poly relationships share per person.
create table public.astro_shares (
  owner    uuid not null references public.profiles (id) on delete cascade,
  partner  uuid not null references public.profiles (id) on delete cascade,
  level    text not null default 'sun' check (level in ('sun','big3','all')),
  cards    boolean not null default false,   -- may the partner put my signs on a share card
  created_at timestamptz not null default now(),
  primary key (owner, partner), check (owner <> partner)
);

alter table public.astro_profiles enable row level security;
alter table public.astro_shares   enable row level security;
create policy astro_own on public.astro_profiles for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy astro_share_own on public.astro_shares for all to authenticated using (owner = auth.uid()) with check (owner = auth.uid() and connected(owner, partner));
grant select, insert, update, delete on public.astro_profiles, public.astro_shares to authenticated;

-- A partner's signs, at the level they chose. Never their birth date, time or place.
create function public.partner_signs(p uuid) returns table (sun text, moon text, moon_either text[], rising text, venus text, mars text, cards boolean)
language sql stable security definer set search_path = public as $$
  select a.sun,
         case when s.level <> 'sun' then a.moon end,
         case when s.level <> 'sun' then a.moon_either end,
         case when s.level <> 'sun' then a.rising end,
         case when s.level = 'all' then a.venus end,
         case when s.level = 'all' then a.mars end,
         s.cards
  from astro_shares s join astro_profiles a on a.user_id = s.owner
  where s.owner = p and s.partner = auth.uid() and a.enabled and connected(p, auth.uid())
$$;
grant execute on function public.partner_signs(uuid) to authenticated;
