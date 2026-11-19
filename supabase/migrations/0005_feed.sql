-- VOUZ 0.7: Feed (Explore & Friends), media, saved posts, couple profiles, notifications, moderation.
-- Builds on 0002. Every rule that decides who sees what lives in the database, not the app.
--   Public   = posts.audience 'everyone'     (Explore, anyone with Social on, unless blocked)
--   Friends  = posts.audience 'connections'  (accepted connections)
--   Private  = posts.audience 'selected'     (the author and the people in post_audience)
-- Nothing here is ever written from intimacy records: posts have no session column, and the card whitelist
-- from 0002 still applies.

-- ---------------- posts: new kinds and fields ----------------
alter table public.posts drop constraint if exists posts_kind_check;
alter table public.posts add constraint posts_kind_check
  check (kind in ('recap','achievement','memory','photo','video','date','trip','milestone','idea'));
alter table public.posts drop constraint if exists posts_caption_check;
alter table public.posts add constraint posts_caption_check check (char_length(caption) <= 500);
alter table public.posts
  add column title        text check (title is null or char_length(title) <= 80),
  add column category     text check (category is null or char_length(category) <= 24),
  add column idea_id      text check (idea_id is null or char_length(idea_id) <= 40),
  -- A place tag is a neighborhood or city. Street numbers, street words and coordinates are refused.
  add column location_tag text check (location_tag is null or (char_length(location_tag) <= 40
                                      and location_tag !~ '[0-9]{2,}'
                                      and location_tag !~* '\m(st|street|ave|avenue|rd|road|apt|unit|suite|blvd|lane|ln|dr|drive)\M')),
  add column couple_id    uuid,
  add column edited_at    timestamptz;
create index posts_public_recent on public.posts (created_at desc) where audience = 'everyone';

-- ---------------- couple profiles ----------------
-- One row per couple. Public only while both members have approved the current version.
create table public.couple_profiles (
  id          uuid primary key default gen_random_uuid(),
  member_a    uuid not null references public.profiles (id) on delete cascade,
  member_b    uuid not null references public.profiles (id) on delete cascade,
  name        text not null check (char_length(name) between 2 and 40),
  bio         text not null default '' check (char_length(bio) <= 200),
  photo_path  text,
  favorites   text[] not null default '{}' check (cardinality(favorites) <= 6),
  badges      text[] not null default '{}' check (cardinality(badges) <= 6),
  approved_a  boolean not null default false,
  approved_b  boolean not null default false,
  updated_at  timestamptz not null default now(),
  check (member_a < member_b)
);
create unique index couple_one_each_a on public.couple_profiles (member_a);
create unique index couple_one_each_b on public.couple_profiles (member_b);
alter table public.posts add constraint posts_couple_fk foreign key (couple_id) references public.couple_profiles (id) on delete set null;

-- Any change to the shared fields withdraws the other member's approval; the editor approves their own version.
create function public.couple_reapprove() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then return new; end if;
  if auth.uid() not in (new.member_a, new.member_b) then raise exception 'not a member'; end if;
  if tg_op = 'INSERT' then
    if not connected(new.member_a, new.member_b) then raise exception 'members must be connected'; end if;
    new.approved_a := auth.uid() = new.member_a; new.approved_b := auth.uid() = new.member_b;
  elsif (new.name, new.bio, new.photo_path, new.favorites, new.badges) is distinct from (old.name, old.bio, old.photo_path, old.favorites, old.badges) then
    new.approved_a := auth.uid() = new.member_a; new.approved_b := auth.uid() = new.member_b; new.updated_at := now();
  else
    -- only approval changes: each member may set their own flag only
    if new.approved_a is distinct from old.approved_a and auth.uid() <> new.member_a then raise exception 'not yours to approve'; end if;
    if new.approved_b is distinct from old.approved_b and auth.uid() <> new.member_b then raise exception 'not yours to approve'; end if;
  end if;
  new.member_a := coalesce(old.member_a, new.member_a); new.member_b := coalesce(old.member_b, new.member_b);
  return new;
end $$;
create trigger couple_reapprove before insert or update on public.couple_profiles for each row execute function public.couple_reapprove();

create function public.couple_live(c uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from couple_profiles where id = c and approved_a and approved_b)
$$;

-- A post shown as the couple's needs the partner's approval of that exact post.
create table public.couple_post_approvals (
  post_id  uuid not null references public.posts (id) on delete cascade,
  approver uuid not null references public.profiles (id) on delete cascade,
  approved_at timestamptz not null default now(),
  primary key (post_id, approver)
);
create function public.joint_ok(p_id uuid) returns boolean language sql stable security definer set search_path = public as $$
  select p.couple_id is null
      or ( couple_live(p.couple_id)
           and exists (select 1 from couple_profiles c join couple_post_approvals a on a.post_id = p.id
                       where c.id = p.couple_id and a.approver = case when c.member_a = p.author then c.member_b else c.member_a end) )
  from posts p where p.id = p_id
$$;

-- The partner (and only the partner) can approve a joint post they can't see yet.
create function public.can_approve_joint(p_id uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from posts p join couple_profiles c on c.id = p.couple_id
                 where p.id = p_id and auth.uid() in (c.member_a, c.member_b) and p.author <> auth.uid())
$$;
-- Joint posts may only name a couple the author belongs to.
create function public.posts_check_couple() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.couple_id is not null and not exists (select 1 from couple_profiles where id = new.couple_id and new.author in (member_a, member_b)) then
    raise exception 'not your couple';
  end if;
  if tg_op = 'UPDATE' and (new.caption, new.location_tag) is distinct from (old.caption, old.location_tag) then new.edited_at := now(); end if;
  return new;
end $$;
create trigger posts_check_couple before insert or update on public.posts for each row execute function public.posts_check_couple();

-- ---------------- who may see a post (replaces 0002's version; same signature) ----------------
create or replace function public.can_view_post(p_id uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from posts p
    where p.id = p_id
      and ( p.author = auth.uid()
         or ( social_live()
              and not is_blocked(p.author, auth.uid())
              and coalesce((select social_on from profiles where id = p.author), false)
              and joint_ok(p.id)
              and ( p.audience = 'everyone'
                 or ( connected(p.author, auth.uid())
                      and coalesce((select case p.kind when 'recap' then cp.see_recaps else cp.see_achievements end
                                    from connection_prefs cp where cp.owner = p.author and cp.other = auth.uid()), true)
                      and ( p.audience = 'connections'
                         or exists (select 1 from post_audience pa where pa.post_id = p.id and pa.user_id = auth.uid()) ) ) ) ) ) )
$$;

-- ---------------- media ----------------
-- Bytes live in a private storage bucket ('post-media'), path '<author>/<media id>'. This table is the index the
-- bucket's policies consult, so a file is readable exactly when its post is.
create table public.post_media (
  id           uuid primary key default gen_random_uuid(),
  post_id      uuid not null references public.posts (id) on delete cascade,
  owner        uuid not null references public.profiles (id) on delete cascade,
  kind         text not null check (kind in ('image','video')),
  mime         text not null check (mime in ('image/jpeg','video/mp4','video/quicktime','video/webm')),
  bytes        int  not null check (bytes > 0 and bytes <= case when kind = 'video' then 10485760 else 4194304 end),
  width        int  check (width is null or width between 1 and 4096),
  height       int  check (height is null or height between 1 and 4096),
  duration_sec numeric check (duration_sec is null or (kind = 'video' and duration_sec <= 60)),
  storage_path text not null unique,
  position     int  not null default 0 check (position between 0 and 3),
  check (storage_path like owner::text || '/%')
);
create function public.media_owner_ok() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from posts where id = new.post_id and author = new.owner) then raise exception 'not your post'; end if;
  if (select count(*) from post_media where post_id = new.post_id) >= 4 then raise exception 'at most 4 files a post'; end if;
  return new;
end $$;
create trigger media_owner_ok before insert on public.post_media for each row execute function public.media_owner_ok();

-- Storage policies, applied only where Supabase Storage exists (the local test database has no storage schema).
do $$ begin
  if to_regclass('storage.objects') is not null then
    insert into storage.buckets (id, name, public) values ('post-media', 'post-media', false) on conflict (id) do nothing;
    execute $p$create policy post_media_read on storage.objects for select to authenticated using (
      bucket_id = 'post-media' and exists (select 1 from public.post_media m where m.storage_path = name and public.can_view_post(m.post_id)))$p$;
    execute $p$create policy post_media_write on storage.objects for insert to authenticated with check (
      bucket_id = 'post-media' and (storage.foldername(name))[1] = auth.uid()::text)$p$;
    execute $p$create policy post_media_delete on storage.objects for delete to authenticated using (
      bucket_id = 'post-media' and (storage.foldername(name))[1] = auth.uid()::text)$p$;
  end if;
end $$;

-- ---------------- saved posts (private to the saver) ----------------
create table public.saved_posts (
  user_id  uuid not null references public.profiles (id) on delete cascade,
  post_id  uuid not null references public.posts (id) on delete cascade,
  saved_at timestamptz not null default now(),
  primary key (user_id, post_id)
);

-- ---------------- profile fields ----------------
alter table public.profiles
  add column bio         text not null default '' check (char_length(bio) <= 160),
  add column avatar_path text;

-- ---------------- notifications ----------------
-- Written only by triggers. Never about intimacy records.
create table public.notifications (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles (id) on delete cascade,
  kind       text not null check (kind in ('friend_request','friend_accepted','like','comment','couple_proposal','joint_post')),
  actor      uuid references public.profiles (id) on delete cascade,
  post_id    uuid references public.posts (id) on delete cascade,
  created_at timestamptz not null default now(),
  read_at    timestamptz
);
create index notifications_user on public.notifications (user_id, created_at desc);

create function public.notify(u uuid, k text, a uuid, p uuid) returns void language sql security definer set search_path = public as $$
  insert into notifications (user_id, kind, actor, post_id) select u, k, a, p where u <> a and not is_blocked(u, a)
$$;
revoke all on function public.notify(uuid, text, uuid, uuid) from public, anon, authenticated;

create function public.notify_rx() returns trigger language plpgsql security definer set search_path = public as $$
begin perform notify((select author from posts where id = new.post_id), 'like', new.user_id, new.post_id); return new; end $$;
create trigger notify_rx after insert on public.reactions for each row execute function public.notify_rx();
create function public.notify_cm() returns trigger language plpgsql security definer set search_path = public as $$
begin perform notify((select author from posts where id = new.post_id), 'comment', new.author, new.post_id); return new; end $$;
create trigger notify_cm after insert on public.comments for each row execute function public.notify_cm();
create function public.notify_conn() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' then perform notify(new.addressee, 'friend_request', new.requester, null);
  elsif new.status = 'accepted' and old.status <> 'accepted' then perform notify(new.requester, 'friend_accepted', new.addressee, null); end if;
  return new;
end $$;
create trigger notify_conn after insert or update on public.connections for each row execute function public.notify_conn();
create function public.notify_couple() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if not (new.approved_a and new.approved_b) then
    perform notify(case when auth.uid() = new.member_a then new.member_b else new.member_a end, 'couple_proposal', auth.uid(), null);
  end if; return new;
end $$;
create trigger notify_couple after insert or update on public.couple_profiles for each row execute function public.notify_couple();
create function public.notify_joint() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.couple_id is not null then
    perform notify((select case when member_a = new.author then member_b else member_a end from couple_profiles where id = new.couple_id), 'joint_post', new.author, new.id);
  end if; return new;
end $$;
create trigger notify_joint after insert on public.posts for each row execute function public.notify_joint();

-- ---------------- moderation ----------------
create table public.moderators (user_id uuid primary key references public.profiles (id) on delete cascade);
create function public.is_moderator() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from moderators where user_id = auth.uid())
$$;
-- Moderators see reports and can remove a reported public post. They never see Friends or Private content.
create function public.moderate_remove(p_report uuid) returns void language plpgsql security definer set search_path = public as $$
declare r reports;
begin
  if not is_moderator() then raise exception 'moderators only'; end if;
  select * into r from reports where id = p_report and resolved_at is null;
  if not found then raise exception 'no open report'; end if;
  if r.post_id is not null and (select audience from posts where id = r.post_id) = 'everyone' then delete from posts where id = r.post_id; end if;
  update reports set resolved_at = now() where id = p_report;
end $$;
-- Reports stay write-only for everyone else; moderators read open ones through this.
create function public.mod_reports() returns setof public.reports language plpgsql stable security definer set search_path = public as $$
begin if not is_moderator() then raise exception 'moderators only'; end if; return query select * from reports where resolved_at is null order by created_at desc; end $$;
create function public.moderate_dismiss(p_report uuid) returns void language plpgsql security definer set search_path = public as $$
begin if not is_moderator() then raise exception 'moderators only'; end if; update reports set resolved_at = now() where id = p_report; end $$;

-- ---------------- feeds ----------------
-- Explore: public posts, ranked by recency, engagement, interests and detail, with each factor returned so the app can
-- show "why this post". No author appears twice in a row's top ten for free: repeats lose 12 points each.
-- p_mode 'latest' skips ranking entirely. Keyset pagination on (created_at, id).
create function public.explore_feed(p_mode text default 'ranked', p_interests text[] default '{}', p_kind text default null,
                                    p_q text default null, p_limit int default 10, p_offset int default 0)
returns table (post_id uuid, author uuid, created_at timestamptz, rec int, eng int, intr int, qual int, div int, total int)
language sql stable security definer set search_path = public as $$
  with base as (
    select p.id, p.author, p.created_at, p.kind, p.category, p.caption, p.location_tag,
           least(40, round(40 * power(0.5, extract(epoch from now() - p.created_at) / 3600 / 72)))::int as rec,
           least(25, round(10 * log(2, 1 + (select count(*) from reactions r where r.post_id = p.id and not is_blocked(r.user_id, auth.uid()))
                                        + 2 * (select count(*) from comments c where c.post_id = p.id and not c.hidden))))::int as eng,
           (case when p.category = any(p_interests) then 15 else 0 end)::int as intr,
           ((case when exists (select 1 from post_media m where m.post_id = p.id) then 5 else 0 end)
            + (case when char_length(p.caption) >= 30 then 3 else 0 end)
            + (case when p.location_tag is not null then 2 else 0 end))::int as qual
    from posts p
    where p.audience = 'everyone' and p.author <> auth.uid() and can_view_post(p.id)
      and (p_kind is null or p.kind = p_kind)
      and (p_q is null or p.caption ilike '%' || p_q || '%' or p.title ilike '%' || p_q || '%' or p.location_tag ilike '%' || p_q || '%')
  ), ranked as (
    select b.*, -12 * (row_number() over (partition by b.author order by b.rec + b.eng + b.intr + b.qual desc) - 1)::int as div from base b
  )
  select id, author, created_at, rec, eng, intr, qual, div, rec + eng + intr + qual + div
  from ranked
  order by case when p_mode = 'latest' then extract(epoch from created_at) else rec + eng + intr + qual + div end desc, id
  limit least(greatest(p_limit, 1), 50) offset greatest(p_offset, 0)
$$;

-- Friends: what friends shared with me, newest first. Keyset pagination with p_before.
create function public.friends_feed(p_before timestamptz default null, p_limit int default 10)
returns setof public.posts language sql stable security definer set search_path = public as $$
  select p.* from posts p
  where p.author <> auth.uid() and connected(p.author, auth.uid()) and can_view_post(p.id)
    and (p_before is null or p.created_at < p_before)
  order by p.created_at desc, p.id
  limit least(greatest(p_limit, 1), 50)
$$;

-- ---------------- row-level security ----------------
alter table public.couple_profiles       enable row level security;
alter table public.couple_post_approvals enable row level security;
alter table public.post_media            enable row level security;
alter table public.saved_posts           enable row level security;
alter table public.notifications         enable row level security;
alter table public.moderators            enable row level security;

create policy couple_read on public.couple_profiles for select to authenticated using (
  auth.uid() in (member_a, member_b)
  or (social_live() and approved_a and approved_b and not is_blocked(member_a, auth.uid()) and not is_blocked(member_b, auth.uid())));
create policy couple_insert on public.couple_profiles for insert to authenticated with check (social_live() and auth.uid() in (member_a, member_b));
create policy couple_update on public.couple_profiles for update to authenticated using (auth.uid() in (member_a, member_b)) with check (auth.uid() in (member_a, member_b));
create policy couple_delete on public.couple_profiles for delete to authenticated using (auth.uid() in (member_a, member_b));   -- either can take it down

create policy cpa_read on public.couple_post_approvals for select to authenticated using (can_view_post(post_id));
create policy cpa_write on public.couple_post_approvals for insert to authenticated with check (approver = auth.uid() and can_approve_joint(post_id));
create policy cpa_delete on public.couple_post_approvals for delete to authenticated using (approver = auth.uid());

create policy media_read   on public.post_media for select to authenticated using (can_view_post(post_id));
create policy media_insert on public.post_media for insert to authenticated with check (social_live() and owner = auth.uid());
create policy media_delete on public.post_media for delete to authenticated using (owner = auth.uid());

create policy saved_rw on public.saved_posts for select to authenticated using (user_id = auth.uid());
create policy saved_add on public.saved_posts for insert to authenticated with check (user_id = auth.uid() and can_view_post(post_id));
create policy saved_del on public.saved_posts for delete to authenticated using (user_id = auth.uid());

create policy notif_read on public.notifications for select to authenticated using (user_id = auth.uid());
create policy notif_mark on public.notifications for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy notif_del  on public.notifications for delete to authenticated using (user_id = auth.uid());


grant select, insert, update, delete on public.couple_profiles to authenticated;
grant select, insert, delete on public.couple_post_approvals, public.post_media, public.saved_posts to authenticated;
grant select, delete on public.notifications to authenticated;
grant update (read_at) on public.notifications to authenticated;
grant update (caption, audience, location_tag) on public.posts to authenticated;
grant insert (title, category, idea_id, location_tag, couple_id) on public.posts to authenticated;
revoke all on function public.explore_feed(text, text[], text, text, int, int), public.friends_feed(timestamptz, int),
  public.moderate_remove(uuid), public.moderate_dismiss(uuid), public.mod_reports(), public.couple_live(uuid), public.joint_ok(uuid), public.can_approve_joint(uuid), public.is_moderator() from public, anon;
grant execute on function public.explore_feed(text, text[], text, text, int, int), public.friends_feed(timestamptz, int),
  public.moderate_remove(uuid), public.moderate_dismiss(uuid), public.mod_reports(), public.couple_live(uuid), public.joint_ok(uuid), public.can_approve_joint(uuid), public.is_moderator() to authenticated;
