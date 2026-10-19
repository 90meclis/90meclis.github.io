import pandas as pd
import streamlit as st

from meclis import trust, ui

st.title("🛡️ Güven Panosu")
st.caption("Arşivin herkese açık yüzü: haftalık kayıt, isabet, 1 birim sabit stake ile kâr/zarar, pazar kırılımı — kayıplar dahil.")
ui.banner()
s, store, pool = ui.resources()

df = trust.predictions_frame(store.select("predictions"))
if df.empty:
    ui.empty_state("Henüz kayıt yok. İlk tahminler maçtan önce deftere düştüğünde burada görünecek.")
    st.stop()
singles = df[df["tag"] == "meclis_gorusu"]
tot = trust.summarize(singles)
k = st.columns(6)
k[0].metric("Meclis Görüşü", tot["toplam"], f"{tot['bekleyen']} bekliyor", delta_color="off")
k[1].metric("Kazanan / Kaybeden", f"{tot['kazanan']} / {tot['kaybeden']}", f"{tot['iade']} iade", delta_color="off")
k[2].metric("İsabet", f"%{100 * tot['isabet']:.1f}" if tot["isabet"] is not None else "—")
k[3].metric("Kâr (birim)", f"{tot['kâr']:+.2f}", f"{tot['piyasa_oranlı']} piyasa oranlı", delta_color="off")
k[4].metric("ROI", f"%{100 * tot['roi']:+.1f}" if tot["roi"] is not None else "—")
k[5].metric("Brier", f"{tot['brier']:.3f}" if tot["brier"] is not None else "—", help="Düşük = daha iyi kalibrasyon")
if tot.get("clv") is not None:
    st.caption(f"Ortalama CLV (kapanış oranına göre): %{100 * tot['clv']:+.2f} · {tot['clv_n']} tahmin")

st.subheader("Kasa eğrisi (piyasa oranlı tekliler, 1 birim)")
eq = trust.equity_curve(singles)
if not eq.empty:
    st.line_chart(eq.set_index("kickoff"))
else:
    st.caption("Henüz piyasa oranlı sonuçlanmış tahmin yok.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Haftalık kayıt")
    st.dataframe(trust.breakdown(singles, "hafta").sort_values("hafta", ascending=False), hide_index=True, width="stretch")
with c2:
    st.subheader("Pazar bazında")
    st.dataframe(trust.breakdown(singles, "pazar"), hide_index=True, width="stretch")

st.subheader("Etiket bazında (kupon bacakları dahil)")
st.dataframe(trust.breakdown(df, "etiket"), hide_index=True, width="stretch")
cp = store.select("coupons")
if cp:
    cdf = pd.DataFrame(cp)
    rows = []
    for tag, g in cdf.groupby("tag"):
        done = g[g["status"].isin(["kazandi", "kaybetti", "iade"])]
        rows.append({"Kupon": {"gunun_karari": "Günün Kararı", "karar_birligi": "Karar Birliği"}[tag], "Kupon sayısı": len(g),
                     "Kazanan": int((done["status"] == "kazandi").sum()), "Kaybeden": int((done["status"] == "kaybetti").sum()),
                     "Kâr (birim)": round(pd.to_numeric(done["profit"], errors="coerce").fillna(0).sum(), 2)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

st.subheader("Kalibrasyon")
cal = trust.calibration(singles)
if cal.empty:
    st.caption("Yeterli sonuç yok.")
else:
    st.dataframe(cal, hide_index=True)

st.subheader("Son kayıplar (gizlenmez)")
lost = df[df["status"] == "kaybetti"].sort_values("kickoff", ascending=False).head(15)
if not lost.empty:
    st.dataframe(ui.predictions_table(lost.to_dict("records")), hide_index=True, width="stretch")
else:
    st.caption("Henüz kaybeden kayıt yok.")

with st.expander("Ölçütler nasıl hesaplanıyor?"):
    st.markdown("""
- **İsabet** = kazanan / (kazanan + kaybeden); iadeler hariç.
- **Kâr / ROI** yalnızca kayıt anında **piyasa oranı** olan tahminlerde, 1 birim sabit stake ile hesaplanır.
  Piyasa oranı olmayan (yalnızca modelin adil oranı olan) tahminler isabete dahildir, kâr/zarara dahil **değildir** —
  adil oranla kâr hesaplamak gerçeği yansıtmaz.
- **Brier skoru** olasılıkların ne kadar isabetli kalibre edildiğini ölçer.
- **CLV**: alınan oran / kapanış oranı − 1 (football-data.co.uk kapanış oranları).
- Kayıtlar değiştirilemez: maç başladıktan sonra ekleme, düzenleme ve silme veritabanı tetikleyicisiyle engellenir.
""")
