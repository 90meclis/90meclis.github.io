"""Senaryolar ve "maç konuşuyor" anlatısı. Ton: kendinden emin ama dürüst — kesinlik/garanti dili YOK."""
from __future__ import annotations

from .markets import pick_label
from .timeutil import tr_str


def _pct(p: float) -> str:
    return f"%{p * 100:.0f}"


def _mk(payload: dict, market: str, selection: str, line=None) -> float | None:
    for m in payload.get("markets", []):
        if m["market"] == market and m["selection"] == selection and (line is None or m["line"] == line):
            return m["probability"]
    return None


def build_scenarios(payload: dict) -> list[dict]:
    home, away = payload["home"], payload["away"]
    p1, px, p2 = (_mk(payload, "1X2", s) or 0 for s in ("1", "X", "2"))
    scores = payload.get("top_scores", [])

    def best_score(cond):
        for s, p in scores:
            h, a = (int(x) for x in s.split("-"))
            if cond(h, a):
                return s
        return None

    lam = payload.get("lambdas", {})
    tot = lam.get("home", 0) + lam.get("away", 0)
    o25 = _mk(payload, "OU_GOALS", "ÜST", 2.5) or 0
    btts = _mk(payload, "BTTS", "VAR") or 0
    sc = [
        {"ad": f"{home} oyunu kurar", "olasılık": p1,
         "anlatım": f"{home} topa sahip olur, baskıyı kurar; tipik skor {best_score(lambda h, a: h > a) or '1-0'}."},
        {"ad": "Denge / kilit maç", "olasılık": px,
         "anlatım": f"İki takım da riske girmez; tipik skor {best_score(lambda h, a: h == a) or '1-1'}."},
        {"ad": f"{away} sürprizi", "olasılık": p2,
         "anlatım": f"{away} geçişlerle cezalandırır; tipik skor {best_score(lambda h, a: h < a) or '0-1'}."},
        {"ad": "Gollü akış" if tot >= 2.7 else "Düşük tempolu akış", "olasılık": o25 if tot >= 2.7 else 1 - o25,
         "anlatım": f"Toplam gol beklentisi {tot:.2f}; KG Var ihtimali {_pct(btts)}."},
    ]
    ci = payload.get("count_info", {})
    if "corners" in ci:
        sc.append({"ad": "Korner trafiği", "olasılık": None,
                   "anlatım": f"Beklenen korner {ci['corners']['total']:.1f} ({home} {ci['corners']['home']:.1f}, {away} {ci['corners']['away']:.1f})."})
    if "cards" in ci:
        sc.append({"ad": "Sertlik", "olasılık": None,
                   "anlatım": f"Beklenen kart {ci['cards']['total']:.1f} — {'sert geçebilir' if ci['cards']['total'] >= 5 else 'normal sertlikte'}."})
    return sorted(sc, key=lambda s: -(s["olasılık"] or 0))


def _form_text(form: list[dict]) -> str:
    if not form:
        return "form verisi yok"
    w = sum(1 for f in form if f["sonuç"] == "G")
    d = sum(1 for f in form if f["sonuç"] == "B")
    l_ = sum(1 for f in form if f["sonuç"] == "M")
    seq = "".join(f["sonuç"] for f in form)
    return f"son {len(form)} maçta {w}G {d}B {l_}M ({seq})"


def narrative(match: dict, payload: dict) -> str:
    home, away = match["home_name"], match["away_name"]
    lines = [f"**{home} – {away}** · {tr_str(match['kickoff_at'])} (TSİ)"]
    if not payload.get("ready"):
        lines.append(
            "Bu maçın analizi kurulamadı: " + "; ".join(payload.get("missing") or ["veri eksik"]) +
            ". Bot sonraki çalışmada güncel veriyle yeniden hesaplayacak.")
        return "\n\n".join(lines)
    lam = payload["lambdas"]
    tot = lam["home"] + lam["away"]
    tempo = "gollü, açık" if tot >= 3.0 else "dengeli" if tot >= 2.3 else "kontrollü, düşük skorlu"
    lines.append(f"🎙️ *Maç konuşuyor:* Ben {tempo} bir maçım. Hesabım net: {home} **{lam['home']:.2f}**, "
                 f"{away} **{lam['away']:.2f}** gol bekliyor. En olası skorlarım: " +
                 ", ".join(f"{s} ({_pct(p)})" for s, p in payload.get("top_scores", [])[:3]) + ".")
    lines.append(f"Form: {home} {_form_text(payload['form']['home'])}; {away} {_form_text(payload['form']['away'])}.")
    if payload.get("h2h"):
        lines.append("Son karşılaşmalar: " + ", ".join(f"{h['skor']} ({h['tarih'][:4]})" for h in payload["h2h"][:4]) + ".")
    ie = payload.get("injury_effect", {})
    if not payload.get("injuries_known"):
        lines.append("Sakatlık/ceza listesi alınamadı (API-Football anahtarı yok veya kota doldu). "
                     "Bu yüzden güvenimi bir kademe düşürdüm.")
    else:
        keys = [m["name"] for m in ie.get("home_missing", []) + ie.get("away_missing", []) if m.get("is_key")]
        tee = (f"Eksik Etkisi: {home} **{ie.get('home_tee', 0):.0f}** ({ie.get('home_band')}), "
               f"{away} **{ie.get('away_tee', 0):.0f}** ({ie.get('away_band')}).")
        if keys:
            lines.append(tee + " Kilit isimler: **" + ", ".join(keys) + "**. "
                         f"Gol beklentisi çarpanları: {home} ×{ie['home_mult']:.2f}, {away} ×{ie['away_mult']:.2f}.")
        elif ie.get("home_missing") or ie.get("away_missing"):
            lines.append(tee + " Eksikler var ama kilit isim değil; etkileri sınırlı tuttum.")
        else:
            lines.append("Bildirilen eksik yok (Eksik Etkisi 0).")
    w = payload.get("weather")
    if w:
        extra = ""
        if (w.get("precip_prob") or 0) >= 60:
            extra = " Zemin ağırlaşabilir; duran toplar ve hatalar önem kazanır."
        elif (w.get("wind_kmh") or 0) >= 30:
            extra = " Rüzgâr uzun topları ve ortaları etkileyebilir."
        lines.append(f"Hava: {w.get('summary')}, {w.get('temperature_c')}°C, yağış ihtimali %{w.get('precip_prob')}, "
                     f"rüzgâr {w.get('wind_kmh')} km/sa.{extra}")
    bp = payload.get("best_pick")
    if bp:
        lab = pick_label(bp["market"], bp["selection"], bp["line"], home, away)
        p = bp["probability"]
        if bp.get("odds"):
            verdict = (f"🗳️ **Meclisin kararı: {lab}** — olasılık {_pct(p)}, adil oran {bp['fair_odds']:.2f}, "
                       f"piyasa {bp['odds']:.2f} (değer {bp['edge'] * 100:+.1f}%). **Bunu oyna**, 1 birim.")
        else:
            verdict = (f"🗳️ **Meclisin kararı: {lab}** — olasılık {_pct(p)}, adil oran {bp['fair_odds']:.2f}. "
                       "Piyasa oranı elimde yok; oranın adil oranın üstündeyse **bunu oyna**, altındaysa pas geç.")
        lose = max(1, round((1 - p) * 10))
        lines.append(verdict)
        lines.append(f"Dürüst olayım: {_pct(p)} demek, bu tip 10 maçın yaklaşık {lose} tanesinde bu seçim kaybeder. "
                     "Garanti yok; kayıtta kayıplar da görünecek.")
    else:
        lines.append("🗳️ **Meclisin kararı: pas.** Piyasa bu maçı doğru fiyatlamış görünüyor ya da güvenim eşiğin "
                     "altında. Pas geçmek de bir karardır.")
    if payload.get("postponed_markets"):
        lines.append("Ertelenen pazarlar: " + "; ".join(payload["postponed_markets"].values()) + ".")
    return "\n\n".join(lines)
