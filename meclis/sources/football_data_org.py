"""football-data.org v4 — FOOTBALL_DATA_TOKEN gerekir (ücretsiz katman: 12 turnuva, dakikada 10 istek).
Ücretsiz katmanda Süper Lig YOK; skorlar gecikmeli olabilir."""
from __future__ import annotations

from datetime import date

from ..config import FDORG_TO_LEAGUE
from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "football-data.org"
BASE = "https://api.football-data.org/v4"

_STATUS = {"SCHEDULED": "planlandi", "TIMED": "planlandi", "IN_PLAY": "basladi", "PAUSED": "basladi",
           "LIVE": "basladi", "FINISHED": "bitti", "AWARDED": "bitti", "POSTPONED": "ertelendi",
           "SUSPENDED": "ertelendi", "CANCELLED": "iptal"}


class FootballDataOrg:
    def __init__(self, token: str | None):
        self.token = token

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.token:
            raise SourceError("FOOTBALL_DATA_TOKEN tanımlı değil.")
        r = get(f"{BASE}{path}", params=params, headers={"X-Auth-Token": self.token})
        if r.status_code != 200:
            raise SourceError(f"football-data.org HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    @staticmethod
    def _rec(m: dict) -> dict | None:
        comp = (m.get("competition") or {}).get("code")
        league = FDORG_TO_LEAGUE.get(comp)
        if not league:
            return None
        ft = (m.get("score") or {}).get("fullTime") or {}
        ht = (m.get("score") or {}).get("halfTime") or {}
        refs = m.get("referees") or []
        return {
            "source": SOURCE, "league": league, "kickoff_at": to_iso(m.get("utcDate")),
            "season": None,
            "home_name": (m.get("homeTeam") or {}).get("shortName") or (m.get("homeTeam") or {}).get("name"),
            "away_name": (m.get("awayTeam") or {}).get("shortName") or (m.get("awayTeam") or {}).get("name"),
            "status": _STATUS.get(m.get("status"), "planlandi"),
            "home_goals": ft.get("home"), "away_goals": ft.get("away"),
            "ht_home_goals": ht.get("home"), "ht_away_goals": ht.get("away"),
            "referee": refs[0].get("name") if refs else None,
            "venue": m.get("venue"),
            "ext_ids": {"fdorg": m.get("id"), "fdorg_home": (m.get("homeTeam") or {}).get("id"),
                        "fdorg_away": (m.get("awayTeam") or {}).get("id")},
        }

    def matches(self, date_from: date, date_to: date, leagues: list[str]) -> list[dict]:
        codes = [c for c, lg in FDORG_TO_LEAGUE.items() if lg in leagues]
        if not codes:
            return []
        data = self._get("/matches", {"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(),
                                      "competitions": ",".join(codes)})
        return [r for r in (self._rec(m) for m in data.get("matches", [])) if r and r["home_name"]]

    def head2head(self, fdorg_match_id: int, limit: int = 10) -> list[dict]:
        data = self._get(f"/matches/{fdorg_match_id}/head2head", {"limit": limit})
        return [r for r in (self._rec(m) for m in data.get("matches", [])) if r]
