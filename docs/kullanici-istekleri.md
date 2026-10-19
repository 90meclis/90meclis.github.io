# 90 Meclis — Kullanıcının kendi sözleriyle istekleri

Hazırlanma: 20.10.2026. Amaç: kullanıcının söylediklerini kendi kelimeleriyle kayda geçirmek, bizim
yorumumuzu yanına yazmak ve özetlerimizin nerede saptığını göstermek. Kural: **kullanıcının sözü özetimizden
üstündür; sonra söylenen önce söyleneni geçersiz kılar.**

> **Kapsam (güncellendi 20.10.2026):** Konuşmanın tam kullanıcı dökümü (`t0u`–`t36u`) artık okundu. §1.0'da ilk brifler
> (`t0u`–`t5u`, `t16u`) aynen yer alıyor. `t6u`–`t15u` ve `t19u`–`t20u` SQL çalıştırma ve sesli arama sorunları gibi süreç
> mesajları; gereksinim içermiyor. §3'teki "dolaylı izler" artık doğrudan alıntıyla doğrulanabilir.

Etiketler: **[SAPMA]** özetimiz kullanıcının sözüyle çelişiyor · **[EKLEME]** kullanıcının hiç istemediği bir şeyi
kural gibi yazmışız · **[BELİRSİZ]** söz iki türlü okunabiliyor · **[UYUMLU]**.

---

## 1. Kullanıcı mesajları (aynen) ve yorumumuz

### 1.0 İlk brifler (aynen)

#### t0u
> Sana ortak demek istiyorum

Yorum: Kullanıcı bizi projenin ortağı olarak görüyor. Kararları onun yerine verip işi bitirmemiz bekleniyor (t11u, t15u ve t30u ile tutarlı).

#### t1u
> [Kullanıcının] 90 Meclis projesi için araştırma görevi. Amaç: piyasadaki futbol tahmin/analiz sitelerini ve uygulamalarını gözlemleyip incelemek, ne yaptıklarını, ne yapamadıklarını bulmak ve 90 Meclis'in farklı bakış açısıyla (her şeyin tek masada olduğu, kazanç-kayıp şeffaf kayıt, veri laboratuvarı, maç merkezi, tahmin botu, tahmin arşivi) neler yapılabileceğini çıkarmak.
>
> Araştırılacak konular:
> 1. Popüler futbol tahmin siteleri ve uygulamaları (Türk ve uluslararası): hangi özellikleri var, nasıl çalışıyorlar, arayüzleri nasıl, hangi verileri gösteriyorlar.
> 2. Maç analizi siteleri: maç merkezi tarzı sayfalar, maça tıklayınca ne gösteriyorlar (kadrolar, form, istatistikler, son karşılaşmalar).
> 3. Veri/istatistik siteleri: hangi pazarlar var (korner, ilk yarı gol, kart, isabetli şut, kale vuruşu), takım bazlı ligler/sıralamalar nasıl tutuluyor.
> 4. Tahmin arşivi/kayıt sistemleri: sonuçların şeffaf gösterildiği, kazanç-kayıp kayıtlı sistemler var mı.
> 5. Ücretsiz/açık kaynak araçlar: Streamlit, Supabase, GitHub Pages gibi araçlarla neler yapılabilir, bunların sınırları neler.
> 6. 90 Meclis'in farklı olabileceği noktalar: bu siteler ne yapmıyor ki biz yapabiliriz?
>
> Çıktı olarak: her kategoride 3-5 örnek site/uygulama, her birinin güçlü ve zayıf yönleri, ve 90 Meclis için alınabilecek fikirler listesi. Türkçe rapor olarak döndür.

Yorum: Pazar araştırması. 90 Meclis'in farkı şunlar: her şey tek masada, kazanç-kayıp şeffaf kayıt, veri laboratuvarı, maç merkezi, tahmin botu, tahmin arşivi. Bölüm adlarının kaynağı bu brif.

#### t2u
> 90 Meclis tahmin uygulamasının ilk sürümünü kur: Streamlit tabanlı tek uygulama, GitHub repo 90-meclis (yoksa oluştur), Supabase bağlantısı (env değişkenleriyle: SUPABASE_URL, SUPABASE_KEY). Uygulama şu altı bölümü içersin: (1) Maç Merkezi — maça tıklayınca o maçın tüm verisi tek ekranda: kadrolar, sakatlıklar, form, istatistikler, son karşılaşmalar, hava durumu; sistemin senaryoları ve yaklaşımı da yazılsın; maç konuşsun, kullanıcıya "bunu oyna" hissi versin. (2) Tahmin Botu — bülteni tarar, maçları eler, her pazarı inceler (skor, gol, korner, kart, isabetli şut, kale vuruşu), senaryolar kurar, tahminleri maçtan önce kayda düşer; veri eksikse maç elenmez, tahmin ertelenir; sakatlıklar ağırlıklı okunur (kilit isim mi değil mi). (3) Tahmin Arşivi — etiketli tahminler: günün kararı (2-3 maçlık kupon, oran bandı 2.30-4.00), meclis görüşü (tekli bahisler), karar birliği (5+ meclis görüşü varsa en güvendiği 2-3 maçtan kombinasyon); her tahminin durumu: bekliyor, başladı, kazandı, kaybetti, iade. (4) Veri Laboratuvarı — pazar ligleri: korner, ilk yarı gol, KG var/yok, kart; takım serileri maç maç (ortalama değil, maç bazlı şut sayıları vb.). (5) Gündem Masası — her sabah gündem taranır: transferler, sakatlık haberleri, teknik direktör kararları; o günün maçlarına bağlanır. (6) Güven Panosu — arşivin herkese açık yüzü: haftalık kayıt, başarı oranı, hangi pazarlarda tuttuğu. Veri kaynakları birleşik çalışsın: birden fazla kaynak aynı havuzda, eksik alan diğerinden tamamlanır, maç asla elenmez. Veri eksikliği bahane olmasın — bulmaya çalış, bulamazsan tahmin ertelenir. Tüm kararlar kilitli: adım adım gitme yok, her adımda "en iyisi bu mu?" diye sorulur. Uygulama Türkçe olsun. Bittiğinde ne kurulduğunu ve nasıl çalıştırıldığını raporla.

Yorum: **Ürünün ana tarifi budur.**
- Altı bölüm ve içerikleri kullanıcının.
- **Maç Merkezi:** maça tıklanınca tek ekranda kadrolar, sakatlıklar, form, istatistikler, son karşılaşmalar ve hava durumu gösterilir; sistemin senaryoları ve yaklaşımı yazılır. **"Maç konuşsun, kullanıcıya 'bunu oyna' hissi versin."** Yayımlanmış bir kararı olan maç sayfası bu yüzden kararı net ve kararlı bir sesle sunar ("Meclis'in kararı" bloğu, gerekçe ve senaryolarla). 6deba6c'de bahse yönlendiren ifadeleri silmiştik. Bu, kullanıcının sözüne aykırıydı ve geri alındı. Yayımlanmamış maçta karar uydurulmaz.
- **Kuponlar:** Günün Kararı 2-3 maç, oran bandı 2.30–4.00. Meclis Görüşü tekli. Karar Birliği, 5+ Meclis Görüşü varsa en güvenilen 2-3 maçtan kurulur.
- **Durumlar:** bekliyor, başladı, kazandı, kaybetti, iade.
- **Güven Panosu:** haftalık kayıt, başarı oranı, hangi pazarlarda tuttuğu.
- **Veri:** birleşik havuz kullanılır, maç asla elenmez. "Veri eksikse tahmin ertelenir" cümlesi t32u ile güncellendi: bahane yok, veri güçlendirilir.
- "Tüm kararlar kilitli": adım adım gitme yok, her adımda "en iyisi bu mu?" diye sorulur.
- **Not:** v1 brifinde 18+ / garanti notu yok. Bunu biz ekledik ve küçük bir not olarak tutuyoruz.

#### t3u
> 90 Meclis (modern futbol medya markası ve tahmin takip uygulaması) için veri kaynakları araştırması ve birleştirme planı. Görev: (1) Maç verisi, oranlar, kadrolar, sakatlıklar, istatistikler (korner, ilk yarı gol, KG var/yok, isabetli şut, kale vuruşu, kartlar) için en iyi ücretsiz/ücretli API ve veri kaynaklarını araştır — WhoScored, Flashscore, Forebet, Windrawwin, WoodStats ve benzeri rakipler dahil. (2) Her maçın verisini eksiksiz alabileceğimiz lider kaynakları belirle. (3) Kaynakların birleşik çalışması için mimari öner: 5-50 kaynak tek havuzda, eksik alan diğer kaynaktan tamamlanır, maç asla elenmez, veri yok diye tahmin yapılmaz ama veri bulunmaya çalışılır. (4) Sakatlıkların ağırlıklı okunması: kilit isim mi, kaç maç oynadı, olmadan takım yapamaz mı — ham liste değil. (5) Rakiplerin koyduğu bölüm isimlerini ve yapılarını incele, 90 Meclis için elit ama Türkçe kaçmayan isim önerileri çıkar. Sonuçları Türkçe rapor olarak döndür: kaynak listesi, mimari, isim önerileri, rakiplerin zayıf yanları.

Yorum: Veri kaynakları ve mimari: 5–50 kaynak tek havuzda, eksik alan başka kaynaktan tamamlanır. Sakatlık ağırlıklı okunur (kilit isim mi, kaç maç oynadı). Bölüm isimleri "elit ama Türkçe kaçmayan" olmalı.

#### t4u
> Research the football statistics website FoodStats (foodstats.com — NOT WoodStats, the user corrected: it's Food, not Wood). Find out: 1) What the site is and what it offers (stats, predictions, data). 2) What data it provides for football matches (leagues covered, stats types, odds, predictions). 3) Whether it has a free plan or API access, and what limits. 4) How it compares to WhoScored, Flashscore, Forebet, Windrawwin — what it does better, what it lacks. 5) Anything useful for a Turkish football prediction/analysis site (90 Meclis) that could be a data source or inspiration. Return a concise report in Turkish with findings and whether FoodStats is worth using as a data source.

Yorum: Kullanıcı düzeltmesi: site "WoodStats" değil, **FoodStats (foodstats.com)**. Veri kaynağı adayı olarak araştırıldı.

#### t5u
> 90 Meclis uygulaması için Supabase veritabanı şeması hazırla. Kullanıcının Supabase hesabında 90 Meclis adında bir proje var (Europe/İrlanda bölgesi, ücretsiz plan). Şunları yap:
>
> 1) matches tablosu: maç tarihi, ev sahibi takım, deplasman takımı, lig, skor, durum (gelecek/canlı/bitti), maç kimliği, veri kaynakları (hangi kaynaklardan veri geldiği), eksik alanlar listesi.
> 2) predictions tablosu: maç kimliği, tahmin (pazar, oran, seçim), etiket (günün kararı / meclis görüşü / karar birliği), botun senaryo notu, güven skoru, sonuç (kazandı/kaybetti/bekliyor), kayıt zamanı.
> 3) injuries tablosu: oyuncu, takım, sakatlık durumu, sezon başından beri kaç maç oynadı, kaç maçta kilit isimdi, gol katkısı, defans katkısı, ağırlık puanı (kilit isim mi değil mi).
> 4) trends tablosu: takım, pazar (korner, KG var/yok, ilk yarı gol, şut sayısı), seri (kaç maçtır), maç maç değerler (ortalama değil, her maçın kendi değeri).
> 5) agenda tablosu: gündem haberi, hangi maça bağlandığı, etki notu.
> 6) sources tablosu: veri kaynağı adı, API anahtarı nerede saklanıyor, günlük istek limiti, hangi alanları dolduruyor.
>
> Tüm tablolar için SQL CREATE TABLE komutlarını hazırla. API-Football anahtarı dahil hiçbir gizli bilgiyi koda gömme — Supabase'in gizli ayarlarında (vault/secrets) saklanacak şekilde talimat ver. Türkçe rapor olarak özetle: hangi tablo ne işe yarar, nasıl bağlanır.

Yorum: Altı tablo (matches, predictions, injuries, trends, agenda, sources) ve alanları kullanıcının tanımı. trends tablosunda "maç maç değerler (ortalama değil)" isteniyor. Gizli anahtarlar koda gömülmez.

#### t16u
> Bak kaynak sınırı yok isteği bağlı deme ekle ekleyebildigimizi çünkü veri sıkıntısı çekmeye lim

Yorum (yarım kalmış sesli mesaj): "Kaynak sınırı yok, isteğe bağlı deme, ekleyebildiğimizi ekle; çünkü veri sıkıntısı çekmeyelim." Hiçbir kaynak "isteğe bağlı" sayılmaz (t32u: "Hiçbir kaynak isteğe bağlı sayılmaz").

### 1.1 Yüzeyler: site ve Streamlit (kararımız, kullanıcının sözüne dayanır)
- **Web sitesi (GitHub Pages) 90 Meclis'in herkese açık yüzüdür.** t29u: "başka misafir kullanıcılar da olacak, daha profesyonel bir şeyler yapamaz mıydık… ben bu yüzden Streamlit kullanmak istememiştim."
- **Streamlit, çalışan ikincil bir uygulama olarak kalır.** t29u: "ama neyse çalışan bir şeyi yapalım da çok önemli değil." Bölümleri sitedekilerle aynı tanımları kullanır (aynı K/Z hesabı). Bot işlemleri yalnızca yönetici anahtarıyla (ADMIN_TOKEN) görünür.
- **t25u'yu misafir/herkese açık erişim olarak okuyoruz:** "herkes açık kalabilir… kullanıcı tarafı olsun, misafir tarafı olsun." Ziyaretçi giriş yapmadan her şeyi görür. Ayrı bir üyelik sistemi kurulmadı.

### 1.2 Sonraki mesajlar (aynen) ve yorumumuz

### t20s4 — veri kaynağı sorusuna yanıt
> "Önce ücretsiz kaynakları dene"

Yorum: Sakatlık ve ilk 11 verisi için önce ücretsiz kaynaklar denenecek; ücretli plan ancak sonra konuşulur.
**[UYUMLU]** BSD, API-Football ücretsiz planı ve Wikipedia eklendi. Ama football-data.org, The Odds API, OddsPapi ve
SportDevs'in ücretsiz kayıtları hâlâ yapılmadı (bkz. `docs/duzeltmeler.md` D3).

### t21u
> "Eee veri konusunda ne? Çok güçlü olmadığımız gerektiğini hatırlıyorsun. Ve Gerekmiyo zö yap. Tam hiçbir şey görmüyorum. Bunu da biliyorsun. Yani her şeyi. Halletme havuzda çalışmıyo."

Yorum (sesli yazım düzeltilmiş): "Veride **çok güçlü olmamız** gerektiğini hatırlıyorsun. **Gerekeni sen yap.**
Ben (uygulamada) hiçbir şey görmüyorum. Her şeyi hallet, **havuz çalışmıyor**." Üç istek var: veri güçlü olmalı,
işi kullanıcıya yıkmadan biz yapalım, uygulama görünür olsun. **[UYUMLU]**

### t22u – t24u (giriş işleri)
> "Şifrem yok galiba mail ile girmeyi dene şifre istemeyi dene [e-posta adresi]" ·
> "Tamam hallettim gönder" · "Citri-Mit. Eee hesabım zaten. Getayp hesabımdı. Bağlı."

Yorum: Streamlit hesabı zaten GitHub'a bağlı. Gereksinim değil, süreç bilgisi.

### t25u
> "Sorry, so this is a little bit. Herkes açıktık. Bu yüzden herkes açık kalabilir. Yani onun ayarlamasını yapamam. Eee, nası diyim? Yani kullanıcı tarafı olsun. Misafir tarafı olsun ya."

Yorum: "(Repo) herkese açık kalabilir, o ayarı ben yapamam." Ardından **"kullanıcı tarafı olsun, misafir tarafı
olsun"**. **[BELİRSİZ]** İki okuma var: (a) site misafirlere açık olsun ("kullanıcı tarafı = misafir tarafı");
(b) iki ayrı yüz olsun: kullanıcının kendi tarafı ve misafir tarafı. Biz yalnızca (a)'yı uyguladık,
yönetimi de gizli bir sayfaya koyduk. **Geçerli okuma (§1.1):** misafir/herkese açık erişim.

### t26u – t28u (Streamlit kurulumu)
> "URL adını değiştirelim mi" · "Yav" · "Giriş de ki URL mi yapistircam bahsettigin keyde attığım mı"

Yorum: Adım sayısından yoruldu ("Yav"). t30u'daki "sen yap" isteğinin habercisi.

### t29u
> "Neden sadece seçili ligler var ve inceleme yapmadım ayrıca fazlası ile veri ve data api kaynaklarımız olması gerekiyordu bak unutma veri sıkıntısı çekmek istemiyorum demiştim ve hani başka misafir kullanıcılar da olacak daha profesyonel bir şeyler yapamaz mıydık ve ben bu yüzden stremlit kullanmak istememiştim ama neyse çalışan bir şeyi yapalım da çok önemli değil ayrıca bir şey sormak istiyorum grok un kendi uygulama ve site yapma şeyini neden kullanmadık o işimize yaramaz mıydı"

Yorum:
- Yalnızca seçili 6 lig görünüyordu. Kullanıcı **tüm ligleri** istiyor. **[UYUMLU]** Lig sayısı artık 21; Streamlit'te varsayılan seçim hepsi.
- "**Fazlasıyla veri ve API kaynağımız olması gerekiyordu… veri sıkıntısı çekmek istemiyorum demiştim**": en az iki kez söylenmiş (öncesi de var: "demiştim").
- "**Başka misafir kullanıcılar da olacak, daha profesyonel bir şey… bu yüzden Streamlit kullanmak istememiştim**": Streamlit'i baştan istememiş. **[SAPMA]** v1 Streamlit olarak kurulmuş, hâlâ `90meclis.streamlit.app` adresinde Streamlit görünümüyle açık. Web sitesi sonradan başladı.
- "Çalışan bir şeyi yapalım da çok önemli değil": geçici çözüm kabul.
- "inceleme yapmadım": uygulamayı henüz incelemedi; gereksinim değil.

### t30u
> "Ya bak, ne yapmamız gerekiyorsa yap. Yani. Yani ben artık. Nasıl söyleyeyim sana. Her şeyi hazırla ya, ben sadece her şeyi hazırlamanı istiyorum. Yani ne yapılması gerekiyorsa Ne bulması gerekiyorsa yap ya."

Yorum: Her şeyi biz hazırlayacağız ve bulacağız. Kullanıcıya yalnızca kendisinin yapması şart olan işler sorulacak.
**[UYUMLU]** (süreç kuralı)

### t31u
> "İstediğimiz uygulamayı siteyi ne yapmak istediğimizi bütün konuştuklarımizi nasıl bir uygulama istediğimizi tam anlamı ile bı tarif eder misin ayriyetten grok da bir işlem deneyeceğim"

Yorum: Konuştuğumuz her şeyin tam bir tarifini istiyor. Grok'ta denemek için istedi. (Ana ajan sonra Grok sürümüne gerek olmadığını iletti.)

### t32u — ilk tarifi sesli okuyup itiraz ediyor
> "She no more positive. Şeyler de biraz karışıklık var bu arada. Şimdi mesela. Varsayalım olarak en yakın. Hindi government. To arrive liquid reservoir. The end of the cargo. Kalderim, hayır böyle bir şey yok. Yani oradan çıkarıyoruz, veri yeterli değilse diye bir bahane üretmeyeceğiz. Verilerim güçlendireceğiz. Her maçı veriyor olacak. Böyle bir karar bekliyor deyip bir durum da olmuyor. Siz hiç de karar vermedik. Hayır, öyle. Mevzu on beş dakika kala mı? Hayır. Biz bu maçta saatler öncesinde paylaşacağız. Saatler öncesi de bunun, bunların hazırlanması, hazırlanması gerekiyor yani. Harun burada sürekli çalışabilecek bir şey olması lazım. Takip değiştirilmez, defter. Tüm geçmiş tam ortamı değil, maç maç değerler gösterilir. Neyse güven panseye fok kral tamam. İki üç maçlık toplam. Beş ve ya daha fazla değil. Başladık kazandık kaybettik. Yerel sınırı yok. Hiçbir kaynak isteye bağlı sayılmaz. Kullanabiliyor. Her kaynak beş lira elli lirası. Çizgansız kabul edemez. Tamam. Birleştirilir. Bu kadar tek sıkılandırırım dolu. Takım cismi röksüş tamam. Ama veri bulmak için her yol nedir? Evet. Yani biz kadro çok da takılmamalıyız. Onlar iki saat, bir saat öncesinden belki de sayıyı beklemeyeceğiz demek ki. Senin kadroların. Tam iyi. 11 çıkarabilirsin kendine göre tahminler. Bilmiyorsan bizim komşumuz her şeyi önce tekrar düşün. Ne istediğimizi bil. Şey yap yani bil yani. Beyan bu. Buraya gelip düzen. Tek adım."

Yorum (tarifi madde madde okuyup yorum yapıyor):
- "Varsayılan olarak en yakın (maç gününü açar)" → okuma. Yorum yok.
- "**Karar Bekliyor? Hayır, böyle bir şey yok.** Oradan çıkarıyoruz. **Veri yeterli değilse diye bir bahane üretmeyeceğiz. Verilerimizi güçlendireceğiz.**" → Karar Bekliyor kalkar, veri güçlendirilir.
- "**Her maçı veriyor olacak**" → t33u'ya göre "her maça tahmin" demek değil. **Her maçın verisi olacak** şeklinde okunmalı. **[SAPMA]** Ana ajan bunu ilk başta "her maça tahmin verilecek" diye uyguladı, t33u'da düzeltildi.
- "**Karar Verilmedi? Hayır.** **On beş dakika kala mı? Hayır. Biz saatler öncesinde paylaşacağız.** Saatler öncesinde hazırlanması gerekiyor." → T-15 yok. Yayın saatler önce. Hazırlık önceden yapılır.
- "(Yani) burada **sürekli çalışabilecek bir şey** olması lazım" → kesintisiz çalışan bir sistem.
- "(Tahmin Arşivi) değiştirilmez defter" → okuma ve onay.
- "**(Trendler) ortalama değil, maç maç değerler gösterilir**" → okuma ve onay.
- "Güven Panosu… tamam" → onay.
- "İki üç maçlık toplam (oran). **Beş veya daha fazla değil.**" → Karar Birliği'nin "5 veya daha fazla tekli" koşuluna itiraz gibi görünüyor. Ama t33u'da "kuponlar için bir şey demedim, onları değiştirme" dedi. **Sonraki söz geçerli: kupon kuralları ilk haliyle kalır.**
- "Başladı, kazandı, kaybetti" → durumlar onay.
- "**Kaynak sınırı yok. Hiçbir kaynak isteğe bağlı sayılmaz.** Kullanılabilen her kaynak (5 ile 50 arası). **Veri sıkıntısı kabul edilemez.** Tamam. Birleştirilir. Tek havuzda (dolu). Takım (ve oyuncu) isimleri eşleşir, tamam." → onay.
- "**Ama veri bulmak için her yol nedir?** Evet." → her yol denenecek. Hangi yollar olduğu soruluyor.
- "**Kadroya çok da takılmamalıyız.** Onlar (resmî ilk 11) iki saat, bir saat önceden; **beklemeyeceğiz.** Senin kadroların… **11 çıkarabilirsin, kendine göre tahminler.**" → resmî ilk 11 beklenmez, kendi tahmini 11'imiz olur.
- "Bilmiyorsan bizim konuşmamızı, her şeyi önce tekrar düşün. **Ne istediğimizi bil.**" → konuşmaları baştan okuyup içselleştir.

### t33u
> "Bak şimdi her maça tahmin mi verelecekti ben ondan mı bahsediyorum sana bak neden konuştuğumuz şeyleri hatırlamıyorsun ve geçmiş sezon değil bu sezon genelinde çalışacaktık bizim tahmin anlayışımızı hatırla istersen ve gerekirse tahminler her gece yenilensin yani kuponlar için bir şey demedim onları değiştirme"

Yorum:
- **Her maça tahmin verilmez.** Daha önce konuşulmuş bir "tahmin anlayışımız" var. Bu anlayış (v1 talimatında) okunamadı; ana ajan "yalnızca değerli seçimler" diye özetledi.
- "**Geçmiş sezon değil, bu sezon genelinde çalışacaktık.**" **[SAPMA]** Ana ajan buna rağmen "geçmiş sezonlar küçük bir destek ve kontrol olarak kullanılıyor" diye yazdı. Kodda da geçmiş sezon 0,3 ağırlıkla modele giriyor. Her gece 2022–2024 sezonları dolduruluyor (16–17 gün süren iş). Sakatlık önemi 2024 sezonundan hesaplanıyor. Kullanıcı bunların hiçbirini istemedi; tersini söyledi.
- "**Gerekirse tahminler her gece yenilensin.**" → yayımlanmamış tahmin adayları her gece yeniden hesaplanır. **[UYUMLU]** (`meclis.yml` her 2 saatte, gece dahil.)
- "**Kuponlar için bir şey demedim, onları değiştirme.**" → Günün Kararı, Meclis Görüşü ve Karar Birliği kuralları ilk haliyle kalır.

### t34u
> "Bak her şeyi karıştırma konuştuğumuz şeyleri hatırla Allah aşkına"

### t35u
> "Onla mi ugrasayayim Allah aşkına ve bazı şeyleri seninle tekrar tekrar konuşmak istemiyorum"

Yorum: Aynı şeyleri tekrar sormamalıyız. Düzeltmeyi kullanıcıya yaptırmamalıyız (tam metni biz vermeliyiz).

### t36u
> "Bak bu tarife birden çok eksik var gibi geldi ama ben beni doğru anladığını ne istediğimizi bildiğini düşünüyordum hala düşünüyorum beni yanıltma olması gerekeni ve istediğimiz şeyi yap"

Yorum: Tarifte birden çok eksik var. Kullanıcı bize güveniyor. **Yanıltmayalım, olması gerekeni yapalım.**

### Ekran görüntüleri (kullanıcının gönderdiği)
- `90meclis.streamlit.app` Maç Merkezi: "🔑 Tanımsız anahtarlar: FOOTBALL_DATA_TOKEN, API_FOOTBALL_KEY, ODDS_API_KEY…" yazısı ve yalnızca 6 lig seçili. 20.10.2026 için "Bu tarihte seçili liglerde maç bulunamadı" diyor. → t29u'daki şikâyetin kaynağı.
- Supabase panosu: proje adı `90meclis`, Free, Edge Functions → Secrets (Vault/secrets kullanımı).

---

## 2. Özetlerimiz ile kullanıcının sözü arasındaki farklar (önem sırasıyla)

| # | Bizim özet/kural (nerede) | Kullanıcının sözü | Durum |
|---|---|---|---|
| S1 | "Geçmiş sezonlar küçük bir destek/kontrol" (sohbetteki tarif); `docs/tarif.md` TA-5 "geçmiş sezon 0,3 önsel"; "eski sezonlar her gece arşive ekleniyor" (sohbet) | "**geçmiş sezon değil bu sezon genelinde çalışacaktık**" (t33u) | **SAPMA**: geçmiş sezon kullanımı istenmemiş |
| S2 | İlk tarif: "Her maç tahmin alır, istisna yok" | "her maça tahmin mi verilecekti ben ondan mı bahsediyorum" (t33u) | Düzeltildi. Kodda da yalnızca değer seçimi yayımlanıyor |
| S3 | Veri kaynakları raporu ve ilk kod: "Karar Bekliyor / Karar Verilmedi / T-15" | "Karar Bekliyor? hayır böyle bir şey yok… on beş dakika kala mı? Hayır" (t32u) | Kodda kaldırıldı; şema, belge ve testte duruyor |
| S4 | Kupon kuralını "2-3 maçlık kombine, 5+ şartı kalktı" diye değiştirdik (sohbet, t32u sonrası) | "kuponlar için bir şey demedim onları değiştirme" (t33u) | Geri alındı. Kural ilk haliyle |
| S5 | Uygulama Streamlit ile kuruldu ve misafire Streamlit açık (artık: site ana yüz, Streamlit ikincil, §1.1) | "ben bu yüzden stremlit kullanmak istememiştim… başka misafir kullanıcılar da olacak daha profesyonel" (t29u) | **SAPMA (kısmen giderildi)**: site yapıldı, Streamlit hâlâ açık |
| S6 | Yalnızca misafir yüzü + gizli yönetim sayfası | "kullanıcı tarafı olsun. Misafir tarafı olsun" (t25u) | **BELİRSİZ**: ayrı kullanıcı tarafı istenmiş olabilir |
| S7 | "Her maçı veriyor olacak" → "her maça tahmin" | t33u ile düzeltildi: kastedilen veri | Belgelerde "her maçın verisi eksiksiz olacak" olarak yazılmalı |
| S8 | Değer eşikleri (edge ≥ %3, p ≥ 0,40, oran ≤ 3,20; oransızda 0,72–0,86), "maç başına tek seçim", "adil oran" seçimleri | Kullanıcı bu sayıları okuduğumuz kısımda söylemedi. "Bizim tahmin anlayışımız" v1'de olabilir | **EKLEME / doğrulanamadı**: v1 talimatıyla karşılaştırılmalı |
| S9 | En az 3 saat önce yayın | "saatler öncesinde paylaşacağız" (t32u) | Uyumlu sayılır. 3 saat alt sınırı bizim seçimimiz |
| S10 | `docs/tarif.md` yol haritası: "Bot vs kullanıcı vs topluluk", "Oybirliği/Oyçokluğu/Şerhli", "Tutanak/Sicil" ad önerileri | Kullanıcı bunları istemedi; bölüm ve etiket adları kullanıcının | **EKLEME**: bizim önerimiz olarak ayrıldı |
| S11 | Ana sayfa içeriği ("dünün kararları" vb.), tasarım paleti, SEO | Kullanıcı "profesyonel" dedi, detay vermedi | Bizim tasarımımız. Kural değil, öneri |
| S12 | "18+ / garanti değildir" notu; 6deba6c'de "bunu oyna" türü ifadelerin silinmesi | v1 (t2u): "maç konuşsun, kullanıcıya 'bunu oyna' hissi versin". 18+ notu v1'de yok | **SAPMA giderildi**: yayımlanmış kararda kararlı ses geri geldi. Küçük 18+ notu bizim eklememiz olarak kalıyor |

## 3. Okunamayan önceki brifler — dolaylı izler
- `supabase/schema.sql` başlığı ve kullanıcının eklediği `.sql` dosyası: "Ana tablolar (**kullanıcı tanımı**): matches, predictions, injuries, trends, agenda, sources". Altı tablo kullanıcıdan geliyor. `sources` tablosunda anahtarın değil yerinin tutulması da kullanıcı kuralı.
- Araştırma raporu: altı sütun "Tek Masa, Şeffaf Kâr/Zarar, Veri Lab, Maç Merkezi, Tahmin Botu, Tahmin Arşivi". Etiketler "Günün Kararı, Meclis Görüşü, Karar Birliği" kullanıcının "mevcut ad"ları. "WoodStats" düzeltmesi kullanıcıdan "FoodStats (foodstats.com)" olarak geldi.
- Veri raporu başlığı: "modern futbol medya markası ve tahmin takip uygulaması"; "5–50 kaynaklı veri havuzu"; ağırlıklı sakatlık okuması.
