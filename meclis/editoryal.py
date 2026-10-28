"""Meclis editoryal katmanı — tamamen veriden, şablonla (uydurma sayı yok), otomatik.

* Meclis Bülteni: günün tek paragraflık özeti (Ortak kaç maçı taradı, Günün Kararı / Karar Birliği / Görüşler neden).
* Gerekçe kartı: her yayımlanan seçim için 3 madde + risk + güven bandının geri test isabeti.
* Maç sonrası not: "Neden tuttu / neden yattı" — skor, gol beklentisi, şut/xG ile.
Kayıt: analyses tablosunda sahte maç kimlikleri ('meclis:bulten:YYYY-AA-GG', 'meclis:not:YYYY-AA-GG'); bu tabloda
yabancı anahtar yoktur ve tarama görünümü yalnızca pazarları olan satırları okur.
"""
from __future__ import annotations

from datetime import timedelta

from .markets import pick_label
from .timeutil import now_utc, to_iso

TR_MONTH = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
MARKET_TR = {"1X2": "maç sonucu", "DC": "çifte şans", "OU_GOALS_2.5": "2.5 gol", "OU_GOALS_1.5": "1.5 gol",
             "OU_GOALS_3.5": "3.5 gol", "BTTS": "karşılıklı gol"}


def f(x, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def pc(x) -> str:
    return f"%{round(100 * float(x))}"


def _day_label(dstr: str) -> str:
    y, m, d = (int(v) for v in dstr.split("-"))
    return f"{d} {TR_MONTH[m]}"


def _form_line(rows) -> str:
    rows = (rows or [])[:5]
    g = sum(1 for r in rows if r.get("sonuç") == "G")
    b = sum(1 for r in rows if r.get("sonuç") == "B")
    m = sum(1 for r in rows if r.get("sonuç") == "M")
    return f"{g}G {b}B {m}M" if rows else ""


def _band_stat(motor: dict | None, p: float) -> dict | None:
    for b in ((motor or {}).get("geritest") or {}).get("bantlar") or []:
        if b.get("alt", 0) <= p < b.get("ust", 1.01) and b.get("n"):
            return b
    return None


def card(pred: dict, a: dict | None, motor: dict | None) -> dict:
    """3 madde + risk + bant. a = maçın analiz yükü (yayın anındaki, kilitli)."""
    a = a or {}
    home, away = pred.get("home_name") or "Ev", pred.get("away_name") or "Dep"
    mk, sel, line = pred["market"], pred["selection"], pred.get("line")
    p = float(pred.get("probability") or 0)
    cal = pred.get("calibration") or {}
    lam = a.get("lambdas") or {}
    lh, la = lam.get("home"), lam.get("away")
    dos = a.get("dosya") or {}
    vs = dos.get("venue_split") or {}
    form = a.get("form") or {}
    ie = a.get("injury_effect") or {}
    bullets: list[str] = []
    pm, pk = cal.get("p_model"), cal.get("p_piyasa")
    first = f"Tutma olasılığı {pc(p)}"
    if pm is not None and pk is not None:
        first += f": model {pc(pm)}, marjsız piyasa {pc(pk)} — ikisi aynı yönde" if abs(pm - pk) <= 0.06 else \
            f": model {pc(pm)}, marjsız piyasa {pc(pk)}"
    if pred.get("odds"):
        first += f"; oran {f(pred['odds'])}"
    bullets.append(first + ".")
    goals_mk = mk in ("OU_GOALS", "BTTS", "HT_OU_GOALS", "TEAM_GOALS_HOME", "TEAM_GOALS_AWAY")
    if lh is not None and la is not None:
        if goals_mk:
            bullets.append(f"Gol beklentisi {home} {f(lh)} – {away} {f(la)} (toplam {f(lh + la)}).")
        else:
            fav = home if lh > la else away
            bullets.append(f"Gol beklentisi {home} {f(lh)} – {away} {f(la)}; üstünlük {fav} tarafında.")
    h, w = vs.get("home") or {}, vs.get("away") or {}
    if h.get("n") and w.get("n") and h.get("gf") is not None and w.get("gf") is not None:
        bullets.append(f"{home} iç sahada maç başı {f(h['gf'], 1)} attı, {f(h['ga'], 1)} yedi ({h['n']} maç); "
                       f"{away} deplasmanda {f(w['gf'], 1)} / {f(w['ga'], 1)} ({w['n']} maç).")
    fh, fa = _form_line(form.get("home")), _form_line(form.get("away"))
    if fh and fa:
        bullets.append(f"Son 5 maç: {home} {fh}, {away} {fa}.")
    # risk: en somut olanı
    risk = None
    unc = a.get("xi_uncertainty") or 0
    for side, team in (("home", home), ("away", away)):
        band = ie.get(f"{side}_band")
        if band and band not in ("Etkisiz", "Hafif"):
            names = [x.get("name") for x in (ie.get(f"{side}_missing") or []) if x.get("is_key")][:2]
            risk = f"{team} tarafında eksik etkisi '{band}'" + (f" ({', '.join(names)})" if names else "") + "."
            break
    if risk is None and unc >= 0.15:
        risk = f"İlk 11 belirsizliği yüksek ({pc(unc)}); kadro açıklanınca tablo değişebilir."
    if risk is None and (a.get("market_weight") or 0) >= 0.55:
        risk = "Takımların bu sezon verisi az; olasılık piyasaya daha çok yaslanıyor."
    if risk is None and mk == "OU_GOALS" and lh is not None and la is not None:
        tot = lh + la
        risk = (f"Toplam gol beklentisi {f(tot)}; erken bir gol oyunu açarsa Alt zorlanır." if sel == "ALT"
                else f"Toplam gol beklentisi {f(tot)}; ilk yarı golsüz geçerse Üst zorlanır.")
    if risk is None and mk == "BTTS":
        risk = "Tek taraflı bir oyun (erken fark) KG'yi bozar." if sel == "VAR" else "Erken gol iki takımı da açar."
    if risk is None:
        risk = f"Tutmama olasılığı {pc(1 - p)}: tek maçta sürpriz her zaman masada."
    b = _band_stat(motor, p)
    bant = None
    if b and b.get("n", 0) >= 30:
        bant = {"bant": b["bant"], "isabet": b.get("isabet"), "n": b["n"],
                "metin": f"Geri testte {b['bant']} bandındaki seçimler {pc(b['isabet'])} tuttu ({b['n']} seçim, örneklem dışı)."}
    return {"maddeler": bullets[:3], "risk": risk, "bant": bant,
            "etiket": pick_label(mk, sel, line, home, away)}


def bulletin(dstr: str, preds: list[dict], coupons: list[dict], n_matches: int, n_leagues: int,
             motor: dict | None, top_match: dict | None) -> dict:
    gk = next((c for c in coupons if c["tag"] == "gunun_karari"), None)
    kb = next((c for c in coupons if c["tag"] == "karar_birligi"), None)
    legs = lambda c: sorted((p for p in preds if p.get("coupon_id") == c["id"]), key=lambda p: p["kickoff_at"])  # noqa: E731
    singles = sorted((p for p in preds if p["tag"] == "meclis_gorusu"), key=lambda p: -(p.get("probability") or 0))
    parts = [f"{_day_label(dstr)} bülteni: Ortak {n_matches} maçı ({n_leagues} lig) taradı."]
    deep = (motor or {}).get("derin_pazarlar")
    if deep:
        grp = lambda p: f"OU_GOALS_{float(p['line']):g}" if p["market"] == "OU_GOALS" and p.get("line") is not None else p["market"]  # noqa: E731
        off = sorted({grp(p) for p in preds} - set(deep))
        parts.append("Motorun güncel kuralına göre yayına açık pazarlar: " + ", ".join(MARKET_TR.get(g, g) for g in deep) + "."
                     + (f" Bu günün bazı kararları ({', '.join(MARKET_TR.get(g, g) for g in off)}) bu kural benimsenmeden "
                        "önce kilitlendi; kayıt değiştirilmez." if off else ""))
    maddeler = []
    if gk:
        ls = legs(gk)
        desc = "; ".join(f"{p['home_name']} – {p['away_name']} {pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])} ({pc(p['probability'])})" for p in ls)
        parts.append(f"Günün Kararı {len(ls)} maçtan: {desc}. Toplam oran {f(gk['total_odds'])}, hepsinin birlikte "
                     f"tutma olasılığı {pc(gk['joint_probability'])}. Bunlar günün kalibre olasılığı en yüksek seçimleri.")
        maddeler.append({"baslik": "Günün Kararı", "metin": desc})
    if kb:
        ls = legs(kb)
        desc = "; ".join(f"{p['home_name']} – {p['away_name']} {pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])}" for p in ls)
        parts.append(f"Karar Birliği (model ile piyasanın aynı yönde olduğu, başka üründe olmayan maçlar): {desc}; toplam oran {f(kb['total_odds'])}.")
    if singles:
        s0 = singles[0]
        parts.append(f"Meclis Görüşleri {len(singles)} maç; en güçlüsü {s0['home_name']} – {s0['away_name']}: "
                     f"{pick_label(s0['market'], s0['selection'], s0.get('line'), s0['home_name'], s0['away_name'])} ({pc(s0['probability'])}).")
    if top_match:
        parts.append(top_match["metin"])
    if not (gk or kb or singles):
        parts.append("Bu gün için henüz yayımlanmış karar yok; kuponlar bir önceki gün 18:00'de (TSİ) kurulur.")
    return {"tarih": dstr, "metin": " ".join(parts), "maddeler": maddeler, "uretildi": to_iso(now_utc()),
            "kaynak": "maç analizleri, kilitli kayıtlar ve motor geri testi (şablon; sayılar veriden)"}


def postmortem(pred: dict, m: dict, stats: dict, a: dict | None) -> str | None:
    if m.get("home_goals") is None or pred.get("status") not in ("kazandi", "kaybetti", "iade"):
        return None
    hg, ag = m["home_goals"], m["away_goals"]
    lab = pick_label(pred["market"], pred["selection"], pred.get("line"), pred["home_name"], pred["away_name"])
    won = pred["status"] == "kazandi"
    head = ("Tuttu ✓" if won else "Yattı ✗" if pred["status"] == "kaybetti" else "İade") + f" — {lab}: maç {hg}-{ag} bitti"
    if pred["market"] in ("OU_GOALS", "BTTS"):
        head += f" ({hg + ag} gol)"
    head += "."
    bits = []
    lam = (a or {}).get("lambdas") or {}
    if lam.get("home") is not None:
        bits.append(f"Maç öncesi beklenti {f(lam['home'])}–{f(lam['away'])} goldü.")
    sh, sa = stats.get("home") or {}, stats.get("away") or {}
    if sh.get("shots") is not None and sa.get("shots") is not None:
        t = f"Şut {sh['shots']}–{sa['shots']}"
        if sh.get("shots_on_target") is not None and sa.get("shots_on_target") is not None:
            t += f" (isabetli {sh['shots_on_target']}–{sa['shots_on_target']})"
        bits.append(t + ".")
    xh, xa = sh.get("xg"), sa.get("xg")
    if xh is not None and xa is not None:
        bits.append(f"xG {f(xh)}–{f(xa)}.")
        if not won and pred["status"] == "kaybetti":
            if pred["market"] == "OU_GOALS":
                exp_over = (xh + xa) > float(pred.get("line") or 2.5)
                ok_play = exp_over == (pred["selection"] == "ÜST")
                bits.append("Oyun tahmine uygun aktı, sonuç bitiricilikte saptı." if ok_play
                            else "Pozisyon üretimi de tahminden saptı.")
            elif pred["market"] == "1X2":
                lead = "1" if xh > xa + 0.3 else "2" if xa > xh + 0.3 else "X"
                bits.append("xG seçimi destekliyordu; skor bitiricilikte kaçtı." if lead == pred["selection"]
                            else "xG de rakip lehine: oyun da tahminden saptı.")
    if (sh.get("red") or 0) + (sa.get("red") or 0) > 0:
        bits.append(f"Kırmızı kart: {sh.get('red') or 0}–{sa.get('red') or 0} — oyunun dengesini değiştirdi.")
    if not won and pred["status"] == "kaybetti":
        bits.append(f"Seçimin dışında kalan {pc(1 - float(pred.get('probability') or 0))}'lik senaryo gerçekleşti.")
    return " ".join([head] + bits)


# ----------------------------------------------------------------------------- işler
def _latest_payload(store, mid: str) -> dict | None:
    from .ayna import frozen_analysis  # yayımlanmış seçimin analizi kilitlidir → bir kez okunur

    return frozen_analysis(store, mid)


def _put(store, key: str, payload: dict) -> None:
    ts = to_iso(now_utc())
    store.upsert("analyses", [{"match_id": key, "created_at": ts, "model_version": "meclis-editoryal-1", "payload": payload}])
    try:
        store.prune("analyses", [("match_id", "eq", key), ("created_at", "lt", ts)])
    except Exception:
        pass


def run_bulletins(store, settings, log: list) -> int:
    """Bugün ve yarın (TSİ) için bülten + gerekçe kartları."""
    from .bot import _tr_day_bounds
    from .motor import latest as motor_latest
    from .timeutil import tr_date

    motor = motor_latest(store)
    today = tr_date(to_iso(now_utc()))
    n = 0
    for day in (today, today + timedelta(days=1)):
        dstr = day.isoformat()
        lo, hi = (to_iso(x) for x in _tr_day_bounds(day))
        preds = store.select("predictions", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
        coupons = store.select("coupons", [("coupon_date", "eq", dstr)])
        ms = [m for m in store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
              if not str(m["league"]).startswith("Y") and m.get("status") != "iptal"]
        if not ms:
            continue
        cards = {}
        pay_cache: dict = {}
        for p in preds:
            if p["match_id"] not in pay_cache:
                pay_cache[p["match_id"]] = _latest_payload(store, p["match_id"])
            cards[p["id"]] = card(p, pay_cache[p["match_id"]], motor)
        top = _top_match(store, ms)
        b = bulletin(dstr, preds, coupons, len(ms), len({m["league"] for m in ms}), motor, top)
        b["kartlar"] = cards
        _put(store, f"meclis:bulten:{dstr}", b)
        n += 1
    log.append(f"✅ editoryal: {n} günün bülteni ve gerekçe kartları yazıldı")
    return n


def _top_match(store, ms: list[dict]) -> dict | None:
    from .config import LEAGUES

    order = {"CL": 0, "EL": 1, "ECL": 2, "E0": 3, "SP1": 4, "I1": 5, "D1": 6, "F1": 7, "T1": 8}
    cand = sorted((m for m in ms if m["league"] in order), key=lambda m: (order[m["league"]], m["kickoff_at"]))
    for m in cand[:6]:
        rows = store.select("analyses", [("match_id", "eq", m["id"])], order="created_at", desc=True, limit=1)
        a = rows[0]["payload"] if rows else None  # vitrin maçı kilitli değil: güncel analiz
        if not a:
            continue
        p = {x["selection"]: x.get("p_kal") or x.get("probability") for x in a.get("markets") or [] if x["market"] == "1X2"}
        if len(p) == 3 and all(v is not None for v in p.values()):
            fav = max(p, key=p.get)
            name = {"1": m["home_name"], "2": m["away_name"], "X": "beraberlik"}[fav]
            lg = LEAGUES[m["league"]].name if m["league"] in LEAGUES else m["league"]
            return {"match_id": m["id"], "metin": f"Günün vitrin maçı ({lg}) {m['home_name']} – {m['away_name']}: "
                                                  f"Ortak'a göre {name} {pc(p[fav])} ile önde."}
    return None


def run_notes(store, log: list, days: int = 3) -> int:
    """Son günlerde sonuçlanan her yayımlanmış seçim için 'neden tuttu / yattı' notu."""
    from .bot import _tr_day_bounds
    from .timeutil import tr_date

    today = tr_date(to_iso(now_utc()))
    total = 0
    for k in range(days):
        day = today - timedelta(days=k)
        dstr = day.isoformat()
        lo, hi = (to_iso(x) for x in _tr_day_bounds(day))
        preds = [p for p in store.select("predictions", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
                 if p.get("status") in ("kazandi", "kaybetti", "iade")]
        if not preds:
            continue
        notes = {}
        for p in preds:
            m = store.get("matches", id=p["match_id"])
            if not m:
                continue
            st = {}
            for r in store.select("match_stats", [("match_id", "eq", p["match_id"])]):
                st[r.get("side")] = r
            n = postmortem(p, m, st, _latest_payload(store, p["match_id"]))
            if n:
                notes[p["id"]] = n
        for c in store.select("coupons", [("coupon_date", "eq", dstr)]):
            if c.get("status") in ("kazandi", "kaybetti"):
                legs = [p for p in preds if p.get("coupon_id") == c["id"]]
                bad = [p for p in legs if p["status"] == "kaybetti"]
                notes[c["id"]] = ("Kupon tuttu ✓ — bütün ayaklar geldi." if c["status"] == "kazandi" else
                                  "Kupon yattı ✗ — bozan ayak: " + ", ".join(
                                      f"{p['home_name']} – {p['away_name']}" for p in bad) + ".")
        if notes:
            _put(store, f"meclis:not:{dstr}", {"tarih": dstr, "notlar": notes, "uretildi": to_iso(now_utc())})
            total += len(notes)
    log.append(f"✅ maç sonrası notlar: {total}")
    return total
