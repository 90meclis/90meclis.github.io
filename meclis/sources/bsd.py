"""Bzzoiro Sports Data (BSD) Football API v2 — BSD_API_KEY gerekir (ücretsiz kayıt: https://sports.bzzoiro.com/register/).

Ücretsiz futbol planı: tüm v2 uç noktaları, kota yok (IP başına 10 istek/sn). Lisans (Data usage & license v4.0):
iç kullanım için saklama ve kendi uygulamanda gösterme serbest; ham verinin yeniden satışı yasak; kaynak gösterilir.

Sağladıkları (6 ligin hepsi): fikstür/sonuç/İY, maç başına sakat-cezalı-şüpheli listesi (unavailable_players),
resmî ilk 11 (~1 saat önce) ve AI tahmini ilk 11 (maç öncesi, `confidence`), kadro + oyuncu uygunluğu.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "bsd"
BASE = "https://sports.bzzoiro.com/api/v2"
# (ülke, lig adı anahtar sözcüğü) → iç lig kodu
LEAGUE_NAMES = {("turkey", "super lig"): "T1", ("england", "premier league"): "E0", ("england", "championship"): "E1",
                ("spain", "la liga"): "SP1", ("spain", "laliga"): "SP1", ("italy", "serie a"): "I1", ("germany", "bundesliga"): "D1",
                ("france", "ligue 1"): "F1", ("netherlands", "eredivisie"): "N1", ("portugal", "liga portugal"): "P1"}
_DONE = {"finished", "aet", "penalties"}
_LIVE = {"inprogress", "1st_half", "halftime", "2nd_half", "extratime"}
# BSD uygunluk durumu → iç durum (model.injuries.certainty ile uyumlu)
STATUS_TR = {"injured": "kesin yok (sakat)", "suspended": "cezalı", "doubtful": "şüpheli", "out": "kesin yok"}


def league_code(country: str | None, name: str | None) -> str | None:
    c = (country or "").lower()
    n = (name or "").lower().replace("ü", "u").replace("é", "e")
    if any(x in n for x in ("2.", " 2", "women", "cup", "pokal", "copa", "coupe", "segunda", "serie b")):
        return None
    for (ct, kw), code in LEAGUE_NAMES.items():
        if ct in c and kw in n:
            if code == "D1" and "austria" in c:
                return None
            return code
    return None


def parse_events(results: list[dict], league_map: dict[int, str]) -> list[dict]:
    out = []
    for e in results or []:
        lg = league_map.get(e.get("league_id"))
        if not lg or not e.get("home_team") or not e.get("event_date"):
            continue
        st = (e.get("status") or "").lower()
        done = st in _DONE and e.get("home_score") is not None
        status = ("bitti" if done else "basladi" if st in _LIVE else "ertelendi" if st in ("postponed", "delayed")
                  else "iptal" if st == "cancelled" else "planlandi")
        out.append({
            "source": SOURCE, "league": lg, "kickoff_at": to_iso(e["event_date"]),
            "home_name": e["home_team"], "away_name": e.get("away_team"), "status": status,
            "home_goals": e.get("home_score") if done else None, "away_goals": e.get("away_score") if done else None,
            "ht_home_goals": e.get("home_score_ht") if done else None,
            "ht_away_goals": e.get("away_score_ht") if done else None,
            "ext_ids": {"bsd": e.get("id"), "bsd_home": e.get("home_team_id"), "bsd_away": e.get("away_team_id")},
        })
    return out


def _side_players(side: dict | None, key: str) -> list[dict]:
    return [{"name": p.get("name"), "number": p.get("jersey_number"), "pos": p.get("position"),
             **({"ai_score": p["ai_score"]} if p.get("ai_score") is not None else {})}
            for p in ((side or {}).get(key) or []) if p.get("name")]


def parse_lineups(data: dict) -> dict:
    """/events/{id}/lineups/ → {'status': 'resmi'|'tahmini'|None, 'lineups': {side: {...}}, 'unavailable': {side: [...]}|None}"""
    st = (data or {}).get("lineup_status")
    status = {"confirmed": "resmi", "predicted": "tahmini"}.get(st)
    lus = {}
    for side in ("home", "away"):
        s = ((data or {}).get("lineups") or {}).get(side)
        if s:
            lus[side] = {"formation": s.get("formation"), "team_name": s.get("team_name"), "team_bsd": s.get("team_id"),
                         "confidence": s.get("confidence"), "start_xi": _side_players(s, "players"),
                         "subs": _side_players(s, "substitutes")}
    un = (data or {}).get("unavailable_players")
    unavailable = None
    if isinstance(un, dict):
        unavailable = {side: [{"player_name": p.get("name"), "player_id": p.get("id"),
                               "kind": STATUS_TR.get((p.get("status") or "").lower(), p.get("status")),
                               "reason": p.get("reason")} for p in (un.get(side) or []) if p.get("name")]
                       for side in ("home", "away")}
    return {"status": status, "lineups": lus, "unavailable": unavailable}


def parse_squad(data: dict) -> list[dict]:
    out = []
    for p in (data or {}).get("players") or []:
        if not p.get("name"):
            continue
        av = (p.get("availability") or "available").lower()
        out.append({"name": p["name"], "position": p.get("position"), "number": p.get("jersey_number"),
                    "bsd_id": p.get("id"), "availability": av,
                    "kind": STATUS_TR.get(av) if av != "available" else None,
                    "reason": p.get("injury_type"), "expected_return": p.get("injury_expected_return")})
    return out


class BSD:
    def __init__(self, key: str | None):
        self.key = key
        self._leagues: dict[int, str] | None = None

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.key:
            raise SourceError("BSD_API_KEY tanımlı değil.")
        r = get(f"{BASE}{path}", params=params, headers={"Authorization": f"Token {self.key}"})
        if r.status_code in (401, 403):
            raise SourceError(f"BSD yetki hatası (HTTP {r.status_code}) — BSD_API_KEY geçersiz olabilir")
        if r.status_code == 404:
            return {}
        if r.status_code != 200:
            raise SourceError(f"BSD HTTP {r.status_code}")
        return r.json() or {}

    def league_map(self) -> dict[int, str]:
        if self._leagues is None:
            out, offset = {}, 0
            for _ in range(10):
                data = self._get("/leagues/", {"limit": 200, "offset": offset})
                for lg in data.get("results") or []:
                    code = league_code(lg.get("country"), lg.get("name"))
                    if code and not lg.get("is_women") and code not in out.values():
                        out[lg["id"]] = code
                if not data.get("next"):
                    break
                offset += 200
            self._leagues = out
        return self._leagues

    def events(self, d_from: date, d_to: date, leagues: list[str]) -> list[dict]:
        lm = {k: v for k, v in self.league_map().items() if v in leagues}
        out = []
        for lid in lm:
            offset = 0
            for _ in range(5):
                data = self._get("/events/", {"league_id": lid, "date_from": d_from.isoformat(),
                                              "date_to": (d_to + timedelta(days=1)).isoformat(),
                                              "limit": 200, "offset": offset})
                out += parse_events(data.get("results") or [], lm)
                if not data.get("next"):
                    break
                offset += 200
        return out

    def lineups(self, event_id: int) -> dict:
        return parse_lineups(self._get(f"/events/{int(event_id)}/lineups/"))

    def squad(self, team_id: int) -> list[dict]:
        return parse_squad(self._get(f"/teams/{int(team_id)}/squad/"))
