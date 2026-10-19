"""FootyStats API (api.football-data-api.com) — FOOTYSTATS_KEY. Ücretsiz plan yalnızca Premier Lig;
Süper Lig ve diğerleri ücretli (Hobby). Hesapta seçili liglerin günlük maçları alınır."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .http import SourceError, get

SOURCE = "footystats"
BASE = "https://api.football-data-api.com"
# (ülke, lig adı anahtar kelimesi) -> lig kodu
LEAGUE_NAMES = {("turkey", "super lig"): "T1", ("england", "premier league"): "E0", ("england", "championship"): "E1",
                ("spain", "la liga"): "SP1", ("italy", "serie a"): "I1", ("germany", "bundesliga"): "D1",
                ("france", "ligue 1"): "F1", ("netherlands", "eredivisie"): "N1", ("portugal", "liga nos"): "P1",
                ("portugal", "primeira liga"): "P1"}


def _n(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f < 0 else f


def map_leagues(league_list: list[dict]) -> dict[int, str]:
    out = {}
    for lg in league_list or []:
        country = (lg.get("country") or "").lower()
        name = (lg.get("league_name") or lg.get("name") or "").lower()
        code = next((c for (ct, kw), c in LEAGUE_NAMES.items() if ct == country and kw in name), None)
        if not code:
            continue
        for s in lg.get("season") or []:
            if s.get("id"):
                out[int(s["id"])] = code
    return out


def parse_matches(data: list[dict], season_map: dict[int, str]) -> list[dict]:
    out = []
    for m in data or []:
        lg = season_map.get(int(m.get("competition_id") or 0))
        if not lg or not m.get("home_name") or not m.get("date_unix"):
            continue
        done = m.get("status") == "complete"
        o1, ox, o2 = _n(m.get("odds_ft_1")), _n(m.get("odds_ft_x")), _n(m.get("odds_ft_2"))
        odds = {}
        if o1 and ox and o2 and min(o1, ox, o2) > 1:
            odds["1X2"] = {"1": o1, "X": ox, "2": o2}
        ov, un = _n(m.get("odds_ft_over25")), _n(m.get("odds_ft_under25"))
        if ov and un and min(ov, un) > 1:
            odds["OU_GOALS_2.5"] = {"ÜST": ov, "ALT": un}

        def side(p):
            return {"corners": _n(m.get(f"team_{p}_corners")), "shots_on_target": _n(m.get(f"team_{p}_shotsOnTarget")),
                    "shots": _n(m.get(f"team_{p}_shots")), "fouls": _n(m.get(f"team_{p}_fouls")),
                    "yellow": _n(m.get(f"team_{p}_yellow_cards")), "red": _n(m.get(f"team_{p}_red_cards")),
                    "possession": _n(m.get(f"team_{p}_possession"))}
        out.append({
            "source": SOURCE, "league": lg,
            "kickoff_at": datetime.fromtimestamp(int(m["date_unix"]), tz=timezone.utc).isoformat(),
            "home_name": m["home_name"], "away_name": m.get("away_name"), "status": "bitti" if done else "planlandi",
            "home_goals": m.get("homeGoalCount") if done else None, "away_goals": m.get("awayGoalCount") if done else None,
            "ht_home_goals": m.get("ht_goals_team_a") if done else None,
            "ht_away_goals": m.get("ht_goals_team_b") if done else None,
            "venue": m.get("stadium_name") or None, "ext_ids": {"footystats": m.get("id")}, "odds": odds,
            "stats": {"home": side("a"), "away": side("b")} if done else None,
        })
    return out


class FootyStats:
    def __init__(self, key: str | None):
        self.key = key
        self._season_map: dict[int, str] | None = None

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, **params) -> dict:
        r = get(f"{BASE}/{path}", params={"key": self.key, **params})
        if r.status_code in (401, 403):
            raise SourceError(f"FootyStats yetki hatası (HTTP {r.status_code})")
        if r.status_code != 200:
            raise SourceError(f"FootyStats HTTP {r.status_code}")
        return r.json()

    def matches_on(self, d: date) -> list[dict]:
        if self._season_map is None:
            self._season_map = map_leagues(self._get("league-list", chosen_leagues_only="true").get("data") or [])
        out, page = [], 1
        while page <= 3:
            j = self._get("todays-matches", date=d.isoformat(), page=page)
            out += parse_matches(j.get("data") or [], self._season_map)
            pager = j.get("pager") or {}
            if not pager or page >= int(pager.get("max_page") or 1):
                break
            page += 1
        return out
