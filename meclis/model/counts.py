"""Sayım pazarları (korner, kart, isabetli şut, şut, kale vuruşu) için takım oranı modeli.

Beklenen değer (ev sahibi için):  E = lig_ev_ortalaması × hücum_oranı(ev) × savunma_izni(deplasman)
Oranlar maç başına (lig ortalamasına bölünmüş) değerlerin zaman ağırlıklı, lig ortalamasına
büzülmüş (shrinkage) ortalamasıdır. Toplam için dağılım: lig toplamlarının varyansı ortalamadan
büyükse negatif binom, değilse Poisson.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import nbinom, poisson

STATS = {
    "corners": ("CORNERS_OU", "Korner"),
    "cards": ("CARDS_OU", "Kart"),
    "shots_on_target": ("SOT_OU", "İsabetli Şut"),
    "goal_kicks": ("GOAL_KICKS_OU", "Kale Vuruşu"),
}


@dataclass
class CountModel:
    stat: str
    league_home_mean: float
    league_away_mean: float
    total_mean: float
    total_var: float
    attack: dict[str, float]
    defence: dict[str, float]
    n_matches: dict[str, int]
    n_league: int

    def has_team(self, team: str, min_matches: int) -> bool:
        return self.n_matches.get(team, 0) >= min_matches

    def expected(self, home: str, away: str) -> tuple[float, float]:
        eh = self.league_home_mean * self.attack.get(home, 1.0) * self.defence.get(away, 1.0)
        ea = self.league_away_mean * self.attack.get(away, 1.0) * self.defence.get(home, 1.0)
        return eh, ea

    def dispersion_r(self, mean: float) -> float | None:
        """Toplam için NB r parametresi; varyans/ortalama oranı ligden ölçülür."""
        if self.total_mean <= 0:
            return None
        ratio = self.total_var / self.total_mean
        if ratio <= 1.05:
            return None
        # Var = m + m²/r  ve  Var/m = ratio  ->  r = m / (ratio - 1)
        return mean / (ratio - 1)


def fit_count_model(rows: list[dict], stat: str, xi: float = 0.0025, k: float = 4.0) -> CountModel | None:
    """rows: [{'home','away','h','a','days_ago'}] (h/a: o istatistiğin ev/deplasman değeri)."""
    data = [r for r in rows if r.get("h") is not None and r.get("a") is not None]
    if len(data) < 20:
        return None
    hm = float(np.mean([r["h"] for r in data]))
    am = float(np.mean([r["a"] for r in data]))
    if hm <= 0 or am <= 0:
        return None
    totals = np.array([r["h"] + r["a"] for r in data], dtype=float)
    acc: dict[str, dict[str, float]] = {}
    for r in data:
        w = math.exp(-xi * max(0.0, r.get("days_ago", 0.0))) * float(r.get("weight", 1.0))
        for team, side_for, side_against, mean_for, mean_against in (
            (r["home"], r["h"], r["a"], hm, am),
            (r["away"], r["a"], r["h"], am, hm),
        ):
            a = acc.setdefault(team, {"fw": 0.0, "f": 0.0, "a": 0.0, "n": 0})
            a["f"] += w * side_for / mean_for
            a["a"] += w * side_against / mean_against
            a["fw"] += w
            a["n"] += 1
    attack = {t: (a["f"] + k) / (a["fw"] + k) for t, a in acc.items()}
    defence = {t: (a["a"] + k) / (a["fw"] + k) for t, a in acc.items()}
    return CountModel(stat=stat, league_home_mean=hm, league_away_mean=am, total_mean=float(totals.mean()),
                      total_var=float(totals.var(ddof=1)), attack=attack, defence=defence,
                      n_matches={t: int(a["n"]) for t, a in acc.items()}, n_league=len(data))


def prob_over(mean: float, line: float, r: float | None) -> float:
    k = math.floor(line)
    if r is None:
        return float(1 - poisson.cdf(k, mean))
    p = r / (r + mean)
    return float(1 - nbinom.cdf(k, r, p))


def prob_exact(mean: float, k: int, r: float | None) -> float:
    if r is None:
        return float(poisson.pmf(k, mean))
    return float(nbinom.pmf(k, r, r / (r + mean)))


def lines_around(mean: float, n: int = 3) -> list[float]:
    base = math.floor(mean) + 0.5
    start = base - (n // 2)
    return [max(0.5, start + i) for i in range(n)]


def count_markets(model: CountModel, home: str, away: str, mult: float = 1.0) -> tuple[list[dict], dict]:
    """mult: dış etken çarpanı (ör. kartta hakem)."""
    market = STATS[model.stat][0]
    eh, ea = model.expected(home, away)
    eh, ea = eh * mult, ea * mult
    total = eh + ea
    r = model.dispersion_r(total)
    out = []
    for line in lines_around(total):
        p = prob_over(total, line, r)
        out.append({"market": market, "selection": "ÜST", "line": line, "probability": p})
        out.append({"market": market, "selection": "ALT", "line": line, "probability": 1 - p})
    info = {"home": round(eh, 2), "away": round(ea, 2), "total": round(total, 2),
            "dist": "negatif binom" if r else "Poisson", "r": round(r, 2) if r else None}
    return out, info
