# 90 Meclis — Denetim: anlaştıklarımıza göre eksik / yanlış olanlar

Denetim tarihi 20.10.2026. Ölçüt `docs/tarif.md` (madde kimlikleri parantez içinde). Denetlenen commit `7761617`:
`meclis/*`, `views/*`, `web/src/*`, `supabase/schema.sql`, `.github/workflows/*`, `docs/*`.
Kod değiştirilmedi. Yalnızca bu belge ve `docs/tarif.md` eklendi.

## P0 — Söz verdiğimiz şeye aykırı ya da veri gücünü doğrudan kısan

1. **"Karar Bekliyor / Karar Verilmedi" hâlâ şemada ve belgede duruyor (TA-6).** `supabase/schema.sql:277,493-496`:
   `v_tutanak` görünümü `analysis_queue` satırlarını hâlâ `karar_bekliyor` / `karar_verilmedi` olarak birleştiriyor.
   `analysis_queue.status` içinde `ertelendi` / `yetismedi` var (`:281`). Ayrıca `docs/supabase-sema.md:66-68` ve
   `tests/test_postgres_schema.py:165-170` aynı eski kuralı anlatıyor ve test ediyor. `views/tahmin_arsivi.py:19,49`
   tarafında eski bölüm kapalı, ama ölü kod olarak duruyor. → Görünümden çıkarılmalı, belge ve test güncellenmeli.
2. **Eksik Etkisi'nde oyuncu önemi geçmiş sezondan geliyor (EE-5, TA-5).** `meclis/teamnews.py:8,73-74,114-115,191-196`:
   önem için "aynı kulüpte en son erişilebilen API-Football sezonu (ücretsiz plan: 2024)" kullanılıyor. Bu, bu
   sezonu esas alma kuralına aykırı. Bileşenlerden yedek açığı (r) ve var/yok farkı (d) hiç hesaplanmıyor
   (`meclis/model/injuries.py:4-8`). → Bu sezonun dakika, ilk 11 ve G/A verisini BSD/SportDevs maç kadrolarından
   ve havuzdaki ilk 11'lerden kendimiz biriktirmeliyiz. d′ havuzdaki maçlardan hesaplanmalı.
3. **Ücretsiz anahtarı olan kaynakların çoğu bağlı değil (VR-1, VR-7).** README / `docs/kaynaklar.md`'ye göre anahtar
   bekleyenler: football-data.org, The Odds API, OddsPapi, SportDevs (dördü de ücretsiz kayıtla açılıyor),
   Sportmonks ve FootyStats (ücretsiz katmanları bizim ligleri kapsamıyor) ve Club Elo (kayıt kapalı). Piyasa oranı
   şu an yalnızca BSD konsensüsünden ve football-data.co.uk'tan geliyor. Bu yüzden değer kuralı (TA-3) ve Günün
   Kararı (KP-2, yalnızca gerçek oranlı ayaklar) sık sık çalışamaz. → Kullanıcıdan 4 ücretsiz kayıt isteyelim.
   BSD'nin gerçekten kayıt getirdiği yönetim sayfasında (`views/sistem.py`) doğrulanmalı; önceki çalıştırmada 0 kayıt vardı.
4. **CLV dar ve dış kaynağa bağlı (GP-5).** `meclis/settlement.py:28-35`: kapanış oranı yalnızca football-data.co.uk'un
   `1X2_closing` ve `OU_GOALS_2.5_closing` alanlarından okunuyor. CL/EL/ECL ve T2'de bu dosya yok (`config.py`
   `fdcuk=False`), KG, korner, kart ve diğer çizgilerde CLV yok. Kendi oran anlık görüntümüz (`odds_snapshots`) de
   yok (`schema.sql`'de böyle bir tablo yok). → Başlamaya yakın oranları biz kaydetmeliyiz.
5. **Yedek yok (DB-4).** Supabase Free otomatik yedek almıyor. Kodda dışa aktarım işi yok (`meclis/*`,
   `.github/workflows/meclis.yml`). Değiştirilemez defterin tek kopyası riskte. → Gece işi `predictions`, `coupons`
   ve `matches` tablolarını JSON/CSV olarak depoya ya da Storage'a yazmalı.

## P1 — Anlaşılan kapsamın eksik kalan kısmı

6. **Güven Panosu'nda lig kırılımı yok; site ile Streamlit farklı hesaplıyor (GP-2, GP-6).**
   `views/guven_panosu.py:37-43` yalnızca hafta, pazar ve etiket kırılımını gösteriyor. `web/src/pages/Trust.tsx:108-111`
   de aynı. Sitede kasa eğrisi "tekliler + kuponlar" (`Trust.tsx:79`), Streamlit'te ise yalnızca tekliler
   (`views/guven_panosu.py:27`). `v_guven_*` görünümleri üçüncü bir tanım. → Lig kırılımı eklenmeli, tek tanım
   seçilmeli (kuponlar ayrı eğri).
7. **Veri havuzu mimarisi raporda anlaşılandan zayıf (VR-4, VR-5, VR-6).** `raw_payloads`, `field_values`,
   `field_priority`, `fetch_jobs` (üstel geri çekilme, 3 hatadan sonra kaynak devri, yavaş kuyruk) ve `review_queue`
   kurulmadı (`schema.sql`). Provenans yalnızca `matches.sources` jsonb'de alan → kaynak adı olarak tutuluyor,
   çekilme zamanı yok (`meclis/pool.py:203,220`). Çelişkiler yalnızca skor için yazılıyor. Oyuncu eşleşmesi ad
   benzerliğine dayanıyor (`model/injuries.py:find_player`); eşleşmeyenler için manuel onay kuyruğu yok.
8. **Gündem Masası tekilleştirmesi yalnızca bağlantıya göre (EK-7).** `meclis/sources/rss.py:58`: kimlik bağlantının
   sha1 özeti. Aynı haberi veren 5 site 5 ayrı satır oluyor. Kategori anahtar kelimeyle, maç bağlantısı takım adıyla
   yapılıyor (`meclis/news.py:10-23`). Lig etiketi yok. → Başlık benzerliğiyle kümeleme yapılmalı, lig/takım etiketi
   eklenmeli.
9. **"Bunu oyna" ifadesi (HK-2, KM-5).** `meclis/scenarios.py:112,115` anlatıda "**Bunu oyna**, 1 birim" diyor.
   Bahis yönlendirmesi yapmama ve ses kuralıyla çelişiyor. Site bu metni maç detayında gösteriyor. → "Meclisin
   kararı" dili korunmalı, oynama çağrısı kaldırılmalı.
10. **Misafir Streamlit'te bot düğmelerini görüyor (EK-4, EK-11).** `views/tahmin_botu.py:49-67`: "Havuzu yenile",
    "Botu çalıştır", "Kuru çalıştır" ve "Sonuçlandır" düğmeleri. Anon anahtarla yazma kapalı, ama "Kuru çalıştır"
    misafire açık ve dış istek tetikleyebilir. `views/gundem_masasi.py:13` için de aynısı geçerli. → Bu düğmeler
    yönetim alanına taşınmalı.
11. **Yönetim alanı korumasız (EK-10).** `app.py:15`: `?yonetim=1` yazan herkes Sistem Durumu sayfasını açıyor.
    Anahtar değeri gösterilmiyor, ama kaynak ve kota bilgisi açık. Sitede (`web/`) yönetim alanı hiç yok.
12. **Lig kapsamı "kaynakların verebildiği tüm ligler" değil (LG-2, LG-3).** `meclis/config.py:66-90`: 21 sabit lig
    var. Türkiye Kupası, TFF 2. Lig, Avusturya, İsviçre, Danimarka (Sportmonks ücretsiz), Brezilya, MLS vb. eklenmedi.
    `web/src/lib/labels.ts:12,25` E3 ve SC1 adlarını taşıyor, ama pipeline bu ligleri çekmiyor (tutarsızlık).
13. **Tahmin Arşivi'nde tarih filtresi yok (EK-5).** `web/src/pages/Archive.tsx:22-27`: filtreler etiket, durum,
    lig, pazar ve metin. Tarih aralığı yok.
14. **Geçmiş veri doldurma bu sezon değil (TA-5).** `python -m meclis gecmis` yalnızca 2022–2024'ü dolduruyor
    (`meclis/backfill.py`, `docs/kaynaklar.md`). Bu sezonun eksik maç istatistikleri için ayrı bir doldurma işi yok;
    istatistik yalnızca sonuçlandırmada deneniyor (`settlement.py:56-60`).
15. **60 gün hareketsizlik koruması yok (ZM-5).** `.github/workflows/meclis.yml` depoya hiç commit atmıyor. Herkese
    açık depoda 60 gün commit olmazsa GitHub zamanlanmış işleri kapatır. → Yedek işi (madde 5) bunu da çözer.

## P2 — Temizlik ve tutarlılık

16. **Eski ayarlar duruyor.** `.env.example`: `BOT_MIN_MINUTES_BEFORE_KICKOFF=15` ve "eşik" gibi okunan
    `COMPLETENESS_MIN=60`. `meclis/config.py:106,131`: `min_minutes_before_kickoff` ("kullanılmıyor") ve
    `completeness_min`. `BOT_PUBLISH_LEAD_HOURS` ile `BOT_PUBLISH_WINDOW_HOURS` `.env.example`'da yok.
17. **İki tamlık tanımı.** README "Model özeti": fikstür 20, ≥8 maç 20; kod (`meclis/analysis.py`
    `COMPLETENESS_WEIGHTS`): fikstür 15, bu sezon ≥6 maç 25. Belge kodla eşitlenmeli.
18. **Ölü kod.** `views/tahmin_arsivi.py:19,49-60` (`show_q=False` bloğu); `markets.py` `QUEUE_LABELS`
    `ertelendi/yetismedi` etiketleri.
19. **Kale vuruşu verisi.** README "Bilinen sınırlar" kale vuruşu için ücretsiz kaynak olmadığını yazıyor, ama BSD
    artık veriyor (`docs/kaynaklar.md` BSD satırı). Belge güncellenmeli.

## Doğrulanan ve uyumlu olanlar (kısaca)
Değer kuralı ve oransız seçim (`analysis.py:select_single`), bu sezonu esas alma (0,3 önsel), 3 saat önce yayın ve
kilit (`bot.py:publishable`), gece dahil 2 saatte bir yeniden hesaplama (`meclis.yml`), kupon kuralları
(`coupons.py`, `bot.py:_coupons`), sonuçlandırma ve iade (`settlement.py`, `markets.py:settle_pick`), değiştirilemezlik
tetikleyicileri ve RLS (`schema.sql:460-482`), Meclis tahmini 11 (`xi.py`), TEE formülü, 21 lig, 18 RSS akışı, kazıma
yasağı listesi, sitede 18+ ve sorumlu oyun metinleri (`web/src/components/ui.tsx:111`, `About.tsx`), SEO
(`postbuild.mjs`, sitemap, robots), GitHub Pages yayını (`.github/workflows/pages.yml`).

## Açık noktalar (kullanıcı kararı gerekiyor)
- A1 (TA-13) Maç başına tek Meclis Görüşü mü, değer geçen her pazar mı? Kod tek seçim yayımlıyor.
- A2 (VR-12) Ücretli plan bütçesi (API-Football Pro 19 $, Sportmonks 29 €, FootyStats £29,99, Odds API 30 $). Türk İddaa oranı için lisanslı kaynak yok.
- A3 (HK-4) Türkiye'de bahis içeriği için hukuki görüş; GitHub Pages ToS uygunluğu ve uzun vadeli barındırma.
- A4 (TA-8) "Saatler önce" = şu an en az 3 saat. Kullanıcı farklı bir süre isterse değişir.
