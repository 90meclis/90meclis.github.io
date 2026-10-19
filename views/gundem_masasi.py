import pandas as pd
import streamlit as st

from meclis import ui
from meclis.pool import today_tr
from meclis.timeutil import day_bounds_utc, tr_str

st.title("📰 Gündem Masası")
st.caption("Her sabah ücretsiz RSS akışları taranır: transfer, sakatlık, teknik direktör kararları. Haberler takım adı eşleşmesiyle günün maçlarına bağlanır.")
ui.banner()
s, store, pool = ui.resources()

if st.button("📡 Gündemi şimdi tara", disabled=s.demo_mode):
    from meclis.news import scan_news

    with st.spinner("Akışlar okunuyor..."):
        r = scan_news(store, s)
    st.code("\n".join(r["log"]), language=None)
st.caption("Akışlar: " + " · ".join(s.news_feeds) + " — yalnızca başlık, kısa özet ve bağlantı saklanır.")

news = store.select("agenda", order="published_at", desc=True, limit=500)
if not news:
    ui.empty_state("Henüz haber yok. 'Gündemi şimdi tara' ile başla (GitHub Actions her sabah otomatik tarar).")
    st.stop()
cats = sorted({n.get("category") or "genel" for n in news})
c1, c2 = st.columns([2, 1])
sel = c1.multiselect("Kategori", cats, default=[c for c in cats if c != "genel"] or cats)
only_linked = c2.toggle("Yalnızca maça bağlı haberler", value=False)

lo, hi = day_bounds_utc(today_tr())
from datetime import timedelta  # noqa: E402

from meclis.timeutil import parse_dt, to_iso  # noqa: E402

matches = pool.matches_between(lo, to_iso(parse_dt(hi) + timedelta(days=1)), s.leagues)
st.subheader("Bugün ve yarının maçları ile bağlantılı gündem")
any_ = False
for m in matches:
    linked = [n for n in news if m["id"] in (n.get("match_ids") or []) and (n.get("category") or "genel") in sel]
    if not linked:
        continue
    any_ = True
    with st.expander(f"{tr_str(m['kickoff_at'], '%d.%m %H:%M')} · {m['home_name']} – {m['away_name']} · {len(linked)} haber"):
        for n in linked[:15]:
            st.markdown(f"- **[{n.get('category')}]** [{n['title']}]({n['link']}) · {n.get('source')} · {tr_str(n.get('published_at'))}")
            if n.get("impact_note"):
                st.caption(f"↳ Etki notu: {n['impact_note']}")
if not any_:
    st.caption("Bugün/yarın oynanacak maçlarla eşleşen haber bulunamadı.")

st.subheader("Tüm gündem")
rows = [n for n in news if (n.get("category") or "genel") in sel and (not only_linked or n.get("match_ids"))]
st.dataframe(pd.DataFrame([{"Zaman": tr_str(n.get("published_at")), "Kategori": n.get("category"), "Başlık": n["title"],
                            "Kaynak": n.get("source"), "Bağlı maç": len(n.get("match_ids") or []), "Bağlantı": n["link"]}
                           for n in rows]), hide_index=True, width="stretch",
             column_config={"Bağlantı": st.column_config.LinkColumn("Bağlantı")})
st.caption("Eşleştirme otomatik ve basittir (takım adı geçiyor mu); yanlış bağlantı olabilir. Haberler model girdisi değildir; "
           "sakatlık verisi modele yalnızca API-Football listesinden girer.")
