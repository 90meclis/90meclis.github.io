begin;
create temp table _s on commit drop as select id from matches where split_part(id,':',3)=split_part(id,':',4) and home_team_id = away_team_id;
insert into backup_2026_10_20_yanlis_birlesme(tablo, anahtar, satir) select 'matches', m.id, to_jsonb(m) from matches m join _s using (id);
do $$ declare t text; begin
  if exists (select 1 from predictions p join _s on _s.id = p.match_id) then raise exception 'kilitli tahmin bağlı'; end if;
  for t in select c.table_name from information_schema.columns c join information_schema.tables tb on tb.table_schema=c.table_schema and tb.table_name=c.table_name
           where c.table_schema='public' and c.column_name='match_id' and tb.table_type='BASE TABLE' and c.table_name not in ('matches','predictions') and c.table_name not like 'deneme_yedek%' loop
    execute format('insert into backup_2026_10_20_yanlis_birlesme(tablo, anahtar, satir) select %L, x.match_id, to_jsonb(x) from %I x join _s on _s.id = x.match_id', t, t);
    execute format('delete from %I where match_id in (select id from _s)', t);
  end loop; end $$;
delete from matches where id in (select id from _s);
commit;
select count(*) from matches where home_team_id = away_team_id;
