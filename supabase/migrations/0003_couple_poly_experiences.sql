-- VOUZ backend schema, part 3: Couple/Poly session modes, satisfaction, shared notes, private memories and plans.
-- Not deployed. Mirrors what the web app does locally (web/index.html, normCats and legacy removal).

-- Sessions: two modes only. Earlier values convert; Solo and Partnered rows are removed, as decided for the product.
alter table public.sessions add column participants smallint, add column satisfaction smallint check (satisfaction between 1 and 5),
  add column shared_note text not null default '' check (char_length(shared_note) <= 500);
alter table public.sessions drop constraint if exists sessions_check;
alter table public.sessions drop constraint if exists sessions_category_check;
alter table public.sessions drop constraint if exists sessions_group_size_check;
update public.sessions set category = 'couple', participants = 2 where category = 'duo';
update public.sessions set category = 'poly', participants = 3 where category = 'trio';
update public.sessions set category = 'poly', participants = least(20, greatest(4, coalesce(group_size, 4))) where category = 'group';
delete from public.sessions where category in ('solo', 'partnered');
alter table public.sessions drop column group_size;
alter table public.sessions add constraint sessions_mode check (
  (category is null and participants is null)
  or (category = 'couple' and participants = 2)
  or (category = 'poly' and participants between 3 and 20));

create or replace function public.upsert_session(s jsonb) returns boolean
language plpgsql security invoker set search_path = public as $$
declare n integer; cat text := s->>'category'; p smallint;
begin
  p := case cat when 'couple' then 2 when 'poly' then (s->>'participants')::smallint else null end;
  insert into sessions (user_id, id, started_at, duration_sec, segments, category, participants, satisfaction, shared_note, title, tags, mood, hr_avg, hr_peak, client_updated_at, deleted_at)
  values (auth.uid(), s->>'id', to_timestamp((s->>'start')::bigint / 1000.0), (s->>'durationSec')::int, s->'segments', cat, p,
          nullif(s->>'satisfaction','')::smallint, coalesce(s->>'sharedNote',''), coalesce(s->>'title',''),
          coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(s->'tags','[]'::jsonb)) x), '{}'),
          nullif(s->>'mood',''), nullif(s->>'hrAvg','')::smallint, nullif(s->>'hrPeak','')::smallint,
          (s->>'updatedAt')::bigint, case when s ? 'deletedAt' then to_timestamp((s->>'deletedAt')::bigint / 1000.0) end)
  on conflict (user_id, id) do update set
    started_at = excluded.started_at, duration_sec = excluded.duration_sec, segments = excluded.segments, category = excluded.category,
    participants = excluded.participants, satisfaction = excluded.satisfaction, shared_note = excluded.shared_note, title = excluded.title,
    tags = excluded.tags, mood = excluded.mood, hr_avg = excluded.hr_avg, hr_peak = excluded.hr_peak,
    client_updated_at = excluded.client_updated_at, deleted_at = excluded.deleted_at
  where sessions.client_updated_at < excluded.client_updated_at;
  get diagnostics n = row_count;
  return n > 0;
end $$;

-- Memories and plans. Private to their owner. Photos are not stored here (device only for now).
create table public.experiences (
  user_id           uuid not null references auth.users (id) on delete cascade,
  id                text not null check (char_length(id) between 1 and 64),
  kind              text not null check (kind in ('done','plan')),
  title             text not null check (char_length(title) between 1 and 80),
  happened_at       timestamptz,
  category          text not null check (category in ('dinner','trip','adventure','movie','celebration','romantic','milestone','other')),
  location          text not null default '' check (char_length(location) <= 80),
  favorite          text not null default '' check (char_length(favorite) <= 200),
  mood              text check (char_length(mood) <= 24),
  notes             text not null default '' check (char_length(notes) <= 2000),
  shared_note       text not null default '' check (char_length(shared_note) <= 500),
  idea              text,
  anniversary       boolean not null default false,
  client_updated_at bigint not null,
  deleted_at        timestamptz,
  primary key (user_id, id),
  check (kind = 'plan' or happened_at is not null),
  check (not anniversary or category = 'milestone')
);
alter table public.experiences enable row level security;
create policy own_exp_rw on public.experiences for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke all on public.experiences from anon, authenticated;
grant select, insert, update, delete on public.experiences to authenticated;

create or replace function public.delete_my_data() returns void
language plpgsql security invoker set search_path = public as $$
begin
  delete from posts where author = auth.uid();
  delete from reactions where user_id = auth.uid();
  delete from comments where author = auth.uid();
  delete from connections where auth.uid() in (requester, addressee);
  delete from connection_prefs where owner = auth.uid();
  delete from blocks where blocker = auth.uid();
  delete from experiences   where user_id = auth.uid();
  delete from sessions      where user_id = auth.uid();
  delete from achievements  where user_id = auth.uid();
  delete from user_settings where user_id = auth.uid();
  delete from profiles      where id = auth.uid();
end $$;

create or replace function public.export_my_data() returns jsonb
language sql stable security invoker set search_path = public as $$
  select jsonb_build_object(
    'app', 'vouz', 'exportedAt', now(),
    'profile',      (select to_jsonb(p) from profiles p where p.id = auth.uid()),
    'settings',     (select data from user_settings where user_id = auth.uid()),
    'sessions',     coalesce((select jsonb_agg(to_jsonb(s) - 'user_id' order by s.started_at) from sessions s where s.user_id = auth.uid() and s.deleted_at is null), '[]'::jsonb),
    'notes',        coalesce((select jsonb_agg(to_jsonb(n) - 'user_id') from session_notes n where n.user_id = auth.uid()), '[]'::jsonb),
    'experiences',  coalesce((select jsonb_agg(to_jsonb(x) - 'user_id' order by x.happened_at) from experiences x where x.user_id = auth.uid() and x.deleted_at is null), '[]'::jsonb),
    'achievements', coalesce((select jsonb_agg(to_jsonb(a) - 'user_id') from achievements a where a.user_id = auth.uid()), '[]'::jsonb),
    'entitlement',  (select to_jsonb(e) - 'user_id' - 'original_transaction_id' from entitlements e where e.user_id = auth.uid()),
    'posts',        coalesce((select jsonb_agg(to_jsonb(p) - 'author') from posts p where p.author = auth.uid()), '[]'::jsonb),
    'comments',     coalesce((select jsonb_agg(to_jsonb(c) - 'author') from comments c where c.author = auth.uid()), '[]'::jsonb))
$$;
