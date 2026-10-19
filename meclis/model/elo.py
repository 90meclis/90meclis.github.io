"""Takım gücü önseli: Elo puanları.

Club Elo (clubelo.com) API'si 2026 Eylül'ünden beri kimlik doğrulama istiyor; bu yüzden puanlar,
havuzdaki gerçek maç sonuçlarından (football-data.co.uk, OpenLigaDB, …) kendi içimizde hesaplanır
("Meclis Elo"). Club Elo erişimi açılırsa (CLUBELO_KEY) başlangıç puanı oradan alınır.

Elo → gol beklentisi: lig geçmişinde maç öncesi Elo farkı (Δ) ile atılan gol arasında Poisson
regresyonu kurulur:  log λ_ev = b0 + b1·Δ/400,  log λ_dep = c0 − c1·Δ/400.
Dixon-Coles λ'ları ile log uzayında w ağırlığıyla harmanlanır (w, geriye dönük testle seçildi).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

INIT = 1500.0
K = 20.0
HOME_ADV = 65.0
BLEND_WEIGHT = 0.45  # geriye dönük testle seçildi (752 maç; bkz. docs/kaynaklar.md)


@dataclass
class EloModel:
    ratings: dict[str, float]
    b: tuple[float, float]
    c: tuple[float, float]
    n_matches: dict[str, int] = field(default_factory=dict)
    source: str = "meclis-elo"

    def lambdas(self, home: str, away: str) -> tuple[float, float] | None:
        if home not in self.ratings or away not in self.ratings:
            return None
        d = (self.ratings[home] + HOME_ADV - self.ratings[away]) / 400.0
        return math.exp(self.b[0] + self.b[1] * d), math.exp(self.c[0] - self.c[1] * d)


def _goal_mult(gd: int) -> float:
    gd = abs(gd)
    return 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)


def run_elo(rows: list[dict], priors: dict[str, float] | None = None) -> tuple[dict[str, float], list[float], dict]:
    """rows zaman sırasıyla: {'home','away','hg','ag'}. Dönüş: son puanlar, maç öncesi Δ listesi, maç sayıları."""
    priors = priors or {}
    r: dict[str, float] = {}
    counts: dict[str, int] = {}
    deltas = []
    for m in rows:
        h, a = m["home"], m["away"]
        rh = r.setdefault(h, priors.get(h, INIT))
        ra = r.setdefault(a, priors.get(a, INIT))
        d = rh + HOME_ADV - ra
        deltas.append(d / 400.0)
        exp_h = 1 / (1 + 10 ** (-d / 400))
        res = 1.0 if m["hg"] > m["ag"] else (0.5 if m["hg"] == m["ag"] else 0.0)
        ch = K * _goal_mult(m["hg"] - m["ag"]) * (res - exp_h)
        r[h], r[a] = rh + ch, ra - ch
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    return r, deltas, counts


def _fit_pois(dl: np.ndarray, g: np.ndarray, sign: float) -> tuple[float, float]:
    def nll(p):
        lam = np.exp(p[0] + sign * p[1] * dl)
        return -(g * np.log(lam) - lam).sum() + 0.5 * p[1] ** 2

    res = minimize(nll, np.array([math.log(max(0.3, g.mean())), 0.5]), method="L-BFGS-B",
                   bounds=[(-2, 2), (-3, 3)])
    return float(res.x[0]), float(res.x[1])


def fit_elo(rows: list[dict], priors: dict[str, float] | None = None, burn_in: int = 60) -> EloModel:
    rows = sorted([m for m in rows if m.get("hg") is not None and m.get("ag") is not None],
                  key=lambda m: -m.get("days_ago", 0.0))
    if len(rows) < burn_in + 30:
        raise ValueError("Elo için yeterli maç yok")
    ratings, deltas, counts = run_elo(rows, priors)
    dl = np.array(deltas[burn_in:])
    hg = np.array([m["hg"] for m in rows[burn_in:]], dtype=float)
    ag = np.array([m["ag"] for m in rows[burn_in:]], dtype=float)
    return EloModel(ratings=ratings, b=_fit_pois(dl, hg, 1.0), c=_fit_pois(dl, ag, -1.0), n_matches=counts)


def blend(dc: tuple[float, float], elo: tuple[float, float] | None, w: float = BLEND_WEIGHT) -> tuple[float, float]:
    if not elo or w <= 0:
        return dc
    return (math.exp((1 - w) * math.log(dc[0]) + w * math.log(elo[0])),
            math.exp((1 - w) * math.log(dc[1]) + w * math.log(elo[1])))
