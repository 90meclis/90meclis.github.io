"""Bu sezonun (2026/27) oyuncu ve maç verisini biriktirme — 'sezon' işi.

Oyuncu önemi GÜNCEL sezondan gelir: BSD'de biten her maç için iki istek
  /events/{id}/lineups/       → ilk 11 + yedekler (oyuncu kimliği, ad, mevki)
  /events/{id}/player-stats/  → oyuncu başına dakika, gol, asist, kart, puan
`player_matches` tablosuna maç maç yazılır; resmî ilk 11 ayrıca `lineups` tablosuna girer (Meclis tahmini ilk 11'in
"son resmî ilk 11'ler" bileşeni). Bu sezonun eksik maç istatistikleri de (şut, korner, kart, kale vuruşu) aynı işte
BSD'den tamamlanır — sonuçlandırmayı beklemeden.

Okuma anında (teamnews.current_players) takım başına toplanır:
  m dakika payı, s ilk 11 payı, c gol+asist payı (bu sezon)
  r yedek açığı  = (oyuncunun dakikası − mevkisindeki ilk yedeğin dakikası) / oyuncunun dakikası  (yalnızca
                   mevkisinde ilk k'da ise; k: K 1, D 4, O 3, F 2)
  d′ var/yok farkı = clip((maç başı averaj oynadığı maçlarda − oynamadığı maçlarda) / 2, 0, 1) × min(1, n_yok/5);
                   en az 2 "var" ve 2 "yok" maçı gerekir, yoksa bileşen formülden çıkar.
İstek tavanı çalışma başına `max_calls` (BSD günlük kota 7.500); kalan maçlar sonraki çalışmaya kalır.
"""
from __future__ import annotations

from .analysis import season_start
from .timeutil import now_utc, to_iso

STARTERS_PER_GROUP = {"GK": 1, "DEF": 4, "MID": 3, "ATT": 2}


def parse_player_stats(lineups_raw: dict, stats_raw: dict, match: dict) -> list[dict]:
    """BSD ilk 11 + oyuncu istatistiği → player_matches satırları."""
    lus = (lineups_raw or {}).get("lineups") or {}
    team_side, meta = {}, {}
    for side in ("home", "away"):
        s = lus.get(side) or {}
        if s.get("team_id") is not None:
            team_side[s["team_id"]] = side
        for key, started in (("players", True), ("substitutes", False)):
            for p in s.get(key) or []:
                if p.get("id") is not None:
                    meta[p["id"]] = {"name": p.get("name"), "position": p.get("position"), "started": started,
                                     "side": side}
    out = []
    for ps in (stats_raw or {}).get("player_stats") or []:
        pid = ps.get("player_id")
        mt = meta.get(pid) or {}
        side = mt.get("side") or team_side.get(ps.get("team_id"))
        if not side or not mt.get("name"):
            continue
        out.append({"match_id": match["id"], "team_id": match[f"{side}_team_id"], "player_id": f"bsd:{pid}",
                    "name": mt["name"], "position": mt.get("position"), "started": bool(mt.get("started")),
                    "minutes": int(ps.get("minutes_played") or 0), "goals": int(ps.get("goals") or 0),
                    "assists": int(ps.get("goal_assist") or 0), "rating": ps.get("rating"),
                    "kickoff_at": match["kickoff_at"], "source": "bsd"})
    return out


def team_season_players(pm_rows: list[dict], team_matches: list[dict], team_id: str) -> list[dict]:
    """player_matches satırlarından takımın bu sezonki oyuncu özeti (dakika, ilk 11, G+A, r, d′)."""
    from .model.injuries import _pos_group

    rows = [r for r in pm_rows if r.get("team_id") == team_id]
    if not rows:
        return []
    played_matches = sorted({r["match_id"] for r in rows})
    gd = {}
    for m in team_matches:
        if m["id"] in played_matches and m.get("home_goals") is not None and m.get("away_goals") is not None:
            d = m["home_goals"] - m["away_goals"]
            gd[m["id"]] = d if m["home_team_id"] == team_id else -d
    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["player_id"], {"player_id": r["player_id"], "name": r["name"], "position": r.get("position"),
                                            "minutes": 0, "lineups": 0, "appearances": 0, "goals": 0, "assists": 0,
                                            "_in": set()})
        a["minutes"] += r.get("minutes") or 0
        a["lineups"] += 1 if r.get("started") else 0
        a["appearances"] += 1 if (r.get("minutes") or 0) > 0 else 0
        a["goals"] += r.get("goals") or 0
        a["assists"] += r.get("assists") or 0
        if (r.get("minutes") or 0) > 0:
            a["_in"].add(r["match_id"])
    players = list(agg.values())
    # r: yedek açığı
    by_group: dict[str, list[dict]] = {}
    for p in players:
        by_group.setdefault(_pos_group(p.get("position")), []).append(p)
    for g, ps in by_group.items():
        ps.sort(key=lambda p: p["minutes"], reverse=True)
        k = STARTERS_PER_GROUP.get(g)
        for i, p in enumerate(ps):
            if not k or p["minutes"] <= 0:
                p["r"] = None
            elif i < k:
                backup = ps[k]["minutes"] if len(ps) > k else 0
                p["r"] = round(max(0.0, min(1.0, (p["minutes"] - backup) / p["minutes"])), 3)
            else:
                p["r"] = 0.0
    # d′: var/yok farkı
    for p in players:
        w = [gd[m] for m in gd if m in p["_in"]]
        wo = [gd[m] for m in gd if m not in p["_in"]]
        if len(w) >= 2 and len(wo) >= 2:
            diff = sum(w) / len(w) - sum(wo) / len(wo)
            p["d"] = round(max(0.0, min(1.0, diff / 2)) * min(1.0, len(wo) / 5), 3)
        else:
            p["d"] = None
        p["season_matches"] = len(played_matches)
        p.pop("_in")
    return players


class SeasonFill:
    def __init__(self, pool, max_calls: int = 900):
        self.pool, self.store, self.s = pool, pool.store, pool.s
        self.max_calls = max_calls
        self.log: list[str] = []

    def pending(self) -> tuple[list[dict], set[str], set[str]]:
        lo = to_iso(season_start())
        ms = [m for m in self.store.select("matches", [("status", "eq", "bitti"), ("kickoff_at", "gte", lo)])
              if m["league"] in self.s.leagues and (m.get("ext_ids") or {}).get("bsd")]
        try:
            have_pm = {r["match_id"] for r in self.store.select("player_matches", [("kickoff_at", "gte", lo)])}
        except Exception:
            have_pm = None  # tablo yok (şema güncellenmedi)
        have_st = set()
        ids = [m["id"] for m in ms]
        for i in range(0, len(ids), 200):
            have_st |= {r["match_id"] for r in self.store.select("match_stats", [("match_id", "in", ids[i:i + 200])])}
        # önce önümüzdeki 36 saatte oynayacak takımların maçları (yarının bülteni), sonra en yeni maç önce
        from datetime import timedelta

        from .timeutil import now_utc, to_iso

        soon = self.store.select("matches", [("kickoff_at", "gte", to_iso(now_utc())),
                                             ("kickoff_at", "lt", to_iso(now_utc() + timedelta(hours=36)))])
        hot = {t for x in soon for t in (x.get("home_team_id"), x.get("away_team_id"))}
        return sorted(ms, key=lambda m: (m.get("home_team_id") in hot or m.get("away_team_id") in hot, m["kickoff_at"]),
                      reverse=True), have_pm, have_st

    def run(self) -> dict:
        from .sources.bsd import parse_lineups, parse_stats

        bsd = self.pool.bsd
        if not bsd.available:
            return {"log": ["⚠️ sezon: BSD_API_KEY yok"], "player_matches": 0, "stats": 0}
        ms, have_pm, have_st = self.pending()
        start_calls = bsd.calls
        n_pm = n_st = n_lu = 0
        pm_ok = have_pm is not None
        for m in ms:
            if bsd.calls - start_calls >= self.max_calls:
                break
            eid = int(m["ext_ids"]["bsd"])
            try:
                if m["id"] not in have_st:
                    st = parse_stats(bsd._get(f"/events/{eid}/stats/"))
                    if st:
                        self.store.upsert("match_stats", [
                            {"match_id": m["id"], "side": side, "team_id": m[f"{side}_team_id"], **st[side],
                             "source": "bsd", "updated_at": to_iso(now_utc())} for side in st if side in ("home", "away")])
                        n_st += 1
                if pm_ok and m["id"] not in have_pm:
                    lraw = bsd._get(f"/events/{eid}/lineups/")
                    sraw = bsd._get(f"/events/{eid}/player-stats/")
                    rows = parse_player_stats(lraw, sraw, m)
                    if rows:
                        self.store.upsert("player_matches", rows)
                        n_pm += 1
                    lu = parse_lineups(lraw)
                    if lu.get("status") == "resmi" and lu.get("lineups"):
                        self.store.upsert("lineups", [
                            {"match_id": m["id"], "side": side, "formation": v.get("formation"),
                             "start_xi": v["start_xi"], "subs": v["subs"], "source": "bsd",
                             "lineup_status": "resmi", "updated_at": to_iso(now_utc())}
                            for side, v in lu["lineups"].items()])
                        n_lu += 1
            except Exception as e:
                self.log.append(f"⚠️ sezon: {m['id']}: {e}")
                if "tavan" in str(e) or "yetki" in str(e):
                    break
        left_pm = 0 if not pm_ok else sum(1 for m in ms if m["id"] not in have_pm) - n_pm
        left_st = sum(1 for m in ms if m["id"] not in have_st) - n_st
        self.log.append(f"Sezon verisi (2026/27): {len(ms)} biten maç; {n_pm} maçın oyuncu dakikaları, {n_lu} resmî ilk 11, "
                        f"{n_st} maç istatistiği eklendi; {bsd.calls - start_calls} BSD isteği. Kalan: oyuncu {left_pm}, "
                        f"istatistik {left_st} maç" + ("" if pm_ok else " (player_matches tablosu yok — SQL bloğunu çalıştırın)"))
        try:
            self.store.set_source_status("bsd:sezon", True, self.log[-1])
        except Exception:
            pass
        return {"log": self.log, "player_matches": n_pm, "stats": n_st}
