"""Yerel lig izi: Avrupa kupasında oynayan HER takımın bu sezonki yerel ligi çözülür ve doldurulur.

Takımın ligi bizim takip ettiğimiz liglerden biriyse (ör. Dortmund → D1) kendi verimiz kullanılır. Değilse
(ör. Sabah FK → Azerbaycan Premyer Liqası):
  1. API-Football /fixtures?date (günde 1 istek) → kupa maçındaki takımların API-Football kimliği,
     /leagues?team=&current=true (takım başına 1 istek, teams.ext_ids'e önbelleğe alınır) → yerel lig kimliği.
     Ücretsiz plan bu sezonun fikstür/puan durumu uçlarını kapatıyor, bu iki uç ise açık.
  2. TheSportsDB (ücretsiz, herkese açık anahtar) search_all_leagues → API-Football kimliğiyle eşleşen lig;
     eventsround.php ile bu sezonun BÜTÜN haftaları (sonuçlar + İY yok) → matches (lig kodu 'Y<tsdb id>').
  3. Puan durumu bu maçlardan v_puan_durumu ile hesaplanır. Kupa takımı yerel ligde kupa kimliğinin slug'ıyla
     yazılır; böylece v_takim_mac_istatistik'te Avrupa ve Lig satırları team_slug ile birleşir.
Uydurma yok: kaynak eşleşmezse takım 'çözülemedi' olarak listelenir.
"""
from __future__ import annotations

import time
from datetime import timedelta
from difflib import SequenceMatcher

from .analysis import season_start
from .names import canonical_key
from .sources.http import get
from .timeutil import now_utc, to_iso

TSDB = "https://www.thesportsdb.com/api/v1/json/123"
APIF = "https://v3.football.api-sports.io"


def _sim(a: str, b: str) -> float:
    a, b = canonical_key(a), canonical_key(b)
    if a and b and (a in b or b in a):
        return 0.9 + 0.1 * min(len(a), len(b)) / max(len(a), len(b))
    return SequenceMatcher(None, a, b).ratio()


class DomesticTrack:
    def __init__(self, store, settings, apif_key: str | None = None, max_apif: int = 30):
        self.store, self.s = store, settings
        self.key = apif_key
        self.max_apif, self.apif_calls = max_apif, 0
        self.log: list[str] = []
        self._tsdb_leagues: dict[str, dict] = {}

    # ---------------- yardımcılar
    def _apif(self, path: str, params: dict) -> list:
        if not self.key or self.apif_calls >= self.max_apif:
            return []
        self.apif_calls += 1
        r = get(f"{APIF}{path}", params=params, headers={"x-apisports-key": self.key})
        d = r.json()
        if d.get("errors"):
            self.log.append(f"⚠️ API-Football {path}: {d['errors']}")
            return []
        return d.get("response") or []

    def _tsdb(self, path: str, params: dict) -> dict:
        time.sleep(2.1)  # ücretsiz anahtar: dakikada 30 istek
        r = get(f"{TSDB}/{path}", params=params)
        try:
            return r.json() or {}
        except Exception:
            return {}

    def _tsdb_league_for_apif(self, apif_league: int, country: str) -> dict | None:
        if country not in self._tsdb_leagues:
            d = self._tsdb("search_all_leagues.php", {"c": country, "s": "Soccer"})
            self._tsdb_leagues[country] = {str(x.get("idAPIfootballv3")): x for x in (d.get("countries") or [])}
        return self._tsdb_leagues[country].get(str(apif_league))

    # ---------------- 1) takım → yerel lig
    def cup_teams(self, hours: float = 60) -> list[dict]:
        from .config import LEAGUES

        now = now_utc()
        cups = [k for k, v in LEAGUES.items() if v.cup]
        ms = self.store.select("matches", [("league", "in", cups), ("kickoff_at", "gte", to_iso(now - timedelta(hours=3))),
                                           ("kickoff_at", "lte", to_iso(now + timedelta(hours=hours)))])
        return ms

    def resolve(self, hours: float = 60) -> dict:
        """Her kupa takımı için teams.domestic_league yazar (bizim lig / 'Y<tsdb>' / çözülemedi)."""
        from .config import LEAGUES

        ms = self.cup_teams(hours)
        s0 = to_iso(season_start())
        dom_by_slug: dict[str, str] = {}
        cup_codes = {r["code"] for r in self.store.select("leagues", [("cup", "eq", True)])}
        for m in self.store.select("matches", [("kickoff_at", "gte", s0), ("status", "eq", "bitti")]):
            lg = m["league"]
            if (lg in LEAGUES and LEAGUES[lg].cup) or lg in cup_codes:
                continue
            for t in (m["home_team_id"], m["away_team_id"]):
                dom_by_slug[t.split(":", 1)[-1]] = lg
        # API-Football fikstür kimliği → takım kimlikleri (tarih başına 1 istek)
        apif_team: dict[str, int] = {}
        dates = sorted({m["kickoff_at"][:10] for m in ms if (m.get("ext_ids") or {}).get("apif")})
        fx: dict[str, dict] = {}
        for d in dates:
            for f in self._apif("/fixtures", {"date": d}):
                fx[str(f["fixture"]["id"])] = f
        out = {"resolved": [], "missing": []}
        for m in ms:
            f = fx.get(str((m.get("ext_ids") or {}).get("apif")))
            for side in ("home", "away"):
                tid = m[f"{side}_team_id"]
                if f:
                    apif_team[tid] = f["teams"][side]["id"]
        for m in ms:
            for side in ("home", "away"):
                tid, name = m[f"{side}_team_id"], m[f"{side}_name"]
                slug = tid.split(":", 1)[-1]
                team = self.store.get("teams", id=tid) or {"id": tid, "league": m["league"], "name": name, "ext_ids": {}}
                ext = dict(team.get("ext_ids") or {})
                if slug in dom_by_slug:
                    dl = dom_by_slug[slug]
                elif ext.get("domestic_tsdb_league"):
                    dl = f"Y{ext['domestic_tsdb_league']}"
                else:
                    dl = None
                    at = apif_team.get(tid) or ext.get("apif_team")
                    if at:
                        ext["apif_team"] = at
                        for lr in self._apif("/leagues", {"team": at, "current": "true"}):
                            if lr["league"]["type"] == "League":
                                tl = self._tsdb_league_for_apif(lr["league"]["id"], lr["country"]["name"])
                                ext["domestic_apif_league"] = lr["league"]["id"]
                                ext["domestic_country"] = lr["country"]["name"]
                                if tl:
                                    ext["domestic_tsdb_league"] = tl["idLeague"]
                                    ext["domestic_league_name"] = tl["strLeague"]
                                    dl = f"Y{tl['idLeague']}"
                                break
                if dl:
                    out["resolved"].append((name, dl))
                else:
                    out["missing"].append(name)
                self.store.upsert("teams", [{"id": tid, "league": team.get("league") or m["league"], "name": team.get("name") or name,
                                             "ext_ids": ext, "domestic_league": dl}])
        return out

    # ---------------- 2) yerel ligi doldur
    def fill_league(self, tsdb_id: str, cup_teams: dict[str, str], max_rounds: int = 46) -> int:
        """tsdb_id ligi için bu sezonun bütün haftalarını yazar. cup_teams: {kupa_slug: takım adı} — bu takımlar
        kupa slug'ıyla yazılır (Avrupa ↔ Lig birleşmesi)."""
        info = (self._tsdb("lookupleague.php", {"id": tsdb_id}).get("leagues") or [{}])[0]
        season = info.get("strCurrentSeason")
        if not season:
            return 0
        code = f"Y{tsdb_id}"
        self.store.upsert("leagues", [{"code": code, "name": info.get("strLeague"), "country": info.get("strCountry"),
                                       "cup": False, "source": "thesportsdb"}])
        s0 = season_start()
        events, empty = [], 0
        for r in range(1, max_rounds + 1):
            ev = self._tsdb("eventsround.php", {"id": tsdb_id, "r": r, "s": season}).get("events") or []
            if not ev:
                empty += 1
                if empty >= 2 and events:
                    break
                continue
            empty = 0
            events += ev
        names = {e[k] for e in events for k in ("strHomeTeam", "strAwayTeam")}
        slug_of = {}
        for n in names:  # kupa takımı eşleşmesi: en yüksek ad benzerliği ≥ 0.75
            best = max(cup_teams.items(), key=lambda kv: _sim(kv[1], n), default=None)
            slug_of[n] = best[0] if best and _sim(best[1], n) >= 0.75 else canonical_key(n)
        rows, teams = [], {}
        for e in events:
            if e.get("intHomeScore") in (None, "") or e.get("intAwayScore") in (None, ""):
                continue
            ko = f"{e['dateEvent']}T{(e.get('strTime') or '12:00:00')[:8]}+00:00"
            if ko < to_iso(s0):
                continue
            hs, as_ = slug_of[e["strHomeTeam"]], slug_of[e["strAwayTeam"]]
            hg, ag = int(e["intHomeScore"]), int(e["intAwayScore"])
            rows.append({"id": f"{code}:{e['dateEvent']}:{hs}:{as_}", "league": code, "season": season,
                         "kickoff_at": ko, "home_team_id": f"{code}:{hs}", "away_team_id": f"{code}:{as_}",
                         "home_name": e["strHomeTeam"], "away_name": e["strAwayTeam"], "home_goals": hg,
                         "away_goals": ag, "score": f"{hg}-{ag}", "status": "bitti", "durum": "bitti",
                         "venue": e.get("strVenue"), "ext_ids": {"tsdb": e["idEvent"]},
                         "sources": {"_all": ["thesportsdb"], "skor": "thesportsdb"}})
            for side, s in (("Home", hs), ("Away", as_)):
                teams[f"{code}:{s}"] = {"id": f"{code}:{s}", "league": code, "name": e[f"str{side}Team"],
                                        "ext_ids": {"tsdb": e[f"id{side}Team"]}, "domestic_league": code}
        if teams:
            self.store.upsert("teams", list(teams.values()))
        for i in range(0, len(rows), 200):
            self.store.upsert("matches", rows[i:i + 200])
        self.log.append(f"ℹ️ yerel lig {info.get('strLeague')} ({code}, {season}): {len(rows)} oynanmış maç "
                        f"(TheSportsDB, {len(events)} fikstür)")
        return len(rows)

    def run(self, hours: float = 60) -> dict:
        res = self.resolve(hours)
        by_lg: dict[str, dict[str, str]] = {}
        for t in self.store.select("teams", [("domestic_league", "like", "Y%")]):
            if ":" in t["id"] and not t["id"].startswith("Y"):
                by_lg.setdefault(t["domestic_league"][1:], {})[t["id"].split(":", 1)[1]] = t["name"]
        n = 0
        for lg, cup_teams in by_lg.items():
            try:
                n += self.fill_league(lg, cup_teams)
            except Exception as e:
                self.log.append(f"⚠️ yerel lig Y{lg}: {e}")
        return {"resolved": res["resolved"], "missing": res["missing"], "matches": n, "apif_calls": self.apif_calls,
                "log": self.log}
