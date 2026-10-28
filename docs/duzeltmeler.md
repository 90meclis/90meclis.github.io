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

## 2026-10-20 gece kararları (kullanıcı)
- Avrupa kupası maçları ayrı veri (Avrupa / Lig / Tümü); model ikisini birlikte kullanır.
- Her takımın iç lig puan durumu ve istatistiği mutlaka olacak (Sabah FK eksikti).
- Kadrolar formasyona göre doğru dizilir.
- Kupon başlığı her yerde "Günün Kararı".
- "Tahmin Botu" → "Ortak" (Meclis'in yapay zekâ analisti); farklı tasarım; bültendeki her maç analiz edilir.
- Ana ekran, Laboratuvar (3 dokunuşta analiz), Güven Panosu (backtest ayrı): elit tasarım.
- Senaryolar film senaryosu gibi: başlık, perdeler, kırılma anı, final skoru, pazarlar, canlı sinyaller; gerçek veriye dayalı.
- Tahmin gücü: kayıp analizi, kalibrasyon, yalnız gerçek yabancı oran, tekli ≥1,50, ≥%3 değer, aşırı değer = hata şüphesi.
- Rakip analizi: /workspace/90-meclis-rakip-analizi.md.
- Ölçüt: "Kullanır mıydım, işime yarar mı, analiz yapabilir miyim, tahminleri iyi mi?"

## 26–27 Ekim 2026 — otonom çalışma ve resmî başlangıç
- Resmî kayıt 27.10.2026 00:00 TSİ'de başladı. Deneme dönemi kayıtları (14 tahmin, 2 kupon, 519 bot seçimi, 15 mühür) `deneme_yedek_*` tablolarında; canlı tablolarda yok. `meclis/bot.py` RESMI_BASLANGIC öncesi maça asla yayın yapmaz. Eski mühür manifestosu `muhur/arsiv/`.
- Tek parça `meclis.yml` kaldırıldı → `meclis-yayin` (saatlik), `meclis-sonuc` (2 saatte bir), `meclis-gundem` (4×/gün), `meclis-gece` (03:40 TSİ), `meclis-saglik` (09:10/21:10 TSİ). Adım başına süre bütçesi; hata → "otomatik-izleme" issue. Ayrıntı README.
- Zaman aşımının kökü: kadro adımı BSD 429 / Wikipedia maxlag yüzünden her çalışmada yüzlerce takımı yeniden deniyordu (+ her maç için 70 günlük maç listesinin yeniden okunması). Devre kesici + günlük deneme + takım dizini önbelleği.
- Arşiv = "Meclis Defteri" (altın, editoryal; yalnız yayımlanan kararlar). Ortak = bütün bültenin canlı analiz masası.

## 27 Ekim 2026 — seçim kuralı: "değer" yerine "isabet" (kullanıcı kararı)
- Kullanıcı: "bizim için değerli maç değil, gelecek/tutacak analiz ve tahmin lazım." Değer-önce kuralı (edge ≥ %3) 27 Ekim'de hiç seçim çıkarmadı: oranlar piyasa ortalaması (marjlı), olasılık marjsız Pinnacle'a harmanlanıyor → oran 1.50–5.00 bandında kalibre değer neredeyse hiç %3'ü geçmiyordu (yalnızca 5.00 üstü uç oranlar).
- Yeni kural (PICK_MODE=isabet, varsayılan): maç başına, oranı ≥ 1.50 olan pazarlar arasında KALİBRE OLASILIĞI en yüksek seçim (model + marjsız piyasa harmanı). Olasılık ≥ %50; Meclis Görüşü için ≥ %52, günde en fazla 8 tekli. Günün Kararı: en güvenilen 2–3 maç, toplam oran 2.30–4.00, beklenen değer şartı yok. Değer artık bilgi amaçlı. Veri kontrol (aşırı ayrışma) seçilmez, kadro belirsizliği güveni düşürür, ≥ 3 saat önce kilit.
- Geri test (bu sezon, 2.311 pazar satırı, açılış oranı): kalibre olasılık bantları isabetle örtüşüyor — 1X2 %50–55 → %53, %55–60 → %57; 2.5 gol %50–55 → %54, %55–60 → %60.
- Yayın penceresi 30 saat: ertesi günün bülteni bir önceki akşam yayımlanabilir (Günün Kararı bütün günün maçlarından kurulur).

## 27 Ekim 2026 (akşam) — ürün ayrılığı ve kupon kapısı (kullanıcı kararı)
- Bir maç günde en fazla bir yayımlanan üründe: Günün Kararı → Karar Birliği → Meclis Görüşleri sırasıyla; sonraki ürün öncekilerin maçını kullanamaz. Karar Birliği artık tekli görüşlerden kurulmuyor: GK'den sonra kalan havuzda olasılığı ≥ %52 olan ve modelle marjsız piyasanın ≤ 6 puan içinde hemfikir olduğu en güvenilen 2–3 maç.
- Kupon kapısı: D gününün kuponları en erken D-1 18:00 TSİ'de (bütün gün 30 saatlik penceredeyken) kurulur. Tekliler kapıdan önce yalnızca kapı açılmadan kilitlenecek maçlar için yayımlanır; böylece kuponların havuzu bölünmez. Yayımlanmış/kilitli kayıtlara dokunulmadı (27–29 Ekim'de mevcut KB/tekli çakışmaları olduğu gibi kalır).

## 27 Ekim 2026 — kopya kayıtların kök çözümü
- Kök neden 1 (erteleme/saat düzeltmesi): maç kimliği tarih içeriyor; kaynak bir maçın tarihini 36 saatten fazla kaydırınca eski kayıt eşleşmiyor ve yeni kimlikle ikinci maç açılıyordu (ör. Manchester City – Brighton 27/28 Ekim, Al Fayha – Al Faisaly 29/31 Ekim). Çözüm: `merge_records` aynı lig + ev + deplasmanın OYNANMAMIŞ kaydını ±10 gün içinde arar ve kimliği korur; eski 'ertelendi' durumu yeni tarihe taşınmaz.
- Kök neden 2 (takım ad kopyası): 'Tranmere' / 'Tranmere Rovers', 'Crewe' / 'Crewe Alexandra', 'Oldham' / 'Oldham Athletic', 'Accrington' / 'Accrington Stanley', 'Partick' / 'Partick Thistle', 'Dunfermline' / 'Dunfermline Athletic' ayrı takım açılıyordu. Çözüm: `TeamRegistry` yalnızca kulüp ekiyle (rovers, athletic, alexandra, stanley, thistle, county, …) ayrılan ve ligde TEK aday olan yazımı aynı takıma bağlar ve eşlemeyi takımın `aliases` alanına kalıcı yazar. 'united' / 'city' bilerek dışarıda: Dundee ≠ Dundee United. Birden çok aday varsa ('Bristol' → City/Rovers) eşleme yapılmaz.
- Mevcut kopyalar `scripts/kopya_birlestir.py --uygula` ile birleştirildi: 81 kopya maç + 6 takım. Silinen her satır `backup_2026_10_20_yanlis_birlesme` (tablo, anahtar, satir) tablosunda; yayımlanmış tahmine bağlı kayıt korunur (Manchester City – Brighton yayımlanan kimlikte kaldı). Oran geçmişi, eksikler, kadrolar, hava, gündem satırları kalıcı kayda taşındı.
- Sparta Praha: bağımsız kaynaklar (UEFA/FIFA maç merkezi, ESPN, BBC, sparta.cz) — Şampiyonlar Ligi 3. ön eleme: Sparta 2–1 Lyon (4 Ağu), Lyon 3–0 Sparta (11 Ağu); Sparta Avrupa Ligi lig aşamasında. Hayalet 'Sparta – Sturm Graz 4 Ağu' kaydı yedeklenip silindi; CL:spartapraha (ön eleme) ve EL:spartapraha ayrı lig kayıtları doğru.

## 27 Ekim 2026 — veri güvenilirliği: kota defteri ve oran zinciri
- Teşhis (canlı): önümüzdeki 72 saatte 178 maçın 79'unda 1X2 oranı vardı. BSD 429 "taster_exhausted" = günlük 7.500 istek kotası öğleden sonra bitiyordu (kök: saatlik iş 200+ maçın her birine her saat eksik + ilk 11 isteği atıyordu; gece sezon işi 1.500+). OddsPapi her gün HTTP 400 veriyordu (kök: istek başına en çok 5 turnuva; biz 9 gönderiyorduk). API-Football günlük 90'lık bütçesi oran sırası gelmeden kadro/yerel işlerde bitiyordu.
- Düzeltmeler: (1) BSD günlük kota defteri (`source_status` 'bsd:kota', UTC günü): her adımdan sonra harcanan yazılır; ağır işler (sezon, geçmiş) saatlik yayın için 2.500 isteği asla harcamaz; saatlik iş payı = kalan / kalan saat × 2; kota bitince BSD o gün denenmez, alanlar sıradaki kaynaktan dolar. (2) Eksik/ilk 11 tazeliği maça uzaklığa göre: ≤ 6 saat her saat, 6–30 saat 3–4 saatte bir, daha uzak 6 saatte bir. (3) OddsPapi 5'erli gruplarla (Pinnacle, 9 büyük lig, günde 2 istek ≈ ayda 60 / 250). (4) API-Football günlük bütçesinin son 30 isteği oranlara ayrıldı. (5) 429 yanıtının gövdesi hata mesajına eklendi (günlük kota mı, saniyelik sınır mı ayırt edilir).
- Oran zinciri (öncelik): The Odds API → API-Football (9 şirket medyanı) → OddsPapi (Pinnacle) → BSD (konsensüs) → football-data.co.uk → diğerleri. Bir kaynak düşerse birleştirme sıradakini kullanır; son alınan oran maç kaydında kalır (önbellek). Oran yoksa analiz modelle sürer (adil oran), yalnızca yayına giren seçim gerçek oran ister.

## 27 Ekim 2026 — öğrenen isabet motoru (meclis/motor.py)
- Gece işinde (geritest adımı) çalışır, insan gerektirmez. Bu sezon biten maçlarda yürüyen pencere Dixon-Coles (yalnızca o haftadan önceki maçlarla) + marjsız ön maç oranı → 1X2, çifte şans, gol A/Ü 1.5/2.5/3.5, KG.
- Öğrenme: pazar grubu başına harman ağırlığı w (log-loss; w ≥ 0.20 — canlı modelin geri testte ölçülemeyen Elo/eksik/ilk 11 girdileri için asgari söz) + izotonik kalibrasyon (PAV). Koruma: yeni parametreler, mevcut parametrelerin uydurulduğu tarihten SONRA oynanan maçlarda (≥ 80 seçim satırı) daha iyi değilse benimsenmez; bu yüzden döngü modeli kötüleştiremez. Lig başına ağırlık için örnek henüz yetersiz (lig başına < 300) — bilinçli olarak tek grup ağırlığı.
- Yayına açık pazarlar otomatik: geri testte ≥ 300 satır VE seçim kuralı o pazarda örneklem dışında söylediği kadar tutuyorsa (isabet ≥ ortalama olasılık − 5 puan, ≥ 40 seçim). İlk çalışma: 1X2, çifte şans, KG, 2.5 gol açık; 3.5 gol (n=66, isabet %45 / beklenen %59) ve 1.5 gol (n=9) kapalı; korner/kart/İY/handikap geçmiş oran derinliği olmadığı için Ortak'ta bilgi olarak kalır. Veri biriktikçe kendiliğinden açılır.
- Seçim kuralının örneklem dışı geri testi (1.200 maç, çapraz uydurma): %50–55 bandı %52,2 (n=318), %55–60 %56,0 (n=361), %60–65 %59,6 (n=366), %65–70 %63,6 (n=44); toplam %56,3 isabet, ortalama oran 1,66, ROI −%7,4 (isabet önceliği değer üretmez — kullanıcı tercihi; Güven Panosu'nda açıkça yazılır).

## 27.10.2026 (gece) — editoryal katman, canlı skor, topluluk motoru
- **Meclis Bülteni** (Ana sayfa) ve **gerekçe kartları** (Defter: her seçim için 3 madde + risk + geri test bandı) yayın işinde veriden yazılır (`meclis/editoryal.py`; `analyses` tablosunda `meclis:bulten:GÜN`). Sayılar analiz yükü, kilitli kayıt ve motor geri testinden; şablon metin.
- **Maç sonrası notlar** ("neden tuttu / yattı": skor, beklenti, şut/xG, kırmızı kart; kuponda bozan ayak) sonuç işinde (`meclis:not:GÜN`).
- **Canlı skor**: `meclis-canli` işi 10 dakikada bir ESPN'in herkese açık skor tablosundan başlamış maçların skorunu/dakikasını yazar (kotasız). Resmî sonuç ve sonuçlandırma bu kaynaktan yapılmaz.
- **Güven Panosu**: geri test ↔ canlı, olasılık bandı ve pazar bazında (n < 20 bant gösterilmez).
- **Motor**: Dixon-Coles↔Elo topluluk ağırlığı gece öğrenilir (korumalı; ilk çalışmada 0.45 korundu: aday 0.00 doğrulamada daha kötü). Lig başına kalibrasyon kancası hazır; bugün hiçbir ligde pazar başına 300 seçim yok (en çok E3: 282) → küresel parametre.
- **Kart pazarı**: hakemin bu sezonki maç başı kart ortalaması lig ortalamasına büzülerek (k=8) beklentiye çarpan olarak girer (0.75–1.30). Korner/kart pazarları geri test derinliği oluşana kadar yayına girmez.
- **Kupa + piyasa oranı yok**: farklı lig seviyelerinde güç farkı yarıya büzülür (Copa del Rey'de %99'luk 1X2 görülmüştü).

## 28.10 — Supabase egress kotası (402) ve kalıcı egress diyeti

27.10 ~22:48 UTC'de proje Free plan 5 GB egress sınırını aştı ve kısıtlandı (HTTP 402). Nedenler: her saatlik yayın
bütün sezonun `matches` satırlarını (ağır `sources` jsonb dahil, ~34 MB) iki kez, `match_stats`'ı, `teams`'i birkaç kez,
oyuncu maçlarını takım takım okuyordu; her upsert yazdığı satırları geri döndürüyordu (`returning=representation`);
canlı skor 10 dakikada bir maç satırlarını okuyup yazıyordu; site her ziyaretçide ~0.5–1.5 MB okuyordu.

- **Ayna** (`meclis/ayna.py`): matches, match_stats, teams, lineups, players, player_matches yerel kopyadan sorgulanır
  (GitHub Actions önbelleği `.ayna`). Artımlı eşitleme iki aşamalı: önce yalnızca anahtar + `updated_at`, sonra yalnız
  gerçekten değişen satırlar. 14 günde bir tam yenileme. Değişmeyen satır yazılmaz; bütün yazmalar `returning=minimal`.
- **Kilitli analizler** bir kez okunur, aynada saklanır (kilitli maç analizi değişmez).
- **Statik site verisi** (`meclis/statik.py`, `veri` dalı, tek commit): defter, editoryal, gün dosyaları (maç + analiz +
  tarama), gün sayımları, takım sezon satırları. Supabase yeniden okunmadan üretilir. Site önce bunları okur; yoksa ya da
  bayatsa Supabase'e düşer.
- **Canlı skor** Supabase'e hiç dokunmaz: gün dosyasından maçları okur, `canli.json` yazar.
- **Egress bütçesi** (`meclis/egress.py`): her iş baytları ölçer, `is:<iş>` mesajına (v_sistem_durumu.son_mesaj) ve aylık
  deftere (`source_status 'egress:ay'`) yazar. %70'te vazgeçilebilir adımlar, %95'te yayın/sonuç dışındaki adımlar atlanır
  (`MECLIS_EGRESS_AY_MB`, varsayılan 2500).
- **402'de zarif davranış**: ortak iş akışı önce yoklar; 402'de iş yeşil biter, tek bir "Supabase erişimi kısıtlı (402)"
  issue açılır (yorum yok), erişim dönünce ilk iş issue'yu kapatır. Hata issue'larına 24 saatte en fazla bir yorum.
- **Yedek koruması**: eksik dışa aktarım `backups` dalını artık silmez (28.10 01:34'te 402 sırasında boş yedek itilmişti;
  önceki tam yedek `d32255b` commit'inde duruyor).
