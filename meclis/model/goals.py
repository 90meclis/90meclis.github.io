"""Gol modeli: zaman ağırlıklı Dixon-Coles (1997) + Poisson skor matrisi.

log λ_ev  = μ + γ + a_ev - d_dep
log λ_dep = μ + a_dep - d_ev
Düşük skorlu sonuçlar için Dixon-Coles τ düzeltmesi (ρ) uygulanır. Kimlik belirlenebilirliği ve
az maçlı takımlar için parametrelere hafif L2 (ridge) cezası eklenir — yeni çıkan takım lig ortalamasına çekilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_GOALS = 10


@dataclass
class GoalModel:
    teams: list[str]
    attack: dict[str, float]
    defence: dict[str, float]
    mu: float
    home_adv: float
    rho: float
    ht_ratio: float = 0.44
    n_matches: dict[str, int] = field(default_factory=dict)
    converged: bool = True

    def has_team(self, t: str, min_matches: int = 1) -> bool:
        return t in self.attack and self.n_matches.get(t, 0) >= min_matches

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        lh = np.exp(self.mu + self.home_adv + self.attack[home] - self.defence[away])
        la = np.exp(self.mu + self.attack[away] - self.defence[home])
        return float(lh), float(la)


def _tau(x, y, lh, la, rho):
    t = np.ones_like(lh)
    t = np.where((x == 0) & (y == 0), 1 - lh * la * rho, t)
    t = np.where((x == 0) & (y == 1), 1 + lh * rho, t)
    t = np.where((x == 1) & (y == 0), 1 + la * rho, t)
    t = np.where((x == 1) & (y == 1), 1 - rho, t)
    return np.clip(t, 1e-6, None)


def fit_dixon_coles(matches: list[dict], xi: float = 0.0019, ridge: float = 0.5,
                    ref_time=None) -> GoalModel:
    """matches: [{'home','away','hg','ag','days_ago', 'hthg','htag'}]"""
    rows = [m for m in matches if m.get("hg") is not None and m.get("ag") is not None]
    if len(rows) < 10:
        raise ValueError("Model için yeterli maç yok (en az 10).")
    teams = sorted({m["home"] for m in rows} | {m["away"] for m in rows})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    hi = np.array([idx[m["home"]] for m in rows])
    ai = np.array([idx[m["away"]] for m in rows])
    x = np.array([m["hg"] for m in rows], dtype=float)
    y = np.array([m["ag"] for m in rows], dtype=float)
    w = np.exp(-xi * np.array([max(0.0, m.get("days_ago", 0.0)) for m in rows]))

    def unpack(p):
        return p[:n], p[n:2 * n], p[2 * n], p[2 * n + 1], p[2 * n + 2]

    def nll(p):
        a, d, mu, gam, rho = unpack(p)
        lh = np.exp(mu + gam + a[hi] - d[ai])
        la = np.exp(mu + a[ai] - d[hi])
        ll = np.log(_tau(x, y, lh, la, rho)) + x * np.log(lh) - lh + y * np.log(la) - la
        return -(w * ll).sum() + ridge * (np.sum(a ** 2) + np.sum(d ** 2))

    def grad(p):
        a, d, mu, gam, rho = unpack(p)
        lh = np.exp(mu + gam + a[hi] - d[ai])
        la = np.exp(mu + a[ai] - d[hi])
        # Poisson kısmının türevi (τ kısmı küçük; sayısal olarak eklenir)
        gh = w * (x - lh)
        ga = w * (y - la)
        g = np.zeros_like(p)
        np.add.at(g, hi, -gh)
        np.add.at(g, ai, -ga)
        np.add.at(g, n + ai, gh)
        np.add.at(g, n + hi, ga)
        g[2 * n] = -(gh.sum() + ga.sum())
        g[2 * n + 1] = -gh.sum()
        # τ terimleri: sayısal türev (yalnızca düşük skorlu maçlar)
        eps = 1e-6
        base_tau = np.log(_tau(x, y, lh, la, rho))
        low = (x <= 1) & (y <= 1)
        if low.any():
            # λ'lar üzerinden zincir kuralı
            lh2 = lh * (1 + eps)
            la2 = la * (1 + eps)
            dth = (np.log(_tau(x, y, lh2, la, rho)) - base_tau) / eps  # d/dlog λh
            dta = (np.log(_tau(x, y, lh, la2, rho)) - base_tau) / eps
            dth, dta = w * dth, w * dta
            np.add.at(g, hi, -dth)
            np.add.at(g, n + ai, dth)
            np.add.at(g, ai, -dta)
            np.add.at(g, n + hi, dta)
            g[2 * n] -= (dth.sum() + dta.sum())
            g[2 * n + 1] -= dth.sum()
            g[2 * n + 2] = -(w * (np.log(_tau(x, y, lh, la, rho + eps)) - base_tau) / eps).sum()
        g[:n] += 2 * ridge * a
        g[n:2 * n] += 2 * ridge * d
        return g

    p0 = np.zeros(2 * n + 3)
    p0[2 * n] = np.log(max(0.3, (x.mean() + y.mean()) / 2))
    p0[2 * n + 1] = 0.2
    bounds = [(-3, 3)] * (2 * n) + [(-3, 3), (-1, 1), (-0.25, 0.25)]
    res = minimize(nll, p0, jac=grad, method="L-BFGS-B", bounds=bounds, options={"maxiter": 500})
    a, d, mu, gam, rho = unpack(res.x)
    counts: dict[str, int] = {t: 0 for t in teams}
    for m in rows:
        counts[m["home"]] += 1
        counts[m["away"]] += 1
    ht = [(m.get("hthg"), m.get("htag"), m["hg"], m["ag"]) for m in rows]
    ht = [h for h in ht if h[0] is not None and h[1] is not None]
    ft_sum = sum(h[2] + h[3] for h in ht)
    ht_ratio = (sum(h[0] + h[1] for h in ht) / ft_sum) if ht and ft_sum > 0 else 0.44
    return GoalModel(teams=teams, attack={t: float(a[i]) for t, i in idx.items()},
                     defence={t: float(d[i]) for t, i in idx.items()}, mu=float(mu), home_adv=float(gam),
                     rho=float(rho), ht_ratio=float(min(0.6, max(0.3, ht_ratio))), n_matches=counts,
                     converged=bool(res.success))


def score_matrix(lh: float, la: float, rho: float = 0.0, max_goals: int = MAX_GOALS) -> np.ndarray:
    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    if rho:
        m[0, 0] *= max(1e-6, 1 - lh * la * rho)
        m[0, 1] *= max(1e-6, 1 + lh * rho)
        m[1, 0] *= max(1e-6, 1 + la * rho)
        m[1, 1] *= max(1e-6, 1 - rho)
    return m / m.sum()


def goal_markets(m: np.ndarray, lh: float, la: float, ht_ratio: float = 0.44) -> list[dict]:
    """Tek skor matrisinden tutarlı pazar olasılıkları."""
    g = np.arange(m.shape[0])
    tot = g[:, None] + g[None, :]
    home = float(np.tril(m, -1).sum())
    draw = float(np.trace(m))
    away = float(np.triu(m, 1).sum())
    out = [
        {"market": "1X2", "selection": "1", "line": None, "probability": home},
        {"market": "1X2", "selection": "X", "line": None, "probability": draw},
        {"market": "1X2", "selection": "2", "line": None, "probability": away},
        {"market": "DC", "selection": "1X", "line": None, "probability": home + draw},
        {"market": "DC", "selection": "X2", "line": None, "probability": draw + away},
        {"market": "DC", "selection": "12", "line": None, "probability": home + away},
    ]
    for line in (1.5, 2.5, 3.5):
        over = float(m[tot > line].sum())
        out.append({"market": "OU_GOALS", "selection": "ÜST", "line": line, "probability": over})
        out.append({"market": "OU_GOALS", "selection": "ALT", "line": line, "probability": 1 - over})
    btts = float(m[1:, 1:].sum())
    out.append({"market": "BTTS", "selection": "VAR", "line": None, "probability": btts})
    out.append({"market": "BTTS", "selection": "YOK", "line": None, "probability": 1 - btts})
    for line in (0.5, 1.5):
        ph = float(m[g > line, :].sum())
        pa = float(m[:, g > line].sum())
        out.append({"market": "TEAM_GOALS_HOME", "selection": "ÜST", "line": line, "probability": ph})
        out.append({"market": "TEAM_GOALS_HOME", "selection": "ALT", "line": line, "probability": 1 - ph})
        out.append({"market": "TEAM_GOALS_AWAY", "selection": "ÜST", "line": line, "probability": pa})
        out.append({"market": "TEAM_GOALS_AWAY", "selection": "ALT", "line": line, "probability": 1 - pa})
    # İlk yarı: λ_İY = λ * İY oranı (ligden ölçülür), bağımsız Poisson
    lht = (lh + la) * ht_ratio
    for line in (0.5, 1.5):
        over = float(1 - poisson.cdf(int(line), lht))
        out.append({"market": "HT_OU_GOALS", "selection": "ÜST", "line": line, "probability": over})
        out.append({"market": "HT_OU_GOALS", "selection": "ALT", "line": line, "probability": 1 - over})
    flat = [(float(m[i, j]), f"{i}-{j}") for i in range(min(6, m.shape[0])) for j in range(min(6, m.shape[1]))]
    for p, s in sorted(flat, reverse=True)[:6]:
        out.append({"market": "CS", "selection": s, "line": None, "probability": p})
    return out


def most_likely_scores(m: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
    flat = [(float(m[i, j]), f"{i}-{j}") for i in range(m.shape[0]) for j in range(m.shape[1])]
    return [(s, p) for p, s in sorted(flat, reverse=True)[:k]]
