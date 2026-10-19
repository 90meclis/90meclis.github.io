from datetime import date, timedelta

import pandas as pd
import streamlit as st

from meclis import ui
from meclis.markets import MARKET_GROUPS, MARKET_LABELS, pick_label
from meclis.pool import status_text, today_tr
from meclis.timeutil import day_bounds_utc, tr_str

st.title("🏟️ Maç Merkezi")
st.caption("Maça tıkla: kadro, eksikler, form, istatistik, son karşılaşmalar, hava durumu ve meclisin senaryoları tek ekranda.")
ui.banner()
s, store, pool = ui.resources()

if not store.select("matches", limit=1):
    ui.empty_state("Maç verisi hazırlanıyor; kısa süre sonra tekrar bak.")
    if not getattr(store, "read_only", False) and st.button("📥 Veri havuzunu doldur", type="primary"):
        with st.spinner("Kaynaklar taranıyor..."):
            r = pool.refresh(history=True)
        ui.clear_caches()
        st.success(f"{r['matches']} maç havuza alındı.")
        st.write("\n".join(f"- {x}" for x in r["log"]))
    st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def match_days(leagues: tuple, start_iso: str, end_iso: str) -> dict:
    """Önümüzdeki günlerde (TR saatiyle) maç olan günler → maç sayısı."""
    from collections import Counter

    rows = pool.matches_between(start_iso, end_iso, list(leagues))
    return dict(sorted(Counter(tr_str(m["kickoff_at"], "%Y-%m-%d") for m in rows).items()))


c1, c2 = st.columns([1, 3])
leagues = c2.multiselect("Ligler", s.leagues, default=s.leagues, format_func=ui.league_name)
today = today_tr()
lo0, _ = day_bounds_utc(today)
_, hi0 = day_bounds_utc(today + timedelta(days=14))
days = match_days(tuple(leagues or s.leagues), lo0, hi0)
# Bugün maç yoksa varsayılan tarih ilk maç günü olur (boş ekranla açılmasın)
nxt = next((date.fromisoformat(d) for d in days if date.fromisoformat(d) >= today), today)
if "mm_day" not in st.session_state:
    st.session_state["mm_day"] = today if today.isoformat() in days else nxt
day = c1.date_input("Tarih", key="mm_day", format="DD.MM.YYYY")
if days:
    st.caption("📅 Önümüzdeki maç günleri: " + " · ".join(
        f"{date.fromisoformat(d):%d.%m} ({n})" for d, n in list(days.items())[:10]))
lo, hi = day_bounds_utc(day)
matches = pool.matches_between(lo, hi, leagues or s.leagues)
if not matches:
    ui.empty_state("Bu tarihte seçili liglerde maç bulunamadı" + (f" — sıradaki maç günü {nxt:%d.%m.%Y}." if days else ".")
                   )
    if days:
        st.button(f"➡️ {nxt:%d.%m.%Y} maçlarına git", type="primary",
                  on_click=lambda: st.session_state.update(mm_day=nxt))
    st.stop()

bot = ui.bot()


@st.cache_data(ttl=600, show_spinner=False)
def quick(match_id: str, updated: str, _m: dict):
    return bot.analyze(_m, fetch_extras=False)


rows = []
for m in matches:
    a = quick(m["id"], m.get("updated_at") or "", m)
    lam = a.get("lambdas") or {}
    p = {x["selection"]: x["probability"] for x in a.get("markets", []) if x["market"] == "1X2"}
    bp = a.get("best_pick")
    rows.append({
        "Saat": tr_str(m["kickoff_at"], "%H:%M"), "Lig": ui.league_name(m["league"]),
        "Maç": f"{m['home_name']} – {m['away_name']}",
        "Durum": status_text(m),
        "Skor": f"{m['home_goals']}-{m['away_goals']}" if m.get("home_goals") is not None else "",
        "1 %": round(100 * p["1"]) if p else None, "X %": round(100 * p["X"]) if p else None,
        "2 %": round(100 * p["2"]) if p else None,
        "Gol bekl.": round(lam["home"] + lam["away"], 2) if lam else None,
        "Tamlık": a.get("quality", {}).get("score"),
        "Meclis": pick_label(bp["market"], bp["selection"], bp.get("line"), m["home_name"], m["away_name"]) if bp
        else "Değer yok",
    })
st.subheader(f"{day.strftime('%d.%m.%Y')} bülteni · {len(matches)} maç")
sel = st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", on_select="rerun",
                   selection_mode="single-row", key="mm_table")
picked = sel.selection.rows if sel and sel.selection else []
ids = [x["id"] for x in matches]
qp = st.query_params.get("mac")
labels = {x["id"]: f"{tr_str(x['kickoff_at'], '%H:%M')} {x['home_name']} – {x['away_name']}" for x in matches}
choice = st.selectbox("…ya da listeden seç", [""] + ids, index=(ids.index(qp) + 1) if qp in ids else 0,
                      format_func=lambda i: labels.get(i, "—"), key="mm_pick")
if picked:
    m = matches[picked[0]]
elif choice:
    m = next(x for x in matches if x["id"] == choice)
else:
    st.info("👆 Ayrıntı için tablodan bir maça tıkla.")
    st.stop()


@st.cache_data(ttl=600, show_spinner=False)
def full(match_id: str, updated: str, _m: dict):
    return bot.analyze(_m, fetch_extras=not s.demo_mode)


with st.spinner("Maç verisi toplanıyor (hava durumu, eksikler, kadro)..."):
    a = full(m["id"], m.get("updated_at") or "", m)

st.divider()
st.header(f"{m['home_name']} – {m['away_name']}")
st.caption(f"{ui.league_name(m['league'])} · {tr_str(m['kickoff_at'])} TSİ · {m.get('venue') or 'stadyum bilgisi yok'}"
           f" · Hakem: {m.get('referee') or 'bilinmiyor'}")
lam = a.get("lambdas") or {}
p1x2 = {x["selection"]: x["probability"] for x in a.get("markets", []) if x["market"] == "1X2"}
k = st.columns(6)
k[0].metric(f"{m['home_name']} gol bekl.", f"{lam['home']:.2f}" if lam else "—")
k[1].metric(f"{m['away_name']} gol bekl.", f"{lam['away']:.2f}" if lam else "—")
for i, (sel_, lab) in enumerate((("1", "MS 1"), ("X", "MS X"), ("2", "MS 2"))):
    k[2 + i].metric(lab, f"%{100 * p1x2[sel_]:.0f}" if p1x2 else "—",
                    help=f"Piyasa: {(m.get('odds') or {}).get('1X2', {}).get(sel_, '—')}")
k[5].metric("Veri tamlığı", f"{a.get('quality', {}).get('score', 0):.0f}/100")

left, right = st.columns([3, 2])
with left:
    st.markdown("#### 🎙️ Meclisin sesi")
    st.markdown(a.get("narrative") or "")
with right:
    st.markdown("#### 🎬 Senaryolar")
    if a.get("scenarios"):
        st.dataframe(pd.DataFrame([{"Senaryo": x["ad"], "Olasılık %": round(100 * x["olasılık"], 1) if x["olasılık"] else None,
                                    "Akış": x["anlatım"]} for x in a["scenarios"]]), hide_index=True, width="stretch")
        st.markdown("**En olası skorlar:** " + " · ".join(f"{s_} (%{100 * p_:.0f})" for s_, p_ in a.get("top_scores", [])))
    else:
        st.info("Bu maç için senaryo kurulamadı.")

st.markdown("#### 📊 Tüm pazarlar")
if a.get("markets"):
    gcols = st.columns(3)
    for i, (g, mks) in enumerate(MARKET_GROUPS.items()):
        rows_ = [x for x in a["markets"] if x["market"] in mks]
        with gcols[i % 3]:
            st.markdown(f"**{g}**")
            if not rows_:
                reason = [v for kk, v in a.get("postponed_markets", {}).items() if kk in mks]
                st.caption(reason[0] if reason else "veri yok")
                continue
            st.dataframe(pd.DataFrame([{
                "Seçim": pick_label(x["market"], x["selection"], x.get("line"), "Ev", "Dep"),
                "Olasılık %": round(100 * x["probability"], 1), "Adil": x.get("fair_odds"),
                "Piyasa": x.get("odds"), "Değer %": round(100 * x["edge"], 1) if x.get("edge") is not None else None,
            } for x in rows_]), hide_index=True, width="stretch", height=min(320, 38 + 35 * len(rows_)))
    ci = a.get("count_info") or {}
    if ci:
        st.caption("Beklenen sayılar: " + " · ".join(
            f"{ {'corners': 'korner', 'cards': 'kart', 'shots_on_target': 'isabetli şut', 'goal_kicks': 'kale vuruşu'}[kk]} "
            f"{v['home']:.1f}+{v['away']:.1f}={v['total']:.1f} ({v['dist']})" for kk, v in ci.items()))
else:
    st.warning("Pazar analizi yapılamadı: " + "; ".join(a.get("missing", [])))

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"#### 📈 Form: {m['home_name']}")
    st.dataframe(pd.DataFrame(a.get("form", {}).get("home", [])), hide_index=True, width="stretch")
with c2:
    st.markdown(f"#### 📈 Form: {m['away_name']}")
    st.dataframe(pd.DataFrame(a.get("form", {}).get("away", [])), hide_index=True, width="stretch")
with c3:
    st.markdown("#### 🤝 Son karşılaşmalar")
    if a.get("h2h"):
        st.dataframe(pd.DataFrame(a["h2h"]), hide_index=True, width="stretch")
    else:
        st.caption("Havuzdaki son iki sezonda karşılaşma yok.")

ctx = bot.context(m["league"])
st.markdown("#### 🔢 İstatistikler (son 10 maç, maç maç)")
s1, s2 = st.columns(2)
for col, side in ((s1, "home"), (s2, "away")):
    ser = pd.DataFrame(ctx.series(m[f"{side}_team_id"], 10))
    with col:
        st.markdown(f"**{m[f'{side}_name']}**")
        if ser.empty:
            st.caption("Geçmiş maç verisi yok.")
        else:
            num = ser[["şut", "isabetli şut", "korner", "kart"]].apply(pd.to_numeric, errors="coerce")
            st.caption("Ortalama (son 10): " + " · ".join(f"{c} {num[c].mean():.1f}" for c in num.columns if num[c].notna().any()))
            st.dataframe(ser.dropna(axis=1, how="all"), hide_index=True, width="stretch")

st.markdown("#### 👥 Kadrolar ve eksikler")
ie = a.get("injury_effect") or {}
k1, k2 = st.columns(2)
lineups = {x["side"]: x for x in store.select("lineups", [("match_id", "eq", m["id"])])}
for col, side in ((k1, "home"), (k2, "away")):
    with col:
        st.markdown(f"**{m[f'{side}_name']}**")
        pxi = ((a.get("predicted_xi") or {}).get(side) or {})
        if pxi.get("players"):
            st.caption("🧠 Meclis tahmini ilk 11 (modelde kullanılan) · dayanak: " + ", ".join(pxi.get("basis") or []))
            st.write(", ".join(p["name"] + (" (şüpheli)" if p.get("note") else "") for p in pxi["players"]))
        else:
            st.caption("Meclis tahmini ilk 11 kurulamadı: " + ", ".join(pxi.get("basis") or ["veri yok"]))
        lu = lineups.get(side)
        if lu:
            from meclis.teamnews import is_confirmed

            if is_confirmed(lu):
                st.caption(f"📋 Resmî ilk 11 ({lu.get('formation') or '—'}) · kaynak: {lu.get('source')} — yalnızca bilgi")
            else:
                st.caption(f"Dış kaynak tahmini ({lu.get('formation') or '—'}) · kaynak: {lu.get('source')}")
            st.write(", ".join(p["name"] for p in lu.get("start_xi") or []))
        if not s.demo_mode:
            with st.expander("Güncel kadro (Wikipedia / BSD)"):
                from meclis.teamnews import current_players

                sq = current_players(store.select("players", [("team_id", "eq", m[f"{side}_team_id"])]))
                if sq:
                    st.dataframe(pd.DataFrame([{"No": p.get("shirt_number"), "Oyuncu": p.get("name"),
                                                "Mevki": p.get("position"), "Dakika": p.get("minutes"),
                                                "İlk 11": p.get("lineups"), "Gol": p.get("goals"), "Asist": p.get("assists"),
                                                "İstatistik": p.get("stats_source") or "—"} for p in sq]),
                                 hide_index=True)
                    st.caption("Kadro: Wikipedia (CC BY-SA 4.0) / BSD. İstatistik: oyuncunun bu kulüpteki son erişilebilen "
                               "sezonu; boşsa oyuncu önemi 'bilinmiyor' sayılır.")
                else:
                    sq = pool.squad_list(m[f"{side}_team_id"], m[f"{side}_name"])
                    if sq:
                        st.dataframe(pd.DataFrame(sq), hide_index=True)
                    else:
                        st.caption("Kadro listesi alınamadı.")
        if a.get("injuries_known"):
            st.metric("Eksik Etkisi (0–100)", f"{ie.get(f'{side}_tee', 0):.0f}", ie.get(f"{side}_band"), delta_color="off")
            miss = ie.get(f"{side}_missing") or []
            if miss:
                st.dataframe(pd.DataFrame([{"Oyuncu": x.get("name"), "Durum": x.get("kind"), "Neden": x.get("reason"),
                                            "Önem (0–1)": x.get("importance"), "Kilit": "Evet" if x.get("is_key") else
                                            ("?" if x.get("is_key") is None else "Hayır"),
                                            "Dakika payı": x.get("minutes_share"), "G+A payı": x.get("ga_share")}
                                           for x in miss]), hide_index=True, width="stretch")
            else:
                st.caption("Bildirilen eksik yok.")
        else:
            st.caption("Sakat/cezalı listesi bu maç için henüz yayımlanmadı. Uydurma liste gösterilmez.")

w1, w2 = st.columns(2)
with w1:
    st.markdown("#### 🌦️ Hava durumu (Open-Meteo)")
    w = a.get("weather")
    if w:
        st.write(f"**{w.get('summary')}** · {w.get('temperature_c')}°C · yağış ihtimali %{w.get('precip_prob')} "
                 f"({w.get('precip_mm')} mm) · rüzgâr {w.get('wind_kmh')} km/sa · nem %{w.get('humidity')}")
        st.caption(f"Konum: {w.get('location') or '—'} — {w.get('approx', '')}. Saat: {w.get('time_utc')} UTC")
    else:
        st.caption("Hava durumu alınamadı (16 günden uzak maç, konum bulunamadı ya da örnek veri modu).")
with w2:
    st.markdown("#### 📰 Bu maçla ilgili gündem")
    news = [n for n in store.select("agenda", order="published_at", desc=True, limit=400) if m["id"] in (n.get("match_ids") or [])]
    if news:
        for n in news[:8]:
            st.markdown(f"- [{n['title']}]({n['link']}) · *{n.get('category')}* · {n.get('source')} · {tr_str(n.get('published_at'))}")
            if n.get("impact_note"):
                st.caption(f"↳ {n['impact_note']}")
    else:
        st.caption("Bağlı haber yok. Gündem Masası'ndan taramayı çalıştırabilirsin.")

with st.expander("🧾 Veri tamlığı ve kaynaklar (alan bazında köken)"):
    q = a.get("quality") or {}
    st.dataframe(pd.DataFrame([{"Alan": k_, "Ağırlık": q.get("weights", {}).get(k_), "Var mı (0–1)": v}
                               for k_, v in (q.get("fields") or {}).items()]), hide_index=True)
    st.caption(f"Tamlık puanı {q.get('score')} / 100 — güven göstergesidir; tahmini durdurmaz. "
               f"Gol beklentisi dayanağı: {a.get('basis') or '—'}.")
    st.json(m.get("sources") or {})
    st.caption("Piyasa oranları: " + ", ".join(f"{k_}: {v}" for k_, v in (m.get("odds") or {}).items()) if m.get("odds") else "Piyasa oranı yok.")
st.caption("Olasılıklar modeldir, kesinlik değildir. Sorumlu oyna; 1 birimden fazlasını riske atma.")
