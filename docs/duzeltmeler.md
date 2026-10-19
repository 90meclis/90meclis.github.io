# 90 Meclis — Düzeltme listesi: kurulan sistem ile kullanıcının sözü

Tarih 20.10.2026 · Denetlenen: `origin/main` @ `6deba6c` · Ölçüt: `docs/kullanici-istekleri.md` (alıntılar) ve `docs/tarif.md` v2.
Sahipler: **P** = pipeline çalışanı (`meclis/*`, `supabase/*`, `.github/workflows/meclis.yml`) · **F** = ön yüz çalışanı
(`web/`, `views/`, `app.py`) · **K** = kullanıcının yapması gereken.
`6deba6c` ile zaten düzeltilenler (lig kırılımı, tek kâr/zarar tanımı, ADMIN_TOKEN, misafirden bot düğmeleri,
arşiv tarih filtresi, bahis çağrısı süzgeci) bu listede yoktur.

## P0

**D1 — Geçmiş sezon hâlâ her yerde (P).** Kullanıcı: "geçmiş sezon değil bu sezon genelinde çalışacaktık" (t33u).
- `meclis/analysis.py:16`: `PRIOR_SEASON_WEIGHT = 0.3`. Geçmiş sezon maçları gol modeline, Elo'ya ve sayım modellerine giriyor. → Bu sezon dışı maçlar modelden çıkarılmalı (ağırlık 0).
- `meclis/pool.py:747`: `history(days=760)` iki sezonu çekiyor. Model, Veri Lab tabloları ve seriler (`meclis/lab.py`, `compute_trends`) buradan besleniyor. → Bu sezona sınırlanmalı. H2H yalnızca gösterim olarak geçmişe bakabilir; bu da kullanıcıya sorulmadan genişletilmemeli.
- `.github/workflows/meclis.yml:8` (03:40 TSİ `gecmis`) ve `meclis/backfill.py`: her gece 2022–2024 doldurma. Ana ajan sohbette bunu "eski sezonlar her gece arşive ekleniyor, ~16 gün" diye sunmuştu. → Durdurulmalı. Gece kotası bu sezonun eksiklerine (kadro dakikaları, istatistik, sakatlık) harcanmalı.
- `meclis/teamnews.py:8,73-74,114-115,191-196`: Eksik Etkisi'nde oyuncu önemi "API-Football 2024" sezonundan geliyor. → Bu sezonun maç kadrolarından ve ilk 11'lerinden hesaplanmalı.
- `meclis/__main__.py` / README: `yenile --gecmis` ("önceki sezonu da çek") ve `gecmis` komutları; README:87,92,104. → Kaldırılmalı ya da "yalnızca arşiv, modele girmez" diye ayrılmalı (kullanıcı onayıyla).
- `views/veri_laboratuvari.py:21`: "Havuzda … bitmiş maç (son iki sezon)". (F)

**D2 — "Karar Bekliyor / Karar Verilmedi" kalıntıları (P).** Kullanıcı: "Kalderim, hayır böyle bir şey yok… Siz hiç de karar vermedik. Hayır" (t32u).
`supabase/schema.sql:277,281,493-496` (`v_tutanak` hâlâ `karar_bekliyor/karar_verilmedi` üretiyor; kuyruk durumları `ertelendi/yetismedi`), `docs/supabase-sema.md:66-68`, `tests/test_postgres_schema.py:165-170`, `meclis/markets.py` `QUEUE_LABELS`.

**D3 — Ücretsiz kaynaklar bağlanmadı (K + P).** Kullanıcı: "Önce ücretsiz kaynakları dene" (t20s4); "fazlası ile veri ve data api kaynaklarımız olması gerekiyordu… veri sıkıntısı çekmek istemiyorum" (t29u).
football-data.org, The Odds API, OddsPapi ve SportDevs ücretsiz anahtarlarla açılıyor; dördü de bekliyor (`docs/kaynaklar.md`). K: dört kayıt (tek listede istenmeli, t30u). P: BSD'nin gerçekten kayıt getirdiği yönetim sayfasında doğrulanmalı; daha önce 0 kayıt vardı. Gerçek oran olmadığı için değer kuralı ve Günün Kararı çoğu gün çalışamıyor.

**D4 — Streamlit hâlâ misafire açık (F + K).** Kullanıcı: "ben bu yüzden stremlit kullanmak istememiştim… başka misafir kullanıcılar da olacak daha profesyonel" (t29u).
`90meclis.streamlit.app` Streamlit görünümüyle yayında. Web sitesi (`web/`, `.github/workflows/pages.yml`) var. GitHub Pages'in repo ayarlarında açılıp açılmadığı doğrulanmadı. → Site yayına alınıp kullanıcıya link verilmeli. Streamlit ya yalnızca yönetim aracı olur ya da kapatılır (kullanıcı onayıyla).

## P1

**D5 — "Kullanıcı tarafı / misafir tarafı" belirsizliği (K).** "kullanıcı tarafı olsun. Misafir tarafı olsun" (t25u).
Şu an misafir yüzü ve ADMIN_TOKEN'lı yönetim var. Ayrı bir kullanıcı  tarafı isteniyorsa kapsam değişir. Tek soru olarak sorulmalı.

**D6 — "Sürekli çalışan sistem" (P).** "burada sürekli çalışabilecek bir şey olması lazım… saatler öncesi… hazırlanması gerekiyor" (t32u).
GitHub Actions cron'u yoğun saatlerde gecikebilir ya da düşebilir. 60 gün commit olmazsa zamanlanmış işler kapanır (`meclis.yml` commit atmıyor). → Kalp atışı/yedek commit'i ve kaçan çalışmayı yakalama mantığı eklenmeli.

**D7 — Belgelerde eski veya bizden çıkma kurallar (P/F).**
- README "Model özeti" tamlık ağırlıkları kodla uyuşmuyor (`meclis/analysis.py` `COMPLETENESS_WEIGHTS`).
- `.env.example`: `BOT_MIN_MINUTES_BEFORE_KICKOFF=15` (T-15 kalıntısı), `COMPLETENESS_MIN=60` ("eşik" gibi okunuyor).
- README "Bilinen sınırlar": kale vuruşu için ücretsiz kaynak yok diyor, ama BSD veriyor.

**D8 — Değer eşikleri ve "maç başına tek seçim" doğrulanmalı (ana ajan).** Kullanıcı "bizim tahmin anlayışımızı hatırla" (t33u) dedi, ama bu anlayışın asıl metni (v1 talimatı) bu denetimde okunamadı.
`meclis/analysis.py:select_single` (edge ≥ 0,03, p ≥ 0,40, oran ≤ 3,20; oransız 0,72–0,86; maç başına 1) v1 metniyle karşılaştırılmalı.

## P2

**D9 — Ad ve etiketler (F).** Bölüm adları (Maç Merkezi, Tahmin Botu, Tahmin Arşivi, Veri Laboratuvarı, Gündem Masası, Güven Panosu) ve etiketler (Günün Kararı, Meclis Görüşü, Karar Birliği) kodda doğru. Araştırma raporundaki "Tutanak / Sicil / Oybirliği" önerileri kullanılmamalı; şu an kullanılmıyor, böyle kalmalı.

**D10 — Kupon kuralları değiştirilmemeli (P).** "kuponlar için bir şey demedim onları değiştirme" (t33u). `meclis/coupons.py` ve `bot.py:_coupons` şu an ilk kurala uygun. Kimse "düzeltme" adına dokunmamalı.

## Uyumlu olanlar
Her maç analiz edilir, yalnızca değer seçimi yayımlanır (t33u). Karar Bekliyor ve T-15 kodda yok (t32u). Yayın
saatler önce yapılır ve kilitlenir (t32u). Gece dahil 2 saatte bir yeniden hesaplama var (t33u). Tahmini 11 var,
resmî 11 beklenmez (t32u). Maç maç değerler gösterilir (t32u). 21 lig var ve varsayılan seçim hepsi (t29u). Repo
herkese açık (t25u).
