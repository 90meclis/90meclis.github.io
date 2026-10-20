-- 90 Meclis — 2026-10-20 düzeltme: yanlış takım birleştirmesi (YALNIZCA ONAYLA ÇALIŞTIRILIR)
-- Neden: fikstürden ad öğrenme 'spor/united' gibi ortak ekleri benzerlik saydı; farklı kulüpler tek takıma bağlandı
-- (Trabzonspor→Samsunspor, Konyaspor→Alanyaspor, Ümraniyespor/Muğlaspor→Antalyaspor, İstanbulspor/Sivasspor→Vanspor,
-- Worthing→Tamworth, Scunthorpe→Southend). Bu satırlar, doğru kimlikli asıl maç kayıtlarının YANLIŞ KİMLİKLİ
-- kopyalarıdır; puan durumunu ve takım formunu bozar. Kod düzeltildi (meclis/pool.py); bu dosya kalan veriyi temizler.
-- Kilitli tahmin/kupon kayıtlarına dokunmaz (hiçbir tahmin bu maçlara bağlı değil — çalıştırmadan önce denetlenir).
begin;

update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'konyaspor' where id = 'T1:alanyaspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'trabzonspor' where id = 'T1:samsunspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'umraniyespor' where id = 'T2:antalyaspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'muglaspor' where id = 'T2:antalyaspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'istanbulspor' where id = 'T2:vanspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'sivasspor' where id = 'T2:vanspor';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'worthing' where id = 'B91:tamworth';
update teams set aliases = coalesce(aliases, '[]'::jsonb) - 'scunthorpeunited' where id = 'B91:southendunited';

create temp table _yanlis(id text primary key) on commit drop;
insert into _yanlis(id) values
  ('B91:2026-08-08:carlisleunited:tamworth'),('B91:2026-08-08:southendunited:yeoviltown'),('B91:2026-08-15:southendunited:southendunited'),('B91:2026-08-15:tamworth:forestgreenrovers'),('B91:2026-08-22:eastleigh:southendunited'),('B91:2026-08-22:tamworth:wealdstone'),('B91:2026-08-28:southendunited:solihullmoors'),('B91:2026-08-28:tamworth:tamworth'),('B91:2026-08-31:carlisleunited:southendunited'),('B91:2026-08-31:tamworth:borehamwood'),('B91:2026-09-05:fylde:tamworth'),('B91:2026-09-05:southendunited:harrogatetown'),('B91:2026-09-12:suttonunited:southendunited'),('B91:2026-09-12:tamworth:barrow'),('B91:2026-09-15:tamworth:hornchurch'),('B91:2026-09-16:southendunited:borehamwood'),('B91:2026-09-19:hartlepoolunited:tamworth'),('B91:2026-09-19:hornchurch:southendunited'),('B91:2026-09-26:southendunited:hartlepoolunited'),('B91:2026-09-26:tamworth:halifaxtown'),('B91:2026-09-29:barrow:southendunited'),('B91:2026-09-29:yeoviltown:tamworth'),('B91:2026-10-03:gateshead:tamworth'),('B91:2026-10-03:southendunited:forestgreenrovers'),('B91:2026-10-10:fylde:southendunited'),('B91:2026-10-10:tamworth:solihullmoors'),('B91:2026-10-24:kidderminsterharriers:tamworth'),('B91:2026-10-24:southendunited:woking'),('B91:2026-10-27:tamworth:southendunited'),('T1:2025-08-10:eyupspor:alanyaspor'),('T1:2025-08-11:samsunspor:kocaelispor'),('T1:2025-08-17:alanyaspor:gaziantep'),('T1:2025-08-18:kasimpasa:samsunspor'),('T1:2025-08-24:samsunspor:antalyaspor'),('T1:2025-08-29:goztepe:alanyaspor'),('T1:2025-08-31:samsunspor:samsunspor'),('T1:2025-09-13:alanyaspor:alanyaspor'),('T1:2025-09-14:fenerbahce:samsunspor'),('T1:2025-09-20:samsunspor:gaziantep'),('T1:2025-09-22:galatasaray:alanyaspor'),('T1:2025-09-27:karagumruk:samsunspor'),('T1:2025-09-28:alanyaspor:basaksehir'),('T1:2025-10-03:samsunspor:kayserispor'),('T1:2025-10-05:kasimpasa:alanyaspor'),('T1:2025-10-18:alanyaspor:kocaelispor'),('T1:2025-10-18:rizespor:samsunspor'),('T1:2025-10-22:alanyaspor:besiktas'),('T1:2025-10-25:samsunspor:eyupspor'),('T1:2025-10-26:genclerbirligi:alanyaspor'),('T1:2025-11-01:galatasaray:samsunspor'),('T1:2025-11-02:alanyaspor:samsunspor'),('T1:2025-11-08:samsunspor:alanyaspor'),('T1:2025-11-09:karagumruk:alanyaspor'),('T1:2025-11-24:alanyaspor:antalyaspor'),('T1:2025-11-24:basaksehir:samsunspor'),('T1:2025-11-29:samsunspor:alanyaspor'),('T1:2025-12-06:alanyaspor:rizespor'),('T1:2025-12-07:goztepe:samsunspor'),('T1:2025-12-14:samsunspor:besiktas'),('T1:2025-12-15:fenerbahce:alanyaspor'),('T1:2025-12-20:alanyaspor:kayserispor'),('T1:2025-12-22:genclerbirligi:samsunspor'),('T1:2026-01-18:kocaelispor:samsunspor'),('T1:2026-01-19:alanyaspor:eyupspor'),('T1:2026-01-23:samsunspor:kasimpasa'),('T1:2026-01-25:gaziantep:alanyaspor'),('T1:2026-01-30:antalyaspor:samsunspor'),('T1:2026-01-31:besiktas:alanyaspor'),('T1:2026-02-07:samsunspor:samsunspor'),('T1:2026-02-08:alanyaspor:goztepe'),('T1:2026-02-14:alanyaspor:alanyaspor'),('T1:2026-02-14:samsunspor:fenerbahce'),('T1:2026-02-21:alanyaspor:galatasaray'),('T1:2026-02-22:gaziantep:samsunspor'),('T1:2026-02-27:basaksehir:alanyaspor'),('T1:2026-02-27:samsunspor:karagumruk'),('T1:2026-03-08:alanyaspor:kasimpasa'),('T1:2026-03-09:kayserispor:samsunspor'),('T1:2026-03-14:kocaelispor:alanyaspor'),('T1:2026-03-14:samsunspor:rizespor'),('T1:2026-03-18:eyupspor:samsunspor'),('T1:2026-03-19:alanyaspor:genclerbirligi'),('T1:2026-04-04:samsunspor:galatasaray'),('T1:2026-04-05:samsunspor:alanyaspor'),('T1:2026-04-11:alanyaspor:samsunspor'),('T1:2026-04-12:alanyaspor:karagumruk'),('T1:2026-04-17:antalyaspor:alanyaspor'),('T1:2026-04-19:samsunspor:basaksehir'),('T1:2026-05-01:rizespor:alanyaspor'),('T1:2026-05-02:samsunspor:goztepe'),('T1:2026-05-09:alanyaspor:fenerbahce'),('T1:2026-05-09:besiktas:samsunspor'),('T1:2026-05-17:kayserispor:alanyaspor'),('T1:2026-05-17:samsunspor:genclerbirligi'),('T1:2026-08-15:alanyaspor:rizespor'),('T1:2026-08-15:kasimpasa:samsunspor'),('T1:2026-08-22:fenerbahce:alanyaspor'),('T1:2026-08-23:samsunspor:basaksehir'),('T1:2026-08-29:alanyaspor:kocaelispor'),('T1:2026-08-31:amedspor:samsunspor'),('T1:2026-09-05:erzurumspor:alanyaspor'),('T1:2026-09-06:samsunspor:genclerbirligi'),('T1:2026-09-12:alanyaspor:samsunspor'),('T1:2026-09-18:kasimpasa:alanyaspor'),('T1:2026-09-19:samsunspor:galatasaray'),('T1:2026-10-10:samsunspor:samsunspor'),('T1:2026-10-11:alanyaspor:basaksehir'),('T1:2026-10-17:amedspor:alanyaspor'),('T1:2026-10-19:samsunspor:besiktas'),('T1:2026-10-25:alanyaspor:genclerbirligi'),('T1:2026-10-26:rizespor:samsunspor'),('T2:2026-10-17:vanspor:sariyer'),('T2:2026-10-18:vanspor:antalyaspor'),('T2:2026-10-19:manisa:antalyaspor'),('T2:2026-10-24:antalyaspor:sivasspor'),('T2:2026-10-24:antalyaspor:vanspor'),('T2:2026-10-24:muglaspor:vanspor'),('T2:2026-11-01:bodrum:antalyaspor'),('T2:2026-11-01:vanspor:boluspor'),('T2:2026-11-01:vanspor:mardin'),('T2:2026-11-02:kayserispor:antalyaspor');

do $$
begin
  if exists (select 1 from predictions p join _yanlis y on y.id = p.match_id) then
    raise exception 'Kilitli bir tahmin bu maçlardan birine bağlı; temizlik durduruldu.';
  end if;
end $$;

do $$
declare t text;
begin
  for t in select table_name from information_schema.columns
           where table_schema = 'public' and column_name = 'match_id' and table_name not in ('predictions', 'matches')
             and table_name in (select table_name from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE')
  loop
    execute format('delete from %I where match_id in (select id from _yanlis)', t);
  end loop;
end $$;
update agenda set match_ids = (select coalesce(jsonb_agg(x), '[]'::jsonb) from jsonb_array_elements_text(match_ids) x where x not in (select id from _yanlis))
  where match_ids ?| (select array_agg(id) from _yanlis);
delete from matches where id in (select id from _yanlis);

commit;
-- Sonraki 'sezon' çalıştırması doğru kimliklerle eksik kalan alanları yeniden doldurur.
