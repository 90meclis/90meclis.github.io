"""Tüm veri kaynaklarının tek listesi (sources tablosu tohumu, arayüz durumu ve belgeler buradan üretilir).

Kural: anahtar değeri ASLA burada/kodda tutulmaz; yalnızca ortam değişkeninin ADI (api_key_secret).
Anahtarı tanımlı olmayan kaynak atlanır ama arayüzde "anahtar bekleniyor" olarak açıkça görünür.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KEY_STORAGE = "env + GitHub Actions Secrets + Supabase Vault"


@dataclass(frozen=True)
class SourceDef:
    name: str
    title: str
    api_key_secret: str | None
    requires_key: bool
    daily_limit: int | None
    free_tier: str
    signup_url: str | None
    fills_fields: list[str] = field(default_factory=list)
    license_note: str = ""
    key_storage: str = KEY_STORAGE

    def seed_row(self) -> dict:
        return {"name": self.name, "api_key_secret": self.api_key_secret,
                "key_storage": self.key_storage if self.api_key_secret else "anahtar gerekmez",
                "daily_limit": self.daily_limit, "fills_fields": list(self.fills_fields),
                "requires_key": self.requires_key,
                "license_note": " ".join(x for x in (f"Ücretsiz katman: {self.free_tier}.", self.license_note,
                                                     f"Kayıt/bilgi: {self.signup_url}" if self.signup_url else "") if x),
                "is_active": True}


SOURCES: list[SourceDef] = [
    # ---------------------------------------------------------------- anahtarsız
    SourceDef("football-data.co.uk", "football-data.co.uk", None, False, None,
              "Ücretsiz CSV, limit yok (makul kullanım)", "https://www.football-data.co.uk/data.php",
              ["sonuç", "İY skoru", "şut", "isabetli şut", "korner", "faul", "kart", "hakem",
               "açılış/kapanış oranları", "fikstür"],
              "Ham veri yeniden yayınlanmaz, iç modelleme için; kaynak gösterilir. Sonuçlar haftada ~2 kez güncellenir."),
    SourceDef("openligadb", "OpenLigaDB", None, False, None,
              "Ücretsiz, anahtarsız REST API (makul kullanım)", "https://www.openligadb.de",
              ["fikstür", "sonuç (dakikalar içinde)", "İY skoru", "gol dakikaları"],
              "Topluluk tarafından girilen açık veri. Bundesliga (bl1) güvenilir; Premier Lig (pl) ve La Liga (la1) "
              "topluluk ligleri yalnızca boşluk doldurur."),
    SourceDef("openfootball", "openfootball / football.json", None, False, None,
              "GitHub ham dosyaları, CC0 (kamu malı)", "https://github.com/openfootball/football.json",
              ["fikstür", "sonuç", "İY skoru"],
              "CC0-1.0 lisanslı açık veri; güncelleme gecikmeli olabilir, en düşük öncelik."),
    SourceDef("thesportsdb", "TheSportsDB", "THESPORTSDB_KEY", False, None,
              "Ücretsiz anahtar '123': ~30 istek/dk, günlük liste lig başına 3 maç", "https://www.thesportsdb.com/pricing",
              ["fikstür", "sonuç", "stadyum", "şehir", "kadro listesi", "ilk 11 (Patreon anahtarıyla)"],
              "Ücretsiz '123' anahtarında ilk 11 boş döner (doğrulandı); Patreon anahtarı (THESPORTSDB_KEY) tüm maçları ve ilk 11'i açar."),
    SourceDef("wikidata", "Wikidata (SPARQL)", None, False, None,
              "Ücretsiz, CC0; sorgu başına 60 sn, User-Agent zorunlu", "https://query.wikidata.org",
              ["stadyum", "stadyum kapasitesi", "şehir", "stadyum koordinatı", "teknik direktör"],
              "CC0 veri; Wikimedia User-Agent politikasına uyulur, sonuçlar 14 gün önbelleklenir."),
    SourceDef("open-meteo", "Open-Meteo", None, False, 10000,
              "Ticari olmayan kullanım ücretsiz, 10.000 istek/gün", "https://open-meteo.com/en/pricing",
              ["hava durumu", "şehir koordinatı"], "CC BY 4.0 veri; kaynak gösterilir."),
    SourceDef("rss", "Haber RSS akışları", None, False, None,
              "Yayıncıların herkese açık RSS akışları", None,
              ["haber başlığı", "özet", "bağlantı"],
              "Yalnızca başlık/özet/bağlantı saklanır; tam metin kopyalanmaz, bağlantı yayıncıya gider."),
    SourceDef("wikipedia", "Wikipedia (güncel kadro)", None, False, None,
              "Ücretsiz MediaWiki API; seri istek, tanımlayıcı User-Agent, maxlag=5", "https://www.mediawiki.org/wiki/API:Etiquette",
              ["güncel A takım kadrosu", "forma no", "mevki"],
              "İçerik CC BY-SA 4.0; kaynak gösterilir. Takım başına 7 günde bir okunur. Sakatlık bilgisi içermez."),
    SourceDef("meclis-elo", "Meclis Elo (iç hesap)", None, False, None,
              "Havuzdaki gerçek sonuçlardan hesaplanır", None,
              ["takım gücü (Elo)", "gol modeli önseli"],
              "Dış kaynak değil; football-data.co.uk/OpenLigaDB sonuçlarından türetilir."),
    # ---------------------------------------------------------------- anahtarlı
    SourceDef("api-football", "API-Football (api-sports.io)", "API_FOOTBALL_KEY", True, 100,
              "Ücretsiz: 100 istek/gün, 10/dk", "https://dashboard.api-football.com/register",
              ["güncel sakat/cezalı (dün–yarın)", "maç öncesi resmî ilk 11", "geçmiş fikstür (2022–2024)",
               "geçmiş sakat/cezalı", "oyuncu dakika/ilk 11/gol/asist (2024)"],
              "Ücretsiz plan (19.10.2026'da doğrulandı): sezonluk sorgu yalnızca 2022–2024, tarih sorgusu dün–yarın, "
              "fikstür kimliğiyle sorgu güncel sezonda açık, page en fazla 3. Kalan bütçe `python -m meclis gecmis` "
              "ile geçmiş veri doldurmaya gider, kaldığı yerden sürer."),
    SourceDef("football-data.org", "football-data.org", "FOOTBALL_DATA_TOKEN", True, 14400,
              "Ücretsiz: 12 turnuva, 10 istek/dk (Süper Lig yok)", "https://www.football-data.org/client/register",
              ["fikstür", "sonuç", "İY skoru", "hakem", "stadyum"], ""),
    SourceDef("the-odds-api", "The Odds API", "ODDS_API_KEY", True, None,
              "Ücretsiz: ayda 500 kredi (h2h+totals × eu = 2 kredi/lig)", "https://the-odds-api.com/#get-access",
              ["1X2 oranı", "Alt/Üst oranı", "Pinnacle oranı"], "Türk bahis şirketi yok."),
    SourceDef("oddspapi", "OddsPapi", "ODDSPAPI_KEY", True, 8,
              "Ücretsiz: ayda 250 istek (bot günde en çok 1 oran çağrısı yapar)", "https://oddspapi.io/en/register",
              ["1X2 oranı (Pinnacle dahil 300+ bahis şirketi)"], ""),
    SourceDef("sportmonks", "Sportmonks Football API v3", "SPORTMONKS_KEY", True, 4320,
              "Ücretsiz plan: yalnızca Danimarka Superliga + İskoçya Premiership (180 istek/saat/varlık); "
              "bizim liglerimiz ücretli planda", "https://my.sportmonks.com/register",
              ["fikstür", "sonuç", "İY skoru", "stadyum", "hakem", "maç istatistiği"], ""),
    SourceDef("footystats", "FootyStats API", "FOOTYSTATS_KEY", True, 4320,
              "Ücretsiz: yalnızca Premier Lig, 180 istek/saat; Süper Lig ücretli (Hobby £29.99/ay)",
              "https://footystats.org/api", ["sonuç", "İY skoru", "korner", "kart", "isabetli şut", "faul",
                                              "stadyum", "1X2 ve 2.5 Alt/Üst oranı"], ""),
    SourceDef("sportdevs", "SportDevs Football API", "SPORTDEVS_KEY", True, 300,
              "Ücretsiz: 300 istek/gün, 10 büyük lig", "https://sportdevs.com/football",
              ["fikstür", "sonuç", "İY skoru", "stadyum", "ilk 11 (matches-lineups)", "eksik oyuncular (kadro içinde)"], ""),
    SourceDef("bsd", "Bzzoiro Sports Data (BSD)", "BSD_API_KEY", True, None,
              "Ücretsiz futbol planı: tüm v2 uç noktaları, günlük 7.500 istek (IP başına 10 istek/sn); 6 ligin hepsi kapsamda",
              "https://sports.bzzoiro.com/register/",
              ["sakat/cezalı/şüpheli (maç başına, 7 gün önceden)", "resmî ilk 11 (~1 saat önce)", "tahmini ilk 11 (AI)",
               "kadro + oyuncu uygunluğu", "fikstür", "sonuç", "İY skoru", "konsensüs oranları (1X2, A/Ü 1.5/2.5/3.5, KG)",
               "maç istatistiği (şut, isabetli şut, korner, faul, kart, kale vuruşu, xG, topla oynama)", "hakem", "stadyum"],
              "Lisans v4.0: iç kullanım için saklama ve kendi uygulamanda gösterim serbest; ham verinin yeniden satışı yasak."),
    # ---------------------------------------------------------------- isteğe bağlı (kullanıcı anahtar eklerse)
    SourceDef("highlightly", "Highlightly Football API", "HIGHLIGHTLY_KEY", True, 100, "100 istek/gün, kart yok",
              "https://highlightly.net/", ["resmî ilk 11", "maç istatistiği", "sakat/cezalı", "oyuncu sezon istatistiği"],
              "Koşullar saklama ve kendi üründe gösterime izin veriyor; ham API yeniden satılmaz. Anahtar tanımlanınca etkinleşir."),
    SourceDef("bigballs", "Big Balls Sports Data", "BIGBALLS_KEY", True, 250, "250 istek/gün (GitHub ile 500)",
              "https://bigballsdata.com/", ["resmî ilk 11", "takım maç istatistiği", "oyuncu sezon istatistiği"],
              "Yalnızca 5 büyük lig + Şampiyonlar Ligi. Anahtar tanımlanınca etkinleşir."),
    SourceDef("nosyapi", "NosyAPI Maç Sonuçları", "NOSYAPI_KEY", True, None, "500 kredi (kredi = dönen satır)",
              "https://www.nosyapi.com/", ["sonuç", "İY skoru", "korner", "kart"],
              "YALNIZCA sonuç/istatistik uç noktaları; iddaa oranı kullanılmaz (kullanıcı kararı: oranlar yalnızca yabancı "
              "kaynaklardan). Anahtar tanımlanınca etkinleşir."),
    SourceDef("soccerdata", "SoccerdataAPI", "SOCCERDATA_KEY", True, 75, "75 istek/gün; ücretsiz planda yalnızca UEL + E1",
              "https://soccerdataapi.com/", ["tahmini ilk 11", "sakat/cezalı"], "Anahtar tanımlanınca etkinleşir."),
    SourceDef("playerelo", "PlayerElo", "PLAYERELO_KEY", True, None, "500 istek/ay, 10/dk",
              "https://playerelo.football/api-access", ["oyuncu Elo (Eksik Etkisi için iç model girdisi)"],
              "Ücretsiz katman değerlendirme/hobi amaçlı: yalnızca iç model girdisi, yayımlanmaz. Anahtar tanımlanınca etkinleşir."),
]

BY_NAME = {s.name: s for s in SOURCES}
SECRET_NAMES = sorted({s.api_key_secret for s in SOURCES if s.api_key_secret})


def key_state(src: SourceDef, settings) -> str:
    """'gerekmez' | 'tanımlı' | 'anahtar bekleniyor' (değer asla döndürülmez)."""
    if not src.api_key_secret:
        return "gerekmez"
    if src.name == "thesportsdb":
        return "tanımlı" if (settings.thesportsdb_key or "123") != "123" else "ücretsiz anahtar (123)"
    val = (getattr(settings, "keys", {}) or {}).get(src.api_key_secret)
    return "tanımlı" if val else "anahtar bekleniyor"
