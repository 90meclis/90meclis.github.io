"""openfootball / football.json — GitHub'daki CC0 (kamu malı) fikstür/sonuç dosyaları.
Saatler yerel saattir (lig saat dilimi); en düşük öncelikli kaynaktır ve yalnızca boşluk doldurur."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..timeutil import to_iso
from .http import SourceError, cached_text

SOURCE = "openfootball"
BASE = "https://raw.githubusercontent.com/openfootball/football.json/master"
FILES = {"T1": ("tr.1", "Europe/Istanbul"), "E0": ("en.1", "Europe/London"), "E1": ("en.2", "Europe/London"),
         "SP1": ("es.1", "Europe/Madrid"), "I1": ("it.1", "Europe/Rome"), "D1": ("de.1", "Europe/Berlin"),
         "F1": ("fr.1", "Europe/Paris"), "N1": ("nl.1", "Europe/Amsterdam"), "P1": ("pt.1", "Europe/Lisbon")}


def season_dir(d: date) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def parse(data: dict, league: str, tz: str) -> list[dict]:
    out = []
    for m in (data or {}).get("matches") or []:
        if not (m.get("team1") and m.get("team2") and m.get("date")):
            continue
        hhmm = (m.get("time") or "00:00")[:5]
        try:
            local = datetime.fromisoformat(f"{m['date']}T{hhmm}").replace(tzinfo=ZoneInfo(tz))
        except ValueError:
            continue
        sc = m.get("score") if isinstance(m.get("score"), dict) else {}
        ft, ht = sc.get("ft"), sc.get("ht")
        done = isinstance(ft, list) and len(ft) == 2
        out.append({
            "source": SOURCE, "league": league, "kickoff_at": to_iso(local), "home_name": m["team1"],
            "away_name": m["team2"], "status": "bitti" if done else "planlandi",
            "home_goals": ft[0] if done else None, "away_goals": ft[1] if done else None,
            "ht_home_goals": ht[0] if done and isinstance(ht, list) and len(ht) == 2 else None,
            "ht_away_goals": ht[1] if done and isinstance(ht, list) and len(ht) == 2 else None,
            "fill_only": True,
        })
    return out


def fetch_league(league: str, today: date, ttl: int = 6 * 3600) -> list[dict]:
    import json

    if league not in FILES:
        return []
    f, tz = FILES[league]
    try:
        text = cached_text(f"{BASE}/{season_dir(today)}/{f}.json", ttl)
    except SourceError:
        return []  # bu lig/sezon için dosya yok
    return parse(json.loads(text), league, tz)
