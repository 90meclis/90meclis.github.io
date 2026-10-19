"""The Odds API (the-odds-api.com) v4 — ODDS_API_KEY gerekir (yoksa "anahtar bekleniyor").
Ücretsiz Starter: ayda 500 kredi. Kredi = pazar sayısı × bölge sayısı (burada h2h+totals × eu = 2 kredi/lig).
Türk bayisi (İddaa) oranı YOK; EU bölgesi şirketleri (Pinnacle, Betfair vb.) döner."""
from __future__ import annotations

from statistics import mean

from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "the-odds-api"
BASE = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {"T1": "soccer_turkey_super_league", "E0": "soccer_epl", "E1": "soccer_efl_champ",
              "SP1": "soccer_spain_la_liga", "I1": "soccer_italy_serie_a", "D1": "soccer_germany_bundesliga",
              "F1": "soccer_france_ligue_one", "N1": "soccer_netherlands_eredivisie",
              "P1": "soccer_portugal_primeira_liga", "E2": "soccer_england_league1",
              "SP2": "soccer_spain_segunda_division", "I2": "soccer_italy_serie_b",
              "D2": "soccer_germany_bundesliga2", "F2": "soccer_france_ligue_two", "B1": "soccer_belgium_first_div",
              "SC0": "soccer_spl", "G1": "soccer_greece_super_league", "CL": "soccer_uefa_champs_league",
              "EL": "soccer_uefa_europa_league", "ECL": "soccer_uefa_europa_conference_league"}


def parse_events(events: list[dict], league: str) -> list[dict]:
    out = []
    for e in events:
        home, away = e.get("home_team"), e.get("away_team")
        h2h: dict[str, list[float]] = {"1": [], "X": [], "2": []}
        pin: dict[str, float] = {}
        totals: dict[float, dict[str, list[float]]] = {}
        for bm in e.get("bookmakers") or []:
            for mk in bm.get("markets") or []:
                if mk.get("key") == "h2h":
                    for o in mk.get("outcomes") or []:
                        sel = "1" if o["name"] == home else "2" if o["name"] == away else "X"
                        h2h[sel].append(float(o["price"]))
                        if bm.get("key") == "pinnacle":
                            pin[sel] = float(o["price"])
                elif mk.get("key") == "totals":
                    for o in mk.get("outcomes") or []:
                        line = float(o.get("point") or 0)
                        sel = "ÜST" if o["name"].lower() == "over" else "ALT"
                        totals.setdefault(line, {"ÜST": [], "ALT": []})[sel].append(float(o["price"]))
        odds: dict = {}
        if all(h2h.values()):
            odds["1X2"] = {k: round(mean(v), 3) for k, v in h2h.items()}
            odds["1X2"]["src"] = f"{SOURCE}:ortalama({len(h2h['1'])} şirket)"
        if len(pin) == 3:
            odds["1X2_pinnacle"] = pin
        for line, d in totals.items():
            if d["ÜST"] and d["ALT"]:
                odds[f"OU_GOALS_{line:g}"] = {"ÜST": round(mean(d["ÜST"]), 3), "ALT": round(mean(d["ALT"]), 3),
                                              "src": f"{SOURCE}:ortalama({len(d['ÜST'])} şirket)"}
        out.append({"source": SOURCE, "league": league, "kickoff_at": to_iso(e.get("commence_time")),
                    "home_name": home, "away_name": away, "status": "planlandi", "odds": odds,
                    "ext_ids": {"oddsapi": e.get("id")}})
    return out


class OddsApi:
    def __init__(self, key: str | None):
        self.key = key

    @property
    def available(self) -> bool:
        return bool(self.key)

    def odds(self, league: str) -> tuple[list[dict], str]:
        if not self.key:
            raise SourceError("ODDS_API_KEY tanımlı değil.")
        sk = SPORT_KEYS.get(league)
        if not sk:
            return [], "lig desteklenmiyor"
        r = get(f"{BASE}/sports/{sk}/odds", params={"apiKey": self.key, "regions": "eu", "markets": "h2h,totals",
                                                     "oddsFormat": "decimal", "dateFormat": "iso"})
        if r.status_code != 200:
            raise SourceError(f"The Odds API HTTP {r.status_code}: {r.text[:150]}")
        remaining = r.headers.get("x-requests-remaining", "?")
        return parse_events(r.json() or [], league), f"kalan kredi: {remaining}"
