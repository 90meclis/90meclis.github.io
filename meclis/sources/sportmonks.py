"""Sportmonks Football API v3 — SPORTMONKS_KEY. Ücretsiz plan yalnızca Danimarka + İskoçya liglerini verir;
bizim liglerimiz (Süper Lig, Premier Lig…) için ücretli plan gerekir. Anahtar tanımlıysa abonelikteki
liglerden gelen her maç havuza girer; abonelik dışı ligler boş döner (hata değildir)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .http import SourceError, get

SOURCE = "sportmonks"
BASE = "https://api.sportmonks.com/v3/football"
LEAGUE_IDS = {"T1": 600, "E0": 8, "E1": 9, "SP1": 564, "I1": 384, "D1": 82, "F1": 301, "N1": 72, "P1": 462}
ID_TO_LEAGUE = {v: k for k, v in LEAGUE_IDS.items()}
FINISHED = {5, 7, 8}
LIVE = {2, 3, 4, 6, 9, 21, 22, 25}
STAT_TYPES = {34: "corners", 86: "shots_on_target", 42: "shots", 84: "yellow", 83: "red", 56: "fouls", 45: "possession"}


def parse_fixtures(data: list[dict]) -> list[dict]:
    out = []
    for f in data or []:
        lg = ID_TO_LEAGUE.get(f.get("league_id"))
        parts = {((p.get("meta") or {}).get("location")): p for p in f.get("participants") or []}
        if not lg or "home" not in parts or "away" not in parts:
            continue
        ts = f.get("starting_at_timestamp")
        ko = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
        if not ko:
            continue
        cur, ht = {}, {}
        for s in f.get("scores") or []:
            side = (s.get("score") or {}).get("participant")
            goals = (s.get("score") or {}).get("goals")
            if s.get("description") == "CURRENT":
                cur[side] = goals
            elif s.get("description") == "1ST_HALF":
                ht[side] = goals
        st_id = f.get("state_id")
        status = "bitti" if st_id in FINISHED else ("basladi" if st_id in LIVE else
                 ("ertelendi" if st_id == 10 else ("iptal" if st_id in (11, 12, 13, 14, 15, 16) else "planlandi")))
        done = status == "bitti" and "home" in cur and "away" in cur
        stats = {"home": {}, "away": {}}
        hid, aid = parts["home"].get("id"), parts["away"].get("id")
        for s in f.get("statistics") or []:
            key = STAT_TYPES.get(s.get("type_id"))
            side = "home" if s.get("participant_id") == hid else "away" if s.get("participant_id") == aid else None
            val = (s.get("data") or {}).get("value")
            if key and side and val is not None:
                stats[side][key] = val
        venue = f.get("venue") or {}
        ref = None
        for r in f.get("referees") or []:
            if r.get("type_id") == 6 and (r.get("referee") or {}).get("common_name"):
                ref = r["referee"]["common_name"]
        out.append({
            "source": SOURCE, "league": lg, "kickoff_at": ko, "home_name": parts["home"].get("name"),
            "away_name": parts["away"].get("name"), "status": status if done or status != "bitti" else "planlandi",
            "home_goals": cur.get("home") if done else None, "away_goals": cur.get("away") if done else None,
            "ht_home_goals": ht.get("home") if done else None, "ht_away_goals": ht.get("away") if done else None,
            "venue": venue.get("name"), "city": venue.get("city_name"), "referee": ref,
            "ext_ids": {"sportmonks": f.get("id")}, "stats": stats if (stats["home"] or stats["away"]) else None,
        })
    return out


class Sportmonks:
    def __init__(self, key: str | None):
        self.key = key

    @property
    def available(self) -> bool:
        return bool(self.key)

    def fixtures(self, leagues: list[str], d_from: date, d_to: date, max_pages: int = 6) -> list[dict]:
        ids = ",".join(str(LEAGUE_IDS[x]) for x in leagues if x in LEAGUE_IDS)
        out, page = [], 1
        while page <= max_pages:
            r = get(f"{BASE}/fixtures/between/{d_from.isoformat()}/{d_to.isoformat()}",
                    params={"api_token": self.key, "include": "participants;scores;venue;referees.referee;statistics",
                            "filters": f"fixtureLeagues:{ids}", "per_page": 50, "page": page})
            if r.status_code in (401, 403):
                raise SourceError(f"Sportmonks yetki hatası (HTTP {r.status_code})")
            if r.status_code != 200:
                raise SourceError(f"Sportmonks HTTP {r.status_code}")
            j = r.json()
            out += parse_fixtures(j.get("data") or [])
            if not (j.get("pagination") or {}).get("has_more"):
                break
            page += 1
        return out
