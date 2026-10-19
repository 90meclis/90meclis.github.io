"""TheSportsDB — ücretsiz test anahtarı "123" ile çalışır (THESPORTSDB_KEY ile değiştirilebilir).
Ücretsiz anahtar kısıtlı: günlük maç listesi, takım/stadyum bilgisi ve kadro listesi açık;
ilk 11 (lookuplineup.php) ücretsiz anahtarla boş döner (19.10.2026'da doğrulandı: {"lineup": null});
Patreon anahtarı (THESPORTSDB_KEY) tanımlanınca aynı çağrı resmî ilk 11'i doldurur."""
from __future__ import annotations

import time
from datetime import date

from ..config import LEAGUES, TSDB_TO_LEAGUE
from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "thesportsdb"


class TheSportsDB:
    def __init__(self, key: str = "123"):
        self.base = f"https://www.thesportsdb.com/api/v1/json/{key or '123'}"

    available = True
    MIN_INTERVAL = 2.1  # ücretsiz anahtar: dakikada ~30 istek sınırına saygı
    _last = 0.0

    def _get(self, path: str, params: dict | None = None) -> dict:
        wait = TheSportsDB._last + self.MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        TheSportsDB._last = time.monotonic()
        r = get(f"{self.base}/{path}", params=params)
        if r.status_code != 200:
            raise SourceError(f"TheSportsDB HTTP {r.status_code}")
        try:
            return r.json() or {}
        except ValueError as e:
            raise SourceError(f"TheSportsDB geçersiz yanıt: {r.text[:120]}") from e

    @staticmethod
    def _rec(e: dict) -> dict | None:
        league = TSDB_TO_LEAGUE.get(str(e.get("idLeague")))
        if not league or not e.get("strHomeTeam"):
            return None
        ts = e.get("strTimestamp") or (f"{e.get('dateEvent')}T{e.get('strTime') or '00:00:00'}")
        hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
        status_raw = (e.get("strStatus") or "").upper()
        if (e.get("strPostponed") or "").lower() == "yes":
            status = "ertelendi"
        elif status_raw in ("FT", "AET", "PEN", "MATCH FINISHED") and hs not in (None, ""):
            status = "bitti"
        elif status_raw in ("1H", "2H", "HT", "LIVE", "ET"):
            status = "basladi"
        elif status_raw in ("CANC", "ABD", "CANCELLED"):
            status = "iptal"
        else:
            status = "planlandi"
        return {
            "source": SOURCE, "league": league, "kickoff_at": to_iso(ts), "season": e.get("strSeason"),
            "home_name": e["strHomeTeam"], "away_name": e["strAwayTeam"], "status": status,
            "home_goals": int(hs) if hs not in (None, "") and status == "bitti" else None,
            "away_goals": int(as_) if as_ not in (None, "") and status == "bitti" else None,
            "venue": e.get("strVenue"),
            "ext_ids": {"tsdb": e.get("idEvent"), "tsdb_home": e.get("idHomeTeam"), "tsdb_away": e.get("idAwayTeam"),
                        "apif": int(e["idAPIfootball"]) if str(e.get("idAPIfootball") or "").isdigit() else None},
        }

    def events_day(self, d: date, leagues: list[str]) -> list[dict]:
        out = []
        for lg in leagues:
            lid = LEAGUES[lg].tsdb_id if lg in LEAGUES else None
            if not lid:
                continue
            data = self._get("eventsday.php", {"d": d.isoformat(), "l": lid})
            out += [r for r in (self._rec(e) for e in (data.get("events") or [])) if r and r["league"] == lg]
        return out

    def search_team(self, name: str) -> dict | None:
        data = self._get("searchteams.php", {"t": name})
        teams = [t for t in (data.get("teams") or []) if t.get("strSport") == "Soccer"]
        if not teams:
            return None
        t = teams[0]
        return {"tsdb_id": t.get("idTeam"), "name": t.get("strTeam"), "alternate": t.get("strTeamAlternate"),
                "stadium": t.get("strStadium"), "location": t.get("strLocation"), "venue_id": t.get("idVenue"),
                "badge": t.get("strBadge")}

    def squad(self, tsdb_team_id: str) -> list[dict]:
        data = self._get("lookup_all_players.php", {"id": tsdb_team_id})
        return [{"name": p.get("strPlayer"), "position": p.get("strPosition"), "number": p.get("strNumber")}
                for p in (data.get("player") or []) if p.get("strTeam")]

    def lineup(self, tsdb_event_id: str) -> list[dict]:
        """Maç kadrosu → [{side, start_xi, subs}] (ücretsiz anahtarda genelde boş)."""
        data = self._get("lookuplineup.php", {"id": tsdb_event_id})
        return parse_lineup(data.get("lineup") or [])


def parse_lineup(items: list[dict]) -> list[dict]:
    sides: dict[str, dict] = {}
    for p in items or []:
        if not p.get("strPlayer"):
            continue
        side = "home" if (p.get("strHome") or "").lower() == "yes" else "away"
        s = sides.setdefault(side, {"side": side, "formation": None, "start_xi": [], "subs": []})
        rec = {"name": p["strPlayer"], "number": p.get("intSquadNumber"), "pos": p.get("strPositionShort") or p.get("strPosition")}
        (s["subs"] if (p.get("strSubstitute") or "").lower() == "yes" else s["start_xi"]).append(rec)
    return [s for s in sides.values() if s["start_xi"]]
