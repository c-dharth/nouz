-- Daily Forecast: check-ins private by default, shared only when both opt in, one forecast per pair per day.
\set lu '''81000000-0000-0000-0000-000000000001'''
\set mo2 '''82000000-0000-0000-0000-000000000002'''
\set ned '''83000000-0000-0000-0000-000000000003'''
insert into auth.users values (:lu), (:mo2), (:ned);
select test.who(:lu);  set role authenticated; insert into profiles (id, handle, social_on) values (:lu, 'lu', true); reset role;
select test.who(:mo2); set role authenticated; insert into profiles (id, handle, social_on) values (:mo2, 'mo2', true); reset role;
select test.who(:ned); set role authenticated; insert into profiles (id, handle, social_on) values (:ned, 'ned', true); reset role;
select test.who(:lu);  set role authenticated; insert into connections (requester, addressee) values (:lu, :mo2); reset role;
select test.who(:mo2); set role authenticated; update connections set status = 'accepted' where requester = :lu; reset role;

select test.who(:lu); set role authenticated;
insert into daily_checkins (user_id, day, energy, close, wants) values (:lu, '2026-11-21', 'Playful', 4, '{talk}');
select test.denied('check-in: only the listed energies and wants', format($$insert into daily_checkins (user_id, day, energy) values (%L, '2026-11-20', 'Horny')$$, :lu));
insert into forecast_share (owner, partner, show_energy) values (:lu, :mo2, false);
select test.denied('sharing: only with a connection', format($$update forecast_share set partner = %L$$, :ned));
reset role;

select test.who(:mo2); set role authenticated;
select test.ok('private: a partner sees nothing until both opt in', not exists (select 1 from daily_checkins) and not exists (select 1 from partner_checkins('2026-11-21')));
insert into forecast_share (owner, partner, show_energy) values (:mo2, :lu, true);
insert into daily_checkins (user_id, day, energy) values (:mo2, '2026-11-21', 'Calm');
select test.ok('together: the partner gets the check-in, but not the energy word they kept private', (select energy is null and close = 4 from partner_checkins('2026-11-21')));
insert into pair_forecasts (member_a, member_b, day, word, body, made_by) values (:lu, :mo2, '2026-11-21', 'ALIGNED', '{"line":"x","src":"library"}', :mo2);
select test.denied('one forecast per pair per day', format($$insert into pair_forecasts (member_a, member_b, day, word, body, made_by) values (%L, %L, '2026-11-21', 'TENDER', '{}', %L)$$, :lu, :mo2, :mo2));
select test.denied('forecast body: only the known fields', format($$insert into pair_forecasts (member_a, member_b, day, word, body, made_by) values (%L, %L, '2026-11-22', 'TENDER', '{"sessions":3}', %L)$$, :lu, :mo2, :mo2));
reset role;
select test.who(:lu); set role authenticated;
select test.ok('together: both read the same forecast', (select word from pair_forecasts where day = '2026-11-21') = 'ALIGNED');
select test.ok('together: the energy word is shown when they allow it', (select energy from partner_checkins('2026-11-21')) = 'Calm');
reset role;
select test.who(:ned); set role authenticated;
select test.ok('others see nothing', not exists (select 1 from pair_forecasts) and not exists (select 1 from daily_checkins) and not exists (select 1 from partner_checkins('2026-11-21')));
reset role;
select test.who(:lu); set role authenticated; delete from forecast_share; reset role;
select test.who(:mo2); set role authenticated;
select test.ok('opting out ends access straight away', not exists (select 1 from partner_checkins('2026-11-21')) and not exists (select 1 from pair_forecasts));
reset role;
