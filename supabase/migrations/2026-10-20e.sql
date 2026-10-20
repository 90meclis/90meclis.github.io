-- 2026-10-20e: Kanıt Mührü, sezon simülasyonu, seriler, paylaşım taslakları. Tekrar çalıştırılabilir.
create table if not exists kanit_muhru (
  ref_table text not null check (ref_table in ('predictions','coupons')), ref_id text not null,
  seq bigint not null, icerik_sha256 text not null, sha256 text not null, onceki_sha256 text not null,
  kanonik text not null, muhurlendi_at timestamptz not null default now(),
  primary key (ref_table, ref_id));
create unique index if not exists kanit_muhru_seq on kanit_muhru (seq);
create or replace function meclis_muhur_degismez() returns trigger language plpgsql as $$
begin raise exception 'Kanıt Mührü değiştirilemez/silinemez'; end $$;
drop trigger if exists kanit_muhru_bu on kanit_muhru;
create trigger kanit_muhru_bu before update or delete on kanit_muhru for each row execute function meclis_muhur_degismez();

create table if not exists sezon_simulasyonu (
  league text not null, team_id text not null, team_name text, kosu int, sampiyon numeric, ilk4 numeric, kume numeric,
  ort_puan numeric, ort_sira numeric, mevcut_puan int, kalan_mac int, sira_dagilimi jsonb, computed_at timestamptz,
  yontem text, primary key (league, team_id));

create table if not exists paylasim_taslaklari (
  id text primary key, platform text not null check (platform in ('telegram','x')), tur text, ref_id text,
  metin text not null, durum text not null default 'taslak' check (durum in ('taslak','onaylandi','paylasildi','iptal')),
  olusturuldu timestamptz not null default now());

do $$ declare t text; begin
  foreach t in array array['kanit_muhru','sezon_simulasyonu'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists herkes_okur on %I', t);
    execute format('create policy herkes_okur on %I for select using (true)', t);
    execute format('grant select on %I to anon, authenticated', t);
  end loop;
end $$;
-- taslaklar herkese açık DEĞİL (yalnızca servis anahtarı)
alter table paylasim_taslaklari enable row level security;

create or replace view v_kanit_muhru with (security_invoker = true) as
  select seq, ref_table, ref_id, icerik_sha256, sha256, onceki_sha256, kanonik, muhurlendi_at from kanit_muhru;
create or replace view v_sezon_simulasyonu with (security_invoker = true) as
  select s.*, rank() over (partition by league order by ort_sira) as tahmini_sira from sezon_simulasyonu s;

-- Seriler: takımın (tüm turnuvalar, team_slug) en son maçtan geriye kesintisiz seri uzunlukları
create or replace view v_seriler with (security_invoker = true) as
  with t as (
    select team_slug, team_name, kickoff_at, competition,
           goals_for > goals_against as g, goals_for >= goals_against as yenilmez, goals_for < goals_against as m,
           (goals_for > 0 and goals_against > 0) as kg, (goals_for + goals_against) > 2.5 as ust25,
           goals_against = 0 as gol_yemedi, goals_for = 0 as gol_atamadi,
           row_number() over (partition by team_slug order by kickoff_at desc) as rn
    from v_takim_mac_istatistik)
  select team_slug, (array_agg(team_name order by kickoff_at desc))[1] as team_name, count(*) as mac,
         coalesce(min(rn) filter (where not g), max(rn) + 1) - 1 as galibiyet,
         coalesce(min(rn) filter (where not yenilmez), max(rn) + 1) - 1 as yenilmezlik,
         coalesce(min(rn) filter (where not m), max(rn) + 1) - 1 as maglubiyet,
         coalesce(min(rn) filter (where not kg), max(rn) + 1) - 1 as kg_var,
         coalesce(min(rn) filter (where kg), max(rn) + 1) - 1 as kg_yok,
         coalesce(min(rn) filter (where not ust25), max(rn) + 1) - 1 as ust_25,
         coalesce(min(rn) filter (where ust25), max(rn) + 1) - 1 as alt_25,
         coalesce(min(rn) filter (where not gol_yemedi), max(rn) + 1) - 1 as gol_yemedi,
         coalesce(min(rn) filter (where not gol_atamadi), max(rn) + 1) - 1 as gol_atamadi,
         string_agg(case when g then 'G' when m then 'M' else 'B' end, '' order by kickoff_at desc) filter (where rn <= 10) as son10
  from t group by team_slug;
grant select on v_kanit_muhru, v_sezon_simulasyonu, v_seriler to anon, authenticated;
