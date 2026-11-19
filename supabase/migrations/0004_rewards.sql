-- VOUZ backend schema, part 4: VOUZ Points, weekly challenges, rewards and redemption.
-- Not deployed. Points are written only by database triggers that look at the user's own records, never by the app,
-- so a modified client can't grant itself points. Every award has a key that can exist once per user.

alter table public.experiences add column planned boolean not null default false, add column done_at timestamptz, add column space_id text,
  add column created_at timestamptz not null default now();

-- Configurable values. Edit rows, not code.
create table public.vp_rules (key text primary key, points int not null check (points >= 0), cap int);
insert into public.vp_rules values ('memory',20,3),('new_kind',50,null),('plan_done',75,2),('bucket',100,2),('session',10,null),('challenge',150,null);

create table public.vp_events (
  user_id    uuid not null references auth.users (id) on delete cascade,
  award_key  text not null,
  points     int  not null check (points >= 0),
  reason     text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, award_key)                 -- the same award can never be given twice
);

create table public.challenges (id text primary key, title text not null, kinds text[], new_place boolean not null default false, active boolean not null default true);
insert into public.challenges (id, title, kinds, new_place) values
 ('newrest','Try a new restaurant','{dinner}',true),('newplace','Go somewhere neither of you has been',null,true),('screenfree','Plan a screen-free date',null,false),
 ('cook','Cook a new recipe together','{dinner,romantic,other}',false),('outdoor','Complete an outdoor adventure','{adventure,trip}',false),('surprise','Surprise your partner with something thoughtful',null,false),
 ('culture','See a show, gallery or museum','{celebration,movie,adventure,other}',false),('theme','Hold a themed movie night','{movie}',false),('green','Take a long walk somewhere green','{adventure,romantic,other}',false),
 ('letters','Write each other a letter',null,false),('learn','Learn something new together','{adventure,other}',false),('brunch','Have a slow brunch','{dinner}',false);

create table public.challenge_completions (
  user_id       uuid not null references auth.users (id) on delete cascade,
  week_start    date not null,
  challenge_id  text not null references public.challenges (id),
  experience_id text not null,
  created_at    timestamptz not null default now(),
  primary key (user_id, week_start)                -- one per week
);

-- Virtual rewards now. A partner reward can only ever be listed once it is verified, has terms, and hasn't expired.
create table public.reward_catalog (
  id         text primary key,
  kind       text not null check (kind in ('virtual','partner')),
  name       text not null,
  cost       int  not null check (cost > 0),
  repeatable boolean not null default false,
  active     boolean not null default true,
  sponsor    text,
  verified   boolean not null default false,
  terms_url  text,
  expires_at timestamptz,
  check (kind = 'virtual' or (sponsor is not null and terms_url is not null and expires_at is not null))
);
insert into public.reward_catalog (id, kind, name, cost, repeatable) values
 ('th_bordeaux','virtual','Bordeaux theme',300,false),('th_midnight','virtual','Midnight theme',400,false),('th_champagne','virtual','Champagne theme',500,false),
 ('fr_rose','virtual','Rose achievement frame',150,false),('fr_gold','virtual','Gold achievement frame',250,false),
 ('st_velvet','virtual','Velvet card style',250,false),('st_champ','virtual','Champagne card style',250,false),('mcard','virtual','Milestone keepsake card',150,true);

create table public.redemptions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  reward_id  text not null references public.reward_catalog (id),
  cost       int  not null,
  created_at timestamptz not null default now()
);

alter table public.vp_rules enable row level security;
alter table public.vp_events enable row level security;
alter table public.challenges enable row level security;
alter table public.challenge_completions enable row level security;
alter table public.reward_catalog enable row level security;
alter table public.redemptions enable row level security;
create policy rules_read on public.vp_rules for select to authenticated using (true);
create policy events_own on public.vp_events for select to authenticated using (user_id = auth.uid());
create policy ch_read on public.challenges for select to authenticated using (active);
create policy chc_own_read on public.challenge_completions for select to authenticated using (user_id = auth.uid());
create policy chc_own_add on public.challenge_completions for insert to authenticated with check (user_id = auth.uid());
create policy catalog_read on public.reward_catalog for select to authenticated using (active and (kind = 'virtual' or (verified and expires_at > now())));
create policy red_own on public.redemptions for select to authenticated using (user_id = auth.uid());
revoke all on public.vp_rules, public.vp_events, public.challenges, public.challenge_completions, public.reward_catalog, public.redemptions from anon, authenticated;
grant select on public.vp_rules, public.vp_events, public.challenges, public.challenge_completions, public.reward_catalog, public.redemptions to authenticated;
grant insert on public.challenge_completions to authenticated;

-- ---- awarding (security definer: the only writers of vp_events) ----
create function public.vp_award(u uuid, k text, rule text, why text, capped_by text default null) returns void
language plpgsql security definer set search_path = public as $$
declare pts int; cap int; used int;
begin
  select points, vp_rules.cap into pts, cap from vp_rules where key = rule;
  if capped_by is not null and cap is not null then
    select count(*) into used from vp_events where user_id = u and award_key like capped_by || ':%' and points > 0 and created_at::date = now()::date;
    if used >= cap then pts := 0; why := why || ' (daily limit reached)'; end if;
  end if;
  insert into vp_events (user_id, award_key, points, reason) values (u, k, pts, why) on conflict (user_id, award_key) do nothing;
end $$;

create function public.vp_on_experience() returns trigger language plpgsql security definer set search_path = public as $$
declare r record;
begin
  if tg_op in ('UPDATE','DELETE') and (tg_op = 'DELETE' or new.deleted_at is not null or new.kind <> 'done') then
    r := old;
    delete from vp_events where user_id = r.user_id and award_key in ('exp:' || r.id, 'plan:' || r.id);
    if not exists (select 1 from experiences where user_id = r.user_id and category = r.category and kind = 'done' and deleted_at is null and id <> r.id) then
      delete from vp_events where user_id = r.user_id and award_key = 'kind:' || r.category;
    end if;
    return null;
  end if;
  if new.kind = 'done' and new.deleted_at is null and new.happened_at is not null and new.happened_at <= now() + interval '1 day' then
    perform vp_award(new.user_id, 'exp:' || new.id, 'memory', 'Memory', 'exp');
    perform vp_award(new.user_id, 'kind:' || new.category, 'new_kind', 'Something new: ' || new.category);
    if new.planned then
      perform vp_award(new.user_id, 'plan:' || new.id, case when new.space_id is null then 'plan_done' else 'bucket' end, 'Plan done', 'plan');
    end if;
  end if;
  return null;
end $$;
create trigger vp_experiences after insert or update or delete on public.experiences for each row execute function public.vp_on_experience();

-- Intimacy: one award per ISO week, never more for more sessions, longer ones, or more people. The reason never describes the session.
create function public.vp_on_session() returns trigger language plpgsql security definer set search_path = public as $$
declare r record; wk text;
begin
  r := case when tg_op = 'DELETE' then old else new end;
  wk := to_char(r.created_at, 'IYYY-IW');
  if tg_op = 'INSERT' and new.deleted_at is null then
    perform vp_award(new.user_id, 'ses:' || wk, 'session', 'Private log');
  elsif not exists (select 1 from sessions where user_id = r.user_id and deleted_at is null and to_char(created_at, 'IYYY-IW') = wk and not (tg_op = 'DELETE' and id = r.id)) then
    delete from vp_events where user_id = r.user_id and award_key = 'ses:' || wk;
  end if;
  return null;
end $$;
create trigger vp_sessions after insert or update of deleted_at or delete on public.sessions for each row execute function public.vp_on_session();

-- A challenge counts only with the user's own memory, logged that week, that fits the challenge.
create function public.vp_on_challenge() returns trigger language plpgsql security definer set search_path = public as $$
declare e record; c record;
begin
  select * into c from challenges where id = new.challenge_id and active;
  select * into e from experiences where user_id = new.user_id and id = new.experience_id and kind = 'done' and deleted_at is null;
  if c is null or e is null then raise exception 'challenge not completed by that memory' using errcode = '23514'; end if;
  if date_trunc('week', e.created_at)::date <> new.week_start or new.week_start <> date_trunc('week', now())::date then raise exception 'not this week' using errcode = '23514'; end if;
  if c.kinds is not null and not (e.category = any (c.kinds)) then raise exception 'wrong kind of memory' using errcode = '23514'; end if;
  if c.new_place and (coalesce(trim(e.location),'') = '' or exists (select 1 from experiences x where x.user_id = e.user_id and x.id <> e.id and lower(trim(x.location)) = lower(trim(e.location)) and x.created_at < e.created_at)) then
    raise exception 'not a new place' using errcode = '23514'; end if;
  perform vp_award(new.user_id, 'ch:' || new.week_start, 'challenge', 'Weekly challenge: ' || c.title);
  return new;
end $$;
create trigger vp_challenges before insert on public.challenge_completions for each row execute function public.vp_on_challenge();

create view public.my_points with (security_invoker = true) as
  select coalesce((select sum(points) from vp_events where user_id = auth.uid()), 0) as earned,
         coalesce((select sum(cost) from redemptions where user_id = auth.uid()), 0) as spent;
grant select on public.my_points to authenticated;

-- Spending: checked and recorded in one transaction, one at a time per user.
create function public.redeem_reward(reward text) returns uuid language plpgsql security definer set search_path = public as $$
declare r record; earned int; spent int; rid uuid;
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = '42501'; end if;
  perform pg_advisory_xact_lock(hashtext(auth.uid()::text));
  select * into r from reward_catalog where id = reward and active and (kind = 'virtual' or (verified and expires_at > now()));
  if r is null then raise exception 'not available' using errcode = '23514'; end if;
  if not r.repeatable and exists (select 1 from redemptions where user_id = auth.uid() and reward_id = reward) then raise exception 'already yours' using errcode = '23505'; end if;
  select coalesce(sum(points),0) into earned from vp_events where user_id = auth.uid();
  select coalesce(sum(cost),0) into spent from redemptions where user_id = auth.uid();
  if earned - spent < r.cost then raise exception 'not enough points' using errcode = '23514'; end if;
  insert into redemptions (user_id, reward_id, cost) values (auth.uid(), reward, r.cost) returning id into rid;
  return rid;
end $$;
revoke all on function public.vp_award(uuid,text,text,text,text) from public, anon, authenticated;
revoke all on function public.redeem_reward(text) from public, anon;
grant execute on function public.redeem_reward(text) to authenticated;
