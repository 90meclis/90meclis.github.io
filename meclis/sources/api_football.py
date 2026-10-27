"""API-Football (api-sports.io) v3 — API_FOOTBALL_KEY gerekir.
Ücretsiz plan (19.10.2026'da canlı doğrulandı):
  * sezon parametreli sorgular yalnızca 2022–2024 için açık (güncel sezon: "Free plans do not have access to this
    season") → kapalı sezon `source_status` içinde 'api-football:sezon:<yıl>' olarak işaretlenir, 7 gün istek atılmaz;
  * tarih parametreli sorgular yalnızca DÜN–BUGÜN–YARIN için açık (/fixtures?date=, /injuries?date=) → güncel sezonun
    fikstür kimlikleri ve sakat/cezalı listesi bu pencereden gelir;
  * fikstür kimliğiyle sorgular güncel sezonda da çalışır (/injuries?fixture=, /fixtures/lineups?fixture=);
  * `page` parametresi en fazla 3.
Günlük bütçenin kalanı geçmiş veri doldurmaya gider (bkz. meclis/backfill.py).
Sağladıkları: fikstür, istatistik, kadro (ilk 11), sakat/cezalı listesi, oyuncu istatistikleri, oranlar."""
from __future__ import annotations

import time
from datetime import date, timedelta

from ..config import APIF_TO_LEAGUE
from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "api-football"
BASE = "https://v3.football.api-sports.io"

_STATUS = {"TBD": "planlandi", "NS": "planlandi", "1H": "basladi", "HT": "basladi", "2H": "basladi",
           "ET": "basladi", "BT": "basladi", "P": "basladi", "LIVE": "basladi", "INT": "basladi",
           "FT": "bitti", "AET": "bitti", "PEN": "bitti", "AWD": "bitti", "WO": "bitti",
           "PST": "ertelendi", "SUSP": "ertelendi", "CANC": "iptal", "ABD": "iptal"}

_STAT_MAP = {"Shots on Goal": "shots_on_target", "Total Shots": "shots", "Corner Kicks": "corners",
             "Fouls": "fouls", "Yellow Cards": "yellow", "Red Cards": "red", "Goal Kicks": "goal_kicks",
             "expected_goals": "xg", "Ball Possession": "possession"}


SEASON_BLOCK_DAYS = 7
MIN_INTERVAL = 6.5  # dakikada 10 istek sınırı


def season_of(d) -> int:
    """API-Football sezon yılı (Avrupa ligleri: Temmuz'dan itibaren yeni sezon)."""
    return d.year if d.month >= 7 else d.year - 1


def is_season_block(msg: str) -> bool:
    m = (msg or "").lower()
    return "do not have access to this season" in m or ("free plan" in m and "season" in m)


ODDS_RESERVE = 30  # günlük bütçenin oran çağrılarına ayrılan kısmı


class ApiFootball:
    _last = 0.0

    def __init__(self, key: str | None, store=None, daily_budget: int = 90):
        self.key = key
        self.store = store
        self.daily_budget = daily_budget

    # ------------------------------------------------------------ sezon erişimi
    def season_blocked(self, season: int) -> bool:
        """Bu sezon ücretsiz planda kapalı olarak işaretlendi mi (son 7 gün içinde)?"""
        if not self.store:
            return False
        from ..timeutil import now_utc, parse_dt

        try:
            st = self.store.get("source_status", source=f"api-football:sezon:{season}")
        except Exception:
            return False
        if not st or st.get("ok"):
            return False
        ts = parse_dt(st.get("updated_at"))
        return bool(ts and now_utc() - ts < timedelta(days=SEASON_BLOCK_DAYS))

    def _mark_season(self, season: int, msg: str) -> None:
        if self.store:
            try:
                self.store.set_source_status(f"api-football:sezon:{season}", False,
                                             f"Ücretsiz plan bu sezonu kapsamıyor: {msg}")
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return bool(self.key)

    def calls_today(self) -> int:
        if not self.store:
            return 0
        from ..timeutil import now_utc

        st = self.store.get("source_status", source=SOURCE) or {}
        return int(st.get("calls_today") or 0) if st.get("calls_date") == now_utc().date().isoformat() else 0

    def _get(self, path: str, params: dict) -> list:
        if not self.key:
            raise SourceError("API_FOOTBALL_KEY tanımlı değil.")
        used = self.calls_today()
        if used >= self.daily_budget:
            raise SourceError(f"Günlük API-Football bütçesi doldu ({self.daily_budget} istek).")
        if path != "/odds" and used >= self.daily_budget - ODDS_RESERVE:
            # oran (pazar karşılaştırması) önceliklidir: diğer işler son ODDS_RESERVE isteğe dokunamaz
            raise SourceError(f"API-Football: kalan {self.daily_budget - used} istek oranlara ayrıldı")
        wait = ApiFootball._last + MIN_INTERVAL - time.monotonic()
        if wait > 0 and ApiFootball._last:
            time.sleep(wait)
        ApiFootball._last = time.monotonic()
        r = get(f"{BASE}{path}", params=params, headers={"x-apisports-key": self.key})
        if self.store:
            self.store.set_source_status(SOURCE, r.status_code == 200, f"{path} -> {r.status_code}", add_calls=1)
        if r.status_code != 200:
            raise SourceError(f"API-Football HTTP {r.status_code}")
        data = r.json()
        errs = data.get("errors")
        if errs:
            msg = "; ".join(f"{k}: {v}" for k, v in errs.items()) if isinstance(errs, dict) else str(errs)
            if self.store:
                self.store.set_source_status(SOURCE, False, msg)
            if is_season_block(msg) and params.get("season"):
                self._mark_season(int(params["season"]), msg)
            raise SourceError(f"API-Football: {msg}")
        self._paging = data.get("paging") or {}
        return data.get("response") or []

    def _get_season(self, path: str, params: dict) -> list:
        season = params.get("season")
        if season and self.season_blocked(int(season)):
            raise SourceError(f"API-Football: {season} sezonu ücretsiz planda kapalı (istek atılmadı)")
        return self._get(path, params)

    def fixtures(self, league: str, season: int, date_from: date, date_to: date) -> list[dict]:
        from ..config import LEAGUES

        lg = LEAGUES[league]
        out = []
        rows = self._get_season("/fixtures", {"league": lg.apif_id, "season": season,
                                              "from": date_from.isoformat(), "to": date_to.isoformat()})
        return [parse_fixture(f, league, season) for f in rows]

    def fixtures_by_date(self, d: date, leagues: list[str] | None = None) -> list[dict]:
        """O tarihteki TÜM maçlar tek istekte (ücretsiz plan: dün/bugün/yarın), bizim liglerimize süzülür."""
        out = []
        for f in self._get("/fixtures", {"date": d.isoformat()}):
            lg = APIF_TO_LEAGUE.get((f.get("league") or {}).get("id"))
            if lg and (not leagues or lg in leagues):
                out.append(parse_fixture(f, lg, (f.get("league") or {}).get("season") or season_of(d)))
        return out

    def injuries_by_date(self, d: date) -> list[dict]:
        """O tarihteki tüm maçların sakat/cezalı listesi tek istekte (ücretsiz plan: dün/bugün/yarın)."""
        out = []
        for it in self._get("/injuries", {"date": d.isoformat()}):
            if (it.get("league") or {}).get("id") not in APIF_TO_LEAGUE:
                continue
            p, t, fx = it.get("player") or {}, it.get("team") or {}, it.get("fixture") or {}
            out.append({"player_name": p.get("name"), "player_id": p.get("id"), "team_apif": t.get("id"),
                        "team_name": t.get("name"), "kind": p.get("type"), "reason": p.get("reason"),
                        "fixture_apif": fx.get("id")})
        return out

    def season_fixtures(self, league: str, season: int) -> list[dict]:
        """Bir lig-sezonun TÜM maçları tek istekte (geçmiş veri doldurma)."""
        from ..config import LEAGUES

        rows = self._get_season("/fixtures", {"league": LEAGUES[league].apif_id, "season": season})
        return [parse_fixture(f, league, season) for f in rows]

    def season_injuries(self, league: str, season: int) -> list[dict]:
        """Bir lig-sezonun tüm sakat/cezalı kayıtları tek istekte (fikstür kimliğiyle)."""
        from ..config import LEAGUES

        out = []
        for it in self._get_season("/injuries", {"league": LEAGUES[league].apif_id, "season": season}):
            p, t, fx = it.get("player") or {}, it.get("team") or {}, it.get("fixture") or {}
            out.append({"player_name": p.get("name"), "player_id": p.get("id"), "team_apif": t.get("id"),
                        "team_name": t.get("name"), "kind": p.get("type"), "reason": p.get("reason"),
                        "fixture_apif": fx.get("id"), "date": fx.get("date")})
        return out

    def team_players_page(self, team_apif: int, season: int, page: int) -> tuple[list[dict], int]:
        """Takım-sezon oyuncu istatistikleri (sayfa başına 20). Döner: (oyuncular, toplam_sayfa)."""
        res = self._get_season("/players", {"team": team_apif, "season": season, "page": page})
        total = int((getattr(self, "_paging", {}) or {}).get("total") or page)
        return [parse_player(it, team_apif=team_apif) for it in res], total

    def league_players_page(self, league: str, season: int, page: int) -> tuple[list[dict], int]:
        """Lig-sezon oyuncu istatistikleri (sayfa başına 20). Döner: (oyuncular, toplam_sayfa)."""
        from ..config import LEAGUES

        res = self._get_season("/players", {"league": LEAGUES[league].apif_id, "season": season, "page": page})
        total = int((getattr(self, "_paging", {}) or {}).get("total") or page)
        return [parse_player(it, LEAGUES[league].apif_id) for it in res], total

    def statistics(self, fixture_id: int) -> dict:
        res = self._get("/fixtures/statistics", {"fixture": fixture_id})
        out = {}
        for i, block in enumerate(res[:2]):
            side = "home" if i == 0 else "away"
            vals = {}
            for s in block.get("statistics", []):
                k = _STAT_MAP.get(s.get("type"))
                v = s.get("value")
                if k and v is not None:
                    if isinstance(v, str):
                        v = v.replace("%", "")
                    try:
                        vals[k] = float(v) if k in ("xg", "possession") else int(float(v))
                    except ValueError:
                        pass
            out[side] = vals
        return out

    def injuries(self, fixture_id: int) -> list[dict]:
        """Fikstür kimliğiyle sakat/cezalı (ücretsiz planda güncel sezonda da açık)."""
        out = []
        for it in self._get("/injuries", {"fixture": fixture_id}):
            p, t = it.get("player") or {}, it.get("team") or {}
            out.append({"player_name": p.get("name"), "player_id": p.get("id"), "team_apif": t.get("id"),
                        "team_name": t.get("name"), "kind": p.get("type"), "reason": p.get("reason")})
        return out

    def lineups(self, fixture_id: int) -> list[dict]:
        """Fikstür kimliğiyle resmî ilk 11 (ücretsiz planda güncel sezonda da açık; maçtan ~20-40 dk önce gelir)."""
        out = []
        for it in self._get("/fixtures/lineups", {"fixture": fixture_id}):
            out.append({
                "team_apif": (it.get("team") or {}).get("id"), "team_name": (it.get("team") or {}).get("name"),
                "formation": it.get("formation"), "coach": (it.get("coach") or {}).get("name"),
                "start_xi": [{"name": x["player"]["name"], "number": x["player"].get("number"),
                              "pos": x["player"].get("pos"),
                              **({"grid": x["player"]["grid"]} if x["player"].get("grid") else {})}
                             for x in it.get("startXI", [])],
                "subs": [{"name": x["player"]["name"], "number": x["player"].get("number"),
                          "pos": x["player"].get("pos")} for x in it.get("substitutes", [])],
            })
        return out

    def fixture_players(self, fixture_id: int) -> list[dict]:
        """Fikstür kimliğiyle oyuncu dakikaları (güncel sezonda fikstür bazlı uç noktalar açık)."""
        out = []
        for blk in self._get("/fixtures/players", {"fixture": fixture_id}):
            tid = (blk.get("team") or {}).get("id")
            for it in blk.get("players") or []:
                p = it.get("player") or {}
                st = ((it.get("statistics") or [{}])[0]) or {}
                g, gl = st.get("games") or {}, st.get("goals") or {}
                out.append({"team_apif": tid, "player_id": p.get("id"), "name": p.get("name"),
                            "position": g.get("position"), "started": g.get("substitute") is False,
                            "minutes": int(g.get("minutes") or 0), "goals": int(gl.get("total") or 0),
                            "assists": int(gl.get("assists") or 0), "rating": g.get("rating")})
        return out

    def team_players(self, team_apif: int, season: int, max_pages: int = 2) -> list[dict]:
        out = []
        for page in range(1, max_pages + 1):
            res = self._get_season("/players", {"team": team_apif, "season": season, "page": page})
            for it in res:
                p = it.get("player") or {}
                st = (it.get("statistics") or [{}])[0]
                games, goals = st.get("games") or {}, st.get("goals") or {}
                out.append({"player_key": str(p.get("id")), "name": p.get("name"), "position": games.get("position"),
                            "minutes": games.get("minutes") or 0, "appearances": games.get("appearences") or 0,
                            "lineups": games.get("lineups") or 0, "goals": goals.get("total") or 0,
                            "assists": goals.get("assists") or 0})
            if len(res) < 20:
                break
        return out


def parse_fixture(f: dict, league: str, season: int) -> dict:
    fx, teams, goals, score = f["fixture"], f["teams"], f.get("goals") or {}, f.get("score") or {}
    ht = score.get("halftime") or {}
    status = _STATUS.get((fx.get("status") or {}).get("short"), "planlandi")
    if status not in ("bitti", "basladi"):  # planlı maçta skor yazılmaz
        goals, ht = {}, {}
    return {
        "source": SOURCE, "league": APIF_TO_LEAGUE.get((f.get("league") or {}).get("id"), league),
        "kickoff_at": to_iso(fx.get("date")), "season": str(season),
        "home_name": teams["home"]["name"], "away_name": teams["away"]["name"],
        "status": status,
        "home_goals": goals.get("home"), "away_goals": goals.get("away"),
        "ht_home_goals": ht.get("home"), "ht_away_goals": ht.get("away"),
        "referee": fx.get("referee"), "venue": (fx.get("venue") or {}).get("name"),
        "city": (fx.get("venue") or {}).get("city"),
        "ext_ids": {"apif": fx.get("id"), "apif_home": teams["home"]["id"], "apif_away": teams["away"]["id"]},
    }


def parse_player(it: dict, apif_league: int | None = None, team_apif: int | None = None) -> dict:
    """/players yanıt öğesi → oyuncu satırı.

    team_apif verilirse YALNIZCA o takımın lig bloğu kullanılır: API-Football takım sorgusunda o takımın bugünkü
    oyuncularını da döndürüp başka kulüpteki istatistiğini ekleyebiliyor (ör. sonradan transfer olan kaleci); o
    takımda bloğu olmayan oyuncunun istatistiği boş (None) bırakılır — önem puanında "bilinmiyor" sayılır."""
    from ..config import APIF_TO_LEAGUE

    p = it.get("player") or {}
    sts = it.get("statistics") or [{}]
    if team_apif is not None:
        own = [x for x in sts if (x.get("team") or {}).get("id") == team_apif]
        lg = [x for x in own if (x.get("league") or {}).get("id") in APIF_TO_LEAGUE] or own
        st = max(lg, key=lambda x: ((x.get("games") or {}).get("minutes") or 0)) if lg else None
    elif apif_league:
        st = next((x for x in sts if (x.get("league") or {}).get("id") == apif_league), sts[0])
    else:
        lg = [x for x in sts if (x.get("league") or {}).get("id") in APIF_TO_LEAGUE] or sts
        st = max(lg, key=lambda x: ((x.get("games") or {}).get("minutes") or 0))
    base = {"player_key": str(p.get("id")), "name": p.get("name"),
            "full_name": " ".join(x for x in (p.get("firstname"), p.get("lastname")) if x) or None}
    if st is None:
        return {**base, "position": None, "minutes": None, "appearances": None, "lineups": None, "goals": None,
                "assists": None, "team_apif": team_apif, "team_name": None, "no_team_stats": True}
    games, goals = st.get("games") or {}, st.get("goals") or {}
    team = st.get("team") or {}
    return {**base, "position": games.get("position"), "minutes": games.get("minutes") or 0,
            "appearances": games.get("appearences") or 0, "lineups": games.get("lineups") or 0,
            "goals": goals.get("total") or 0, "assists": goals.get("assists") or 0,
            "team_apif": team.get("id"), "team_name": team.get("name")}


# ---------------------------------------------------------------- oranlar (/odds?date=, ücretsiz planda açık)
# API-Football bahis kimliği → (iç pazar, değer ayrıştırıcı). Asya handikapta "Home L" / "Away L" çifti EV SAHİBİ
# çizgisine göre verilir (canlı doğrulandı: Home -0.5 = MS1 oranı, Away -0.5 = X2 tarafı).
_OU_BETS = {5: "OU_GOALS", 6: "HT_OU_GOALS", 16: "TEAM_GOALS_HOME", 17: "TEAM_GOALS_AWAY", 45: "CORNERS_OU",
            80: "CARDS_OU", 87: "SOT_OU"}
_PREFERRED_BOOKS = 3  # medyan için en az bu kadar şirket varsa medyan, yoksa var olanların medyanı


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def parse_odds_response(resp: list[dict]) -> dict[int, dict]:
    """/odds yanıtı → {fixture_id: iç oran sözlüğü}. Her fiyat şirketlerin MEDYANIDIR (en iyi fiyat değil:
    değer hesabını şişirmemek için); kaynak 'api-football:medyan(n)'."""
    out: dict[int, dict] = {}
    for x in resp or []:
        fid = (x.get("fixture") or {}).get("id")
        if not fid:
            continue
        acc: dict = {}
        for bm in x.get("bookmakers") or []:
            for b in bm.get("bets") or []:
                bid = b.get("id")
                for v in b.get("values") or []:
                    try:
                        odd = float(v.get("odd"))
                    except (TypeError, ValueError):
                        continue
                    val = str(v.get("value") or "")
                    key = sel = None
                    if bid == 1:
                        key, sel = "1X2", {"Home": "1", "Draw": "X", "Away": "2"}.get(val)
                    elif bid == 12:
                        key, sel = "DC", {"Home/Draw": "1X", "Draw/Away": "X2", "Home/Away": "12"}.get(val)
                    elif bid == 8:
                        key, sel = "BTTS", {"Yes": "VAR", "No": "YOK"}.get(val)
                    elif bid == 4:
                        parts = val.split()
                        if len(parts) == 2 and parts[0] in ("Home", "Away"):
                            try:
                                ln = float(parts[1])
                            except ValueError:
                                continue
                            if abs(ln * 2 % 2 - 1) < 1e-9:  # yalnızca yarım çizgiler (±0.5, ±1.5 …; iade yok)
                                key, sel = f"AH_{ln:g}", "1" if parts[0] == "Home" else "2"
                    elif bid in _OU_BETS:
                        parts = val.split()
                        if len(parts) == 2 and parts[0] in ("Over", "Under"):
                            try:
                                ln = float(parts[1])
                            except ValueError:
                                continue
                            if abs(ln * 2 % 2 - 1) < 1e-9:
                                key, sel = f"{_OU_BETS[bid]}_{ln:g}", "ÜST" if parts[0] == "Over" else "ALT"
                    if key and sel and odd > 1.0:
                        acc.setdefault(key, {}).setdefault(sel, []).append(odd)
        odds = {}
        for key, sels in acc.items():
            if len(sels) < (3 if key in ("1X2",) or key.startswith("DC") else 2):
                continue  # pazarın bütün tarafları yoksa yazılmaz
            n = min(len(v) for v in sels.values())
            odds[key] = {s: round(_median(v), 3) for s, v in sels.items()}
            odds[key]["src"] = f"{SOURCE}:medyan({n})"
        if odds:
            out[int(fid)] = odds
    return out


def _odds_by_date(self, d, max_pages: int = 3) -> dict[int, dict]:
    """Bir günün oranları (sayfa başına 10 maç; ücretsiz planda tarih dün–yarın ve en çok 3 sayfa)."""
    out: dict[int, dict] = {}
    page, total = 1, 1
    while page <= min(total, max_pages):
        resp = self._get("/odds", {"date": d.isoformat(), "page": page})
        out.update(parse_odds_response(resp))
        total = int((self._paging or {}).get("total") or 1)
        page += 1
    return out


ApiFootball.odds_by_date = _odds_by_date


def _odds_by_fixture(self, fixture_id: int) -> dict:
    """Tek fikstürün oranları (güncel sezonda da açık; ~10 şirket)."""
    return parse_odds_response(self._get("/odds", {"fixture": int(fixture_id)})).get(int(fixture_id)) or {}


ApiFootball.odds_by_fixture = _odds_by_fixture
