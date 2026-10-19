"""OddsPapi (api.oddspapi.io v4) — ODDSPAPI_KEY. Ücretsiz: ayda 250 istek. Bot günde en çok bir oran
çağrısı yapar (tüm liglerin turnuva kimlikleri tek istekte); turnuva/takım listeleri 7 gün önbelleklenir."""
from __future__ import annotations

import json

from ..timeutil import to_iso
from .http import SourceError, cached_text, get

SOURCE = "oddspapi"
BASE = "https://api.oddspapi.io/v4"
SPORT_ID = 10
# lig kodu -> (categorySlug, tournamentSlug)
SLUGS = {"T1": ("turkiye", "super-lig"), "E0": ("england", "premier-league"), "E1": ("england", "championship"),
         "SP1": ("spain", "laliga"), "I1": ("italy", "serie-a"), "D1": ("germany", "bundesliga"),
         "F1": ("france", "ligue-1"), "N1": ("netherlands", "eredivisie"), "P1": ("portugal", "liga-portugal")}
BOOKMAKER = "pinnacle"


def map_tournaments(tours: list[dict], leagues: list[str]) -> dict[int, str]:
    out = {}
    for t in tours or []:
        for lg in leagues:
            cat, slug = SLUGS.get(lg, (None, None))
            if cat and t.get("tournamentSlug") == slug and (t.get("categorySlug") or "").startswith(cat[:5]):
                out[int(t["tournamentId"])] = lg
    return out


def parse_odds(rows: list[dict], tour_map: dict[int, str], names: dict[int, str]) -> list[dict]:
    out = []
    for f in rows or []:
        lg = tour_map.get(int(f.get("tournamentId") or 0))
        h, a = names.get(f.get("participant1Id")), names.get(f.get("participant2Id"))
        if not (lg and h and a and f.get("startTime")):
            continue
        mk = (((f.get("bookmakerOdds") or {}).get(BOOKMAKER) or {}).get("markets") or {}).get("101") or {}
        oc = mk.get("outcomes") or {}

        def price(o):
            p = ((oc.get(o) or {}).get("players") or {}).get("0") or {}
            return float(p["price"]) if p.get("active", True) and p.get("price") else None
        p1, px, p2 = price("101"), price("102"), price("103")
        if not (p1 and px and p2):
            continue
        out.append({"source": SOURCE, "league": lg, "kickoff_at": to_iso(f["startTime"]), "home_name": h,
                    "away_name": a, "status": "planlandi", "ext_ids": {"oddspapi": f.get("fixtureId")},
                    "odds": {"1X2": {"1": p1, "X": px, "2": p2}, "1X2_pinnacle": {"1": p1, "X": px, "2": p2}}})
    return out


class OddsPapi:
    def __init__(self, key: str | None):
        self.key = key

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _cached(self, path: str, ttl: int, **params) -> list:
        text = cached_text(f"{BASE}/{path}", ttl, params={"apiKey": self.key, **params})
        return json.loads(text)

    def odds(self, leagues: list[str]) -> list[dict]:
        tours = map_tournaments(self._cached("tournaments", 7 * 86400, sportId=SPORT_ID), leagues)
        if not tours:
            return []
        parts = self._cached("participants", 7 * 86400, sportId=SPORT_ID)
        if isinstance(parts, dict):
            names = {int(k): v for k, v in parts.items()}
        else:
            names = {int(p.get("participantId")): p.get("participantName") for p in parts or [] if p.get("participantId")}
        r = get(f"{BASE}/odds-by-tournaments", params={"apiKey": self.key, "bookmaker": BOOKMAKER,
                                                         "tournamentIds": ",".join(str(t) for t in tours)})
        if r.status_code in (401, 403):
            raise SourceError(f"OddsPapi yetki hatası (HTTP {r.status_code})")
        if r.status_code != 200:
            raise SourceError(f"OddsPapi HTTP {r.status_code}")
        return parse_odds(r.json(), tours, names)
