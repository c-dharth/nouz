-- VOUZ backend schema, part 2: optional social.
-- Ships switched off. Two switches must both be on before any social row can be read or written:
--   1. app_config.social_enabled  (project-wide; only the service role can change it)
--   2. profiles.social_on         (per person; off by default)
-- Sessions are never referenced from here. A post holds only a sanitised card.

create table public.app_config (key text primary key, value jsonb not null);
insert into public.app_config values ('social_enabled', 'false'::jsonb);
alter table public.app_config enable row level security;
create policy config_read on public.app_config for select to authenticated using (true);
revoke all on public.app_config from anon, authenticated;
grant select on public.app_config to authenticated;

create function public.social_live() returns boolean language sql stable security definer set search_path = public as $$
  select coalesce((select value = 'true'::jsonb from app_config where key = 'social_enabled'), false)
     and coalesce((select social_on from profiles where id = auth.uid()), false)
$$;

create table public.connections (
  requester  uuid not null references public.profiles (id) on delete cascade,
  addressee  uuid not null references public.profiles (id) on delete cascade,
  status     text not null default 'pending' check (status in ('pending','accepted')),
  created_at timestamptz not null default now(),
  primary key (requester, addressee),
  check (requester <> addressee)
);

-- What I let one particular connection see. No row means both kinds are allowed. Each side sets only their own.
create table public.connection_prefs (
  owner            uuid not null references public.profiles (id) on delete cascade,
  other            uuid not null references public.profiles (id) on delete cascade,
  see_recaps       boolean not null default true,
  see_achievements boolean not null default true,
  primary key (owner, other)
);

create table public.blocks (
  blocker uuid not null references public.profiles (id) on delete cascade,
  blocked uuid not null references public.profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker, blocked),
  check (blocker <> blocked)
);

create table public.posts (
  id         uuid primary key default gen_random_uuid(),
  author     uuid not null references public.profiles (id) on delete cascade,
  kind       text not null check (kind in ('recap','achievement')),
  audience   text not null default 'connections' check (audience in ('connections','selected','everyone')),
  caption    text not null default '' check (char_length(caption) <= 280),
  -- The card is a whitelist. Anything else (notes, mood, tags, heart rate, exact times, who was there) is rejected by the database.
  card       jsonb not null check (
               jsonb_typeof(card) = 'object'
               and (card - array['style','title','duration','arc','category','badge','streakWeeks']) = '{}'::jsonb
               and pg_column_size(card) < 1024),
  created_at timestamptz not null default now()
);
create index posts_author on public.posts (author, created_at desc);

create table public.post_audience (
  post_id uuid not null references public.posts (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  primary key (post_id, user_id)
);

create table public.reactions (
  post_id uuid not null references public.posts (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  emoji   text not null check (emoji in ('🔥','❤️','👏','✨')),
  primary key (post_id, user_id)
);

create table public.comments (
  id         uuid primary key default gen_random_uuid(),
  post_id    uuid not null references public.posts (id) on delete cascade,
  author     uuid not null references public.profiles (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 500),
  hidden     boolean not null default false,          -- the post's author can hide a comment
  created_at timestamptz not null default now()
);

create table public.reports (
  id          uuid primary key default gen_random_uuid(),
  reporter    uuid not null references public.profiles (id) on delete cascade,
  post_id     uuid references public.posts (id) on delete set null,
  comment_id  uuid references public.comments (id) on delete set null,
  about_user  uuid,
  reason      text not null check (char_length(reason) between 1 and 500),
  created_at  timestamptz not null default now(),
  resolved_at timestamptz
);

-- ---- helpers (security definer so policies can consult tables the caller cannot read directly) ----
create function public.is_blocked(a uuid, b uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from blocks where (blocker = a and blocked = b) or (blocker = b and blocked = a))
$$;

create function public.connected(a uuid, b uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from connections where status = 'accepted' and ((requester = a and addressee = b) or (requester = b and addressee = a)))
$$;

-- The one place that decides who may see a post.
create function public.can_view_post(p_id uuid) returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from posts p
    where p.id = p_id
      and ( p.author = auth.uid()
         or ( social_live()
              and not is_blocked(p.author, auth.uid())
              and coalesce((select social_on from profiles where id = p.author), false)
              and ( p.audience = 'everyone'
                 or ( connected(p.author, auth.uid())
                      and coalesce((select case p.kind when 'recap' then cp.see_recaps else cp.see_achievements end
                                    from connection_prefs cp where cp.owner = p.author and cp.other = auth.uid()), true)
                      and ( p.audience = 'connections'
                         or exists (select 1 from post_audience pa where pa.post_id = p.id and pa.user_id = auth.uid()) ) ) ) ) ) )
$$;

revoke all on function public.social_live(), public.is_blocked(uuid, uuid), public.connected(uuid, uuid), public.can_view_post(uuid) from public, anon;
grant execute on function public.social_live(), public.is_blocked(uuid, uuid), public.connected(uuid, uuid), public.can_view_post(uuid) to authenticated;

alter table public.connections   enable row level security;
alter table public.blocks        enable row level security;
alter table public.connection_prefs enable row level security;
alter table public.posts         enable row level security;
alter table public.post_audience enable row level security;
alter table public.reactions     enable row level security;
alter table public.comments      enable row level security;
alter table public.reports       enable row level security;

-- Other people's profiles: handle only matters once both sides have social on, the profile is discoverable or connected, and nobody is blocked.
create policy social_profiles_read on public.profiles for select to authenticated
  using (social_live() and social_on and not is_blocked(id, auth.uid()) and (not is_private or connected(id, auth.uid())
         or exists (select 1 from connections c where c.requester = profiles.id and c.addressee = auth.uid())));

create policy conn_read   on public.connections for select to authenticated using (social_live() and auth.uid() in (requester, addressee));
create policy conn_ask    on public.connections for insert to authenticated with check (social_live() and requester = auth.uid() and status = 'pending' and not is_blocked(requester, addressee));
-- Only the person who was asked can accept; either side can adjust nothing else about the other.
create policy conn_accept on public.connections for update to authenticated using (social_live() and addressee = auth.uid()) with check (addressee = auth.uid());
create policy conn_leave  on public.connections for delete to authenticated using (auth.uid() in (requester, addressee));

create policy prefs_rw on public.connection_prefs for all to authenticated using (owner = auth.uid()) with check (owner = auth.uid());
create policy blocks_rw on public.blocks for all to authenticated using (blocker = auth.uid()) with check (blocker = auth.uid());

create policy posts_read   on public.posts for select to authenticated using (can_view_post(id));
create policy posts_write  on public.posts for insert to authenticated with check (social_live() and author = auth.uid());
create policy posts_edit   on public.posts for update to authenticated using (author = auth.uid()) with check (author = auth.uid());
create policy posts_delete on public.posts for delete to authenticated using (author = auth.uid());   -- always allowed, even with social off

create policy aud_read  on public.post_audience for select to authenticated using (user_id = auth.uid() or exists (select 1 from posts p where p.id = post_id and p.author = auth.uid()));
create policy aud_write on public.post_audience for insert to authenticated with check (exists (select 1 from posts p where p.id = post_id and p.author = auth.uid()) and connected(auth.uid(), user_id));
create policy aud_del   on public.post_audience for delete to authenticated using (exists (select 1 from posts p where p.id = post_id and p.author = auth.uid()));

create policy rx_read  on public.reactions for select to authenticated using (can_view_post(post_id) and not is_blocked(user_id, auth.uid()));
create policy rx_write on public.reactions for insert to authenticated with check (social_live() and user_id = auth.uid() and can_view_post(post_id));
create policy rx_edit  on public.reactions for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid() and can_view_post(post_id));
create policy rx_del   on public.reactions for delete to authenticated using (user_id = auth.uid());

create policy cm_read  on public.comments for select to authenticated
  using (can_view_post(post_id) and not is_blocked(author, auth.uid())
         and (not hidden or author = auth.uid() or exists (select 1 from posts p where p.id = post_id and p.author = auth.uid())));
create policy cm_write on public.comments for insert to authenticated with check (social_live() and author = auth.uid() and not hidden and can_view_post(post_id));
create policy cm_del   on public.comments for delete to authenticated using (author = auth.uid() or exists (select 1 from posts p where p.id = post_id and p.author = auth.uid()));

-- Reports go in and are never readable by clients, including the person reported. Moderators use the service role.
create policy rep_write on public.reports for insert to authenticated with check (reporter = auth.uid());

revoke all on public.connection_prefs from anon, authenticated;
grant select, insert, update, delete on public.connection_prefs to authenticated;
revoke all on public.connections, public.blocks, public.posts, public.post_audience, public.reactions, public.comments, public.reports from anon, authenticated;
grant select, insert, delete on public.connections, public.blocks, public.post_audience, public.reactions, public.comments to authenticated;
grant update (status) on public.connections to authenticated;
grant update (emoji) on public.reactions to authenticated;
grant select, insert, delete on public.posts to authenticated;
grant update (caption, audience) on public.posts to authenticated;
grant insert on public.reports to authenticated;

-- A post's author hides a comment through this, so that nobody can edit a comment's text.
create function public.hide_comment(c_id uuid, hide boolean) returns void language plpgsql security definer set search_path = public as $$
begin
  update comments c set hidden = hide where c.id = c_id and exists (select 1 from posts p where p.id = c.post_id and p.author = auth.uid());
  if not found then raise exception 'not allowed' using errcode = '42501'; end if;
end $$;
revoke all on function public.hide_comment(uuid, boolean) from public, anon;
grant execute on function public.hide_comment(uuid, boolean) to authenticated;

-- Blocking removes any connection between the two people.
create function public.on_block() returns trigger language plpgsql security definer set search_path = public as $$
begin
  delete from connections where (requester = new.blocker and addressee = new.blocked) or (requester = new.blocked and addressee = new.blocker);
  delete from post_audience pa using posts p where pa.post_id = p.id and ((p.author = new.blocker and pa.user_id = new.blocked) or (p.author = new.blocked and pa.user_id = new.blocker));
  return new;
end $$;
create trigger blocks_cut after insert on public.blocks for each row execute function public.on_block();

-- Social rows are part of account erasure and export too.
create or replace function public.delete_my_data() returns void
language plpgsql security invoker set search_path = public as $$
begin
  delete from posts where author = auth.uid();
  delete from reactions where user_id = auth.uid();
  delete from comments where author = auth.uid();
  delete from connections where auth.uid() in (requester, addressee);
  delete from connection_prefs where owner = auth.uid();
  delete from blocks where blocker = auth.uid();
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
    'achievements', coalesce((select jsonb_agg(to_jsonb(a) - 'user_id') from achievements a where a.user_id = auth.uid()), '[]'::jsonb),
    'entitlement',  (select to_jsonb(e) - 'user_id' - 'original_transaction_id' from entitlements e where e.user_id = auth.uid()),
    'posts',        coalesce((select jsonb_agg(to_jsonb(p) - 'author') from posts p where p.author = auth.uid()), '[]'::jsonb),
    'comments',     coalesce((select jsonb_agg(to_jsonb(c) - 'author') from comments c where c.author = auth.uid()), '[]'::jsonb))
$$;
