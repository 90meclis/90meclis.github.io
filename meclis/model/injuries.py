"""Ağırlıklı sakatlık okuması: oyuncu önem puanı (0–1) ve Takım Eksik Etkisi (TEE, 0–100).

Oyuncu önem puanı (veri kaynakları raporu §4.1):
  I_p = u × clip( (0.20·m + 0.10·s + 0.25·c + 0.25·r + 0.20·d′) / W_mevcut , 0, 1 )
    m: dakika payı (oyuncu dakikası / takımdaki en yüksek dakika)
    s: ilk 11 payı, r: yedek açığı, d′: var/yok farkı — ücretsiz kaynaklarda bulunmadığında formülden
       çıkarılır ve ağırlıklar mevcut bileşenlere göre yeniden ölçeklenir (W_mevcut); kullanılan bileşenler
       kırılımda gösterilir.
    c: katkı payı = (gol + asist) / takımın toplam gol+asisti
    u: kesinlik — kesin yok/cezalı 1.0, şüpheli 0.5, maç günü kararı 0.3
  Oyuncu istatistiği hiç yoksa I_p = u × 0.15 (bilinmiyor) kabul edilir.

Takım Eksik Etkisi:
  TEE = 100 × [1 − Π(1 − 0.6·I_p)] × (1 + 0.15·çakışma)     (çakışma: aynı mevki grubunda ≥2 eksik)
  Bantlar: 0–10 Etkisiz, 10–25 Hissedilir, 25–45 Ciddi, 45+ Ağır.

Modele aktarma (γ = 0.35):
  hücum çarpanı   = 1 − γ·Σ(I_p · hücum_payı)     → takımın kendi λ'sı
  savunma çarpanı = 1 + γ·Σ(I_p · savunma_payı)   → rakibin λ'sı
  Çarpanlar [0.70, 1.30] aralığında sınırlanır. Ağırlıklar başlangıç değeridir; kalibrasyona açıktır.
"""
from __future__ import annotations

from ..names import strip_accents

UNKNOWN_IMPORTANCE = 0.15
ALPHA, BETA, GAMMA = 0.6, 0.15, 0.35
WEIGHTS = {"m": 0.20, "s": 0.10, "c": 0.25, "r": 0.25, "d": 0.20}
SHARES = {"ATT": (0.9, 0.1), "MID": (0.5, 0.5), "DEF": (0.15, 0.85), "GK": (0.0, 1.0), "UNK": (0.5, 0.5)}


def _pos_group(pos: str | None) -> str:
    p = (pos or "").strip().lower()
    if not p:
        return "UNK"
    if p.startswith(("g", "k")) or "goal" in p or "kaleci" in p:
        return "GK"
    if p.startswith("d") or "def" in p or "back" in p or "savun" in p or "stoper" in p:
        return "DEF"
    if p.startswith("m") or "mid" in p or "orta" in p:
        return "MID"
    if p.startswith(("f", "a")) or "att" in p or "forw" in p or "forv" in p or "kanat" in p:
        return "ATT"
    return "UNK"


def certainty(kind: str | None) -> float:
    k = (kind or "").lower()
    if "şüpheli" in k or "questionable" in k or "doubt" in k:
        return 0.5
    if "karar" in k or "game time" in k:
        return 0.3
    return 1.0


def _key(name: str) -> str:
    return "".join(ch for ch in strip_accents(name or "").lower() if ch.isalnum())


def find_player(name: str, players: list[dict]) -> dict | None:
    k = _key(name)
    if not k:
        return None
    for p in players:
        if _key(p.get("name")) == k:
            return p
    surname = _key((name or "").split()[-1]) if name else ""
    cands = [p for p in players if surname and _key(p.get("name", "")).endswith(surname)]
    return cands[0] if len(cands) == 1 else None


def player_importance(player: dict | None, team_players: list[dict], kind: str | None = None) -> dict:
    u = certainty(kind)
    if not player or not team_players:
        return {"importance": round(u * UNKNOWN_IMPORTANCE, 3), "is_key": None, "minutes_share": None,
                "ga_share": None, "group": _pos_group((player or {}).get("position")), "known": False,
                "components": [], "certainty": u}
    max_min = max((p.get("minutes") or 0) for p in team_players) or 1
    total_ga = sum((p.get("goals") or 0) + (p.get("assists") or 0) for p in team_players) or 1
    comps = {"m": (player.get("minutes") or 0) / max_min,
             "c": ((player.get("goals") or 0) + (player.get("assists") or 0)) / total_ga}
    max_lu = max((p.get("lineups") or 0) for p in team_players)
    if max_lu and player.get("lineups") is not None:
        comps["s"] = (player.get("lineups") or 0) / max_lu  # ilk 11 payı
    for opt in ("r", "d"):  # yedek açığı, var/yok farkı (varsa)
        if player.get(opt) is not None:
            comps[opt] = float(player[opt])
    w = sum(WEIGHTS[k] for k in comps)
    raw = sum(WEIGHTS[k] * v for k, v in comps.items()) / w
    imp = u * min(1.0, max(0.0, raw))
    grp = _pos_group(player.get("position"))
    return {"importance": round(imp, 3), "is_key": bool(comps["m"] >= 0.6 or comps["c"] >= 0.20),
            "defensive_share": round(comps["m"], 3) if grp in ("DEF", "GK") else 0.0,
            "minutes_share": round(comps["m"], 3), "ga_share": round(comps["c"], 3),
            "group": grp, "known": True, "components": sorted(comps),
            "certainty": u}


def band(tee: float) -> str:
    return "Etkisiz" if tee < 10 else "Hissedilir" if tee < 25 else "Ciddi" if tee < 45 else "Ağır"


def team_absence_impact(missing: list[dict]) -> dict:
    prod = 1.0
    groups: dict[str, int] = {}
    att = dfn = 0.0
    for m in missing:
        i = float(m.get("importance") or 0)
        prod *= (1 - ALPHA * i)
        g = m.get("group") or "UNK"
        groups[g] = groups.get(g, 0) + 1
        a_sh, d_sh = SHARES.get(g, SHARES["UNK"])
        att += i * a_sh
        dfn += i * d_sh
    overlap = any(n >= 2 for g, n in groups.items() if g != "UNK")
    tee = min(100.0, 100 * (1 - prod) * (1 + BETA * (1 if overlap else 0)))
    return {"tee": round(tee, 1), "band": band(tee), "overlap": overlap,
            "attack_mult": round(max(0.70, 1 - GAMMA * att), 4),
            "defence_mult": round(min(1.30, 1 + GAMMA * dfn), 4)}


def injury_adjustment(missing_home: list[dict], missing_away: list[dict]) -> dict:
    h, a = team_absence_impact(missing_home), team_absence_impact(missing_away)
    return {
        "home_mult": h["attack_mult"] * a["defence_mult"],
        "away_mult": a["attack_mult"] * h["defence_mult"],
        "home_tee": h["tee"], "away_tee": a["tee"], "home_band": h["band"], "away_band": a["band"],
        "home_attack_mult": h["attack_mult"], "away_attack_mult": a["attack_mult"],
        "home_defence_mult": h["defence_mult"], "away_defence_mult": a["defence_mult"],
    }
