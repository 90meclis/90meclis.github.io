import numpy as np
import pytest

from meclis.model.counts import count_markets, fit_count_model, prob_over
from meclis.model.goals import fit_dixon_coles, goal_markets, score_matrix


def synthetic(n_rounds=2, seed=3):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(14)]
    att = {t: rng.normal(0, 0.35) for t in teams}
    att["T0"] = 0.6  # güçlü takım
    att["T1"] = -0.6  # zayıf takım
    dfn = {t: 0.0 for t in teams}
    rows = []
    for _ in range(n_rounds):
        for h in teams:
            for a in teams:
                if h != a:
                    lh, la = np.exp(0.1 + 0.25 + att[h] - dfn[a]), np.exp(0.1 + att[a] - dfn[h])
                    rows.append({"home": h, "away": a, "hg": rng.poisson(lh), "ag": rng.poisson(la),
                                 "days_ago": rng.uniform(0, 300)})
    return rows


def test_score_matrix_sums_to_one_and_markets_consistent():
    m = score_matrix(1.6, 1.1, rho=-0.05)
    assert m.sum() == pytest.approx(1.0)
    mk = {(x["market"], x["selection"], x["line"]): x["probability"] for x in goal_markets(m, 1.6, 1.1)}
    assert mk[("1X2", "1", None)] + mk[("1X2", "X", None)] + mk[("1X2", "2", None)] == pytest.approx(1.0)
    assert mk[("OU_GOALS", "ÜST", 2.5)] + mk[("OU_GOALS", "ALT", 2.5)] == pytest.approx(1.0)
    assert mk[("OU_GOALS", "ÜST", 1.5)] > mk[("OU_GOALS", "ÜST", 2.5)] > mk[("OU_GOALS", "ÜST", 3.5)]
    assert mk[("DC", "1X", None)] == pytest.approx(mk[("1X2", "1", None)] + mk[("1X2", "X", None)])
    assert mk[("1X2", "1", None)] > mk[("1X2", "2", None)]  # ev sahibi daha yüksek λ


def test_dixon_coles_recovers_strength_order_and_home_advantage():
    gm = fit_dixon_coles(synthetic())
    assert gm.converged
    assert gm.attack["T0"] > gm.attack["T1"]
    assert gm.home_adv > 0
    lh, la = gm.lambdas("T0", "T1")
    assert lh > la
    assert -0.25 <= gm.rho <= 0.25


def test_dixon_coles_needs_data():
    with pytest.raises(ValueError):
        fit_dixon_coles([{"home": "A", "away": "B", "hg": 1, "ag": 0}])


def test_count_model_negative_binomial_and_lines():
    rng = np.random.default_rng(1)
    rows = []
    teams = [f"T{i}" for i in range(10)]
    for h in teams:
        for a in teams:
            if h != a:
                rows.append({"home": h, "away": a, "h": int(rng.negative_binomial(5, 5 / (5 + 5.5))),
                             "a": int(rng.negative_binomial(5, 5 / (5 + 4.5))), "days_ago": 10})
    cm = fit_count_model(rows, "corners")
    assert cm.total_mean == pytest.approx(10, abs=1.2)
    mk, info = count_markets(cm, "T0", "T1")
    assert info["dist"] == "negatif binom"
    overs = [x for x in mk if x["selection"] == "ÜST"]
    assert overs[0]["probability"] > overs[-1]["probability"]
    for x in mk:
        assert 0 <= x["probability"] <= 1


def test_prob_over_poisson_vs_nb():
    p_pois = prob_over(9.5, 9.5, None)
    p_nb = prob_over(9.5, 9.5, 5.0)
    assert 0.3 < p_pois < 0.6 and 0.3 < p_nb < 0.6
