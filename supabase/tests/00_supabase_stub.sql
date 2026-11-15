-- Stand-in for the parts of Supabase the schema relies on, so policies can be tested on plain Postgres.
create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
create extension if not exists pgcrypto;

create schema test; grant usage on schema test to anon, authenticated, service_role;
create table test.results (n serial, label text, ok boolean); grant all on test.results, test.results_n_seq to anon, authenticated, service_role;
create function test.ok(label text, cond boolean) returns void language plpgsql as $$ begin insert into test.results (label, ok) values (label, coalesce(cond, false)); end $$;
-- The statement must be refused with an error.
create function test.denied(label text, q text) returns void language plpgsql as $$
begin begin execute q; exception when others then perform test.ok(label || ' [' || sqlstate || ']', true); return; end; perform test.ok(label || ' (was allowed)', false); end $$;
-- The statement must run and touch exactly n rows (row-level security filters silently on update/delete).
create function test.affects(label text, q text, n int) returns void language plpgsql as $$
declare c int; begin begin execute q; get diagnostics c = row_count; exception when others then perform test.ok(label || ' (error: ' || sqlerrm || ')', false); return; end;
  perform test.ok(label || case when c = n then '' else ' (rows: ' || c || ')' end, c = n); end $$;
create function test.who(u uuid) returns void language sql as $$ select set_config('request.jwt.claim.sub', coalesce(u::text, ''), false) $$;
