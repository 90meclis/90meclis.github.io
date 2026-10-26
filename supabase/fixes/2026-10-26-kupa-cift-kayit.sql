begin;
create temp table _g on commit drop as
select unnest(array['ECL:2026-10-22:crvenazvezda:copenhagen','ECL:2026-10-22:redstarbelgrade:copenhagen','ECL:2026-10-22:crvenazvezda:kbenhavn']) id, 1 g
union all select unnest(array['ECL:2026-10-22:aarhus:egnatiarrogozhine','ECL:2026-10-22:aarhus:kfegnatia','ECL:2026-10-22:agf:kfegnatia']), 2
union all select unnest(array['ECL:2026-10-22:boracbanjaluka:kuopionpalloseura','ECL:2026-10-22:boracbanjaluka:kups']), 3;
create temp table _r on commit drop as
select g.id, g.g, (m.score is not null)::int * 100 + (select count(*) from match_stats s where s.match_id = g.id) + (select count(*) from lineups l where l.match_id = g.id) sc
from _g g join matches m on m.id = g.id;
create temp table _s on commit drop as
select id from (select id, row_number() over (partition by g order by sc desc, id) rn from _r) x where rn > 1;
insert into backup_2026_10_20_yanlis_birlesme(tablo, anahtar, satir) select 'matches', m.id, to_jsonb(m) from matches m join _s using (id);
do $$ declare t text; begin
  if exists (select 1 from predictions p join _s on _s.id = p.match_id) then raise exception 'kilitli tahmin bağlı'; end if;
  for t in select c.table_name from information_schema.columns c join information_schema.tables tb on tb.table_schema=c.table_schema and tb.table_name=c.table_name
           where c.table_schema='public' and c.column_name='match_id' and tb.table_type='BASE TABLE' and c.table_name not in ('matches','predictions') and c.table_name not like 'deneme_yedek%' loop
    execute format('insert into backup_2026_10_20_yanlis_birlesme(tablo, anahtar, satir) select %L, x.match_id, to_jsonb(x) from %I x join _s on _s.id = x.match_id', t, t);
    execute format('delete from %I where match_id in (select id from _s)', t);
  end loop; end $$;
delete from matches where id in (select id from _s);
select string_agg(id, ', ') from _s;
commit;
