"""Anahtarlı ek istatistik kaynakları — yalnızca BOŞLUK doldurur (bitmiş maçın eksik şut/isabetli şut/korner/
kart/faul/kale vuruşu/topla oynama alanları). Anahtar tanımlı değilse hiç çağrılmaz.

* Highlightly (HIGHLIGHTLY_KEY, 100 istek/gün, 950+ lig): /matches?date=&homeTeamName= → /statistics/{id}
* Big Balls Sports Data (BIGBALLS_KEY, 250 istek/gün; 5 büyük lig + Şampiyonlar Ligi): /v1/matches?sport=soccer&date=
  → /v1/matches/{id}/statistics
* NosyAPI Maç Sonuçları (NOSYAPI_KEY, 500 kredi): yalnızca sonuç/İY/korner/kart — iddaa ORANI KULLANILMAZ (kullanıcı
  kararı: oranlar yalnızca yabancı kaynaklardan).
Kimlik eşleme: takım adları names.same_team ile (aksan/kısaltma toleranslı); eşleşmeyen maç atlanır, uydurma yok."""
from __future__ import annotations

from .. import names
from .http import SourceError, get

HL_BASE = "https://soccer.highlightly.net"
BB_BASE = "https://api.bigballsdata.com"
BB_LEAGUES = {"E0", "SP1", "I1", "D1", "F1", "CL"}

_HL_MAP = {"Shots on target": "shots_on_target", "Corners": "corners", "Fouls": "fouls", "Yellow cards": "yellow",
           "Red cards": "red", "Goal Kicks": "goal_kicks"}


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def parse_highlightly_stats(data: list, home_name: str, away_name: str) -> dict:
    out = {}
    for t in data or []:
        nm = (t.get("team") or {}).get("name") or ""
        side = "home" if names.same_team(nm, home_name, 0.8) else "away" if names.same_team(nm, away_name, 0.8) else None
        if not side:
            continue
        vals = {s.get("displayName"): s.get("value") for s in t.get("statistics") or []}
        row = {f: int(_num(vals[k])) for k, f in _HL_MAP.items() if _num(vals.get(k)) is not None}
        on, off, bl = (_num(vals.get(k)) for k in ("Shots on target", "Shots off target", "Blocked shots"))
        if None not in (on, off, bl):
            row["shots"] = int(on + off + bl)
        pos = _num(vals.get("Possession"))
        if pos is not None:
            row["possession"] = round(pos * 100 if pos <= 1 else pos, 1)
        out[side] = row
    return out


def parse_bigballs_stats(data: dict) -> dict:
    d = (data or {}).get("data") or {}
    out = {}
    for side in ("home", "away"):
        s = d.get(side) or {}
        row = {"shots": s.get("total_shots"), "shots_on_target": s.get("shots_on_target"), "corners": s.get("corner_kicks"),
               "fouls": s.get("fouls"), "yellow": s.get("yellow_cards"), "red": s.get("red_cards"),
               "possession": s.get("ball_possession")}
        row = {k: v for k, v in row.items() if v is not None}
        if row:
            out[side] = row
    return out


class Highlightly:
    def __init__(self, key: str | None):
        self.key = key
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict | None = None):
        r = get(f"{HL_BASE}{path}", params=params, headers={"x-rapidapi-key": self.key})
        self.calls += 1
        if r.status_code != 200:
            raise SourceError(f"Highlightly HTTP {r.status_code}")
        return r.json()

    def find_match(self, day: str, home: str, away: str) -> int | None:
        data = self._get("/matches", {"date": day, "timezone": "UTC", "homeTeamName": names.display_name(home)})
        for x in (data or {}).get("data") or []:
            if names.same_team((x.get("awayTeam") or {}).get("name") or "", away, 0.8):
                return x.get("id")
        return None

    def stats(self, match_id: int, home: str, away: str) -> dict:
        return parse_highlightly_stats(self._get(f"/statistics/{int(match_id)}"), home, away)


class BigBalls:
    def __init__(self, key: str | None):
        self.key = key
        self.calls = 0
        self._day: dict = {}

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict | None = None):
        r = get(f"{BB_BASE}{path}", params=params, headers={"Authorization": f"Bearer {self.key}"})
        self.calls += 1
        if r.status_code != 200:
            raise SourceError(f"Big Balls HTTP {r.status_code}")
        return r.json()

    def find_match(self, day: str, home: str, away: str) -> str | None:
        if day not in self._day:
            self._day[day] = (self._get("/v1/matches", {"sport": "soccer", "date": day, "limit": 100}) or {}).get("data") or []
        for x in self._day[day]:
            if names.same_team((x.get("home") or {}).get("name") or "", home, 0.8) and \
                    names.same_team((x.get("away") or {}).get("name") or "", away, 0.8):
                return x.get("id")
        return None

    def stats(self, match_id: str) -> dict:
        return parse_bigballs_stats(self._get(f"/v1/matches/{match_id}/statistics"))


NOSY_BASE = "https://www.nosyapi.com/apiv2/service"


def parse_nosy_results(data: dict) -> list[dict]:
    """matches-result → [{home, away, date, ht_home, ht_away, corners_h/a, yellow_h/a, red_h/a}] (oran alanları ATILIR)."""
    out = []
    for x in (data or {}).get("data") or []:
        meta = {r.get("metaName"): r.get("value") for r in x.get("matchResult") or []}

        def iv(k):
            try:
                return int(meta[k]) if meta.get(k) not in (None, "") else None
            except (TypeError, ValueError):
                return None
        out.append({"home": x.get("Team1"), "away": x.get("Team2"), "date": x.get("Date"),
                    "ht_home": iv("htHomeScore"), "ht_away": iv("htAwayScore"),
                    "home_stats": {k: v for k, v in (("corners", iv("homeCorner")), ("yellow", iv("homeyellowCard")),
                                                      ("red", iv("homeredCard"))) if v is not None},
                    "away_stats": {k: v for k, v in (("corners", iv("awayCorner")), ("yellow", iv("awayyellowCard")),
                                                      ("red", iv("awayredCard"))) if v is not None}})
    return out


class NosyResults:
    """NosyAPI 'Maç Sonuçları' — yalnızca sonuç/İY/korner/kart (iddaa oranı kullanılmaz)."""

    def __init__(self, key: str | None):
        self.key = key
        self.calls = 0
        self._day: dict = {}

    @property
    def available(self) -> bool:
        return bool(self.key)

    def day(self, d: str) -> list[dict]:
        if d not in self._day:
            r = get(f"{NOSY_BASE}/matches-result", params={"type": 1, "date": d}, headers={"X-NSYP": self.key})
            self.calls += 1
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code != 200 or data.get("status") != "success":
                raise SourceError(f"NosyAPI HTTP {r.status_code}: {(data.get('messageTR') or data.get('message') or '')[:120]}")
            self._day[d] = parse_nosy_results(data)
        return self._day[d]

    def find(self, d: str, home: str, away: str) -> dict | None:
        for x in self.day(d):
            if names.same_team(x["home"] or "", home, 0.8) and names.same_team(x["away"] or "", away, 0.8):
                return x
        return None
