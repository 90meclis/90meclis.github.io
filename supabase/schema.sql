-- =====================================================================
-- 90 Meclis — Supabase (PostgreSQL) şeması
-- Proje: "90 Meclis" (AB / İrlanda bölgesi, Free plan)
-- Çalıştırma: Supabase paneli > SQL Editor > New query > bu dosyanın TAMAMINI yapıştır > Run.
-- Dosya tekrar çalıştırılabilir (idempotent). Hiçbir gizli anahtar içermez.
--
-- Ana tablolar (kullanıcı tanımı):
--   1) matches      maçlar + alan bazında kaynak (provenance) + eksik alanlar
--   2) predictions  değiştirilemez tahmin defteri
--   3) injuries     sakat/cezalı oyuncular + ağırlık puanı
--   4) trends       takım × pazar serileri (maç maç değerler, ortalama değil)
--   5) agenda       Gündem Masası haberleri (+ bağlı maç, etki notu)
--   6) sources      veri kaynakları (anahtarın YERİ — değeri asla — , günlük limit, doldurduğu alanlar)
-- Yardımcı tablolar: teams, match_stats, players, lineups, weather, coupons, analysis_queue,
--   analyses, source_status.
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 6) sources — veri kaynakları
-- ---------------------------------------------------------------------
create table if not exists sources (
  name             text primary key,          -- ör. 'api-football'
  api_key_secret   text,                       -- anahtarın SAKLANDIĞI YERİN ADI (ör. env/Vault adı 'API_FOOTBALL_KEY'); değer DEĞİL
  key_storage      text,                       -- 'env + GitHub Secrets + Supabase Vault' gibi
  daily_limit      int,                        -- günlük istek limiti (null = belirsiz/limitsiz)
  fills_fields     jsonb not null default '[]'::jsonb,  -- doldurduğu alanlar
  requires_key     boolean not null default false,
  license_note     text,
  is_active        boolean not null default true,
  updated_at       timestamptz not null default now()
);

-- Tohum meclis/sources/registry.py'den üretilir (tests/test_registry.py ikisinin eşit olduğunu denetler).
-- Her kaynak zorunludur: anahtarı tanımlı değilse arayüzde "anahtar bekleniyor" görünür.
insert into sources (name, api_key_secret, key_storage, daily_limit, fills_fields, requires_key, license_note) values
  ('football-data.co.uk', null, 'anahtar gerekmez', null,
   '["sonuç","İY skoru","şut","isabetli şut","korner","faul","kart","hakem","açılış/kapanış oranları","fikstür"]', false,
   'Ücretsiz katman: Ücretsiz CSV, limit yok (makul kullanım). Ham veri yeniden yayınlanmaz, iç modelleme için; kaynak gösterilir. Sonuçlar haftada ~2 kez güncellenir. Kayıt/bilgi: https://www.football-data.co.uk/data.php'),
  ('openligadb', null, 'anahtar gerekmez', null,
   '["fikstür","sonuç (dakikalar içinde)","İY skoru","gol dakikaları"]', false,
   'Ücretsiz katman: Ücretsiz, anahtarsız REST API (makul kullanım). Topluluk tarafından girilen açık veri. Bundesliga (bl1) güvenilir; Premier Lig (pl) ve La Liga (la1) topluluk ligleri yalnızca boşluk doldurur. Kayıt/bilgi: https://www.openligadb.de'),
  ('openfootball', null, 'anahtar gerekmez', null,
   '["fikstür","sonuç","İY skoru"]', false,
   'Ücretsiz katman: GitHub ham dosyaları, CC0 (kamu malı). CC0-1.0 lisanslı açık veri; güncelleme gecikmeli olabilir, en düşük öncelik. Kayıt/bilgi: https://github.com/openfootball/football.json'),
  ('thesportsdb', 'THESPORTSDB_KEY', 'env + GitHub Actions Secrets + Supabase Vault', null,
   '["fikstür","sonuç","stadyum","şehir","kadro listesi","ilk 11 (Patreon anahtarıyla)"]', false,
   'Ücretsiz katman: Ücretsiz anahtar ''123'': ~30 istek/dk, günlük liste lig başına 3 maç. Ücretsiz ''123'' anahtarında ilk 11 boş döner (doğrulandı); Patreon anahtarı (THESPORTSDB_KEY) tüm maçları ve ilk 11''i açar. Kayıt/bilgi: https://www.thesportsdb.com/pricing'),
  ('wikidata', null, 'anahtar gerekmez', null,
   '["stadyum","stadyum kapasitesi","şehir","stadyum koordinatı","teknik direktör"]', false,
   'Ücretsiz katman: Ücretsiz, CC0; sorgu başına 60 sn, User-Agent zorunlu. CC0 veri; Wikimedia User-Agent politikasına uyulur, sonuçlar 14 gün önbelleklenir. Kayıt/bilgi: https://query.wikidata.org'),
  ('open-meteo', null, 'anahtar gerekmez', 10000,
   '["hava durumu","şehir koordinatı"]', false,
   'Ücretsiz katman: Ticari olmayan kullanım ücretsiz, 10.000 istek/gün. CC BY 4.0 veri; kaynak gösterilir. Kayıt/bilgi: https://open-meteo.com/en/pricing'),
  ('rss', null, 'anahtar gerekmez', null,
   '["haber başlığı","özet","bağlantı"]', false,
   'Ücretsiz katman: Yayıncıların herkese açık RSS akışları. Yalnızca başlık/özet/bağlantı saklanır; tam metin kopyalanmaz, bağlantı yayıncıya gider.'),
  ('wikipedia', null, 'anahtar gerekmez', null,
   '["güncel A takım kadrosu","forma no","mevki"]', false,
   'Ücretsiz katman: Ücretsiz MediaWiki API; seri istek, tanımlayıcı User-Agent, maxlag=5. İçerik CC BY-SA 4.0; kaynak gösterilir. Takım başına 7 günde bir okunur. Sakatlık bilgisi içermez. Kayıt/bilgi: https://www.mediawiki.org/wiki/API:Etiquette'),
  ('meclis-elo', null, 'anahtar gerekmez', null,
   '["takım gücü (Elo)","gol modeli önseli"]', false,
   'Ücretsiz katman: Havuzdaki gerçek sonuçlardan hesaplanır. Dış kaynak değil; football-data.co.uk/OpenLigaDB sonuçlarından türetilir.'),
  ('api-football', 'API_FOOTBALL_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 100,
   '["güncel sakat/cezalı (dün–yarın)","maç öncesi resmî ilk 11","geçmiş fikstür (2022–2024)","geçmiş sakat/cezalı","oyuncu dakika/ilk 11/gol/asist (2024)"]', true,
   'Ücretsiz katman: Ücretsiz: 100 istek/gün, 10/dk. Ücretsiz plan (19.10.2026''da doğrulandı): sezonluk sorgu yalnızca 2022–2024, tarih sorgusu dün–yarın, fikstür kimliğiyle sorgu güncel sezonda açık, page en fazla 3. Kalan bütçe `python -m meclis gecmis` ile geçmiş veri doldurmaya gider, kaldığı yerden sürer. Kayıt/bilgi: https://dashboard.api-football.com/register'),
  ('football-data.org', 'FOOTBALL_DATA_TOKEN', 'env + GitHub Actions Secrets + Supabase Vault', 14400,
   '["fikstür","sonuç","İY skoru","hakem","stadyum"]', true,
   'Ücretsiz katman: Ücretsiz: 12 turnuva, 10 istek/dk (Süper Lig yok). Kayıt/bilgi: https://www.football-data.org/client/register'),
  ('the-odds-api', 'ODDS_API_KEY', 'env + GitHub Actions Secrets + Supabase Vault', null,
   '["1X2 oranı","Alt/Üst oranı","Pinnacle oranı"]', true,
   'Ücretsiz katman: Ücretsiz: ayda 500 kredi (h2h+totals × eu = 2 kredi/lig). Türk bahis şirketi yok. Kayıt/bilgi: https://the-odds-api.com/#get-access'),
  ('oddspapi', 'ODDSPAPI_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 8,
   '["1X2 oranı (Pinnacle dahil 300+ bahis şirketi)"]', true,
   'Ücretsiz katman: Ücretsiz: ayda 250 istek (bot günde en çok 1 oran çağrısı yapar). Kayıt/bilgi: https://oddspapi.io/en/register'),
  ('sportmonks', 'SPORTMONKS_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 4320,
   '["fikstür","sonuç","İY skoru","stadyum","hakem","maç istatistiği"]', true,
   'Ücretsiz katman: Ücretsiz plan: yalnızca Danimarka Superliga + İskoçya Premiership (180 istek/saat/varlık); bizim liglerimiz ücretli planda. Kayıt/bilgi: https://my.sportmonks.com/register'),
  ('footystats', 'FOOTYSTATS_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 4320,
   '["sonuç","İY skoru","korner","kart","isabetli şut","faul","stadyum","1X2 ve 2.5 Alt/Üst oranı"]', true,
   'Ücretsiz katman: Ücretsiz: yalnızca Premier Lig, 180 istek/saat; Süper Lig ücretli (Hobby £29.99/ay). Kayıt/bilgi: https://footystats.org/api'),
  ('sportdevs', 'SPORTDEVS_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 300,
   '["fikstür","sonuç","İY skoru","stadyum","ilk 11 (matches-lineups)","eksik oyuncular (kadro içinde)"]', true,
   'Ücretsiz katman: Ücretsiz: 300 istek/gün, 10 büyük lig. Kayıt/bilgi: https://sportdevs.com/football'),
  ('bsd', 'BSD_API_KEY', 'env + GitHub Actions Secrets + Supabase Vault', null,
   '["sakat/cezalı/şüpheli (maç başına, 7 gün önceden)","resmî ilk 11 (~1 saat önce)","tahmini ilk 11 (AI)","kadro + oyuncu uygunluğu","fikstür","sonuç","İY skoru","konsensüs oranları (1X2, A/Ü 1.5/2.5/3.5, KG)","maç istatistiği (şut, isabetli şut, korner, faul, kart, kale vuruşu, xG, topla oynama)","hakem","stadyum"]', true,
   'Ücretsiz katman: Ücretsiz futbol planı: tüm v2 uç noktaları, günlük 7.500 istek (IP başına 10 istek/sn); 6 ligin hepsi kapsamda. Lisans v4.0: iç kullanım için saklama ve kendi uygulamanda gösterim serbest; ham verinin yeniden satışı yasak. Kayıt/bilgi: https://sports.bzzoiro.com/register/'),
  ('highlightly', 'HIGHLIGHTLY_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 100,
   '["resmî ilk 11","maç istatistiği","sakat/cezalı","oyuncu sezon istatistiği"]', true,
   'Ücretsiz katman: 100 istek/gün, kart yok. Koşullar saklama ve kendi üründe gösterime izin veriyor; ham API yeniden satılmaz. Anahtar tanımlanınca etkinleşir. Kayıt/bilgi: https://highlightly.net/'),
  ('bigballs', 'BIGBALLS_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 250,
   '["resmî ilk 11","takım maç istatistiği","oyuncu sezon istatistiği"]', true,
   'Ücretsiz katman: 250 istek/gün (GitHub ile 500). Yalnızca 5 büyük lig + Şampiyonlar Ligi. Anahtar tanımlanınca etkinleşir. Kayıt/bilgi: https://bigballsdata.com/'),
  ('nosyapi', 'NOSYAPI_KEY', 'env + GitHub Actions Secrets + Supabase Vault', null,
   '["sonuç","İY skoru","korner","kart"]', true,
   'Ücretsiz katman: 500 kredi (kredi = dönen satır). YALNIZCA sonuç/istatistik uç noktaları; iddaa oranı kullanılmaz (kullanıcı kararı: oranlar yalnızca yabancı kaynaklardan). Anahtar tanımlanınca etkinleşir. Kayıt/bilgi: https://www.nosyapi.com/'),
  ('soccerdata', 'SOCCERDATA_KEY', 'env + GitHub Actions Secrets + Supabase Vault', 75,
   '["tahmini ilk 11","sakat/cezalı"]', true,
   'Ücretsiz katman: 75 istek/gün; ücretsiz planda yalnızca UEL + E1. Anahtar tanımlanınca etkinleşir. Kayıt/bilgi: https://soccerdataapi.com/'),
  ('playerelo', 'PLAYERELO_KEY', 'env + GitHub Actions Secrets + Supabase Vault', null,
   '["oyuncu Elo (Eksik Etkisi için iç model girdisi)"]', true,
   'Ücretsiz katman: 500 istek/ay, 10/dk. Ücretsiz katman değerlendirme/hobi amaçlı: yalnızca iç model girdisi, yayımlanmaz. Anahtar tanımlanınca etkinleşir. Kayıt/bilgi: https://playerelo.football/api-access')
on conflict (name) do update set
  api_key_secret = excluded.api_key_secret, key_storage = excluded.key_storage, daily_limit = excluded.daily_limit,
  fills_fields = excluded.fills_fields, requires_key = excluded.requires_key, license_note = excluded.license_note,
  updated_at = now();

-- ---------------------------------------------------------------------
-- Takımlar (yardımcı)
-- ---------------------------------------------------------------------
create table if not exists teams (
  id            text primary key,            -- ör. "T1:galatasaray"
  league        text not null,
  name          text not null,
  aliases       jsonb not null default '[]'::jsonb,
  ext_ids       jsonb not null default '{}'::jsonb,
  stadium       text,
  city          text,
  lat           double precision,
  lon           double precision,
  coach         text,                        -- teknik direktör (Wikidata P286)
  capacity      int,                         -- stadyum kapasitesi (Wikidata P1083)
  updated_at    timestamptz not null default now()
);
-- Eski kurulumlar için (idempotent)
alter table teams add column if not exists coach text;
alter table teams add column if not exists capacity int;

-- ---------------------------------------------------------------------
-- 1) matches — birleşik veri havuzundaki maçlar
-- ---------------------------------------------------------------------
create table if not exists matches (
  id             text primary key,           -- maç kimliği, ör. "T1:2026-10-19:trabzonspor:besiktas"
  league         text not null,
  season         text,
  kickoff_at     timestamptz not null,       -- maç tarihi/saati (UTC)
  home_team_id   text not null,
  away_team_id   text not null,
  home_name      text not null,              -- ev sahibi
  away_name      text not null,              -- deplasman
  home_goals     int,
  away_goals     int,
  score          text,                       -- "2-1" (bitti/canlı ise)
  ht_home_goals  int,
  ht_away_goals  int,
  status         text not null default 'planlandi'
                 check (status in ('planlandi','basladi','bitti','ertelendi','iptal')),   -- iç durum
  durum          text not null default 'gelecek'
                 check (durum in ('gelecek','canlı','bitti','ertelendi','iptal')),        -- görünen durum
  venue          text,
  referee        text,
  city           text,                       -- stadyumun şehri (hava durumu için)
  ext_ids        jsonb not null default '{}'::jsonb,   -- kaynak kimlikleri
  odds           jsonb not null default '{}'::jsonb,   -- piyasa oranları (kaynağıyla)
  sources        jsonb not null default '{}'::jsonb,   -- veri kaynakları: {"_all":[...], "<alan>":"<kaynak>", "odds":{...}, "stats":{...}}
  missing_fields jsonb not null default '[]'::jsonb,   -- eksik alanlar listesi
  completeness   numeric,                              -- son analizdeki tamlık puanı (0–100)
  updated_at     timestamptz not null default now()
);
alter table matches add column if not exists score text;
alter table matches add column if not exists durum text not null default 'gelecek';
alter table matches add column if not exists missing_fields jsonb not null default '[]'::jsonb;
alter table matches add column if not exists completeness numeric;
alter table matches add column if not exists city text;
create index if not exists matches_kickoff_idx on matches (kickoff_at);
create index if not exists matches_league_idx on matches (league, kickoff_at);

create table if not exists match_stats (
  match_id        text not null references matches(id) on delete cascade,
  side            text not null check (side in ('home','away')),
  team_id         text not null,
  shots           int,
  shots_on_target int,
  corners         int,
  fouls           int,
  yellow          int,
  red             int,
  goal_kicks      int,
  xg              double precision,
  possession      double precision,
  source          text,
  updated_at      timestamptz not null default now(),
  primary key (match_id, side)
);

create table if not exists players (
  team_id     text not null,
  player_key  text not null,
  name        text not null,
  position    text,
  minutes     int,
  appearances int,
  lineups     int,
  goals       int,
  assists     int,
  season      text,
  source      text,
  updated_at  timestamptz not null default now(),
  shirt_number int,                          -- forma numarası (Wikipedia/BSD kadrosu)
  stats_source text,                         -- istatistiğin geldiği kaynak+sezon, ör. "api-football 2024"
  primary key (team_id, player_key)
);
-- Eski kurulumlar için (idempotent)
alter table players add column if not exists shirt_number int;
alter table players add column if not exists stats_source text;

-- ---------------------------------------------------------------------
-- 3) injuries — sakat / cezalı / şüpheli oyuncular
-- ---------------------------------------------------------------------
create table if not exists injuries (
  id                     text primary key,
  match_id               text references matches(id) on delete set null,
  team_id                text not null,
  team_name              text,
  player_name            text not null,        -- oyuncu
  injury_status          text,                 -- sakatlık durumu: kesin yok / şüpheli / cezalı
  reason                 text,
  matches_played         int,                  -- sezon başından beri oynadığı maç
  key_matches            int,                  -- ilk 11 başladığı (kilit oyuncu olarak oynadığı) maç
  goal_contribution      numeric,              -- gol katkısı: (gol+asist) / takımın gol+asisti
  defensive_contribution numeric,              -- savunma katkısı (vekil: savunmacı/kalecide dakika payı)
  minutes_share          numeric,
  weight_score           numeric,              -- ağırlık puanı (0–1)
  is_key                 boolean,              -- kilit oyuncu mu
  source                 text,
  fetched_at             timestamptz not null default now()
);
create index if not exists injuries_match_idx on injuries (match_id);

-- ---------------------------------------------------------------------
-- 4) trends — takım × pazar serileri (maç maç)
-- ---------------------------------------------------------------------
create table if not exists trends (
  id             text primary key,            -- "<team_id>:<market>"
  team_id        text not null,
  team_name      text not null,
  league         text not null,
  market         text not null,               -- korner / KG / ilk yarı gol / şut / isabetli şut / kart / gol
  condition      text,                        -- seri koşulu, ör. "toplam korner > 9.5"
  streak         int not null default 0,      -- koşulun art arda kaç maçtır sürdüğü (+ tuttu, − tutmadı)
  hits_last10    int,                         -- son 10 maçta koşulun tuttuğu maç sayısı
  match_values   jsonb not null default '[]'::jsonb,  -- [{"tarih","rakip","yer","değer"}] — her maçın kendi değeri
  updated_at     timestamptz not null default now()
);
create index if not exists trends_team_idx on trends (team_id);
create index if not exists trends_market_idx on trends (league, market);

create table if not exists lineups (
  match_id   text not null,
  side       text not null check (side in ('home','away')),
  formation  text,
  start_xi   jsonb not null default '[]'::jsonb,
  subs       jsonb not null default '[]'::jsonb,
  coach      text,
  source     text,
  updated_at timestamptz not null default now(),
  lineup_status text,                        -- 'resmi' (açıklanan ilk 11) | 'tahmini' (BSD AI tahmini)
  primary key (match_id, side)
);
alter table lineups add column if not exists lineup_status text;

create table if not exists weather (
  match_id   text primary key,
  data       jsonb not null,
  source     text,
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 5) agenda — Gündem Masası
-- ---------------------------------------------------------------------
create table if not exists agenda (
  id           text primary key,               -- bağlantının özeti (hash)
  title        text not null,                  -- haber
  link         text not null,
  source       text,
  published_at timestamptz,
  summary      text,
  category     text,                           -- transfer / sakatlık / teknik direktör / kadro / genel
  match_id     text references matches(id) on delete set null,   -- bağlı maç (boş olabilir)
  match_ids    jsonb not null default '[]'::jsonb,               -- birden fazla maça bağlanırsa
  team_ids     jsonb not null default '[]'::jsonb,
  impact_note  text,                           -- etki notu
  fetched_at   timestamptz not null default now(),
  sources_all  jsonb not null default '[]'::jsonb,  -- aynı haberi veren bütün kaynaklar (başlık benzerliğiyle birleşir)
  cluster_size int not null default 1,
  leagues      jsonb not null default '[]'::jsonb   -- lig etiketleri
);
create index if not exists agenda_published_idx on agenda (published_at desc);

-- Analiz kuyruğu: her maç analiz edilir. 'bekliyor' = yayın penceresi/değer bekleniyor, 'tamamlandi' = yayımlandı.
-- 'ertelendi' / 'yetismedi' yalnızca eski kayıtlar için izinli kalır (yeni kod yazmaz).
create table if not exists analysis_queue (
  match_id        text primary key,
  status          text not null default 'bekliyor'
                  check (status in ('bekliyor','ertelendi','tamamlandi','yetismedi')),
  missing         jsonb not null default '[]'::jsonb,
  attempts        int not null default 0,
  last_attempt_at timestamptz,
  next_retry_at   timestamptz,
  note            text
);

create table if not exists analyses (
  match_id      text not null,
  created_at    timestamptz not null default now(),
  model_version text,
  payload       jsonb not null,
  primary key (match_id, created_at)
);

-- Kaynaklardan keşfedilen ligler (meclis/leagues.py). Çekirdek ligler koddadır (config.LEAGUES).
create table if not exists leagues (
  code       text primary key,          -- ör. "B96" (BSD lig kimliği 96)
  name       text not null,
  country    text,
  bsd_id     int,
  cup        boolean not null default false,
  source     text,
  updated_at timestamptz not null default now()
);

-- Bu sezonun oyuncu-maç kayıtları (BSD ilk 11 + oyuncu istatistiği): oyuncu önemi, yedek açığı, var/yok farkı
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

-- Kendi oran anlık görüntülerimiz: başlamaya yakın her çalışmada matches.odds kopyalanır → kapanış oranı ve CLV
create table if not exists odds_snapshots (
  match_id   text not null references matches(id),
  taken_at   timestamptz not null default now(),
  kickoff_at timestamptz not null,
  odds       jsonb not null,             -- {"1X2": {"1":..,"X":..,"2":..,"src":..}, "OU_GOALS_2.5": {...}, "BTTS": {...}}
  primary key (match_id, taken_at)
);
create index if not exists odds_snapshots_match_idx on odds_snapshots (match_id, taken_at desc);

-- Kaynak çekme işleri: hata → üstel geri çekilme; 3 hatadan sonra alan bir sonraki kaynağa devredilir
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

-- TAHMİN BOTU: botun ham çıktısı — bültendeki her maçın en değerli seçimi (maç başına bir satır, id = match_id).
-- Her çalışmada yeniden hesaplanır; maç arşive (Günün Kararı / Meclis Görüşü) alındığında locked_at yazılır ve
-- satır bir daha değişmez (tetikleyici güncellemeyi yok sayar).
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
create or replace function meclis_bot_pick_lock() returns trigger language plpgsql as $f$
begin
  if old.locked_at is not null then
    return old;  -- arşive alınmış seçim kilitli: güncelleme sessizce yok sayılır
  end if;
  return new;
end $f$;
drop trigger if exists bot_picks_lock on bot_picks;
create trigger bot_picks_lock before update on bot_picks for each row execute function meclis_bot_pick_lock();

create table if not exists source_status (
  source       text primary key,
  ok           boolean,
  message      text,
  calls_today  int not null default 0,
  calls_date   date,
  updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Kuponlar (Günün Kararı / Karar Birliği) — değiştirilemez
-- ---------------------------------------------------------------------
create table if not exists coupons (
  id                uuid primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),
  coupon_date       date not null,
  tag               text not null check (tag in ('gunun_karari','karar_birligi')),
  total_odds        numeric not null,
  joint_probability numeric,
  legs_count        int not null,
  stake             numeric not null default 1,
  first_kickoff_at  timestamptz not null,
  odds_source       text,            -- 'piyasa' veya 'model_adil' (adil oranla kâr/zarar hesaplanmaz)
  model_version     text,
  note              text,
  status            text not null default 'bekliyor'
                    check (status in ('bekliyor','basladi','kazandi','kaybetti','iade')),
  profit            numeric,
  settled_at        timestamptz,
  settlement_note   text
);
create unique index if not exists coupons_one_per_day on coupons (coupon_date, tag);

-- ---------------------------------------------------------------------
-- 2) predictions — değiştirilemez tahmin defteri
-- ---------------------------------------------------------------------
create table if not exists predictions (
  id             uuid primary key default gen_random_uuid(),
  recorded_at    timestamptz not null default now(),  -- kayıt zamanı (sunucu saati, tetikleyici yazar)
  match_id       text not null references matches(id),
  kickoff_at     timestamptz not null,
  league         text,
  home_name      text,
  away_name      text,
  tag            text not null check (tag in ('meclis_gorusu','gunun_karari','karar_birligi')),
  coupon_id      uuid references coupons(id),
  market         text not null,       -- tahmin: pazar
  selection      text not null,       -- tahmin: seçim
  line           numeric,
  probability    numeric not null check (probability >= 0 and probability <= 1),
  odds           numeric,             -- tahmin anındaki piyasa oranı (yoksa null)
  odds_source    text,
  fair_odds      numeric,             -- modelin adil oranı (1/olasılık)
  edge           numeric,
  confidence     numeric,             -- güven puanı
  stake          numeric not null default 1,
  rationale      text,                -- gerekçe (kısa)
  scenario_note  text,                -- botun senaryo notu
  completeness   numeric,             -- kayıt anındaki veri tamlığı (0–100)
  model_version  text,
  status         text not null default 'bekliyor'
                 check (status in ('bekliyor','basladi','kazandi','kaybetti','iade')),
  result_value   text,
  profit         numeric,
  closing_odds   numeric,             -- kapanış oranı (CLV için; sonuçlandırmada yazılır)
  clv            numeric,             -- alınan oran / kapanış oranı − 1
  settled_at     timestamptz,
  settlement_note text
);
create index if not exists predictions_kickoff_idx on predictions (kickoff_at);
-- arşiv satırının dayandığı bot seçimi (Tahmin Botu → Tahmin Arşivi bağı)
alter table predictions add column if not exists bot_pick_id text references bot_picks(id);
create unique index if not exists predictions_single_unique
  on predictions (match_id, market, selection, coalesce(line, -1)) where tag = 'meclis_gorusu';
create unique index if not exists predictions_leg_unique
  on predictions (coupon_id, match_id) where coupon_id is not null;

-- ---------------------------------------------------------------------
-- Değiştirilemezlik garantisi (tetikleyiciler)
--  * Maç başladıktan sonra tahmin/kupon EKLENEMEZ.
--  * recorded_at / created_at sunucu saatiyle yazılır (istemci değiştiremez).
--  * Çekirdek alanlar GÜNCELLENEMEZ; yalnızca durum/sonuç alanları güncellenir.
--  * Sonuçlanmış (kazandi/kaybetti/iade) kayıt bir daha değiştirilemez.
--  * Kayıt SİLİNEMEZ, tablo TRUNCATE edilemez.
-- service_role anahtarı RLS'i aşar ama tetikleyicileri AŞAMAZ.
-- ---------------------------------------------------------------------
create or replace function meclis_prediction_before_insert() returns trigger
language plpgsql as $$
declare
  real_kickoff timestamptz;
begin
  new.recorded_at := now();
  select kickoff_at into real_kickoff from matches where id = new.match_id;
  if real_kickoff is null then
    raise exception 'Maç bulunamadı: %', new.match_id;
  end if;
  if new.kickoff_at <> real_kickoff then
    raise exception 'kickoff_at maç kaydıyla uyuşmuyor (%, %)', new.kickoff_at, real_kickoff;
  end if;
  if now() >= real_kickoff then
    raise exception 'Maç başladı: tahmin kaydı kapandı (%).', new.match_id;
  end if;
  if new.status <> 'bekliyor' then
    raise exception 'Yeni tahmin yalnızca "bekliyor" durumuyla eklenebilir.';
  end if;
  new.fair_odds := coalesce(new.fair_odds, round(1 / nullif(new.probability, 0), 3));
  return new;
end $$;

create or replace function meclis_prediction_before_update() returns trigger
language plpgsql as $$
begin
  if old.status in ('kazandi','kaybetti','iade') then
    raise exception 'Sonuçlanmış tahmin değiştirilemez (%).', old.id;
  end if;
  if (new.id, new.recorded_at, new.match_id, new.kickoff_at, new.league, new.home_name, new.away_name,
      new.tag, new.coupon_id, new.market, new.selection, new.line, new.probability, new.odds,
      new.odds_source, new.fair_odds, new.edge, new.confidence, new.stake, new.rationale,
      new.scenario_note, new.completeness, new.model_version)
     is distinct from
     (old.id, old.recorded_at, old.match_id, old.kickoff_at, old.league, old.home_name, old.away_name,
      old.tag, old.coupon_id, old.market, old.selection, old.line, old.probability, old.odds,
      old.odds_source, old.fair_odds, old.edge, old.confidence, old.stake, old.rationale,
      old.scenario_note, old.completeness, old.model_version) then
    raise exception 'Tahminin çekirdek alanları değiştirilemez; yalnızca durum/sonuç güncellenebilir.';
  end if;
  return new;
end $$;

create or replace function meclis_coupon_before_insert() returns trigger
language plpgsql as $$
begin
  new.created_at := now();
  if now() >= new.first_kickoff_at then
    raise exception 'Kuponun ilk maçı başladı: kupon kaydı kapandı.';
  end if;
  if new.status <> 'bekliyor' then
    raise exception 'Yeni kupon yalnızca "bekliyor" durumuyla eklenebilir.';
  end if;
  return new;
end $$;

create or replace function meclis_coupon_before_update() returns trigger
language plpgsql as $$
begin
  if old.status in ('kazandi','kaybetti','iade') then
    raise exception 'Sonuçlanmış kupon değiştirilemez (%).', old.id;
  end if;
  if (new.id, new.created_at, new.coupon_date, new.tag, new.total_odds, new.joint_probability,
      new.legs_count, new.stake, new.first_kickoff_at, new.odds_source, new.model_version, new.note)
     is distinct from
     (old.id, old.created_at, old.coupon_date, old.tag, old.total_odds, old.joint_probability,
      old.legs_count, old.stake, old.first_kickoff_at, old.odds_source, old.model_version, old.note) then
    raise exception 'Kuponun çekirdek alanları değiştirilemez; yalnızca durum/sonuç güncellenebilir.';
  end if;
  return new;
end $$;

create or replace function meclis_block_delete() returns trigger
language plpgsql as $$
begin
  raise exception 'Tahmin defteri kayıtları silinemez (%).', tg_table_name;
end $$;

drop trigger if exists predictions_bi on predictions;
create trigger predictions_bi before insert on predictions
  for each row execute function meclis_prediction_before_insert();
drop trigger if exists predictions_bu on predictions;
create trigger predictions_bu before update on predictions
  for each row execute function meclis_prediction_before_update();
drop trigger if exists predictions_bd on predictions;
create trigger predictions_bd before delete on predictions
  for each row execute function meclis_block_delete();
drop trigger if exists predictions_bt on predictions;
create trigger predictions_bt before truncate on predictions
  for each statement execute function meclis_block_delete();

drop trigger if exists coupons_bi on coupons;
create trigger coupons_bi before insert on coupons
  for each row execute function meclis_coupon_before_insert();
drop trigger if exists coupons_bu on coupons;
create trigger coupons_bu before update on coupons
  for each row execute function meclis_coupon_before_update();
drop trigger if exists coupons_bd on coupons;
create trigger coupons_bd before delete on coupons
  for each row execute function meclis_block_delete();
drop trigger if exists coupons_bt on coupons;
create trigger coupons_bt before truncate on coupons
  for each statement execute function meclis_block_delete();

-- ---------------------------------------------------------------------
-- Güven Panosu görünümleri (herkese açık yüz). security_invoker: alttaki tabloların RLS'ine uyar.
-- ---------------------------------------------------------------------
create or replace view v_tutanak with (security_invoker = true) as
  select p.id, p.recorded_at, p.kickoff_at, p.league, p.home_name, p.away_name, p.tag, p.market, p.selection,
         p.line, p.probability, p.odds, p.fair_odds, p.status, p.result_value, p.profit, p.clv, p.coupon_id
  from predictions p;

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
  from predictions group by 1 order by 1 desc;

create or replace view v_guven_pazar with (security_invoker = true) as
  select tag, market, count(*) as tahmin,
         count(*) filter (where status = 'kazandi') as kazanan,
         count(*) filter (where status = 'kaybetti') as kaybeden,
         round(100.0 * count(*) filter (where status = 'kazandi')
               / nullif(count(*) filter (where status in ('kazandi','kaybetti')), 0), 1) as isabet_yuzde,
         round(coalesce(sum(profit) filter (where odds is not null), 0), 2) as kar_birim
  from predictions group by 1, 2 order by 1, 2;

-- ---------------------------------------------------------------------
-- RLS: anon/authenticated yalnızca OKUR (Güven Panosu herkese açık). Yazma yalnızca service_role ile
-- (service_role RLS'i aşar; politikasız tablolarda anon yazamaz). 'sources' ve 'source_status'
-- herkese açık değildir.
-- ---------------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['teams','matches','match_stats','players','injuries','trends','lineups','weather',
                           'agenda','analysis_queue','analyses','coupons','predictions','leagues','odds_snapshots',
                           'player_matches','bot_picks']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "herkes_okur" on %I', t);
    execute format('create policy "herkes_okur" on %I for select to anon, authenticated using (true)', t);
  end loop;
  foreach t in array array['sources','source_status','fetch_jobs']
  loop
    execute format('alter table %I enable row level security', t);
    -- politika yok: yalnızca service_role erişir
  end loop;
end $$;

grant select on v_tutanak, v_guven_haftalik, v_guven_pazar to anon, authenticated;

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

-- Kaynak durumu (herkese açık, temizlenmiş): arayüz anon anahtarıyla source_status tablosunu okuyamaz.
-- Bu görünüm yalnızca kaynak adı / başarı / zaman / temizlenmiş mesajı verir (URL'deki anahtar/jeton maskelenir).
create or replace view v_kaynak_durumu as
  select source, ok,
         left(regexp_replace(regexp_replace(coalesce(message, ''),
              '(key|token|apikey|api_key|access_token|apiToken)=[^&[:space:]]+', '\1=***', 'gi'),
              '/json/[^/]+/', '/json/***/', 'g'), 300) as message,
         calls_today, calls_date, updated_at
  from source_status;
grant select on v_kaynak_durumu to anon, authenticated;

-- ---------------------------------------------------------------------
-- Supabase Vault — anahtarları veritabanında şifreli saklamak için ÖRNEK.
-- Gerçek anahtarı buraya YAZIP bu dosyayı depoya koymayın; aşağıdakini yalnızca SQL Editor'da,
-- yer tutucuyu kendi anahtarınızla değiştirerek bir kez çalıştırın:
--
--   select vault.create_secret('<API_FOOTBALL_ANAHTARINIZ>', 'API_FOOTBALL_KEY', 'API-Football anahtarı');
--   select vault.create_secret('<FOOTBALL_DATA_TOKENINIZ>', 'FOOTBALL_DATA_TOKEN', 'football-data.org');
--   select vault.create_secret('<ODDS_API_ANAHTARINIZ>',   'ODDS_API_KEY',        'The Odds API');
--
-- Okuma (yalnızca service_role / postgres; Edge Function veya sunucu tarafı için):
--   select decrypted_secret from vault.decrypted_secrets where name = 'API_FOOTBALL_KEY';
--
-- Streamlit uygulaması ve GitHub Actions anahtarları ORTAM DEĞİŞKENİNDEN okur
-- (Streamlit Cloud > Secrets, GitHub > Settings > Secrets and variables > Actions).
-- ---------------------------------------------------------------------
