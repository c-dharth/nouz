select test.ok('migration: Duo to Couple, Trio and Group to Poly with head counts, unset left alone',
  (select string_agg(id||':'||coalesce(category,'-')||':'||coalesce(participants::text,'-'),',' order by id) from public.sessions where user_id='d0000000-0000-0000-0000-00000000000d')
  = 'duo:couple:2,g:poly:4,g6:poly:6,none:-:-,trio:poly:3');
select test.ok('migration: Solo and Partnered rows removed', (select count(*)=0 from public.sessions where id in ('solo','part')));
delete from auth.users where id='d0000000-0000-0000-0000-00000000000d';
