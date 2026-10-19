# ⚽ 90 Meclis

Maç maç analiz yapan, tahminlerini **maç başlamadan önce kilitli bir deftere yazan** ve sonra kendi
karnesini dürüstçe (kayıplar dahil) gösteren bir futbol tahmin uygulaması. Arayüz tamamen Türkçedir,
tek bir çok sayfalı Streamlit uygulamasıdır; veri Supabase'te (PostgreSQL) tutulur.

> ⚠️ Bu uygulama bahis tavsiyesi değildir. Model olasılıkları hata payı taşır; geçmiş isabet gelecek
> için garanti vermez. 18 yaş altı için uygun değildir.

## Bölümler

| Menü | Ne yapar |
|---|---|
| **Maç Merkezi** | Seçilen maçın **Meclis tahmini ilk 11'i** (modelde kullanılan; resmî liste beklenmez), dış kaynak tahmini / resmî ilk 11 (gelirse yalnızca bilgi), sakat/cezalılar ve **Eksik Etkisi (0–100)**, son form, istatistik ortalamaları, H2H, Open-Meteo hava durumu, model λ'ları, pazar olasılıkları ve "🎙️ Maç konuşuyor" senaryo metni. Veri yoksa "yok" der; uydurmaz. |
| **Tahmin Botu** | Önümüzdeki 7 günün bütün maçlarını tarar ve her maçın **tam analizini** (tüm pazarlar, Meclis tahmini ilk 11, senaryolar) seçimden bağımsız olarak kaydeder; tüm pazarları (skor, 1X2, çifte şans, gol Alt/Üst, KG, takım golü, İY gol, korner, kart, isabetli şut, kale vuruşu) hesaplar. Eksik veri analizi durdurmaz (tamlık yalnızca güven göstergesi); yalnızca **değer kuralını** geçen seçim **maçtan en az 3 saat önce** yayımlanır (sabah çalışması günün bütün maçlarına karar verir). Yayımlanmamış adaylar her çalışmada (gece dahil) güncel veriyle yeniden hesaplanır; yayımlanan seçim kilitlidir. |
| **Tahmin Arşivi** | Etiketli kayıtlar: **Günün Kararı** (2–3 maç, toplam oran 2.30–4.00), **Meclis Görüşü** (tekli), **Karar Birliği** (günde ≥5 tekli varsa en güvenilen 2–3). Durumlar: bekliyor / başladı / kazandı / kaybetti / iade — otomatik sonuçlanır. |
| **Veri Laboratuvarı** | Pazar ligleri (korner, ilk yarı gol, KG, kart, isabetli şut…) ve takımların **maç maç** serileri (ortalama değil, her maçın kendi değeri). |
| **Gündem Masası** | Sabah RSS taraması (sakatlık / teknik direktör / transfer / kadro), haberler takım adıyla maçlara bağlanır ve etki notu eklenir. |
| **Güven Panosu** | Haftalık karne, isabet oranı, 1 birim sabit bahisle ROI (yalnızca gerçek piyasa oranlı kayıtlar), pazar bazında döküm, kasa eğrisi, kalibrasyon, CLV. Kayıplar dahil her şey görünür. |

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # değerleri doldurun (.env depoya girmez)
streamlit run app.py
```

Hiç anahtar olmadan da çalışır: Supabase yoksa veriler yerel `data/meclis.db` (SQLite) dosyasında tutulur ve
uygulama bunu her sayfada açıkça söyler. Yerel SQLite da aynı değiştirilemezlik tetikleyicilerini taşır.

### Örnek veri modu (demo)

```bash
DEMO_MODE=1 streamlit run app.py
```

Tamamen **uydurma** takımlar ("Örnek Kartal" vb.) ve oranlarla arayüzü dener. Her sayfada kırmızı
**ÖRNEK VERİ** bandı görünür; gerçek veriyle asla karışmaz (ayrı bellek içi veritabanı).

### Supabase

1. supabase.com'da proje açın (ör. "90 Meclis", AB/İrlanda, Free plan).
2. **SQL Editor → New query** → `supabase/schema.sql` dosyasının tamamını yapıştırıp **Run**. Dosya tekrar
   çalıştırılabilir.
3. **Project Settings → API**: `Project URL` → `SUPABASE_URL`; anahtarlar:
   - **anon / publishable** → herkese açık Streamlit uygulaması (salt okunur; RLS yazmayı engeller).
   - **service_role / secret** → yalnızca bot (GitHub Actions secret). İstemciye, Streamlit Cloud'a, depoya **asla**.

Ayrıntılar, tablo tablo şema ve Vault kullanımı: **[docs/supabase-sema.md](docs/supabase-sema.md)**.

### Ortam değişkenleri

Okuma sırası: ortam değişkeni → `.streamlit/secrets.toml` (Streamlit Cloud Secrets) → `.env` → varsayılan.

| Değişken | Zorunlu mu | Açıklama |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_KEY` | Önerilir | Kalıcı kayıt. Yoksa yerel SQLite. |
| Veri kaynağı anahtarları | Evet (her biri) | Aşağıdaki tablo. Tanımlı değilse kaynak atlanır ve arayüzde **🔑 anahtar bekleniyor** yazar. |
| `LEAGUES` | Hayır | Boşsa 21 lig: `T1,E0,SP1,I1,D1,F1,CL,EL,ECL,T2,E1,N1,P1,B1,SC0,G1,E2,SP2,I2,D2,F2` (T1 = Süper Lig, T2 = TFF 1. Lig, CL/EL/ECL = UEFA kupaları). |
| `BOT_PUBLISH_LEAD_HOURS` | Hayır | Seçim en geç başlamadan kaç saat önce yayımlanır (varsayılan 3). |
| `BOT_PUBLISH_WINDOW_HOURS` | Hayır | TR günü dışındaki maçlar için yayın penceresi (varsayılan 12 saat). |
| `DEMO_MODE` | Hayır | `1` = örnek veri modu. |

**Veri kaynağı anahtarları** (hepsi ücretsiz kayıtla alınır; değerleri yalnızca env / GitHub Secrets / Streamlit
Secrets / Supabase Vault'a yazın):

| Ortam değişkeni / Secret | Kaynak | Nereden alınır | Ücretsiz limit |
|---|---|---|---|
| `THESPORTSDB_KEY` | TheSportsDB | https://www.thesportsdb.com/pricing | Ücretsiz anahtar '123': ~30 istek/dk, günlük liste lig başına 3 maç |
| `API_FOOTBALL_KEY` | API-Football (api-sports.io) | https://dashboard.api-football.com/register | Ücretsiz: 100 istek/gün, 10/dk |
| `FOOTBALL_DATA_TOKEN` | football-data.org | https://www.football-data.org/client/register | Ücretsiz: 12 turnuva, 10 istek/dk (Süper Lig yok) |
| `ODDS_API_KEY` | The Odds API | https://the-odds-api.com/#get-access | Ücretsiz: ayda 500 kredi (h2h+totals × eu = 2 kredi/lig) |
| `ODDSPAPI_KEY` | OddsPapi | https://oddspapi.io/en/register | Ücretsiz: ayda 250 istek (bot günde en çok 1 oran çağrısı yapar) |
| `SPORTMONKS_KEY` | Sportmonks Football API v3 | https://my.sportmonks.com/register | Ücretsiz plan: yalnızca Danimarka Superliga + İskoçya Premiership (180 istek/saat/varlık); bizim liglerimiz ücretli planda |
| `FOOTYSTATS_KEY` | FootyStats API | https://footystats.org/api | Ücretsiz: yalnızca Premier Lig, 180 istek/saat; Süper Lig ücretli (Hobby £29.99/ay) |
| `SPORTDEVS_KEY` | SportDevs Football API | https://sportdevs.com/football | Ücretsiz: 300 istek/gün, 10 büyük lig |
| `CLUBELO_KEY` | Club Elo | http://clubelo.com/API | Eskiden anahtarsızdı; Eylül 2026'dan beri API kimlik doğrulama istiyor, kayıt henüz kapalı |
| `BSD_API_KEY` | Bzzoiro Sports Data (BSD) | https://sports.bzzoiro.com/register/ | Ücretsiz futbol planı, kota yok: maç başına sakat/cezalı, resmî + tahmini ilk 11, kadro uygunluğu (6 lig) |

Diğer ayarlar için `.env.example` dosyasına bakın. **Gerçek anahtar hiçbir dosyada depoya girmez.**

## Bot (komut satırı)

```bash
python -m meclis yenile [--gecmis]     # veri havuzunu güncelle (--gecmis: önceki sezonu da çek)
python -m meclis gundem                # RSS gündem taraması
python -m meclis bot [--kuru]          # analiz + kayıt (--kuru: hiçbir şey yazmadan dene)
python -m meclis sonuclandir           # biten maçları otomatik sonuçlandır
python -m meclis kadro [--zorla]       # güncel kadrolar (Wikipedia+BSD) + yaklaşan maçların eksikleri ve ilk 11'i
python -m meclis gecmis                # API-Football ücretsiz plan 2022–2024 geçmiş veri (günlük bütçe, kaldığı yerden)
python -m meclis sabah                 # yenile + gündem + kadro + bot + sonuçlandır
python -m meclis durum                 # kaynak durumu / kuyruk özeti
python -m meclis bot --ligler T1,E0    # lig seçimi
```

Aynı işlemler arayüzde **Tahmin Botu** sayfasından da yapılabilir (anon anahtarla bağlıyken yalnızca kuru çalıştırma).

### Zamanlanmış çalışma (GitHub Actions)

`.github/workflows/meclis.yml`:
- 08:00 TSİ `sabah`, gün içinde her 2 saatte bir `yenile + kadro + bot + sonuclandir`, gece `sonuclandir`,
  03:40 TSİ `gecmis` (API-Football kotası sıfırlandıktan sonra);
  ayrıca **Actions → Run workflow** ile elle.
- Repo → Settings → Secrets and variables → Actions → **Secrets**: `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY` ve yukarıdaki tablodaki tüm veri anahtarları (`API_FOOTBALL_KEY`,
  `FOOTBALL_DATA_TOKEN`, `ODDS_API_KEY`, `ODDSPAPI_KEY`, `SPORTMONKS_KEY`, `FOOTYSTATS_KEY`, `SPORTDEVS_KEY`,
  `CLUBELO_KEY`, `THESPORTSDB_KEY`, `BSD_API_KEY`). Tanımlanmayan secret boş geçer; bot o kaynağı "anahtar bekleniyor" diye raporlar.
  **Variables**: `LEAGUES` (boşsa 21 ligin tamamı — bkz. `meclis/config.py` `DEFAULT_LEAGUES`).

## Model özeti

- **Temel: güncel sezon (2026/27).** Geçmiş sezon maçları yalnızca zayıf önsel/kalibrasyon olarak 0.3 ağırlıkla girer.
  Takımın bu sezonki maçı 3'ten azsa piyasa oranı (varsa) gol beklentisine yarı ağırlıkla katılır; lig geçmişi
  hiç yoksa (ör. UEFA kupaları) gol beklentisi piyasa oranından türetilir (bu durumda "değer" iddiası kurulmaz).
- **Gol / skor:** zaman ağırlıklı (ξ = 0.0019/gün) **Dixon-Coles** Poisson modeli; 10×10 skor matrisinden 1X2,
  çifte şans, Alt/Üst 1.5/2.5/3.5, KG, takım golleri, doğru skor; ilk yarı oranı ligden ölçülür.
- **Sayım pazarları:** korner, kart, isabetli şut, kale vuruşu için takım hücum/savunma oranları (büzülmeli);
  lig varyansı ortalamayı aşıyorsa **negatif binom**, değilse Poisson.
- **Meclis tahmini ilk 11 + sakatlık:** her takım için kendi ilk 11 tahminimiz (son resmî ilk 11'ler 0.45, sezon ilk 11
  payı 0.35, dış tahmin 0.20; sakat/cezalı dışarıda, şüpheli ×0.5). Eksik Etkisi'ne sakat/cezalı/şüpheli listesi +
  en güçlü 11'de olup tahmini 11'de olmayanlar (rotasyon, kesinlik 0.5) girer; oyuncu önemi = dakika, ilk 11,
  gol+asist katkısı, savunma payı; "Eksik Etkisi" (TEE, 0–100) ve λ çarpanı (0.70–1.30 ile sınırlı).
- **Veri tamlığı (0–100, yalnızca güven göstergesi):** fikstür 15, bu sezonki maçlar (≥6) 25, piyasa oranı 15,
  sakatlık 15, istatistik geçmişi 15, hakem 5, Meclis tahmini ilk 11 10. Tahmini durdurmaz; seçim puanını 0.85–1.0
  arasında çarpar.
- **Seçim (yayın kuralı):** iki takımın da modelde en az 4 maçı olmalı; piyasa oranı varsa değer (edge) ≥ %3; yoksa yüksek olasılıklı, "adil oran" etiketli seçim
  (bunlar ROI'ye katılmaz). Günün Kararı yalnızca gerçek oranlı ayaklardan, beklenen değeri ≥ 0 olan en
  yüksek ortak olasılıklı kombinasyondur; bant tutmazsa **kupon yok** denir.

## Veri kaynakları ve sınırları

Ayrıntılı liste, kullanım koşulu notları ve Elo geriye dönük testi: **[docs/kaynaklar.md](docs/kaynaklar.md)**.

**Anahtarsız (şu an çalışıyor):** football-data.co.uk (Süper Lig dahil sonuç/istatistik/hakem/oran CSV),
OpenLigaDB (Bundesliga dakikalar içinde; Premier Lig ve La Liga boşluk doldurur), openfootball (CC0, boşluk doldurur),
TheSportsDB (ücretsiz anahtar `123`), Wikidata SPARQL (stadyum, kapasite, şehir, koordinat, teknik direktör),
Open-Meteo (hava), 18 Türkçe ve uluslararası RSS akışı, Meclis Elo (iç hesap, gol modeli önseli).

**Anahtar bekleyenler:** API-Football, football-data.org, The Odds API, OddsPapi, Sportmonks, FootyStats,
SportDevs, Club Elo. Anahtar eklenince bir sonraki `yenile` ile devreye girerler.

**Bilinçli olarak KULLANILMAYANLAR:** FotMob, SofaScore, Flashscore, WhoScored, Transfermarkt, Forebet,
Understat, FBref, Nesine iç uç noktaları, ESPN'in belgelenmemiş API'si. Bunlarda kazıma (scraping) yapılmaz.
Tüm istekler `90Meclis/1.0` kimliğiyle, önbellekli ve sınırlı hızda yapılır.

**Birleştirme:** aynı maç = aynı lig + iki takım eşleşti + başlama saati ±36 saat. Genel alanlarda öncelik
API-Football → Sportmonks → football-data.org → FootyStats → SportDevs → OpenLigaDB → The Odds API → OddsPapi →
TheSportsDB → football-data.co.uk → openfootball. Oranlarda öncelik The Odds API → OddsPapi →
football-data.co.uk → FootyStats → API-Football → Sportmonks. Boş alan sıradaki kaynaktan doldurulur. Her alanın
kaynağı `matches.sources` içinde, eksikler `missing_fields` içinde saklanır, skor çelişkileri
`sources._conflicts` altına yazılır. Hiçbir maç düşürülmez.

## Değiştirilemez defter

Veritabanı tetikleyicileri (Supabase'te ve yerel SQLite'ta):
- Maç başladıktan sonra tahmin/kupon **eklenemez** (başlama saati maç kaydından doğrulanır).
- `recorded_at` sunucu saatiyle yazılır; istemci değiştiremez.
- Çekirdek alanlar (pazar, seçim, oran, olasılık, gerekçe…) **güncellenemez**; yalnızca durum/sonuç alanları.
- Sonuçlanmış kayıt bir daha değişmez; kayıt **silinemez**, tablo boşaltılamaz.

## Testler

```bash
pytest -q
# Şemayı gerçek PostgreSQL'de sınamak için (boş bir test veritabanı verin)
MECLIS_TEST_PG_DSN="host=localhost dbname=meclis_test user=postgres" pytest tests/test_postgres_schema.py
```

Kapsam: Dixon-Coles ve sayım modelleri, kaynak birleştirme (Türkçe ad eşleme, provenance, maç düşürmeme),
kupon bandı, sonuçlandırma (iade dahil), değiştirilemezlik tetikleyicileri, TEE, yayın penceresi (≥3 saat önce),
tahmini ilk 11, piyasa oranından gol beklentisi, altı sayfanın açılışı (Streamlit AppTest) ve başsız sunucu sağlık kontrolü.

## Bilinen sınırlar

- Kale vuruşu verisi azdır (BSD biten maç istatistiğinden gelir) → bu pazar çoğu maçta hesaplanmaz.
- Anahtarsız modda sakatlık ve ilk 11 yok; tamlık puanı buna göre düşer, metinlerde açıkça yazılır.
- Piyasa oranı yoksa Günün Kararı genellikle kurulmaz (bilinçli).
- Takım adı eşleştirme muhafazakârdır; yeni bir ad varyantı ayrı takım sanılabilir (`meclis/names.py` → `ALIASES`).
- Haber–maç eşleşmesi takım adına dayanır; yanlış pozitif/negatif olabilir.
- Kaynakların kullanım koşulları değişebilir; ticari kullanımdan önce hukuki kontrol önerilir.

## Streamlit Community Cloud'a yayınlama

1. https://share.streamlit.io → **Create app** → depo `ebrarmutlu3434-afk/90-meclis`, dal `main`, **Main file path: `app.py`**.
2. **Advanced settings → Secrets** alanına yalnızca şu ikisini yazın (bkz. `.streamlit/secrets.toml.example`):
   `SUPABASE_URL` ve `SUPABASE_KEY` (anon / publishable anahtar — service_role değil).
3. Uygulama yerel dosyaya ihtiyaç duymaz; veriyi Supabase'den okur. Veri toplama, kadro/eksik/ilk 11 güncellemesi
   ve tahmin defteri GitHub Actions'taki zamanlanmış iş (`.github/workflows/meclis.yml`) tarafından yapılır.
