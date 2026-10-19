# 90 Meclis — Gereksinim Kontrol Listesi (iç belge)

Sürüm 2 · 20.10.2026 · Öncelik: **kullanıcının kendi sözü** (`docs/kullanici-istekleri.md`) > bizim özetlerimiz; sonra söylenen önce söyleneni geçer. Kaynaklar: kullanıcıyla konuşmalar, `90-meclis-arastirma.md`,
`90-meclis-veri-kaynaklari.md`, `foodstats-inceleme.md`, depodaki kod ve belgeler.
Her madde kontrol edilebilir bir gereksinimdir. Kimlikler (`TA-3` gibi) `docs/eksikler.md` içinde kullanılır.
**[AÇIK]** = kullanıcı henüz karar vermedi; uydurma karar yok. **[PARAMETRE]** = sayıyı kullanıcı değil biz koyduk (değiştirilebilir). Alıntı kimlikleri (t29u vb.) `docs/kullanici-istekleri.md`'dedir.

## 1. Kimlik, kitle, ses (KM)
- [ ] KM-1 Marka: modern futbol medyası + tahmin takip platformu. Slogan "Her şey tek masada".
- [ ] KM-2 Konum: Türkçe, bahis satmayan, kayıpları da gösteren, hesap veren tek masa (tahmin + maç merkezi + niş istatistik + doğrulanmış kayıt).
- [ ] KM-3 Kitle: misafir kullanıcılar (girişsiz), Türk futbol takipçisi; mobil öncelikli.
- [ ] KM-4 Arayüz %100 Türkçe; saat dilimi Europe/Istanbul; tarih `gg.aa.yyyy`, saat `SS:dd TSİ`, `tr-TR` sayı biçimi.
- [ ] KM-5 Ses: kendinden emin ama dürüst, olasılık dili. "Garanti", "kesin", "banko" yok. Kayıp ihtimali açıkça söylenir.
- [ ] KM-6 Bölüm adları (kesin): Maç Merkezi, Tahmin Botu, Tahmin Arşivi, Veri Laboratuvarı, Gündem Masası, Güven Panosu (+ Yöntem ve Sorumlu Oyun).
- [ ] KM-7 Misafirlerin yüzü profesyonel bir web sitesidir; Streamlit misafire ana ürün olarak sunulmaz ("ben bu yüzden stremlit kullanmak istememiştim", t29u).
- [ ] KM-8 [AÇIK] "kullanıcı tarafı olsun. Misafir tarafı olsun" (t25u): ayrı bir kullanıcı (Ebraar) tarafı mı isteniyor? Şu an yalnızca misafir yüzü + gizli yönetim.
- [ ] KM-9 Süreç: her şeyi biz hazırlarız; kullanıcıya yalnızca kendisinin yapması şart işler, tek listede sorulur; aynı şey tekrar sorulmaz (t30u, t35u).

## 2. Tahmin anlayışı (TA) — en kritik bölüm
- [ ] TA-1 Her maç bütün pazarlarda analiz edilir; hiçbir maç düşürülmez; **her maçın verisi** eksiksiz olur ("Her maçı veriyor olacak", t32u — tahmin değil veri, t33u).
- [ ] TA-2 Her maça tahmin verilmez ("her maça tahmin mi verilecekti ben ondan mı bahsediyorum", t33u): yalnızca değer kuralını geçen seçim yayımlanır.
- [ ] TA-3 [PARAMETRE] Değer kuralı (gerçek piyasa oranı varsa): edge = p × oran − 1 ≥ %3, p ≥ 0,40, oran ≤ 3,20. (v1 talimatındaki "tahmin anlayışı" ile doğrulanmalı.)
- [ ] TA-4 [PARAMETRE] Oran yoksa: yalnızca kendi modelimizden, 0,72 ≤ p ≤ 0,86, "adil oran" etiketiyle; ROI/kâr hesabına girmez (isabete girer).
- [ ] TA-5 **Bu sezon genelinde çalışılır; geçmiş sezon model girdisi değildir** ("geçmiş sezon değil bu sezon genelinde çalışacaktık", t33u). Geçmiş sezon önseli, geçmiş sezon backfill'i ve geçmiş sezondan oyuncu önemi kullanılmaz. Sezon başı az veri; bu sezonun maçları, piyasa oranı ve ek kaynaklarla güçlendirilir.
- [ ] TA-6 "Karar Bekliyor", "Karar Verilmedi", "veri yetersiz" bahanesi ve T-15 dk kuralı YOK — hiçbir ekranda, SQL görünümünde, belgede, testte ("Kalderim, hayır böyle bir şey yok… bahane üretmeyeceğiz. Verilerimizi güçlendireceğiz", t32u).
- [ ] TA-7 Eksik veri tahmini durdurmaz; başka kaynaklardan tamamlanır. Tamlık puanı yalnızca güven göstergesidir.
- [ ] TA-8 Yayın maçtan saatler önce ("Biz bu maçta saatler öncesinde paylaşacağız", t32u); hazırlık önceden ve **sürekli çalışan** bir sistemle yapılır. [PARAMETRE] alt sınır 3 saat; sabah 08:00 çalışması günün maçlarını yayımlar.
- [ ] TA-9 "gerekirse tahminler her gece yenilensin" (t33u): yayımlanmamış adaylar her gece (ve gün içinde) güncel veriyle yeniden hesaplanır.
- [ ] TA-10 Yayımlanan seçim kilitlenir; bir daha hesaplanmaz, değişmez, silinmez.
- [ ] TA-11 Resmî ilk 11 beklenmez ("kadro çok da takılmamalıyız… beklemeyeceğiz… 11 çıkarabilirsin kendine göre", t32u); Meclis tahmini 11 kullanılır, resmî 11 gelirse yalnızca gösterilir.
- [ ] TA-12 Lig tabanından (model ve oran yokken) seçim yayımlanmaz; uydurma veri gösterilmez.
- [ ] TA-13 [AÇIK] Maç başına en fazla 1 Meclis Görüşü mü, yoksa değer geçen her pazar mı? (Kod: 1 seçim.)

## 3. Etiketler ve kuponlar (KP) — ilk haliyle; "kuponlar için bir şey demedim onları değiştirme" (t33u)
- [ ] KP-1 Meclis Görüşü = tekli tahmin.
- [ ] KP-2 Günün Kararı = 2–3 maçlık kupon, toplam oran 2,30–4,00; aynı maçtan iki ayak yok; yalnızca gerçek oranlı ayaklar; EV ≥ 0; bant tutmazsa "bugün kupon yok" denir.
- [ ] KP-3 Karar Birliği = günde 5 veya daha fazla Meclis Görüşü varsa, en güvenilen 2–3 tekliden kombine.
- [ ] KP-4 Kuponlar da tahminler gibi kilitlidir (ekleme maç başlamadan, değişiklik/silme yok).
- [ ] KP-5 Durumlar: bekliyor, başladı, kazandı, kaybetti, iade.

## 4. Pazarlar (PZ)
- [ ] PZ-1 Skor (doğru skor; yalnızca bilgi, yayımlanmaz), 1X2, Çifte Şans.
- [ ] PZ-2 Toplam gol A/Ü 1.5/2.5/3.5, KG Var/Yok, ev/deplasman takım golü A/Ü 0.5/1.5, İY gol A/Ü 0.5/1.5.
- [ ] PZ-3 Korner, kart, isabetli şut, kale vuruşu toplam A/Ü (beklenen değer etrafında 3 çizgi).
- [ ] PZ-4 Her pazar için olasılık, adil oran, (varsa) piyasa oranı + kaynağı, edge gösterilir.
- [ ] PZ-5 Verisi olmayan pazar "hesaplanmadı: neden" ile görünür, gizlenmez.

## 5. Model (MD)
- [ ] MD-1 Gol: zaman ağırlıklı Dixon-Coles (ξ = 0,0019/gün, ridge), 10×10 skor matrisi; tüm gol pazarları tek matristen.
- [ ] MD-2 Meclis Elo (K=20, ev avantajı 65, gol farkı çarpanı; Club Elo açılırsa başlangıç) λ ile log uzayında %45 harmanlanır.
- [ ] MD-3 Takımın bu sezon maçı < 3 ise piyasa oranından türetilen λ %50 harmanlanır.
- [ ] MD-4 Sayım pazarları: büzülmeli takım hücum/savunma oranları; var/ort > 1,05 ise negatif binom, değilse Poisson.
- [ ] MD-5 Eksik Etkisi ve tahmini 11 λ çarpanı olarak girer (0,70–1,30); hava durumu anlatıda.
- [ ] MD-6 Modelde takım başına < 4 maç varsa "değer" iddiası kurulmaz.
- [ ] MD-7 Model sürümü her kayda yazılır; geriye dönük test (log loss) belgelenir.

## 6. Sonuçlandırma (SN)
- [ ] SN-1 Otomatik; skor ve istatistikten.
- [ ] SN-2 İade: maç iptal/ertelendi (48 saat beklenir), A/Ü tam çizgi.
- [ ] SN-3 Sonuç verisi yoksa iade edilmez; "sonuç verisi bekleniyor" ile açık kalır, istatistik kaynakları yeniden denenir.
- [ ] SN-4 Kupon: bir ayak kaybederse kaybetti; iade ayak oranı 1 sayılır; hepsi iade ise kupon iade.
- [ ] SN-5 1 birim sabit stake; kâr yalnızca piyasa oranlı kayıtlarda.

## 7. Güven Panosu (GP)
- [ ] GP-1 Toplam/sonuçlanan/kazanan/kaybeden/iade/bekleyen, isabet (iade hariç), kâr (birim), ROI, Brier, CLV (kapanış oranına göre).
- [ ] GP-2 Kasa eğrisi (kümülatif kâr), haftalık, pazar, lig ve etiket kırılımı; kuponlar ayrı.
- [ ] GP-3 Kalibrasyon tablosu/grafiği (söylenen % ↔ gerçekleşen %).
- [ ] GP-4 Son kayıplar gizlenmeden listelenir; ölçüt tanımları açıklanır.
- [ ] GP-5 CLV için kendi kapanış oranı anlık görüntümüz (başlama saatine yakın) tutulur; tüm oranlı pazarlarda.
- [ ] GP-6 Aynı metrik her yüzde (site, Streamlit, SQL görünümü) aynı tanımla hesaplanır.

## 8. Bölümler ve ekranlar (EK)
- [ ] EK-1 Ana sayfa: "Her şey tek masada", masadaki kararlar, bugünün/sıradaki maç günü, Gündem özeti, "Neden güvenebilirsin?", dünün kararları.
- [ ] EK-2 Maç Merkezi: en yakın maç gününü açar; tarih şeridi + lig filtresi; maç satırı (saat, lig, takımlar, skor/durum, karar rozeti); boş durum "Bu tarihte maç yok" + sonraki maç günleri.
- [ ] EK-3 Maç detayı: başlık (lig, TSİ saat, stadyum, şehir, hakem), Meclisin analizi (anlatı), senaryolar, en olası skorlar, bu maçtaki kararlar, Meclis güveni (tamlık), tüm pazarlar, form (son 5), maç maç istatistik (son 10), son karşılaşmalar (İY dahil), eksikler + Eksik Etkisi + oyuncu kırılımı, Meclis tahmini 11 (+ resmî 11 bilgi), oranlar, hava durumu, maçın gündemi, alan bazında veri kaynağı.
- [ ] EK-4 Tahmin Botu: günün yayımlanan kararları ve kuponlar; "Bot nasıl karar verir?" açıklaması; misafire çalıştırma düğmesi yok.
- [ ] EK-5 Tahmin Arşivi: Kayıtlar/Kuponlar görünümü; tarih, lig, etiket, pazar, durum filtreleri; gerekçe ve senaryo notu; kilit zamanı; yalnızca yayımlananlar.
- [ ] EK-6 Veri Laboratuvarı: lig seçimi; pazar ligleri (korner, İY gol, KG, kart, isabetli şut, kale vuruşu; tümü/iç saha/deplasman, son N); takım serisi maç maç (ortalama değil); süren seriler (son 10, isabet sayısı); puan durumu.
- [ ] EK-7 Gündem Masası: çok kaynaklı akış; kategori (sakatlık, teknik direktör, kadro, transfer, genel); maça/takıma bağlama + etki notu; yalnızca başlık/özet/bağlantı; aynı haber tekilleştirilir.
- [ ] EK-8 Güven Panosu: §7.
- [ ] EK-9 Yöntem ve Sorumlu Oyun sayfası: model, kilit, durumlar, 18+, YEDAM 115.
- [ ] EK-10 Yönetim alanı misafirden gizli: kaynak sağlığı, anahtar bekleyen kaynaklar, 7 günlük kapsam, kuyruk, günlük; anahtar değeri asla gösterilmez.
- [ ] EK-11 Misafir ekranlarında geliştirici notu, "anahtar bekleniyor", ham hata, ÖRNEK VERİ görünmez.
- [ ] EK-12 Her ekranın yükleniyor / boş / hata durumu Türkçe ve dürüst.

## 9. Veri (VR)
- [ ] VR-1 Kaynak sınırı yok; hiçbir kaynak "isteğe bağlı" değil; veri sıkıntısı kabul edilmez ("fazlası ile veri ve data api kaynaklarımız olması gerekiyordu… veri sıkıntısı çekmek istemiyorum", t29u; "Hiçbir kaynak isteğe bağlı sayılmaz", t32u).
- [ ] VR-0 Önce ücretsiz kaynaklar denenir ("Önce ücretsiz kaynakları dene", t20s4); veri bulmak için her yol denenir (t32u).
- [ ] VR-2 Tek havuz: alan bazında öncelikli birleştirme, boş alan sıradaki kaynaktan dolar, çelişki kaydedilir.
- [ ] VR-3 Kimlik eşleme: Türkçe karakter normalizasyonu + takım ad eşlemeleri (alias) + fikstürden öğrenme; aynı maç = lig + iki takım + ±36 saat; çift kayıt yok.
- [ ] VR-4 Provenans: her alanın kaynağı ve çekilme zamanı saklanır ve gösterilir; eksik alanlar listelenir.
- [ ] VR-5 Ham yanıtlar yeniden işlenebilir şekilde saklanır (raw payload) — mimari raporu §3.
- [ ] VR-6 Yeniden deneme kuyruğu: üstel geri çekilme, 3 hatadan sonra sonraki kaynağa devir, iş silinmez; kota bütçesi.
- [ ] VR-7 Kaynaklar: football-data.co.uk, OpenLigaDB, openfootball, TheSportsDB, Wikidata, Wikipedia (kadro), Open-Meteo, 18+ RSS, Meclis Elo, API-Football, BSD, football-data.org, The Odds API, OddsPapi, Sportmonks, FootyStats, SportDevs, Club Elo; yenileri eklenebilir.
- [ ] VR-8 Kazıma yok / ToS'a uyulur: FotMob, SofaScore, Flashscore, WhoScored, Transfermarkt, Forebet, Understat, FBref, Nesine iç API, ESPN gizli API, FPL kullanılmaz.
- [ ] VR-9 Kadro: Wikipedia + BSD; sakat/cezalı: BSD → API-Football → SportDevs; ilk 11: BSD resmî → API-Football → SportDevs → TheSportsDB → BSD tahmini.
- [ ] VR-10 Oranlar: The Odds API → OddsPapi (Pinnacle) → football-data.co.uk → FootyStats → API-Football → Sportmonks; BSD konsensüs.
- [ ] VR-11 Her kaynağın durumu (çalışıyor / anahtar bekliyor / kota / hata, kayıt sayısı) yönetim alanında izlenir.
- [ ] VR-12 [AÇIK] Ücretli plan bütçesi (API-Football Pro, Sportmonks, FootyStats Hobby, Odds API 20K); Türk (İddaa) oranı için lisanslı kaynak yok.

## 10. Eksik Etkisi (EE)
- [ ] EE-1 Ham liste değil, takım başına 0–100 puan + bant (Etkisiz <10, Hissedilir <25, Ciddi <45, Ağır).
- [ ] EE-2 Oyuncu önemi I_p = u × (0,20 dakika + 0,10 ilk 11 + 0,25 katkı + 0,25 yedek açığı + 0,20 var/yok farkı), eksik bileşen çıkarılıp yeniden ölçeklenir; u: kesin 1, şüpheli 0,5, maç günü 0,3; bilinmiyor = 0,15 × u.
- [ ] EE-3 TEE = 100 × [1 − Π(1 − 0,6·I_p)] × (1 + 0,15·aynı mevki çakışması).
- [ ] EE-4 λ çarpanı γ = 0,35, [0,70; 1,30]; kırılımda oyuncu katkısı gösterilir.
- [ ] EE-5 Oyuncu istatistiği **bu sezondan** gelir (TA-5).
- [ ] EE-6 Ağırlıklar kalibre edilir (Veri Laboratuvarı).

## 11. Meclis tahmini 11 (XI)
- [ ] XI-1 Puan = 0,45 son ≤5 resmî ilk 11 payı + 0,35 sezon ilk 11 payı + 0,20 dış tahmin (BSD); eksik bileşen çıkarılır.
- [ ] XI-2 Kesin yok/cezalı dışarıda; şüpheli ×0,5; maç günü ×0,7; diziliş 1 KL + ≥3 D + ≥3 OS + ≥1 F.
- [ ] XI-3 "En güçlü 11"de olup tahmini 11'de olmayan oyuncu Eksik Etkisi'ne rotasyon (u 0,5) olarak girer.
- [ ] XI-4 Dayanak (kullanılan bileşenler) ekranda yazılır.

## 12. Lig kapsamı (LG)
- [ ] LG-0 Yalnızca "seçili" ligler değil, tüm ligler varsayılan olarak görünür ("Neden sadece seçili ligler var", t29u).
- [ ] LG-1 Süper Lig, TFF 1. Lig, Premier Lig, Championship, League One, La Liga, La Liga 2, Serie A, Serie B, Bundesliga, 2. Bundesliga, Ligue 1, Ligue 2, Eredivisie, Liga Portugal, Belçika, İskoçya, Yunanistan, Şampiyonlar Ligi, Avrupa Ligi, Konferans Ligi.
- [ ] LG-2 "Kaynakların verebildiği tüm diğer ligler" eklenir (kupalar, Türkiye Kupası vb.).
- [ ] LG-3 Lig listesi pipeline, Streamlit ve site arasında tutarlı.

## 13. Veri modeli ve güvenlik (DB)
- [ ] DB-1 Ana tablolar: matches, predictions, injuries, trends, agenda, sources; yardımcı: teams, players, lineups, match_stats, weather, coupons, analyses, analysis_queue, source_status.
- [ ] DB-2 Tetikleyiciler: başlama sonrası ekleme yok, `recorded_at` sunucu saati, çekirdek alan güncellenmez, sonuçlanan değişmez, DELETE/TRUNCATE yok (predictions + coupons).
- [ ] DB-3 RLS: herkes okur, yalnızca service_role yazar; sources/source_status herkese kapalı.
- [ ] DB-4 Supabase Free, AB/İrlanda. Yedek yok → düzenli dışa aktarım (JSON/CSV) zorunlu.
- [ ] DB-5 Gizli anahtar kodda/depoda yok; GitHub Secrets, Streamlit Secrets, Supabase Vault; tabloda yalnızca anahtar adı.
- [ ] DB-6 Site yalnızca publishable/anon anahtarla okur; service_role yalnızca Actions'ta.

## 14. Zamanlanmış işler (ZM)
- [ ] ZM-1 08:00 TSİ sabah (havuz + gündem + kadro + bot + sonuç).
- [ ] ZM-2 Sürekli çalışma (t32u) — gece dahil 2 saatte bir: havuz (7 gün) + kadro/eksik/ilk 11 + bot (yeniden hesaplama) + sonuç.
- [ ] ZM-3 Gece sonuçlandırma. Gece kotası **bu sezonun** eksik verisini doldurmaya harcanır (geçmiş sezon doldurma TA-5'e aykırı).
- [ ] ZM-4 İşler idempotent; eşzamanlı çalışma yok; elle tetiklenebilir.
- [ ] ZM-5 GitHub'ın 60 gün hareketsizlikte zamanlanmış işi kapatmasına karşı önlem.

## 15. Hukuk ve uyum (HK)
- [ ] HK-1 Her sayfada: "Olasılık tahminidir, garanti değildir. 18 yaş altı için değildir."
- [ ] HK-2 Bahis sitesi bağlantısı, affiliate, "oyna" butonu yok.
- [ ] HK-3 Haberlerde tam metin kopyalanmaz; atıf ve bağlantı verilir; Wikipedia CC BY-SA atfı.
- [ ] HK-4 [AÇIK] Türkiye'de bahisle ilgili içerik için hukuki görüş alınmadı; GitHub Pages ToS'unda "get-rich-quick" maddesi.

## 16. Tasarım, SEO, performans (TS)
- [ ] TS-1 Koyu spor medyası teması (gece maçı paleti, limon/nane vurgusu), Barlow Condensed + Inter, durum renkleri (kazandı yeşil, kaybetti kırmızı, iade gri, bekliyor turuncu, başladı mavi).
- [ ] TS-2 Mobil öncelikli, alt menü, erişilebilirlik (odak, skip link, reduced-motion).
- [ ] TS-3 Her bölüm için başlık/açıklama, canonical, OG görseli, sitemap, robots, 404.
- [ ] TS-4 Hızlı: statik site, Supabase'den doğrudan okuma, uyuyan sunucu yok.

## 17. Bizim önerilerimiz (kullanıcı istemedi; onay olmadan kural değildir)
- YH-1 Maç sonrası "neden tuttu/tutmadı" kartı. YH-2 Bot vs Ebraar vs topluluk karşılaştırması (araştırma raporu önerisi; bölüm/etiket adları değiştirilmez). YH-3 Haftalık şeffaflık raporu. YH-4 StatsBomb Open Data ile eğitim içerikleri. YH-5 xG ve aut atışı için lisanslı kaynak. YH-6 Çift kaynak doğrulama rozeti.

## 18. Açık noktalar
- A1 (TA-13) Maç başına tek Meclis Görüşü mü?
- A2 (VR-12) Ücretli plan bütçesi; İddaa oranı.
- A3 (HK-4) Hukuki görüş; GitHub Pages ToS.
- A4 (TA-8) "Saatler önce" alt sınırı 3 saat mi?
- A5 (KM-8) Ayrı "kullanıcı tarafı" isteniyor mu?
- A6 (TA-3/4, HK-1) Değer eşikleri ve 18+ notu v1 talimatındaki "tahmin anlayışımız"la birebir mi? (v1 dökümü bu denetimde okunamadı.)
