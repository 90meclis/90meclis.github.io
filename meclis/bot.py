"""Tahmin Botu.

Akış: bülteni tara → maçları süz (lig, zaman penceresi) → her maç için tüm pazarları analiz et →
senaryoları kur → maçtan ÖNCE deftere yaz. Veri eksikse maç elenmez: analiz kuyruğunda 'ertelendi'
olarak bekler ve bir sonraki çalışmada yeniden denenir. Başlama saati gelip hâlâ eksikse 'yetismedi'
olarak kayıtta kalır (sessizce kaybolmaz).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from . import MODEL_VERSION
from .analysis import LeagueContext, analyze_match
from .coupons import build_consensus, build_daily_coupon
from .markets import pick_label
from .pool import DataPool
from .store import StoreError
from .timeutil import TR, now_utc, parse_dt, to_iso, tr_date


def _retry_at(now, kickoff, attempts: int):
    gap = kickoff - now
    if gap <= timedelta(hours=3):
        step = timedelta(minutes=30)
    else:
        step = timedelta(hours=min(6, 2 + attempts))
    return min(now + step, kickoff - timedelta(minutes=15))


def _prediction_row(match: dict, pick: dict, tag: str, rationale: str, coupon_id: str | None = None,
                    scenario_note: str | None = None, completeness: float | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()), "match_id": match["id"], "kickoff_at": match["kickoff_at"],
        "league": match["league"], "home_name": match["home_name"], "away_name": match["away_name"],
        "tag": tag, "coupon_id": coupon_id, "market": pick["market"], "selection": pick["selection"],
        "line": pick.get("line"), "probability": round(float(pick["probability"]), 4),
        "odds": pick.get("odds"), "odds_source": pick.get("odds_source"),
        "fair_odds": pick.get("fair_odds"), "edge": pick.get("edge"),
        "confidence": pick.get("confidence"), "stake": 1, "rationale": rationale[:2000],
        "scenario_note": (scenario_note or "")[:2000] or None, "completeness": completeness,
        "model_version": MODEL_VERSION, "status": "bekliyor",
    }


class Bot:
    def __init__(self, store, settings, pool: DataPool | None = None):
        self.store = store
        self.s = settings
        self.pool = pool or DataPool(store, settings)
        self.log: list[str] = []
        self.contexts: dict[str, LeagueContext] = {}

    def context(self, league: str) -> LeagueContext:
        if league not in self.contexts:
            ms, stats = self.pool.history(league)
            self.contexts[league] = LeagueContext.build(league, ms, stats)
        return self.contexts[league]

    def analyze(self, match: dict, fetch_extras: bool = True) -> dict:
        ctx = self.context(match["league"])
        injuries, known, weather, players, lineups = [], False, None, {}, []
        if fetch_extras:
            try:
                lineups = self.pool.lineups(match)
            except Exception:
                lineups = []
            ko = parse_dt(match["kickoff_at"])
            if ko - now_utc() <= timedelta(hours=30):
                injuries, known = self.pool.injuries(match)
            for side in ("home", "away"):
                players[match[f"{side}_team_id"]] = self.store.select("players", [("team_id", "eq", match[f"{side}_team_id"])])
            try:
                weather = self.pool.weather(match)
            except Exception as e:
                self.log.append(f"⚠️ hava durumu alınamadı ({match['home_name']}): {e}")
        else:
            injuries = self.store.select("injuries", [("match_id", "eq", match["id"])])
            known = bool(self.store.get("source_status", source=f"injuries:{match['id']}"))
            w = self.store.get("weather", match_id=match["id"])
            weather = w["data"] if w else None
            lineups = self.store.select("lineups", [("match_id", "eq", match["id"])])
        return analyze_match(match, ctx, self.s, injuries, known, players, weather, lineups_known=bool(lineups))

    def candidates(self, now) -> list[dict]:
        lo = now + timedelta(minutes=self.s.min_minutes_before_kickoff)
        hi = now + timedelta(hours=self.s.horizon_hours)
        ms = self.pool.matches_between(to_iso(lo), to_iso(hi), self.s.leagues)
        ids = {m["id"] for m in ms}
        for q in self.store.select("analysis_queue", [("status", "in", ["bekliyor", "ertelendi"])]):
            if q["match_id"] not in ids:
                m = self.store.get("matches", id=q["match_id"])
                if m and parse_dt(m["kickoff_at"]) > lo:
                    ms.append(m)
                    ids.add(m["id"])
        return [m for m in ms if m.get("status") in ("planlandi", None)]

    def run(self, record: bool = True, now=None, fetch_extras: bool = True) -> dict:
        now = now or now_utc()
        if record:  # kuru çalıştırma hiçbir şey yazmaz (salt okunur bağlantıda da güvenli)
            self._expire_queue(now)
        matches = self.candidates(now)
        self.log.append(f"Bülten: {len(matches)} maç ({', '.join(self.s.leagues)}; {self.s.horizon_hours:.0f} saat)")
        analyses, recorded, postponed = [], 0, 0
        for m in matches:
            q = self.store.get("analysis_queue", match_id=m["id"]) or {"match_id": m["id"], "attempts": 0}
            if q.get("status") == "tamamlandi":
                if self.store.select("predictions", [("match_id", "eq", m["id"]), ("tag", "eq", "meclis_gorusu")], limit=1) \
                        or q.get("note") == "pas":
                    a = self._latest_analysis(m["id"])
                    if a:
                        analyses.append((m, a))
                    continue
            if record and q.get("status") == "ertelendi" and q.get("next_retry_at") and parse_dt(q["next_retry_at"]) > now:
                postponed += 1
                continue
            try:
                a = self.analyze(m, fetch_extras)
            except Exception as e:  # analiz hatası maçı ELEMEZ
                a = {"ready": False, "missing": [f"analiz hatası: {e}"], "match_id": m["id"]}
            attempts = int(q.get("attempts") or 0) + 1
            if not a.get("ready"):
                postponed += 1
                if not record:
                    continue
                self.store.upsert("analysis_queue", [{
                    "match_id": m["id"], "status": "ertelendi", "missing": a.get("missing", []),
                    "attempts": attempts, "last_attempt_at": to_iso(now),
                    "next_retry_at": to_iso(_retry_at(now, parse_dt(m["kickoff_at"]), attempts)),
                    "note": "Karar Bekliyor — veri eksik, tahmin ertelendi"}])
                if a.get("narrative"):
                    self._save_analysis(m["id"], a, now)
                continue
            if record:
                self._save_analysis(m["id"], a, now)
                self.store.update("matches", {"completeness": a["quality"]["score"]}, [("id", "eq", m["id"])])
            analyses.append((m, a))
            bp = a.get("best_pick")
            note = "pas"
            if bp and record:
                lab = pick_label(bp["market"], bp["selection"], bp.get("line"), m["home_name"], m["away_name"])
                why = (f"{lab}: olasılık %{bp['probability'] * 100:.1f}; λ {a['lambdas']['home']:.2f}-{a['lambdas']['away']:.2f}; "
                       f"tür: {bp['kind']}; tamlık {a['quality']['score']:.0f}/100")
                try:
                    sc = "; ".join(f"{x['ad']} (%{100 * x['olasılık']:.0f})" if x.get("olasılık") else x["ad"]
                                   for x in a.get("scenarios", [])[:4])
                    self.store.insert("predictions", [_prediction_row(m, bp, "meclis_gorusu", why, scenario_note=sc,
                                                                      completeness=a["quality"]["score"])])
                    recorded += 1
                    note = "kaydedildi"
                    self.log.append(f"📝 Meclis Görüşü: {m['home_name']} – {m['away_name']} → {lab}")
                except StoreError as e:
                    note = "kayıt reddedildi"
                    self.log.append(f"⚠️ kayıt reddedildi ({m['home_name']} – {m['away_name']}): {e}")
            elif bp:
                self.log.append(f"🧪 (kuru) {m['home_name']} – {m['away_name']} → "
                                f"{pick_label(bp['market'], bp['selection'], bp.get('line'), m['home_name'], m['away_name'])}")
            if record:
                self.store.upsert("analysis_queue", [{
                    "match_id": m["id"], "status": "tamamlandi", "missing": [],
                    "attempts": attempts, "last_attempt_at": to_iso(now), "next_retry_at": None, "note": note}])
        coupons = self._coupons(analyses, now) if record else []
        if record:
            self.update_trends()
        self.log.append(f"Analiz: {len(analyses)} hazır, {postponed} ertelendi, {recorded} yeni tahmin, "
                        f"{len(coupons)} yeni kupon")
        return {"analyzed": len(analyses), "postponed": postponed, "recorded": recorded, "coupons": coupons,
                "log": list(self.pool.log) + self.log}

    def update_trends(self) -> int:
        from .lab import compute_trends

        rows = []
        for lg in self.s.leagues:
            rows += compute_trends(self.context(lg))
        self.store.upsert("trends", rows)
        return len(rows)

    def _latest_analysis(self, match_id: str) -> dict | None:
        rows = self.store.select("analyses", [("match_id", "eq", match_id)], order="created_at", desc=True, limit=1)
        return rows[0]["payload"] if rows else None

    def _save_analysis(self, match_id: str, a: dict, now) -> None:
        self.store.upsert("analyses", [{"match_id": match_id, "created_at": to_iso(now),
                                        "model_version": MODEL_VERSION, "payload": a}])

    def _expire_queue(self, now) -> None:
        """Başlama saatine 15 dk (BOT_MIN_MINUTES_BEFORE_KICKOFF) kala hâlâ eksikse: Karar Verilmedi."""
        cutoff = now + timedelta(minutes=self.s.min_minutes_before_kickoff)
        for q in self.store.select("analysis_queue", [("status", "in", ["bekliyor", "ertelendi"])]):
            m = self.store.get("matches", id=q["match_id"])
            if m and parse_dt(m["kickoff_at"]) <= cutoff:
                self.store.update("analysis_queue", {
                    "status": "yetismedi",
                    "note": "Karar Verilmedi: veri yetersiz (eksik: " + ", ".join(q.get("missing") or ["?"]) + ")"},
                    [("match_id", "eq", q["match_id"])])

    def _coupons(self, analyses: list[tuple[dict, dict]], now) -> list[str]:
        created = []
        min_ko = now + timedelta(minutes=self.s.min_minutes_before_kickoff)
        by_day: dict = {}
        for m, a in analyses:
            if parse_dt(m["kickoff_at"]) > min_ko and a.get("ready"):
                by_day.setdefault(tr_date(m["kickoff_at"]), []).append((m, a))
        for day, items in sorted(by_day.items()):
            dstr = day.isoformat()
            mmap = {m["id"]: m for m, _ in items}
            if not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "gunun_karari")], limit=1):
                cands = []
                for m, a in items:
                    for mk in a["markets"]:
                        if mk.get("odds") and mk["probability"] >= 0.45 and mk["market"] != "CS":
                            cands.append(dict(mk, match_id=m["id"]))
                c = build_daily_coupon(cands, self.s.coupon_min_odds, self.s.coupon_max_odds, self.s.coupon_min_ev)
                if c:
                    created += self._insert_coupon("gunun_karari", dstr, c, mmap, "piyasa")
                else:
                    self.log.append(f"Günün Kararı ({dstr}): {self.s.coupon_min_odds:.2f}-{self.s.coupon_max_odds:.2f} "
                                    "bandında değerli kombinasyon kurulamadı — kupon yok.")
            if not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "karar_birligi")], limit=1):
                lo, hi = (to_iso(x) for x in _tr_day_bounds(day))
                singles = self.store.select("predictions", [("tag", "eq", "meclis_gorusu"), ("kickoff_at", "gte", lo),
                                                            ("kickoff_at", "lt", hi)])
                future = [s for s in singles if parse_dt(s["kickoff_at"]) > min_ko]
                if len(singles) >= self.s.consensus_min_singles:
                    c = build_consensus(future, min_singles=2)
                    if c:
                        for leg in c["legs"]:
                            mmap.setdefault(leg["match_id"], self.store.get("matches", id=leg["match_id"]))
                        created += self._insert_coupon("karar_birligi", dstr, c, mmap, c["odds_source"])
        return created

    def _insert_coupon(self, tag: str, dstr: str, c: dict, mmap: dict, odds_source: str) -> list[str]:
        cid = str(uuid.uuid4())
        first = min(parse_dt(mmap[l["match_id"]]["kickoff_at"]) for l in c["legs"])
        try:
            self.store.insert("coupons", [{
                "id": cid, "coupon_date": dstr, "tag": tag, "total_odds": c["total_odds"],
                "joint_probability": c["joint_probability"], "legs_count": len(c["legs"]), "stake": 1,
                "first_kickoff_at": to_iso(first), "odds_source": odds_source, "model_version": MODEL_VERSION,
                "note": f"EV {c.get('ev', 0):+.3f}" if "ev" in c else None, "status": "bekliyor"}])
            rows = []
            for leg in c["legs"]:
                m = mmap[leg["match_id"]]
                lab = pick_label(leg["market"], leg["selection"], leg.get("line"), m["home_name"], m["away_name"])
                rows.append(_prediction_row(m, leg, tag, f"{lab} (kupon {dstr})", coupon_id=cid))
            self.store.insert("predictions", rows)
        except StoreError as e:
            self.log.append(f"⚠️ {tag} kuponu kaydedilemedi: {e}")
            return []
        self.log.append(f"🎫 {tag} {dstr}: {len(c['legs'])} maç, toplam oran {c['total_odds']:.2f}")
        return [cid]


def _tr_day_bounds(day):
    from datetime import datetime

    start = datetime(day.year, day.month, day.day, tzinfo=TR)
    return start, start + timedelta(days=1)
