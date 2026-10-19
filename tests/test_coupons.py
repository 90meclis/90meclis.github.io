from meclis.coupons import build_consensus, build_daily_coupon, settle_coupon


def c(mid, p, o, market="1X2", sel="1"):
    return {"match_id": mid, "probability": p, "odds": o, "market": market, "selection": sel, "line": None}


def test_daily_coupon_in_band_and_distinct_matches():
    cands = [c("a", .70, 1.55), c("b", .66, 1.62), c("c", .60, 1.80), c("d", .55, 1.95), c("a", .62, 1.70, "OU_GOALS", "ÜST")]
    res = build_daily_coupon(cands, 2.30, 4.00)
    assert res is not None
    assert 2.30 <= res["total_odds"] <= 4.00
    assert len({l["match_id"] for l in res["legs"]}) == len(res["legs"]) in (2, 3)
    assert res["ev"] >= 0


def test_daily_coupon_none_when_band_impossible():
    assert build_daily_coupon([c("a", .9, 1.10), c("b", .9, 1.12)], 2.30, 4.00) is None
    assert build_daily_coupon([c("a", .3, 5.0), c("b", .3, 6.0)], 2.30, 4.00) is None


def test_daily_coupon_rejects_negative_ev_and_unpriced():
    cands = [c("a", .50, 1.60), c("b", .50, 1.60)]  # 0.25 × 2.56 − 1 < 0
    assert build_daily_coupon(cands, 2.30, 4.00) is None
    unpriced = [{"match_id": "a", "probability": .8, "odds": None}, {"match_id": "b", "probability": .8, "odds": None}]
    assert build_daily_coupon(unpriced) is None


def test_daily_coupon_prefers_higher_joint_probability():
    cands = [c("a", .72, 1.60), c("b", .70, 1.62), c("c", .45, 2.40), c("d", .44, 2.45)]
    res = build_daily_coupon(cands, 2.30, 4.00)
    assert {l["match_id"] for l in res["legs"]} == {"a", "b"}


def test_consensus_requires_min_singles():
    singles = [dict(c(str(i), .6 + i / 100, 1.7), confidence=.6 + i / 100) for i in range(4)]
    assert build_consensus(singles, min_singles=5) is None
    singles.append(dict(c("x", .8, 1.4), confidence=.8))
    res = build_consensus(singles, min_singles=5)
    assert res and len(res["legs"]) in (2, 3) and res["legs"][0]["match_id"] == "x"
    assert res["odds_source"] == "piyasa"


def test_settle_coupon_rules():
    assert settle_coupon([("kazandi", 1.5), ("kazandi", 2.0)]) == ("kazandi", 3.0, 2.0)
    assert settle_coupon([("kazandi", 1.5), ("kaybetti", 2.0)])[0] == "kaybetti"
    assert settle_coupon([("kazandi", 1.5), ("iade", 2.0)]) == ("kazandi", 1.5, 0.5)
    assert settle_coupon([("iade", 1.5), ("iade", 2.0)])[0] == "iade"
    assert settle_coupon([("kazandi", 1.5), ("bekliyor", 2.0)])[0] is None
    assert settle_coupon([("kazandi", 1.5), ("kazandi", 2.0)], odds_source="model_adil")[2] is None
