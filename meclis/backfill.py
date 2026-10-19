"""API-Football ücretsiz planıyla geçmiş veri doldurma (2022–2024), günlük 100 istek içinde, kaldığı yerden devam eder.

Neden: ücretsiz plan güncel sezonu kapatıyor ama 2022–2024'ü açıyor. Bu sezonlar
  * oyuncu önem puanı (dakika, ilk 11, gol+asist) için kulüp bazında son bilinen istatistiği,
  * geçmiş sakat/cezalı kayıtlarını (var/yok farkı ve model eğitimi için),
  * fikstür kimliklerini (sakatlıkları maçlara bağlamak için)
sağlar. Sıra: en yeni sezon önce; her lig-sezon için fikstür → oyuncular (sayfa sayfa) → sakatlıklar.

İlerleme `source_status` tablosunda 'gecmis:apif:<lig>:<sezon>:<iş>' satırlarında tutulur (ok=true → bitti;
oyuncular için mesajda 'sayfa=<sonraki>/<toplam>'). Özet 'api-football-gecmis' satırındadır.
Bütçe: API-Football günlük sayacı (aynı tablo) `API_FOOTBALL_DAILY_BUDGET` (90) eksi 45 isteklik rezerv
(güncel sezon: dün/bugün/yarın fikstür + sakat/cezalı + maç öncesi ilk 11 için) değerine ulaşınca durur; ertesi gün aynı komut kaldığı yerden sürer. Tahmin defterine (predictions/coupons) dokunulmaz.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from . import names
from .pool import TeamRegistry, merge_records
from .sources.http import SourceError
from .timeutil import now_utc, to_iso

SEASONS = (2024, 2023, 2022)
JOBS = ("fixtures", "players", "injuries")
SUMMARY = "api-football-gecmis"
MAX_PAGE = 3  # ücretsiz plan: "limited to a maximum value of 3 for the Page parameter"


def task_key(league: str, season: int, job: str) -> str:
    return f"gecmis:apif:{league}:{season}:{job}"


def season_window(season: int) -> tuple[str, str]:
    lo = datetime(season, 7, 1, tzinfo=timezone.utc)
    hi = datetime(season + 1, 7, 15, tzinfo=timezone.utc)
    return to_iso(lo), to_iso(hi)


class Backfill:
    def __init__(self, pool, reserve: int = 45, seasons=SEASONS):
        self.pool = pool
        self.store = pool.store
        self.apif = pool.apif
        from .config import LEAGUES

        # API-Football geçmiş doldurma yalnızca API-Football kimliği olan ligler için
        self.leagues = [lg for lg in pool.s.leagues if lg != "DEMO" and lg in LEAGUES and LEAGUES[lg].apif_id]
        self.reserve = reserve
        self.seasons = seasons
        self.log: list[str] = []
        self.counts = {"calls": 0, "matches": 0, "players": 0, "injuries": 0}

    # ------------------------------------------------------------ ilerleme
    def _status(self, key: str) -> dict:
        return self.store.get("source_status", source=key) or {}

    def _done(self, key: str) -> bool:
        return bool(self._status(key).get("ok"))

    def _mark(self, key: str, ok: bool, msg: str) -> None:
        self.store.set_source_status(key, ok, msg)

    def budget_left(self) -> int:
        return self.apif.daily_budget - self.reserve - self.apif.calls_today()

    def pending(self) -> list[tuple[str, int, str]]:
        return [(lg, se, job) for se in self.seasons for lg in self.leagues for job in JOBS
                if not self._done(task_key(lg, se, job))]

    # ------------------------------------------------------------ yardımcılar
    def _registry(self) -> TeamRegistry:
        reg = TeamRegistry()
        for t in self.store.select("teams"):
            reg.add(t["league"], t["id"].split(":", 1)[1], t["name"])
        return reg

    def _season_matches(self, league: str, season: int) -> list[dict]:
        lo, hi = season_window(season)
        return self.store.select("matches", [("league", "eq", league), ("kickoff_at", "gte", lo),
                                             ("kickoff_at", "lt", hi)])

    # ------------------------------------------------------------ işler
    def do_fixtures(self, league: str, season: int) -> None:
        recs = self.apif.season_fixtures(league, season)
        self.counts["calls"] += 1
        reg = self._registry()
        existing = self._season_matches(league, season)
        merged = merge_records(recs, reg, existing)
        self.pool.save(merged)
        self.counts["matches"] += len(merged)
        self._mark(task_key(league, season, "fixtures"), True, f"{len(recs)} fikstür → {len(merged)} maç")
        self.log.append(f"✅ {league} {season}: {len(recs)} fikstür, {len(merged)} birleşik maç")

    def _team_map(self, league: str, season: int) -> dict[int, str]:
        """API-Football takım kimliği → iç takım kimliği (sezon maçlarının ext_ids'inden)."""
        out = {}
        for m in self._season_matches(league, season):
            ext = m.get("ext_ids") or {}
            for side in ("home", "away"):
                if ext.get(f"apif_{side}"):
                    out[int(ext[f"apif_{side}"])] = m[f"{side}_team_id"]
        return out

    def do_players(self, league: str, season: int) -> bool:
        """Takım takım oyuncu istatistikleri. Ücretsiz plan `page` parametresini en fazla 3'e izin veriyor
        (lig bazında sayfalama bu yüzden kullanılamaz); takım başına ≤3 sayfa × 20 oyuncu yeterli."""
        key = task_key(league, season, "players")
        msg = self._status(key).get("message") or ""
        m = re.search(r"takim=(\d+)/(\d+) sayfa=(\d+)", msg)
        tmap = self._team_map(league, season)
        teams = sorted(tmap)
        ti, page = (int(m.group(1)), int(m.group(3))) if m else (0, 1)
        while ti < len(teams):
            if self.budget_left() <= 0:
                self._mark(key, False, f"sürüyor: takim={ti}/{len(teams)} sayfa={page}")
                return False
            apif_team = teams[ti]
            rows, total = self.apif.team_players_page(apif_team, season, page)
            self.counts["calls"] += 1
            ts = to_iso(now_utc())
            out = []
            for p in rows:
                if not p.get("name"):
                    continue
                if not p.get("no_team_stats") and not (p.get("minutes") or p.get("appearances")):
                    continue  # bu takımda hiç oynamamış oyuncu önem hesabına katkı vermez
                # no_team_stats: başka kulübün istatistiği gelmişti → boş yazılır (eski hatalı satır da düzelir)
                out.append({"team_id": tmap[apif_team], "player_key": f"apif:{p['player_key']}:{season}",
                            "name": p["name"], "position": p.get("position"), "minutes": p.get("minutes"),
                            "appearances": p.get("appearances"), "lineups": p.get("lineups"), "goals": p.get("goals"),
                            "assists": p.get("assists"), "season": str(season),
                            "stats_source": f"api-football {season}", "source": "api-football", "updated_at": ts})
            if out:
                self.store.upsert("players", out)
                self.counts["players"] += len(out)
            if page >= min(total, MAX_PAGE) or not rows:
                ti, page = ti + 1, 1
            else:
                page += 1
            self._mark(key, False, f"sürüyor: takim={ti}/{len(teams)} sayfa={page}")
        self._mark(key, True, f"tamam: {len(teams)} takım")
        return True

    def do_injuries(self, league: str, season: int) -> None:
        from .model.injuries import find_player, player_importance

        raw = self.apif.season_injuries(league, season)
        self.counts["calls"] += 1
        by_fx: dict[int, dict] = {}
        for m in self._season_matches(league, season):
            fx = (m.get("ext_ids") or {}).get("apif")
            if fx:
                by_fx[int(fx)] = m
        tmap = self._team_map(league, season)
        players: dict[str, list[dict]] = {}
        ts = to_iso(now_utc())
        rows = {}
        for it in raw:
            if not it.get("player_name"):
                continue
            m = by_fx.get(int(it["fixture_apif"])) if it.get("fixture_apif") else None
            tid = tmap.get(it.get("team_apif"))
            if not tid:
                continue
            if tid not in players:
                players[tid] = [p for p in self.store.select("players", [("team_id", "eq", tid)])
                                if str(p.get("season")) == str(season) and str(p.get("player_key", "")).startswith("apif:")]
            kind = {"Missing Fixture": "kesin yok", "Questionable": "şüpheli"}.get(it.get("kind"), it.get("kind"))
            pl = find_player(it["player_name"], players[tid])
            imp = player_importance(pl, players[tid], kind)
            rid = f"apif:{it.get('fixture_apif')}:{it.get('player_id') or names.basic_key(it['player_name'])}"
            side = ("home" if m["home_team_id"] == tid else "away") if m else None
            rows[rid] = {"id": rid, "match_id": m["id"] if m else None, "team_id": tid,
                         "team_name": m[f"{side}_name"] if m else it.get("team_name"),
                         "player_name": it["player_name"], "injury_status": kind, "reason": it.get("reason"),
                         "matches_played": (pl or {}).get("appearances"), "key_matches": (pl or {}).get("lineups"),
                         "goal_contribution": imp.get("ga_share"), "defensive_contribution": imp.get("defensive_share"),
                         "minutes_share": imp.get("minutes_share"), "weight_score": imp["importance"],
                         "is_key": imp["is_key"], "source": f"api-football (geçmiş {season})", "fetched_at": ts}
        self.store.upsert("injuries", list(rows.values()))
        self.counts["injuries"] += len(rows)
        linked = sum(1 for r in rows.values() if r["match_id"])
        self._mark(task_key(league, season, "injuries"), True, f"{len(raw)} kayıt, {len(rows)} yazıldı, {linked} maça bağlı")
        self.log.append(f"✅ {league} {season}: {len(rows)} geçmiş sakat/cezalı kaydı ({linked} maça bağlı)")

    # ------------------------------------------------------------ çalıştır
    def run(self, max_tasks: int | None = None) -> dict:
        if not self.apif.available:
            self.log.append("⚠️ api-football: API_FOOTBALL_KEY tanımlı değil — geçmiş veri doldurma atlandı")
            return {"log": self.log, **self.counts, "pending": None}
        n = 0
        for lg, se, job in self.pending():
            if self.budget_left() <= 0:
                self.log.append(f"ℹ️ günlük API-Football bütçesi doldu ({self.apif.calls_today()} istek); "
                                f"yarın kaldığı yerden sürer")
                break
            if self.apif.season_blocked(se):
                continue
            if job != "fixtures" and not self._done(task_key(lg, se, "fixtures")):
                continue
            if job == "injuries" and not self._done(task_key(lg, se, "players")):
                continue
            try:
                if job == "fixtures":
                    self.do_fixtures(lg, se)
                elif job == "players":
                    if not self.do_players(lg, se):
                        continue
                else:
                    self.do_injuries(lg, se)
            except SourceError as e:
                self.log.append(f"⚠️ {lg} {se} {job}: {e}")
                if "bütçe" in str(e) or "limit" in str(e).lower() or "429" in str(e):
                    break
                continue
            n += 1
            if max_tasks and n >= max_tasks:
                break
        pend = self.pending()
        total = len(self.seasons) * len(self.leagues) * len(JOBS)
        msg = (f"{total - len(pend)}/{total} iş bitti; bu çalıştırma: {self.counts['calls']} istek, "
               f"{self.counts['matches']} maç, {self.counts['players']} oyuncu, {self.counts['injuries']} sakatlık")
        self.store.set_source_status(SUMMARY, True, msg)
        self.log.append(f"ℹ️ geçmiş veri: {msg}")
        return {"log": self.log, **self.counts, "pending": len(pend), "total": total}
