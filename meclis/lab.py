"""Veri Laboratuvarı: pazar ligleri (takım bazlı tablolar) ve maç maç takım serileri."""
from __future__ import annotations

import pandas as pd

from .analysis import LeagueContext, _stat_value


def team_rows(ctx: LeagueContext, scope: str = "tümü", last_n: int | None = None) -> pd.DataFrame:
    """Her takım-maç için bir satır (takım bakış açısıyla)."""
    teams = {}
    for m in ctx.matches:
        teams[m["home_team_id"]] = m["home_name"]
        teams[m["away_team_id"]] = m["away_name"]
    rows = []
    for tid, name in teams.items():
        ms = ctx.team_matches(tid)
        if scope == "iç saha":
            ms = [m for m in ms if m["home_team_id"] == tid]
        elif scope == "deplasman":
            ms = [m for m in ms if m["away_team_id"] == tid]
        if last_n:
            ms = ms[:last_n]
        for m in ms:
            home = m["home_team_id"] == tid
            st = ctx.stats.get(m["id"]) or {}
            mine, opp = (st.get("home") or {}, st.get("away") or {}) if home else (st.get("away") or {}, st.get("home") or {})
            gf, ga = (m["home_goals"], m["away_goals"]) if home else (m["away_goals"], m["home_goals"])
            hf, ha = (m.get("ht_home_goals"), m.get("ht_away_goals")) if home else (m.get("ht_away_goals"), m.get("ht_home_goals"))
            rows.append({"takım": name, "team_id": tid, "tarih": m["kickoff_at"][:10], "gf": gf, "ga": ga,
                         "ht_total": (hf + ha) if hf is not None and ha is not None else None,
                         "ht_gf": hf, "btts": int(gf > 0 and ga > 0),
                         "corners_for": mine.get("corners"), "corners_against": opp.get("corners"),
                         "cards_for": _stat_value(mine, "cards"), "cards_against": _stat_value(opp, "cards"),
                         "sot_for": mine.get("shots_on_target"), "sot_against": opp.get("shots_on_target"),
                         "shots_for": mine.get("shots"), "goal_kicks_for": mine.get("goal_kicks")})
    return pd.DataFrame(rows)


def _pct(series, cond) -> float | None:
    s = series.dropna()
    return round(100 * float(cond(s).mean()), 1) if len(s) else None


def market_tables(ctx: LeagueContext, scope: str = "tümü", last_n: int | None = None) -> dict[str, pd.DataFrame]:
    df = team_rows(ctx, scope, last_n)
    if df.empty:
        return {}
    out = {}
    g = df.groupby("takım")

    def build(cols):
        rows = []
        for team, d in g:
            row = {"Takım": team, "Maç": len(d)}
            for label, fn in cols:
                row[label] = fn(d)
            rows.append(row)
        return pd.DataFrame(rows)

    def avg(c):
        return lambda d: round(float(d[c].dropna().mean()), 2) if d[c].notna().any() else None

    def tot_corners(d):
        t = (d["corners_for"] + d["corners_against"]).dropna()
        return t

    out["Korner"] = build([
        ("Attığı (ort.)", avg("corners_for")), ("Yediği (ort.)", avg("corners_against")),
        ("Toplam (ort.)", lambda d: round(float(tot_corners(d).mean()), 2) if len(tot_corners(d)) else None),
        ("Toplam 8.5 Üst %", lambda d: _pct(d["corners_for"] + d["corners_against"], lambda s: s > 8.5)),
        ("Toplam 9.5 Üst %", lambda d: _pct(d["corners_for"] + d["corners_against"], lambda s: s > 9.5)),
        ("Veri olan maç", lambda d: int(d["corners_for"].notna().sum())),
    ]).sort_values("Toplam (ort.)", ascending=False, na_position="last")
    out["İlk Yarı Gol"] = build([
        ("İY toplam gol (ort.)", avg("ht_total")),
        ("İY 0.5 Üst %", lambda d: _pct(d["ht_total"], lambda s: s > 0.5)),
        ("İY 1.5 Üst %", lambda d: _pct(d["ht_total"], lambda s: s > 1.5)),
        ("İY gol attığı maç %", lambda d: _pct(d["ht_gf"], lambda s: s > 0)),
    ]).sort_values("İY 0.5 Üst %", ascending=False, na_position="last")
    out["KG Var/Yok"] = build([
        ("KG Var %", lambda d: _pct(d["btts"], lambda s: s == 1)),
        ("KG Yok %", lambda d: _pct(d["btts"], lambda s: s == 0)),
        ("Attığı gol (ort.)", avg("gf")), ("Yediği gol (ort.)", avg("ga")),
        ("Gol atamadığı maç %", lambda d: _pct(d["gf"], lambda s: s == 0)),
        ("Gol yemediği maç %", lambda d: _pct(d["ga"], lambda s: s == 0)),
    ]).sort_values("KG Var %", ascending=False, na_position="last")
    out["Kart"] = build([
        ("Gördüğü kart (ort.)", avg("cards_for")), ("Rakibin kartı (ort.)", avg("cards_against")),
        ("Maç toplamı 4.5 Üst %", lambda d: _pct(d["cards_for"] + d["cards_against"], lambda s: s > 4.5)),
        ("Veri olan maç", lambda d: int(d["cards_for"].notna().sum())),
    ]).sort_values("Gördüğü kart (ort.)", ascending=False, na_position="last")
    out["İsabetli Şut"] = build([
        ("Attığı isabetli şut (ort.)", avg("sot_for")), ("Rakip isabetli şut (ort.)", avg("sot_against")),
        ("Toplam şut (ort.)", avg("shots_for")), ("Veri olan maç", lambda d: int(d["sot_for"].notna().sum())),
    ]).sort_values("Attığı isabetli şut (ort.)", ascending=False, na_position="last")
    gk = df["goal_kicks_for"].notna().sum()
    if gk:
        out["Kale Vuruşu"] = build([("Kale vuruşu (ort.)", avg("goal_kicks_for")),
                                    ("Veri olan maç", lambda d: int(d["goal_kicks_for"].notna().sum()))])
    return out


TREND_DEFS = [
    # (pazar, koşul metni, değer fonksiyonu(row), eşik)
    ("korner", "maç toplam korner > 9.5", lambda r: _sum(r["corners_for"], r["corners_against"]), 9.5),
    ("takım kornerı", "takımın korneri > 4.5", lambda r: r["corners_for"], 4.5),
    ("KG var/yok", "karşılıklı gol var", lambda r: r["btts"], 0.5),
    ("ilk yarı gol", "ilk yarıda gol var (> 0.5)", lambda r: r["ht_total"], 0.5),
    ("gol", "maç toplam gol > 2.5", lambda r: _sum(r["gf"], r["ga"]), 2.5),
    ("şut sayısı", "takımın şutu > 11.5", lambda r: r["shots_for"], 11.5),
    ("isabetli şut", "takımın isabetli şutu > 4.5", lambda r: r["sot_for"], 4.5),
    ("kart", "maç toplam kart > 4.5", lambda r: _sum(r["cards_for"], r["cards_against"]), 4.5),
]


def _sum(a, b):
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return None
    return a + b


def compute_trends(ctx: LeagueContext, n: int = 10) -> list[dict]:
    """trends tablosu satırları: her takım × pazar için maç maç değerler ve süren seri."""
    from .timeutil import now_utc, to_iso

    df = team_rows(ctx)
    if df.empty:
        return []
    out = []
    ts = to_iso(now_utc())
    for tid, g in df.groupby("team_id"):
        g = g.sort_values("tarih", ascending=False).head(n)
        name = g["takım"].iloc[0]
        raw = [m for m in ctx.team_matches(tid, n)]
        for market, cond, fn, thr in TREND_DEFS:
            vals = []
            for (_, r), m in zip(g.iterrows(), raw):
                v = fn(r)
                v = None if v is None or pd.isna(v) else (int(v) if float(v).is_integer() else float(v))
                home = m["home_team_id"] == tid
                vals.append({"tarih": r["tarih"], "rakip": m["away_name"] if home else m["home_name"],
                             "yer": "İ" if home else "D", "değer": v})
            known = [x["değer"] for x in vals if x["değer"] is not None]
            if not known:
                continue
            first = known[0] > thr
            streak = 0
            for v in known:
                if (v > thr) == first:
                    streak += 1
                else:
                    break
            out.append({"id": f"{tid}:{market}", "team_id": tid, "team_name": name, "league": ctx.league,
                        "market": market, "condition": cond, "streak": streak if first else -streak,
                        "hits_last10": int(sum(1 for v in known if v > thr)), "match_values": vals,
                        "updated_at": ts})
    return out
