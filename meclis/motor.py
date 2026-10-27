"""İsabet motoru — öğrenen kalibrasyon + seçim kuralının dürüst geri testi (otomatik, gece işi).

1) Yürüyen pencere (lig başına haftalık Dixon-Coles; yalnızca o haftadan ÖNCEKİ maçlar) ile bu sezon biten her maçın
   gol pazarları tahmin edilir: 1X2, çifte şans, gol A/Ü 1.5/2.5/3.5, KG. Karar anı oranı (ön maç oranı) marjsızlaştırılır.
2) Pazar grubu başına harman ağırlığı w (p = w·model + (1−w)·piyasa) log-loss'u en aza indirecek şekilde ve
   ardından izotonik kalibrasyon (PAV) öğrenilir. Lig başına ağırlık yalnızca ligde yeterli örnek varsa.
3) KORUMA: yeni parametreler, zaman sırasıyla ayrılmış SON %30'luk dilimde mevcut parametrelerden daha iyi
   (log-loss) değilse benimsenmez — öğrenme döngüsü modeli kötüleştiremez.
4) Seçim kuralı (canlıyla aynı): maç başına oranı ≥ 1.50, model–piyasa farkı ≤ 20 puan olan seçimler içinde
   kalibre olasılığı en yüksek olan; olasılık ≥ %50. İsabet, güven bandı ve pazar başına; çapraz uydurma (iki yarı:
   biri öğrenir, öteki ölçülür) → bantlardaki oranlar örneklem dışıdır.
Sonuç analyses tablosunda 'meclis:motor' satırına yazılır (Güven Panosu ve canlı seçim buradan okur).
Not: geri test saf Dixon-Coles'tur (canlı modeldeki Elo, eksik oyuncu, ilk 11 etkisi yok) → canlı modelin
temkinli bir ölçüsüdür. Çifte şans oranı geçmişte ayrı tutulmadığı için 1X2 oranlarından türetilir (marj korunur).
"""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

from .analysis import season_start
from .backtest import _novig, _odds
from .model.goals import fit_dixon_coles, score_matrix
from .timeutil import now_utc, parse_dt, to_iso

MOTOR_ID = "meclis:motor"
GROUPS = ("1X2", "DC", "OU_GOALS_1.5", "OU_GOALS_2.5", "OU_GOALS_3.5", "BTTS")
BANDS = ((0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 1.01))
MIN_ODDS, MAX_GAP, MIN_P = 1.50, 0.20, 0.50
W_MIN = 0.20
DEEP_N = 300  # canlı yayına girebilecek pazar grubu için en az geri test örneği


def band_of(p: float) -> str | None:
    for lo, hi in BANDS:
        if lo <= p < hi:
            return f"%{lo * 100:.0f}–{min(hi, 1.0) * 100:.0f}" if hi <= 1 else f"%{lo * 100:.0f}+"
    return None


# ----------------------------------------------------------------------------- veri
def collect(store, min_train: int = 40, ridge: float = 10.0) -> list[dict]:
    """Maç başına: {league, t, sels: [{g, sel, pm, pk, odds, y}]} (örneklem dışı model olasılığı)."""
    s0 = season_start()
    ms = store.select("matches", [("status", "eq", "bitti"), ("kickoff_at", "gte", to_iso(s0))], order="kickoff_at")
    by_lg: dict[str, list] = {}
    for m in ms:
        if m.get("home_goals") is not None and (m.get("odds") or {}):
            by_lg.setdefault(m["league"], []).append(m)
    allm = {}
    for m in ms:
        if m.get("home_goals") is not None:
            allm.setdefault(m["league"], []).append(m)
    out = []
    for lg, lst_all in allm.items():
        lst_all.sort(key=lambda m: m["kickoff_at"])
        if len(lst_all) < min_train + 10 or lg not in by_lg:
            continue
        t0 = parse_dt(lst_all[min_train]["kickoff_at"])
        end = parse_dt(lst_all[-1]["kickoff_at"]) + timedelta(days=1)
        cut = t0
        while cut < end:
            nxt = cut + timedelta(days=7)
            train = [m for m in lst_all if parse_dt(m["kickoff_at"]) < cut]
            test = [m for m in by_lg[lg] if cut <= parse_dt(m["kickoff_at"]) < nxt]
            cut = nxt
            if len(train) < min_train or not test:
                continue
            rows = [{"home": m["home_team_id"], "away": m["away_team_id"], "hg": m["home_goals"], "ag": m["away_goals"],
                     "days_ago": (cut - parse_dt(m["kickoff_at"])).total_seconds() / 86400} for m in train]
            try:
                gm = fit_dixon_coles(rows, ridge=ridge)
            except Exception:
                continue
            for m in test:
                h, a = m["home_team_id"], m["away_team_id"]
                if not (gm.has_team(h, 3) and gm.has_team(a, 3)):
                    continue
                rec = _match_rows(m, gm)
                if rec:
                    out.append({"league": lg, "t": m["kickoff_at"], "id": m["id"], "sels": rec})
    out.sort(key=lambda r: r["t"])
    return out


def _match_rows(m: dict, gm) -> list[dict]:
    lh, la = gm.lambdas(m["home_team_id"], m["away_team_id"])
    sm = score_matrix(lh, la, gm.rho)
    g = np.arange(sm.shape[0])
    d = g[:, None] - g[None, :]
    tot = g[:, None] + g[None, :]
    hg, ag = m["home_goals"], m["away_goals"]
    p1, px, p2 = float(sm[d > 0].sum()), float(sm[d == 0].sum()), float(sm[d < 0].sum())
    out = []
    o = _odds(m, "1X2", "open")
    nv = _novig(o, ("1", "X", "2")) if o else None
    if nv:
        res = "1" if hg > ag else ("X" if hg == ag else "2")
        oo = {k: float(o[k]) for k in ("1", "X", "2")}
        for sel, pm, pk in (("1", p1, nv[0]), ("X", px, nv[1]), ("2", p2, nv[2])):
            out.append({"g": "1X2", "sel": sel, "pm": pm, "pk": pk, "odds": oo[sel], "y": int(res == sel)})
        for sel, a_, b_ in (("1X", "1", "X"), ("12", "1", "2"), ("X2", "X", "2")):
            pm = {"1": p1, "X": px, "2": p2}
            pkk = {"1": nv[0], "X": nv[1], "2": nv[2]}
            out.append({"g": "DC", "sel": sel, "pm": pm[a_] + pm[b_], "pk": pkk[a_] + pkk[b_],
                        "odds": round(1 / (1 / oo[a_] + 1 / oo[b_]), 3), "y": int(res in (a_, b_))})
    for line in (1.5, 2.5, 3.5):
        o = _odds(m, f"OU_GOALS_{line:g}", "open")
        if not o:
            continue
        ks = next((k for k in (("ÜST", "ALT"), ("over", "under"), ("Üst", "Alt")) if k[0] in o), None)
        nv = _novig(o, ks) if ks else None
        if not nv:
            continue
        pov = float(sm[tot > line].sum())
        over = hg + ag > line
        out.append({"g": f"OU_GOALS_{line:g}", "sel": "ÜST", "pm": pov, "pk": nv[0], "odds": float(o[ks[0]]), "y": int(over)})
        out.append({"g": f"OU_GOALS_{line:g}", "sel": "ALT", "pm": 1 - pov, "pk": nv[1], "odds": float(o[ks[1]]), "y": int(not over)})
    o = _odds(m, "BTTS", "open")
    if o:
        ks = next((k for k in (("VAR", "YOK"), ("yes", "no"), ("Var", "Yok")) if k[0] in o), None)
        nv = _novig(o, ks) if ks else None
        if nv:
            pb = float(sm[1:, 1:].sum())
            yb = hg > 0 and ag > 0
            out.append({"g": "BTTS", "sel": "VAR", "pm": pb, "pk": nv[0], "odds": float(o[ks[0]]), "y": int(yb)})
            out.append({"g": "BTTS", "sel": "YOK", "pm": 1 - pb, "pk": nv[1], "odds": float(o[ks[1]]), "y": int(not yb)})
    return out


# ----------------------------------------------------------------------------- öğrenme
def _ll(p: float, y: int) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def pav(xs: list[float], ys: list[int], bins: int = 20) -> list[list[float]]:
    """İzotonik regresyon (havuzlu bitişik ihlal): [[x, y], ...] artan; önce eşit sayılı kutulara özetlenir."""
    if len(xs) < 50:
        return []
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    k = max(1, len(order) // bins)
    blocks = []
    for i in range(0, len(order), k):
        idx = order[i:i + k]
        blocks.append([sum(xs[j] for j in idx) / len(idx), sum(ys[j] for j in idx) / len(idx), len(idx)])
    st: list[list[float]] = []
    for b in blocks:
        st.append(b)
        while len(st) > 1 and st[-2][1] > st[-1][1]:
            x2, y2, n2 = st.pop()
            x1, y1, n1 = st.pop()
            n = n1 + n2
            st.append([(x1 * n1 + x2 * n2) / n, (y1 * n1 + y2 * n2) / n, n])
    return [[round(x, 4), round(y, 4)] for x, y, _ in st]


def iso_apply(p: float, iso: list | None) -> float:
    if not iso:
        return p
    xs = [a for a, _ in iso]
    if p <= xs[0]:
        return float(iso[0][1]) if p >= xs[0] - 0.05 else p * iso[0][1] / max(xs[0], 1e-6)
    if p >= xs[-1]:
        return float(iso[-1][1])
    for (x1, y1), (x2, y2) in zip(iso, iso[1:]):
        if x1 <= p <= x2:
            return y1 + (y2 - y1) * (p - x1) / max(x2 - x1, 1e-9)
    return p


def _blend(r: dict, prm: dict) -> float:
    pc = prm.get("w", 0.35) * r["pm"] + (1 - prm.get("w", 0.35)) * r["pk"]
    return min(0.99, max(0.01, iso_apply(pc, prm.get("iso"))))


def fit_group(rows: list[dict]) -> dict:
    """rows: aynı pazar grubunun seçim satırları. En iyi w (log-loss) + izotonik harita."""
    if len(rows) < 100:
        return {}
    best = min((sum(_ll(w * r["pm"] + (1 - w) * r["pk"], r["y"]) for r in rows), w)
               for w in [i / 20 for i in range(4, 21)])  # w ≥ 0.20: canlı modelin geri testte ölçülemeyen
    # girdileri (Elo, eksik oyuncu, ilk 11) için asgari söz hakkı; büyük ayrışmalar MAX_GAP ile zaten elenir
    w = best[1]
    xs = [w * r["pm"] + (1 - w) * r["pk"] for r in rows]
    iso = pav(xs, [r["y"] for r in rows])
    return {"w": w, "iso": iso, "n": len(rows)}


def _flat(matches: list[dict], g: str) -> list[dict]:
    return [s for mt in matches for s in mt["sels"] if s["g"] == g]


def learn(matches: list[dict], current: dict | None) -> tuple[dict, list[dict]]:
    """Grup başına yeni parametre. Doğrulama dilimi, mevcut parametrelerin uydurulduğu tarihten SONRAKİ maçlardır
    (ilk çalışmada son %30): yeni parametre bu dilimde mevcuttan daha iyi (log-loss) değilse eskisi kalır."""
    current = current or {}
    adopted, log = {}, []
    last_t = matches[-1]["t"] if matches else None
    for g in GROUPS:
        old = current.get(g) or {}
        since = old.get("fit_until")
        if since:
            tr = [m for m in matches if m["t"] <= since]
            va = [m for m in matches if m["t"] > since]
        else:
            cut = int(len(matches) * 0.7)
            tr, va = matches[:cut], matches[cut:]
        rtr, rva = _flat(tr, g), _flat(va, g)
        base = old if old.get("w") is not None else {"w": 0.35}
        if since and len(rva) < 80:
            adopted[g] = old
            log.append({"grup": g, "durum": "yeni veri az — mevcut korundu", "n_yeni": len(rva)})
            continue
        new = fit_group(rtr)
        if not new or len(rva) < 40:
            adopted[g] = old
            log.append({"grup": g, "durum": "yetersiz örnek", "n_ogren": len(rtr), "n_dogrula": len(rva)})
            continue
        ll_new = sum(_ll(_blend(r, new), r["y"]) for r in rva) / len(rva)
        ll_old = sum(_ll(_blend(r, base), r["y"]) for r in rva) / len(rva)
        ll_mkt = sum(_ll(r["pk"], r["y"]) for r in rva) / len(rva)
        take = ll_new <= ll_old + 1e-9
        if take:
            final = fit_group(rtr + rva) or new  # benimsenirse bütün veriyle yeniden uydurulur
            final["fit_until"] = last_t
        else:
            final = dict(base, fit_until=last_t)  # eskisi korunur; bir sonraki doğrulama yeni maçlarla yapılır
        adopted[g] = final
        log.append({"grup": g, "durum": "benimsendi" if take else "mevcut korundu (yeni daha kötü)",
                    "ll_yeni": round(ll_new, 4), "ll_mevcut": round(ll_old, 4), "ll_piyasa": round(ll_mkt, 4),
                    "w": final.get("w"), "n_ogren": len(rtr), "n_dogrula": len(rva)})
    return adopted, log


# ----------------------------------------------------------------------------- seçim kuralının geri testi
def select(match: dict, params: dict, deep: set | None = None) -> dict | None:
    best = None
    for s in match["sels"]:
        if s["odds"] < MIN_ODDS or s["odds"] > 5.0 or abs(s["pm"] - s["pk"]) > MAX_GAP:
            continue
        if deep is not None and s["g"] not in deep:
            continue
        pc = _blend(s, params.get(s["g"]) or {"w": 0.35})
        if pc >= MIN_P and (best is None or pc > best["pc"]):
            best = dict(s, pc=pc)
    return best


def selection_backtest(matches: list[dict]) -> dict:
    """Çapraz uydurma: A yarısıyla öğren → B'de seç/ölç, B ile öğren → A'da ölç."""
    half = len(matches) // 2
    parts = [(matches[:half], matches[half:]), (matches[half:], matches[:half])]
    picks = []
    for fit_on, test_on in parts:
        prm = {g: fit_group(_flat(fit_on, g)) for g in GROUPS}
        for mt in test_on:
            b = select(mt, prm)
            if b:
                picks.append(b)

    def agg(rows):
        n = len(rows)
        if not n:
            return {"n": 0}
        hit = sum(r["y"] for r in rows)
        return {"n": n, "isabet": round(hit / n, 4), "ort_olasilik": round(sum(r["pc"] for r in rows) / n, 4),
                "ort_oran": round(sum(r["odds"] for r in rows) / n, 3),
                "roi": round(sum((r["odds"] - 1) if r["y"] else -1 for r in rows) / n, 4)}
    bands = []
    for lo, hi in BANDS:
        rs = [p for p in picks if lo <= p["pc"] < hi]
        bands.append({"bant": band_of(lo), "alt": lo, "ust": min(hi, 1.0), **agg(rs)})
    by_g = [{"pazar": g, **agg([p for p in picks if p["g"] == g])} for g in GROUPS]
    return {"toplam": agg(picks), "bantlar": bands, "pazarlar": by_g, "mac": len(matches)}


def run(store, log: list | None = None) -> dict:
    """Gece işi: veri → öğren (korumalı) → seçim geri testi → 'meclis:motor' satırı."""
    log = log if log is not None else []
    prev = latest(store) or {}
    matches = collect(store)
    if len(matches) < 200:
        log.append(f"ℹ️ motor: yeterli geri test maçı yok ({len(matches)})")
        return prev
    params, learn_log = learn(matches, prev.get("params"))
    bt = selection_backtest(matches)
    n_by = {g: len(_flat(matches, g)) for g in GROUPS}
    # Yayına girebilecek pazar: geri testte yeterli örnek VE seçim kuralı o pazarda tuttuğunu söylediği kadar tutuyor
    # (örneklem dışı isabet ≥ ortalama olasılık − 5 puan, en az 40 seçim). Diğerleri Ortak'ta bilgi olarak kalır.
    sel_by = {x["pazar"]: x for x in bt["pazarlar"]}
    deep = sorted(g for g in GROUPS if n_by[g] >= DEEP_N and (sel_by.get(g) or {}).get("n", 0) >= 40
                  and sel_by[g]["isabet"] >= sel_by[g]["ort_olasilik"] - 0.05)
    hist = (prev.get("gecmis") or [])[-29:] + [{"tarih": now_utc().date().isoformat(), "mac": len(matches),
                                                "benimsenen": [x["grup"] for x in learn_log if x["durum"] == "benimsendi"],
                                                "isabet": bt["toplam"].get("isabet"), "n": bt["toplam"].get("n")}]
    out = {"params": params, "ogrenme": learn_log, "geritest": bt, "derin_pazarlar": deep, "ornek": n_by,
           "gecmis": hist, "guncellendi": to_iso(now_utc()),
           "yontem": "yürüyen pencere Dixon-Coles + marjsız ön maç oranı; w ve izotonik kalibrasyon log-loss ile; "
                     "son %30 doğrulamada iyileşmeyen parametre benimsenmez; bantlar çapraz uydurmayla örneklem dışı"}
    ts = to_iso(now_utc())
    store.upsert("analyses", [{"match_id": MOTOR_ID, "created_at": ts, "model_version": "meclis-motor-1", "payload": out}])
    try:
        store.prune("analyses", [("match_id", "eq", MOTOR_ID), ("created_at", "lt", ts)])
    except Exception:
        pass
    t = bt["toplam"]
    log.append(f"✅ motor: {len(matches)} maç; seçim geri testi n={t.get('n')} isabet %{(t.get('isabet') or 0) * 100:.1f} "
               f"ROI {(t.get('roi') or 0) * 100:+.1f}%; derin pazarlar: {', '.join(deep)}; "
               + "; ".join(f"{x['grup']}: {x['durum']}" for x in learn_log))
    return out


def latest(store) -> dict | None:
    try:
        rows = store.select("analyses", [("match_id", "eq", MOTOR_ID)], order="created_at", desc=True, limit=1)
        return rows[0]["payload"] if rows else None
    except Exception:
        return None
