"""Model geri testi (BACKTEST — kilitli canlı kayıttan AYRIDIR).

Bu sezon biten maçlarda yürüyen pencere: her lig için her hafta, o haftadan ÖNCEKİ maçlarla Dixon-Coles kurulur,
haftanın maçları tahmin edilir ve football-data.co.uk kapanış oranlarının (marjsız) olasılığıyla karşılaştırılır.
Pazarlar: 1X2 (3 yollu) ve 2.5 gol alt/üst (kapanış oranı olan pazarlar).
Ölçüler: Brier, log-loss (model / piyasa / harman), log-loss'u en aza indiren harman ağırlığı w* (p = w·model +
(1−w)·piyasa), değer kuralının (kalibre edilmiş p ile edge ≥ %3, oran 1.50–5.00) kapanış oranında ROI'si,
10 kutulu kalibrasyon tablosu. w* canlı seçimde pazar başına kalibrasyon ağırlığı olarak kullanılır.
Not: geri test saf Dixon-Coles'tur (Elo harmanı ve eksik etkisi yok) → canlı modelin yaklaşık bir ölçüsüdür.
"""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

from . import MODEL_VERSION
from .analysis import season_start
from .model.goals import fit_dixon_coles, score_matrix
from .timeutil import now_utc, parse_dt, to_iso

EDGE_MIN, OMIN, OMAX = 0.03, 1.50, 5.00


def _novig(d: dict, keys) -> list[float] | None:
    try:
        inv = [1 / float(d[k]) for k in keys]
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    s = sum(inv)
    return [x / s for x in inv] if s > 0 else None


def _odds(m: dict, key: str, which: str = "closing") -> dict | None:
    o = m.get("odds") or {}
    if which == "open":  # karar anı oranı (football-data.co.uk ön maç / bizim çektiğimiz oran)
        return o.get(key)
    return o.get(f"{key}_closing") or o.get(key)


def collect(store, leagues: list[str] | None = None, min_train: int = 40, which: str = "closing",
            ridge: float = 10.0) -> list[dict]:
    """Her tahmin satırı: {market, league, p_model[], p_market[], odds[], outcome_idx}."""
    s0 = season_start()
    ms = store.select("matches", [("status", "eq", "bitti"), ("kickoff_at", "gte", to_iso(s0))], order="kickoff_at")
    by_lg: dict[str, list] = {}
    for m in ms:
        if m.get("home_goals") is None or (leagues and m["league"] not in leagues):
            continue
        by_lg.setdefault(m["league"], []).append(m)
    out = []
    for lg, lst in by_lg.items():
        if len(lst) < min_train + 10 or not any(_odds(m, "1X2") for m in lst):
            continue
        lst.sort(key=lambda m: m["kickoff_at"])
        t0 = parse_dt(lst[min_train]["kickoff_at"])
        end = parse_dt(lst[-1]["kickoff_at"]) + timedelta(days=1)
        cut = t0
        while cut < end:
            nxt = cut + timedelta(days=7)
            train = [m for m in lst if parse_dt(m["kickoff_at"]) < cut]
            test = [m for m in lst if cut <= parse_dt(m["kickoff_at"]) < nxt]
            cut = nxt
            if len(train) < min_train or not test:
                continue
            rows = [{"home": m["home_team_id"], "away": m["away_team_id"], "hg": m["home_goals"], "ag": m["away_goals"],
                     "days_ago": (cut - parse_dt(m["kickoff_at"])).total_seconds() / 86400} for m in train]
            try:
                gm = fit_dixon_coles(rows, ridge=ridge)
            except Exception:
                continue
            for m in test:
                h, a = m["home_team_id"], m["away_team_id"]
                if not (gm.has_team(h, 3) and gm.has_team(a, 3)):
                    continue
                lh, la = gm.lambdas(h, a)
                sm = score_matrix(lh, la, gm.rho)
                g = np.arange(sm.shape[0])
                d = g[:, None] - g[None, :]
                tot = g[:, None] + g[None, :]
                p1x2 = [float(sm[d > 0].sum()), float(sm[d == 0].sum()), float(sm[d < 0].sum())]
                pou = [float(sm[tot > 2.5].sum()), float(sm[tot < 2.5].sum())]
                hg, ag = m["home_goals"], m["away_goals"]
                o = _odds(m, "1X2", which)
                if o:
                    pm = _novig(o, ("1", "X", "2"))
                    if pm:
                        out.append({"market": "1X2", "league": lg, "pm": p1x2, "pk": pm,
                                    "odds": [float(o[k]) for k in ("1", "X", "2")],
                                    "y": 0 if hg > ag else (1 if hg == ag else 2)})
                o = _odds(m, "OU_GOALS_2.5", which)
                if o:
                    ks = next((k for k in (("ÜST", "ALT"), ("over", "under"), ("Üst", "Alt")) if k[0] in o), None)
                    pm = _novig(o, ks) if ks else None
                    if pm:
                        out.append({"market": "OU_GOALS_2.5", "league": lg, "pm": pou, "pk": pm,
                                    "odds": [float(o[k]) for k in ks], "y": 0 if hg + ag > 2.5 else 1})
    return out


def _ll(p: list[float], y: int) -> float:
    return -math.log(max(1e-6, p[y]))


def _brier(p: list[float], y: int) -> float:
    return sum((pi - (1.0 if i == y else 0.0)) ** 2 for i, pi in enumerate(p))


def summarize(rows: list[dict]) -> list[dict]:
    res = []
    for mk in sorted({r["market"] for r in rows}):
        rs = [r for r in rows if r["market"] == mk]
        n = len(rs)
        if n < 30:
            continue

        def blend(r, w):
            return [w * a + (1 - w) * b for a, b in zip(r["pm"], r["pk"])]

        grid = [i / 20 for i in range(21)]
        lls = {w: sum(_ll(blend(r, w), r["y"]) for r in rs) / n for w in grid}
        w_opt = min(lls, key=lls.get)
        # canlı değer kuralı (p = w·model + (1−w)·piyasa, w = max(0.20, w*); ayrışma > 20 puan elenir), bu oranlarda
        w_live = max(0.20, w_opt)
        stake = profit = hits = 0
        for r in rs:
            p = blend(r, w_live)
            for i, (pi, o) in enumerate(zip(p, r["odds"])):
                if OMIN <= o <= OMAX and 0.03 <= pi * o - 1 <= 0.25 and abs(r["pm"][i] - r["pk"][i]) <= 0.20:
                    stake += 1
                    if i == r["y"]:
                        hits += 1
                        profit += o - 1
                    else:
                        profit -= 1
        bins = []
        for b in range(10):  # model olasılığı kalibrasyonu (seçim başına)
            lo, hi = b / 10, (b + 1) / 10
            xs = [(r["pm"][i], 1.0 if i == r["y"] else 0.0) for r in rs for i in range(len(r["pm"]))
                  if lo <= r["pm"][i] < hi]
            if xs:
                bins.append({"kutu": f"{lo:.1f}-{hi:.1f}", "n": len(xs), "model_ort": round(sum(x for x, _ in xs) / len(xs), 3),
                             "gercek": round(sum(y for _, y in xs) / len(xs), 3)})
        res.append({"market": mk, "segment": "tum", "n": n,
                    "brier_model": round(sum(_brier(r["pm"], r["y"]) for r in rs) / n, 4),
                    "brier_market": round(sum(_brier(r["pk"], r["y"]) for r in rs) / n, 4),
                    "brier_blend": round(sum(_brier(blend(r, w_opt), r["y"]) for r in rs) / n, 4),
                    "ll_model": round(lls[1.0], 4), "ll_market": round(lls[0.0], 4), "ll_blend": round(lls[w_opt], 4),
                    "w_opt": w_opt, "n_value": stake, "hit_value": round(hits / stake, 4) if stake else None,
                    "roi_value": round(profit / stake, 4) if stake else None, "calib": bins,
                    "computed_at": to_iso(now_utc()), "label": "backtest", "model_version": MODEL_VERSION,
                    "leagues": sorted({r["league"] for r in rs})})
    return res


def run_backtest(store, leagues=None) -> dict:
    rows = collect(store, leagues)
    res = summarize(rows)
    if res:
        store.upsert("model_backtest", res)
    return {"rows": len(rows), "markets": res}


def calibration_weights(store) -> dict[str, float]:
    """Canlı seçim için pazar başına harman ağırlığı (geri testten); yoksa boş."""
    try:
        return {r["market"]: float(r["w_opt"]) for r in store.select("model_backtest", [("segment", "eq", "tum")])
                if r.get("w_opt") is not None}
    except Exception:
        return {}
