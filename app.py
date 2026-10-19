"""90 Meclis — Streamlit giriş noktası.  Çalıştırma: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="90 Meclis", page_icon="⚽", layout="wide")

pages = [
    st.Page("views/mac_merkezi.py", title="Maç Merkezi", icon="🏟️", default=True),
    st.Page("views/tahmin_botu.py", title="Tahmin Botu", icon="🤖"),
    st.Page("views/tahmin_arsivi.py", title="Tahmin Arşivi", icon="🗂️"),
    st.Page("views/veri_laboratuvari.py", title="Veri Laboratuvarı", icon="🧪"),
    st.Page("views/gundem_masasi.py", title="Gündem Masası", icon="📰"),
    st.Page("views/guven_panosu.py", title="Güven Panosu", icon="🛡️"),
]
# Yönetim / tanılama sayfası ziyaretçi menüsünde yok: ?yonetim=1 ile açılır
if st.query_params.get("yonetim") == "1" or st.session_state.get("yonetim"):
    st.session_state["yonetim"] = True
    pages.append(st.Page("views/sistem.py", title="Sistem Durumu", icon="🔧"))
nav = st.navigation(pages)
with st.sidebar:
    st.markdown("### ⚽ 90 Meclis")
    st.caption("Her şey tek masada · kayıtlar değiştirilemez · kayıplar da görünür.")
    st.caption("Bu uygulama olasılık tahmini sunar; garanti vermez. 18 yaş altı için değildir.")
nav.run()
