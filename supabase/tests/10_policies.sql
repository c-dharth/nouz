-- Authorization tests. Every check runs as a real `authenticated` (or `anon`) role with row-level security in force.
\set alice '''a0000000-0000-0000-0000-00000000000a'''
\set bob   '''b0000000-0000-0000-0000-00000000000b'''
\set carol '''c0000000-0000-0000-0000-00000000000c'''
insert into auth.users values (:alice), (:bob), (:carol);

-- ================= private data =================
select test.who(:alice); set role authenticated;
insert into profiles (id) values (:alice);
select test.ok('upload a session', upsert_session('{"id":"s1","start":1763150000000,"durationSec":1980,"category":"duo","title":"PRIVATETITLE","tags":["SECRETTAG"],"mood":"Electric","hrAvg":"123","updatedAt":10}'));
insert into session_notes (user_id, session_id, notes, reflection) values (:alice, 's1', 'SECRETNOTE', 'SECRETREFLECTION');
insert into user_settings (user_id, data) values (:alice, '{"showStreak":false}');
insert into achievements (user_id, key) values (:alice, 'first');
select test.ok('retried upload is accepted', upsert_session('{"id":"s1","start":1763150000000,"durationSec":2000,"category":"duo","title":"PRIVATETITLE","updatedAt":11}'));
select test.ok('retried upload does not duplicate', (select count(*) = 1 and max(duration_sec) = 2000 from sessions));
select test.ok('an older copy is turned away', not upsert_session('{"id":"s1","start":1763150000000,"durationSec":5,"updatedAt":9}'));
select test.ok('an older copy never overwrites a newer one', (select duration_sec = 2000 from sessions));
select upsert_session('{"id":"s2","start":1763150000000,"durationSec":60,"updatedAt":5,"deletedAt":1763150000000}');
select test.ok('deletion syncs as a tombstone', (select deleted_at is not null from sessions where id = 's2'));
select test.denied('duration over 24 h is refused', $$select upsert_session('{"id":"s3","start":1,"durationSec":90000,"updatedAt":1}')$$);
select test.denied('unknown category is refused', $$select upsert_session('{"id":"s3","start":1,"durationSec":60,"category":"quartet","updatedAt":1}')$$);
select test.denied('group size without Group is refused', $$select upsert_session('{"id":"s3","start":1,"durationSec":60,"category":"duo","groupSize":5,"updatedAt":1}')$$);
select test.denied('cannot insert a session as someone else', format($$insert into sessions (user_id, id, started_at, duration_sec, client_updated_at) values (%L, 'x', now(), 60, 1)$$, :bob));
select test.denied('cannot grant myself Plus', format($$insert into entitlements values (%L, 'vouz.plus.annual', 'active', 'production', now() + interval '1 year', null, true, 'fake', now())$$, :alice));
reset role;

insert into entitlements values (:alice, 'vouz.plus.monthly', 'active', 'production', now() + interval '20 days', null, true, 'tx1', now());

select test.who(:bob); set role authenticated;
insert into profiles (id) values (:bob);
select test.ok('another user sees none of my sessions', (select count(*) = 0 from sessions));
select test.ok('another user sees none of my notes', (select count(*) = 0 from session_notes));
select test.ok('another user sees none of my settings, achievements or entitlement', (select count(*) = 0 from user_settings) and (select count(*) = 0 from achievements) and (select count(*) = 0 from entitlements));
select test.ok('another user cannot see my profile while social is off', (select count(*) = 1 from profiles));
select test.affects('another user cannot edit my session', $$update sessions set title = 'hacked'$$, 0);
select test.affects('another user cannot delete my session', $$delete from sessions$$, 0);
select test.affects('another user cannot delete my notes', $$delete from session_notes$$, 0);
select test.denied('another user cannot attach notes to my session', format($$insert into session_notes (user_id, session_id, notes) values (%L, 's1', 'x')$$, :alice));
select upsert_session('{"id":"s1","start":1763150000000,"durationSec":60,"updatedAt":99}');
select test.ok('upload with the same id as someone else lands in my account only', (select count(*) = 1 and max(duration_sec) = 60 from sessions));
select test.ok('export holds only my data', (select jsonb_array_length(export_my_data()->'sessions') = 1) and export_my_data()::text not like '%SECRETNOTE%' and export_my_data()::text not like '%PRIVATETITLE%');
reset role;

select test.who(null); set role anon;
select test.denied('signed-out: sessions unreadable', $$select * from sessions$$);
select test.denied('signed-out: notes unreadable', $$select * from session_notes$$);
select test.denied('signed-out: profiles unreadable', $$select * from profiles$$);
select test.denied('signed-out: posts unreadable', $$select * from posts$$);
select test.denied('signed-out: cannot call export', $$select export_my_data()$$);
reset role;

select test.who(:alice); set role authenticated;
select test.ok('my own data is intact after all that', (select title = 'PRIVATETITLE' and duration_sec = 2000 from sessions where id = 's1') and (select notes = 'SECRETNOTE' from session_notes));
select test.ok('I can read my own entitlement', (select status = 'active' from entitlements));
select test.denied('I cannot extend my own entitlement', $$update entitlements set expires_at = now() + interval '10 years'$$);
select test.ok('my export includes notes and leaves out the store transaction id', export_my_data()::text like '%SECRETNOTE%' and export_my_data()::text not like '%tx1%');
reset role;

-- ================= social: off by default =================
select test.who(:alice); set role authenticated;
update profiles set handle = 'ali', social_on = true, is_private = false where id = :alice;
select test.denied('social disabled project-wide: cannot post', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"title":"x"}')$$, :alice));
select test.denied('social disabled project-wide: cannot request a connection', format($$insert into connections (requester, addressee) values (%L, %L)$$, :alice, :bob));
select test.denied('clients cannot switch social on for the project', $$update app_config set value = 'true'$$);
reset role;
select test.who(:bob); set role authenticated;
select test.ok('social disabled project-wide: profiles stay hidden', (select count(*) = 1 from profiles));
reset role;

update app_config set value = 'true'::jsonb where key = 'social_enabled';   -- what the service role would do after review

select test.who(:carol); set role authenticated;
insert into profiles (id, handle) values (:carol, 'caz');
select test.denied('personal switch off: cannot post', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"title":"x"}')$$, :carol));
select test.ok('personal switch off: sees nobody', (select count(*) = 1 from profiles));
update profiles set social_on = true where id = :carol;
reset role;
select test.who(:bob); set role authenticated;
update profiles set handle = 'bobby', social_on = true where id = :bob;
select test.ok('discoverable profile is visible, private one is not', (select count(*) = 1 from profiles where id = :alice) and (select count(*) = 0 from profiles where id = :carol));
reset role;

-- ================= connections =================
select test.who(:alice); set role authenticated;
select test.denied('cannot create a request in someone else''s name', format($$insert into connections (requester, addressee) values (%L, %L)$$, :bob, :alice));
select test.denied('cannot create an already-accepted connection', format($$insert into connections (requester, addressee, status) values (%L, %L, 'accepted')$$, :alice, :bob));
select test.affects('request a connection', format($$insert into connections (requester, addressee) values (%L, %L)$$, :alice, :bob), 1);
select test.affects('the requester cannot accept their own request', $$update connections set status = 'accepted'$$, 0);
insert into posts (id, author, kind, card, caption) values ('00000000-0000-0000-0000-0000000000a1', :alice, 'recap', '{"title":"Recap","duration":"About 35 min","category":"Duo"}', 'CONNCAPTION');
insert into posts (id, author, kind, card, caption, audience) values ('00000000-0000-0000-0000-0000000000a2', :alice, 'achievement', '{"badge":"First Round"}', 'PUBLICCAP', 'everyone');
select test.denied('card with notes is refused by the database', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"title":"x","notes":"SECRETNOTE"}')$$, :alice));
select test.denied('card with a start time is refused', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"title":"x","start":1763150000000}')$$, :alice));
select test.denied('card with mood, tags, heart rate or people is refused', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"mood":"Electric","tags":[],"hrAvg":1,"people":[]}')$$, :alice));
select test.denied('cannot post as someone else', format($$insert into posts (author, kind, card) values (%L, 'recap', '{"title":"x"}')$$, :bob));
reset role;

select test.who(:bob); set role authenticated;
select test.ok('pending request: connections-only post is not visible yet', (select count(*) = 0 from posts where caption = 'CONNCAPTION'));
select test.ok('everyone-post is visible to people with social on', (select count(*) = 1 from posts where caption = 'PUBLICCAP'));
select test.affects('the person asked can accept', $$update connections set status = 'accepted'$$, 1);
select test.ok('accepted connection sees the connections-only post', (select count(*) = 1 from posts where caption = 'CONNCAPTION'));
select test.affects('connection can react', format($$insert into reactions values ('00000000-0000-0000-0000-0000000000a1', %L, '🔥')$$, :bob), 1);
select test.affects('connection can comment', format($$insert into comments (id, post_id, author, body) values ('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-0000000000a1', %L, 'nice')$$, :bob), 1);
select test.denied('cannot comment as someone else', format($$insert into comments (post_id, author, body) values ('00000000-0000-0000-0000-0000000000a1', %L, 'x')$$, :alice));
select test.affects('cannot edit someone else''s post', $$update posts set caption = 'hacked'$$, 0);
select test.affects('cannot delete someone else''s post', $$delete from posts$$, 0);
select test.denied('cannot hide a comment on someone else''s post', $$select hide_comment('00000000-0000-0000-0000-0000000000c1', true)$$);
select test.ok('a social post never exposes session rows', (select count(*) = 1 from sessions where user_id = :bob) and (select count(*) = 0 from sessions where user_id = :alice));
reset role;

select test.who(:carol); set role authenticated;
select test.ok('unconnected user cannot see the connections-only post', (select count(*) = 0 from posts where caption = 'CONNCAPTION'));
select test.ok('...nor its reactions or comments', (select count(*) = 0 from reactions) and (select count(*) = 0 from comments));
select test.denied('...nor react to it', format($$insert into reactions values ('00000000-0000-0000-0000-0000000000a1', %L, '🔥')$$, :carol));
select test.denied('...nor comment on it', format($$insert into comments (post_id, author, body) values ('00000000-0000-0000-0000-0000000000a1', %L, 'x')$$, :carol));
select test.ok('...nor see who is connected to whom', (select count(*) = 0 from connections));
select test.affects('report a post', format($$insert into reports (reporter, post_id, about_user, reason) values (%L, '00000000-0000-0000-0000-0000000000a2', %L, 'Harassment')$$, :carol, :alice), 1);
select test.denied('reports are write-only for clients', $$select * from reports$$);
reset role;

-- ================= audiences, permissions, hiding, blocking =================
select test.who(:alice); set role authenticated;
select test.denied('reported user cannot read reports', $$select * from reports$$);
select hide_comment('00000000-0000-0000-0000-0000000000c1', true);
insert into connection_prefs (owner, other, see_recaps) values (:alice, :bob, false);
reset role;
select test.who(:bob); set role authenticated;
select test.ok('permission off: connection loses recaps', (select count(*) = 0 from posts where caption = 'CONNCAPTION'));
select test.affects('cannot change someone else''s sharing permission', $$update connection_prefs set see_recaps = true$$, 0);
reset role;
select test.who(:alice); set role authenticated;
update connection_prefs set see_recaps = true where other = :bob;
update posts set audience = 'selected' where caption = 'CONNCAPTION';
reset role;
select test.who(:bob); set role authenticated;
select test.ok('selected audience: not chosen, not visible', (select count(*) = 0 from posts where caption = 'CONNCAPTION'));
select test.denied('cannot add myself to someone''s audience', format($$insert into post_audience values ('00000000-0000-0000-0000-0000000000a1', %L)$$, :bob));
reset role;
select test.who(:alice); set role authenticated;
select test.denied('audience can only include connections', format($$insert into post_audience values ('00000000-0000-0000-0000-0000000000a1', %L)$$, :carol));
insert into post_audience values ('00000000-0000-0000-0000-0000000000a1', :bob);
reset role;
select test.who(:bob); set role authenticated;
select test.ok('selected audience: chosen person sees it', (select count(*) = 1 from posts where caption = 'CONNCAPTION'));
select test.ok('hidden comment stays visible to its writer only', (select count(*) = 1 from comments));
reset role;
select test.who(:alice); set role authenticated;
insert into blocks values (:alice, :bob);
select test.ok('blocking removes the connection and the audience entry', (select count(*) = 0 from connections) and (select count(*) = 0 from post_audience));
reset role;
select test.who(:bob); set role authenticated;
select test.ok('blocked: no posts, not even public ones', (select count(*) = 0 from posts where author = :alice));
select test.ok('blocked: profile not visible', (select count(*) = 0 from profiles where id = :alice));
select test.denied('blocked: cannot send a new request', format($$insert into connections (requester, addressee) values (%L, %L)$$, :bob, :alice));
select test.ok('blocked person cannot see that they are blocked', (select count(*) = 0 from blocks));
reset role;

-- ================= turning social off, deletion =================
select test.who(:alice); set role authenticated;
update profiles set social_on = false where id = :alice;
select test.affects('post deletion still works with social off', $$delete from posts where caption = 'CONNCAPTION'$$, 1);
reset role;
select test.who(:carol); set role authenticated;
select test.ok('author turned social off: their public post disappears for others', (select count(*) = 0 from posts where caption = 'PUBLICCAP'));
reset role;
select test.who(:alice); set role authenticated;
select delete_my_data();
select test.ok('account erasure: nothing of mine is left', (select count(*) = 0 from sessions) and (select count(*) = 0 from session_notes) and (select count(*) = 0 from profiles) and (select count(*) = 0 from posts) and (select count(*) = 0 from user_settings) and (select count(*) = 0 from achievements));
reset role;
select test.ok('account erasure leaves other users untouched', (select count(*) = 1 from sessions where user_id = :bob) and (select count(*) = 2 from profiles));
select test.ok('erasure really removed rows (checked without row-level security)', (select count(*) = 0 from sessions where user_id = :alice) and (select count(*) = 0 from session_notes) and (select count(*) = 0 from posts));
delete from auth.users where id = :bob;
select test.ok('deleting the login cascades to every table', (select count(*) = 0 from sessions) and (select count(*) = 0 from profiles where id = :bob) and (select count(*) = 0 from comments) and (select count(*) = 0 from reactions));
select test.ok('every public table has row-level security on', (select bool_and(relrowsecurity) from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r'));
select test.ok('anon has no table privileges at all', (select count(*) = 0 from information_schema.role_table_grants where grantee = 'anon' and table_schema = 'public'));
