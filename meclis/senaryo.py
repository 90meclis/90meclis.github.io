"""Senaryo motoru — 'maçı kafanda oynat'.

Her maç için modelin gol beklentisinden (λ, İY payı) 20.000 maçlık dakika dakika benzetim yapılır. Sonuç uzayı
BİRBİRİNİ DIŞLAYAN 5 ana senaryoya bölünür (olasılıklar toplamı 1): ev rahat (2+ fark), ev dar (1 fark),
beraberlik, deplasman dar, deplasman rahat. Ek olarak ÖRTÜŞEN senaryolar (ör. 'Kaos: erken gol') ayrıca etiketlenir.

Her senaryo bir film senaryosu gibi perdelere ayrılır (0–15′, 15–45′, devre arası, 45–70′, 70–90′+). Metindeki
her sayı bu maçın verisinden gelir (benzetim, takımın bu sezonki iç/dış saha ortalamaları, korner/kart beklentisi,
eksikler, hakem, hava, dinlenme). Veri yoksa cümle kurulmaz; uydurma istatistik yok.

Şema (analyses.payload->'senaryolar'):
{surum, simulasyon, ortusmeyen_toplam, liste:[{id, baslik, tur:'ana'|'ortusen', olasilik, final_skor,
  skorlar:[{skor,p}], perde:[{dakika,baslik,metin}], kirilma_ani:{dakika,olay,metin},
  pazarlar:{'1X2':{1,X,2}, 'Gol 1.5/2.5/3.5 Üst':p, 'KG Var':p, 'İY 0.5 Üst':p, 'İY 1.5 Üst':p,
            'Korner'|'Kart'|'İsabetli şut': {beklenen, ev, dep, bagimsiz:true}},
  canli_sinyaller:[{sinyal, olasilik_once, olasilik_sonra, metin}],
  meclis_secimi:{etiket, kazanma_olasiligi, durum:'kazanır'|'kaybeder'|'belirsiz'|'senaryodan bağımsız'},
  dayanaklar:[metin]}], eksik_etkisi:{...}}
"""
from __future__ import annotations

import numpy as np

from .markets import pick_label

N_SIM = 20000


def _pct(p) -> str:
    return f"%{p * 100:.0f}" if p is not None else "—"


def _num(x, d=1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def simulate(lh: float, la: float, ht_ratio: float = 0.44, n: int = N_SIM, seed: int = 90):
    """Dakikalı gol benzetimi. Döner: (hg, ag, gol dakikaları listesi [(dk, taraf)])."""
    rng = np.random.default_rng(seed)
    hg = rng.poisson(lh, n)
    ag = rng.poisson(la, n)
    mx = int(max(hg.max(initial=0), ag.max(initial=0)))

    def minutes(k):
        first = rng.random((n, k)) < ht_ratio
        m = np.where(first, rng.integers(1, 46, (n, k)), rng.integers(46, 91, (n, k)))
        return m

    hm = minutes(max(mx, 1)).astype(float)
    am = minutes(max(mx, 1)).astype(float)
    idx = np.arange(max(mx, 1))
    hm[idx[None, :] >= hg[:, None]] = np.inf
    am[idx[None, :] >= ag[:, None]] = np.inf
    return hg, ag, hm, am


def _pick_wins(pick: dict, hg, ag, ht_h, ht_a):
    mk, sel, ln = pick.get("market"), pick.get("selection"), pick.get("line")
    tot = hg + ag
    if mk == "1X2":
        return {"1": hg > ag, "X": hg == ag, "2": hg < ag}.get(sel)
    if mk == "DC":
        return {"1X": hg >= ag, "X2": hg <= ag, "12": hg != ag}.get(sel)
    if mk == "OU_GOALS" and ln is not None:
        return tot > ln if sel == "ÜST" else tot < ln
    if mk == "BTTS":
        return (hg > 0) & (ag > 0) if sel == "VAR" else ~((hg > 0) & (ag > 0))
    if mk == "HT_OU_GOALS" and ln is not None:
        return (ht_h + ht_a > ln) if sel == "ÜST" else (ht_h + ht_a < ln)
    if mk == "AH" and ln is not None:
        d = (hg - ag) + ln if sel == "1" else (ag - hg) + ln
        return d > 0
    if mk in ("TEAM_GOALS_HOME", "TEAM_GOALS_AWAY") and ln is not None:
        g = hg if mk == "TEAM_GOALS_HOME" else ag
        return g > ln if sel == "ÜST" else g < ln
    return None


def _top_scores(hg, ag, mask, k=3):
    if not mask.any():
        return []
    pairs = hg[mask] * 100 + ag[mask]
    vals, cnt = np.unique(pairs, return_counts=True)
    order = np.argsort(-cnt)[:k]
    tot = mask.sum()
    return [{"skor": f"{vals[i] // 100}-{vals[i] % 100}", "p": round(float(cnt[i] / tot), 3)} for i in order]


def build_film(payload: dict, match: dict, dossier: dict | None = None) -> dict:
    dossier = dossier or {}
    home, away = payload["home"], payload["away"]
    lam = payload.get("lambdas") or {}
    lh, la = float(lam.get("home") or 1.3), float(lam.get("away") or 1.1)
    hr = float(lam.get("ht_ratio") or 0.44)
    hg, ag, hm, am = simulate(lh, la, hr)
    ht_h = (hm <= 45).sum(1)
    ht_a = (am <= 45).sum(1)
    first_h = hm.min(1)
    first_a = am.min(1)
    first = np.minimum(first_h, first_a)
    n = len(hg)
    diff = hg - ag
    ci = payload.get("count_info") or {}
    xi = payload.get("predicted_xi") or {}
    inj = payload.get("injury_effect") or {}
    wx = payload.get("weather") or {}
    ref = match.get("referee")
    venue = match.get("venue")
    split = dossier.get("venue_split") or {}
    rest = dossier.get("rest") or {}
    refst = dossier.get("referee") or {}
    coach = dossier.get("coach") or {}
    best = payload.get("best_pick")

    def att(side, k=2):
        ps = (xi.get(side) or {}).get("players") or []
        a = [p for p in ps if str(p.get("position") or "").upper()[:1] in ("F", "A")] or ps[-3:]
        return [p["name"] for p in sorted(a, key=lambda p: -(p.get("score") or 0))[:k]]

    def mid(side, k=1):
        ps = (xi.get(side) or {}).get("players") or []
        a = [p for p in ps if str(p.get("position") or "").upper()[:1] == "M"]
        return [p["name"] for p in sorted(a, key=lambda p: -(p.get("score") or 0))[:k]]

    def missing(side):
        rows = inj.get(f"{side}_missing") or []
        rows = sorted(rows, key=lambda r: -(r.get("importance") or 0))
        return [r for r in rows if (r.get("importance") or 0) >= 0.1][:2]

    def split_txt(side):
        s = split.get(side) or {}
        if not s.get("n"):
            return None
        where = "iç sahada" if side == "home" else "deplasmanda"
        bits = [f"{where} {s['n']} maçta maç başı {_num(s['gf'])} attı, {_num(s['ga'])} yedi"]
        if s.get("cf") is not None:
            bits.append(f"{_num(s['cf'])} korner kullandı")
        return f"{home if side == 'home' else away} " + ", ".join(bits)

    def cnt(stat):
        c = ci.get(stat)
        return (c["home"], c["away"], c["total"]) if c else None

    corners, cards, sot = cnt("corners"), cnt("cards"), cnt("shots_on_target")
    names = {"home": home, "away": away}

    # ---------------- ana senaryolar (birbirini dışlar)
    defs = [("ev_rahat", diff >= 2, f"{home} Fırtınası"),
            ("ev_dar", diff == 1, f"{home}: Tek Golün Ağırlığı"),
            ("beraberlik", diff == 0, "Kilit: Kimse Kaybetmek İstemiyor"),
            ("dep_dar", diff == -1, f"{away} Sessizce Gelir"),
            ("dep_rahat", diff <= -2, f"{away} Gecesi")]
    out = []
    for sid, mask, title in defs:
        p = float(mask.mean())
        if p < 0.03:
            continue
        out.append(_scenario(sid, title, "ana", mask, p, hg, ag, ht_h, ht_a, first, first_h, first_a, n, names,
                             best, corners, cards, sot, att, mid, missing, split_txt, rest, refst, ref, venue, wx,
                             coach, payload))
    # ---------------- örtüşen: kaos (ilk 15 dakikada gol)
    early = first <= 15
    if early.mean() >= 0.05:
        out.append(_scenario("kaos", "Kaos Senaryosu: Erken Gol Her Şeyi Değiştirir", "ortusen", early,
                             float(early.mean()), hg, ag, ht_h, ht_a, first, first_h, first_a, n, names, best, corners,
                             cards, sot, att, mid, missing, split_txt, rest, refst, ref, venue, wx, coach, payload))
    # örtüşen: geç dram (70′ sonrası belirleyici gol)
    late = (np.minimum(np.where(hm > 70, hm, np.inf).min(1), np.where(am > 70, am, np.inf).min(1)) < np.inf) & \
           (np.abs(diff) <= 1)
    if late.mean() >= 0.08:
        out.append(_scenario("yedek_kulubesi", "Yedek Kulübesi: Son 20 Dakikanın Hikâyesi", "ortusen", late,
                             float(late.mean()), hg, ag, ht_h, ht_a, first, first_h, first_a, n, names, best, corners,
                             cards, sot, att, mid, missing, split_txt, rest, refst, ref, venue, wx, coach, payload))
    # örtüşen: hakem / kart senaryosu (yalnızca hakemin bu sezonki verisi varsa)
    if refst.get("n", 0) >= 3 and cards and refst.get("kart") is not None and refst["kart"] >= cards[2] + 0.5:
        out.append({"id": "hakem", "baslik": f"Düdük Konuşur: {ref}", "tur": "ortusen", "olasilik": None,
                    "perde": [{"dakika": "0–90′", "baslik": "Hakem faktörü",
                               "metin": f"{ref} bu sezon {refst['n']} maçta maç başı {_num(refst['kart'])} kart gösterdi; "
                                        f"modelin bu maç için beklediği {_num(cards[2])}. Erken bir sarı kart, ikili "
                                        "mücadelelerde temkini artırır; kart pazarı bu hakemle yukarı esner."}],
                    "kirilma_ani": None, "final_skor": None, "pazarlar": {"Kart": {"beklenen": round(cards[2], 2),
                                                                                    "hakem_ortalama": refst["kart"],
                                                                                    "bagimsiz": True}},
                    "canli_sinyaller": [], "meclis_secimi": None, "dayanaklar": [f"hakem: {refst['n']} maç, {_num(refst['kart'])} kart/maç"]})
    main_sum = round(sum(s["olasilik"] for s in out if s["tur"] == "ana"), 3)
    return {"surum": 1, "simulasyon": n, "ortusmeyen_toplam": main_sum, "liste": out,
            "eksik_etkisi": _what_if(payload)}


def _scenario(sid, title, kind, mask, p, hg, ag, ht_h, ht_a, first, first_h, first_a, n, names, best, corners, cards,
              sot, att, mid, missing, split_txt, rest, refst, ref, venue, wx, coach, payload):
    home, away = names["home"], names["away"]
    m = mask
    k = max(1, int(m.sum()))
    scores = _top_scores(hg, ag, m)
    fs = scores[0]["skor"] if scores else None
    p_ht_lead_h = float(((ht_h > ht_a) & m).sum() / k)
    p_ht_draw = float(((ht_h == ht_a) & m).sum() / k)
    p_first_h = float(((first_h < first_a) & m).sum() / k)
    fm = first[m & np.isfinite(first)]
    med_first = int(np.median(fm)) if fm.size else None
    tot = hg + ag
    mk = {"1X2": {"1": round(float(((hg > ag) & m).sum() / k), 3), "X": round(float(((hg == ag) & m).sum() / k), 3),
                  "2": round(float(((hg < ag) & m).sum() / k), 3)},
          "Gol 1.5 Üst": round(float(((tot > 1.5) & m).sum() / k), 3),
          "Gol 2.5 Üst": round(float(((tot > 2.5) & m).sum() / k), 3),
          "Gol 3.5 Üst": round(float(((tot > 3.5) & m).sum() / k), 3),
          "KG Var": round(float(((hg > 0) & (ag > 0) & m).sum() / k), 3),
          "İY 0.5 Üst": round(float(((ht_h + ht_a > 0.5) & m).sum() / k), 3),
          "İY 1.5 Üst": round(float(((ht_h + ht_a > 1.5) & m).sum() / k), 3)}
    for lab, c in (("Korner", corners), ("Kart", cards), ("İsabetli şut", sot)):
        if c:
            mk[lab] = {"beklenen": round(c[2], 2), "ev": round(c[0], 2), "dep": round(c[1], 2), "bagimsiz": True}
    # ---- dayanaklar (bu maçın sayıları)
    basis = []
    for side in ("home", "away"):
        t = split_txt(side)
        if t:
            basis.append(t)
    lam = payload.get("lambdas") or {}
    basis.append(f"gol beklentisi {home} {_num(lam.get('home', 0), 2)} – {away} {_num(lam.get('away', 0), 2)}")
    if corners:
        basis.append(f"korner beklentisi {home} {_num(corners[0])}, {away} {_num(corners[1])}")
    if cards:
        basis.append(f"kart beklentisi toplam {_num(cards[2])}")
    for side in ("home", "away"):
        r = rest.get(side)
        if r is not None:
            basis.append(f"{names[side]} {_num(r, 0)} gün dinlenmiş")
    # ---- perdeler
    fav = "home" if (lam.get("home") or 0) >= (lam.get("away") or 0) else "away"
    leader = "home" if sid.startswith("ev") else "away" if sid.startswith("dep") else fav
    L, O = names[leader], names["away" if leader == "home" else "home"]
    a_l, a_o = att(leader), att("away" if leader == "home" else "home")
    m_l = mid(leader)
    miss_o = missing("away" if leader == "home" else "home")
    miss_l = missing(leader)
    c_l = (corners[0] if leader == "home" else corners[1]) if corners else None
    w_bits = []
    if wx.get("temperature_c") is not None:
        w_bits.append(f"{_num(wx['temperature_c'], 0)}°C")
    if wx.get("wind_kmh"):
        w_bits.append(f"rüzgâr {_num(wx['wind_kmh'], 0)} km/sa")
    if wx.get("precip_mm"):
        w_bits.append(f"yağış {_num(wx['precip_mm'])} mm")
    stage = f"{venue}" if venue else "Stat"
    open_txt = (f"{stage}{', ' + ', '.join(w_bits) if w_bits else ''}. " +
                (f"Hakem {ref}. " if ref else "") +
                f"{L} topu ilk dakikalardan sahiplenir" + (f"; {m_l[0]} oyunu kurar" if m_l else "") +
                (f", maç boyu beklenen {_num(c_l)} kornerin ilk dalgası kanatlardan gelir" if c_l else "") + ". " +
                (f"İlk golün ortanca dakikası bu senaryoda {med_first}′." if med_first else "Uzun süre gol yok."))
    mid_txt = (f"{L} ilk golü {_pct(p_first_h if leader == 'home' else 1 - p_first_h)} olasılıkla atan taraf. " +
               (f"Gol yükü {', '.join(a_l)} üzerinde (tahmini 11'in hücum hattı). " if a_l else "") +
               (f"{O} cephesinde {', '.join(r['name'] for r in miss_o)} yokluğu "
                f"(etki puanı {', '.join(_num(r.get('importance') or 0, 2) for r in miss_o)}) geçişlerin hızını düşürür. "
                if miss_o else "") +
               f"Devreye {_pct(p_ht_lead_h if leader == 'home' else float(((ht_a > ht_h) & m).sum() / k))} "
               f"olasılıkla {L} önde, {_pct(p_ht_draw)} eşitlikle girilir.")
    ht_txt = ((f"{coach.get(leader)} " if coach.get(leader) else f"{L} teknik ekibi ") +
              "skoru korumak için orta sahayı sıklaştırır; " +
              (f"{coach.get('away' if leader == 'home' else 'home')} " if coach.get('away' if leader == 'home' else 'home')
               else f"{O} teknik ekibi ") + "hücum oyuncusu sayısını artırır.")
    p_second = float((((hg - ht_h) + (ag - ht_a) > 0) & m).sum() / k)
    s2_txt = (f"İkinci yarıda en az bir gol olasılığı bu senaryoda {_pct(p_second)}. " +
              (f"{O} yanıt arar" + (f"; {', '.join(a_o)} ceza sahasına daha sık girer" if a_o else "") + ". ") +
              (f"Kart beklentisi {_num(cards[2])}; tempo düştükçe ikili mücadele sertleşir." if cards else ""))
    end_txt = (f"Son düdük: {fs}. " if fs else "") + (
        f"Bu senaryonun en sık üç skoru: {', '.join(s['skor'] + ' (' + _pct(s['p']) + ')' for s in scores)}." if scores else "")
    perde = [{"dakika": "0–15′", "baslik": "Açılış", "metin": open_txt},
             {"dakika": "15–45′", "baslik": "İlk yarının ortası", "metin": mid_txt},
             {"dakika": "Devre arası", "baslik": "Soyunma odası", "metin": ht_txt},
             {"dakika": "45–70′", "baslik": "Yeniden başlangıç", "metin": s2_txt},
             {"dakika": "70–90′+", "baslik": "Final", "metin": end_txt}]
    if miss_l:
        perde[3]["metin"] += (f" {L} için {', '.join(r['name'] for r in miss_l)} eksikliği rotasyonu daraltır.")
    turn = None
    if med_first:
        who = L if (p_first_h >= 0.5) == (leader == "home") else O
        turn = {"dakika": f"{med_first}′", "olay": "ilk gol",
                "metin": f"Maçın kırılma anı ilk gol: bu senaryoda ortanca {med_first}. dakikada ve en sık {who} atıyor."}
    # ---- canlı sinyaller: koşullu olasılıklar (benzetimden)
    sig = []
    nog20 = ~(first <= 20)
    if nog20.sum() > 100:
        sig.append({"sinyal": "İlk 20 dakikada gol yoksa", "olasilik_once": round(p, 3),
                    "olasilik_sonra": round(float((m & nog20).sum() / nog20.sum()), 3),
                    "metin": f"bu senaryonun olasılığı {_pct(p)} → {_pct(float((m & nog20).sum() / nog20.sum()))}"})
    for side, fsd, nm in (("home", first_h < first_a, home), ("away", first_a < first_h, away)):
        cond = fsd & (first <= 30)
        if cond.sum() > 100:
            q = float((m & cond).sum() / cond.sum())
            sig.append({"sinyal": f"İlk 30 dakikada golü {nm} atarsa", "olasilik_once": round(p, 3),
                        "olasilik_sonra": round(q, 3), "metin": f"bu senaryonun olasılığı {_pct(p)} → {_pct(q)}"})
    # ---- Meclis seçimi bu senaryoda
    ms = None
    if best:
        w = _pick_wins(best, hg, ag, ht_h, ht_a)
        lab = pick_label(best["market"], best["selection"], best.get("line"), home, away)
        if w is None:
            ms = {"etiket": lab, "kazanma_olasiligi": best.get("probability"), "durum": "senaryodan bağımsız"}
        else:
            q = float((w & m).sum() / k)
            ms = {"etiket": lab, "kazanma_olasiligi": round(q, 3),
                  "durum": "kazanır" if q >= 0.65 else "kaybeder" if q <= 0.35 else "belirsiz"}
    return {"id": sid, "baslik": title, "tur": kind, "olasilik": round(p, 3), "final_skor": fs, "skorlar": scores,
            "perde": perde, "kirilma_ani": turn, "pazarlar": mk, "canli_sinyaller": sig, "meclis_secimi": ms,
            "dayanaklar": basis}


def _what_if(payload: dict) -> dict | None:
    """Eksik etkisi: kilit eksikler oynasaydı (sakatlık çarpanı olmadan) 1X2 ve gol beklentisi."""
    lam = payload.get("lambdas") or {}
    inj = payload.get("injury_effect") or {}
    if not inj or (abs((inj.get("home_mult") or 1) - 1) < 0.005 and abs((inj.get("away_mult") or 1) - 1) < 0.005):
        return None
    from .model.goals import score_matrix

    def x12(lh, la):
        mt = score_matrix(lh, la, lam.get("rho") or 0.0)
        g = np.arange(mt.shape[0])
        d = g[:, None] - g[None, :]
        return {"1": round(float(mt[d > 0].sum()), 3), "X": round(float(mt[d == 0].sum()), 3),
                "2": round(float(mt[d < 0].sum()), 3)}

    now = x12(lam["home"], lam["away"])
    back = x12(lam.get("base_home") or lam["home"], lam.get("base_away") or lam["away"])
    names = lambda side: [r.get("name") for r in (inj.get(f"{side}_missing") or []) if (r.get("importance") or 0) >= 0.1]  # noqa: E731
    return {"eksiklerle": {"lambda": [lam["home"], lam["away"]], "1X2": now},
            "eksikler_oynasaydi": {"lambda": [lam.get("base_home"), lam.get("base_away")], "1X2": back},
            "ev_eksikler": names("home"), "dep_eksikler": names("away"),
            "metin": f"Kilit eksikler oynasaydı ev sahibinin kazanma olasılığı {_pct(now['1'])} yerine {_pct(back['1'])}, "
                     f"deplasmanınki {_pct(now['2'])} yerine {_pct(back['2'])} olurdu."}
