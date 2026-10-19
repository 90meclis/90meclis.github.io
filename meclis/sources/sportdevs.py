"""SportDevs Football API (football.sportdevs.com) — SPORTDEVS_KEY (Bearer). Ücretsiz: 300 istek/gün.
Sorgular PostgREST sözdizimiyle (start_time=gte.…) yapılır; ligler ad + ülke ile eşleştirilir."""
from __future__ import annotations

from datetime import date, timedelta

from ..timeutil import to_iso
from .http import SourceError, get

SOURCE = "sportdevs"
BASE = "https://football.sportdevs.com"
LEAGUE_NAMES = {("turkey", "super lig"): "T1", ("england", "premier league"): "E0", ("england", "championship"): "E1",
                ("spain", "laliga"): "SP1", ("spain", "la liga"): "SP1", ("italy", "serie a"): "I1",
                ("germany", "bundesliga"): "D1", ("france", "ligue 1"): "F1", ("netherlands", "eredivisie"): "N1",
                ("portugal", "liga portugal"): "P1"}


def _league(m: dict) -> str | None:
    country = (m.get("class_name") or m.get("country_name") or "").lower()
    name = (m.get("league_name") or m.get("tournament_name") or "").lower().replace("ü", "u")
    if "2." in name or " 2" in name or "women" in name:
        return None
    return next((c for (ct, kw), c in LEAGUE_NAMES.items() if ct in country and kw in name), None)


def parse_matches(data: list[dict]) -> list[dict]:
    out = []
    for m in data or []:
        lg = _league(m)
        if not lg or not m.get("home_team_name") or not m.get("start_time"):
            continue
        st = (m.get("status_type") or "").lower()
        hs, as_ = m.get("home_team_score") or {}, m.get("away_team_score") or {}
        done = st == "finished" and hs.get("current") is not None
        status = "bitti" if done else ("basladi" if st == "live" else
                 ("ertelendi" if st == "postponed" else ("iptal" if st in ("canceled", "cancelled") else "planlandi")))
        out.append({
            "source": SOURCE, "league": lg, "kickoff_at": to_iso(m["start_time"]),
            "home_name": m["home_team_name"], "away_name": m.get("away_team_name"), "status": status,
            "home_goals": hs.get("current") if done else None, "away_goals": as_.get("current") if done else None,
            "ht_home_goals": hs.get("period_1") if done else None, "ht_away_goals": as_.get("period_1") if done else None,
            "venue": m.get("arena_name") or None, "ext_ids": {"sportdevs": m.get("id")},
        })
    return out


class SportDevs:
    def __init__(self, key: str | None):
        self.key = key

    @property
    def available(self) -> bool:
        return bool(self.key)

    def matches(self, d_from: date, d_to: date, max_pages: int = 4) -> list[dict]:
        out = []
        for page in range(max_pages):
            params = [("start_time", f"gte.{d_from.isoformat()}T00:00:00"),
                      ("start_time", f"lt.{(d_to + timedelta(days=1)).isoformat()}T00:00:00"),
                      ("limit", "50"), ("offset", str(page * 50))]
            r = get(f"{BASE}/matches", params=params, headers={"Authorization": f"Bearer {self.key}"})
            if r.status_code in (401, 403):
                raise SourceError(f"SportDevs yetki hatası (HTTP {r.status_code})")
            if r.status_code != 200:
                raise SourceError(f"SportDevs HTTP {r.status_code}")
            rows = r.json() or []
            out += parse_matches(rows)
            if len(rows) < 50:
                break
        return out

    def lineups(self, sportdevs_match_id: int) -> list[dict]:
        """/matches-lineups?id=eq.<maç> → [{side, formation, start_xi, subs, confirmed, missing}].
        Belgeye göre kadro kimliği maç kimliğiyle aynıdır; 5 dakikada bir güncellenir."""
        r = get(f"{BASE}/matches-lineups", params=[("id", f"eq.{int(sportdevs_match_id)}")],
                headers={"Authorization": f"Bearer {self.key}"})
        if r.status_code in (401, 403):
            raise SourceError(f"SportDevs yetki hatası (HTTP {r.status_code})")
        if r.status_code != 200:
            raise SourceError(f"SportDevs HTTP {r.status_code}")
        return parse_lineups(r.json() or [])


MISSING_REASONS = {0: "diğer", 1: "sakat", 2: "hasta", 3: "cezalı", 11: "cezalı (sarı kart)",
                   12: "cezalı (çift sarı)", 13: "cezalı (kırmızı kart)", 21: "kiralık"}


def parse_lineups(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows or []:
        for side in ("home", "away"):
            t = row.get(f"{side}_team") or {}
            players = t.get("players") or []
            xi, subs, missing = [], [], []
            for p in players:
                name = p.get("player_name") or p.get("name")
                if not name:
                    continue
                rec = {"name": name, "number": p.get("shirt_number") or p.get("jersey_number"), "pos": p.get("position")}
                if p.get("missing") or p.get("reason") is not None and p.get("is_missing"):
                    missing.append({"player_name": name, "kind": MISSING_REASONS.get(p.get("reason"), "kesin yok"),
                                    "reason": MISSING_REASONS.get(p.get("reason"))})
                elif p.get("substitute"):
                    subs.append(rec)
                else:
                    xi.append(rec)
            if xi or missing:
                out.append({"side": side, "formation": t.get("formation"), "start_xi": xi, "subs": subs,
                            "confirmed": bool(row.get("confirmed")), "missing": missing})
    return out
