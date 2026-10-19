"""Pazar tanımları, Türkçe etiketler, piyasa oranı eşleme ve sonuçlandırma kuralları."""
from __future__ import annotations

import math

MARKET_LABELS = {
    "1X2": "Maç Sonucu", "DC": "Çifte Şans", "OU_GOALS": "Toplam Gol", "BTTS": "Karşılıklı Gol",
    "TEAM_GOALS_HOME": "Ev Sahibi Gol", "TEAM_GOALS_AWAY": "Deplasman Gol", "CS": "Skor",
    "HT_OU_GOALS": "İlk Yarı Gol", "CORNERS_OU": "Toplam Korner", "CARDS_OU": "Toplam Kart",
    "SOT_OU": "Toplam İsabetli Şut", "GOAL_KICKS_OU": "Toplam Kale Vuruşu",
}
MARKET_GROUPS = {
    "Skor / Sonuç": ["1X2", "DC", "CS"],
    "Gol": ["OU_GOALS", "BTTS", "TEAM_GOALS_HOME", "TEAM_GOALS_AWAY", "HT_OU_GOALS"],
    "Korner": ["CORNERS_OU"], "Kart": ["CARDS_OU"], "İsabetli Şut": ["SOT_OU"], "Kale Vuruşu": ["GOAL_KICKS_OU"],
}
STATUS_LABELS = {"bekliyor": "Bekliyor", "basladi": "Başladı", "kazandi": "Kazandı", "kaybetti": "Kaybetti",
                 "iade": "İade"}
STATUS_ICONS = {"bekliyor": "⏳", "basladi": "▶️", "kazandi": "✅", "kaybetti": "❌", "iade": "↩️"}
QUEUE_LABELS = {"bekliyor": "Yayın bekliyor / yeniden hesaplanacak", "tamamlandi": "Yayımlandı"}
TAG_LABELS = {"meclis_gorusu": "Meclis Görüşü", "gunun_karari": "Günün Kararı", "karar_birligi": "Karar Birliği"}


def pick_label(market: str, selection: str, line: float | None, home: str = "Ev", away: str = "Dep") -> str:
    lab = MARKET_LABELS.get(market, market)
    if market == "1X2":
        return {"1": f"MS 1 ({home})", "X": "MS X (beraberlik)", "2": f"MS 2 ({away})"}[selection]
    if market == "DC":
        return f"Çifte Şans {selection}"
    if market == "BTTS":
        return f"KG {selection.title()}"
    if market == "CS":
        return f"Skor {selection}"
    if line is not None:
        return f"{lab} {line:g} {selection.title()}"
    return f"{lab} {selection}"


def attach_odds(pick: dict, odds: dict) -> dict:
    """Piyasa oranı varsa ekler; yoksa yalnızca modelin adil oranı kalır."""
    p = pick["probability"]
    pick["fair_odds"] = round(1 / p, 3) if p > 0 else None
    pick["odds"], pick["odds_source"], pick["edge"] = None, "model_adil", None
    o = None
    if pick["market"] == "1X2" and "1X2" in odds:
        o, src = odds["1X2"].get(pick["selection"]), odds["1X2"].get("src")
    elif pick["market"] == "OU_GOALS" and pick["line"] is not None:
        key = f"OU_GOALS_{pick['line']:g}"
        if key in odds:
            o, src = odds[key].get(pick["selection"]), odds[key].get("src")
    elif pick["market"] == "BTTS" and "BTTS" in odds:
        o, src = odds["BTTS"].get(pick["selection"]), odds["BTTS"].get("src")
    elif pick["market"] == "DC" and "1X2" in odds:
        # Çifte şans piyasa oranı ayrı yoksa 1X2'den TÜRETİLMEZ (marj belirsiz) — adil oranla kalır.
        o = None
    if o and o > 1.0:
        pick["odds"], pick["odds_source"] = float(o), src or "piyasa"
        pick["edge"] = round(p * float(o) - 1, 4)
    return pick


def _ou(total: float | None, line: float, selection: str) -> str | None:
    if total is None:
        return None
    if abs(total - line) < 1e-9:
        return "iade"
    over = total > line
    return "kazandi" if (over == (selection == "ÜST")) else "kaybetti"


def settle_pick(market: str, selection: str, line: float | None, r: dict) -> tuple[str | None, str | None]:
    """r: sonuç sözlüğü. Döner: (durum, sonuç_değeri) — veri yoksa (None, None)."""
    hg, ag = r.get("home_goals"), r.get("away_goals")
    if r.get("status") in ("iptal", "ertelendi"):
        return "iade", r.get("status")
    if market in ("1X2", "DC", "OU_GOALS", "BTTS", "TEAM_GOALS_HOME", "TEAM_GOALS_AWAY", "CS"):
        if hg is None or ag is None:
            return None, None
        res = "1" if hg > ag else "X" if hg == ag else "2"
        val = f"{hg}-{ag}"
        if market == "1X2":
            return ("kazandi" if res == selection else "kaybetti"), val
        if market == "DC":
            return ("kazandi" if res in selection else "kaybetti"), val
        if market == "OU_GOALS":
            return _ou(hg + ag, line, selection), val
        if market == "TEAM_GOALS_HOME":
            return _ou(hg, line, selection), val
        if market == "TEAM_GOALS_AWAY":
            return _ou(ag, line, selection), val
        if market == "BTTS":
            yes = hg > 0 and ag > 0
            return ("kazandi" if yes == (selection == "VAR") else "kaybetti"), val
        if market == "CS":
            return ("kazandi" if val == selection else "kaybetti"), val
    if market == "HT_OU_GOALS":
        h, a = r.get("ht_home_goals"), r.get("ht_away_goals")
        if h is None or a is None:
            return None, None
        return _ou(h + a, line, selection), f"İY {h}-{a}"
    stat = {"CORNERS_OU": "corners", "CARDS_OU": "cards", "SOT_OU": "shots_on_target",
            "GOAL_KICKS_OU": "goal_kicks"}.get(market)
    if stat:
        h, a = r.get(f"home_{stat}"), r.get(f"away_{stat}")
        if h is None or a is None:
            return None, None
        return _ou(h + a, line, selection), f"{h}+{a}={h + a}"
    return None, None


def profit_for(status: str, odds: float | None, stake: float = 1.0) -> float | None:
    """1 birim sabit stake ile kâr/zarar. Piyasa oranı yoksa kâr hesaplanmaz (None)."""
    if status == "iade":
        return 0.0
    if odds is None or (isinstance(odds, float) and math.isnan(odds)):
        return None
    if status == "kazandi":
        return round(stake * (odds - 1), 4)
    if status == "kaybetti":
        return -float(stake)
    return None
