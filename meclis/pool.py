"""Birleşik veri havuzu.

Birden fazla kaynaktan gelen maç kayıtları tek havuzda birleştirilir:
* Aynı maç = aynı lig + iki takım eşleşiyor + başlama saatleri en fazla 36 saat farklı.
* Alan bazında doldurma: bir kaynakta eksik olan alan diğerinden tamamlanır; her alanın kökeni
  `sources` içinde saklanır. Skor çelişkisi varsa `_conflicts` listesine yazılır.
* Bir maç hiçbir koşulda havuzdan atılmaz; eksik alanlar "eksik" olarak işaretlenir.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import names
from .timeutil import now_utc, parse_dt, to_iso

# Alan bazında öncelik (ilk dolu değer kazanır; boşlar sıradaki kaynaktan dolar)
PRIORITY = ["api-football", "sportmonks", "football-data.org", "footystats", "sportdevs", "openligadb",
            "the-odds-api", "oddspapi", "thesportsdb", "football-data.co.uk", "openfootball"]
# Görünen ad önceliği (mevcut adlar kararlı kalsın diye eski kaynaklar önde)
NAME_PRIORITY = ["thesportsdb", "api-football", "football-data.org", "sportmonks", "football-data.co.uk",
                 "footystats", "sportdevs", "openligadb", "the-odds-api", "oddspapi", "openfootball"]
# Oran önceliği: çok şirketli ortalama > Pinnacle > CSV ortalaması > tekil kaynaklar
ODDS_PRIORITY = ["the-odds-api", "oddspapi", "football-data.co.uk", "footystats", "api-football", "sportmonks"]
SCALARS = ["kickoff_at", "season", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals",
           "venue", "referee", "city"]
STAT_FIELDS = ["shots", "shots_on_target", "corners", "fouls", "yellow", "red", "goal_kicks", "xg", "possession"]
STATUS_RANK = {"planlandi": 1, "basladi": 2, "ertelendi": 3, "iptal": 3, "bitti": 4}


class TeamRegistry:
    """Lig bazında takım anahtarlarını tutar; farklı yazımları aynı takıma bağlar."""

    def __init__(self):
        self.keys: dict[str, dict[str, str]] = {}  # league -> {key: display name}

    def add(self, league: str, key: str, display: str) -> None:
        self.keys.setdefault(league, {}).setdefault(key, display)

    def lookup(self, league: str, name: str) -> str | None:
        """resolve() gibi ama bilinmeyen adı EKLEMEZ (yalnızca boşluk dolduran kaynaklar için)."""
        k = names.canonical_key(name)
        known = self.keys.get(league, {})
        if k in known:
            return k
        for kk in known:
            if names.same_team(k, kk):
                return kk
        return None

    def resolve(self, league: str, name: str) -> str:
        k = names.canonical_key(name)
        known = self.keys.setdefault(league, {})
        if k in known:
            return k
        for kk in known:
            if names.same_team(k, kk):
                return kk
        known[k] = names.display_name(name)
        return k


def _prio(src: str, order: list[str]) -> int:
    return order.index(src) if src in order else len(order)


def _bucket_key(league: str, hk: str, ak: str) -> tuple:
    return (league, hk, ak)


def merge_records(records: list[dict], registry: TeamRegistry | None = None,
                  existing: list[dict] | None = None) -> list[dict]:
    """Kaynak kayıtlarını birleştirir. Dönen her öğe `matches` tablosuna yazılabilir bir sözlük + 'stats'."""
    reg = registry or TeamRegistry()
    for e in existing or []:
        reg.add(e["league"], e["home_team_id"].split(":", 1)[1], e["home_name"])
        reg.add(e["league"], e["away_team_id"].split(":", 1)[1], e["away_name"])
    recs = sorted([r for r in records if r.get("kickoff_at") and r.get("home_name") and r.get("away_name")],
                  key=lambda r: _prio(r["source"], PRIORITY))
    buckets: dict[tuple, list[dict]] = {}
    merged: list[dict] = []
    ex_keys: dict[tuple, list] = {}
    for e in existing or []:
        ex_keys.setdefault(_bucket_key(e["league"], e["home_team_id"].split(":", 1)[1],
                                       e["away_team_id"].split(":", 1)[1]), []).append(parse_dt(e["kickoff_at"]))
    reg.unmatched = []  # boşluk dolduran kaynakların eşleşmeyen kayıtları (ad eşlemesi bakımı için)

    def find(league, hk, ak, ko):
        for m in buckets.get(_bucket_key(league, hk, ak), []):
            if abs((parse_dt(m["kickoff_at"]) - ko).total_seconds()) <= 36 * 3600:
                return m
        return None

    for r in recs:
        league = r["league"]
        ko = parse_dt(r["kickoff_at"])
        if r.get("fill_only"):
            # Topluluk/gecikmeli kaynak: yalnızca var olan maçın boşluklarını doldurur, yeni takım/maç açmaz
            hk, ak = reg.lookup(league, r["home_name"]), reg.lookup(league, r["away_name"])
            known = hk and ak and (find(league, hk, ak, ko) is not None or any(
                abs((t - ko).total_seconds()) <= 36 * 3600 for t in ex_keys.get(_bucket_key(league, hk, ak), [])))
            if not known:
                reg.unmatched.append(f"{r['source']}:{league}:{r['home_name']}–{r['away_name']}")
                continue
        else:
            hk, ak = reg.resolve(league, r["home_name"]), reg.resolve(league, r["away_name"])
        m = find(league, hk, ak, ko)
        if m is None:
            m = {"league": league, "home_team_id": f"{league}:{hk}", "away_team_id": f"{league}:{ak}",
                 "home_name": None, "away_name": None, "status": None, "ext_ids": {}, "odds": {},
                 "sources": {"_all": [], "_conflicts": []}, "stats": {"home": {}, "away": {}},
                 "_name_prio": 99}
            for f in SCALARS:
                m[f] = None
            buckets.setdefault(_bucket_key(league, hk, ak), []).append(m)
            merged.append(m)
        src = r["source"]
        if src not in m["sources"]["_all"]:
            m["sources"]["_all"].append(src)
        for f in SCALARS:
            v = r.get(f)
            if v is None or v == "":
                continue
            if m[f] is None:
                m[f] = to_iso(v) if f == "kickoff_at" else v
                m["sources"][f] = src
            elif f in ("home_goals", "away_goals") and m[f] != v:
                m["sources"]["_conflicts"].append(f"{f}: {m['sources'].get(f)}={m[f]} / {src}={v}")
        st = r.get("status") or "planlandi"
        if m["status"] is None or STATUS_RANK.get(st, 0) > STATUS_RANK.get(m["status"], 0):
            if not (st == "bitti" and r.get("home_goals") is None):
                m["status"] = st
                m["sources"]["status"] = src
        np_ = _prio(src, NAME_PRIORITY)
        if np_ < m["_name_prio"]:
            m["home_name"], m["away_name"], m["_name_prio"] = r["home_name"], r["away_name"], np_
        for k, v in (r.get("ext_ids") or {}).items():
            if v is not None and k not in m["ext_ids"]:
                m["ext_ids"][k] = v
        for k, v in (r.get("odds") or {}).items():
            cur = m["sources"].setdefault("odds", {}).get(k)
            if k not in m["odds"] or _prio(src, ODDS_PRIORITY) < _prio(cur or "", ODDS_PRIORITY):
                m["odds"][k] = v
                m["sources"]["odds"][k] = src
        for side in ("home", "away"):
            for f, v in ((r.get("stats") or {}).get(side) or {}).items():
                if v is not None and m["stats"][side].get(f) is None:
                    m["stats"][side][f] = v
                    m["sources"].setdefault("stats", {})[f"{side}.{f}"] = src

    # Var olan kayıtlarla eşleştir: id'yi koru, eksik alanları eskisinden doldur
    ex_index: dict[tuple, list[dict]] = {}
    for e in existing or []:
        ex_index.setdefault(_bucket_key(e["league"], e["home_team_id"].split(":", 1)[1],
                                        e["away_team_id"].split(":", 1)[1]), []).append(e)
    out = []
    for m in merged:
        m.pop("_name_prio", None)
        if m["status"] == "bitti" and (m["home_goals"] is None or m["away_goals"] is None):
            m["status"] = "planlandi"
        m["status"] = m["status"] or "planlandi"
        ko = parse_dt(m["kickoff_at"])
        hk, ak = m["home_team_id"].split(":", 1)[1], m["away_team_id"].split(":", 1)[1]
        prev = None
        for e in ex_index.get(_bucket_key(m["league"], hk, ak), []):
            if abs((parse_dt(e["kickoff_at"]) - ko).total_seconds()) <= 36 * 3600:
                prev = e
                break
        if prev:
            m["id"] = prev["id"]
            for f in SCALARS:
                if m.get(f) is None and prev.get(f) is not None:
                    m[f] = prev[f]
            for k, v in (prev.get("ext_ids") or {}).items():
                m["ext_ids"].setdefault(k, v)
            for k, v in (prev.get("odds") or {}).items():
                m["odds"].setdefault(k, v)
            if STATUS_RANK.get(prev.get("status"), 0) > STATUS_RANK.get(m["status"], 0):
                m["status"] = prev["status"]
            for f, v in (prev.get("sources") or {}).items():
                if f not in m["sources"]:
                    m["sources"][f] = v
        else:
            m["id"] = f"{m['league']}:{ko.date().isoformat()}:{hk}:{ak}"
        m["home_name"] = names.display_name(m["home_name"])
        m["away_name"] = names.display_name(m["away_name"])
        out.append(m)
    return out


DURUM = {"planlandi": "gelecek", "basladi": "canlı", "bitti": "bitti", "ertelendi": "ertelendi", "iptal": "iptal"}


LIVE_WINDOW = timedelta(hours=2, minutes=30)


def durum_for(m: dict, now=None) -> str:
    """Görünen durum. Başlama saati geçmiş ama hiçbir kaynak sonuç vermemişse maç 'gelecek' görünmez:
    ilk 2,5 saat 'canlı' (tahmini), sonrası 'gelecek' kalır ama arayüz 'Sonuç bekleniyor' der."""
    st = m.get("status") or "planlandi"
    if st == "planlandi" and m.get("kickoff_at"):
        now = now or now_utc()
        ko = parse_dt(m["kickoff_at"])
        if ko and ko <= now < ko + LIVE_WINDOW:
            return "canlı"
    return DURUM.get(st, "gelecek")


def status_text(m: dict, now=None) -> str:
    st = m.get("status") or "planlandi"
    if st == "planlandi" and m.get("kickoff_at"):
        now = now or now_utc()
        ko = parse_dt(m["kickoff_at"])
        if ko and ko <= now:
            return "Oynanıyor (tahmini)" if now < ko + LIVE_WINDOW else "Sonuç bekleniyor"
    return {"planlandi": "Oynanacak", "bitti": "Bitti", "basladi": "Oynanıyor", "ertelendi": "Ertelendi",
            "iptal": "İptal"}.get(st, st)


def missing_fields(m: dict) -> list[str]:
    """Maç kaydında boş kalan alanlar (Maç Merkezi ve tamlık puanı için)."""
    miss = []
    if m.get("status") in ("planlandi", "basladi") and m.get("kickoff_at") and parse_dt(m["kickoff_at"]) \
            and parse_dt(m["kickoff_at"]) + LIVE_WINDOW <= now_utc():
        miss.append("sonuç")
    if not (m.get("odds") or {}).get("1X2"):
        miss.append("piyasa oranı (1X2)")
    if not m.get("venue"):
        miss.append("stadyum")
    if not m.get("referee"):
        miss.append("hakem")
    if m.get("status") == "bitti":
        st = m.get("stats") or {}
        for f, lab in (("corners", "korner"), ("shots_on_target", "isabetli şut"), ("yellow", "kart"),
                       ("goal_kicks", "kale vuruşu")):
            if (st.get("home") or {}).get(f) is None:
                miss.append(f"istatistik: {lab}")
        if m.get("ht_home_goals") is None:
            miss.append("İY skoru")
    return miss


class DataPool:
    """Kaynakları çağırır, birleştirir ve depoya (Supabase/SQLite) yazar."""

    def __init__(self, store, settings):
        from .sources.api_football import ApiFootball
        from .sources.football_data_org import FootballDataOrg
        from .sources.odds_api import OddsApi
        from .sources.footystats import FootyStats
        from .sources.oddspapi import OddsPapi
        from .sources.sportdevs import SportDevs
        from .sources.sportmonks import Sportmonks
        from .sources.thesportsdb import TheSportsDB

        self.store = store
        self.s = settings
        self.sportmonks = Sportmonks(settings.sportmonks_key)
        self.footystats = FootyStats(settings.footystats_key)
        self.sportdevs = SportDevs(settings.sportdevs_key)
        self.oddspapi = OddsPapi(settings.oddspapi_key)
        self.fdorg = FootballDataOrg(settings.football_data_token)
        self.apif = ApiFootball(settings.api_football_key, store, settings.apif_daily_budget)
        self.tsdb = TheSportsDB(settings.thesportsdb_key)
        self.oddsapi = OddsApi(settings.odds_api_key)
        self.log: list[str] = []

    def _waiting_key(self, source: str, env: str, what: str) -> None:
        """Anahtar yoksa kaynak atlanır ama bu GİZLENMEZ: durum tablosunda 'anahtar bekleniyor' görünür."""
        self._note(source, False, f"anahtar bekleniyor: {env} tanımlı değil — {what} bu kaynaktan gelmiyor")

    def _daily_once(self, source: str) -> bool:
        """Aylık kotası küçük kaynaklar için: bugün başarıyla çağrıldıysa tekrar çağırma."""
        try:
            st = self.store.get("source_status", source=source) or {}
        except Exception:
            return True
        return not (st.get("ok") and st.get("calls_date") == now_utc().date().isoformat()
                    and int(st.get("calls_today") or 0) > 0)

    def _note(self, source: str, ok: bool, msg: str, calls: int = 0) -> None:
        self.log.append(("✅ " if ok else "⚠️ ") + f"{source}: {msg}")
        try:
            self.store.set_source_status(source, ok, msg, add_calls=calls)
        except Exception:
            pass

    # ---------------------------------------------------------------- toplama
    def collect(self, days_back: int = 3, days_ahead: int = 3, history: bool = False) -> list[dict]:
        from .sources import football_data_co_uk as fdcuk

        today = now_utc().date()
        recs: list[dict] = []
        leagues = self.s.leagues
        if history:
            code = fdcuk.season_code(today)
            prev = f"{(int(code[:2]) - 1) % 100:02d}{code[:2]}"
            for lg in leagues:
                for c in (prev, code):
                    try:
                        rows = fdcuk.fetch_season(lg, c)
                        recs += rows
                        self._note(fdcuk.SOURCE, True, f"{lg} {fdcuk.season_label(c)}: {len(rows)} maç")
                    except Exception as e:
                        self._note(fdcuk.SOURCE, False, f"{lg} {c}: {e}")
        try:
            fx = fdcuk.fetch_fixtures(leagues)
            recs += fx
            self._note(fdcuk.SOURCE, True, f"fikstür: {len(fx)} maç (oranlı)")
        except Exception as e:
            self._note(fdcuk.SOURCE, False, f"fikstür: {e}")
        n = 0
        for i in range(-min(days_back, 2), min(days_ahead, 2) + 1):
            d = today + timedelta(days=i)
            try:
                rows = self.tsdb.events_day(d, leagues)
                recs += rows
                n += len(rows)
            except Exception as e:
                self._note("thesportsdb", False, f"{d}: {e}")
                break
        self._note("thesportsdb", True, f"{n} maç (günlük liste)")
        if self.fdorg.available:
            try:
                rows = self.fdorg.matches(today - timedelta(days=days_back), today + timedelta(days=days_ahead), leagues)
                recs += rows
                self._note("football-data.org", True, f"{len(rows)} maç")
            except Exception as e:
                self._note("football-data.org", False, str(e))
        else:
            self._waiting_key("football-data.org", "FOOTBALL_DATA_TOKEN", "fikstür/sonuç/hakem (büyük Avrupa ligleri)")
        if self.apif.available:
            season = today.year if today.month >= 7 else today.year - 1
            for lg in leagues:
                try:
                    rows = self.apif.fixtures(lg, season, today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                    recs += rows
                    self._note("api-football", True, f"{lg}: {len(rows)} maç")
                except Exception as e:
                    self._note("api-football", False, f"{lg}: {e}")
                    break
        else:
            self._waiting_key("api-football", "API_FOOTBALL_KEY", "ilk 11, sakat/cezalı, oyuncu dakikaları, hakem, maç istatistiği")
        if self.oddsapi.available:
            for lg in leagues:
                try:
                    rows, info = self.oddsapi.odds(lg)
                    recs += rows
                    self._note("the-odds-api", True, f"{lg}: {len(rows)} maç oranı ({info})")
                except Exception as e:
                    self._note("the-odds-api", False, f"{lg}: {e}")
                    break
        else:
            self._waiting_key("the-odds-api", "ODDS_API_KEY", "çok şirketli 1X2/Alt-Üst oranları")
        self._collect_extra(recs, today, days_back, days_ahead, history)
        return recs

    def _collect_extra(self, recs: list[dict], today, days_back: int, days_ahead: int, history: bool) -> None:
        from .sources import openfootball, openligadb

        leagues = self.s.leagues
        lo = now_utc() - timedelta(days=days_back + 1)
        hi = now_utc() + timedelta(days=days_ahead + 1)

        def in_window(rows):
            return rows if history else [r for r in rows if lo <= parse_dt(r["kickoff_at"]) <= hi]

        for lg in leagues:
            if lg in openligadb.LEAGUE_MAP:
                try:
                    rows = in_window(openligadb.fetch_league(lg, today))
                    recs += rows
                    self._note("openligadb", True, f"{lg} ({openligadb.LEAGUE_MAP[lg][0]}): {len(rows)} maç", calls=1)
                except Exception as e:
                    self._note("openligadb", False, f"{lg}: {e}")
        n_of = 0
        for lg in leagues:
            try:
                rows = in_window(openfootball.fetch_league(lg, today))
                recs += rows
                n_of += len(rows)
            except Exception as e:
                self._note("openfootball", False, f"{lg}: {e}")
        self._note("openfootball", True, f"{n_of} maç (yalnızca boşluk doldurur)")
        if self.sportmonks.available:
            try:
                rows = self.sportmonks.fixtures(leagues, today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                recs += rows
                self._note("sportmonks", True, f"{len(rows)} maç (abonelikteki ligler)", calls=1)
            except Exception as e:
                self._note("sportmonks", False, str(e))
        else:
            self._waiting_key("sportmonks", "SPORTMONKS_KEY", "fikstür/sonuç/stadyum/hakem/istatistik")
        if self.footystats.available:
            n = 0
            try:
                for i in range(-min(days_back, 2), min(days_ahead, 2) + 1):
                    rows = self.footystats.matches_on(today + timedelta(days=i))
                    recs += rows
                    n += len(rows)
                self._note("footystats", True, f"{n} maç (hesapta seçili ligler)", calls=1)
            except Exception as e:
                self._note("footystats", False, str(e))
        else:
            self._waiting_key("footystats", "FOOTYSTATS_KEY", "korner/kart/şut istatistikleri ve oranlar")
        if self.sportdevs.available:
            try:
                rows = self.sportdevs.matches(today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                recs += rows
                self._note("sportdevs", True, f"{len(rows)} maç", calls=1)
            except Exception as e:
                self._note("sportdevs", False, str(e))
        else:
            self._waiting_key("sportdevs", "SPORTDEVS_KEY", "fikstür/sonuç/İY skoru")
        if self.oddspapi.available:
            if self._daily_once("oddspapi"):
                try:
                    rows = self.oddspapi.odds(leagues)
                    recs += rows
                    self._note("oddspapi", True, f"{len(rows)} maç oranı (Pinnacle)", calls=1)
                except Exception as e:
                    self._note("oddspapi", False, str(e))
            else:
                self.log.append("ℹ️ oddspapi: bugünkü oran çağrısı yapıldı (aylık 250 istek kotası korunuyor)")
        else:
            self._waiting_key("oddspapi", "ODDSPAPI_KEY", "Pinnacle 1X2 oranı")

    def elo_priors(self, league: str) -> dict[str, float]:
        """Club Elo başlangıç puanları (API erişilebilirse). Erişilemezse boş — Meclis Elo yine çalışır."""
        from .sources import clubelo

        if getattr(self, "_clubelo_failed", False):
            return {}
        cache = getattr(self, "_clubelo_rows", None)
        if cache is None:
            try:
                cache = clubelo.ratings(now_utc().date(), self.s.clubelo_key)
                self._clubelo_rows = cache
                self._note("clubelo", True, f"{len(cache)} kulüp puanı")
            except Exception as e:
                self._clubelo_failed = True
                hint = "" if self.s.clubelo_key else " (CLUBELO_KEY bekleniyor; API Eylül 2026'dan beri kimlik istiyor)"
                self._note("clubelo", False, f"{e}{hint} — Meclis Elo iç hesabı kullanılıyor")
                return {}
        country = clubelo.COUNTRY.get(league)
        reg = TeamRegistry()
        for t in self.store.select("teams", [("league", "eq", league)]):
            reg.add(league, t["id"].split(":", 1)[1], t["name"])
        out = {}
        for r in cache:
            if r["country"] != country:
                continue
            k = reg.lookup(league, r["club"])
            if k:
                out[f"{league}:{k}"] = r["elo"]
        return out

    def enrich_teams(self, max_lookups: int = 200) -> int:
        """Wikidata'dan stadyum/şehir/kapasite/koordinat/teknik direktör doldurur (takım başına 14 günde bir)."""
        from .sources import wikidata

        today = now_utc().date().isoformat()
        rows, done = [], 0
        for t in self.store.select("teams"):
            if t["league"] not in self.s.leagues:
                continue
            ext = dict(t.get("ext_ids") or {})
            checked = ext.get("wikidata_checked")
            if checked and (now_utc().date() - parse_dt(checked + "T00:00:00+00:00").date()).days < 14:
                continue
            if done >= max_lookups:
                break
            done += 1
            try:
                info = None
                for q in dict.fromkeys([names.display_name(t["name"]), t["name"]]):
                    info = wikidata.team_info(q, t["league"])
                    if info:
                        break
            except Exception as e:
                self._note("wikidata", False, f"{t['name']}: {e}")
                break
            ext["wikidata_checked"] = today
            if info:
                ext["wikidata"] = info["wikidata"]
                for f in ("stadium", "city", "coach", "capacity"):
                    if info.get(f) and not t.get(f):
                        t[f] = info[f]
                if info.get("lat") is not None:  # stadyum noktası, şehir merkezinden daha doğru
                    t["lat"], t["lon"] = info["lat"], info["lon"]
            t["ext_ids"] = ext
            t["updated_at"] = to_iso(now_utc())
            rows.append(t)
        if rows:
            self.store.upsert("teams", rows)
            found = sum(1 for r in rows if (r.get("ext_ids") or {}).get("wikidata"))
            self._note("wikidata", True, f"{len(rows)} takım sorgulandı, {found} eşleşti", calls=len(rows))
        return len(rows)

    def refresh(self, days_back: int = 3, days_ahead: int = 3, history: bool = False) -> dict:
        from .store import seed_sources

        try:
            seed_sources(self.store)
        except Exception as e:
            self.log.append(f"⚠️ sources tablosu güncellenemedi: {e}")
        recs = self.collect(days_back, days_ahead, history)
        lo = to_iso(now_utc() - timedelta(days=days_back + 2))
        hi = to_iso(now_utc() + timedelta(days=days_ahead + 2))
        existing = self.store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lte", hi)])
        if history:
            existing = self.store.select("matches", [("kickoff_at", "gte", to_iso(now_utc() - timedelta(days=800)))])
        reg = TeamRegistry()
        for t in self.store.select("teams"):
            reg.add(t["league"], t["id"].split(":", 1)[1], t["name"])
        merged = merge_records(recs, reg, existing)
        if getattr(reg, "unmatched", None):
            self.log.append(f"ℹ️ boşluk dolduran kaynaklarda eşleşmeyen {len(reg.unmatched)} kayıt atlandı "
                            f"(ör. {', '.join(reg.unmatched[:3])})")
        self.save(merged)
        try:
            self.enrich_teams()
        except Exception as e:
            self._note("wikidata", False, str(e))
        self.fill_venues()
        return {"records": len(recs), "matches": len(merged), "log": list(self.log),
                "unmatched": list(getattr(reg, "unmatched", []))}

    def fill_venues(self) -> int:
        """Stadyumu boş maçlara ev sahibinin (Wikidata/TheSportsDB) stadını yazar; kaynağı açıkça işaretlenir."""
        teams = {t["id"]: t for t in self.store.select("teams") if t.get("stadium")}
        if not teams:
            return 0
        lo = to_iso(now_utc() - timedelta(days=7))
        rows = []
        for m in self.store.select("matches", [("kickoff_at", "gte", lo), ("venue", "is_null", True)]):
            t = teams.get(m["home_team_id"])
            if not t:
                continue
            src = dict(m.get("sources") or {})
            src["venue"] = "wikidata (ev sahibi stadı)" if (t.get("ext_ids") or {}).get("wikidata") else "thesportsdb (ev sahibi stadı)"
            mm = dict(m, venue=t["stadium"], city=m.get("city") or t.get("city"), sources=src)
            mm["missing_fields"] = [f for f in (m.get("missing_fields") or []) if f != "stadyum"]
            rows.append(mm)
        if rows:
            self.store.upsert("matches", rows)
        return len(rows)

    def save(self, merged: list[dict]) -> None:
        ts = to_iso(now_utc())
        match_rows, stat_rows, teams = [], [], {}
        for m in merged:
            row = {k: v for k, v in m.items() if k != "stats"}
            row["updated_at"] = ts
            row["durum"] = durum_for(m)
            row["score"] = f"{m['home_goals']}-{m['away_goals']}" if m.get("home_goals") is not None and m.get("away_goals") is not None else None
            row["missing_fields"] = missing_fields(m)
            match_rows.append(row)
            for side in ("home", "away"):
                st = m["stats"][side]
                if st:
                    stat_rows.append({"match_id": m["id"], "side": side, "team_id": m[f"{side}_team_id"],
                                      **{f: st.get(f) for f in STAT_FIELDS}, "source": "birlesik",
                                      "updated_at": ts})
                tid = m[f"{side}_team_id"]
                teams.setdefault(tid, {"id": tid, "league": m["league"], "name": m[f"{side}_name"],
                                       "updated_at": ts})
        existing_teams = {t["id"] for t in self.store.select("teams")}
        self.store.upsert("teams", [t for k, t in teams.items() if k not in existing_teams])
        self.store.upsert("matches", match_rows)
        self.store.upsert("match_stats", stat_rows)

    # ---------------------------------------------------------------- okuma
    def matches_between(self, start_iso: str, end_iso: str, leagues: list[str] | None = None) -> list[dict]:
        f = [("kickoff_at", "gte", start_iso), ("kickoff_at", "lt", end_iso)]
        if leagues:
            f.append(("league", "in", leagues))
        return self.store.select("matches", f, order="kickoff_at")

    def history(self, league: str, days: int = 760) -> tuple[list[dict], dict[str, dict]]:
        ms = self.store.select("matches", [("league", "eq", league), ("status", "eq", "bitti"),
                                           ("kickoff_at", "gte", to_iso(now_utc() - timedelta(days=days)))],
                               order="kickoff_at")
        stats = {}
        ids = [m["id"] for m in ms]
        for i in range(0, len(ids), 200):
            for s in self.store.select("match_stats", [("match_id", "in", ids[i:i + 200])]):
                stats.setdefault(s["match_id"], {})[s["side"]] = s
        return ms, stats

    # ---------------------------------------------------------------- zenginleştirme
    def team_info(self, team_id: str, name: str) -> dict:
        from .sources import open_meteo

        t = self.store.get("teams", id=team_id) or {"id": team_id, "league": team_id.split(":")[0], "name": name}
        if t.get("lat") is not None:
            return t
        changed = False
        try:
            info = self.tsdb.search_team(names.display_name(name)) or self.tsdb.search_team(name)
        except Exception:
            info = None
        if info:
            t["stadium"] = t.get("stadium") or info.get("stadium")
            t["city"] = t.get("city") or info.get("location")
            ext = dict(t.get("ext_ids") or {})
            ext["tsdb"] = info.get("tsdb_id")
            t["ext_ids"] = ext
            changed = True
        queries = []
        if t.get("city"):
            parts = [p.strip() for p in str(t["city"]).split(",") if p.strip()]
            queries += [p for p in reversed(parts[:3])][::-1]
        base = names.strip_accents(names.display_name(name))
        queries.append(base.replace("spor", "").replace("Spor", "").strip())
        for q in queries:
            try:
                g = open_meteo.geocode(q)
            except Exception:
                g = None
            if g:
                t["lat"], t["lon"] = g["lat"], g["lon"]
                t["city"] = t.get("city") or g["name"]
                changed = True
                break
        if changed:
            t["updated_at"] = to_iso(now_utc())
            self.store.upsert("teams", [t])
        return t

    def weather(self, match: dict, max_age_h: float = 6) -> dict | None:
        from .sources import open_meteo

        w = self.store.get("weather", match_id=match["id"])
        if w and (now_utc() - parse_dt(w["updated_at"])).total_seconds() < max_age_h * 3600:
            return w["data"]
        ko = parse_dt(match["kickoff_at"])
        if (ko - now_utc()).days > 15:
            return None
        t = self.team_info(match["home_team_id"], match["home_name"])
        if t.get("lat") is None:
            return None
        try:
            data = open_meteo.match_weather(t["lat"], t["lon"], match["kickoff_at"])
        except Exception as e:
            self._note("open-meteo", False, str(e))
            return w["data"] if w else None
        if data:
            data["location"] = t.get("city") or t.get("stadium")
            data["approx"] = "Ev sahibi takımın şehir koordinatı (stadyum noktası değil)"
            self.store.upsert("weather", [{"match_id": match["id"], "data": data, "source": "open-meteo",
                                           "updated_at": to_iso(now_utc())}])
        return data

    def squad_players(self, team_id: str, team_apif: int | None, season: int) -> list[dict]:
        cached = self.store.select("players", [("team_id", "eq", team_id)])
        fresh = cached and all(parse_dt(p["updated_at"]) > now_utc() - timedelta(days=4) for p in cached[:1])
        if fresh or not (self.apif.available and team_apif):
            return cached
        try:
            ps = self.apif.team_players(team_apif, season)
        except Exception as e:
            self._note("api-football", False, f"oyuncular: {e}")
            return cached
        ts = to_iso(now_utc())
        rows = [{"team_id": team_id, **p, "season": str(season), "source": "api-football", "updated_at": ts} for p in ps]
        self.store.upsert("players", rows)
        return rows

    def injuries(self, match: dict, max_age_h: float = 8) -> tuple[list[dict], bool]:
        """Döner: (sakat/cezalı listesi, veri_var_mı). Veri yoksa False — tahmin bunu not eder."""
        from .model.injuries import find_player, player_importance

        cached = self.store.select("injuries", [("match_id", "eq", match["id"])])
        fetched_ok = self.store.get("source_status", source=f"injuries:{match['id']}")
        if fetched_ok and (now_utc() - parse_dt(fetched_ok["updated_at"])).total_seconds() < max_age_h * 3600:
            return cached, True
        fid = (match.get("ext_ids") or {}).get("apif")
        if not (self.apif.available and fid):
            return cached, bool(fetched_ok)
        try:
            raw = self.apif.injuries(int(fid))
        except Exception as e:
            self._note("api-football", False, f"sakatlık: {e}")
            return cached, bool(fetched_ok)
        ko = parse_dt(match["kickoff_at"])
        season = ko.year if ko.month >= 7 else ko.year - 1
        ext = match.get("ext_ids") or {}
        rows = []
        for it in raw:
            side = "home" if it.get("team_apif") == ext.get("apif_home") else "away" \
                if it.get("team_apif") == ext.get("apif_away") else \
                ("home" if names.same_team(it.get("team_name") or "", match["home_name"]) else "away")
            tid = match[f"{side}_team_id"]
            players = self.squad_players(tid, ext.get(f"apif_{side}"), season)
            status = {"Missing Fixture": "kesin yok", "Questionable": "şüpheli"}.get(it.get("kind"), it.get("kind"))
            pl = find_player(it["player_name"], players)
            imp = player_importance(pl, players, status)
            rows.append({"id": f"{match['id']}:{it.get('player_id') or it['player_name']}", "match_id": match["id"],
                         "team_id": tid, "team_name": match[f"{side}_name"], "player_name": it["player_name"],
                         "injury_status": status, "reason": it.get("reason"),
                         "matches_played": (pl or {}).get("appearances"), "key_matches": (pl or {}).get("lineups"),
                         "goal_contribution": imp["ga_share"], "defensive_contribution": imp.get("defensive_share"),
                         "minutes_share": imp["minutes_share"], "weight_score": imp["importance"],
                         "is_key": imp["is_key"], "source": "api-football", "fetched_at": to_iso(now_utc())})
        self.store.upsert("injuries", rows)
        self.store.set_source_status(f"injuries:{match['id']}", True, f"{len(rows)} kayıt")
        return rows, True

    def lineups(self, match: dict) -> list[dict]:
        cached = self.store.select("lineups", [("match_id", "eq", match["id"])])
        if cached:
            return cached
        fid = (match.get("ext_ids") or {}).get("apif")
        ko = parse_dt(match["kickoff_at"])
        if not (self.apif.available and fid) or (ko - now_utc()).total_seconds() > 75 * 60:
            return []
        try:
            raw = self.apif.lineups(int(fid))
        except Exception as e:
            self._note("api-football", False, f"kadro: {e}")
            return []
        rows = []
        ext = match.get("ext_ids") or {}
        for it in raw:
            side = "home" if it.get("team_apif") == ext.get("apif_home") else "away"
            rows.append({"match_id": match["id"], "side": side, "formation": it.get("formation"),
                         "start_xi": it.get("start_xi"), "subs": it.get("subs"), "coach": it.get("coach"),
                         "source": "api-football", "updated_at": to_iso(now_utc())})
        self.store.upsert("lineups", rows)
        return rows

    def squad_list(self, team_id: str, name: str) -> list[dict]:
        t = self.team_info(team_id, name)
        tsdb_id = (t.get("ext_ids") or {}).get("tsdb")
        if not tsdb_id:
            return []
        try:
            return self.tsdb.squad(tsdb_id)
        except Exception:
            return []

    def fill_match_stats(self, match: dict) -> bool:
        """Bitmiş maçın eksik istatistiklerini API-Football'dan tamamlar (anahtar varsa)."""
        fid = (match.get("ext_ids") or {}).get("apif")
        if not (self.apif.available and fid):
            return False
        try:
            st = self.apif.statistics(int(fid))
        except Exception as e:
            self._note("api-football", False, f"istatistik: {e}")
            return False
        existing = {s["side"]: s for s in self.store.select("match_stats", [("match_id", "eq", match["id"])])}
        rows = []
        for side in ("home", "away"):
            cur = dict(existing.get(side) or {"match_id": match["id"], "side": side,
                                               "team_id": match[f"{side}_team_id"]})
            for f, v in (st.get(side) or {}).items():
                if cur.get(f) is None:
                    cur[f] = v
            cur["source"] = "birlesik"
            cur["updated_at"] = to_iso(now_utc())
            rows.append(cur)
        self.store.upsert("match_stats", rows)
        return True


def today_tr() -> date:
    from .timeutil import TR

    return now_utc().astimezone(TR).date()
