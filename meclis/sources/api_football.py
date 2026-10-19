"""API-Football (api-sports.io) v3 — API_FOOTBALL_KEY gerekir.
Ücretsiz plan: günde 100 istek, dakikada 10 istek; ücretsiz planda erişilebilen sezonlar SINIRLI
(güncel sezon kapalı olabilir — API bu durumda 'errors' alanında açıklama döndürür).
Sağladıkları: fikstür, istatistik, kadro (ilk 11), sakat/cezalı listesi, oyuncu istatistikleri, oranlar."""
from __future__ import annotations

from datetime import date

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


class ApiFootball:
    def __init__(self, key: str | None, store=None, daily_budget: int = 90):
        self.key = key
        self.store = store
        self.daily_budget = daily_budget

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
        if self.calls_today() >= self.daily_budget:
            raise SourceError(f"Günlük API-Football bütçesi doldu ({self.daily_budget} istek).")
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
            raise SourceError(f"API-Football: {msg}")
        return data.get("response") or []

    def fixtures(self, league: str, season: int, date_from: date, date_to: date) -> list[dict]:
        from ..config import LEAGUES

        lg = LEAGUES[league]
        out = []
        for f in self._get("/fixtures", {"league": lg.apif_id, "season": season,
                                         "from": date_from.isoformat(), "to": date_to.isoformat()}):
            fx, teams, goals, score = f["fixture"], f["teams"], f.get("goals") or {}, f.get("score") or {}
            ht = score.get("halftime") or {}
            out.append({
                "source": SOURCE, "league": APIF_TO_LEAGUE.get(f["league"]["id"], league),
                "kickoff_at": to_iso(fx.get("date")), "season": str(season),
                "home_name": teams["home"]["name"], "away_name": teams["away"]["name"],
                "status": _STATUS.get((fx.get("status") or {}).get("short"), "planlandi"),
                "home_goals": goals.get("home"), "away_goals": goals.get("away"),
                "ht_home_goals": ht.get("home"), "ht_away_goals": ht.get("away"),
                "referee": fx.get("referee"), "venue": (fx.get("venue") or {}).get("name"),
                "city": (fx.get("venue") or {}).get("city"),
                "ext_ids": {"apif": fx.get("id"), "apif_home": teams["home"]["id"], "apif_away": teams["away"]["id"]},
            })
        return out

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
        out = []
        for it in self._get("/injuries", {"fixture": fixture_id}):
            p, t = it.get("player") or {}, it.get("team") or {}
            out.append({"player_name": p.get("name"), "player_id": p.get("id"), "team_apif": t.get("id"),
                        "team_name": t.get("name"), "kind": p.get("type"), "reason": p.get("reason")})
        return out

    def lineups(self, fixture_id: int) -> list[dict]:
        out = []
        for it in self._get("/fixtures/lineups", {"fixture": fixture_id}):
            out.append({
                "team_apif": (it.get("team") or {}).get("id"), "team_name": (it.get("team") or {}).get("name"),
                "formation": it.get("formation"), "coach": (it.get("coach") or {}).get("name"),
                "start_xi": [{"name": x["player"]["name"], "number": x["player"].get("number"),
                              "pos": x["player"].get("pos")} for x in it.get("startXI", [])],
                "subs": [{"name": x["player"]["name"], "number": x["player"].get("number"),
                          "pos": x["player"].get("pos")} for x in it.get("substitutes", [])],
            })
        return out

    def team_players(self, team_apif: int, season: int, max_pages: int = 2) -> list[dict]:
        out = []
        for page in range(1, max_pages + 1):
            res = self._get("/players", {"team": team_apif, "season": season, "page": page})
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
