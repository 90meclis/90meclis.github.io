"""Otomatik sonuçlandırma: maç sonuçları ve istatistiklerden tahmin ve kupon durumlarını günceller.
Sonuç verisi bulunamayan tahmin İADE EDİLMEZ; 'sonuç verisi bekleniyor' notuyla açık kalır."""
from __future__ import annotations

from datetime import timedelta

from .coupons import settle_coupon
from .markets import profit_for, settle_pick
from .timeutil import now_utc, parse_dt, to_iso

STAT_MARKETS = {"CORNERS_OU", "CARDS_OU", "SOT_OU", "GOAL_KICKS_OU"}


def result_dict(match: dict, stats: list[dict]) -> dict:
    r = {k: match.get(k) for k in ("status", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals")}
    by = {s["side"]: s for s in stats}
    for side in ("home", "away"):
        s = by.get(side) or {}
        r[f"{side}_corners"] = s.get("corners")
        r[f"{side}_shots_on_target"] = s.get("shots_on_target")
        r[f"{side}_goal_kicks"] = s.get("goal_kicks")
        y, red = s.get("yellow"), s.get("red")
        r[f"{side}_cards"] = None if y is None else y + (red or 0)
    return r


def odds_key(market: str, line) -> str | None:
    """Tahmin pazarı → matches.odds anahtarı (oranını tuttuğumuz bütün pazarlar)."""
    if market in ("1X2", "BTTS", "DC"):
        return market
    if market == "AH":
        return None  # AH anahtarı seçime bağlı (ev sahibi çizgisi); kapanış için closing_odds içinde çözülür
    if line is not None:
        return f"{market}_{float(line):g}"
    return None


def closing_odds(match: dict, pred: dict, store=None) -> tuple[float | None, str | None]:
    """Kapanış oranı: önce football-data.co.uk 'C' sütunları, yoksa başlamadan önceki SON kendi oran görüntümüz.
    CLV = alınan oran / kapanış − 1. Döner: (oran, kaynak)."""
    key = odds_key(pred["market"], pred.get("line"))
    if not key:
        return None, None
    odds = match.get("odds") or {}
    v = (odds.get(f"{key}_closing") or {}).get(pred["selection"])
    if v:
        return float(v), "football-data.co.uk kapanış"
    if store is not None:
        try:
            snaps = store.select("odds_snapshots", [("match_id", "eq", match.get("id") or pred["match_id"]),
                                                    ("taken_at", "lte", pred["kickoff_at"])],
                                 order="taken_at", desc=True, limit=1)
        except Exception:
            snaps = []
        if snaps:
            v = ((snaps[0].get("odds") or {}).get(key) or {}).get(pred["selection"])
            if v:
                return float(v), f"kendi görüntümüz {snaps[0]['taken_at'][:16]}"
    return None, None


def run_settlement(store, pool=None, now=None) -> dict:
    now = now or now_utc()
    log, n_settled = [], 0
    open_preds = store.select("predictions", [("status", "in", ["bekliyor", "basladi"])])
    match_cache: dict[str, dict] = {}
    tried_fill: set[str] = set()
    for p in open_preds:
        mid = p["match_id"]
        if mid not in match_cache:
            match_cache[mid] = store.get("matches", id=mid) or {}
        m = match_cache[mid]
        ko = parse_dt(p["kickoff_at"])
        if now < ko:
            continue
        status = m.get("status")
        if status in ("ertelendi", "iptal") and now < ko + timedelta(hours=48):
            if p["status"] == "bekliyor":
                store.update("predictions", {"status": "basladi", "settlement_note": f"maç {status}; 48 saat beklenir"},
                             [("id", "eq", p["id"])])
            continue
        if status == "bitti" or status in ("ertelendi", "iptal"):
            stats = store.select("match_stats", [("match_id", "eq", mid)])
            res = result_dict(m, stats)
            st, val = settle_pick(p["market"], p["selection"], p.get("line"), res)
            if st is None and p["market"] in STAT_MARKETS and pool is not None and mid not in tried_fill:
                tried_fill.add(mid)
                if pool.fill_match_stats(m):
                    res = result_dict(m, store.select("match_stats", [("match_id", "eq", mid)]))
                    st, val = settle_pick(p["market"], p["selection"], p.get("line"), res)
            if st:
                close, _src = closing_odds(m, p, store)
                clv = round(p["odds"] / close - 1, 4) if close and p.get("odds") else None
                store.update("predictions", {"status": st, "result_value": val,
                                             "profit": profit_for(st, p.get("odds"), p.get("stake") or 1),
                                             "closing_odds": close, "clv": clv,
                                             "settled_at": to_iso(now), "settlement_note": None},
                             [("id", "eq", p["id"])])
                n_settled += 1
                continue
            store.update("predictions", {"status": "basladi", "settlement_note": "sonuç verisi bekleniyor"},
                         [("id", "eq", p["id"])])
        elif p["status"] == "bekliyor":
            store.update("predictions", {"status": "basladi"}, [("id", "eq", p["id"])])
    log.append(f"{n_settled} tahmin sonuçlandı")

    n_c = 0
    for c in store.select("coupons", [("status", "in", ["bekliyor", "basladi"])]):
        legs = store.select("predictions", [("coupon_id", "eq", c["id"])])
        if not legs:
            continue
        st, eff, profit = settle_coupon([(l["status"], l.get("odds") or l.get("fair_odds")) for l in legs],
                                        c.get("stake") or 1, c.get("odds_source") or "piyasa")
        if st:
            store.update("coupons", {"status": st, "profit": profit, "settled_at": to_iso(now),
                                     "settlement_note": f"etkin oran {eff}" if eff else None}, [("id", "eq", c["id"])])
            n_c += 1
        elif c["status"] == "bekliyor" and now >= parse_dt(c["first_kickoff_at"]):
            store.update("coupons", {"status": "basladi"}, [("id", "eq", c["id"])])
    log.append(f"{n_c} kupon sonuçlandı")
    return {"settled": n_settled, "coupons": n_c, "log": log}
