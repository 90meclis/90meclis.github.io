"""90 Meclis — Streamlit giriş noktası.  Çalıştırma: streamlit run app.py"""
import hmac

import streamlit as st

from meclis.config import get_setting

st.set_page_config(page_title="90 Meclis", page_icon="⚽", layout="wide")

pages = [
    st.Page("views/ana_sayfa.py", title="Ana Sayfa", icon="⚽", default=True),
    st.Page("views/mac_merkezi.py", title="Maç Merkezi", icon="🏟️"),
    st.Page("views/tahmin_botu.py", title="Tahmin Botu", icon="🤖"),
    st.Page("views/tahmin_arsivi.py", title="Tahmin Arşivi", icon="🗂️"),
    st.Page("views/veri_laboratuvari.py", title="Veri Laboratuvarı", icon="🧪"),
    st.Page("views/gundem_masasi.py", title="Gündem Masası", icon="📰"),
    st.Page("views/guven_panosu.py", title="Güven Panosu", icon="🛡️"),
]

# Yönetim: yalnızca ADMIN_TOKEN (Streamlit secret / ortam değişkeni) tanımlıysa ve girilen değer eşleşirse açılır.
# Tanımlı değilse yönetim alanı hiç yoktur. Ziyaretçi menüsünde ve sayfalarda iz bırakmaz.
_token = get_setting("ADMIN_TOKEN") or ""
if not _token:
    st.session_state["is_admin"] = False
elif not st.session_state.get("is_admin") and "yonetim" in st.query_params:
    with st.sidebar:
        _given = st.text_input("Yönetici anahtarı", type="password", key="_admin_try")
    if _given and hmac.compare_digest(_given.encode(), _token.encode()):
        st.session_state["is_admin"] = True
        st.session_state.pop("_admin_try", None)
if st.session_state.get("is_admin"):
    pages.append(st.Page("views/sistem.py", title="Sistem Durumu", icon="🔧"))

nav = st.navigation(pages)
with st.sidebar:
    st.markdown("### ⚽ 90 Meclis")
    st.caption("Her şey tek masada · kayıtlar değiştirilemez · kayıplar da görünür.")
    st.caption("Bu uygulama olasılık tahmini sunar; garanti vermez. 18 yaş altı için değildir.")
    if st.session_state.get("is_admin") and st.button("Yönetimden çık"):
        st.session_state["is_admin"] = False
        st.rerun()
nav.run()
