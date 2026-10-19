"""Güven Panosu. Kâr/zarar tanımı sitedekiyle (web/src/lib/trust.ts) birebir aynıdır:

* Tekliler  = Meclis Görüşü kayıtları. Kâr/ROI yalnızca kayıt anında PİYASA oranı olanlarda (1 birim). İsabet hepsinde.
* Kuponlar  = Günün Kararı / Karar Birliği kuponları, KUPON düzeyinde (ayaklar ayrı bahis sayılmaz).
              Kâr/ROI yalnızca piyasa oranlı kuponlarda (odds_source = 'piyasa').
* Toplam    = tekliler + kuponlar.
* ROI       = kâr / piyasa oranlı, iade olmayan sonuçlanmış bahis sayısı.  İsabet = kazanan / (kazanan + kaybeden).
* Eğri sırası: tekliler başlama saatine, kuponlar ilk maçın başlama saatine göre.
"""
import pandas as pd
import streamlit as st

from meclis import trust, ui
from meclis.markets import MARKET_LABELS

st.title("🛡️ Güven Panosu")
st.caption("Arşivin herkese açık yüzü: isabet, 1 birim sabit stake ile kâr/zarar, kasa eğrisi ve kırılımlar — kayıplar dahil. "
           "Tekliler ve kuponlar ayrı, toplam ayrıca gösterilir.")
ui.banner()
s, store, pool = ui.resources()

DONE = ("kazandi", "kaybetti", "iade")


def bets_frame(preds: list[dict], coupons: list[dict]) -> pd.DataFrame:
    rows = []
    for p in preds:
        if p["tag"] != "meclis_gorusu":
            continue
        rows.append({"tür": "Tekli", "t": p["kickoff_at"], "status": p["status"], "priced": p.get("odds") is not None,
                     "profit": p.get("profit"), "league": p.get("league"), "market": p["market"]})
    for c in coupons:
        rows.append({"tür": "Kupon", "t": c["first_kickoff_at"], "status": c["status"],
                     "priced": c.get("odds_source") == "piyasa", "profit": c.get("profit"), "league": None,
                     "market": {"gunun_karari": "Günün Kararı", "karar_birligi": "Karar Birliği"}.get(c["tag"], c["tag"])})
    df = pd.DataFrame(rows, columns=["tür", "t", "status", "priced", "profit", "league", "market"])
    if not df.empty:
        df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert("Europe/Istanbul")
        df["profit"] = pd.to_numeric(df["profit"], errors="coerce")
    return df


def summ(g: pd.DataFrame) -> dict:
    done = g[g["status"].isin(DONE)]
    won, lost = int((done["status"] == "kazandi").sum()), int((done["status"] == "kaybetti").sum())
    priced = done[done["priced"] & (done["status"] != "iade")]
    profit = float(priced["profit"].fillna(0).sum())
    return {"Bahis": len(g), "Bekleyen": int((~g["status"].isin(DONE)).sum()), "Kazanan": won, "Kaybeden": lost,
            "İade": int((done["status"] == "iade").sum()),
            "İsabet %": round(100 * won / (won + lost), 1) if won + lost else None,
            "Kâr (birim)": round(profit, 2) if len(priced) else None,
            "ROI %": round(100 * profit / len(priced), 1) if len(priced) else None, "Piyasa oranlı": len(priced)}


def table(df: pd.DataFrame, key, label: str) -> pd.DataFrame:
    return pd.DataFrame([{label: k, **summ(g)} for k, g in df.groupby(key, sort=True)])


preds = store.select("predictions")
coupons = store.select("coupons")
bets = bets_frame(preds, coupons)
if bets.empty:
    ui.empty_state("Henüz kayıt yok. İlk tahminler maçtan önce deftere düştüğünde burada görünecek.")
    st.stop()
singles, cps = bets[bets["tür"] == "Tekli"], bets[bets["tür"] == "Kupon"]

st.subheader("Özet")
summary = pd.DataFrame([{"Grup": "Tekliler (Meclis Görüşü)", **summ(singles)},
                        {"Grup": "Kuponlar (Günün Kararı + Karar Birliği)", **summ(cps)},
                        {"Grup": "Toplam", **summ(bets)}])
st.dataframe(summary, hide_index=True, width="stretch")
sd = trust.summarize(trust.predictions_frame([p for p in preds if p["tag"] == "meclis_gorusu"]))
k = st.columns(3)
k[0].metric("Brier (tekliler)", f"{sd['brier']:.3f}" if sd["brier"] is not None else "—", help="Düşük = daha iyi kalibrasyon")
k[1].metric("Ortalama CLV", f"%{100 * sd['clv']:+.2f}" if sd.get("clv") is not None else "—", f"{sd.get('clv_n', 0)} tahmin", delta_color="off")
n = summ(singles)["Kazanan"] + summ(singles)["Kaybeden"]
k[2].metric("Sonuçlanan tekli", n)
if n < 30:
    st.caption(f"Örneklem küçük ({n} sonuç). Bu aşamada isabet ve ROI rastlantıya çok açıktır.")

st.subheader("Kasa eğrisi (1 birim, yalnızca piyasa oranlı)")
pr = bets[bets["status"].isin(("kazandi", "kaybetti")) & bets["priced"]].sort_values("t")
if pr.empty:
    st.caption("Henüz piyasa oranlı sonuçlanmış bahis yok.")
else:
    curve = pd.DataFrame({"zaman": pr["t"],
                          "Tekliler": pr["profit"].where(pr["tür"] == "Tekli", 0).fillna(0).cumsum(),
                          "Kuponlar": pr["profit"].where(pr["tür"] == "Kupon", 0).fillna(0).cumsum(),
                          "Toplam": pr["profit"].fillna(0).cumsum()}).set_index("zaman")
    st.line_chart(curve)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Lig bazında (tekliler)")
    st.dataframe(table(singles.assign(lig=singles["league"].map(ui.league_name)), "lig", "Lig"), hide_index=True, width="stretch")
with c2:
    st.subheader("Kupon türüne göre")
    st.dataframe(table(cps, "market", "Kupon") if not cps.empty else pd.DataFrame(), hide_index=True, width="stretch")
c3, c4 = st.columns(2)
with c3:
    st.subheader("Haftalık (tekliler)")
    w = singles.assign(hafta=singles["t"].dt.strftime("%G-H%V"))
    st.dataframe(table(w, "hafta", "Hafta").sort_values("Hafta", ascending=False), hide_index=True, width="stretch")
with c4:
    st.subheader("Pazar bazında (tekliler)")
    st.dataframe(table(singles.assign(pazar=singles["market"].map(MARKET_LABELS).fillna(singles["market"])), "pazar", "Pazar"),
                 hide_index=True, width="stretch")

st.subheader("Kalibrasyon (tekliler)")
cal = trust.calibration(trust.predictions_frame([p for p in preds if p["tag"] == "meclis_gorusu"]))
if cal.empty:
    st.caption("Yeterli sonuç yok.")
else:
    st.dataframe(cal, hide_index=True)

st.subheader("Son kayıplar (gizlenmez)")
lost = sorted([p for p in preds if p["status"] == "kaybetti"], key=lambda p: p["kickoff_at"], reverse=True)[:15]
if lost:
    st.dataframe(ui.predictions_table(lost), hide_index=True, width="stretch")
else:
    st.caption("Henüz kaybeden kayıt yok.")

with st.expander("Ölçütler nasıl hesaplanıyor?"):
    st.markdown("""
- **Tekliler**: Meclis Görüşü kayıtları. **Kuponlar**: Günün Kararı ve Karar Birliği, kupon düzeyinde
  (kupon ayakları ayrı bahis sayılmaz). **Toplam** = tekliler + kuponlar.
- **İsabet** = kazanan / (kazanan + kaybeden); iadeler hariç.
- **Kâr / ROI** yalnızca kayıt anında gerçek **piyasa oranı** olan bahislerde, 1 birim sabit stake ile.
  Yalnızca modelin adil oranı olanlar isabete dahildir, kâr/zarara dahil değildir.
- **ROI** = kâr / piyasa oranlı, iade olmayan sonuçlanmış bahis sayısı.
- **Brier skoru** olasılıkların ne kadar isabetli kalibre edildiğini ölçer. **CLV**: alınan oran / kapanış oranı − 1.
- Site (90 Meclis web) ve bu sayfa aynı tanımı kullanır.
""")
