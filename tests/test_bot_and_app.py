import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["mac_merkezi", "tahmin_botu", "tahmin_arsivi", "veri_laboratuvari", "gundem_masasi", "guven_panosu"]


@pytest.fixture()
def demo_env(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    import streamlit as st

    import meclis.store as S

    S._STORE_CACHE.clear()
    st.cache_resource.clear()
    yield
    S._STORE_CACHE.clear()
    st.cache_resource.clear()


def test_demo_bot_pipeline(demo_env):
    from meclis.config import load_settings
    from meclis.store import get_store

    st = get_store(load_settings())
    preds = st.select("predictions")
    open_ = [p for p in preds if p["status"] == "bekliyor"]
    assert open_, "bot açık tahmin üretmeli"
    assert all(p["recorded_at"] < p["kickoff_at"] for p in open_)       # maçtan ÖNCE kayıt
    for c in st.select("coupons", [("tag", "eq", "gunun_karari")]):
        assert 2.30 <= c["total_odds"] <= 4.00
    assert st.select("trends") and st.select("sources")
    assert all(q["status"] in ("tamamlandi", "ertelendi", "yetismedi", "bekliyor") for q in st.select("analysis_queue"))


def test_missing_data_postpones_not_drops(demo_env):
    from datetime import timedelta

    from meclis.bot import Bot
    from meclis.config import load_settings
    from meclis.store import get_store
    from meclis.timeutil import now_utc, to_iso

    s = load_settings()
    st = get_store(s)
    ko = to_iso(now_utc() + timedelta(hours=6))
    st.upsert("matches", [{"id": "DEMO:yeni", "league": "DEMO", "kickoff_at": ko, "home_team_id": "DEMO:yenitakim1",
                           "away_team_id": "DEMO:yenitakim2", "home_name": "Yeni Takım Bir (örnek)",
                           "away_name": "Yeni Takım İki (örnek)", "status": "planlandi"}])
    Bot(st, s).run(record=True, fetch_extras=False)
    q = st.get("analysis_queue", match_id="DEMO:yeni")
    assert q["status"] == "ertelendi" and q["missing"] and "Karar Bekliyor" in q["note"]
    assert not st.select("predictions", [("match_id", "eq", "DEMO:yeni")])
    assert st.get("matches", id="DEMO:yeni")  # maç havuzda duruyor
    # başlamaya 15 dk kala hâlâ eksik → Karar Verilmedi
    Bot(st, s).run(record=True, now=now_utc() + timedelta(hours=5, minutes=50), fetch_extras=False)
    assert st.get("analysis_queue", match_id="DEMO:yeni")["status"] == "yetismedi"


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_in_demo(demo_env, page):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "views" / f"{page}.py"), default_timeout=90).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("ÖRNEK VERİ" in e.value for e in at.error)  # örnek veri uyarısı her sayfada


def test_match_detail_renders(demo_env):
    from streamlit.testing.v1 import AppTest

    import meclis.store as S

    at = AppTest.from_file(str(ROOT / "views" / "mac_merkezi.py"), default_timeout=90).run()
    st = list(S._STORE_CACHE.values())[0]
    from meclis.timeutil import now_utc, tr_date

    m0 = st.select("matches", [("status", "eq", "planlandi"), ("kickoff_at", "gte", now_utc().isoformat())],
                   order="kickoff_at")[0]
    at.date_input[0].set_value(tr_date(m0["kickoff_at"]))
    at.run()
    at.selectbox(key="mm_pick").set_value(m0["id"])
    at.run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Veri tamlığı" in labels
    assert any("Maç konuşuyor" in md.value for md in at.markdown)


def test_no_keys_message_without_demo(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    import streamlit as st

    import meclis.store as S

    S._STORE_CACHE.clear()
    st.cache_resource.clear()
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("LOCAL_DB_PATH", str(tmp_path / "bos.db"))
    at = AppTest.from_file(str(ROOT / "views" / "guven_panosu.py"), default_timeout=60).run()
    assert not at.exception
    assert any("Supabase bağlı değil" in w.value for w in at.warning)
    assert any("Henüz" in i.value for i in at.info)
    assert not any("ÖRNEK VERİ" in e.value for e in at.error)
    S._STORE_CACHE.clear()
    st.cache_resource.clear()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_streamlit_server_boots_headless():
    port = _free_port()
    env = dict(os.environ, DEMO_MODE="1")
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"), "--server.headless", "true",
                             "--server.port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        ok = False
        for _ in range(60):
            try:
                r = requests.get(f"http://127.0.0.1:{port}/_stcore/health", timeout=2)
                if r.status_code == 200 and r.text.strip() == "ok":
                    ok = True
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        assert ok, "Streamlit sağlık kontrolü başarısız"
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def test_dry_run_writes_nothing(demo_env):
    from meclis.bot import Bot
    from meclis.config import load_settings
    from meclis.store import get_store

    s = load_settings()
    st = get_store(s)
    before = {t: st.select(t) for t in ("predictions", "coupons", "analysis_queue", "analyses")}
    Bot(st, s).run(record=False, fetch_extras=False)
    assert {t: st.select(t) for t in before} == before


def test_read_only_key_detection(monkeypatch):
    import base64
    import json

    from meclis.store import key_is_read_only

    monkeypatch.delenv("SUPABASE_READONLY", raising=False)

    def jwt(role):
        body = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
        return f"eyJhbGciOiJIUzI1NiJ9.{body}.imza"

    assert key_is_read_only(jwt("anon")) and not key_is_read_only(jwt("service_role"))
    assert key_is_read_only("sb_publishable_xxx") and not key_is_read_only("sb_secret_xxx")
    monkeypatch.setenv("SUPABASE_READONLY", "1")
    assert key_is_read_only("sb_secret_xxx")
