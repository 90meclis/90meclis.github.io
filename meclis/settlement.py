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
    """Kapanış oranı (bütün pazarlar, Avrupa kupaları dahil): önce başlama saatinden önceki SON kendi oran
    görüntümüz (odds_snapshots; başlamaya ≤3 saat kala alınmışsa), yoksa football-data.co.uk kapanış ('C'
    sütunları), o da yoksa daha eski son görüntümüz. CLV = alınan oran / kapanış − 1. Döner: (oran, kaynak)."""
    mk, line, sel = pred["market"], pred.get("line"), pred["selection"]
    if mk == "AH" and line is not None:
        key = f"AH_{(float(line) if sel == '1' else -float(line)):g}"  # oran sözlüğü ev sahibi çizgisine göre
    else:
        key = odds_key(mk, line)
    if not key:
        return None, None
    snap = None
    if store is not None:
        try:
            snaps = store.select("odds_snapshots", [("match_id", "eq", match.get("id") or pred["match_id"]),
                                                    ("taken_at", "lte", pred["kickoff_at"])],
                                 order="taken_at", desc=True, limit=1)
        except Exception:
            snaps = []
        if snaps:
            v = ((snaps[0].get("odds") or {}).get(key) or {}).get(sel)
            if v:
                snap = (float(v), snaps[0]["taken_at"])
    if snap and (parse_dt(pred["kickoff_at"]) - parse_dt(snap[1])).total_seconds() <= 3 * 3600:
        return snap[0], f"kendi kapanış görüntümüz {snap[1][:16]}"
    v = ((match.get("odds") or {}).get(f"{key}_closing") or {}).get(sel)
    if v:
        return float(v), "football-data.co.uk kapanış"
    if snap:
        return snap[0], f"kendi son görüntümüz {snap[1][:16]}"
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
