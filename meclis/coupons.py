"""Kupon kurma: Günün Kararı (2-3 maç, toplam oran bandı) ve Karar Birliği."""
from __future__ import annotations

from itertools import combinations
from math import prod


def build_daily_coupon(candidates: list[dict], min_odds: float = 2.30, max_odds: float = 4.00,
                       min_ev: float = 0.0, leg_counts=(2, 3), max_pool: int = 16,
                       rank: str = "probability") -> dict | None:
    """Toplam oranı [min_odds, max_odds] bandında olan, ortak olasılığı en yüksek 2-3 maçlık kombinasyon.

    candidates: [{'match_id','probability','odds',...}] — yalnızca PİYASA oranlı seçimler kullanılır.
    Aynı maçtan iki seçim alınmaz. Beklenen değer (ortak olasılık × toplam oran − 1) en az `min_ev` olmalı.
    rank="confidence": bacaklar botun değer×kalite sırasına göre seçilir (Günün Kararı = en güvenilen maçlar).
    """
    pool = [c for c in candidates if c.get("odds") and c["odds"] > 1.0 and 0 < c["probability"] < 1]
    best_by_match: dict[str, list[dict]] = {}
    sk = (lambda c: -(c.get("confidence") or 0)) if rank == "confidence" else (lambda c: -c["probability"])
    for c in sorted(pool, key=sk):
        best_by_match.setdefault(c["match_id"], []).append(c)
    flat = sorted((c for lst in best_by_match.values() for c in lst[:4]), key=sk)[:max_pool]
    best, best_key = None, None
    for k in leg_counts:
        for combo in combinations(flat, k):
            if len({c["match_id"] for c in combo}) < k:
                continue
            total = prod(c["odds"] for c in combo)
            if not (min_odds <= total <= max_odds):
                continue
            joint = prod(c["probability"] for c in combo)
            ev = joint * total - 1
            if ev < min_ev:
                continue
            key = ((round(sum(c.get("confidence") or 0 for c in combo) / k, 6), round(ev, 6)) if rank == "confidence"
                   else (round(joint, 6), round(ev, 6)))
            if best_key is None or key > best_key:
                best, best_key = {"legs": list(combo), "total_odds": round(total, 3),
                                  "joint_probability": round(joint, 4), "ev": round(ev, 4)}, key
    return best


def build_consensus(singles: list[dict], min_singles: int = 5, min_third_prob: float = 0.60) -> dict | None:
    """Günde en az `min_singles` Meclis Görüşü varsa en güvenilen 2-3 seçimden kombinasyon."""
    if len(singles) < min_singles:
        return None
    ranked = sorted(singles, key=lambda s: -(s.get("confidence") or s["probability"]))
    seen, legs = set(), []
    for s in ranked:
        if s["match_id"] in seen:
            continue
        legs.append(s)
        seen.add(s["match_id"])
        if len(legs) == 3:
            break
    if len(legs) < 2:
        return None
    if len(legs) == 3 and legs[2]["probability"] < min_third_prob:
        legs = legs[:2]
    all_market = all(leg.get("odds") for leg in legs)
    total = prod((leg.get("odds") if all_market else leg.get("odds") or leg.get("fair_odds")) for leg in legs)
    return {"legs": legs, "total_odds": round(total, 3), "joint_probability": round(prod(l["probability"] for l in legs), 4),
            "odds_source": "piyasa" if all_market else "model_adil"}


def settle_coupon(leg_statuses: list[tuple[str, float | None]], stake: float = 1.0,
                  odds_source: str = "piyasa") -> tuple[str, float | None, float | None]:
    """leg_statuses: [(durum, oran)] → (kupon durumu, etkin oran, kâr). Sonuçlanmamış bacak varsa durum None."""
    sts = [s for s, _ in leg_statuses]
    if "kaybetti" in sts:
        return "kaybetti", None, (-stake if odds_source == "piyasa" else None)
    if any(s not in ("kazandi", "iade") for s in sts):
        return None, None, None
    live = [o for s, o in leg_statuses if s == "kazandi"]
    if not live:
        return "iade", 1.0, 0.0
    eff = prod(o for o in live if o)
    profit = round(stake * (eff - 1), 4) if odds_source == "piyasa" else None
    return "kazandi", round(eff, 3), profit
