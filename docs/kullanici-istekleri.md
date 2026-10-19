# 90 Meclis — Kullanıcının kendi sözleriyle istekleri

Hazırlanma: 20.10.2026. Amaç: kullanıcının (Ebraar) söylediklerini kendi kelimeleriyle kayda geçirmek, bizim
yorumumuzu yanına yazmak ve özetlerimizin nerede saptığını göstermek. Kural: **kullanıcının sözü özetimizden
üstündür; sonra söylenen önce söyleneni geçersiz kılar.**

> **Kapsam sınırı (önemli):** Bu belgeyi yazan alt ajanın ReadTranscript aracına erişimi yoktu (`cursor` ad alanı
> bulunamadı). Bu yüzden konuşmanın baştan sonuna dökümü okunamadı. Aşağıdaki alıntılar, devralınan konuşmada
> görünen kullanıcı mesajlarıdır (`t20s4` → `t36u`). Mesajların saat damgası bu görünümde yoktu, bu yüzden tur
> kimliği kullanıldı (hepsi 19–20.10.2026 gecesi). İlk sürüm (v1) yapım talimatı, pazar araştırması, veri kaynakları
> ve Supabase şeması brifleri ile önceki widget yanıtları **okunamadı**. Bu briflerden yalnızca dolaylı izler
> kullanıldı (§3). Ana ajanın dökümü okuyup §1'i tamamlaması gerekiyor.

Etiketler: **[SAPMA]** özetimiz kullanıcının sözüyle çelişiyor · **[EKLEME]** kullanıcının hiç istemediği bir şeyi
kural gibi yazmışız · **[BELİRSİZ]** söz iki türlü okunabiliyor · **[UYUMLU]**.

---

## 1. Kullanıcı mesajları (aynen) ve yorumumuz

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
> "Şifrem yok galiba mail ile girmeyi dene şifre istemeyi dene ebrarmutlu3434@gmail.com" ·
> "Tamam hallettim gönder" · "Citri-Mit. Eee hesabım zaten. Getayp hesabımdı. Bağlı."

Yorum: Streamlit hesabı zaten GitHub'a bağlı. Gereksinim değil, süreç bilgisi.

### t25u
> "Sorry, so this is a little bit. Herkes açıktık. Bu yüzden herkes açık kalabilir. Yani onun ayarlamasını yapamam. Eee, nası diyim? Yani kullanıcı tarafı olsun. Misafir tarafı olsun ya."

Yorum: "(Repo) herkese açık kalabilir, o ayarı ben yapamam." Ardından **"kullanıcı tarafı olsun, misafir tarafı
olsun"**. **[BELİRSİZ]** İki okuma var: (a) site misafirlere açık olsun ("kullanıcı tarafı = misafir tarafı");
(b) iki ayrı yüz olsun: kullanıcının (Ebraar'ın) kendi tarafı ve misafir tarafı. Biz yalnızca (a)'yı uyguladık,
yönetimi de gizli bir sayfaya koyduk. Kullanıcıya sorulmalı (`docs/tarif.md` A5).

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
| S5 | Uygulama Streamlit ile kuruldu ve misafire Streamlit açık | "ben bu yüzden stremlit kullanmak istememiştim… başka misafir kullanıcılar da olacak daha profesyonel" (t29u) | **SAPMA (kısmen giderildi)**: site yapıldı, Streamlit hâlâ açık |
| S6 | Yalnızca misafir yüzü + gizli yönetim sayfası | "kullanıcı tarafı olsun. Misafir tarafı olsun" (t25u) | **BELİRSİZ**: ayrı kullanıcı tarafı istenmiş olabilir |
| S7 | "Her maçı veriyor olacak" → "her maça tahmin" | t33u ile düzeltildi: kastedilen veri | Belgelerde "her maçın verisi eksiksiz olacak" olarak yazılmalı |
| S8 | Değer eşikleri (edge ≥ %3, p ≥ 0,40, oran ≤ 3,20; oransızda 0,72–0,86), "maç başına tek seçim", "adil oran" seçimleri | Kullanıcı bu sayıları okuduğumuz kısımda söylemedi. "Bizim tahmin anlayışımız" v1'de olabilir | **EKLEME / doğrulanamadı**: v1 talimatıyla karşılaştırılmalı |
| S9 | En az 3 saat önce yayın | "saatler öncesinde paylaşacağız" (t32u) | Uyumlu sayılır. 3 saat alt sınırı bizim seçimimiz |
| S10 | `docs/tarif.md` yol haritası: "Bot vs Ebraar vs topluluk", "Oybirliği/Oyçokluğu/Şerhli", "Tutanak/Sicil" ad önerileri | Kullanıcı bunları istemedi; bölüm ve etiket adları kullanıcının | **EKLEME**: bizim önerimiz olarak ayrıldı |
| S11 | Ana sayfa içeriği ("dünün kararları" vb.), tasarım paleti, SEO | Kullanıcı "profesyonel" dedi, detay vermedi | Bizim tasarımımız. Kural değil, öneri |
| S12 | "18+ / garanti değildir" notu | Bu turda kullanıcı söylemedi (v1'de olabilir) | Doğrulanamadı. Tutulması önerilir |

## 3. Okunamayan önceki brifler — dolaylı izler
- `supabase/schema.sql` başlığı ve kullanıcının eklediği `.sql` dosyası: "Ana tablolar (**kullanıcı tanımı**): matches, predictions, injuries, trends, agenda, sources". Altı tablo kullanıcıdan geliyor. `sources` tablosunda anahtarın değil yerinin tutulması da kullanıcı kuralı.
- Araştırma raporu: altı sütun "Tek Masa, Şeffaf Kâr/Zarar, Veri Lab, Maç Merkezi, Tahmin Botu, Tahmin Arşivi". Etiketler "Günün Kararı, Meclis Görüşü, Karar Birliği" kullanıcının "mevcut ad"ları. "WoodStats" düzeltmesi kullanıcıdan "FoodStats (foodstats.com)" olarak geldi.
- Veri raporu başlığı: "modern futbol medya markası ve tahmin takip uygulaması"; "5–50 kaynaklı veri havuzu"; ağırlıklı sakatlık okuması.
