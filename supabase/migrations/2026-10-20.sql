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

create or replace view v_tutanak with (security_invoker = true) as
  select p.id, p.recorded_at, p.kickoff_at, p.league, p.home_name, p.away_name, p.tag, p.market, p.selection,
         p.line, p.probability, p.odds, p.fair_odds, p.status, p.result_value, p.profit, p.clv, p.coupon_id
  from predictions p;

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
  left join coupons c on c.id = p.coupon_id;
grant select on v_bot_bulten, v_arsiv to anon, authenticated;

grant select on v_tutanak, v_guven_haftalik, v_guven_pazar to anon, authenticated;

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
