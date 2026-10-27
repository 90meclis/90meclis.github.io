from meclis.editoryal import card, postmortem


def _pred(**kw):
    p = {"id": "p1", "market": "OU_GOALS", "selection": "ÜST", "line": 2.5, "probability": 0.61, "odds": 1.62,
         "home_name": "A", "away_name": "B", "status": "bekliyor",
         "calibration": {"p_model": 0.60, "p_piyasa": 0.62}}
    p.update(kw)
    return p


def test_card_has_three_bullets_and_band():
    a = {"lambdas": {"home": 1.6, "away": 1.3}, "injury_effect": {}}
    motor = {"geritest": {"bantlar": [{"bant": "%60–65", "alt": 0.60, "ust": 0.65, "n": 300, "isabet": 0.6}]}}
    k = card(_pred(), a, motor)
    assert 1 <= len(k["maddeler"]) <= 3
    assert k["maddeler"][0].startswith("Tutma olasılığı %61") and k["maddeler"][0].endswith(".")
    assert "aynı yönde" in k["maddeler"][0]
    assert k["bant"]["bant"] == "%60–65"


def test_card_without_odds_or_motor():
    k = card(_pred(odds=None, calibration={}), None, None)
    assert k["maddeler"][0] == "Tutma olasılığı %61."
    assert k["bant"] is None


def test_postmortem_lost_over():
    m = {"home_goals": 1, "away_goals": 0}
    st = {"home": {"shots": 14, "shots_on_target": 5, "xg": 1.9}, "away": {"shots": 9, "shots_on_target": 3, "xg": 1.1}}
    n = postmortem(_pred(status="kaybetti"), m, st, {"lambdas": {"home": 1.6, "away": 1.3}})
    assert n.startswith("Yattı ✗") and "(1 gol)" in n
    assert "bitiricilik" in n  # xG 3.0 > 2.5: oyun tahmine uygundu
    n2 = postmortem(_pred(status="kazandi"), {"home_goals": 2, "away_goals": 1}, {}, None)
    assert n2.startswith("Tuttu ✓")


def test_live_pairing_and_no_settlement():
    from meclis.canli import pair

    m = {"kickoff_at": "2026-10-27T19:45:00Z", "home_name": "Bradford", "away_name": "Peterborough"}
    ev = [{"ko": "2026-10-27T19:45Z", "home": "Bradford City", "away": "Peterborough United", "hg": 1, "ag": 0,
           "canli": True, "bitti": False, "durum": "1. yarı", "dakika": "15'"},
          {"ko": "2026-10-27T22:45Z", "home": "Bradford City", "away": "Peterborough United", "hg": 0, "ag": 0,
           "canli": False, "bitti": False, "durum": None, "dakika": None}]
    assert pair(m, ev)["hg"] == 1
    assert pair({**m, "home_name": "Fleetwood"}, ev) is None
