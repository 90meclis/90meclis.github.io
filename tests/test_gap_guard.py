from types import SimpleNamespace

from meclis.analysis import rank_picks


def _payload(p_home, o_home, o_draw, o_away):
    return {"quality": {"factor": 1.0}, "basis": "model", "markets": [
        {"market": "1X2", "selection": "1", "line": None, "probability": p_home, "odds": o_home},
        {"market": "1X2", "selection": "X", "line": None, "probability": 0.25, "odds": o_draw},
        {"market": "1X2", "selection": "2", "line": None, "probability": 1 - p_home - 0.25, "odds": o_away}]}


def test_wild_gap_is_not_value():
    pl = _payload(0.53, 4.99, 4.2, 1.6)  # model %53, piyasa ~%19
    picks = rank_picks(pl, SimpleNamespace(value_edge_min=0.03), annotate=True)
    assert not [x for x in picks if x["selection"] == "1" and x.get("kind") == "değer"]
    assert "ayrışıyor" in pl["markets"][0]["neden"]


def test_normal_edge_still_value():
    pl = _payload(0.53, 2.20, 3.4, 3.6)  # kalibrasyon (w=0.35) sonrası değer ≈ +%4
    picks = rank_picks(pl, SimpleNamespace(value_edge_min=0.03))
    assert any(x["selection"] == "1" and x.get("kind") == "değer" for x in picks)
