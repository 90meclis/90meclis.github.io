"""Gece doldurma işi ('gecmis' komutu): BU SEZONUN eksiklerini kapatır — geçmiş sezon (2022–2024) çekilmez.

Kullanıcı kuralı: model girdileri yalnızca güncel sezondur. API-Football ücretsiz planı güncel sezonun sezonluk
sorgusunu kapatır ama fikstür kimliğiyle sorguyu açar. Günlük bütçenin (API_FOOTBALL_DAILY_BUDGET, 90; 45 istek
gün içi maç öncesi işler için ayrılır) kalanı bu sezon biten maçlara harcanır, en yeni maç önce:
  1. maç istatistiği yoksa   /fixtures/statistics  (şut, isabetli şut, korner, kart, faul, xG…)
  2. oyuncu dakikası yoksa   /fixtures/players     → player_matches (oyuncu önemi, yedek açığı, var/yok farkı)
  3. resmî ilk 11 yoksa      /fixtures/lineups     → lineups (Meclis tahmini ilk 11'in "son ilk 11'ler" bileşeni)
BSD tarafı (meclis/season.py) aynı eksikleri kendi kotasıyla doldurur; hangisi önce gelirse alan dolar.
İlerleme kendiliğinden tutulur: eksik olan her şey bir sonraki gece yeniden denenir. Defter tablolarına dokunulmaz.
"""
from __future__ import annotations

from .sources.http import SourceError
from .timeutil import now_utc, to_iso

SUMMARY = "api-football-sezon"


class Backfill:
    def __init__(self, pool, reserve: int = 45):
        self.pool, self.store, self.apif = pool, pool.store, pool.apif
        self.leagues = [lg for lg in pool.s.leagues if lg != "DEMO"]
        self.reserve = reserve
        self.log: list[str] = []
        self.counts = {"calls": 0, "stats": 0, "player_matches": 0, "lineups": 0}

    def budget_left(self) -> int:
        return self.apif.daily_budget - self.reserve - self.apif.calls_today()

    def pending(self) -> list[tuple[dict, list[str]]]:
        from .analysis import season_start
        from .teamnews import is_confirmed

        lo = to_iso(season_start())
        ms = [m for m in self.store.select("matches", [("status", "eq", "bitti"), ("kickoff_at", "gte", lo)])
              if m["league"] in self.leagues and (m.get("ext_ids") or {}).get("apif")]
        ids = [m["id"] for m in ms]
        have_st, have_pm, have_lu = set(), set(), {}
        for i in range(0, len(ids), 200):
            chunk = ids[i:i + 200]
            have_st |= {r["match_id"] for r in self.store.select("match_stats", [("match_id", "in", chunk)])}
            try:
                have_pm |= {r["match_id"] for r in self.store.select("player_matches", [("match_id", "in", chunk)])}
            except Exception:
                have_pm = None
            for r in self.store.select("lineups", [("match_id", "in", chunk)]):
                if is_confirmed(r):
                    have_lu[r["match_id"]] = have_lu.get(r["match_id"], 0) + 1
            if have_pm is None:
                have_pm = set(ids)  # tablo yok: oyuncu işi atlanır
        # önce önümüzdeki 36 saatte oynayacak takımların maçları (yarının bülteni), sonra en yeni maç önce
        from datetime import timedelta

        soon = self.store.select("matches", [("kickoff_at", "gte", to_iso(now_utc())),
                                             ("kickoff_at", "lt", to_iso(now_utc() + timedelta(hours=36)))])
        hot = {t for x in soon for t in (x.get("home_team_id"), x.get("away_team_id"))}
        out = []
        for m in sorted(ms, key=lambda m: (m.get("home_team_id") in hot or m.get("away_team_id") in hot,
                                           m["kickoff_at"]), reverse=True):
            jobs = [j for j, need in (("stats", m["id"] not in have_st), ("players", m["id"] not in have_pm),
                                      ("lineups", have_lu.get(m["id"], 0) < 2)) if need]
            if jobs:
                out.append((m, jobs))
        return out

    def _side(self, m: dict, team_apif) -> str | None:
        ext = m.get("ext_ids") or {}
        if team_apif is None:
            return None
        if str(ext.get("apif_home")) == str(team_apif):
            return "home"
        if str(ext.get("apif_away")) == str(team_apif):
            return "away"
        return None

    def run(self) -> dict:
        if not self.apif.available:
            self.log.append("⚠️ api-football: API_FOOTBALL_KEY tanımlı değil — bu sezonun API-Football doldurması atlandı")
            return {"log": self.log, **self.counts, "pending": None}
        todo = self.pending()
        done = 0
        for m, jobs in todo:
            stop = False
            for job in jobs:
                if self.budget_left() <= 0:
                    self.log.append(f"ℹ️ günlük API-Football bütçesi doldu ({self.apif.calls_today()} istek); "
                                    "kalan eksikler sonraki gece")
                    stop = True
                    break
                fid = int(m["ext_ids"]["apif"])
                try:
                    self.counts["calls"] += 1
                    if job == "stats":
                        if self.pool.fill_match_stats(m):
                            self.counts["stats"] += 1
                    elif job == "players":
                        rows = []
                        for p in self.apif.fixture_players(fid):
                            side = self._side(m, p.get("team_apif"))
                            if side and p.get("name"):
                                rows.append({"match_id": m["id"], "team_id": m[f"{side}_team_id"],
                                             "player_id": f"apif:{p['player_id']}", "name": p["name"],
                                             "position": p.get("position"), "started": bool(p.get("started")),
                                             "minutes": p["minutes"], "goals": p["goals"], "assists": p["assists"],
                                             "rating": p.get("rating"), "kickoff_at": m["kickoff_at"],
                                             "source": "api-football"})
                        if rows:
                            self.store.upsert("player_matches", rows)
                            self.counts["player_matches"] += 1
                    else:
                        rows = []
                        for lu in self.apif.lineups(fid):
                            side = self._side(m, lu.get("team_apif"))
                            if side:
                                rows.append({"match_id": m["id"], "side": side, "formation": lu.get("formation"),
                                             "start_xi": lu["start_xi"], "subs": lu["subs"], "coach": lu.get("coach"),
                                             "source": "api-football", "lineup_status": "resmi",
                                             "updated_at": to_iso(now_utc())})
                        if rows:
                            self.store.upsert("lineups", rows)
                            self.counts["lineups"] += 1
                except SourceError as e:
                    self.log.append(f"⚠️ {m['id']} {job}: {e}")
                    if "bütçe" in str(e) or "limit" in str(e).lower() or "429" in str(e):
                        stop = True
                        break
            done += 1
            if stop:
                break
        left = max(0, len(todo) - done)
        msg = (f"Bu sezon (API-Football, fikstür kimliğiyle): {self.counts['stats']} maç istatistiği, "
               f"{self.counts['player_matches']} maçın oyuncu dakikaları, {self.counts['lineups']} resmî ilk 11; "
               f"{self.counts['calls']} istek; eksiği kalan {left} maç")
        self.log.append(msg)
        try:
            self.store.set_source_status(SUMMARY, True, msg)
        except Exception:
            pass
        return {"log": self.log, **self.counts, "pending": left}
