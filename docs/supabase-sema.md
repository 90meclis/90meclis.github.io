# 90 Meclis — Supabase şeması

Bu belge `supabase/schema.sql` dosyasının ne kurduğunu, tabloların birbirine nasıl bağlandığını,
SQL'in nasıl çalıştırılacağını, gizli anahtarların nerede saklanacağını ve `SUPABASE_URL` / `SUPABASE_KEY`
değerlerinin nereden alınıp nereye konacağını anlatır.

Proje: **"90 Meclis"**, bölge **AB (İrlanda, eu-west-1)**, **Free** plan.

---

## 1. SQL'i çalıştırmak

1. Supabase paneli → projeyi açın → sol menüde **SQL Editor** → **New query**.
2. `supabase/schema.sql` dosyasının **tamamını** kopyalayıp yapıştırın → **Run** (Ctrl/Cmd + Enter).
3. "Success. No rows returned" görmelisiniz. Dosya **tekrar çalıştırılabilir** (idempotent):
   tablolar `if not exists`, yeni sütunlar `add column if not exists`, tetikleyici ve politikalar önce
   silinip yeniden kurulur. Şema güncellendiğinde aynı dosyayı yeniden çalıştırmanız yeterli.
4. Kontrol: **Table Editor**'da altı ana tablo (`matches`, `predictions`, `injuries`, `trends`, `agenda`,
   `sources`) ve yardımcı tablolar görünür; **Database → Triggers**'da `predictions_*` ve `coupons_*`
   tetikleyicileri bulunur.

> Dosya hiçbir gizli anahtar içermez. Vault örneği yalnızca yorum satırıdır ve yer tutucu kullanır.

Şema, depodaki testlerle gerçek PostgreSQL 17 üzerinde iki kez arka arkaya çalıştırılarak, tetikleyici ve
RLS davranışı sınanarak doğrulanmıştır (`tests/test_postgres_schema.py`).

---

## 2. Altı ana tablo

### 2.1 `matches` — maçlar
Birleşik veri havuzundaki her maç tek satırdır; hiçbir maç eksik veri yüzünden silinmez.

| Sütun | Anlamı |
|---|---|
| `id` (PK) | Maç kimliği, ör. `T1:2026-10-19:trabzonspor:besiktas` |
| `kickoff_at` | Maç tarihi/saati (UTC, `timestamptz`) |
| `home_name`, `away_name` | Ev sahibi / deplasman (görünen ad) |
| `home_team_id`, `away_team_id` | `teams.id` ile aynı biçim (`T1:galatasaray`) |
| `league`, `season` | Lig kodu (T1 = Süper Lig) ve sezon (`2627`) |
| `home_goals`, `away_goals`, `score` | Skor (`"2-1"`), `ht_home_goals`, `ht_away_goals` ilk yarı |
| `durum` | Görünen durum: **gelecek / canlı / bitti** (+ ertelendi / iptal) |
| `status` | İç durum: planlandi / basladi / bitti / ertelendi / iptal |
| `sources` (jsonb) | **Alan bazında veri kaynağı**: `{"_all":[…], "kickoff_at":"api-football", "venue":"thesportsdb", "odds":{…}, "stats":{…}, "_conflicts":[…]}` |
| `missing_fields` (jsonb) | Eksik alanlar listesi, ör. `["hakem","ilk 11"]` |
| `completeness` | Son analizdeki veri tamlığı puanı (0–100) |
| `venue`, `city`, `referee`, `odds`, `ext_ids` | Stadyum, şehir, hakem, piyasa oranları, kaynak kimlikleri |

### 2.2 `predictions` — değiştirilemez tahmin defteri

| Sütun | Anlamı |
|---|---|
| `id` (uuid, PK) | |
| `match_id` → `matches.id` (FK) | Hangi maç |
| `market`, `selection`, `line` | Tahmin: pazar (`1X2`, `OU_GOALS`, `CORNERS_OU`…), seçim (`1`, `ÜST`…), çizgi (2.5) |
| `odds`, `odds_source`, `fair_odds`, `edge` | Kayıt anındaki piyasa oranı ve kaynağı (yoksa boş), modelin adil oranı, değer |
| `probability`, `confidence` | Model olasılığı ve güven puanı |
| `tag` | **meclis_gorusu** (tekli) / **gunun_karari** / **karar_birligi** |
| `coupon_id` → `coupons.id` | Kupon ayağıysa |
| `scenario_note` | Botun senaryo notu ("Ev sahibi baskısı (%41); …") |
| `rationale`, `completeness`, `model_version` | Kısa gerekçe, kayıt anındaki tamlık, model sürümü |
| `status` | **bekliyor / basladi / kazandi / kaybetti / iade** |
| `result_value`, `profit`, `closing_odds`, `clv`, `settled_at`, `settlement_note` | Sonuçlandırma alanları |
| `recorded_at` | Kayıt zamanı — **sunucu saatiyle** tetikleyici yazar |

Yayımlanmamış adaylar tahmin satırı değildir: her yaklaşan maçın en güncel tam analizi `analyses`'te, yayın
durumu `analysis_queue`'da tutulur. `v_tutanak` yalnızca yayımlanan tahminleri listeler. Maç hiçbir zaman havuzdan düşmez.

**Değiştirilemezlik (tetikleyiciler):**
- `predictions_bi`: maç bulunamazsa, istemcinin yolladığı `kickoff_at` maç kaydıyla uyuşmazsa veya
  `now() >= kickoff_at` ise ekleme **reddedilir**; yeni kayıt yalnızca `bekliyor` olabilir; `recorded_at := now()`.
- `predictions_bu`: çekirdek alanlar (pazar, seçim, çizgi, oran, olasılık, etiket, gerekçe, senaryo, tamlık,
  `recorded_at`…) değişirse **reddedilir**; yalnızca durum/sonuç alanları güncellenir. Sonuçlanmış
  (kazandi/kaybetti/iade) satır bir daha değişmez.
- `predictions_bd` / `predictions_bt`: **DELETE ve TRUNCATE yasak**.
- Aynısı `coupons` tablosu için de geçerlidir. `service_role` anahtarı RLS'i aşar ama **tetikleyicileri aşamaz**.

### 2.3 `injuries` — sakat / cezalı oyuncular
`player_name`, `team_id` / `team_name`, `injury_status` (kesin yok / şüpheli / cezalı), `reason`,
`matches_played` (oynadığı maç), `key_matches` (ilk 11 başladığı maç), `goal_contribution` ((gol+asist) / takımın
gol+asisti), `defensive_contribution` (savunmacı/kaleci dakika payı), `minutes_share`, `weight_score`
(ağırlık puanı 0–1), `is_key` (kilit oyuncu mu), `match_id` → `matches.id` (boş olabilir; maç silinirse `null`),
`source`, `fetched_at`. Takım düzeyindeki **Eksik Etkisi (0–100)** bu satırlardan hesaplanır.

### 2.4 `trends` — takım × pazar serileri
`team_id`, `team_name`, `league`, `market` (korner, KG, ilk yarı gol, kart, isabetli şut, gol…),
`condition` (ör. "toplam korner > 9.5"), `streak` (art arda kaç maçtır sürüyor; + tuttu, − tutmadı),
`hits_last10`, `match_values` (jsonb) — **her maçın kendi değeri** (`[{"tarih","rakip","yer","değer"}]`),
ortalama değil. Bot her çalışmada yeniler.

### 2.5 `agenda` — Gündem Masası
`title` (haber), `link`, `source`, `published_at`, `summary`, `category` (sakatlık / teknik direktör /
transfer / kadro / genel), `match_id` → `matches.id` (**boş olabilir**, `on delete set null`), `match_ids`,
`team_ids`, `impact_note` (etki notu).

### 2.6 `sources` — veri kaynakları
`name` (PK), `api_key_secret` — anahtarın **saklandığı yerin ADI** (ör. `API_FOOTBALL_KEY`), **değeri asla**;
`key_storage` (env / GitHub Secrets / Vault), `daily_limit`, `fills_fields` (doldurduğu alanlar, jsonb),
`requires_key`, `license_note`, `is_active`. SQL dosyası yedi kaynağı tohum veri olarak ekler.

### Yardımcı tablolar
| Tablo | Görev |
|---|---|
| `teams` | Takım adı, ad varyantları, kaynak kimlikleri, stadyum, şehir, koordinat |
| `match_stats` | Maç × taraf istatistikleri (şut, isabetli şut, korner, faul, kart, kale vuruşu, xG) |
| `players` | Oyuncu dakika / maç / ilk 11 / gol / asist (sakatlık ağırlığı için) |
| `lineups`, `weather` | İlk 11 ve hava durumu önbelleği |
| `coupons` | Günün Kararı / Karar Birliği kuponları (değiştirilemez) |
| `analysis_queue` | Analiz kuyruğu: `bekliyor` = yayın penceresi / değer bekleniyor (her çalışmada yeniden hesaplanır), `tamamlandi` = yayımlandı. `ertelendi` / `yetismedi` yalnızca eski kayıtlarda kalır. |
| `analyses` | Maç analizinin tam yükü (Maç Merkezi metni, olasılıklar) |
| `source_status` | Kaynak sağlığı ve günlük istek sayacı |

### Görünümler (Güven Panosu'nun herkese açık yüzü)
- `v_tutanak` — tüm tahminler (eski kayıtlarda yayımlanmamış maçlar da görünür).
- `v_kaynak_durumu` — kaynak durumu (anon okuyabilir; mesajdaki anahtar/jetonlar maskelenir).
- `v_guven_haftalik` — hafta bazında tahmin, kazanan, kaybeden, iade, isabet %, kâr (birim), ROI %.
- `v_guven_pazar` — etiket × pazar bazında döküm.

Hepsi `security_invoker = true` ile kurulur (alttaki tabloların RLS kuralına uyar).

---

## 3. İlişkiler

```
teams.id ◄─── matches.home_team_id / away_team_id      (mantıksal bağ)
matches.id ◄── predictions.match_id                    (FK, zorunlu)
matches.id ◄── match_stats.match_id                    (FK, on delete cascade)
matches.id ◄── injuries.match_id                       (FK, boş olabilir, on delete set null)
matches.id ◄── agenda.match_id                         (FK, boş olabilir, on delete set null)
coupons.id ◄── predictions.coupon_id                   (FK, kupon ayakları)
matches.id ◄── analysis_queue / analyses / lineups / weather (match_id ile)
teams.id   ◄── trends.team_id, players.team_id, injuries.team_id
sources.name ◄─ source_status.source                   (mantıksal bağ)
```

Tahmini olan bir maç silinemez (FK), tahmin de silinemez (tetikleyici); defter bütünlüğü böyle korunur.

---

## 4. RLS (satır düzeyi güvenlik)

- Veri tablolarında ve görünümlerde **herkes okur** (`anon`, `authenticated` için `select` politikası):
  Güven Panosu ve arayüz herkese açık okunabilir.
- **Yazma politikası yoktur** → `anon` ile ekleme/güncelleme RLS tarafından reddedilir. Yazma yalnızca RLS'i
  aşan **service_role** anahtarıyla (bot) yapılır.
- `sources` ve `source_status` herkese açık **değildir** (politika yok; yalnızca service_role).

---

## 5. Gizli anahtarlar: kodda değil

Kurala göre **hiçbir anahtar koda veya depoya girmez**. Uygulama ve bot anahtarları yalnızca **ortam
değişkeninden** okur (sıra: ortam değişkeni → `.streamlit/secrets.toml` → `.env`; son ikisi `.gitignore`'dadır).

| Nerede | Ne için |
|---|---|
| **GitHub → Settings → Secrets and variables → Actions** | Zamanlanmış bot: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` + tüm veri anahtarları (`API_FOOTBALL_KEY`, `FOOTBALL_DATA_TOKEN`, `ODDS_API_KEY`, `ODDSPAPI_KEY`, `SPORTMONKS_KEY`, `FOOTYSTATS_KEY`, `SPORTDEVS_KEY`, `CLUBELO_KEY`, `THESPORTSDB_KEY`; liste: docs/kaynaklar.md) |
| **Streamlit Cloud → App → Settings → Secrets** | Herkese açık uygulama: `SUPABASE_URL`, `SUPABASE_KEY` (= **anon**). Veri anahtarları uygulamada yalnızca "tanımlı / anahtar bekleniyor" durumunu göstermek için okunur |
| **Supabase Vault** | Anahtarları veritabanında şifreli saklamak (ör. ileride Edge Function / sunucu tarafı kullanım) |
| **Supabase Edge Function secrets** | Edge Function yazılırsa: `supabase secrets set API_FOOTBALL_KEY=...` (değer yalnızca terminalde) |

### Vault kullanımı (yalnızca yer tutucu)

SQL Editor'da, yer tutucuyu kendi anahtarınızla değiştirerek **bir kez** çalıştırın; bu satırı dosyaya
kaydedip depoya koymayın:

```sql
select vault.create_secret('<API_FOOTBALL_ANAHTARINIZ>', 'API_FOOTBALL_KEY', 'API-Football anahtarı');
select vault.create_secret('<FOOTBALL_DATA_TOKENINIZ>', 'FOOTBALL_DATA_TOKEN', 'football-data.org');
select vault.create_secret('<ODDS_API_ANAHTARINIZ>',   'ODDS_API_KEY',        'The Odds API');
```

Okuma (yalnızca `postgres` / `service_role`; asla istemci tarafında):

```sql
select decrypted_secret from vault.decrypted_secrets where name = 'API_FOOTBALL_KEY';
```

Güncelleme: `select vault.update_secret('<secret_uuid>', '<YENI_ANAHTAR>');`

`sources.api_key_secret` sütunu bu adları (`API_FOOTBALL_KEY` gibi) tutar — değeri değil. Uygulama
v1'de anahtarları Vault'tan değil ortam değişkeninden okur; Vault, anahtarın tek doğru kaynağı olarak
saklanması ve ileride sunucu tarafı işler için hazırdır.

---

## 6. `SUPABASE_URL` ve `SUPABASE_KEY`

Supabase paneli → **Project Settings → API** (yeni panelde **API Keys**):

- **Project URL** → `SUPABASE_URL` (ör. `https://abcdxyz.supabase.co`). Gizli değildir.
- **anon / publishable key** (`eyJ…` JWT veya `sb_publishable_…`):
  - Tarayıcıya/istemciye açılabilir; RLS nedeniyle yalnızca **okur**.
  - **Streamlit Cloud** (herkese açık uygulama) için `SUPABASE_KEY` = anon.
  - Uygulama anon anahtarı tanır ve kendini **salt okunur** moda alır (Tahmin Botu'nda yalnızca
    kuru çalıştırma). Gerekirse `SUPABASE_READONLY=1` ile zorlanabilir.
- **service_role / secret key** (`eyJ…` JWT veya `sb_secret_…`):
  - RLS'i aşar, **tam yetkilidir**. Yalnızca **GitHub Actions secret** (`SUPABASE_SERVICE_ROLE_KEY`) ve
    kendi bilgisayarınızda bot çalıştırırken `.env` içinde.
  - Workflow bunu `SUPABASE_KEY` olarak bota verir.
  - **Asla** istemciye, Streamlit Cloud'a, ekran görüntüsüne veya depoya koymayın. Sızarsa panelden hemen
    yenileyin (rotate).

| Ortam | SUPABASE_URL | SUPABASE_KEY |
|---|---|---|
| Streamlit Cloud (herkese açık) | Project URL | **anon** |
| GitHub Actions (bot) | Project URL | **service_role** (secret adı `SUPABASE_SERVICE_ROLE_KEY`) |
| Yerel geliştirme, bot çalıştırma | Project URL | service_role (`.env`, depoya girmez) |
| Yerel geliştirme, yalnızca arayüz | Project URL | anon |
