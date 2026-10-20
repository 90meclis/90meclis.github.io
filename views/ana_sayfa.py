"""Açılış sayfası: marka, Günün Kararı, bugünün maçları, Güven Panosu özeti, gündem ve bölümler."""
import streamlit as st

from meclis import trust, ui
from meclis.markets import pick_label
from meclis.pool import today_tr
from meclis.timeutil import day_bounds_utc, tr_str

st.title("⚽ 90 Meclis")
st.markdown("### Her şey tek masada.")
st.markdown("90 Meclis her maçı veriyle tartışır: kadro, eksik, form, istatistik, hava ve piyasa. Değer gördüğü yerde "
            "kararını maçtan saatler önce verir ve kilitler; kazancı da kaybı da herkesin önünde tutar.")
ui.banner()
s, store, pool = ui.resources()
today = today_tr()
preds = store.select("predictions")
coupons = store.select("coupons")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown("#### 🎯 Günün Kararı")
        gk = sorted([c for c in coupons if c["tag"] == "gunun_karari" and str(c["coupon_date"]) >= today.isoformat()],
                    key=lambda c: str(c["coupon_date"]))
        if gk:
            c = gk[0]
            legs = [p for p in preds if p.get("coupon_id") == c["id"]]
            st.markdown(f"**{c['coupon_date']}** · {len(legs)} maç · toplam oran **{c['total_odds']:.2f}** · {ui.status_badge(c['status'])}")
            for p in legs:
                st.markdown(f"- {tr_str(p['kickoff_at'], '%H:%M')} {p['home_name']} – {p['away_name']}: "
                            f"**{pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])}**")
        else:
            st.caption("Meclis'in ana tercihlerinden oluşan günün kuponu.")
        st.page_link("views/tahmin_arsivi.py", label="Masaya git →")
with c2:
    with st.container(border=True):
        st.markdown("#### 🛡️ Güven Panosu")
        # Sitedekiyle aynı sayım: kupon = 1 kayıt; Günün Kararı ayağı olan maçın teklisi ayrıca sayılmaz.
        singles = trust.public_singles(preds)
        settled = [p for p in singles if p["status"] in ("kazandi", "kaybetti")]
        won = sum(p["status"] == "kazandi" for p in settled)
        k1, k2 = st.columns(2)
        k1.metric("Kilitli karar", len(singles) + len(coupons), help="Tekli görüşler + kuponlar (her kupon tek kayıt)")
        k2.metric("Tekli isabet", f"%{100 * won / len(settled):.1f}" if settled else "—", f"{won}/{len(settled)}", delta_color="off")
        st.page_link("views/guven_panosu.py", label="Tüm kayıt →")

with st.container(border=True):
    lo, hi = day_bounds_utc(today)
    ms = store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)], order="kickoff_at")
    st.markdown(f"#### 🏟️ Bugünün maçları · {len(ms)}")
    for m in ms[:8]:
        st.markdown(f"- {tr_str(m['kickoff_at'], '%H:%M')} · {ui.league_name(m['league'])} · **{m['home_name']} – {m['away_name']}**")
    if not ms:
        st.caption("Bugün bültende maç yok.")
    st.page_link("views/mac_merkezi.py", label="Maç Merkezi →")

with st.container(border=True):
    st.markdown("#### 📰 Gündem")
    seen, shown = [], 0
    for n in store.select("agenda", order="published_at", desc=True, limit=60):
        key = set((n.get("title") or "").lower().split())
        if any(key and k and len(key & k) / len(key | k) >= 0.6 for k in seen):
            continue
        seen.append(key)
        st.markdown(f"- [{n['title']}]({n['link']}) · {n.get('source')}")
        shown += 1
        if shown >= 5:
            break
    st.page_link("views/gundem_masasi.py", label="Tüm gündem →")

st.markdown("#### Bölümler")
cols = st.columns(3)
for i, (path, label, desc) in enumerate([
    ("views/mac_merkezi.py", "🏟️ Maç Merkezi", "Kadro, ağırlıklı eksikler, form, istatistik, hava ve senaryolar."),
    ("views/tahmin_botu.py", "🤖 Ortak", "Meclis'in yapay zekâ analisti: bütün maçlar, bütün pazarlar, model ↔ piyasa."),
    ("views/tahmin_arsivi.py", "🗂️ Tahmin Arşivi", "Günün Kararı, Meclis Görüşleri, Karar Birliği ve kilitli defter."),
    ("views/guven_panosu.py", "🛡️ Güven Panosu", "Haftalık kayıt, isabet, ROI ve pazar bazında sonuçlar."),
    ("views/gundem_masasi.py", "📰 Gündem Masası", "Transfer, sakatlık, teknik direktör gündemi."),
    ("views/veri_laboratuvari.py", "🧪 Veri Laboratuvarı", "Bu sezonun pazar ligleri ve maç maç seriler."),
]):
    with cols[i % 3]:
        st.page_link(path, label=label)
        st.caption(desc)
st.caption("18+ · Tahminler olasılık hesabıdır; garanti vermez.")
