-- Feed: Explore & Friends, media, saves, couple profiles, notifications, moderation. Run as signed-in users with RLS in force.
\set fay  '''10000000-0000-0000-0000-000000000001'''
\set gus  '''20000000-0000-0000-0000-000000000002'''
\set hal  '''30000000-0000-0000-0000-000000000003'''
\set mo   '''40000000-0000-0000-0000-000000000004'''
\set pub  '''00000000-0000-0000-0000-0000000000f1'''
\set fri  '''00000000-0000-0000-0000-0000000000f2'''
\set prv  '''00000000-0000-0000-0000-0000000000f3'''
\set jnt  '''00000000-0000-0000-0000-0000000000f4'''
insert into auth.users values (:fay), (:gus), (:hal), (:mo);
select test.who(:fay); set role authenticated; insert into profiles (id, handle, social_on, is_private) values (:fay, 'fay', true, false); reset role;
select test.who(:gus); set role authenticated; insert into profiles (id, handle, social_on, is_private) values (:gus, 'gus', true, false); reset role;
select test.who(:hal); set role authenticated; insert into profiles (id, handle, social_on, is_private) values (:hal, 'hal', true, false); reset role;
select test.who(:mo);  set role authenticated; insert into profiles (id, handle, social_on, is_private) values (:mo, 'mo', true, false); reset role;

-- fay and gus are friends; hal is not
select test.who(:fay); set role authenticated; insert into connections (requester, addressee) values (:fay, :gus); reset role;
select test.who(:gus); set role authenticated; update connections set status = 'accepted' where requester = :fay; reset role;
select test.who(:fay); set role authenticated;
select test.ok('notify: an accepted request tells the requester', exists (select 1 from notifications where kind = 'friend_accepted'));
insert into posts (id, author, kind, card, caption, audience, location_tag, category) values (:pub, :fay, 'date', '{}', 'PUBLICDATE dinner by the water, highly recommend', 'everyone', 'Mission District', 'dinner');
insert into posts (id, author, kind, card, caption, audience) values (:fri, :fay, 'photo', '{}', 'FRIENDSONLY', 'connections');
insert into posts (id, author, kind, card, caption, audience) values (:prv, :fay, 'idea', '{}', 'PRIVATEONE', 'selected');
insert into post_audience values (:prv, :gus);
select test.denied('place tag: a street address is refused', format($$insert into posts (author, kind, card, audience, location_tag) values (%L, 'trip', '{}', 'everyone', '123 Main St')$$, :fay));
select test.denied('place tag: coordinates are refused', format($$insert into posts (author, kind, card, audience, location_tag) values (%L, 'trip', '{}', 'everyone', '37.77,-122.41')$$, :fay));
select test.denied('a post kind outside the list is refused', format($$insert into posts (author, kind, card) values (%L, 'session', '{}')$$, :fay));
insert into post_media (post_id, owner, kind, mime, bytes, width, height, storage_path) values (:pub, :fay, 'image', 'image/jpeg', 120000, 1080, 1350, :fay || '/m1');
insert into post_media (post_id, owner, kind, mime, bytes, duration_sec, storage_path) values (:fri, :fay, 'video', 'video/mp4', 900000, 12, :fay || '/m2');
select test.denied('media: a video over 60 seconds is refused', format($$insert into post_media (post_id, owner, kind, mime, bytes, duration_sec, storage_path) values (%L, %L, 'video', 'video/mp4', 1000, 61, %L)$$, :fri, :fay, :fay || '/m3'));
select test.denied('media: a video over 10 MB is refused', format($$insert into post_media (post_id, owner, kind, mime, bytes, storage_path) values (%L, %L, 'video', 'video/mp4', 11000000, %L)$$, :fri, :fay, :fay || '/m4'));
select test.denied('media: a file stored under someone else''s folder is refused', format($$insert into post_media (post_id, owner, kind, mime, bytes, storage_path) values (%L, %L, 'image', 'image/jpeg', 1000, %L)$$, :fri, :fay, :gus || '/m5'));
reset role;

select test.who(:gus); set role authenticated;
select test.ok('friends: a friend sees Public, Friends and their Private post', (select count(*) = 3 from friends_feed()));
select test.ok('friends: newest first', (select array_agg(caption) from friends_feed())[1] = 'PRIVATEONE');
select test.ok('friends: pagination', (select count(*) = 1 from friends_feed(null, 1)) and (select count(*) = 2 from friends_feed((select created_at from posts where id = :prv), 10)));
select test.ok('media: a friend can read the friends-only video''s index', (select count(*) = 2 from post_media));
select test.denied('media: nobody can attach files to someone else''s post', format($$insert into post_media (post_id, owner, kind, mime, bytes, storage_path) values (%L, %L, 'image', 'image/jpeg', 1000, %L)$$, :pub, :gus, :gus || '/x'));
reset role;

select test.who(:hal); set role authenticated;
select test.ok('privacy: a non-friend sees only the public post', (select array_agg(caption) from posts where author = :fay) = array['PUBLICDATE dinner by the water, highly recommend']);
select test.ok('privacy: and only the public post''s media', (select count(*) = 1 from post_media));
select test.ok('friends: empty for a non-friend', not exists (select 1 from friends_feed()));
select test.ok('explore: public post with every factor and a total', (select total = rec + eng + intr + qual + div and qual = 5 + 3 + 2 from explore_feed()));
select test.ok('explore: interests raise a post', (select intr from explore_feed('ranked', array['dinner'])) = 15);
select test.ok('explore: search and kind filter', (select count(*) = 1 from explore_feed('ranked', '{}', null, 'mission')) and not exists (select 1 from explore_feed('ranked', '{}', 'trip')));
insert into reactions (post_id, user_id, emoji) values (:pub, :hal, '❤️');
insert into saved_posts (user_id, post_id) values (:hal, :pub);
select test.denied('saved: can''t save a post you can''t see', format($$insert into saved_posts (user_id, post_id) values (%L, %L)$$, :hal, :fri));
select test.denied('likes: can''t like a post you can''t see', format($$insert into reactions (post_id, user_id, emoji) values (%L, %L, '❤️')$$, :fri, :hal));
select test.ok('explore: engagement counts the like', (select eng from explore_feed()) = 10);
reset role;

select test.who(:fay); set role authenticated;
select test.ok('notify: the author hears about the like', exists (select 1 from notifications where kind = 'like' and actor = :hal));
select test.ok('saved: other people can''t see who saved', not exists (select 1 from saved_posts));
select test.affects('edit: the author can change the caption', format($$update posts set caption = 'EDITED' where id = %L$$, :pub), 1);
select test.ok('edit: marked as edited', (select edited_at is not null from posts where id = :pub));
-- couple profile
insert into couple_profiles (member_a, member_b, name) values (:fay, :gus, 'Fay and Gus');
reset role;
select test.who(:hal); set role authenticated;
select test.ok('couple: not public until both approve', not exists (select 1 from couple_profiles));
select test.denied('couple: can''t create one for other people', format($$insert into couple_profiles (member_a, member_b, name) values (%L, %L, 'x')$$, :fay, :gus));
reset role;
select test.who(:gus); set role authenticated;
select test.ok('notify: the partner is asked', exists (select 1 from notifications where kind = 'couple_proposal'));
select test.denied('couple: can''t approve on the other member''s behalf', $$update couple_profiles set approved_a = false$$);
update couple_profiles set approved_b = true;
reset role;
select test.who(:hal); set role authenticated;
select test.ok('couple: public once both approve', (select count(*) = 1 from couple_profiles));
reset role;
select test.who(:fay); set role authenticated;
insert into posts (id, author, kind, card, caption, audience, couple_id) values (:jnt, :fay, 'trip', '{}', 'JOINT', 'everyone', (select id from couple_profiles));
select test.denied('joint: can''t post as a couple you''re not in', format($$insert into posts (author, kind, card, audience, couple_id) values (%L, 'trip', '{}', 'everyone', (select id from couple_profiles))$$, :hal));
reset role;
select test.who(:hal); set role authenticated;
select test.ok('joint: hidden until the partner approves the post', not exists (select 1 from posts where id = :jnt));
select test.denied('joint: only the partner can approve it', format($$insert into couple_post_approvals (post_id, approver) values (%L, %L)$$, :jnt, :hal));
reset role;
select test.who(:gus); set role authenticated;
insert into couple_post_approvals (post_id, approver) values (:jnt, :gus);
reset role;
select test.who(:hal); set role authenticated;
select test.ok('joint: visible after approval', exists (select 1 from posts where id = :jnt));
reset role;
select test.who(:fay); set role authenticated;
update couple_profiles set name = 'Fay & Gus';
reset role;
select test.who(:hal); set role authenticated;
select test.ok('couple: any edit needs the partner again, and joint posts go with it', not exists (select 1 from couple_profiles) and not exists (select 1 from posts where id = :jnt));
-- block
insert into posts (author, kind, card, caption, audience) values (:hal, 'idea', '{}', 'HALPOST', 'everyone');
insert into blocks (blocker, blocked) values (:hal, :fay);
select test.ok('block: the blocker stops seeing them', not exists (select 1 from posts where author = :fay) and not exists (select 1 from explore_feed()));
reset role;
select test.who(:fay); set role authenticated;
select test.ok('block: the blocked person loses access too', not exists (select 1 from posts where author = :hal));
reset role;
select test.who(:hal); set role authenticated;
delete from blocks where blocker = :hal;
insert into reports (reporter, post_id, reason) values (:hal, :pub, 'Spam');
select test.denied('reports: a reporter can''t read the report list', $$select * from reports$$);
reset role;
select test.who(:mo); set role authenticated;
select test.denied('moderation: non-moderators can''t list reports', $$select * from mod_reports()$$);
select test.denied('moderation: non-moderators can''t remove posts', $$select moderate_remove('00000000-0000-0000-0000-000000000000')$$);
reset role;
insert into moderators values (:mo);   -- what the service role would do
select test.who(:mo); set role authenticated;
select test.ok('moderation: a moderator sees the report', (select count(*) = 1 from mod_reports() where post_id = :pub));
select moderate_remove((select id from mod_reports() where post_id = :pub));
reset role;
select test.ok('moderation: the reported public post and its media are gone', not exists (select 1 from posts where id = :pub) and not exists (select 1 from post_media where storage_path = :fay || '/m1'));
select test.who(:gus); set role authenticated;
select test.ok('notifications are private to their owner', not exists (select 1 from notifications where user_id <> :gus));
reset role;
