# 90 Meclis — veri kaynakları

Bu dosya `meclis/sources/registry.py` ile aynı listeyi anlatır; `sources` tablosu tohumu
(`supabase/schema.sql`) ve arayüzdeki **Tahmin Botu → Veri kaynakları** tablosu da oradan üretilir.

**Kural:** listedeki her kaynak zorunludur. Anahtarı tanımlı olmayan kaynak çalıştırmada atlanır, ama
arayüzde ve bot günlüğünde **🔑 anahtar bekleniyor** olarak açıkça görünür ve o kaynağın alanları boş kalır
(uydurma veri konmaz). Anahtar değerleri yalnızca ortam değişkeni / GitHub Actions Secrets / Streamlit Secrets /
Supabase Vault içinde durur; kodda, depoda veya tabloda yalnızca değişkenin **adı** tutulur.

## Anahtarsız çalışanlar (şu an etkin)

| Kaynak | Anahtar (ortam değişkeni) | Ücretsiz katman | Doldurduğu alanlar | Kayıt / bilgi |
|---|---|---|---|---|
| **football-data.co.uk** | — | Ücretsiz CSV, limit yok (makul kullanım) | sonuç, İY skoru, şut, isabetli şut, korner, faul, kart, hakem, açılış/kapanış oranları, fikstür | https://www.football-data.co.uk/data.php |
| **OpenLigaDB** | — | Ücretsiz, anahtarsız REST API (makul kullanım) | fikstür, sonuç (dakikalar içinde), İY skoru, gol dakikaları | https://www.openligadb.de |
| **openfootball / football.json** | — | GitHub ham dosyaları, CC0 (kamu malı) | fikstür, sonuç, İY skoru | https://github.com/openfootball/football.json |
| **TheSportsDB** | `THESPORTSDB_KEY` | Ücretsiz anahtar '123': ~30 istek/dk, günlük liste lig başına 3 maç | fikstür, sonuç, stadyum, şehir, kadro listesi | https://www.thesportsdb.com/pricing |
| **Wikidata (SPARQL)** | — | Ücretsiz, CC0; sorgu başına 60 sn, User-Agent zorunlu | stadyum, stadyum kapasitesi, şehir, stadyum koordinatı, teknik direktör | https://query.wikidata.org |
| **Open-Meteo** | — | Ticari olmayan kullanım ücretsiz, 10.000 istek/gün | hava durumu, şehir koordinatı | https://open-meteo.com/en/pricing |
| **Haber RSS akışları** | — | Yayıncıların herkese açık RSS akışları | haber başlığı, özet, bağlantı | — |
| **Meclis Elo (iç hesap)** | — | Havuzdaki gerçek sonuçlardan hesaplanır | takım gücü (Elo), gol modeli önseli | — |

## Anahtar gerektirenler (anahtar gelene kadar "anahtar bekleniyor")

| Kaynak | Anahtar (ortam değişkeni) | Ücretsiz katman | Doldurduğu alanlar | Kayıt / bilgi |
|---|---|---|---|---|
| **API-Football (api-sports.io)** | `API_FOOTBALL_KEY` | Ücretsiz: 100 istek/gün, 10/dk | fikstür, ilk 11, sakat/cezalı, maç istatistiği, oyuncu dakika/gol/asist, hakem | https://dashboard.api-football.com/register |
| **football-data.org** | `FOOTBALL_DATA_TOKEN` | Ücretsiz: 12 turnuva, 10 istek/dk (Süper Lig yok) | fikstür, sonuç, İY skoru, hakem, stadyum | https://www.football-data.org/client/register |
| **The Odds API** | `ODDS_API_KEY` | Ücretsiz: ayda 500 kredi (h2h+totals × eu = 2 kredi/lig) | 1X2 oranı, Alt/Üst oranı, Pinnacle oranı | https://the-odds-api.com/#get-access |
| **OddsPapi** | `ODDSPAPI_KEY` | Ücretsiz: ayda 250 istek (bot günde en çok 1 oran çağrısı yapar) | 1X2 oranı (Pinnacle dahil 300+ bahis şirketi) | https://oddspapi.io/en/register |
| **Sportmonks Football API v3** | `SPORTMONKS_KEY` | Ücretsiz plan: yalnızca Danimarka Superliga + İskoçya Premiership (180 istek/saat/varlık); bizim liglerimiz ücretli planda | fikstür, sonuç, İY skoru, stadyum, hakem, maç istatistiği | https://my.sportmonks.com/register |
| **FootyStats API** | `FOOTYSTATS_KEY` | Ücretsiz: yalnızca Premier Lig, 180 istek/saat; Süper Lig ücretli (Hobby £29.99/ay) | sonuç, İY skoru, korner, kart, isabetli şut, faul, stadyum, 1X2 ve 2.5 Alt/Üst oranı | https://footystats.org/api |
| **SportDevs Football API** | `SPORTDEVS_KEY` | Ücretsiz: 300 istek/gün, 10 büyük lig | fikstür, sonuç, İY skoru, stadyum | https://sportdevs.com/football |
| **Club Elo** | `CLUBELO_KEY` | Eskiden anahtarsızdı; Eylül 2026'dan beri API kimlik doğrulama istiyor, kayıt henüz kapalı | takım gücü (Elo) başlangıç puanı | http://clubelo.com/API |

## Tüm anahtarlar

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

GitHub: Repo → Settings → Secrets and variables → Actions → **New repository secret** (adlar yukarıdaki gibi).
İş akışı (`.github/workflows/meclis.yml`) hepsini ortam değişkeni olarak geçirir.

## Haber akışları (RSS)

Yalnızca başlık, özet ve bağlantı saklanır; tam metin kopyalanmaz.

- https://www.trthaber.com/spor_articles.rss
- https://www.aa.com.tr/tr/rss/default?cat=spor
- https://www.fotomac.com.tr/rss/futbol.xml
- https://www.ntvspor.net/rss/kategori/futbol
- https://www.ntvspor.net/rss/kategori/dunyadan-futbol
- https://www.sporx.com/_xml/rss.php
- https://www.hurriyet.com.tr/rss/spor
- https://www.sabah.com.tr/rss/spor.xml
- https://www.aspor.com.tr/rss/futbol.xml
- https://www.ajansspor.com/rss
- https://www.cnnturk.com/feed/rss/spor/news
- https://www.haberturk.com/rss/spor.xml
- https://www.sozcu.com.tr/feeds-rss-category-spor
- https://feeds.bbci.co.uk/sport/football/rss.xml
- https://www.theguardian.com/football/rss
- https://www.skysports.com/rss/12040
- https://www.marca.com/rss/futbol/primera-division.xml
- https://www.gazzetta.it/rss/calcio.xml

Denenip eklenmeyenler: NTV Spor kök `/rss` (HTML dönüyor), Fanatik, Milliyet, TFF ve kulüp siteleri (RSS yok ya da
403), kicker ve L'Équipe (403), ESPN ve Daily Mail (akışta 1–2 öğe).

## Birleştirme önceliği (alan bazında)

- **Genel alanlar:** API-Football → Sportmonks → football-data.org → FootyStats → SportDevs → OpenLigaDB →
  The Odds API → OddsPapi → TheSportsDB → football-data.co.uk → openfootball.
- **Oranlar:** The Odds API → OddsPapi (Pinnacle) → football-data.co.uk → FootyStats → API-Football → Sportmonks.
- **Boşluk dolduranlar:** openfootball ile OpenLigaDB `pl`/`la1` (topluluk ligleri) yeni maç ya da takım
  açmaz. Yalnızca havuzda zaten olan maçın boş alanlarını doldurur; eşleşmeyen kayıtlar günlükte listelenir.
- **Stadyum, şehir, kapasite, koordinat, teknik direktör:** takım kartında boşsa Wikidata'dan gelir (14 günde bir
  yeniden sorgulanır). Maçta stadyum yoksa ev sahibinin stadı yazılır ve kaynağı `wikidata (ev sahibi stadı)`
  olarak işaretlenir. Wikidata bazen eski stadı döndürür (ör. Brentford için Griffin Park); bu bilinen bir
  veri kalitesi sınırıdır.

## Elo önseli (gol modeli)

`meclis/model/elo.py`: havuzdaki gerçek sonuçlardan maç öncesi Elo hesaplanır (K=20, ev avantajı 65, gol farkı
çarpanı). Club Elo API'si açılıp `CLUBELO_KEY` tanımlanırsa başlangıç puanı olarak Club Elo kullanılır. Gol
sayıları maç öncesi Elo farkına Poisson regresyonuyla bağlanır; elde edilen λ, Dixon-Coles λ ile log uzayında
**%45 Elo** ağırlığıyla harmanlanır.

Geriye dönük test (T1, E0, SP1, I1; 752 maç; her maç yalnızca kendinden önceki veriyle tahmin edildi):

| Elo ağırlığı | 1X2 log loss | Alt/Üst 2.5 log loss |
|---|---|---|
| 0 (yalnız Dixon-Coles) | 1.0128 | 0.6945 |
| 0.45 (seçilen) | 1.0096 | 0.6870 |

## Bilinçli olarak KULLANILMAYANLAR (kullanım koşulları)

| Kaynak | Neden |
|---|---|
| FotMob, SofaScore, Flashscore, WhoScored | Koşulları otomatik erişimi / kazımayı yasaklıyor; resmî açık API yok. |
| Transfermarkt, Forebet, Understat, FBref | Koşullar kazımayı yasaklıyor (FBref/Sports-Reference otomatik erişimi açıkça sınırlıyor). |
| Nesine iç uç noktaları | Belgelenmemiş iç API; kullanım koşulları izin vermiyor. |
| ESPN belgelenmemiş API | Kamuya açık kullanım koşulu yok; kullanılmıyor. |
| Club Elo web sayfaları | Yalnızca resmî API kullanılır; Eylül 2026'dan beri API kimlik doğrulaması istiyor ve kayıt kapalı. |
| odds-api.io | Yeni ücretsiz anahtar verilmesi 27 Ağustos 2026'da durduruldu. |
| iSports API, AllSportsAPI | Kalıcı ücretsiz katman yok, yalnızca deneme süresi. |
| 5DollarFootballAPI | Kullanım koşulları doğrulanamadı. |
