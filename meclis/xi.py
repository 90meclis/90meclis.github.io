"""Meclis tahmini ilk 11 — resmî ilk 11'i (maçtan ~1 saat önce) BEKLEMEDEN, her takım için kendi tahminimiz.

Oyuncu başlama puanı (mevcut bileşenlerin ağırlıklı ortalaması; olmayan bileşen formülden çıkar):
  0.45 · son resmî ilk 11'lerde yer alma payı (takımın son ≤5 maçı)
  0.35 · sezon ilk 11 payı (oyuncunun ilk 11 sayısı / takımdaki en yüksek)
  0.20 · dış kaynak tahmini (BSD tahmini ilk 11'deyse ai_score, değilse 0)
Uygunluk: kesin yok / cezalı → dışarıda; şüpheli → puan × 0.5; maç günü kararı → × 0.7.
Diziliş: 1 kaleci + 10 oyuncu (en az 3 defans, 3 orta saha, 1 forvet; kalan yerler puana göre).

Modele etkisi: "en güçlü 11" (uygunluk yok sayılarak aynı yöntemle) ile tahmini 11 karşılaştırılır.
Eksik Etkisi'ne giren oyuncular = sakat/cezalı/şüpheli listesindeki herkes + en güçlü 11'de olup tahmini 11'de
olmayan (rotasyon) oyuncular (kesinlik 0.5). Resmî ilk 11 kilitten önce gelirse yalnızca saklanır/gösterilir.
"""
from __future__ import annotations

from .model.injuries import _key, _pos_group, certainty, find_player, has_stats, player_importance

W_RECENT, W_SEASON, W_EXT = 0.45, 0.35, 0.20
MIN_GROUP = {"DEF": 3, "MID": 3, "ATT": 1}


def _status_of(name: str, unavailable: list[dict]) -> dict | None:
    k = _key(name)
    for u in unavailable:
        if _key(u.get("player_name") or u.get("name")) == k:
            return u
    hit = find_player(name, [{"name": u.get("player_name") or u.get("name"), "_u": u} for u in unavailable])
    return hit["_u"] if hit else None


def _scores(players: list[dict], recent_xis: list[list[str]], ext_pred: list[dict] | None) -> tuple[dict, list[str]]:
    used = []
    max_lu = max(((p.get("lineups") or 0) for p in players if has_stats(p)), default=0)
    ext_map = {}
    if ext_pred:
        used.append("dış tahmin (BSD)")
        for e in ext_pred:
            ext_map[_key(e.get("name"))] = float(e.get("ai_score") if e.get("ai_score") is not None else 0.7)
    rec_keys = [{_key(n) for n in xi} for xi in recent_xis if xi]
    if rec_keys:
        used.append(f"son {len(rec_keys)} resmî ilk 11")
    if max_lu:
        used.append("sezon ilk 11 payı")
    out = {}
    for p in players:
        k = _key(p.get("name"))
        parts = []
        if rec_keys:
            share = sum(1 for s in rec_keys if k in s or find_player(p["name"], [{"name": n} for n in s]))
            parts.append((W_RECENT, share / len(rec_keys)))
        if max_lu and p.get("lineups") is not None:
            parts.append((W_SEASON, (p.get("lineups") or 0) / max_lu))
        if ext_map:
            v = ext_map.get(k)
            if v is None:
                hit = find_player(p["name"], [{"name": n} for n in ext_map])
                v = ext_map.get(_key(hit["name"])) if hit else 0.0
            parts.append((W_EXT, v))
        out[p["name"]] = (sum(w * v for w, v in parts) / sum(w for w, _ in parts)) if parts else None
    return out, used


def _pick_eleven(cands: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    cands = sorted(cands, key=lambda x: -x[1])
    gk = [c for c in cands if _pos_group(c[0].get("position")) == "GK"]
    xi = gk[:1]
    rest = [c for c in cands if c not in xi and _pos_group(c[0].get("position")) != "GK"]
    for grp, n in MIN_GROUP.items():
        xi += [c for c in rest if _pos_group(c[0].get("position")) == grp and c not in xi][:n]
    for c in rest:
        if len(xi) >= 11:
            break
        if c not in xi:
            xi.append(c)
    return xi[:11]


def predict_xi(players: list[dict], unavailable: list[dict] | None = None, recent_xis: list[list[str]] | None = None,
               ext_pred: list[dict] | None = None) -> dict:
    """Döner: {'players': [{name, position, score, note}], 'basis': [...], 'effect_rows': [...] | None}."""
    unavailable = unavailable or []
    players = [p for p in players or [] if p.get("name")]
    if len(players) < 11:
        return {"players": [], "basis": ["kadro verisi yetersiz"], "effect_rows": None}
    sc, used = _scores(players, recent_xis or [], ext_pred)
    if not used:
        return {"players": [], "basis": ["başlama verisi yok (son ilk 11 / sezon istatistiği / dış tahmin)"],
                "effect_rows": None}
    base = [(p, sc.get(p["name"]) or 0.0) for p in players]
    best = _pick_eleven(base)
    avail = []
    for p, s in base:
        st = _status_of(p["name"], unavailable)
        u = certainty(st.get("injury_status") or st.get("kind")) if st else 0.0
        if st and u >= 1.0:
            continue
        mult = 1.0 if not st else (0.5 if u == 0.5 else 0.7)
        avail.append((p, s * mult))
    pred = _pick_eleven(avail)
    pred_names = {p["name"] for p, _ in pred}
    effect = []
    seen = set()
    for u in unavailable:  # sakat/cezalı/şüpheli listesindeki herkes
        nm = u.get("player_name") or u.get("name")
        pl = find_player(nm, players)
        imp = player_importance(pl, players, u.get("injury_status") or u.get("kind"))
        imp.update(name=nm, reason=u.get("reason"), kind=u.get("injury_status") or u.get("kind"))
        effect.append(imp)
        seen.add(_key(pl["name"] if pl else nm))
    for p, _s in best:  # en güçlü 11'de olup tahmini 11'de olmayan (rotasyon)
        if p["name"] in pred_names or _key(p["name"]) in seen:
            continue
        imp = player_importance(p, players, "rotasyon")
        imp.update(name=p["name"], reason="tahmini 11'de değil (rotasyon/form)", kind="rotasyon")
        effect.append(imp)
    return {"players": [{"name": p["name"], "position": p.get("position"), "score": round(s, 3),
                         "note": "şüpheli" if _status_of(p["name"], unavailable) else None} for p, s in pred],
            "basis": used, "effect_rows": effect}


GROUP_ORDER = {"GK": 0, "DEF": 1, "MID": 2, "ATT": 3}


def assign_grid(players: list[dict], formation: str | None) -> tuple[str | None, list[dict]]:
    """Diziliş + oyuncu sırası → API-Football tarzı 'satır:sütun' ızgarası (1:1 kaleci, 2:x savunma…).
    Oyuncular mevki grubuna göre (K, D, OS, F) sıralanır, dizilişin satırlarına sırayla yerleştirilir.
    Diziliş bilinmiyorsa mevki sayılarından türetilir (ör. 4 D, 3 OS, 3 F → '4-3-3'); 'formation_source' bunu söyler."""
    if not players:
        return formation, players
    ps = sorted(enumerate(players), key=lambda ip: (GROUP_ORDER.get(_pos_group(ip[1].get("position")), 2), ip[0]))
    ps = [p for _, p in ps]
    rows = None
    if formation:
        try:
            rows = [int(x) for x in str(formation).split("-") if x.strip()]
        except ValueError:
            rows = None
    if not rows or sum(rows) != len(ps) - 1:
        cnt = {}
        for p in ps[1:]:
            g = _pos_group(p.get("position"))
            cnt[g] = cnt.get(g, 0) + 1
        rows = [cnt.get(g, 0) for g in ("DEF", "MID", "ATT") if cnt.get(g)]
        formation = "-".join(str(r) for r in rows) if rows else None
    out, i = [], 0
    for r_idx, n in enumerate([1] + rows):
        for c in range(n):
            if i < len(ps):
                out.append(dict(ps[i], grid=f"{r_idx + 1}:{c + 1}"))
                i += 1
    out += [dict(p, grid=None) for p in ps[i:]]
    return formation, out


def xi_uncertainty(xi_side: dict) -> float:
    """İlk 11'deki kilit oyuncuların (en yüksek 5 olasılık) oynama belirsizliği: 1 − ortalama olasılık, 'şüpheli'
    notu ek ceza. 0 = kesin, 1 = tamamen belirsiz."""
    ps = (xi_side or {}).get("players") or []
    if not ps:
        return 0.5
    top = sorted(ps, key=lambda p: -(p.get("score") or 0))[:5]
    u = 1 - sum(min(1.0, p.get("score") or 0) for p in top) / len(top)
    u += 0.1 * sum(1 for p in ps if p.get("note") == "şüpheli")
    return round(min(1.0, max(0.0, u)), 3)
