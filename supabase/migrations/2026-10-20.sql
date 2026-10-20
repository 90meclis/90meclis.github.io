-- 90 Meclis — 2026-10-20 artımlı geçiş (tekrar çalıştırılabilir; kilitli tahmin/kupona dokunmaz)

alter table teams add column if not exists coach text;

alter table teams add column if not exists capacity int;

alter table players add column if not exists shirt_number int;

alter table players add column if not exists stats_source text;

alter table lineups add column if not exists lineup_status text;

alter table agenda add column if not exists sources_all jsonb default '[]'::jsonb;

alter table agenda add column if not exists cluster_size int default 1;

alter table agenda add column if not exists leagues jsonb default '[]'::jsonb;

create table if not exists leagues (
  code       text primary key,          -- ör. "B96" (BSD lig kimliği 96)
  name       text not null,
  country    text,
  bsd_id     int,
  cup        boolean not null default false,
  source     text,
  updated_at timestamptz not null default now()
);


create table if not exists player_matches (
  match_id   text not null references matches(id),
  team_id    text not null,
  player_id  text not null,             -- "bsd:<id>"
  name       text not null,
  position   text,
  started    boolean not null default false,
  minutes    int not null default 0,
  goals      int not null default 0,
  assists    int not null default 0,
  rating     numeric,
  kickoff_at timestamptz,
  source     text,
  primary key (match_id, player_id)
);


create index if not exists player_matches_team_idx on player_matches (team_id, kickoff_at desc);

create table if not exists odds_snapshots (
  match_id   text not null references matches(id),
  taken_at   timestamptz not null default now(),
  kickoff_at timestamptz not null,
  odds       jsonb not null,             -- {"1X2": {"1":..,"X":..,"2":..,"src":..}, "OU_GOALS_2.5": {...}, "BTTS": {...}}
  primary key (match_id, taken_at)
);


create index if not exists odds_snapshots_match_idx on odds_snapshots (match_id, taken_at desc);

create table if not exists fetch_jobs (
  id           text primary key,         -- "<kaynak>:<iş>"
  source       text not null,
  attempts     int not null default 0,
  status       text not null default 'tekrar' check (status in ('tekrar','devredildi','tamam')),
  next_try_at  timestamptz,
  last_error   text,
  fallback     text,                     -- devredilen kaynak(lar)
  updated_at   timestamptz not null default now()
);


create table if not exists bot_picks (
  id            text primary key,
  match_id      text not null references matches(id),
  kickoff_at    timestamptz not null,
  league        text,
  home_name     text,
  away_name     text,
  market        text not null,
  selection     text not null,
  line          numeric,
  probability   numeric not null,        -- kalibre olasılık
  odds          numeric,                 -- piyasa oranı (yoksa null → "adil oran" seçimi, arşive girmez)
  fair_odds     numeric,
  edge          numeric,
  confidence    numeric,                 -- değer × veri kalitesi (sıralama ölçütü)
  kind          text,                    -- 'değer' | 'adil oran (piyasa oranı yok)'
  basis         text,
  completeness  numeric,
  model_version text,
  status        text not null default 'aday' check (status in ('aday','gunun_karari','meclis_gorusu')),
  computed_at   timestamptz not null default now(),
  locked_at     timestamptz
);


create index if not exists bot_picks_kickoff_idx on bot_picks (kickoff_at);

alter table predictions add column if not exists bot_pick_id text references bot_picks(id);

create or replace function meclis_bot_pick_lock() returns trigger language plpgsql as $f$
begin
  if old.locked_at is not null then
    return old;  -- arşive alınmış seçim kilitli: güncelleme sessizce yok sayılır
  end if;
  return new;
end $f$;
drop trigger if exists bot_picks_lock on bot_picks;
create trigger bot_picks_lock before update on bot_picks for each row execute function meclis_bot_pick_lock();

do $$
declare t text;
begin
  foreach t in array array['leagues','odds_snapshots','player_matches','bot_picks']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "herkes_okur" on %I', t);
    execute format('create policy "herkes_okur" on %I for select to anon, authenticated using (true)', t);
  end loop;
  alter table fetch_jobs enable row level security;  -- politika yok: yalnızca service_role
end $$;

-- görünümler yeniden kurulur (sütun listesi değişen eski görünümler için önce düşürülür; veri tablolarına dokunulmaz)
drop view if exists v_oran_hareketi, v_dinlenme, v_puan_durumu, v_hakem_sezon, v_takim_mac_istatistik, v_bot_tarama, v_arsiv, v_bot_bulten, v_guven_pazar, v_guven_haftalik, v_tutanak, v_kayit, v_kayit_tekli, v_kaynak_durumu cascade;

-- Kural: aynı gün Günün Kararı ayağı olan maç o gün Meclis Görüşü olarak SAYILMAZ (19.10.2026 Getafe/Parma
-- çakışması kilitli satırlarda kalır ama hiçbir herkese açık görünümde ayrı kayıt olarak görünmez/sayılmaz).
-- Kupon ayakları ayrı kayıt değildir: güven/kâr görünümlerinde her kupon TEK kayıttır.
create or replace view v_kayit_tekli with (security_invoker = true) as
  select p.* from predictions p
  where p.tag = 'meclis_gorusu'
    and not exists (select 1 from predictions g
                    where g.tag = 'gunun_karari' and g.match_id = p.match_id
                      and (g.kickoff_at at time zone 'Europe/Istanbul')::date
                          = (p.kickoff_at at time zone 'Europe/Istanbul')::date);

create or replace view v_kayit with (security_invoker = true) as
  select t.id::text as id, 'meclis_gorusu'::text as tag, t.market, t.kickoff_at, t.status, t.odds,
         t.probability, t.profit, t.clv, 1 as ayak
  from v_kayit_tekli t
  union all
  select c.id::text, c.tag, 'KUPON'::text, c.first_kickoff_at, c.status, c.total_odds, c.joint_probability,
         c.profit, null::numeric, c.legs_count
  from coupons c;

create or replace view v_tutanak with (security_invoker = true) as
  select p.id, p.recorded_at, p.kickoff_at, p.league, p.home_name, p.away_name, p.tag, p.market, p.selection,
         p.line, p.probability, p.odds, p.fair_odds, p.status, p.result_value, p.profit, p.clv, p.coupon_id
  from predictions p
  where p.tag <> 'meclis_gorusu' or p.id in (select id from v_kayit_tekli);

create or replace view v_guven_haftalik with (security_invoker = true) as
  select to_char(kickoff_at at time zone 'Europe/Istanbul', 'IYYY-"H"IW') as hafta,
         count(*) as tahmin,
         count(*) filter (where status = 'kazandi') as kazanan,
         count(*) filter (where status = 'kaybetti') as kaybeden,
         count(*) filter (where status = 'iade') as iade,
         round(100.0 * count(*) filter (where status = 'kazandi')
               / nullif(count(*) filter (where status in ('kazandi','kaybetti')), 0), 1) as isabet_yuzde,
         round(coalesce(sum(profit) filter (where odds is not null), 0), 2) as kar_birim,
         round(100.0 * sum(profit) filter (where odds is not null and status in ('kazandi','kaybetti'))
               / nullif(count(*) filter (where odds is not null and status in ('kazandi','kaybetti')), 0), 1) as roi_yuzde
  from v_kayit group by 1 order by 1 desc;

create or replace view v_guven_pazar with (security_invoker = true) as
  select tag, market, count(*) as tahmin,
         count(*) filter (where status = 'kazandi') as kazanan,
         count(*) filter (where status = 'kaybetti') as kaybeden,
         round(100.0 * count(*) filter (where status = 'kazandi')
               / nullif(count(*) filter (where status in ('kazandi','kaybetti')), 0), 1) as isabet_yuzde,
         round(coalesce(sum(profit) filter (where odds is not null), 0), 2) as kar_birim
  from v_kayit group by 1, 2 order by 1, 2;

grant select on v_tutanak, v_guven_haftalik, v_guven_pazar, v_kayit, v_kayit_tekli to anon, authenticated;

-- Tahmin Botu sayfası: botun ham bülteni (yayımlanmış olsun olmasın her seçim)
create or replace view v_bot_bulten with (security_invoker = true) as
  select b.id, b.match_id, b.kickoff_at, b.league, b.home_name, b.away_name, b.market, b.selection, b.line,
         b.probability, b.odds, b.fair_odds, b.edge, b.confidence, b.kind, b.basis, b.completeness,
         b.status as arsiv_durumu, b.computed_at, b.locked_at
  from bot_picks b
  where b.kickoff_at > now() - interval '3 hours';
-- Tahmin Arşivi sayfası: yayımlanan içerik (Günün Kararı bacakları, Meclis Görüşü tekliler, Karar Birliği) ve bot seçimine bağ
create or replace view v_arsiv with (security_invoker = true) as
  select p.id, p.recorded_at, p.kickoff_at, p.league, p.home_name, p.away_name, p.tag, p.coupon_id, p.market,
         p.selection, p.line, p.probability, p.odds, p.fair_odds, p.edge, p.confidence, p.rationale, p.scenario_note,
         p.status, p.result_value, p.profit, p.closing_odds, p.clv, p.bot_pick_id, b.computed_at as bot_computed_at,
         b.kind as bot_kind, c.total_odds as kupon_oran, c.status as kupon_durum
  from predictions p
  left join bot_picks b on b.id = p.bot_pick_id
  left join coupons c on c.id = p.coupon_id
  where p.tag <> 'meclis_gorusu' or p.id in (select id from v_kayit_tekli);
-- Tahmin Botu taraması: günün bütün maçlarının BÜTÜN pazarları (model olasılığı, kalibre olasılık, piyasa oranı,
-- değer, seçildi/geçildi nedeni) — en güncel analizden
create or replace view v_bot_tarama with (security_invoker = true) as
  select a.match_id, a.created_at, (a.payload->>'kickoff_at')::timestamptz as kickoff_at, a.payload->>'league' as league,
         a.payload->>'home' as home_name, a.payload->>'away' as away_name, a.payload->>'basis' as basis,
         x->>'market' as market, x->>'selection' as selection, (x->>'line')::numeric as line,
         (x->>'probability')::numeric as p_model, (x->>'p_kal')::numeric as p_kal,
         (x->>'p_piyasa')::numeric as p_piyasa, (x->>'odds')::numeric as odds, x->>'odds_source' as odds_source,
         (x->>'fair_odds')::numeric as fair_odds, coalesce((x->>'edge_kal')::numeric, (x->>'edge')::numeric) as edge,
         coalesce((x->>'deger')::boolean, false) as deger, coalesce((x->>'secildi')::boolean, false) as secildi,
         x->>'neden' as neden
  from analyses a
  cross join lateral jsonb_array_elements(a.payload->'markets') x
  where (a.payload->>'kickoff_at')::timestamptz > now() - interval '3 hours';
grant select on v_bot_bulten, v_arsiv, v_bot_tarama to anon, authenticated;

-- ---------------------------------------------------------------------
-- Maç sayfası veri görünümleri (yalnızca BU SEZON; 1 Temmuz'dan itibaren). Takım kimliği 'lig:slug'tır;
-- Avrupa kupası ile lig maçlarını birleştirmek için team_slug kullanılır. competition: 'Avrupa' | 'Lig'.
-- ---------------------------------------------------------------------
create or replace view v_takim_mac_istatistik with (security_invoker = true) as
  with m as (
    select m.*, case when m.league in ('CL','EL','ECL') then 'Avrupa' else 'Lig' end as competition,
           case when extract(month from now()) >= 7 then make_date(extract(year from now())::int, 7, 1)
                else make_date(extract(year from now())::int - 1, 7, 1) end as s0
    from matches m where m.status = 'bitti' and m.home_goals is not null
  )
  select m.id as match_id, m.kickoff_at, m.league, m.competition, t.side,
         case when t.side = 'home' then 'İç saha' else 'Deplasman' end as venue,
         case when t.side = 'home' then m.home_team_id else m.away_team_id end as team_id,
         split_part(case when t.side = 'home' then m.home_team_id else m.away_team_id end, ':', 2) as team_slug,
         case when t.side = 'home' then m.home_name else m.away_name end as team_name,
         case when t.side = 'home' then m.away_name else m.home_name end as opponent,
         case when t.side = 'home' then m.home_goals else m.away_goals end as goals_for,
         case when t.side = 'home' then m.away_goals else m.home_goals end as goals_against,
         case when t.side = 'home' then m.ht_home_goals else m.ht_away_goals end as ht_for,
         case when t.side = 'home' then m.ht_away_goals else m.ht_home_goals end as ht_against,
         (m.home_goals > 0 and m.away_goals > 0) as btts,
         me.corners as corners_for, op.corners as corners_against,
         (me.yellow + coalesce(me.red, 0)) as cards_for, (op.yellow + coalesce(op.red, 0)) as cards_against,
         me.shots as shots_for, op.shots as shots_against,
         me.shots_on_target as sot_for, op.shots_on_target as sot_against,
         me.goal_kicks as goal_kicks_for, op.goal_kicks as goal_kicks_against,
         me.fouls as fouls_for, op.fouls as fouls_against, me.xg as xg_for, op.xg as xg_against,
         me.possession as possession, m.referee
  from m
  cross join (values ('home'), ('away')) t(side)
  left join match_stats me on me.match_id = m.id and me.side = t.side
  left join match_stats op on op.match_id = m.id and op.side = case when t.side = 'home' then 'away' else 'home' end
  where m.kickoff_at >= m.s0;

-- Hakem: bu sezon maç başına kart / faul (penaltı verisi kaynaklarda yok → gösterilmez)
create or replace view v_hakem_sezon with (security_invoker = true) as
  select referee, count(distinct match_id) as mac,
         round(avg(coalesce(cards_for, 0) + coalesce(cards_against, 0)) filter (where cards_for is not null), 2) as kart_mac,
         round(avg(coalesce(fouls_for, 0) + coalesce(fouls_against, 0)) filter (where fouls_for is not null), 2) as faul_mac,
         round(avg(goals_for + goals_against), 2) as gol_mac
  from v_takim_mac_istatistik where side = 'home' and referee is not null and referee <> ''
  group by referee;

-- Puan durumu (bu sezon, lig maçlarından hesaplanır)
create or replace view v_puan_durumu with (security_invoker = true) as
  select league, team_id, max(team_name) as team_name, count(*) as o,
         count(*) filter (where goals_for > goals_against) as g, count(*) filter (where goals_for = goals_against) as b,
         count(*) filter (where goals_for < goals_against) as m, sum(goals_for) as ag, sum(goals_against) as yg,
         sum(goals_for) - sum(goals_against) as av,
         3 * count(*) filter (where goals_for > goals_against) + count(*) filter (where goals_for = goals_against) as puan,
         rank() over (partition by league order by
           3 * count(*) filter (where goals_for > goals_against) + count(*) filter (where goals_for = goals_against) desc,
           sum(goals_for) - sum(goals_against) desc, sum(goals_for) desc) as sira
  from v_takim_mac_istatistik group by league, team_id;

-- Dinlenme / yoğunluk: yaklaşan maçta her takımın son maçından bu yana gün ve son 14 gündeki maç sayısı (tüm turnuvalar)
create or replace view v_dinlenme with (security_invoker = true) as
  select u.id as match_id, u.kickoff_at, s.side,
         case when s.side = 'home' then u.home_name else u.away_name end as team_name,
         round(extract(epoch from (u.kickoff_at - (select max(x.kickoff_at) from v_takim_mac_istatistik x
               where x.team_slug = split_part(case when s.side = 'home' then u.home_team_id else u.away_team_id end, ':', 2)
                 and x.kickoff_at < u.kickoff_at))) / 86400.0, 1) as dinlenme_gun,
         (select count(*) from v_takim_mac_istatistik x
           where x.team_slug = split_part(case when s.side = 'home' then u.home_team_id else u.away_team_id end, ':', 2)
             and x.kickoff_at between u.kickoff_at - interval '14 days' and u.kickoff_at) as son14_mac
  from matches u cross join (values ('home'), ('away')) s(side)
  where u.kickoff_at > now() - interval '3 hours' and u.kickoff_at < now() + interval '8 days';

-- Oran hareketi: açılış (ilk görüntü) ve güncel (son görüntü) oranlar
create or replace view v_oran_hareketi with (security_invoker = true) as
  select distinct on (o.match_id) o.match_id, o.kickoff_at,
         first_value(o.odds) over w as acilis, first_value(o.taken_at) over w as acilis_zamani,
         last_value(o.odds) over w as guncel, last_value(o.taken_at) over w as guncel_zamani,
         count(*) over (partition by o.match_id) as goruntu
  from odds_snapshots o
  window w as (partition by o.match_id order by o.taken_at rows between unbounded preceding and unbounded following);

grant select on v_takim_mac_istatistik, v_hakem_sezon, v_puan_durumu, v_dinlenme, v_oran_hareketi to anon, authenticated;

create or replace view v_kaynak_durumu as
  select source, ok,
         left(regexp_replace(regexp_replace(coalesce(message, ''),
              '(key|token|apikey|api_key|access_token|apiToken)=[^&[:space:]]+', '\1=***', 'gi'),
              '/json/[^/]+/', '/json/***/', 'g'), 300) as message,
         calls_today, calls_date, updated_at
  from source_status;
grant select on v_kaynak_durumu to anon, authenticated;

update analysis_queue set status = 'bekliyor' where status in ('ertelendi','yetismedi');

notify pgrst, 'reload schema';
