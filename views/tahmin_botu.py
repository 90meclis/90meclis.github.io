import pandas as pd
import streamlit as st

from meclis import ui
from meclis.store import StoreError
from meclis.timeutil import tr_str

st.title("🤖 Ortak")
st.caption("Meclis'in yapay zekâ analisti")
st.caption("Bülteni tarar, maçları süzer, her pazarı inceler, senaryo kurar ve tahmini maçtan ÖNCE deftere yazar.")
ui.banner()
s, store, pool = ui.resources()

with st.expander("Bot nasıl çalışır?", expanded=False):
    st.markdown(f"""
1. **Bülten taraması:** Seçili liglerde (**{', '.join(ui.league_name(x) for x in s.leagues)}**) önümüzdeki
   **{s.horizon_hours:.0f} saat** içindeki maçlar alınır. Maç asla elenmez. Model **bu sezon genelinde** çalışır;
   girdi bu sezonun maçlarıdır. İlk 11 için resmî liste beklenmez: **Meclis tahmini ilk 11**
   (son resmî ilk 11'ler, sezon ilk 11 payı, sakat/cezalı listesi) modele işlenir.
2. **Veri toplama:** Birleşik havuz: 18 kaynak (anahtarsız: football-data.co.uk, OpenLigaDB, openfootball,
   TheSportsDB, Wikidata, Open-Meteo, RSS, Meclis Elo; anahtarlı: API-Football, Sportmonks, football-data.org,
   FootyStats, SportDevs, BSD, Wikipedia, The Odds API, OddsPapi, Club Elo). Eksik alan bir kaynaktan diğerine
   tamamlanır; hiçbir kaynakta olmayan alan boş kalır, uydurulmaz.
3. **Her maç analiz edilir:** Eksik veri analizi durdurmaz; boşluklar ek kaynaklar, güncel sezon verisi, Elo
   önseli ve piyasa oranıyla kapatılır. Tamlık puanı yalnızca **güven göstergesidir**. Maçlar her çalışmada
   güncel veriyle yeniden hesaplanır; verilen karar maç başlamadan kilitlenir.
4. **Modeller:** Gol/skor için zaman ağırlıklı **Dixon-Coles** (Poisson skor matrisi), Elo önseliyle (%45)
   harmanlanır; korner, kart, isabetli şut,
   kale vuruşu için takım oranları + **negatif binom/Poisson**. Sakatlıklar **Eksik Etkisi (0–100)** ile λ'ya işlenir.
5. **Seçim:** Her maç için bütün pazarlar taranır; Meclis maç başına tek **Meclis Görüşü** verir. **Günün Kararı**:
   Meclis'in ana tercihlerinden oluşan günün kuponu. **Karar Birliği**: günün en güvenilen tekli kararlarından kombinasyon.
6. **Kilit:** Kayıtlar veritabanı tetikleyicisiyle kilitlidir: maç başladıktan sonra eklenemez, değiştirilemez, silinemez.
""")

ro = getattr(store, "read_only", False)
# Bot düğmeleri yalnızca yöneticiye (ADMIN_TOKEN, app.py). Ziyaretçi hiçbir dış isteği tetikleyemez.
if st.session_state.get("is_admin"):
    if ro:
        st.caption("Tahminler zamanlanmış bot tarafından maçtan önce kaydedilir. Buradan deftere yazmadan "
                   "bir deneme analizi çalıştırabilirsin.")
        c3 = st.columns(4)[0]
        c1 = c2 = c4 = None
    else:
        c1, c2, c3, c4 = st.columns(4)
    run_log = []
    try:
        if c1 is not None and c1.button("🔄 Havuzu yenile", disabled=s.demo_mode or ro, width="stretch"):
            with st.spinner("Kaynaklar taranıyor..."):
                r = pool.refresh(history=True)
            ui.clear_caches()
            run_log = r["log"] + [f"{r['records']} kaynak kaydı → {r['matches']} birleşik maç"]
        if c2 is not None and c2.button("📝 Botu çalıştır (kayda yaz)", type="primary", width="stretch", disabled=ro):
            with st.spinner("Analiz ediliyor..."):
                from meclis.bot import Bot

                r = Bot(store, s, pool).run(record=True, fetch_extras=not s.demo_mode)
            ui.clear_caches()
            run_log = r["log"]
        if c3.button("🧪 Kuru çalıştır", width="stretch", help="Analiz eder ama deftere yazmaz"):
            with st.spinner("Analiz ediliyor..."):
                from meclis.bot import Bot

                r = Bot(store, s, pool).run(record=False, fetch_extras=False)
            run_log = r["log"]
        if c4 is not None and c4.button("🏁 Sonuçlandır", width="stretch", disabled=ro):
            with st.spinner("Sonuçlar kontrol ediliyor..."):
                from meclis.settlement import run_settlement

                if not s.demo_mode:
                    pool.refresh(days_back=5, days_ahead=0, history=True)
                r = run_settlement(store, pool)
            ui.clear_caches()
            run_log = r["log"]
    except StoreError as e:
        st.error(f"Kayıt hatası: {e}")
    if run_log:
        st.code("\n".join(run_log), language=None)

st.subheader("📋 Bülten çıktısı: değer kuralını geçen bütün seçimler")
st.caption("Ortak'ın ham çıktısı. Masanın seçtiği kararlar (Günün Kararı, Meclis Görüşleri, Karar Birliği) **Tahmin Arşivi**'nde.")
from datetime import timedelta as _td  # noqa: E402

from meclis.markets import TAG_LABELS, pick_label  # noqa: E402
from meclis.pool import today_tr  # noqa: E402
from meclis.timeutil import day_bounds_utc  # noqa: E402

_t0 = today_tr()
_day = st.radio("Gün", [_t0, _t0 + _td(days=1), _t0 + _td(days=2)], horizontal=True,
                format_func=lambda d: "Bugün" if d == _t0 else ("Yarın" if d == _t0 + _td(days=1) else d.strftime("%d.%m")))
_lo, _hi = day_bounds_utc(_day)
_ms = store.select("matches", [("kickoff_at", "gte", _lo), ("kickoff_at", "lt", _hi)], order="kickoff_at")
_ids = [m["id"] for m in _ms]
_an: dict = {}
for i in range(0, len(_ids), 50):
    for r in store.select("analyses", [("match_id", "in", _ids[i:i + 50])], order="created_at", desc=True):
        _an.setdefault(r["match_id"], r.get("payload") or {})
_pub: dict = {}
for p in store.select("predictions", [("kickoff_at", "gte", _lo), ("kickoff_at", "lt", _hi)]):
    _pub.setdefault((p["match_id"], p["market"], p["selection"], p.get("line")), p["tag"])


def value_picks(pl: dict) -> list[dict]:
    """Botun değer kuralı: meclis.analysis.rank_picks (maç başına bütün adaylar, değere göre sıralı)."""
    from meclis.analysis import rank_picks

    if not pl.get("ready") or not pl.get("markets"):
        return []
    mm = pl.get("model_matches") or {}
    if str(pl.get("basis") or "").startswith("model") and min(mm.get("home", 0), mm.get("away", 0)) < pl.get("min_team_matches", 4):
        return []
    try:
        return rank_picks(pl, s)
    except (KeyError, TypeError):
        return []


# Kaynak: bot_picks (botun kaydettiği bülten); yoksa son analizlerden aynı kuralla türetilir.
try:
    _bp = store.select("bot_picks", [("kickoff_at", "gte", _lo), ("kickoff_at", "lt", _hi)], order="kickoff_at")
except Exception:
    _bp = []
_bp_by: dict = {}
for x in _bp:
    _bp_by.setdefault(x["match_id"], []).append(x)

rows_ = []
for m in _ms:
    pl = _an.get(m["id"]) or {}
    top = max((x for x in pl.get("scenarios") or [] if x.get("olasılık") is not None), key=lambda x: x["olasılık"], default=None)
    for v in (_bp_by.get(m["id"]) if _bp_by else value_picks(pl)) or []:
        why = f"Model %{100 * v['probability']:.0f}"
        if v.get("odds"):
            why += f", piyasa %{100 / v['odds']:.0f} → değer %{100 * v['edge']:+.1f}"
        if top:
            why += f" · akış: {top['ad'].lower()}"
        rows_.append({"Lig": ui.league_name(m["league"]), "Saat": tr_str(m["kickoff_at"], "%H:%M"),
                      "Maç": f"{m['home_name']} – {m['away_name']}",
                      "Pazar": pick_label(v["market"], v["selection"], v.get("line"), m["home_name"], m["away_name"]),
                      "Oran": v.get("odds") or v.get("fair_odds"), "Model %": round(100 * v["probability"], 1),
                      "Değer %": round(100 * v["edge"], 1) if v.get("edge") is not None else None,
                      "Masada": TAG_LABELS.get(_pub.get((m["id"], v["market"], v["selection"], v.get("line"))) or v.get("status"), ""),
                      "Kısa gerekçe": why})
k1, k2, k3 = st.columns(3)
k1.metric("Bültendeki maç", len(_ms))
k2.metric("Analiz edilen", len(_an))
k3.metric("Değer seçimi", len(rows_))
st.caption("Kaynak: botun kaydettiği bülten (bot_picks)." if _bp_by else
           "Kaynak: son analizler, botun değer kuralıyla (kalibre olasılık, değer ≥ %3, oran 1,50–5,00).")
if rows_:
    st.dataframe(pd.DataFrame(rows_).sort_values(["Lig", "Saat"]), hide_index=True, width="stretch")
elif _ms:
    ui.empty_state("Bot bu bültende henüz değer bulmadı. Maçlar her çalışmada güncel veriyle yeniden hesaplanır.")
else:
    ui.empty_state("Bu gün bültende maç yok.")
