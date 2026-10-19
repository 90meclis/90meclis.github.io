"""Güven Panosu metrikleri: kayıplar dahil her şey. Ölçütler ayrı tanımlanır:
* İsabet oranı = kazanan / (kazanan + kaybeden)   (iade hariç)
* Kâr (birim)  = 1 birim sabit stake, yalnızca PİYASA oranı olan tahminlerde
* ROI          = kâr / piyasa oranlı sonuçlanmış (iade hariç) tahmin sayısı
* Brier skoru  = ortalama (olasılık − sonuç)²  (düşük = iyi)
"""
from __future__ import annotations

import pandas as pd

from .markets import MARKET_LABELS, TAG_LABELS
from .timeutil import TR

SETTLED = ("kazandi", "kaybetti", "iade")


def predictions_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["id", "kickoff_at", "tag", "market", "status", "odds", "probability", "profit"])
    df = pd.DataFrame(rows)
    df["kickoff"] = pd.to_datetime(df["kickoff_at"], utc=True).dt.tz_convert(TR)
    df["hafta"] = df["kickoff"].dt.strftime("%G-H%V")
    df["has_odds"] = df["odds"].notna()
    df["pazar"] = df["market"].map(MARKET_LABELS).fillna(df["market"])
    df["etiket"] = df["tag"].map(TAG_LABELS).fillna(df["tag"])
    return df


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"toplam": 0, "sonuçlanan": 0, "kazanan": 0, "kaybeden": 0, "iade": 0, "bekleyen": 0,
                "isabet": None, "kâr": 0.0, "roi": None, "piyasa_oranlı": 0, "brier": None, "clv": None, "clv_n": 0}
    s = df[df["status"].isin(SETTLED)]
    won, lost = int((s["status"] == "kazandi").sum()), int((s["status"] == "kaybetti").sum())
    priced = s[s["has_odds"] & (s["status"] != "iade")]
    profit = float(pd.to_numeric(priced["profit"], errors="coerce").fillna(0).sum())
    wl = s[s["status"] != "iade"]
    brier = float(((wl["probability"].astype(float) - (wl["status"] == "kazandi").astype(float)) ** 2).mean()) if len(wl) else None
    clv = pd.to_numeric(s["clv"], errors="coerce").dropna() if "clv" in s else pd.Series(dtype=float)
    return {"clv": float(clv.mean()) if len(clv) else None, "clv_n": int(len(clv)), "toplam": int(len(df)), "sonuçlanan": int(len(s)), "kazanan": won, "kaybeden": lost,
            "iade": int((s["status"] == "iade").sum()), "bekleyen": int((~df["status"].isin(SETTLED)).sum()),
            "isabet": (won / (won + lost)) if (won + lost) else None, "kâr": round(profit, 2),
            "roi": (profit / len(priced)) if len(priced) else None, "piyasa_oranlı": int(len(priced)), "brier": brier}


def breakdown(df: pd.DataFrame, by: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    rows = []
    for key, g in df.groupby(by, sort=True):
        s = summarize(g)
        rows.append({by: key, "tahmin": s["toplam"], "kazanan": s["kazanan"], "kaybeden": s["kaybeden"],
                     "iade": s["iade"], "bekleyen": s["bekleyen"],
                     "isabet %": round(s["isabet"] * 100, 1) if s["isabet"] is not None else None,
                     "kâr (birim)": s["kâr"], "ROI %": round(s["roi"] * 100, 1) if s["roi"] is not None else None,
                     "piyasa oranlı": s["piyasa_oranlı"]})
    return pd.DataFrame(rows)


def equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["kickoff", "kümülatif kâr"])
    s = df[df["status"].isin(("kazandi", "kaybetti")) & df["has_odds"]].sort_values("kickoff")
    out = pd.DataFrame({"kickoff": s["kickoff"], "kümülatif kâr": pd.to_numeric(s["profit"]).fillna(0).cumsum()})
    return out


def calibration(df: pd.DataFrame, bins=(0, .4, .5, .6, .7, .8, 1.0)) -> pd.DataFrame:
    s = df[df["status"].isin(("kazandi", "kaybetti"))] if not df.empty else df
    if s.empty:
        return pd.DataFrame()
    cut = pd.cut(s["probability"].astype(float), bins=list(bins), include_lowest=True)
    g = s.assign(win=(s["status"] == "kazandi").astype(float), aralik=cut.astype(str)).groupby("aralik", observed=True)
    return pd.DataFrame({"tahmin": g.size(), "ortalama olasılık %": (g["probability"].mean() * 100).round(1),
                         "gerçekleşen %": (g["win"].mean() * 100).round(1)}).reset_index()
