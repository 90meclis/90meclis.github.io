"""OpenLigaDB (api.openligadb.de) — anahtarsız, açık topluluk veritabanı.

bl1 (Bundesliga) sonuçları maçtan dakikalar sonra girilir: football-data.co.uk'nin haftalık gecikmesini kapatır.
'pl' ve 'la1' topluluk ligleridir; yalnızca var olan maçlardaki boşlukları doldurur (fill_only).
"""
from __future__ import annotations

from datetime import date

from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "openligadb"
BASE = "https://api.openligadb.de"
# lig kodu -> (OpenLigaDB kısaltması, yalnızca boşluk doldur?)
LEAGUE_MAP = {"D1": ("bl1", False), "E0": ("pl", True), "SP1": ("la1", True)}


def season_year(d: date) -> int:
    return d.year if d.month >= 7 else d.year - 1


def parse_matches(data: list[dict], league: str, fill_only: bool) -> list[dict]:
    out = []
    for m in data or []:
        t1, t2 = (m.get("team1") or {}).get("teamName"), (m.get("team2") or {}).get("teamName")
        ko = m.get("matchDateTimeUTC")
        if not (t1 and t2 and ko):
            continue
        res = {r.get("resultTypeID"): r for r in m.get("matchResults") or []}
        ft, ht = res.get(2), res.get(1)
        done = bool(m.get("matchIsFinished")) and ft is not None
        loc = m.get("location") or {}
        out.append({
            "source": SOURCE, "league": league, "kickoff_at": to_iso(ko), "home_name": t1, "away_name": t2,
            "status": "bitti" if done else "planlandi",
            "home_goals": ft.get("pointsTeam1") if done else None, "away_goals": ft.get("pointsTeam2") if done else None,
            "ht_home_goals": ht.get("pointsTeam1") if done and ht else None,
            "ht_away_goals": ht.get("pointsTeam2") if done and ht else None,
            "venue": loc.get("locationStadium"), "city": loc.get("locationCity"),
            "ext_ids": {"oldb": m.get("matchID")}, "fill_only": fill_only,
        })
    return out


def fetch_league(league: str, today: date) -> list[dict]:
    if league not in LEAGUE_MAP:
        return []
    short, fill_only = LEAGUE_MAP[league]
    r = get(f"{BASE}/getmatchdata/{short}/{season_year(today)}")
    if r.status_code != 200:
        raise SourceError(f"OpenLigaDB HTTP {r.status_code}")
    return parse_matches(r.json(), league, fill_only)
