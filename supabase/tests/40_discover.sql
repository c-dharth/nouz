-- Discover: saved places, feedback, history and shared taste are private; the provider cache is server-only.
\set ivy '''50000000-0000-0000-0000-000000000005'''
\set jo  '''60000000-0000-0000-0000-000000000006'''
\set kit '''70000000-0000-0000-0000-000000000007'''
insert into auth.users values (:ivy), (:jo), (:kit);
select test.who(:ivy); set role authenticated; insert into profiles (id, handle, social_on) values (:ivy, 'ivy', true); reset role;
select test.who(:jo);  set role authenticated; insert into profiles (id, handle, social_on) values (:jo, 'jo', true); reset role;
select test.who(:kit); set role authenticated; insert into profiles (id, handle, social_on) values (:kit, 'kit', true); reset role;
select test.who(:ivy); set role authenticated; insert into connections (requester, addressee) values (:ivy, :jo); reset role;
select test.who(:jo);  set role authenticated; update connections set status = 'accepted' where requester = :ivy; reset role;

select test.who(:ivy); set role authenticated;
insert into saved_places (user_id, place_id, source, snapshot) values (:ivy, 'yelp:x', 'yelp', '{"name":"A cafe","kind":"coffee","rating":4.5}');
select test.denied('saved place: provider facts only (no notes or coordinates)', format($$insert into saved_places (user_id, place_id, source, snapshot) values (%L, 'yelp:y', 'yelp', '{"name":"x","notes":"private"}')$$, :ivy));
select test.denied('saved place: only Yelp or demo sources', format($$insert into saved_places (user_id, place_id, source, snapshot) values (%L, 'z', 'made-up', '{"name":"x"}')$$, :ivy));
insert into rec_feedback values (:ivy, 'yelp:x', 'coffee', 1);
insert into rec_history (user_id, query, area, results) values (:ivy, 'romantic under $50', 'Mission District', 6);
insert into shared_taste (owner, viewer, weights, price, max_km) values (:ivy, :jo, '{"food":1,"outdoors":0.5}', 2, 8);
select test.denied('taste: can''t share with someone who isn''t a connection', format($$insert into shared_taste (owner, viewer, weights) values (%L, %L, '{"food":1}')$$, :ivy, :kit));
select test.denied('taste: only interest weights, nothing else', format($$insert into shared_taste (owner, viewer, weights) values (%L, %L, '{"intimacy":1}')$$, :jo, :ivy));
select test.denied('provider cache: clients can''t read it', $$select * from provider_cache$$);
reset role;

select test.who(:jo); set role authenticated;
select test.ok('taste: the connection it was shared with can read it', (select count(*) = 1 from shared_taste where owner = :ivy));
select test.ok('private: nobody else sees saved places, feedback or history', not exists (select 1 from saved_places) and not exists (select 1 from rec_feedback) and not exists (select 1 from rec_history));
reset role;
select test.who(:kit); set role authenticated;
select test.ok('taste: others can''t read it', not exists (select 1 from shared_taste));
reset role;
select test.who(:ivy); set role authenticated;
select reset_personalization(); select delete_rec_history();
select test.ok('controls: reset and delete history clear only those', not exists (select 1 from rec_feedback) and not exists (select 1 from rec_history) and exists (select 1 from saved_places));
reset role;
