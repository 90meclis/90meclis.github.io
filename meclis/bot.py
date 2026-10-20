"""Tahmin Botu.

Akış: bülteni tara → her maç için tüm pazarları analiz et (eksik veri analizi durdurmaz; tamlık yalnızca güven
göstergesi) → senaryoları kur → değer kuralını geçen seçimi maçtan SAATLER önce deftere yaz.

Yayın zamanı: maç, yayın penceresine girdiğinde (Türkiye saatiyle aynı gün ya da 12 saatten yakın) ve başlamasına
en az BOT_PUBLISH_LEAD_HOURS (varsayılan 3) saat varken yayımlanır — sabah çalışması günün bütün maçlarına
karar verir, gün içinde eklenen maç sonraki çalışmada. Yayımlanmamış adaylar (değer çıkmadı / pencere dışında)
her çalışmada (gece dahil) güncel veriyle yeniden hesaplanır; yayımlanan seçim kilitlidir.
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
            from .config import LEAGUES

            if league in LEAGUES and LEAGUES[league].cup:
                ms, stats = self._with_domestic(league, ms, stats)
            try:
                priors = self.pool.elo_priors(league) if league != "DEMO" else {}
            except Exception:
                priors = {}
            self.contexts[league] = LeagueContext.build(league, ms, stats, elo_priors=priors)
        return self.contexts[league]

    def _with_domestic(self, league: str, ms: list[dict], stats: dict) -> tuple[list[dict], dict]:
        """Avrupa kupası: takımın kupada bu sezon 2-3 maçı vardır; model takımın BU SEZONKİ lig maçlarını da görür
        (kimlikler 'lig:slug' → kupa kimliğine eşlenir). Ligler arası güç farkını Meclis Elo ve piyasa kalibrasyonu
        dengeler."""
        from .analysis import season_start

        up = self.store.select("matches", [("league", "eq", league), ("kickoff_at", "gte", to_iso(season_start()))])
        slugs = {t.split(":", 1)[1] for m in up + ms for t in (m["home_team_id"], m["away_team_id"])}
        if "_all_season" not in self.__dict__:
            self._all_season = self.store.select("matches", [("status", "eq", "bitti"),
                                                             ("kickoff_at", "gte", to_iso(season_start()))])
        from .config import LEAGUES

        extra = []
        for m in self._all_season:
            if m["league"] == league or (m["league"] in LEAGUES and LEAGUES[m["league"]].cup):
                continue
            hs, as_ = m["home_team_id"].split(":", 1)[-1], m["away_team_id"].split(":", 1)[-1]
            if hs in slugs or as_ in slugs:
                extra.append(dict(m, home_team_id=f"{league}:{hs}" if hs in slugs else m["home_team_id"],
                                  away_team_id=f"{league}:{as_}" if as_ in slugs else m["away_team_id"]))
        ids = [m["id"] for m in extra]
        stats = dict(stats)
        for i in range(0, len(ids), 200):
            for r in self.store.select("match_stats", [("match_id", "in", ids[i:i + 200])]):
                stats.setdefault(r["match_id"], {})[r["side"]] = r
        if extra:
            self.log.append(f"ℹ️ {league}: modele takımların bu sezonki {len(extra)} lig maçı eklendi")
        return sorted(ms + extra, key=lambda m: m["kickoff_at"]), stats

    def analyze(self, match: dict, fetch_extras: bool = True) -> dict:
        ctx = self.context(match["league"])
        injuries, known, weather, players, lineups = [], False, None, {}, []
        if fetch_extras:
            try:
                lineups = self.pool.lineups(match)
            except Exception:
                lineups = []
            ko = parse_dt(match["kickoff_at"])
            injuries, known = self.pool.injuries(match)  # BSD listesi 7 gün önceden gelir
            for side in ("home", "away"):
                players[match[f"{side}_team_id"]] = self.pool.squad_players(match[f"{side}_team_id"])
            try:
                weather = self.pool.weather(match)
            except Exception as e:
                self.log.append(f"⚠️ hava durumu alınamadı ({match['home_name']}): {e}")
        else:
            from .teamnews import fresh_injuries, team_current_players

            injuries = fresh_injuries(self.store, match["id"])
            for side in ("home", "away"):
                players[match[f"{side}_team_id"]] = team_current_players(self.store, match[f"{side}_team_id"])
            known = bool(self.store.get("source_status", source=f"injuries:{match['id']}"))
            w = self.store.get("weather", match_id=match["id"])
            weather = w["data"] if w else None
            lineups = self.store.select("lineups", [("match_id", "eq", match["id"])])
        from .teamnews import build_xi

        try:
            xi = build_xi(self.store, match, injuries, players)
        except Exception as e:  # tahmini 11 kurulamazsa sakat listesiyle devam
            self.log.append(f"⚠️ tahmini ilk 11 kurulamadı ({match['home_name']}): {e}")
            xi = {}
        return analyze_match(match, ctx, self.s, injuries, known, players, weather, xi=xi)

    def lead(self) -> timedelta:
        return timedelta(hours=self.s.publish_lead_hours)

    def publishable(self, m: dict, now) -> bool:
        """Yayın penceresi: başlamaya ≥ lead saat var VE (TR saatiyle bugün ya da 12 saatten yakın)."""
        ko = parse_dt(m["kickoff_at"])
        if ko - now < self.lead():
            return False
        return tr_date(m["kickoff_at"]) <= tr_date(to_iso(now)) or ko - now <= timedelta(hours=self.s.publish_window_hours)

    def candidates(self, now) -> list[dict]:
        """Başlamamış TÜM maçlar (ufuk boyunca). Yayın kararı ayrıca publishable() ile verilir."""
        lo = now
        hi = now + timedelta(hours=self.s.horizon_hours)
        ms = self.pool.matches_between(to_iso(lo), to_iso(hi), self.s.leagues)
        return [m for m in ms if m.get("status") in ("planlandi", None)]

    def run(self, record: bool = True, now=None, fetch_extras: bool = True, publish: bool = True) -> dict:
        """record=False: kuru. publish=False: yalnızca analiz + bot bülteni (arşive tahmin/kupon yazılmaz).

        İki katman:
          * TAHMİN BOTU (bot_picks): botun ham çıktısı — bültendeki her maçın en değerli seçimi, her çalışmada
            yeniden hesaplanır; maç arşive alındığında kilitlenir.
          * TAHMİN ARŞİVİ (predictions/coupons): bot seçimlerinden EN GÜVENDİKLERİMİZLE kurulan içerik —
            önce Günün Kararı (2-3 maç, 2.30–4.00), sonra Meclis Görüşü tekliler (Günün Kararı'ndaki maçlar o gün
            tekli olarak yayımlanmaz), 5+ Meclis Görüşü varsa Karar Birliği. Her içerik satırı bot_pick_id taşır."""
        now = now or now_utc()
        matches = self.candidates(now)
        self.log.append(f"Bülten: {len(matches)} maç ({len(self.s.leagues)} lig; {self.s.horizon_hours:.0f} saat; "
                        f"yayın: başlamadan ≥ {self.s.publish_lead_hours:g} saat önce)")
        ids = {m["id"] for m in matches}
        locked = {r["match_id"] for r in self.store.select(
            "predictions", [("status", "eq", "bekliyor")]) if r["match_id"] in ids and r.get("tag") != "karar_birligi"}
        pre = self._analyze_all([m for m in matches if m["id"] not in locked], now, fetch_extras)
        from .analysis import annotate_scan, slate_bias

        good = [a for a in pre.values() if isinstance(a, dict)]
        bias = slate_bias(good)
        from .config import LEAGUES

        for a in good:  # en iyi seçim bülten geneli kalibrasyonla yeniden seçilir
            a["bias"] = bias
            if a.get("league") in LEAGUES and LEAGUES[a["league"]].cup:
                a["cal_w"] = 0.5  # kupa: ligler arası güç farkı belirsiz → piyasaya daha yakın
            a["best_pick"] = annotate_scan(a, self.s)
        if bias:
            self.log.append("ℹ️ kalibrasyon (model − piyasa, bülten ortalaması): " + ", ".join(
                f"{k} {v:+.3f}" for k, v in sorted(bias.items()) if abs(v) >= 0.01)[:400])
        analyses, bot_rows, nopick = [], [], 0
        for m in matches:
            if m["id"] in locked:  # arşive alınmış maç kilitli: yeniden hesaplanmaz
                a = self._latest_analysis(m["id"])
                if a:
                    analyses.append((m, a))
                continue
            a = pre.get(m["id"])
            if isinstance(a, Exception) or a is None:  # analiz hatası maçı ELEMEZ; sonraki çalışmada yeniden
                self.log.append(f"⚠️ analiz hatası ({m['home_name']} – {m['away_name']}): {a}")
                continue
            q = self.store.get("analysis_queue", match_id=m["id"]) or {"match_id": m["id"], "attempts": 0}
            attempts = int(q.get("attempts") or 0) + 1
            if record:
                self._save_analysis(m["id"], a, now)
                self.store.update("matches", {"completeness": a["quality"]["score"]}, [("id", "eq", m["id"])])
            analyses.append((m, a))
            bp = a.get("best_pick")
            if bp:
                bot_rows.append(self._bot_pick_row(m, a, bp, now))
                if not record:
                    self.log.append(f"🧪 (kuru) {m['home_name']} – {m['away_name']} → "
                                    f"{pick_label(bp['market'], bp['selection'], bp.get('line'), m['home_name'], m['away_name'])}"
                                    f" [{bp['kind']}]")
            else:
                nopick += 1
            if record:
                note = (("değerli seçim — " if bp.get("kind") == "değer" else "adil oran seçimi (piyasa oranı yok) — ")
                        + "yayın penceresi / arşiv seçimi bekleniyor") if bp else \
                    "değer kuralını geçen seçim yok — güncel veriyle yeniden hesaplanacak"
                self.store.upsert("analysis_queue", [{
                    "match_id": m["id"], "status": "bekliyor", "missing": a.get("missing", []),
                    "attempts": attempts, "last_attempt_at": to_iso(now), "next_retry_at": None, "note": note}])
        if record and bot_rows:
            try:
                self.store.upsert("bot_picks", bot_rows)
            except Exception as e:
                self.log.append(f"⚠️ bot bülteni yazılamadı (bot_picks tablosu yok mu?): {e}")
        recorded, coupons = 0, []
        if record and publish:
            recorded, coupons = self._publish(analyses, now)
        if record:
            self.update_trends()
        nval = sum(1 for r in bot_rows if r["kind"] == "değer")
        self.log.append(f"Analiz: {len(analyses)} maç; Tahmin Botu: {len(bot_rows)} seçim ({nval} değer, "
                        f"{len(bot_rows) - nval} adil oran), {nopick} maçta seçim yok; Arşiv: {recorded} yeni Meclis "
                        f"Görüşü, {len(coupons)} yeni kupon")
        return {"analyzed": len(analyses), "postponed": 0, "recorded": recorded, "coupons": coupons,
                "bot_picks": len(bot_rows), "log": list(self.pool.log) + self.log}

    def _bot_pick_row(self, m: dict, a: dict, bp: dict, now) -> dict:
        return {"id": m["id"], "match_id": m["id"], "kickoff_at": m["kickoff_at"], "league": m["league"],
                "home_name": m["home_name"], "away_name": m["away_name"], "market": bp["market"],
                "selection": bp["selection"], "line": bp.get("line"), "probability": bp["probability"],
                "odds": bp.get("odds"), "fair_odds": bp.get("fair_odds"), "edge": bp.get("edge"),
                "confidence": bp.get("confidence"), "kind": bp.get("kind"), "basis": a.get("basis"),
                "completeness": a["quality"]["score"], "status": "aday", "computed_at": to_iso(now),
                "model_version": MODEL_VERSION}

    def _publish(self, analyses: list[tuple[dict, dict]], now) -> tuple[int, list[str]]:
        """Arşiv katmanı: yayın penceresindeki maçların bot seçimlerinden içerik kurar."""
        by_day: dict = {}
        for m, a in analyses:
            bp = a.get("best_pick")
            if bp and bp.get("kind") == "değer" and bp.get("odds") and self.publishable(m, now):
                by_day.setdefault(tr_date(m["kickoff_at"]), []).append((m, a, bp))
        recorded, created = 0, []
        for day, items in sorted(by_day.items()):
            dstr = day.isoformat()
            lo, hi = (to_iso(x) for x in _tr_day_bounds(day))
            day_preds = self.store.select("predictions", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
            singles_ids = {p["match_id"] for p in day_preds if p["tag"] == "meclis_gorusu"}
            gk_ids = {p["match_id"] for p in day_preds if p["tag"] == "gunun_karari"}
            mmap = {m["id"]: m for m, _, _ in items}
            # 1) Günün Kararı — ana kupon: en değerli/güvenilen 2-3 maç, toplam oran 2.30–4.00
            if not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "gunun_karari")], limit=1):
                cands = [dict(bp, match_id=m["id"]) for m, a, bp in items
                         if m["id"] not in singles_ids and m["id"] not in gk_ids]
                c = build_daily_coupon(cands, self.s.coupon_min_odds, self.s.coupon_max_odds, self.s.coupon_min_ev,
                                       rank="confidence")
                if c:
                    created += self._insert_coupon("gunun_karari", dstr, c, mmap, "piyasa")
                    gk_ids |= {l["match_id"] for l in c["legs"]}
                else:
                    self.log.append(f"Günün Kararı ({dstr}): {self.s.coupon_min_odds:.2f}-{self.s.coupon_max_odds:.2f} "
                                    "bandında değerli kombinasyon kurulamadı — kupon yok.")
            # 2) Meclis Görüşü — tekliler; Günün Kararı'ndaki maç o gün tekli olarak yayımlanmaz
            for m, a, bp in sorted(items, key=lambda x: -(x[2].get("confidence") or 0)):
                if m["id"] in gk_ids or m["id"] in singles_ids:
                    continue
                if (bp.get("confidence") or 0) < self.s.single_min_trust:
                    continue  # bot bülteninde kalır, arşive alınmaz
                lab = pick_label(bp["market"], bp["selection"], bp.get("line"), m["home_name"], m["away_name"])
                why = (f"{lab}: olasılık %{bp['probability'] * 100:.1f} (kalibre), oran {bp['odds']:.2f}, değer "
                       f"{bp['edge'] * 100:+.1f}%; λ {a['lambdas']['home']:.2f}-{a['lambdas']['away']:.2f}; "
                       f"dayanak: {a.get('basis')}; veri derinliği {a['quality']['score']:.0f}/100")
                sc = "; ".join(f"{x['ad']} (%{100 * x['olasılık']:.0f})" if x.get("olasılık") else x["ad"]
                               for x in a.get("scenarios", [])[:4])
                row = _prediction_row(m, bp, "meclis_gorusu", why, scenario_note=sc, completeness=a["quality"]["score"])
                row["bot_pick_id"] = m["id"]
                try:
                    self.store.insert("predictions", [row])
                except StoreError as e:
                    self.log.append(f"⚠️ kayıt reddedildi ({m['home_name']} – {m['away_name']}): {e}")
                    continue
                recorded += 1
                singles_ids.add(m["id"])
                self.log.append(f"📝 Meclis Görüşü: {m['home_name']} – {m['away_name']} → {lab}")
            # bot bülteni satırlarını kilitle (arşive giren maç artık yeniden hesaplanmaz)
            for mid, st in [(x, "gunun_karari") for x in gk_ids] + [(x, "meclis_gorusu") for x in singles_ids]:
                try:
                    self.store.update("bot_picks", {"status": st, "locked_at": to_iso(now)}, [("id", "eq", mid)])
                except Exception:
                    pass
                self.store.upsert("analysis_queue", [{"match_id": mid, "status": "tamamlandi", "note": "yayımlandı",
                                                      "last_attempt_at": to_iso(now)}])
            # 3) Karar Birliği — 5+ Meclis Görüşü varsa en güvenilen 2-3'ten kombinasyon (değişmedi)
            if not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "karar_birligi")], limit=1):
                singles = self.store.select("predictions", [("tag", "eq", "meclis_gorusu"), ("kickoff_at", "gte", lo),
                                                            ("kickoff_at", "lt", hi)])
                future = [x for x in singles if parse_dt(x["kickoff_at"]) > now + self.lead()]
                if len(singles) >= self.s.consensus_min_singles:
                    c = build_consensus(future, min_singles=2)
                    if c:
                        for leg in c["legs"]:
                            mmap.setdefault(leg["match_id"], self.store.get("matches", id=leg["match_id"]))
                        created += self._insert_coupon("karar_birligi", dstr, c, mmap, c["odds_source"])
        return recorded, created

    def _analyze_all(self, matches: list[dict], now, fetch_extras: bool) -> dict:
        """Analizleri paralel hesaplar (G/Ç ağırlıklı). Canlı kaynak çağrıları yalnızca yayına yakın maçlar için;
        uzaktaki maçlar 'kadro' işinin havuza yazdığı eksik/ilk 11/kadro verisiyle analiz edilir."""
        from concurrent.futures import ThreadPoolExecutor

        for lg in sorted({m["league"] for m in matches}):
            try:
                self.context(lg)
            except Exception as e:
                self.log.append(f"⚠️ lig bağlamı kurulamadı ({lg}): {e}")

        def one(m):
            try:
                near = parse_dt(m["kickoff_at"]) - now <= timedelta(hours=self.s.live_extras_hours)
                return m["id"], self.analyze(m, fetch_extras and near)
            except Exception as e:
                return m["id"], e

        workers = 1 if self.store.kind == "sqlite" else 6
        if workers == 1:
            return dict(one(m) for m in matches)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return dict(ex.map(one, matches))

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
        ts = to_iso(now)
        self.store.upsert("analyses", [{"match_id": match_id, "created_at": ts,
                                        "model_version": MODEL_VERSION, "payload": a}])
        try:  # yalnızca en güncel analiz tutulur (yayımlanan seçimin analizi zaten yeniden hesaplanmaz)
            self.store.prune("analyses", [("match_id", "eq", match_id), ("created_at", "lt", ts)])
        except Exception as e:
            self.log.append(f"⚠️ eski analizler budanamadı ({match_id}): {e}")

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
                row = _prediction_row(m, leg, tag, f"{lab} (kupon {dstr})", coupon_id=cid)
                if tag == "gunun_karari":
                    row["bot_pick_id"] = leg["match_id"]
                rows.append(row)
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
