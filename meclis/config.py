"""Ayarlar: ortam değişkenleri, .env dosyası ve Streamlit secrets.

Öncelik sırası: ortam değişkeni > .streamlit/secrets.toml > .env > varsayılan.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

try:  # .env dosyası varsa okunur
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except Exception:  # pragma: no cover
    pass


def _from_streamlit_secrets(name: str):
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        return None
    return None


def get_setting(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val not in (None, ""):
        return val
    val = _from_streamlit_secrets(name)
    if val not in (None, ""):
        return val
    return default


def get_bool(name: str, default: bool = False) -> bool:
    v = get_setting(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "evet", "yes", "on"}


def get_float(name: str, default: float) -> float:
    v = get_setting(name)
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class League:
    code: str  # uygulamanın iç kimliği (football-data.co.uk kodu varsa o)
    name: str  # Türkçe görünen ad
    country: str
    tsdb_id: str | None
    apif_id: int | None
    fdorg_code: str | None
    bsd_id: int | None = None  # Bzzoiro Sports Data lig kimliği
    fdcuk: bool = True  # football-data.co.uk'ta sezon CSV'si var mı
    cup: bool = False  # Avrupa kupası (takımlar farklı ülkelerden)
    tz: str = "Europe/Istanbul"


# Kimlikler 19.10.2026'da canlı doğrulandı (TheSportsDB lookupleague, BSD /leagues/).
LEAGUES: dict[str, League] = {
    "T1": League("T1", "Süper Lig", "Türkiye", "4339", 203, None, 11),
    "T2": League("T2", "TFF 1. Lig", "Türkiye", "4676", 204, None, None, fdcuk=False),
    "E0": League("E0", "Premier Lig", "İngiltere", "4328", 39, "PL", 1),
    "E1": League("E1", "Championship", "İngiltere", "4329", 40, "ELC", 12),
    "E2": League("E2", "League One", "İngiltere", "4396", 41, None, 86),
    "SP1": League("SP1", "La Liga", "İspanya", "4335", 140, "PD", 3),
    "SP2": League("SP2", "La Liga 2", "İspanya", "4400", 141, None, 38),
    "I1": League("I1", "Serie A", "İtalya", "4332", 135, "SA", 4),
    "I2": League("I2", "Serie B", "İtalya", "4394", 136, None, 100),
    "D1": League("D1", "Bundesliga", "Almanya", "4331", 78, "BL1", 5),
    "D2": League("D2", "2. Bundesliga", "Almanya", "4399", 79, None, 94),
    "F1": League("F1", "Ligue 1", "Fransa", "4334", 61, "FL1", 6),
    "F2": League("F2", "Ligue 2", "Fransa", "4401", 62, None, 89),
    "N1": League("N1", "Eredivisie", "Hollanda", "4337", 88, "DED", 10),
    "P1": League("P1", "Liga Portugal", "Portekiz", "4344", 94, "PPL", 2),
    "B1": League("B1", "Belçika Pro Lig", "Belçika", "4338", 144, None, 14),
    "SC0": League("SC0", "İskoçya Premiership", "İskoçya", "4330", 179, None, 13),
    "G1": League("G1", "Yunanistan Süper Lig", "Yunanistan", "4336", 197, None, 24),
    "CL": League("CL", "UEFA Şampiyonlar Ligi", "Avrupa", "4480", 2, "CL", 7, fdcuk=False, cup=True),
    "EL": League("EL", "UEFA Avrupa Ligi", "Avrupa", "4481", 3, None, 8, fdcuk=False, cup=True),
    "ECL": League("ECL", "UEFA Konferans Ligi", "Avrupa", "5071", 848, None, 83, fdcuk=False, cup=True),
    # Yalnızca DEMO_MODE=1 iken kullanılır; tüm verisi ÖRNEK (uydurma) veridir.
    "DEMO": League("DEMO", "Örnek Lig (ÖRNEK VERİ)", "—", None, None, None, fdcuk=False),
}
# Varsayılan sıra = arayüzdeki sıra: büyük 6 lig + Türkiye, Avrupa kupaları, sonra diğer ligler
DEFAULT_LEAGUES = "T1,E0,SP1,I1,D1,F1,CL,EL,ECL,T2,E1,N1,P1,B1,SC0,G1,E2,SP2,I2,D2,F2"

FDORG_TO_LEAGUE = {lg.fdorg_code: lg.code for lg in LEAGUES.values() if lg.fdorg_code}
APIF_TO_LEAGUE = {lg.apif_id: lg.code for lg in LEAGUES.values() if lg.apif_id}
TSDB_TO_LEAGUE = {lg.tsdb_id: lg.code for lg in LEAGUES.values() if lg.tsdb_id}


@dataclass
class Settings:
    supabase_url: str | None = None
    supabase_key: str | None = None
    football_data_token: str | None = None
    api_football_key: str | None = None
    odds_api_key: str | None = None
    sportmonks_key: str | None = None
    footystats_key: str | None = None
    sportdevs_key: str | None = None
    oddspapi_key: str | None = None
    clubelo_key: str | None = None
    bsd_api_key: str | None = None
    keys: dict = field(default_factory=dict)  # ENV ADI -> değer (yalnızca "tanımlı mı" kontrolü için)
    completeness_min: float = 60.0
    thesportsdb_key: str = "123"
    leagues: list[str] = field(default_factory=list)
    demo_mode: bool = False
    horizon_hours: float = 48.0
    min_minutes_before_kickoff: float = 15.0
    require_injury_data: bool = False
    min_team_matches: int = 4
    value_edge_min: float = 0.03
    no_odds_min_prob: float = 0.72
    coupon_min_odds: float = 2.30
    coupon_max_odds: float = 4.00
    coupon_min_ev: float = 0.0
    consensus_min_singles: int = 5
    local_db_path: str = str(DATA_DIR / "meclis.db")
    news_feeds: list[str] = field(default_factory=list)
    apif_daily_budget: int = 90

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


# Herkese açık RSS akışları (19.10.2026'da doğrulandı). Yalnızca başlık/özet/bağlantı saklanır.
DEFAULT_FEEDS = [
    # Türkiye
    "https://www.trthaber.com/spor_articles.rss",
    "https://www.aa.com.tr/tr/rss/default?cat=spor",
    "https://www.fotomac.com.tr/rss/futbol.xml",
    "https://www.ntvspor.net/rss/kategori/futbol",
    "https://www.ntvspor.net/rss/kategori/dunyadan-futbol",
    "https://www.sporx.com/_xml/rss.php",
    "https://www.hurriyet.com.tr/rss/spor",
    "https://www.sabah.com.tr/rss/spor.xml",
    "https://www.aspor.com.tr/rss/futbol.xml",
    "https://www.ajansspor.com/rss",
    "https://www.cnnturk.com/feed/rss/spor/news",
    "https://www.haberturk.com/rss/spor.xml",
    "https://www.sozcu.com.tr/feeds-rss-category-spor",
    # Uluslararası
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.theguardian.com/football/rss",
    "https://www.skysports.com/rss/12040",
    "https://www.marca.com/rss/futbol/primera-division.xml",
    "https://www.gazzetta.it/rss/calcio.xml",
]


def _all_keys() -> dict:
    from .sources.registry import SECRET_NAMES

    return {n: get_setting(n) for n in SECRET_NAMES}


def load_settings() -> Settings:
    leagues = [x.strip().upper() for x in (get_setting("LEAGUES", DEFAULT_LEAGUES) or "").split(",") if x.strip()]
    leagues = [x for x in leagues if x in LEAGUES and x != "DEMO"]
    demo = get_bool("DEMO_MODE", False)
    if demo:
        leagues = ["DEMO"]
    feeds_raw = get_setting("NEWS_FEEDS")
    feeds = [f.strip() for f in feeds_raw.split(",") if f.strip()] if feeds_raw else list(DEFAULT_FEEDS)
    return Settings(
        supabase_url=get_setting("SUPABASE_URL"),
        supabase_key=get_setting("SUPABASE_KEY"),
        football_data_token=get_setting("FOOTBALL_DATA_TOKEN"),
        api_football_key=get_setting("API_FOOTBALL_KEY"),
        odds_api_key=get_setting("ODDS_API_KEY"),
        sportmonks_key=get_setting("SPORTMONKS_KEY"),
        footystats_key=get_setting("FOOTYSTATS_KEY"),
        sportdevs_key=get_setting("SPORTDEVS_KEY"),
        oddspapi_key=get_setting("ODDSPAPI_KEY"),
        clubelo_key=get_setting("CLUBELO_KEY"),
        bsd_api_key=get_setting("BSD_API_KEY"),
        keys=_all_keys(),
        completeness_min=get_float("COMPLETENESS_MIN", 60.0),
        thesportsdb_key=get_setting("THESPORTSDB_KEY", "123") or "123",
        leagues=leagues,
        demo_mode=demo,
        horizon_hours=get_float("BOT_HORIZON_HOURS", 48.0),
        min_minutes_before_kickoff=get_float("BOT_MIN_MINUTES_BEFORE_KICKOFF", 15.0),
        require_injury_data=get_bool("REQUIRE_INJURY_DATA", False),
        min_team_matches=int(get_float("MIN_TEAM_MATCHES", 4)),
        value_edge_min=get_float("VALUE_EDGE_MIN", 0.03),
        no_odds_min_prob=get_float("NO_ODDS_MIN_PROB", 0.72),
        coupon_min_odds=get_float("COUPON_MIN_ODDS", 2.30),
        coupon_max_odds=get_float("COUPON_MAX_ODDS", 4.00),
        coupon_min_ev=get_float("COUPON_MIN_EV", 0.0),
        consensus_min_singles=int(get_float("CONSENSUS_MIN_SINGLES", 5)),
        local_db_path=get_setting("LOCAL_DB_PATH", str(DATA_DIR / "meclis.db")) or str(DATA_DIR / "meclis.db"),
        news_feeds=feeds,
        apif_daily_budget=int(get_float("API_FOOTBALL_DAILY_BUDGET", 90)),
    )
