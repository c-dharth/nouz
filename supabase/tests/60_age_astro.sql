-- 18+ gate on the server, and astrology kept private, separate and deletable.
\set ad '''91000000-0000-0000-0000-000000000001'''
\set kid '''92000000-0000-0000-0000-000000000002'''
\set pa '''93000000-0000-0000-0000-000000000003'''
\set ot '''94000000-0000-0000-0000-000000000004'''
insert into auth.users values (:ad), (:kid), (:pa), (:ot);

select test.who(:kid); set role authenticated;
select test.ok('under 18 (one day short, by the server date): refused', declare_birth_date((current_date - interval '18 years' + interval '1 day')::date) = false);
select test.ok('under 18: no birth date kept', not exists (select 1 from age_records));
select test.ok('under 18: a later, older date does not get round it', declare_birth_date('1990-01-01') = false);
select test.denied('under 18: cannot make a profile', format($$insert into profiles (id, handle) values (%L, 'kid')$$, :kid));
select test.denied('the app cannot write the age record directly', format($$insert into age_records (user_id, birth_date) values (%L, '1990-01-01')$$, :kid));
reset role;
select test.ok('under 18: only the time of the attempt is kept', (select count(*) from age_blocks where user_id = :kid) = 1);
select test.denied('even with full access, the trigger refuses an under-18 date', format($$insert into age_records (user_id, birth_date) values (%L, current_date - 3650)$$, :kid));

select test.who(:ad); set role authenticated;
select test.ok('turns 18 today: allowed', declare_birth_date((current_date - interval '18 years')::date));
insert into profiles (id, handle, social_on) values (:ad, 'ad', true);
select declare_birth_date('1995-11-08') as fixed \gset
select test.ok('correction: a new date is checked again', :'fixed'::boolean and (select birth_date from age_records) = '1995-11-08');
select test.ok('correction to an under-18 date is refused and leaves the old date', declare_birth_date(current_date - 100) = false);
reset role;
select test.ok('...and it is the blocked state now, kept without a date', (select birth_date from age_records where user_id = :ad) = '1995-11-08');
delete from age_blocks where user_id = :ad;

select test.who(:pa); set role authenticated; select declare_birth_date('1993-04-02'); insert into profiles (id, handle, social_on) values (:pa, 'pa', true); reset role;
select test.who(:ot); set role authenticated; select declare_birth_date('1980-06-15'); insert into profiles (id, handle, social_on) values (:ot, 'ot', true); reset role;
select test.who(:ad); set role authenticated; insert into connections (requester, addressee) values (:ad, :pa); reset role;
select test.who(:pa); set role authenticated; update connections set status = 'accepted' where requester = :ad; reset role;

select test.who(:ad); set role authenticated;
insert into astro_profiles (user_id, sun, moon_either, venus, mars, time_unknown, birth_place) values (:ad, 'Scorpio', '{Taurus,Gemini}', 'Libra', 'Sagittarius', true, 'San Francisco');
select test.denied('no Rising without a birth time', format($$update astro_profiles set rising = 'Leo' where user_id = %L$$, :ad));
select test.denied('signs only from the twelve', format($$update astro_profiles set sun = 'Ophiuchus' where user_id = %L$$, :ad));
select test.ok('astrology has no birth date column', not exists (select 1 from information_schema.columns where table_name = 'astro_profiles' and column_name in ('birth_date','dob')));
insert into astro_shares (owner, partner, level) values (:ad, :pa, 'sun');
select test.denied('share only with a connection', format($$insert into astro_shares (owner, partner) values (%L, %L)$$, :ad, :ot));
reset role;

select test.who(:pa); set role authenticated;
select test.ok('partner cannot read the age record', not exists (select 1 from age_records where user_id = :ad));
select test.ok('partner cannot read the astro profile', not exists (select 1 from astro_profiles where user_id = :ad));
select test.ok('partner gets the Sun only at level sun', (select sun = 'Scorpio' and moon_either is null and venus is null and not cards from partner_signs(:ad)));
reset role;
select test.who(:ad); set role authenticated; update astro_shares set level = 'all', cards = true; reset role;
select test.who(:pa); set role authenticated;
select test.ok('level all: Venus and Mars, still no time or place', (select venus = 'Libra' and mars = 'Sagittarius' and cards from partner_signs(:ad)));
reset role;
select test.who(:ot); set role authenticated;
select test.ok('others see nothing', not exists (select 1 from partner_signs(:ad)) and not exists (select 1 from astro_profiles) and not exists (select 1 from age_records where user_id <> :ot));
reset role;
select test.who(:ad); set role authenticated; update astro_profiles set enabled = false; reset role;
select test.who(:pa); set role authenticated; select test.ok('astrology off: partner sees nothing', not exists (select 1 from partner_signs(:ad))); reset role;
select test.who(:ad); set role authenticated;
delete from astro_profiles; delete from astro_shares;
select test.ok('delete: astrology gone, age record untouched', not exists (select 1 from astro_profiles) and exists (select 1 from age_records));
reset role;
