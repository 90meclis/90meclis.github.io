"""Streamlit ortak yardımcıları (önbellek, uyarı bantları, biçimlendirme)."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from .config import LEAGUES, load_settings
from .markets import MARKET_LABELS, STATUS_ICONS, STATUS_LABELS, TAG_LABELS, pick_label
from .store import get_store
from .timeutil import tr_str


@st.cache_resource(show_spinner=False)
def _resources(_key: str):
    s = load_settings()
    store = get_store(s)
    from .pool import DataPool

    return s, store, DataPool(store, s)


def resources():
    s = load_settings()
    key = f"{s.demo_mode}|{s.supabase_url}|{s.local_db_path}|{','.join(s.leagues)}"
    return _resources(key)


@st.cache_resource(show_spinner=False, ttl=900)
def _bot(_key: str, _bucket: int):
    from .bot import Bot

    s, store, pool = resources()
    return Bot(store, s, pool)


def bot():
    s, store, _ = resources()
    return _bot(f"{s.demo_mode}|{s.supabase_url}|{s.local_db_path}", int(time.time() // 900))


def clear_caches():
    _bot.clear()
    st.cache_data.clear()


def banner():
    s, store, _ = resources()
    if s.demo_mode:
        st.error("🧪 **ÖRNEK VERİ MODU** — Bu sayfadaki takımlar, maçlar, oranlar ve geçmiş tahminler UYDURMADIR. "
                 "Gerçek veri için `DEMO_MODE` değişkenini kaldırın.", icon="⚠️")
        return
    if not s.supabase_enabled:
        st.warning("Supabase bağlı değil (SUPABASE_URL / SUPABASE_KEY yok). Veriler bu makinedeki yerel SQLite "
                   "dosyasında tutuluyor; paylaşılmaz ve Streamlit Cloud'da kalıcı değildir.", icon="🗄️")
    # Anahtarlar veri toplayan işte (GitHub Actions) tanımlıdır; arayüz yalnızca okur. Bu yüzden eksik anahtar
    # bilgisi uygulamanın kendi ortamından değil, havuzun yazdığı kaynak durumundan okunur.
    missing = _waiting_keys(store)
    if missing:
        st.caption("🔑 Anahtar bekleyen kaynaklar: " + ", ".join(missing) +
                   " — bu kaynakların verisi gelmiyor, yerine uydurma veri KONMAZ (diğer kaynaklar boşluğu doldurur).")


@st.cache_data(ttl=600, show_spinner=False)
def _waiting_keys(_store) -> list[str]:
    try:
        rows = _store.select("source_status")
    except Exception:
        return []
    return sorted({r["source"] for r in rows if str(r.get("message") or "").startswith("anahtar bekleniyor")})


def league_name(code: str) -> str:
    return LEAGUES[code].name if code in LEAGUES else code


def status_badge(status: str) -> str:
    return f"{STATUS_ICONS.get(status, '')} {STATUS_LABELS.get(status, status)}"


def predictions_table(rows: list[dict]) -> pd.DataFrame:
    out = []
    for p in rows:
        out.append({
            "Başlama (TSİ)": tr_str(p["kickoff_at"]), "Etiket": TAG_LABELS.get(p["tag"], p["tag"]),
            "Maç": f"{p['home_name']} – {p['away_name']}",
            "Seçim": pick_label(p["market"], p["selection"], p.get("line"), p["home_name"], p["away_name"]),
            "Pazar": MARKET_LABELS.get(p["market"], p["market"]), "Olasılık %": round(100 * p["probability"], 1),
            "Oran": p.get("odds"), "Oran türü": "piyasa" if p.get("odds") else "yalnızca adil oran",
            "Adil oran": p.get("fair_odds"), "Durum": status_badge(p["status"]), "Sonuç": p.get("result_value") or "",
            "Kâr (birim)": p.get("profit"), "Kayıt zamanı": tr_str(p.get("recorded_at"), "%d.%m %H:%M:%S"),
        })
    return pd.DataFrame(out)


def empty_state(msg: str):
    st.info(msg, icon="ℹ️")
