"""Yönetim / tanılama sayfası — yalnızca ADMIN_TOKEN eşleşen yöneticiye görünür (app.py)."""
import pandas as pd
import streamlit as st

from meclis import ui
from meclis.coverage import COLS, upcoming_coverage
from meclis.sources.registry import SOURCES as _REG

if not st.session_state.get("is_admin"):
    st.stop()
st.title("🔧 Sistem Durumu")
st.caption("Geliştirici / yönetici görünümü: kaynak sağlığı, anahtar bekleyen kaynaklar ve veri kapsamı.")
s, store, pool = ui.resources()
ro = getattr(store, "read_only", False)
st.write(f"Depo: **{store.label}** · Ligler: {len(s.leagues)} ({', '.join(s.leagues)})")
if ro:
    st.caption("Arayüz salt okunur anahtarla bağlı; veri toplama ve tahmin defteri GitHub Actions'taki bot ile yazılır. "
               "Kaynak durumları botun yazdığı `v_kaynak_durumu` görünümünden okunur.")

st.subheader("Önümüzdeki 7 günün veri kapsamı")
cov = upcoming_coverage(store, s.leagues)
st.dataframe(pd.DataFrame([{"Lig": ui.league_name(lg), **{n: c[k or "maç"] for n, k in COLS},
                            "Eksik kaydı": c["eksik kaydı"], "Tahmini ilk 11 tarafı": c["tahmini"],
                            "Resmî ilk 11 tarafı": c["resmi"]} for lg, c in cov.items()]),
             hide_index=True, width="stretch")

st.subheader("Veri kaynakları")
try:
    rows = store.select("source_status")
except Exception:
    rows = []
status = {x["source"]: x for x in rows if not x["source"].startswith(("injuries:", "gecmis:", "api-football:tarih:"))}
_rows = []
for d in _REG:
    st_row = status.get(d.name)
    msg = (st_row or {}).get("message") or ""
    waiting = msg.startswith("anahtar bekleniyor")
    _rows.append({
        "Kaynak": d.title,
        "Durum": "🔑 anahtar bekleniyor" if waiting else ("✅ çalışıyor" if st_row and st_row.get("ok") else
                                                          "⚠️ sorun" if st_row else "—"),
        "Ortam değişkeni": d.api_key_secret or "—", "Ücretsiz katman": d.free_tier,
        "Kayıt / bilgi": d.signup_url or "—", "Doldurduğu alanlar": ", ".join(d.fills_fields),
        "Son mesaj": msg[:300], "Güncelleme": (st_row or {}).get("updated_at"),
    })
waiting = [r["Ortam değişkeni"] for r in _rows if r["Durum"].startswith("🔑")]
if waiting:
    st.warning(f"🔑 {len(waiting)} kaynak anahtar bekliyor: " + ", ".join(waiting)
               + ". Anahtar GitHub Actions secret'ı olarak eklenince bot bu kaynakları da kullanır.")
st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch",
             column_config={"Kayıt / bilgi": st.column_config.LinkColumn("Kayıt / bilgi")})
st.caption("Anahtar değerleri hiçbir yerde gösterilmez; yalnızca ortam değişkeni adı tutulur.")
