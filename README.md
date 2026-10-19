# ⚽ 90 Meclis

Maç maç analiz yapan, tahminlerini **maç başlamadan önce kilitli bir deftere yazan** ve sonra kendi
karnesini dürüstçe (kayıplar dahil) gösteren bir futbol tahmin uygulaması. Arayüz tamamen Türkçedir,
tek bir çok sayfalı Streamlit uygulamasıdır; veri Supabase'te (PostgreSQL) tutulur.

> ⚠️ Bu uygulama bahis tavsiyesi değildir. Model olasılıkları hata payı taşır; geçmiş isabet gelecek
> için garanti vermez. 18 yaş altı için uygun değildir.

## Bölümler

| Menü | Ne yapar |
|---|---|
| **Maç Merkezi** | Seçilen maçın ilk 11'leri (API-Football anahtarıyla, maça ~75 dk kala), sakat/cezalılar ve **Eksik Etkisi (0–100)**, son form, istatistik ortalamaları, H2H, Open-Meteo hava durumu, model λ'ları, pazar olasılıkları ve "🎙️ Maç konuşuyor" senaryo metni. Veri yoksa "yok" der; uydurmaz. |
| **Tahmin Botu** | Bülteni (önümüzdeki 48 saat) tarar, her maçta tüm pazarları (skor, 1X2, çifte şans, gol Alt/Üst, KG, takım golü, İY gol, korner, kart, isabetli şut, kale vuruşu) hesaplar, tamlık kapısından geçenleri **maçtan önce** kaydeder. Eksik veri maçı elemez: tahmin **Karar Bekliyor** olur, yeniden denenir; maça 15 dk kala hâlâ eksikse **Karar Verilmedi** olarak kayıtta kalır. |
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
| `FOOTBALL_DATA_TOKEN` | Hayır | football-data.org (ücretsiz kayıt). |
| `API_FOOTBALL_KEY` | Hayır (önerilir) | İlk 11, sakatlık, oyuncu dakikaları, maç istatistiği. |
| `ODDS_API_KEY` | Hayır | The Odds API piyasa oranları. |
| `LEAGUES` | Hayır | `T1,E0,SP1,I1,D1,F1` (T1 = Süper Lig; ayrıca E1, N1, P1). |
| `COMPLETENESS_MIN` | Hayır | Tamlık eşiği (varsayılan 60/100). |
| `DEMO_MODE` | Hayır | `1` = örnek veri modu. |

Diğer ayarlar için `.env.example` dosyasına bakın. **Gerçek anahtar hiçbir dosyada depoya girmez.**

## Bot (komut satırı)

```bash
python -m meclis yenile [--gecmis]     # veri havuzunu güncelle (--gecmis: önceki sezonu da çek)
python -m meclis gundem                # RSS gündem taraması
python -m meclis bot [--kuru]          # analiz + kayıt (--kuru: hiçbir şey yazmadan dene)
python -m meclis sonuclandir           # biten maçları otomatik sonuçlandır
python -m meclis sabah                 # yenile + gündem + bot + sonuçlandır
python -m meclis durum                 # kaynak durumu / kuyruk özeti
python -m meclis bot --ligler T1,E0    # lig seçimi
```

Aynı işlemler arayüzde **Tahmin Botu** sayfasından da yapılabilir (anon anahtarla bağlıyken yalnızca kuru çalıştırma).

### Zamanlanmış çalışma (GitHub Actions)

`.github/workflows/meclis.yml`:
- 08:00 TSİ `sabah`, gün içinde her 2 saatte bir `yenile + bot + sonuclandir`, gece `sonuclandir`;
  ayrıca **Actions → Run workflow** ile elle.
- Repo → Settings → Secrets and variables → Actions → **Secrets**: `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, (isteğe bağlı) `API_FOOTBALL_KEY`, `FOOTBALL_DATA_TOKEN`, `ODDS_API_KEY`.
  **Variables**: `LEAGUES` (isteğe bağlı).

## Model özeti

- **Gol / skor:** zaman ağırlıklı (ξ = 0.0019/gün) **Dixon-Coles** Poisson modeli; 10×10 skor matrisinden 1X2,
  çifte şans, Alt/Üst 1.5/2.5/3.5, KG, takım golleri, doğru skor; ilk yarı oranı ligden ölçülür.
- **Sayım pazarları:** korner, kart, isabetli şut, kale vuruşu için takım hücum/savunma oranları (büzülmeli);
  lig varyansı ortalamayı aşıyorsa **negatif binom**, değilse Poisson.
- **Sakatlık:** oyuncu önemi = dakika, ilk 11, gol+asist katkısı, savunma payı; "Eksik Etkisi" (TEE, 0–100)
  ve λ çarpanı (0.70–1.30 ile sınırlı). Sakatlık verisi yoksa bu açıkça yazılır.
- **Veri tamlığı (0–100):** fikstür 20, takım geçmişi (≥8 maç) 20, piyasa oranı 15, sakatlık 15, istatistik
  geçmişi 15, hakem 5, ilk 11 10. Eşik altı → Karar Bekliyor.
- **Seçim:** piyasa oranı varsa değer (edge) ≥ %3; yoksa yüksek olasılıklı, "adil oran" etiketli seçim
  (bunlar ROI'ye katılmaz). Günün Kararı yalnızca gerçek oranlı ayaklardan, beklenen değeri ≥ 0 olan en
  yüksek ortak olasılıklı kombinasyondur; bant tutmazsa **kupon yok** denir.

## Veri kaynakları ve sınırları

**Anahtarsız çalışanlar**
- **football-data.co.uk** — Süper Lig dahil sonuç, İY skoru, şut, isabetli şut, korner, faul, kart, hakem,
  açılış/kapanış oranları (CSV). Güncel sezon fikstürü de alınır. Kale vuruşu ve xG Süper Lig için yok.
- **TheSportsDB** (ücretsiz anahtar `123`) — fikstür/sonuç, stadyum, şehir. Ücretsiz uç noktalar sınırlı ve
  yavaş (istekler arası bekleme uygulanır).
- **Open-Meteo** — hava durumu (anahtarsız, ticari olmayan kullanım).
- **RSS** — TRT Spor, AA Spor, Fotomaç, BBC Football; yalnızca başlık/özet/bağlantı saklanır.

**Anahtar gerektirenler**
- **API-Football** (birincil kaynak: fikstür, ilk 11, sakatlık, oyuncu istatistiği) — ücretsiz plan 100 istek/gün;
  ücretsiz planda güncel sezona erişim kısıtlı olabilir. Bot günlük bütçeyi sayar (`API_FOOTBALL_DAILY_BUDGET`).
- **football-data.org** — ücretsiz planda Süper Lig yok (büyük Avrupa ligleri var), 10 istek/dk.
- **The Odds API** — ücretsiz ayda 500 kredi; Türk bahis şirketleri yok (uluslararası ortalama + Pinnacle).
- **Supabase** — kalıcı kayıt.

**Bilinçli olarak KULLANILMAYANLAR:** FotMob, SofaScore, Flashscore, WhoScored, Transfermarkt, Forebet,
Understat, FBref, Nesine — kazıma (scraping) yapılmaz. Tüm istekler `90Meclis/1.0` kimliğiyle, önbellekli ve
sınırlı hızda yapılır; kaynakların kullanım koşullarına uyulur.

**Birleştirme:** aynı maç = aynı lig + iki takım eşleşti + başlama saati ±36 saat. Alan bazında öncelik
API-Football → The Odds API → football-data.org → TheSportsDB → football-data.co.uk; boş alan sıradaki kaynaktan
doldurulur, her alanın kaynağı `matches.sources` içinde, eksikler `missing_fields` içinde saklanır, skor çelişkileri
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
# İsteğe bağlı: şemayı gerçek PostgreSQL'de sına (boş bir test veritabanı verin)
MECLIS_TEST_PG_DSN="host=localhost dbname=meclis_test user=postgres" pytest tests/test_postgres_schema.py
```

Kapsam: Dixon-Coles ve sayım modelleri, kaynak birleştirme (Türkçe ad eşleme, provenance, maç düşürmeme),
kupon bandı, sonuçlandırma (iade dahil), değiştirilemezlik tetikleyicileri, TEE, Karar Bekliyor → Karar
Verilmedi akışı, altı sayfanın açılışı (Streamlit AppTest) ve başsız sunucu sağlık kontrolü.

## Bilinen sınırlar

- Kale vuruşu için ücretsiz kaynak yok → bu pazar çoğunlukla **Karar Bekliyor** kalır.
- Anahtarsız modda sakatlık ve ilk 11 yok; tamlık puanı buna göre düşer, metinlerde açıkça yazılır.
- Piyasa oranı yoksa Günün Kararı genellikle kurulmaz (bilinçli).
- Takım adı eşleştirme muhafazakârdır; yeni bir ad varyantı ayrı takım sanılabilir (`meclis/names.py` → `ALIASES`).
- Haber–maç eşleşmesi takım adına dayanır; yanlış pozitif/negatif olabilir.
- Kaynakların kullanım koşulları değişebilir; ticari kullanımdan önce hukuki kontrol önerilir.
