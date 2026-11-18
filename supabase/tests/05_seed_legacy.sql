-- Rows written under the earlier categories, before migration 0003 runs.
insert into auth.users values ('d0000000-0000-0000-0000-00000000000d');
insert into public.sessions (user_id, id, started_at, duration_sec, category, group_size, client_updated_at) values
 ('d0000000-0000-0000-0000-00000000000d','solo',now(),60,'solo',null,1),('d0000000-0000-0000-0000-00000000000d','part',now(),60,'partnered',null,1),
 ('d0000000-0000-0000-0000-00000000000d','duo',now(),60,'duo',null,1),('d0000000-0000-0000-0000-00000000000d','trio',now(),60,'trio',null,1),
 ('d0000000-0000-0000-0000-00000000000d','g6',now(),60,'group',6,1),('d0000000-0000-0000-0000-00000000000d','g',now(),60,'group',null,1),
 ('d0000000-0000-0000-0000-00000000000d','none',now(),60,null,null,1);
