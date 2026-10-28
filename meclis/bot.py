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
        "calibration": dict(pick.get("calibration") or {}, model_version=MODEL_VERSION) if pick.get("calibration") else None,
    }



RESMI_BASLANGIC = parse_dt("2026-10-26T21:00:00+00:00")  # 27.10.2026 00:00 TSİ

class Bot:
    def __init__(self, store, settings, pool: DataPool | None = None):
        self.store = store
        self.s = settings
        self.pool = pool or DataPool(store, settings)
        self.log: list[str] = []
        self.contexts: dict[str, LeagueContext] = {}

    def is_cup(self, league: str) -> bool:
        """Kupa mı? config (CL/EL/ECL) + BSD'den keşfedilen ligler tablosundaki kupa bayrağı (FA Cup, DFB Pokal…)."""
        from .config import LEAGUES

        if league in LEAGUES:
            return bool(LEAGUES[league].cup)
        if "_cup_codes" not in self.__dict__:
            try:
                self._cup_codes = {r["code"] for r in self.store.select("leagues", [("cup", "eq", True)])}
            except Exception:
                self._cup_codes = set()
        return league in self._cup_codes

    def context(self, league: str) -> LeagueContext:
        if league not in self.contexts:
            ms, stats = self.pool.history(league)
            from .config import LEAGUES

            if self.is_cup(league):
                ms, stats = self._with_domestic(league, ms, stats)
            sp = self._league_strength_prior(league, ms) if self.is_cup(league) else None
            try:
                priors = self.pool.elo_priors(league) if league != "DEMO" else {}
            except Exception:
                priors = {}
            if self.is_cup(league):
                priors = {**self._cup_elo_priors(league, ms), **priors}
            self.contexts[league] = LeagueContext.build(league, ms, stats, elo_priors=priors, strength_prior=sp)
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
            if m["league"] == league or self.is_cup(m["league"]):
                continue
            hs, as_ = m["home_team_id"].split(":", 1)[-1], m["away_team_id"].split(":", 1)[-1]
            if hs in slugs or as_ in slugs:
                extra.append(dict(m, dom_league=m["league"], home_team_id=f"{league}:{hs}" if hs in slugs else m["home_team_id"],
                                  away_team_id=f"{league}:{as_}" if as_ in slugs else m["away_team_id"]))
        ids = [m["id"] for m in extra]
        stats = dict(stats)
        for i in range(0, len(ids), 200):
            for r in self.store.select("match_stats", [("match_id", "in", ids[i:i + 200])]):
                stats.setdefault(r["match_id"], {})[r["side"]] = r
        if extra:
            self.log.append(f"ℹ️ {league}: modele takımların bu sezonki {len(extra)} lig maçı eklendi")
        return sorted(ms + extra, key=lambda m: m["kickoff_at"]), stats

    def league_strength(self) -> dict[str, dict]:
        """Lig gücü (BU SEZON): ligin kulüplerinin bu sezonki Avrupa maçlarındaki (ön eleme dahil) maç başı averajı,
        örneklem azsa sıfıra büzülür. Log-gol ölçeğinde: s = 0.35 × averaj × n/(n+20). Harici katsayı kullanılmaz."""
        if "_lstr" in self.__dict__:
            return self._lstr
        from .analysis import season_start
        from .config import LEAGUES

        if "_all_season" not in self.__dict__:
            self._all_season = self.store.select("matches", [("status", "eq", "bitti"),
                                                             ("kickoff_at", "gte", to_iso(season_start()))])
        dom = {}
        for m in self._all_season:
            if not self.is_cup(m["league"]):
                for t in (m["home_team_id"], m["away_team_id"]):
                    dom[t.split(":", 1)[-1]] = m["league"]
        # Ligler arası güç = Avrupa maçlarında lig-lig averaj regresyonu (rakibin ligi hesaba katılır):
        #   averaj ≈ g[ev ligi] − g[dep ligi] + saha avantajı;  ridge (λ=6) ile sıfıra büzülür.
        # Eski ölçü (ham Avrupa averajı) ön elemede zayıf rakip ezen ligleri şişiriyordu (Azerbaycan > 0).
        import numpy as np

        rows, n_by = [], {}
        for m in self._all_season:
            if m["league"] not in ("CL", "EL", "ECL") or m.get("home_goals") is None:
                continue
            lh, la = dom.get(m["home_team_id"].split(":", 1)[-1]), dom.get(m["away_team_id"].split(":", 1)[-1])
            if not lh or not la or lh == la:
                continue
            rows.append((lh, la, m["home_goals"] - m["away_goals"]))
            for lg in (lh, la):
                n_by[lg] = n_by.get(lg, 0) + 1
        leagues = sorted(n_by)
        self._lstr = {}
        if rows:
            ix = {lg: i for i, lg in enumerate(leagues)}
            X = np.zeros((len(rows), len(leagues) + 1))
            y = np.zeros(len(rows))
            for r, (lh, la, gd) in enumerate(rows):
                X[r, ix[lh]], X[r, ix[la]], X[r, -1], y[r] = 1.0, -1.0, 1.0, gd
            R = np.eye(len(leagues) + 1) * 6.0
            R[-1, -1] = 0.0
            beta = np.linalg.solve(X.T @ X + R, X.T @ y)
            for lg, i in ix.items():
                self._lstr[lg] = {"mac": n_by[lg], "averaj_mac": round(float(beta[i]), 3),
                                  "s": round(0.35 * float(beta[i]), 4), "yontem": "lig-lig regresyon"}
        return self._lstr

    def _league_strength_prior(self, league: str, ms: list[dict]) -> dict[str, float]:
        """Kupa bağlamında yalnızca yerel lig maçlarında görünen rakiplere kendi liglerinin gücü önsel olarak verilir;
        böylece zayıf ligde rakip ezmek, güçlü ligde ezmekle aynı sayılmaz."""
        ls = self.league_strength()
        out = {}
        for m in ms:
            if not m.get("dom_league"):
                continue
            s = ls.get(m["dom_league"], {}).get("s", 0.0)
            for t in (m["home_team_id"], m["away_team_id"]):
                if not t.startswith(f"{league}:"):
                    out[t] = s
        return out

    ELO_PER_STRENGTH = 650.0  # log-güç 1.0 ≈ 650 Elo (Δ/400 → gol regresyonu eğimi ≈ 1.2, iki yön)

    def _cup_elo_priors(self, league: str, ms: list[dict]) -> dict[str, float]:
        """Kupada Elo, ligler arası karşılaştırılabilir olsun diye takımın yerel liginin gücüyle başlatılır
        (Elo 1500 + 650·s; s = ligin bu sezonki Avrupa sonuçlarından ölçülen log-gücü). Aksi halde Azerbaycan
        şampiyonu ile Bundesliga takımı aynı 1500'den başlar ve kupada 'eşit' görünür."""
        ls = self.league_strength()
        dom: dict[str, str] = {}
        for m in ms:
            dl = m.get("dom_league")
            if not dl:
                continue
            for t in (m["home_team_id"], m["away_team_id"]):
                dom.setdefault(t, dl)
        return {t: 1500.0 + self.ELO_PER_STRENGTH * ls.get(dl, {}).get("s", 0.0) for t, dl in dom.items()}

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
        from .xi import assign_grid, xi_uncertainty

        for side in ("home", "away"):  # diziliş + ızgara (frontend oyuncuları dizilişe göre yerleştirir)
            sx = xi.get(side) if isinstance(xi, dict) else None
            if not sx or not sx.get("players"):
                continue
            lu = next((x for x in lineups if x.get("side") == side and x.get("formation")), None)
            sx["formation"], sx["players"] = assign_grid(sx["players"], (lu or {}).get("formation"))
            sx["formation_source"] = ((lu or {}).get("source") or "lineups") if lu else "mevki sayısından türetildi"
            sx["uncertainty"] = xi_uncertainty(sx)
        a = analyze_match(match, ctx, self.s, injuries, known, players, weather, xi=xi)
        if isinstance(a, dict):
            try:
                a["dosya"] = self._dossier(match, ctx, lineups)
            except Exception as e:
                self.log.append(f"⚠️ maç dosyası ({match['home_name']}): {e}")
        if isinstance(a, dict) and isinstance(xi, dict):
            a["xi_uncertainty"] = max((xi.get(s_) or {}).get("uncertainty", 0.5) if xi.get(s_) else 0.5
                                      for s_ in ("home", "away"))
        from .config import LEAGUES

        if self.is_cup(match["league"]) and match["league"] in LEAGUES and isinstance(a, dict):
            a["avrupa_baglam"] = self._europe_context(match, ctx)
        return a

    def _dossier(self, match: dict, ctx, lineups: list[dict]) -> dict:
        """Senaryo ve maç sayfası için maçın kendi sayıları: iç/dış saha ortalamaları (bu sezon), dinlenme günü,
        hakemin bu sezonki kart/faul ortalaması, teknik direktör."""
        from .timeutil import parse_dt as _pd

        out = {"venue_split": {}, "rest": {}, "referee": {}, "coach": {}}
        ko = _pd(match["kickoff_at"])
        for side in ("home", "away"):
            tid = match[f"{side}_team_id"]
            slug = tid.split(":", 1)[-1]
            ms = [m for m in ctx.matches if m.get("home_goals") is not None and
                  (m["home_team_id"] if side == "home" else m["away_team_id"]).split(":", 1)[-1] == slug]
            if ms:
                gf = [m["home_goals"] if side == "home" else m["away_goals"] for m in ms]
                ga = [m["away_goals"] if side == "home" else m["home_goals"] for m in ms]
                cf = [((ctx.stats.get(m["id"]) or {}).get(side) or {}).get("corners") for m in ms]
                cf = [c for c in cf if c is not None]
                out["venue_split"][side] = {"n": len(ms), "gf": round(sum(gf) / len(ms), 2), "ga": round(sum(ga) / len(ms), 2),
                                            "cf": round(sum(cf) / len(cf), 2) if cf else None}
            prev = [m for m in ctx.matches if slug in (m["home_team_id"].split(":", 1)[-1], m["away_team_id"].split(":", 1)[-1])
                    and _pd(m["kickoff_at"]) < ko and m.get("home_goals") is not None]
            if prev:
                out["rest"][side] = round((ko - _pd(max(prev, key=lambda m: m["kickoff_at"])["kickoff_at"])).total_seconds() / 86400, 1)
            lu = next((x for x in lineups if x.get("side") == side and x.get("coach")), None)
            if lu:
                out["coach"][side] = lu["coach"]
        ref = match.get("referee")
        if ref:
            rm = [m for m in ctx.matches if m.get("referee") == ref and m.get("home_goals") is not None]
            cards = []
            for m in rm:
                st = ctx.stats.get(m["id"]) or {}
                c = [((st.get(sd) or {}).get("yellow") or 0) + ((st.get(sd) or {}).get("red") or 0)
                     for sd in ("home", "away") if (st.get(sd) or {}).get("yellow") is not None]
                if len(c) == 2:
                    cards.append(sum(c))
            out["referee"] = {"ad": ref, "n": len(cards), "kart": round(sum(cards) / len(cards), 2) if cards else None}
        return out

    def _europe_context(self, match: dict, ctx) -> dict:
        """Avrupa izi: her takımın bu sezonki Avrupa maçları (ön eleme dahil) ve lig maçları ayrı ayrı + lig gücü."""
        ls = self.league_strength()
        out = {"lig_gucu": ls, "harmanlama": "Avrupa maçları ağırlık 1.0, lig maçları 0.6; lig rakiplerine lig gücü önseli"}
        for side in ("home", "away"):
            tid = match[f"{side}_team_id"]
            eu, dom = [], []
            for m in ctx.matches:
                if m.get("home_goals") is None or tid not in (m["home_team_id"], m["away_team_id"]):
                    continue
                home = m["home_team_id"] == tid
                r = {"tarih": m["kickoff_at"][:10], "rakip": m["away_name"] if home else m["home_name"],
                     "saha": "İç" if home else "Dış", "lehte": m["home_goals"] if home else m["away_goals"],
                     "aleyhte": m["away_goals"] if home else m["home_goals"]}
                (dom if m.get("dom_league") else eu).append(dict(r, lig=m.get("dom_league")) if m.get("dom_league") else r)
            dl = next((r["lig"] for r in dom), None)
            out[side] = {"yerel_lig": dl, "lig_gucu": ls.get(dl) if dl else None,
                         "avrupa": {"mac": len(eu), "atti": sum(r["lehte"] for r in eu), "yedi": sum(r["aleyhte"] for r in eu),
                                    "maclar": eu[-8:]},
                         "lig": {"mac": len(dom), "atti": sum(r["lehte"] for r in dom), "yedi": sum(r["aleyhte"] for r in dom)}}
        return out

    def lead(self) -> timedelta:
        return timedelta(hours=self.s.publish_lead_hours)

    def publishable(self, m: dict, now) -> bool:
        """Yayın penceresi: başlamaya ≥ lead saat var VE (TR saatiyle bugün ya da 12 saatten yakın)."""
        ko = parse_dt(m["kickoff_at"])
        if ko < RESMI_BASLANGIC:  # resmî kayıt 27 Ekim 2026 00:00 TSİ'de başladı; öncesi deneme dönemi
            return False
        if ko - now < self.lead():
            return False
        return tr_date(m["kickoff_at"]) <= tr_date(to_iso(now)) or ko - now <= timedelta(hours=self.s.publish_window_hours)

    def candidates(self, now) -> list[dict]:
        """Başlamamış TÜM maçlar (ufuk boyunca). Yayın kararı ayrıca publishable() ile verilir."""
        lo = now
        hi = now + timedelta(hours=self.s.horizon_hours)
        # BÜTÜN ligler (BSD'nin keşfettikleri dahil): bültendeki hiçbir maç atlanmaz. 'Y' ligleri yalnızca
        # Avrupa takımlarının yerel lig geçmişi içindir (fikstürü bültene girmez).
        ms = self.pool.matches_between(to_iso(lo), to_iso(hi), None)
        return [m for m in ms if m.get("status") in ("planlandi", None) and not m["league"].startswith("Y")]

    def run(self, record: bool = True, now=None, fetch_extras: bool = True, publish: bool = True) -> dict:
        """record=False: kuru. publish=False: yalnızca analiz + bot bülteni (arşive tahmin/kupon yazılmaz).

        İki katman:
          * TAHMİN BOTU (bot_picks): botun ham çıktısı — bültendeki her maçın en değerli seçimi, her çalışmada
            yeniden hesaplanır; maç arşive alındığında kilitlenir.
          * TAHMİN ARŞİVİ (predictions/coupons): bot seçimlerinden EN GÜVENDİKLERİMİZLE kurulan içerik —
            önce Günün Kararı (2-3 maç, 2.30–4.00), sonra Meclis Görüşü tekliler (Günün Kararı'ndaki maçlar o gün
            tekli olarak yayımlanmaz), 5+ Meclis Görüşü varsa Karar Birliği. Her içerik satırı bot_pick_id taşır."""
        now = now or now_utc()
        try:  # motorun öğrendiği topluluk ağırlığı (Dixon-Coles ↔ Elo) analizden ÖNCE uygulanır
            from .motor import latest as _motor0

            _ew = (_motor0(self.store) or {}).get("elo_w")
            if _ew is not None:
                self.s.elo_weight = float(_ew)
        except Exception:
            pass
        matches = self.candidates(now)
        self.log.append(f"Bülten: {len(matches)} maç ({len(self.s.leagues)} lig; {self.s.horizon_hours:.0f} saat; "
                        f"yayın: başlamadan ≥ {self.s.publish_lead_hours:g} saat önce)")
        ids = {m["id"] for m in matches}
        locked = {r["match_id"] for r in self.store.select(
            "predictions", [("status", "eq", "bekliyor")]) if r["match_id"] in ids and r.get("tag") != "karar_birligi"}
        pre = self._analyze_all([m for m in matches if m["id"] not in locked], now, fetch_extras)
        from .analysis import annotate_scan, slate_bias

        good = [a for a in pre.values() if isinstance(a, dict)]
        mby = {m["id"]: m for m in matches}
        bias = slate_bias(good)
        from .config import LEAGUES

        try:  # pazar başına kalibrasyon ağırlığı ve değer kuralının geri test ROI'si (model_backtest)
            # w = max(w*, CAL_W_FLOOR): geri testte model kapanış oranını yenemiyor (w*≈0); modele asgari söz hakkı
            # bırakılır, büyük ayrışmalar zaten MAX_MODEL_GAP ile elenir.
            from .analysis import CAL_W_FLOOR

            cal_params = {r["market"]: {"w": max(CAL_W_FLOOR, float(r["w_opt"])), "w_opt": float(r["w_opt"]),
                                        "roi": r.get("roi_value"), "n": r.get("n")}
                          for r in self.store.select("model_backtest", [("segment", "eq", "tum")])
                          if r.get("w_opt") is not None and (r.get("n") or 0) >= 100}
        except Exception:
            cal_params = {}
        deep = None
        try:  # öğrenen motor (gece işi, korumalı): pazar grubu başına w + izotonik kalibrasyon ve yayına açık pazarlar
            from .motor import latest as _motor

            mot = _motor(self.store) or {}
            for g, prm in (mot.get("params") or {}).items():
                if prm and prm.get("w") is not None:
                    cal_params[g] = dict(cal_params.get(g) or {}, w=float(prm["w"]), iso=prm.get("iso") or None,
                                         kaynak="motor")
            if mot.get("derin_pazarlar"):
                deep = list(mot["derin_pazarlar"])
            self._motor = mot
        except Exception as e:
            self.log.append(f"⚠️ motor parametreleri okunamadı: {e}")
        for a in good:  # en iyi seçim bülten geneli kalibrasyonla yeniden seçilir
            if deep is not None:
                a["derin_pazarlar"] = deep
            a["bias"] = bias
            if self.is_cup(a.get("league") or ""):
                a["cal_w_factor"] = 0.5  # kupa: ligler arası güç farkı belirsiz → piyasaya daha yakın
            a["cal_params"] = cal_params
            lgp = ((getattr(self, "_motor", None) or {}).get("params_lig") or {}).get(a.get("league") or "")
            if lgp:  # lig başına kalibrasyon (motor; yalnızca ligde yeterli örnek ve doğrulamada küreselden iyiyse)
                a["cal_params"] = {**cal_params, **{g: dict(v, kaynak="motor-lig") for g, v in lgp.items() if v}}
            a["best_pick"] = annotate_scan(a, self.s)
            try:  # film senaryoları (benzetim + maçın kendi sayıları); seçim bilindikten sonra kurulur
                from .senaryo import build_film

                a["senaryolar"] = build_film(a, mby.get(a.get("match_id")) or {}, a.get("dosya"))
            except Exception as e:
                self.log.append(f"⚠️ senaryo ({a.get('home')}): {e}")
        if bias:
            self.log.append("ℹ️ kalibrasyon (model − piyasa, bülten ortalaması): " + ", ".join(
                f"{k} {v:+.3f}" for k, v in sorted(bias.items()) if abs(v) >= 0.01)[:400])
        analyses, bot_rows, nopick = [], [], 0
        for m in matches:
            if m["id"] in locked:  # arşive alınmış maç kilitli: yeniden hesaplanmaz (analizi aynadan)
                from .ayna import frozen_analysis

                a = frozen_analysis(self.store, m["id"])
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
                "calibration": bp.get("calibration"),
                "completeness": a["quality"]["score"], "status": "aday", "computed_at": to_iso(now),
                "model_version": MODEL_VERSION}

    def _publish(self, analyses: list[tuple[dict, dict]], now) -> tuple[int, list[str]]:
        """Arşiv katmanı: yayın penceresindeki maçların bot seçimlerinden içerik kurar."""
        by_day: dict = {}
        seen_slots: set = set()  # aynı saatte aynı takım = aynı maçın ikinci kaydı (ad eşleşmesi kopyası) → bir kez
        for m, a in analyses:
            ko = m["kickoff_at"][:16]
            slots = {(ko, v) for v in (m.get("home_team_id"), m.get("away_team_id"),
                                       (m.get("home_name") or "").casefold(), (m.get("away_name") or "").casefold()) if v}
            if slots & seen_slots:
                continue
            seen_slots |= slots
            bp = a.get("best_pick")
            if bp and bp.get("kind") in ("değer", "isabet") and bp.get("odds") and self.publishable(m, now):
                by_day.setdefault(tr_date(m["kickoff_at"]), []).append((m, a, bp))
        recorded, created = 0, []
        isabet = getattr(self.s, "pick_mode", "isabet") == "isabet"
        for day, items in sorted(by_day.items()):
            dstr = day.isoformat()
            lo, hi = (to_iso(x) for x in _tr_day_bounds(day))
            day_preds = self.store.select("predictions", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
            used = {p["match_id"] for p in day_preds}  # bir maç günde en fazla bir üründe (GK / KB / Görüş)
            singles_n = len({p["match_id"] for p in day_preds if p["tag"] == "meclis_gorusu"})
            mmap = {m["id"]: m for m, _, _ in items}
            gate = coupon_gate(day)  # kuponlar: bütün TR günü pencereye girdiğinde (önceki gün 18:00 TSİ)
            gate_open = now >= gate
            # 1) Günün Kararı — en güvenilen 2-3 maç, toplam oran 2.30–4.00
            if gate_open and not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "gunun_karari")], limit=1):
                cands = [dict(bp, match_id=m["id"]) for m, a, bp in items if m["id"] not in used]
                c = build_daily_coupon(cands, self.s.coupon_min_odds, self.s.coupon_max_odds,
                                       -1.0 if isabet else self.s.coupon_min_ev, rank="confidence")
                if c:
                    created += self._insert_coupon("gunun_karari", dstr, c, mmap, "piyasa")
                    used |= {l["match_id"] for l in c["legs"]}
                else:
                    self.log.append(f"Günün Kararı ({dstr}): {self.s.coupon_min_odds:.2f}-{self.s.coupon_max_odds:.2f} "
                                    "bandında kombinasyon kurulamadı — kupon yok.")
            # 2) Karar Birliği — GK'den sonra kalan havuzdan, model ile piyasanın birlikte en güçlü gördüğü 2-3 maç
            if gate_open and not self.store.select("coupons", [("coupon_date", "eq", dstr), ("tag", "eq", "karar_birligi")], limit=1):
                pool = [dict(bp, match_id=m["id"]) for m, a, bp in items
                        if m["id"] not in used and bp.get("probability", 0) >= self.s.single_min_prob
                        and _agrees(bp)]
                c = build_consensus(pool, min_singles=2)
                if c:
                    created += self._insert_coupon("karar_birligi", dstr, c, mmap, c["odds_source"])
                    used |= {l["match_id"] for l in c["legs"]}
            # 3) Meclis Görüşü — tekliler. Kapı açılmadan yalnızca kapıdan önce kilitlenecek maçlar (havuz bölünmesin)
            for m, a, bp in sorted(items, key=lambda x: -(x[2].get("confidence") or 0)):
                if m["id"] in used:
                    continue
                if not gate_open and parse_dt(m["kickoff_at"]) - self.lead() > gate:
                    continue
                if isabet:
                    if bp.get("probability", 0) < self.s.single_min_prob or singles_n >= self.s.singles_max_per_day:
                        continue  # Ortak'ta kalır, Defter'e alınmaz
                elif (bp.get("confidence") or 0) < self.s.single_min_trust:
                    continue
                lab = pick_label(bp["market"], bp["selection"], bp.get("line"), m["home_name"], m["away_name"])
                why = (f"{lab}: olasılık %{bp['probability'] * 100:.1f} (kalibre: model + marjsız piyasa), oran {bp['odds']:.2f}, değer "
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
                singles_n += 1
                used.add(m["id"])
                self.log.append(f"📝 Meclis Görüşü: {m['home_name']} – {m['away_name']} → {lab}")
            # yayımlanan maçların bot satırlarını kilitle
            tags = {p["match_id"]: p["tag"] for p in self.store.select("predictions", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])}
            for mid in used & set(mmap):
                try:
                    self.store.update("bot_picks", {"status": tags.get(mid, "meclis_gorusu"), "locked_at": to_iso(now)}, [("id", "eq", mid)])
                except Exception:
                    pass
                self.store.upsert("analysis_queue", [{"match_id": mid, "status": "tamamlandi", "note": "yayımlandı",
                                                      "last_attempt_at": to_iso(now)}])
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

        # SQLite deposu iş parçacığı güvenli (RLock); yalnızca bellek içi test deposu sıralı çalışır
        workers = 1 if getattr(self.store, "path", None) == ":memory:" else 6
        if workers == 1:
            return dict(one(m) for m in matches)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            out = dict(ex.map(one, matches))
        retry = [m for m in matches if isinstance(out.get(m["id"]), Exception)]
        for m in retry:  # geçici bağlantı hatası: aynı çalışmada sıralı ikinci deneme
            out[m["id"]] = one(m)[1]
        return out

    def update_trends(self) -> int:
        from .lab import compute_trends

        rows = []
        for lg in self.s.leagues:
            try:
                rows += compute_trends(self.context(lg))
            except Exception as e:
                self.log.append(f"⚠️ trend ({lg}): {e}")
        rows = list({r["id"]: r for r in rows}.values())  # aynı kimlik iki kez gelirse upsert düşmesin
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


def coupon_gate(day):
    """Gün D'nin kuponları en erken D-1 18:00 TSİ'de kurulur (bütün gün 30 saatlik pencerede)."""
    from datetime import datetime

    return datetime(day.year, day.month, day.day, tzinfo=TR) - timedelta(hours=6)


def _agrees(bp: dict) -> bool:
    """Karar Birliği: model ile marjsız piyasa aynı yönde (fark ≤ 6 puan); piyasa yoksa model tek başına yetmez."""
    cal = bp.get("calibration") or {}
    pm, pk = bp.get("probability_model") or cal.get("p_model"), cal.get("p_piyasa")
    if pm is None or pk is None:
        return bool(bp.get("odds"))
    return abs(float(pm) - float(pk)) <= 0.06


def _tr_day_bounds(day):
    from datetime import datetime

    start = datetime(day.year, day.month, day.day, tzinfo=TR)
    return start, start + timedelta(days=1)
