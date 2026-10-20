"""Birleşik veri havuzu.

Birden fazla kaynaktan gelen maç kayıtları tek havuzda birleştirilir:
* Aynı maç = aynı lig + iki takım eşleşiyor + başlama saatleri en fazla 36 saat farklı.
* Alan bazında doldurma: bir kaynakta eksik olan alan diğerinden tamamlanır; her alanın kökeni
  `sources` içinde saklanır. Skor çelişkisi varsa `_conflicts` listesine yazılır.
* Bir maç hiçbir koşulda havuzdan atılmaz; eksik alanlar "eksik" olarak işaretlenir.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from . import names
from .timeutil import now_utc, parse_dt, to_iso

# Alan bazında öncelik (ilk dolu değer kazanır; boşlar sıradaki kaynaktan dolar)
PRIORITY = ["api-football", "sportmonks", "football-data.org", "footystats", "sportdevs", "bsd", "openligadb",
            "the-odds-api", "oddspapi", "thesportsdb", "football-data.co.uk", "openfootball"]
# Görünen ad önceliği (mevcut adlar kararlı kalsın diye eski kaynaklar önde)
NAME_PRIORITY = ["thesportsdb", "api-football", "football-data.org", "sportmonks", "football-data.co.uk",
                 "footystats", "sportdevs", "openligadb", "the-odds-api", "oddspapi", "openfootball", "bsd"]
# Oran önceliği: çok şirketli ortalama > Pinnacle > CSV ortalaması > tekil kaynaklar
ODDS_PRIORITY = ["the-odds-api", "api-football", "oddspapi", "bsd", "football-data.co.uk", "footystats", "sportmonks"]
SCALARS = ["kickoff_at", "season", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals",
           "venue", "referee", "city"]
STAT_FIELDS = ["shots", "shots_on_target", "corners", "fouls", "yellow", "red", "goal_kicks", "xg", "possession"]
TSDB_DAY_LEAGUES = {"T1", "E0", "SP1", "I1", "D1", "F1"}
STATUS_RANK = {"planlandi": 1, "basladi": 2, "ertelendi": 3, "iptal": 3, "bitti": 4}


class TeamRegistry:
    """Lig bazında takım anahtarlarını tutar; farklı yazımları aynı takıma bağlar."""

    def __init__(self):
        self.keys: dict[str, dict[str, str]] = {}  # league -> {key: display name}
        self.alias: dict[str, dict[str, str]] = {}  # league -> {farklı yazımın anahtarı: takım anahtarı}
        self.learned: dict[str, dict[str, str]] = {}  # bu çalıştırmada fikstürden öğrenilenler

    def add(self, league: str, key: str, display: str, aliases: list | None = None) -> None:
        self.keys.setdefault(league, {}).setdefault(key, display)
        for a in aliases or []:
            ak = names.canonical_key(str(a))
            if ak and ak != key:
                self.alias.setdefault(league, {})[ak] = key

    def _alias(self, league: str, k: str) -> str:
        seen = set()
        while k in self.alias.get(league, {}) and k not in seen:
            seen.add(k)
            k = self.alias[league][k]
        return k

    def lookup(self, league: str, name: str) -> str | None:
        """resolve() gibi ama bilinmeyen adı EKLEMEZ (yalnızca boşluk dolduran kaynaklar için)."""
        k = self._alias(league, names.canonical_key(name))
        known = self.keys.get(league, {})
        if k in known:
            return k
        for kk in known:
            if names.same_team(k, kk):
                return kk
        return None

    def resolve(self, league: str, name: str) -> str:
        k = self._alias(league, names.canonical_key(name))
        known = self.keys.setdefault(league, {})
        if k in known:
            return k
        for kk in known:
            if names.same_team(k, kk):
                return kk
        known[k] = names.display_name(name)
        return k


def _similar(a: str, b: str) -> bool:
    """Fikstür eşleşmesi varken ad benzerliği için GEVŞEK ölçüt (ör. 'hearts' ~ 'heartofmidlothian',
    'spgijon' ~ 'sportinggijon', 'forsittard' ~ 'fortunasittard')."""
    import difflib

    if not a or not b:
        return False
    if a[:4] == b[:4] or a in b or b in a:
        return True
    sm = difflib.SequenceMatcher(None, a, b)
    lcs = sm.find_longest_match(0, len(a), 0, len(b)).size
    # ortak uzun parça (ör. 'sittard', 'gijon', 'braunschweig') ya da yüksek benzerlik + ortak parça
    return lcs >= 5 or (lcs >= 4 and sm.ratio() >= 0.6)


def learn_aliases(records: list[dict], reg: "TeamRegistry", existing: list[dict] | None = None) -> int:
    """Farklı kaynaklar aynı maçı farklı takım adlarıyla verdiğinde (ör. BSD 'Heart of Midlothian',
    football-data.co.uk 'Hearts') adları FİKSTÜRDEN eşler: aynı lig, aynı başlama saati (±3 sa) ve bir taraf aynı
    ise diğer taraf da aynı takımdır (ad gevşek benzerlik şartıyla). İki taraf da farklıysa saat ±15 dk ve iki ad
    çifti de benzer olmalı. Hedef anahtar: kayıtlarda/veritabanında daha çok görülen yazım. Öğrenilen eşlemeler
    takımın `aliases` alanına yazılır, sonraki çalıştırmalarda tek kaynak gelse bile aynı takıma bağlanır."""
    from collections import Counter, defaultdict

    def key(lg, name):
        return reg._alias(lg, names.canonical_key(name))

    rows = []
    for r in records:
        if r.get("kickoff_at") and r.get("home_name") and r.get("away_name"):
            ko = parse_dt(r["kickoff_at"])
            if ko is not None:
                rows.append((r["league"], ko, key(r["league"], r["home_name"]), key(r["league"], r["away_name"]),
                             r["source"]))
    for e in existing or []:
        ko = parse_dt(e["kickoff_at"])
        if ko is not None:
            rows.append((e["league"], ko, e["home_team_id"].split(":", 1)[1], e["away_team_id"].split(":", 1)[1], "_db"))
    freq = Counter()
    for lg, _, h, a, _src in rows:
        freq[(lg, h)] += 1
        freq[(lg, a)] += 1
    for lg, keys in reg.keys.items():
        for k in keys:
            freq[(lg, k)] += 5  # veritabanında olan anahtar tercih edilir
    by_day = defaultdict(list)
    for row in rows:
        by_day[(row[0], row[1].date())].append(row)
    votes = Counter()
    for (lg, _d), grp in by_day.items():
        for i, x in enumerate(grp):
            for y in grp[i + 1:]:
                if x[4] == y[4] or (x[2], x[3]) == (y[2], y[3]):
                    continue
                dt = abs((x[1] - y[1]).total_seconds())
                if dt > 3 * 3600:
                    continue
                pairs = []
                if x[2] == y[2] and x[3] != y[3]:
                    pairs = [(x[3], y[3])]
                elif x[3] == y[3] and x[2] != y[2]:
                    pairs = [(x[2], y[2])]
                elif x[2] != y[2] and x[3] != y[3]:  # iki taraf da farklı: iki ad çifti de benzer olmalı
                    pairs = [(x[2], y[2]), (x[3], y[3])]
                if pairs and all(_similar(a, b) for a, b in pairs):
                    for a, b in pairs:
                        votes[(lg, *sorted((a, b)))] += 1
    n = 0
    for (lg, a, b), _v in votes.most_common():
        a2, b2 = reg._alias(lg, a), reg._alias(lg, b)
        if a2 == b2:
            continue
        tgt, var = sorted((a2, b2), key=lambda k: (-freq[(lg, k)], len(k)))
        reg.alias.setdefault(lg, {})[var] = tgt
        reg.learned.setdefault(lg, {})[var] = tgt
        n += 1
    return n


def _prio(src: str, order: list[str]) -> int:
    return order.index(src) if src in order else len(order)


def _bucket_key(league: str, hk: str, ak: str) -> tuple:
    return (league, hk, ak)


def merge_records(records: list[dict], registry: TeamRegistry | None = None,
                  existing: list[dict] | None = None) -> list[dict]:
    """Kaynak kayıtlarını birleştirir. Dönen her öğe `matches` tablosuna yazılabilir bir sözlük + 'stats'."""
    reg = registry or TeamRegistry()
    run_ts = to_iso(now_utc())
    for e in existing or []:
        reg.add(e["league"], e["home_team_id"].split(":", 1)[1], e["home_name"])
        reg.add(e["league"], e["away_team_id"].split(":", 1)[1], e["away_name"])
    learn_aliases(records, reg, existing)
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
        fetched = m["sources"].setdefault("_fetched", {})  # alan → bu çalışmada çekildiği an (provenans)
        for f in SCALARS:
            v = r.get(f)
            if v is None or v == "":
                continue
            if m[f] is None:
                m[f] = to_iso(v) if f == "kickoff_at" else v
                m["sources"][f] = src
                fetched[f] = run_ts
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
                fetched[f"odds.{k}"] = run_ts
        for side in ("home", "away"):
            for f, v in ((r.get("stats") or {}).get(side) or {}).items():
                if v is not None and m["stats"][side].get(f) is None:
                    m["stats"][side][f] = v
                    m["sources"].setdefault("stats", {})[f"{side}.{f}"] = src
                    fetched[f"stats.{side}.{f}"] = run_ts

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
                elif f == "_fetched" and isinstance(v, dict):  # bu çalışmada çekilmeyen alanlar eski zamanını korur
                    m["sources"]["_fetched"] = {**v, **m["sources"]["_fetched"]}
        else:
            m["id"] = f"{m['league']}:{ko.date().isoformat()}:{hk}:{ak}"
        m["home_name"] = names.display_name(m["home_name"])
        m["away_name"] = names.display_name(m["away_name"])
        out.append(m)
    return out


DURUM = {"planlandi": "gelecek", "basladi": "canlı", "bitti": "bitti", "ertelendi": "ertelendi", "iptal": "iptal"}


LIVE_WINDOW = timedelta(hours=2, minutes=30)
APIF_DATE_REFRESH_H = 8  # API-Football tarih sorgusu en fazla 6 saatte bir (günlük 100 istek bütçesi)


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
        from .sources.bsd import BSD
        from .sources.thesportsdb import TheSportsDB
        from .teamnews import TeamNews

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
        self.bsd = BSD(getattr(settings, "bsd_api_key", None), getattr(settings, "bsd_max_calls", 1200))
        self.log: list[str] = []
        self.news = TeamNews(self)

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
        self._job(source, ok, msg)

    # Çekme işi kuyruğu: hata → üstel geri çekilme (2, 4, 8 … saat, en çok 24); 3 hatadan sonra kaynak alanlarını
    # öncelik sırasındaki sonraki kaynaklara DEVREDER (birleştirme zaten bir sonraki kaynağı kullanır; bu kayıt
    # devri görünür kılar ve geri çekilme süresince kotalı kaynağa boşuna istek atılmasını önler).
    def _job(self, source: str, ok: bool, msg: str) -> None:
        if source.startswith(("injuries:", "gecmis:", "api-football:tarih:")):
            return
        try:
            cur = self.store.get("fetch_jobs", id=source) or {"id": source, "source": source, "attempts": 0}
            now = now_utc()
            if ok:
                if cur.get("status") in (None, "tamam") and cur.get("attempts", 0) == 0:
                    return  # gereksiz yazma yok
                row = dict(cur, attempts=0, status="tamam", next_try_at=None, last_error=None, updated_at=to_iso(now))
            else:
                n = int(cur.get("attempts") or 0) + 1
                fb = [s for s in PRIORITY if s != source][:3]
                row = dict(cur, attempts=n, status="devredildi" if n >= 3 else "tekrar",
                           next_try_at=to_iso(now + timedelta(hours=min(24, 2 ** n))), last_error=str(msg)[:300],
                           fallback=", ".join(fb) if n >= 3 else None, updated_at=to_iso(now))
            self.store.upsert("fetch_jobs", [row])
        except Exception:
            pass  # fetch_jobs tablosu yoksa sessizce geç

    def backoff(self, source: str) -> bool:
        """Kaynak geri çekilmedeyse True (bu çalışmada atlanır)."""
        try:
            j = self.store.get("fetch_jobs", id=source)
        except Exception:
            return False
        return bool(j and j.get("status") != "tamam" and j.get("next_try_at")
                    and parse_dt(j["next_try_at"]) > now_utc())

    # ---------------------------------------------------------------- toplama
    def collect(self, days_back: int = 3, days_ahead: int = 7, history: bool = False) -> list[dict]:
        from .sources import football_data_co_uk as fdcuk

        today = now_utc().date()
        recs: list[dict] = []
        leagues = self.s.leagues
        if history:
            code = fdcuk.season_code(today)  # yalnızca güncel sezon CSV'si (geçmiş sezon çekilmez)
            from .config import LEAGUES

            for lg in leagues:
                if lg in LEAGUES and not LEAGUES[lg].fdcuk:
                    continue  # football-data.co.uk'ta bu ligin CSV'si yok (kupa / TFF 1. Lig)
                for c in (code,):
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
        from .config import LEAGUES

        n = 0
        # Ücretsiz anahtar dakikada ~30 istek: günlük liste (lig başına gün başına 1 istek) yalnızca çekirdek liglerde;
        # BSD kapsamı olmayan liglerde (TFF 1. Lig) tam hafta listesi (eventsround) kullanılır.
        day_lgs = [lg for lg in leagues if lg in TSDB_DAY_LEAGUES]
        for i in range(-min(days_back, 1), min(days_ahead, 1) + 1):
            d = today + timedelta(days=i)
            try:
                rows = self.tsdb.events_day(d, day_lgs)
                recs += rows
                n += len(rows)
            except Exception as e:
                self._note("thesportsdb", False, f"{d}: {e}")
                break
        for lg in leagues:
            if lg in LEAGUES and LEAGUES[lg].bsd_id is None and LEAGUES[lg].tsdb_id:
                try:
                    rows = self.tsdb.events_rounds(lg)
                    recs += rows
                    n += len(rows)
                except Exception as e:
                    self._note("thesportsdb", False, f"{lg} hafta listesi: {e}")
        self._note("thesportsdb", True, f"{n} maç (günlük liste + hafta listesi)")
        if self.fdorg.available and self.backoff("football-data.org"):
            self.log.append("⏸️ football-data.org: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.fdorg.available:
            try:
                rows = self.fdorg.matches(today - timedelta(days=days_back), today + timedelta(days=days_ahead), leagues)
                recs += rows
                self._note("football-data.org", True, f"{len(rows)} maç")
            except Exception as e:
                self._note("football-data.org", False, str(e))
        else:
            self._waiting_key("football-data.org", "FOOTBALL_DATA_TOKEN", "fikstür/sonuç/hakem (büyük Avrupa ligleri)")
        if self.apif.available and self.apif.season_blocked(today.year if today.month >= 7 else today.year - 1):
            # Ücretsiz plan: sezonluk sorgu kapalı ama dün/bugün/yarın tarih sorgusu açık (tek istekte tüm ligler).
            n_fx = 0
            for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
                key = f"api-football:tarih:{d.isoformat()}"
                st = self.store.get("source_status", source=key) or {}
                if st.get("ok") and st.get("updated_at") and \
                        now_utc() - parse_dt(st["updated_at"]) < timedelta(hours=APIF_DATE_REFRESH_H):
                    continue
                try:
                    rows = self.apif.fixtures_by_date(d, leagues)
                    recs += rows
                    n_fx += len(rows)
                    self.store.set_source_status(key, True, f"{len(rows)} maç")
                except Exception as e:
                    self._note("api-football", False, f"{d}: {e}")
                    break
            self.log.append(f"ℹ️ api-football: güncel sezon sezonluk sorguya kapalı; dün/bugün/yarın tarih sorgusuyla "
                            f"{n_fx} maç eşleştirildi (fikstür kimliği → sakat/cezalı ve ilk 11)")
        elif self.apif.available:
            season = today.year if today.month >= 7 else today.year - 1
            for lg in leagues:
                if lg not in LEAGUES or not LEAGUES[lg].apif_id:
                    continue
                try:
                    rows = self.apif.fixtures(lg, season, today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                    recs += rows
                    self._note("api-football", True, f"{lg}: {len(rows)} maç")
                except Exception as e:
                    self._note("api-football", False, f"{lg}: {e}")
                    break
        else:
            self._waiting_key("api-football", "API_FOOTBALL_KEY", "ilk 11, sakat/cezalı, oyuncu dakikaları, hakem, maç istatistiği")
        if self.oddsapi.available and self.backoff("the-odds-api"):
            self.log.append("⏸️ the-odds-api: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.oddsapi.available:
            # Ücretsiz plan 500 kredi/ay; lig çağrısı 2 kredi (h2h+totals, tek bölge). Günlük çağrı bütçesi
            # ODDS_API_DAILY_CALLS (varsayılan 8 → ~480 kredi/ay); önce 36 saat içinde maçı olan, oranı eksik ligler.
            import os

            from .sources.odds_api import SPORT_KEYS

            budget = int(float(os.environ.get("ODDS_API_DAILY_CALLS", "8")))
            try:
                st = self.store.get("source_status", source="the-odds-api:kota") or {}
                used = int(st.get("calls_today") or 0) if st.get("calls_date") == now_utc().date().isoformat() else 0
            except Exception:
                used = 0
            soon = self.store.select("matches", [("kickoff_at", "gte", to_iso(now_utc())),
                                                 ("kickoff_at", "lt", to_iso(now_utc() + timedelta(hours=36)))])
            need: dict = {}
            for m in soon:
                if m["league"] in SPORT_KEYS and m["league"] in leagues:
                    need[m["league"]] = need.get(m["league"], 0) + (2 if not (m.get("odds") or {}).get("1X2") else 1)
            order = sorted(need, key=lambda lg: -need[lg])
            done_today = set((st.get("message") or "").split(",")) if used else set()
            order = [lg for lg in order if lg not in done_today][:max(0, budget - used)]
            if not order:
                self.log.append(f"ℹ️ the-odds-api: günlük bütçe ({budget} çağrı) kullanıldı ya da 36 saatte desteklenen maç yok")
            for lg in order:
                try:
                    rows, info = self.oddsapi.odds(lg)
                    recs += rows
                    done_today.add(lg)
                    self._note("the-odds-api", True, f"{lg}: {len(rows)} maç oranı ({info})")
                    self.store.set_source_status("the-odds-api:kota", True, ",".join(sorted(x for x in done_today if x)),
                                                 add_calls=1)
                except Exception as e:
                    self._note("the-odds-api", False, f"{lg}: {e}")
                    break
        else:
            self._waiting_key("the-odds-api", "ODDS_API_KEY", "çok şirketli 1X2/Alt-Üst oranları")
        if self.bsd.available:
            try:
                rows = self.bsd.events(today - timedelta(days=days_back), today + timedelta(days=days_ahead), leagues,
                                       known=self._bsd_known(today - timedelta(days=days_back)),
                                       odds_hours=getattr(self.s, "bsd_odds_hours", 48.0))
                recs += rows
                self._note("bsd", True, f"{len(rows)} maç (sakat/cezalı ve ilk 11 için eşleştirme)", calls=1)
            except Exception as e:
                self._note("bsd", False, str(e))
        else:
            self._waiting_key("bsd", "BSD_API_KEY", "maç başına sakat/cezalı listesi, resmî ve tahmini ilk 11, kadro uygunluğu")
        self._collect_extra(recs, today, days_back, days_ahead, history)
        return recs

    def _bsd_known(self, d_from) -> dict:
        """Havuzda hakem/stadyum/istatistiği zaten olan BSD maçları: aynı bilgi BSD'den yeniden istenmez (kota)."""
        try:
            ms = self.store.select("matches", [("kickoff_at", "gte", to_iso(datetime.combine(d_from, datetime.min.time(),
                                                                                         tzinfo=timezone.utc)))])
        except Exception:
            return {}
        with_stats: set = set()
        fin = [m["id"] for m in ms if m.get("status") == "bitti"]
        for i in range(0, len(fin), 200):
            try:
                with_stats |= {r["match_id"] for r in self.store.select("match_stats", [("match_id", "in", fin[i:i + 200])])}
            except Exception:
                break
        out = {}
        for m in ms:
            eid = (m.get("ext_ids") or {}).get("bsd")
            if eid:
                out[eid] = {"referee": m.get("referee"), "venue": m.get("venue"), "city": m.get("city"),
                            "stats": m["id"] in with_stats}
        return out

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
        if self.sportmonks.available and self.backoff("sportmonks"):
            self.log.append("⏸️ sportmonks: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.sportmonks.available:
            try:
                rows = self.sportmonks.fixtures(leagues, today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                recs += rows
                self._note("sportmonks", True, f"{len(rows)} maç (abonelikteki ligler)", calls=1)
            except Exception as e:
                self._note("sportmonks", False, str(e))
        else:
            self._waiting_key("sportmonks", "SPORTMONKS_KEY", "fikstür/sonuç/stadyum/hakem/istatistik")
        if self.footystats.available and self.backoff("footystats"):
            self.log.append("⏸️ footystats: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.footystats.available:
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
        if self.sportdevs.available and self.backoff("sportdevs"):
            self.log.append("⏸️ sportdevs: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.sportdevs.available:
            try:
                rows = self.sportdevs.matches(today - timedelta(days=days_back), today + timedelta(days=days_ahead))
                recs += rows
                self._note("sportdevs", True, f"{len(rows)} maç", calls=1)
            except Exception as e:
                self._note("sportdevs", False, str(e))
        else:
            self._waiting_key("sportdevs", "SPORTDEVS_KEY", "fikstür/sonuç/İY skoru")
        if self.oddspapi.available and self.backoff("oddspapi"):
            self.log.append("⏸️ oddspapi: geri çekilmede (son hatalardan sonra); alanlar sıradaki kaynaktan doluyor")
        elif self.oddspapi.available:
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

    def refresh(self, days_back: int = 3, days_ahead: int = 7, history: bool = False) -> dict:
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
            from .analysis import season_start

            existing = self.store.select("matches", [("kickoff_at", "gte", to_iso(season_start() - timedelta(days=2)))])
        reg = TeamRegistry()
        teams_all = self.store.select("teams")
        for t in teams_all:
            reg.add(t["league"], t["id"].split(":", 1)[1], t["name"], t.get("aliases"))
        merged = merge_records(recs, reg, existing)
        self._save_learned_aliases(reg, teams_all)
        if getattr(reg, "unmatched", None):
            self.log.append(f"ℹ️ boşluk dolduran kaynaklarda eşleşmeyen {len(reg.unmatched)} kayıt atlandı "
                            f"(ör. {', '.join(reg.unmatched[:3])})")
        self.save(merged)
        try:
            self.enrich_teams()
        except Exception as e:
            self._note("wikidata", False, str(e))
        self.fill_venues()
        try:
            self.apif_odds()
        except Exception as e:
            self._note("api-football:oran", False, str(e))
        try:
            n_snap = self.snapshot_odds()
            if n_snap:
                self.log.append(f"ℹ️ oran anlık görüntüsü: {n_snap} maç (kapanış oranı / CLV için)")
        except Exception as e:
            self.log.append(f"⚠️ oran anlık görüntüsü yazılamadı: {e}")
        return {"records": len(recs), "matches": len(merged), "log": list(self.log),
                "unmatched": list(getattr(reg, "unmatched", []))}

    def apif_odds(self) -> int:
        """API-Football /odds?date= (bugün + yarın, tarih başına günde bir kez, ~15 sayfa): 9 şirketin medyanı;
        1X2, çifte şans, Asya handikap, gol A/Ü, İY gol, takım golü, KG, korner, kart, isabetli şut. Fikstür kimliği
        (ext_ids.apif) olan maçlara yazılır; daha öncelikli kaynağın aynı pazar oranı korunur."""
        if not self.apif.available or self.backoff("api-football"):
            return 0
        from .sources.api_football import SOURCE as APIF

        today = now_utc().date()
        n = 0
        for d in (today, today + timedelta(days=1)):
            key = f"api-football:oran:{d.isoformat()}"
            st = self.store.get("source_status", source=key) or {}
            fresh = st.get("ok") and st.get("calls_date") == today.isoformat()
            if fresh and d == today:
                continue  # bugünün oranı bu gün zaten alındı
            if fresh and d > today and int(st.get("calls_today") or 0) >= 2:
                continue  # yarın için günde en çok iki tur (gece + sabah)
            if self.apif.daily_budget - self.apif.calls_today() < 25:
                self.log.append("ℹ️ api-football oranları: günlük bütçe azaldı, atlandı")
                break
            by_fx = self.apif.odds_by_date(d)
            lo = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) - timedelta(hours=4)
            ms = self.store.select("matches", [("kickoff_at", "gte", to_iso(lo)),
                                               ("kickoff_at", "lt", to_iso(lo + timedelta(hours=32)))])
            rows = []
            for m in ms:
                fid = (m.get("ext_ids") or {}).get("apif")
                o = by_fx.get(int(fid)) if fid else None
                if not o or m.get("status") not in ("planlandi", None):
                    continue
                cur = dict(m.get("odds") or {})
                srcs = dict(m.get("sources") or {})
                so = dict(srcs.get("odds") or {})
                changed = False
                for k, v in o.items():
                    if k not in cur or _prio(APIF, ODDS_PRIORITY) <= _prio(so.get(k) or "", ODDS_PRIORITY):
                        cur[k], so[k], changed = v, APIF, True
                if changed:
                    srcs["odds"] = so
                    rows.append({"id": m["id"], "odds": cur, "sources": srcs})
            for r in rows:
                self.store.update("matches", {"odds": r["odds"], "sources": r["sources"]}, [("id", "eq", r["id"])])
            n += len(rows)
            mk = sorted({k.split("_")[0] if not k.startswith(("OU_", "HT_", "TEAM_", "CORNERS_", "CARDS_", "SOT_"))
                         else k.rsplit("_", 1)[0] for o in by_fx.values() for k in o})
            self.store.set_source_status(key, True, f"{len(by_fx)} fikstür oranı, {len(rows)} maçımıza yazıldı", add_calls=1)
            self._note("api-football:oran", True, f"{d}: {len(by_fx)} fikstür, {len(rows)} maçımız; pazarlar: {', '.join(mk)}")
        return n

    def snapshot_odds(self, hours: float = 30) -> int:
        """Başlamasına ≤ hours kalan maçların oranlarını odds_snapshots'a yazar (değişmediyse yazmaz).
        Çalışmalar 2 saatte bir olduğundan son görüntü başlama saatine en fazla ~2 saat uzaktır → kapanış oranı."""
        now = now_utc()
        ms = self.store.select("matches", [("kickoff_at", "gte", to_iso(now)),
                                           ("kickoff_at", "lte", to_iso(now + timedelta(hours=hours)))])
        rows = []
        for m in ms:
            odds = {k: v for k, v in (m.get("odds") or {}).items() if isinstance(v, dict) and not k.endswith("_closing")}
            if not odds or m.get("status") not in ("planlandi", None):
                continue
            last = self.store.select("odds_snapshots", [("match_id", "eq", m["id"])], order="taken_at", desc=True, limit=1)
            if last and last[0].get("odds") == odds:
                continue
            rows.append({"match_id": m["id"], "taken_at": to_iso(now), "kickoff_at": m["kickoff_at"], "odds": odds})
        if rows:
            self.store.upsert("odds_snapshots", rows)
        return len(rows)

    def _save_learned_aliases(self, reg: "TeamRegistry", teams_all: list[dict]) -> None:
        """Fikstürden öğrenilen ad eşlemelerini hedef takımın aliases listesine ekler (silme yapılmaz)."""
        if not reg.learned:
            return
        by_id = {t["id"]: t for t in teams_all}
        rows = []
        for lg, mp in reg.learned.items():
            tgt_vars: dict[str, list[str]] = {}
            for var, tgt in mp.items():
                tgt_vars.setdefault(reg._alias(lg, tgt), []).append(var)
            for tgt, vars_ in tgt_vars.items():
                tid = f"{lg}:{tgt}"
                t = by_id.get(tid)
                if not t:
                    continue  # takım bu çalıştırmada yeni yazılıyor; sonraki çalıştırma da aynı eşlemeyi öğrenir
                cur = list(t.get("aliases") or [])
                add = [v for v in vars_ if v not in cur]
                if add:
                    rows.append(dict(t, aliases=cur + add))
        if rows:
            self.store.upsert("teams", rows)
            self.log.append(f"ℹ️ fikstürden {sum(len(v) for v in reg.learned.values())} takım adı eşlemesi öğrenildi")

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

    def history(self, league: str) -> tuple[list[dict], dict[str, dict]]:
        """Ligin BU SEZON biten maçları ve istatistikleri (model girdisi yalnızca güncel sezondur)."""
        from .analysis import season_start

        ms = self.store.select("matches", [("league", "eq", league), ("status", "eq", "bitti"),
                                           ("kickoff_at", "gte", to_iso(season_start()))],
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

    def squad_players(self, team_id: str, team_apif: int | None = None, season: int | None = None) -> list[dict]:
        """Takımın güncel oyuncu listesi (Wikipedia/BSD kadrosu + API-Football geçmiş istatistiği)."""
        return self.news.team_players(team_id)

    def injuries(self, match: dict, max_age_h: float = 8) -> tuple[list[dict], bool]:
        """Döner: (sakat/cezalı listesi, veri_var_mı). Kaynaklar: BSD, API-Football, SportDevs (bkz. teamnews)."""
        return self.news.injuries(match, max_age_h)

    def lineups(self, match: dict) -> list[dict]:
        """İlk 11: resmî (BSD/API-Football/SportDevs/TheSportsDB) → yoksa BSD tahmini."""
        return self.news.lineups(match)

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
