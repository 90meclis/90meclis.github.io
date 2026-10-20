"""Sezon simülasyonu (10.000 koşu): kalan fikstür = çift devreli lig takviminin oynanmamış eşleşmeleri.
Gol beklentisi ligin bu sezonki Dixon-Coles modelinden; puan durumu oynanmış maçlardan başlar.
Çıktı: takım başına şampiyonluk, ilk 4, küme düşme (KUME_DUSME tablosu) olasılığı, ortalama puan/sıra, sıra dağılımı.
Bölünmüş/play-off formatlı ligler (İskoçya, Belçika vb.) için normal sezon sonu sırası verilir (yöntem alanı söyler).
"""
from __future__ import annotations

import numpy as np

from .timeutil import now_utc, to_iso

KUME_DUSME = {"E0": 3, "SP1": 3, "I1": 3, "D1": 2, "F1": 2, "T1": 4, "E1": 3, "N1": 2, "P1": 2, "B1": 2, "SC0": 1,
              "G1": 2, "D2": 2, "F2": 2, "SP2": 4, "I2": 3, "E2": 4, "E3": 2, "SC1": 1, "T2": 3}


def simulate_league(ctx, runs: int = 10000, seed: int = 90) -> list[dict]:
    gm = ctx.goal_model
    if gm is None:
        return []
    played = [m for m in ctx.matches if m.get("home_goals") is not None and m["league"] == ctx.league]
    teams = sorted({t for m in played for t in (m["home_team_id"], m["away_team_id"])})
    if len(teams) < 6:
        return []
    idx = {t: i for i, t in enumerate(teams)}
    pts = np.zeros(len(teams))
    gd = np.zeros(len(teams))
    seen = set()
    for m in played:
        h, a = idx[m["home_team_id"]], idx[m["away_team_id"]]
        seen.add((h, a))
        hg, ag = m["home_goals"], m["away_goals"]
        pts[h] += 3 if hg > ag else 1 if hg == ag else 0
        pts[a] += 3 if ag > hg else 1 if hg == ag else 0
        gd[h] += hg - ag
        gd[a] += ag - hg
    rem = [(h, a) for h in range(len(teams)) for a in range(len(teams)) if h != a and (h, a) not in seen]
    rng = np.random.default_rng(seed)
    P = np.tile(pts, (runs, 1))
    G = np.tile(gd, (runs, 1))
    for h, a in rem:
        lh, la = gm.lambdas(teams[h], teams[a])
        x, y = rng.poisson(lh, runs), rng.poisson(la, runs)
        P[:, h] += np.where(x > y, 3, np.where(x == y, 1, 0))
        P[:, a] += np.where(y > x, 3, np.where(x == y, 1, 0))
        G[:, h] += x - y
        G[:, a] += y - x
    key = P * 1000 + G + rng.random(P.shape) * 0.1
    rank = (-key).argsort(1).argsort(1) + 1
    nrel = KUME_DUSME.get(ctx.league, 0)
    names = {}
    for m in played:
        names[m["home_team_id"]] = m["home_name"]
        names[m["away_team_id"]] = m["away_name"]
    out = []
    nt = len(teams)
    for t, i in idx.items():
        r = rank[:, i]
        dist = np.bincount(r, minlength=nt + 1)[1:] / runs
        out.append({"league": ctx.league, "team_id": t, "team_name": names.get(t, t), "kosu": runs,
                    "sampiyon": round(float((r == 1).mean()), 4), "ilk4": round(float((r <= 4).mean()), 4),
                    "kume": round(float((r > nt - nrel).mean()), 4) if nrel else None,
                    "ort_puan": round(float(P[:, i].mean()), 1), "ort_sira": round(float(r.mean()), 2),
                    "mevcut_puan": int(pts[i]), "kalan_mac": sum(1 for h, a in rem if i in (h, a)),
                    "sira_dagilimi": [round(float(x), 4) for x in dist], "computed_at": to_iso(now_utc()),
                    "yontem": "çift devre kalan eşleşmeler; Dixon-Coles (bu sezon)"})
    return out
