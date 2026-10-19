"""Wikidata SPARQL — stadyum, kapasite, şehir, koordinat ve teknik direktör (CC0, anahtarsız).
Wikimedia User-Agent politikasına uyulur; sonuçlar takım başına önbelleklenir."""
from __future__ import annotations

import time

from .http import USER_AGENT, SourceError, get

SOURCE = "wikidata"
ENDPOINT = "https://query.wikidata.org/sparql"
COUNTRY = {"T1": "Q43", "E0": "Q145", "E1": "Q145", "SP1": "Q29", "I1": "Q38", "D1": "Q183", "F1": "Q142",
           "N1": "Q55", "P1": "Q45", "T2": "Q43", "E2": "Q145", "SP2": "Q29", "I2": "Q38", "D2": "Q183",
           "F2": "Q142", "B1": "Q31", "SC0": "Q22", "G1": "Q41"}
_EXCLUDE = ("women", "kadın", "femen", "frauen", "féminin", "u19", "u21", "u23", " b", " ii", "a2", "youth",
            "reserves", "primavera", "akademi")

QUERY = """SELECT ?item ?itemLabel ?ord ?venueLabel ?vstart ?coord ?cap ?cityLabel ?coachLabel ?cstart ?country WHERE {
 SERVICE wikibase:mwapi { bd:serviceParam wikibase:api "EntitySearch"; wikibase:endpoint "www.wikidata.org";
   mwapi:search "%s"; mwapi:language "en". ?item wikibase:apiOutputItem mwapi:item. ?ord wikibase:apiOrdinal true. }
 ?item wdt:P31/wdt:P279* wd:Q476028.
 OPTIONAL { ?item wdt:P17 ?country }
 OPTIONAL { ?item p:P115 ?vst. ?vst ps:P115 ?venue. FILTER NOT EXISTS { ?vst pq:P582 ?vend }
   OPTIONAL { ?vst pq:P580 ?vstart } OPTIONAL { ?venue wdt:P625 ?coord } OPTIONAL { ?venue wdt:P1083 ?cap }
   OPTIONAL { ?venue wdt:P131 ?city } }
 OPTIONAL { ?item p:P286 ?cst. ?cst ps:P286 ?coach. FILTER NOT EXISTS { ?cst pq:P582 ?cend }
   OPTIONAL { ?cst pq:P580 ?cstart } }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "tr,en". }
} LIMIT 40"""

_last = 0.0


def _val(b: dict, k: str):
    return (b.get(k) or {}).get("value")


def pick(bindings: list[dict], country: str | None) -> dict | None:
    """Arama sırasına göre ilk uygun kulübü seçer; birden çok stat/TD varsa en yeni başlangıçlıyı alır."""
    by_item: dict[str, list[dict]] = {}
    order: list[tuple[int, str]] = []
    for b in bindings:
        qid = (_val(b, "item") or "").rsplit("/", 1)[-1]
        if not qid:
            continue
        if qid not in by_item:
            order.append((int(_val(b, "ord") or 99), qid))
        by_item.setdefault(qid, []).append(b)
    for _, qid in sorted(order):
        rows = by_item[qid]
        label = (_val(rows[0], "itemLabel") or "").lower()
        if any(x in f" {label}" for x in _EXCLUDE):
            continue
        ctry = (_val(rows[0], "country") or "").rsplit("/", 1)[-1]
        if country and ctry and ctry != country:
            continue
        venues = sorted([r for r in rows if _val(r, "venueLabel")], key=lambda r: _val(r, "vstart") or "", reverse=True)
        coaches = sorted([r for r in rows if _val(r, "coachLabel")], key=lambda r: _val(r, "cstart") or "", reverse=True)
        out = {"wikidata": qid, "name": _val(rows[0], "itemLabel")}
        if venues:
            v = venues[0]
            out["stadium"] = _val(v, "venueLabel")
            out["city"] = _val(v, "cityLabel")
            cap = _val(v, "cap")
            out["capacity"] = int(float(cap)) if cap else None
            coord = _val(v, "coord")
            if coord and coord.startswith("Point("):
                lon, lat = coord[6:-1].split()
                out["lat"], out["lon"] = float(lat), float(lon)
        if coaches:
            out["coach"] = _val(coaches[0], "coachLabel")
        return out
    return None


def team_info(name: str, league: str) -> dict | None:
    global _last
    wait = _last + 1.0 - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    safe = name.replace('"', " ").replace("\\", " ")
    r = get(ENDPOINT, params={"query": QUERY % safe, "format": "json"},
            headers={"User-Agent": USER_AGENT + " https://github.com/90meclis/90meclis.github.io",
                     "Accept": "application/sparql-results+json"}, timeout=60)
    if r.status_code != 200:
        raise SourceError(f"Wikidata HTTP {r.status_code}")
    return pick(r.json().get("results", {}).get("bindings", []), COUNTRY.get(league))
