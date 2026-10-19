import streamlit as st

from meclis import ui
from meclis.markets import TAG_LABELS, pick_label
from meclis.timeutil import tr_str

st.title("🗂️ Tahmin Arşivi")
st.caption("Etiketli, kilitli kayıtlar: Günün Kararı · Meclis Görüşü · Karar Birliği. Durum: bekliyor, başladı, kazandı, kaybetti, iade.")
ui.banner()
s, store, pool = ui.resources()

preds = store.select("predictions", order="kickoff_at", desc=True)
coupons = store.select("coupons", order="coupon_date", desc=True)

# Günün masası: Günün Kararı vitrinde, sonra Meclis Görüşleri (Günün Kararı'ndaki maçlar hariç), sonra Karar Birliği.
_days = sorted({str(c["coupon_date"]) for c in coupons} | {tr_str(p["kickoff_at"], "%Y-%m-%d") for p in preds})
if _days:
    from meclis.pool import today_tr

    _t = today_tr().isoformat()
    _focus = next((d for d in _days if d >= _t), _days[-1])
    st.subheader(("Bugünün masası" if _focus == _t else f"Masa · {_focus}"))
    _gk = [c for c in coupons if str(c["coupon_date"]) == _focus and c["tag"] == "gunun_karari"]
    _gk_m = set()
    for c in _gk:
        legs = [p for p in preds if p.get("coupon_id") == c["id"]]
        _gk_m |= {p["match_id"] for p in legs}
        with st.container(border=True):
            st.markdown(f"#### 🎯 Günün Kararı · {len(legs)} maç · toplam oran **{c['total_odds']:.2f}** · {ui.status_badge(c['status'])}")
            for p in legs:
                st.markdown(f"- {tr_str(p['kickoff_at'], '%H:%M')} **{p['home_name']} – {p['away_name']}**: "
                            f"{pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])} "
                            f"({(p.get('odds') or p.get('fair_odds') or 0):.2f}) {ui.status_badge(p['status'])}")
            st.caption("Maçlardan önce kilitlendi · 18+ · garanti yoktur")
    if not _gk:
        st.info("Bu gün için Günün Kararı kurulmadı: 2,30–4,00 bandında yeterince değerli 2–3 maçlık kombinasyon çıkmadı.")
    _ss = [p for p in preds if p["tag"] == "meclis_gorusu" and tr_str(p["kickoff_at"], "%Y-%m-%d") == _focus and p["match_id"] not in _gk_m]
    st.markdown(f"#### 🗳️ Meclis Görüşleri · {len(_ss)}")
    if _ss:
        st.dataframe(ui.predictions_table(_ss), hide_index=True, width="stretch")
    else:
        st.caption("Günün Kararı dışında tekli görüş yok.")
    for c in [c for c in coupons if str(c["coupon_date"]) == _focus and c["tag"] == "karar_birligi"]:
        st.markdown(f"#### 🤝 Karar Birliği · toplam oran **{c['total_odds']:.2f}** · {ui.status_badge(c['status'])}")
        st.dataframe(ui.predictions_table([p for p in preds if p.get("coupon_id") == c["id"]]), hide_index=True, width="stretch")
    st.divider()
st.subheader("📚 Geçmiş: kilitli defter")
c1, c2, c3 = st.columns(3)
tags = c1.multiselect("Etiket", list(TAG_LABELS), default=list(TAG_LABELS), format_func=TAG_LABELS.get)
statuses = c2.multiselect("Durum", ["bekliyor", "basladi", "kazandi", "kaybetti", "iade"],
                          default=["bekliyor", "basladi", "kazandi", "kaybetti", "iade"], format_func=ui.status_badge)
_rdays = sorted({tr_str(p["kickoff_at"], "%Y-%m-%d") for p in preds})
if _rdays:
    from datetime import date

    _lo, _hi = date.fromisoformat(_rdays[0]), date.fromisoformat(_rdays[-1])
    rng = c3.date_input("Tarih aralığı", value=(_lo, _hi), min_value=_lo, max_value=_hi, format="DD.MM.YYYY")
    d_lo, d_hi = (rng[0], rng[-1]) if isinstance(rng, (tuple, list)) and rng else (_lo, _hi)
    preds = [p for p in preds if d_lo.isoformat() <= tr_str(p["kickoff_at"], "%Y-%m-%d") <= d_hi.isoformat()]
    coupons = [c for c in coupons if d_lo.isoformat() <= str(c["coupon_date"]) <= d_hi.isoformat()]

st.subheader("🎫 Kuponlar")
if not coupons:
    ui.empty_state("Henüz kupon yok. Günün Kararı yalnızca toplam oran bandında değerli bir kombinasyon bulunursa kurulur.")
for c in coupons:
    if c["tag"] not in tags or c["status"] not in statuses:
        continue
    legs = [p for p in preds if p.get("coupon_id") == c["id"]]
    title = (f"{TAG_LABELS[c['tag']]} · {c['coupon_date']} · {len(legs)} maç · toplam oran {c['total_odds']:.2f}"
             f"{' (adil oran)' if c.get('odds_source') == 'model_adil' else ''} · {ui.status_badge(c['status'])}")
    with st.expander(title, expanded=c["status"] in ("bekliyor", "basladi")):
        st.dataframe(ui.predictions_table(legs).drop(columns=["Etiket"]), hide_index=True, width="stretch")
        st.caption(f"Ortak olasılık %{100 * (c.get('joint_probability') or 0):.1f} · {c.get('note') or ''} · "
                   f"kâr: {c.get('profit') if c.get('profit') is not None else '—'} birim · kayıt: {tr_str(c.get('created_at'))}")

st.subheader("🗳️ Tekli kayıtlar")
singles = [p for p in preds if p["tag"] in tags and p["status"] in statuses and (p["tag"] == "meclis_gorusu" or not p.get("coupon_id"))]
if singles:
    df = ui.predictions_table(singles)
    st.dataframe(df, hide_index=True, width="stretch")
    with st.expander("Gerekçeler ve senaryo notları"):
        for p in singles[:100]:
            st.markdown(f"**{p['home_name']} – {p['away_name']}** · "
                        f"{pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])}: "
                        f"{p.get('rationale') or ''}  \n_Senaryolar:_ {p.get('scenario_note') or '—'}")
else:
    ui.empty_state("Seçili filtrelerde tekli kayıt yok.")

st.caption("Kayıtlar veritabanı tetikleyicileriyle kilitlidir: maç başladıktan sonra eklenemez; seçim, oran ve olasılık "
           "değiştirilemez; kayıt silinemez. Yalnızca durum/sonuç alanları otomatik güncellenir.")
