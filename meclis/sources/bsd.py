"""Bzzoiro Sports Data (BSD) Football API v2 — BSD_API_KEY gerekir (ücretsiz kayıt: https://sports.bzzoiro.com/register/).

Ücretsiz futbol planı: tüm v2 uç noktaları, kota yok (IP başına 10 istek/sn). Lisans (Data usage & license v4.0):
iç kullanım için saklama ve kendi uygulamanda gösterme serbest; ham verinin yeniden satışı yasak; kaynak gösterilir.

Sağladıkları (6 ligin hepsi, 19.10.2026'da anahtarla canlı doğrulandı; günlük kota başlığı: 7.500 istek):
fikstür/sonuç/İY, hakem (ad + kart ortalaması), stadyum (ad, şehir, kapasite, koordinat), konsensüs oranları
(1X2, Alt/Üst 1.5/2.5/3.5, KG Var/Yok; 4 saatte bir güncellenir), biten maç istatistiği (şut, isabetli şut, korner,
faul, kart, kale vuruşu, xG, topla oynama), maç başına sakat-cezalı-şüpheli listesi (unavailable_players), resmî ilk 11
(~1 saat önce) ve AI tahmini ilk 11 (maç öncesi, `confidence`), kadro + oyuncu uygunluğu.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..timeutil import now_utc, parse_dt, to_iso
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


def parse_odds(data: dict) -> dict:
    """/events/{id}/odds/ → iç oran sözlüğü (boş piyasa yazılmaz)."""
    o = (data or {}).get("odds") or {}
    src = f"{SOURCE}:konsensüs"
    out = {}
    if all(o.get(k) for k in ("home_win", "draw", "away_win")):
        out["1X2"] = {"1": o["home_win"], "X": o["draw"], "2": o["away_win"], "src": src}
    for line, k in ((1.5, "15"), (2.5, "25"), (3.5, "35")):
        if o.get(f"over_{k}_goals") and o.get(f"under_{k}_goals"):
            out[f"OU_GOALS_{line:g}"] = {"ÜST": o[f"over_{k}_goals"], "ALT": o[f"under_{k}_goals"], "src": src}
    if o.get("btts_yes") and o.get("btts_no"):
        out["BTTS"] = {"VAR": o["btts_yes"], "YOK": o["btts_no"], "src": src}
    return out


def _num(v):
    if isinstance(v, dict):
        v = v.get("actual") if "actual" in v else v.get("value")
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def parse_stats(data: dict) -> dict:
    """/events/{id}/stats/ → {'home': {...}, 'away': {...}} (yalnızca dolu alanlar)."""
    out = {}
    for side in ("home", "away"):
        st = ((data or {}).get("stats") or {}).get(side) or {}
        vals = {"shots": _num(st.get("total_shots")), "shots_on_target": _num(st.get("shots_on_target")),
                "corners": _num(st.get("corner_kicks")), "fouls": _num(st.get("fouls")),
                "yellow": _num(st.get("yellow_cards")), "red": _num(st.get("red_cards")),
                "goal_kicks": _num(st.get("goal_kicks")),
                "xg": _num(st.get("expected_goals")) if st.get("expected_goals") is not None else _num(st.get("xg")),
                "possession": _num(st.get("ball_possession"))}
        vals = {k: (v if k in ("xg", "possession") else int(v)) for k, v in vals.items() if v is not None}
        if vals:
            out[side] = vals
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
    def __init__(self, key: str | None, max_calls: int = 1200):
        self.key = key
        self.max_calls = max_calls
        self._leagues: dict[int, str] | None = None
        self._ref: dict[int, str | None] = {}
        self._venue: dict[int, dict] = {}
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.key:
            raise SourceError("BSD_API_KEY tanımlı değil.")
        if self.calls >= self.max_calls:
            raise SourceError(f"BSD çalışma başı istek tavanı doldu ({self.max_calls}; günlük kota 7.500)")
        self.calls += 1
        r = get(f"{BASE}{path}", params=params, headers={"Authorization": f"Token {self.key}"})
        if r.status_code in (401, 403):
            raise SourceError(f"BSD yetki hatası (HTTP {r.status_code}) — BSD_API_KEY geçersiz olabilir")
        if r.status_code == 404:
            return {}
        if r.status_code != 200:
            raise SourceError(f"BSD HTTP {r.status_code}")
        return r.json() or {}

    def league_map(self) -> dict[int, str]:
        """BSD lig kimliği → iç lig kodu (config.LEAGUES.bsd_id; kimlikler /leagues/ ile doğrulandı)."""
        if self._leagues is None:
            from ..config import LEAGUES

            self._leagues = {lg.bsd_id: code for code, lg in LEAGUES.items() if lg.bsd_id}
        return self._leagues

    def events(self, d_from: date, d_to: date, leagues: list[str], enrich: bool = True,
               known: dict | None = None, odds_hours: float = 96, stats_for=None) -> list[dict]:
        """Maç kayıtları; enrich=True ise başlamasına ≤ odds_hours kalan maçlara oran (BSD daha uzağa oran vermez),
        bitenlere istatistik (stats_for verilmişse yalnızca o BSD kimliklerine), hakem ve stadyum eklenir.
        known = {bsd_event_id: {"referee", "venue", "city", "stats"}}: havuzda zaten olan bilgi yeniden istenmez."""
        self._known = known or {}
        self._odds_until = now_utc() + timedelta(hours=odds_hours)
        self._stats_for = stats_for
        lm = {k: v for k, v in self.league_map().items() if v in leagues}
        out = []
        raw: dict[int, dict] = {}
        for lid in lm:
            offset = 0
            for _ in range(5):
                data = self._get("/events/", {"league_id": lid, "date_from": d_from.isoformat(),
                                              "date_to": (d_to + timedelta(days=1)).isoformat(),
                                              "limit": 200, "offset": offset})
                for e in data.get("results") or []:
                    raw[e.get("id")] = e
                out += parse_events(data.get("results") or [], lm)
                if not data.get("next"):
                    break
                offset += 200
        if enrich and out:
            # maç başına 1–3 istek; BSD IP başına 10 istek/sn'ye izin verir → 6 paralel işçi
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(lambda rec: self._enrich(rec, raw.get(rec["ext_ids"]["bsd"]) or {}), out))
        return out

    def _enrich(self, rec: dict, e: dict) -> None:
        eid = rec["ext_ids"]["bsd"]
        kn = (getattr(self, "_known", None) or {}).get(eid) or {}
        try:
            if rec["status"] in ("planlandi", "basladi"):
                if parse_dt(rec["kickoff_at"]) <= getattr(self, "_odds_until", parse_dt(rec["kickoff_at"])):
                    odds = parse_odds(self._get(f"/events/{eid}/odds/"))
                    if odds:
                        rec["odds"] = odds
            elif rec["status"] == "bitti" and not kn.get("stats"):
                sf = getattr(self, "_stats_for", None)
                if sf is None or eid in sf:
                    st = parse_stats(self._get(f"/events/{eid}/stats/"))
                    if st:
                        rec["stats"] = st
            if kn.get("referee"):
                rec["referee"] = kn["referee"]
            elif e.get("referee_id"):
                rec["referee"] = self.referee(e["referee_id"])
            if kn.get("venue"):
                rec["venue"], rec["city"] = kn["venue"], kn.get("city")
            elif e.get("venue_id"):
                v = self.venue(e["venue_id"])
                rec["venue"], rec["city"] = v.get("name"), v.get("city")
        except Exception:  # zenginleştirme isteğe bağlı değil ama bir maçın hatası diğerlerini durdurmasın
            pass

    def referee(self, rid: int) -> str | None:
        if rid not in self._ref:
            self._ref[rid] = (self._get(f"/referees/{int(rid)}/") or {}).get("name")
        return self._ref[rid]

    def venue(self, vid: int) -> dict:
        if vid not in self._venue:
            self._venue[vid] = self._get(f"/venues/{int(vid)}/") or {}
        return self._venue[vid]

    def lineups(self, event_id: int) -> dict:
        return parse_lineups(self._get(f"/events/{int(event_id)}/lineups/"))

    def squad(self, team_id: int) -> list[dict]:
        return parse_squad(self._get(f"/teams/{int(team_id)}/squad/"))
