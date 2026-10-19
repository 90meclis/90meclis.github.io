import pandas as pd
import streamlit as st

from meclis import ui
from meclis.markets import QUEUE_LABELS
from meclis.store import StoreError
from meclis.timeutil import tr_str

st.title("🤖 Tahmin Botu")
st.caption("Bülteni tarar, maçları süzer, her pazarı inceler, senaryo kurar ve tahmini maçtan ÖNCE deftere yazar.")
ui.banner()
s, store, pool = ui.resources()

with st.expander("Bot nasıl çalışır?", expanded=False):
    st.markdown(f"""
1. **Bülten taraması:** Seçili liglerde (**{', '.join(ui.league_name(x) for x in s.leagues)}**) önümüzdeki
   **{s.horizon_hours:.0f} saat** içindeki maçlar alınır. Maç asla elenmez.
2. **Veri toplama:** Birleşik havuz: 16 kaynak (anahtarsız: football-data.co.uk, OpenLigaDB, openfootball,
   TheSportsDB, Wikidata, Open-Meteo, RSS, Meclis Elo; anahtarlı: API-Football, Sportmonks, football-data.org,
   FootyStats, SportDevs, The Odds API, OddsPapi, Club Elo). Eksik alan bir kaynaktan diğerine tamamlanır.
   Anahtarı gelmemiş kaynaklar aşağıdaki tabloda **🔑 anahtar bekleniyor** diye görünür.
3. **Tamlık kapısı:** Tamlık puanı **{s.completeness_min:.0f}/100** altındaysa veya takım geçmişi
   **{s.min_team_matches}** maçtan azsa tahmin **Karar Bekliyor** olur ve yeniden denenir. Maçtan
   **{s.min_minutes_before_kickoff:.0f} dk** önce hâlâ eksikse **Karar Verilmedi** olarak kayıtta kalır.
4. **Modeller:** Gol/skor için zaman ağırlıklı **Dixon-Coles** (Poisson skor matrisi), Elo önseliyle (%45)
   harmanlanır; korner, kart, isabetli şut,
   kale vuruşu için takım oranları + **negatif binom/Poisson**. Sakatlıklar **Eksik Etkisi (0–100)** ile λ'ya işlenir.
5. **Seçim:** Maç başına tek **Meclis Görüşü** (piyasa oranı varsa değer ≥ %{100 * s.value_edge_min:.0f};
   yoksa olasılık ≥ %{100 * s.no_odds_min_prob:.0f}). **Günün Kararı**: 2–3 maç, toplam oran
   {s.coupon_min_odds:.2f}–{s.coupon_max_odds:.2f}. **Karar Birliği**: günde ≥ {s.consensus_min_singles} Meclis Görüşü varsa
   en güvenilen 2–3 seçim.
6. **Kilit:** Kayıtlar veritabanı tetikleyicisiyle kilitlidir: maç başladıktan sonra eklenemez, değiştirilemez, silinemez.
""")

ro = getattr(store, "read_only", False)
if ro:
    st.info("Bu uygulama Supabase'e **anon (salt okunur)** anahtarla bağlı. Tahminleri yalnızca service_role "
            "anahtarıyla çalışan zamanlanmış bot (GitHub Actions) yazar; buradan sadece kuru çalıştırma yapılabilir.")
c1, c2, c3, c4 = st.columns(4)
run_log = []
try:
    if c1.button("🔄 Havuzu yenile", disabled=s.demo_mode or ro, width="stretch"):
        with st.spinner("Kaynaklar taranıyor..."):
            r = pool.refresh(history=True)
        ui.clear_caches()
        run_log = r["log"] + [f"{r['records']} kaynak kaydı → {r['matches']} birleşik maç"]
    if c2.button("📝 Botu çalıştır (kayda yaz)", type="primary", width="stretch", disabled=ro):
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
    if c4.button("🏁 Sonuçlandır", width="stretch", disabled=ro):
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

st.subheader("Analiz kuyruğu")
q = store.select("analysis_queue")
if q:
    mm = {m["id"]: m for m in store.select("matches", [("id", "in", [x["match_id"] for x in q])])}
    df = pd.DataFrame([{
        "Başlama": tr_str(mm.get(x["match_id"], {}).get("kickoff_at")),
        "Maç": f"{mm.get(x['match_id'], {}).get('home_name', '?')} – {mm.get(x['match_id'], {}).get('away_name', '?')}",
        "Durum": QUEUE_LABELS.get(x["status"], x["status"]), "Not": x.get("note"),
        "Eksik": ", ".join(x.get("missing") or []), "Deneme": x.get("attempts"),
        "Sonraki deneme": tr_str(x.get("next_retry_at")), "_ko": mm.get(x["match_id"], {}).get("kickoff_at") or "",
    } for x in q]).sort_values("_ko", ascending=False).drop(columns="_ko")
    st.dataframe(df, hide_index=True, width="stretch")
else:
    ui.empty_state("Kuyruk boş. Botu çalıştırınca bültendeki maçlar burada görünür.")

st.subheader("Veri kaynakları")
from meclis.sources.registry import SOURCES as _REG, key_state  # noqa: E402

db_src = {x["name"]: x for x in store.select("sources")}
status = {x["source"]: x for x in store.select("source_status") if not x["source"].startswith("injuries:")}
_KEY_ICON = {"gerekmez": "✅ gerekmez", "tanımlı": "✅ tanımlı", "ücretsiz anahtar (123)": "✅ ücretsiz anahtar (123)",
             "anahtar bekleniyor": "🔑 anahtar bekleniyor"}
_rows = []
for d in _REG:
    ks = key_state(d, s)
    st_row = status.get(d.name)
    _rows.append({
        "Kaynak": d.title, "Anahtar durumu": _KEY_ICON.get(ks, ks), "Ortam değişkeni": d.api_key_secret or "—",
        "Ücretsiz katman": d.free_tier, "Kayıt / bilgi": d.signup_url or "—",
        "Doldurduğu alanlar": ", ".join(d.fills_fields),
        "Son durum": ((("✅ " if st_row["ok"] else "⚠️ ") + (st_row.get("message") or "")) if st_row else "—"),
        "Depoda kayıtlı": "evet" if d.name in db_src else "hayır (şema/tohum güncellenmeli)",
    })
waiting = [r["Ortam değişkeni"] for r in _rows if r["Anahtar durumu"].startswith("🔑")]
if waiting:
    st.warning(f"🔑 {len(waiting)} kaynak anahtar bekliyor: " + ", ".join(waiting)
               + ". Anahtar gelene kadar bu kaynakların alanları boş kalır (uydurma veri konmaz). "
               "Kayıt bağlantıları tabloda.")
st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch",
             column_config={"Kayıt / bilgi": st.column_config.LinkColumn("Kayıt / bilgi")})
st.caption("Anahtar değerleri hiçbir yerde gösterilmez; yalnızca ortam değişkeni adı tutulur.")
