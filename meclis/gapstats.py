"""Bitmiş maçların eksik istatistiğini anahtarlı ek kaynaklarla doldurur ('sezon' adımının sonunda).
Öncelik: önümüzdeki 36 saatte oynayacak takımların bu sezonki maçları, sonra en yeni maç. Var olan alan EZİLMEZ;
satırın kaynağı "birlesik" olur, alan bazında kaynak `sources_note` yerine source_status özetinde raporlanır."""
from __future__ import annotations

import os
from datetime import timedelta

from .sources.extra_stats import BB_LEAGUES, BigBalls, Highlightly
from .timeutil import now_utc, to_iso

NEED = ("shots", "shots_on_target", "corners", "yellow")


class GapStats:
    def __init__(self, pool):
        self.pool, self.store, s = pool, pool.store, pool.s
        keys = getattr(s, "keys", {}) or {}
        self.hl = Highlightly(keys.get("HIGHLIGHTLY_KEY") or os.environ.get("HIGHLIGHTLY_KEY"))
        self.bb = BigBalls(keys.get("BIGBALLS_KEY") or os.environ.get("BIGBALLS_KEY"))
        self.hl_budget = int(float(os.environ.get("HIGHLIGHTLY_DAILY_CALLS", "90")))
        self.bb_budget = int(float(os.environ.get("BIGBALLS_DAILY_CALLS", "200")))
        self.log: list[str] = []

    def _used(self, source: str) -> int:
        st = self.store.get("source_status", source=source) or {}
        return int(st.get("calls_today") or 0) if st.get("calls_date") == now_utc().date().isoformat() else 0

    def pending(self) -> list[dict]:
        from .analysis import season_start

        ms = self.store.select("matches", [("status", "eq", "bitti"), ("kickoff_at", "gte", to_iso(season_start()))])
        have: dict = {}
        ids = [m["id"] for m in ms]
        for i in range(0, len(ids), 200):
            for r in self.store.select("match_stats", [("match_id", "in", ids[i:i + 200])]):
                have.setdefault(r["match_id"], {})[r["side"]] = r
        soon = self.store.select("matches", [("kickoff_at", "gte", to_iso(now_utc())),
                                             ("kickoff_at", "lt", to_iso(now_utc() + timedelta(hours=36)))])
        hot = {t for x in soon for t in (x.get("home_team_id"), x.get("away_team_id"))}
        out = []
        for m in ms:
            h = have.get(m["id"]) or {}
            if all((h.get(side) or {}).get(f) is not None for side in ("home", "away") for f in NEED):
                continue
            m["_have"] = h
            out.append(m)
        out.sort(key=lambda m: (m.get("home_team_id") in hot or m.get("away_team_id") in hot, m["kickoff_at"]), reverse=True)
        return out

    def _write(self, m: dict, st: dict, src: str) -> bool:
        rows = []
        for side in ("home", "away"):
            new = st.get(side) or {}
            if not new:
                continue
            cur = dict(m["_have"].get(side) or {"match_id": m["id"], "side": side, "team_id": m[f"{side}_team_id"]})
            changed = False
            for f, v in new.items():
                if cur.get(f) is None and v is not None:
                    cur[f], changed = v, True
            if changed:
                cur["source"] = src if not m["_have"].get(side) else "birlesik"
                cur["updated_at"] = to_iso(now_utc())
                rows.append(cur)
        if rows:
            self.store.upsert("match_stats", rows)
        return bool(rows)

    def run(self) -> dict:
        if not (self.hl.available or self.bb.available):
            return {"log": ["ℹ️ ek istatistik: HIGHLIGHTLY_KEY / BIGBALLS_KEY yok — atlandı"], "filled": 0}
        hl_left = self.hl_budget - self._used("highlightly") if self.hl.available else 0
        bb_left = self.bb_budget - self._used("bigballs") if self.bb.available else 0
        todo = self.pending()
        n = {"highlightly": 0, "bigballs": 0, "eşleşmedi": 0}
        for m in todo:
            if hl_left - self.hl.calls < 2 and bb_left - self.bb.calls < 2:
                break
            day = m["kickoff_at"][:10]
            done = False
            try:
                if m["league"] in BB_LEAGUES and bb_left - self.bb.calls >= 2:
                    try:  # ücretsiz plan yalnızca bu sezonu kapsar (Temmuz ön eleme maçları "geçen sezon" sayılabilir)
                        mid = self.bb.find_match(day, m["home_name"], m["away_name"])
                        if mid:
                            done = self._write(m, self.bb.stats(mid), "bigballs")
                            n["bigballs"] += int(done)
                    except Exception as e:
                        self.bb._day.setdefault(day, [])
                        self.log.append(f"ℹ️ big balls ({day}): {e}")
                if not done and hl_left - self.hl.calls >= 2:
                    mid = self.hl.find_match(day, m["home_name"], m["away_name"])
                    if mid:
                        done = self._write(m, self.hl.stats(mid, m["home_name"], m["away_name"]), "highlightly")
                        n["highlightly"] += int(done)
                    else:
                        n["eşleşmedi"] += 1
            except Exception as e:
                self.log.append(f"⚠️ ek istatistik ({m['home_name']} – {m['away_name']}): {e}")
                break
        for src, cl in (("highlightly", self.hl), ("bigballs", self.bb)):
            if cl.calls:
                self.store.set_source_status(src, True, f"{n[src]} maçın eksik istatistiği dolduruldu ({cl.calls} istek)",
                                             add_calls=cl.calls)
        self.log.append(f"✅ ek istatistik: Highlightly {n['highlightly']}, Big Balls {n['bigballs']} maç; "
                        f"eşleşmeyen {n['eşleşmedi']}; bekleyen {max(0, len(todo) - n['highlightly'] - n['bigballs'])}")
        return {"log": self.log, "filled": n["highlightly"] + n["bigballs"]}
