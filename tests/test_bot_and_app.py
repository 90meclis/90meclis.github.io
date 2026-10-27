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
    r = Bot(st, s).run(record=True, fetch_extras=False)
    q = st.get("analysis_queue", match_id="DEMO:yeni")
    # eksik veri analizi durdurmaz: maç analiz edilir; değer iddiası kurulamadığı için yayımlanmaz, yeniden hesaplanır
    assert q["status"] == "bekliyor" and "yeniden hesaplanacak" in q["note"]
    assert "Karar" not in q["note"]
    assert st.select("analyses", [("match_id", "eq", "DEMO:yeni")])
    assert not st.select("predictions", [("match_id", "eq", "DEMO:yeni")])
    assert st.get("matches", id="DEMO:yeni")  # maç havuzda duruyor
    assert r["postponed"] == 0
    # başlamaya 3 saatten az kala yeni yayın yapılmaz, 'yetismedi' gibi bir durum da yazılmaz
    Bot(st, s).run(record=True, now=now_utc() + timedelta(hours=4), fetch_extras=False)
    assert st.get("analysis_queue", match_id="DEMO:yeni")["status"] == "bekliyor"
    assert not st.select("predictions", [("match_id", "eq", "DEMO:yeni")])


def test_publish_window_and_lead():
    from datetime import timedelta

    from meclis.bot import Bot
    from meclis.config import load_settings
    from meclis.store import SQLiteStore
    from meclis.timeutil import now_utc, to_iso

    s = load_settings()
    b = Bot(SQLiteStore(":memory:"), s)
    now = now_utc()
    assert not b.publishable({"kickoff_at": to_iso(now + timedelta(hours=2))}, now)  # < 3 saat
    assert b.publishable({"kickoff_at": to_iso(now + timedelta(hours=5))}, now)
    assert not b.publishable({"kickoff_at": to_iso(now + timedelta(days=3))}, now)  # pencere dışı


def test_predicted_xi_excludes_injured_and_flags_rotation():
    from meclis.xi import predict_xi

    pos = ["G"] + ["D"] * 6 + ["M"] * 6 + ["F"] * 4
    players = [{"name": f"Oyuncu {i}", "position": pos[i], "minutes": 900 - 40 * i, "lineups": 10 - (i % 11) // 2,
                "appearances": 10, "goals": 1 if pos[i] == "F" else 0, "assists": 0} for i in range(len(pos))]
    recent = [[f"Oyuncu {i}" for i in range(11)]] * 3
    inj = [{"player_name": "Oyuncu 1", "injury_status": "kesin yok (sakat)", "team_id": "x"}]
    xi = predict_xi(players, inj, recent)
    names = [p["name"] for p in xi["players"]]
    assert len(names) == 11 and "Oyuncu 1" not in names
    assert sum(1 for p in xi["players"] if p["position"] == "G") == 1
    assert any(r["name"] == "Oyuncu 1" for r in xi["effect_rows"])
    # kadro verisi yoksa uydurma 11 kurulmaz
    assert predict_xi(players[:5])["players"] == []


def test_lambdas_from_odds_roundtrip():
    from meclis.model.goals import goal_markets, lambdas_from_odds, score_matrix

    m = goal_markets(score_matrix(1.7, 0.9), 1.7, 0.9)
    p = {(x["market"], x["selection"], x["line"]): x["probability"] for x in m}
    odds = {"1X2": {"1": 1 / p[("1X2", "1", None)], "X": 1 / p[("1X2", "X", None)], "2": 1 / p[("1X2", "2", None)]},
            "OU_GOALS_2.5": {"ÜST": 1 / p[("OU_GOALS", "ÜST", 2.5)], "ALT": 1 / p[("OU_GOALS", "ALT", 2.5)]}}
    lh, la = lambdas_from_odds(odds)
    assert abs(lh - 1.7) < 0.1 and abs(la - 0.9) < 0.1


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
    assert "Veri derinliği" in labels
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


def test_analysis_only_run_stores_every_match_once(demo_env):
    from datetime import timedelta

    from meclis.bot import Bot
    from meclis.config import load_settings
    from meclis.store import get_store
    from meclis.timeutil import now_utc

    s = load_settings()
    st = get_store(s)
    n_pred = len(st.select("predictions"))
    b = Bot(st, s)
    r1 = b.run(record=True, fetch_extras=False, publish=False)
    Bot(st, s).run(record=True, fetch_extras=False, publish=False, now=now_utc() + timedelta(minutes=1))
    assert len(st.select("predictions")) == n_pred  # analiz modu tahmin/kupon yazmaz
    ms = b.candidates(now_utc() + timedelta(minutes=1))
    assert r1["analyzed"] >= len(ms) > 0
    for m in ms:
        rows = st.select("analyses", [("match_id", "eq", m["id"])])
        assert len(rows) == 1  # eski sürümler budanır
        p = rows[0]["payload"]
        assert p.get("markets") and "predicted_xi" in p and "scenarios" in p


def _mk_market(market, sel, line, p, odds):
    return {"market": market, "selection": sel, "line": line, "probability": p, "odds": odds,
            "fair_odds": round(1 / p, 3), "edge": (p * odds - 1) if odds else None}


def test_value_ranking_opens_all_markets_and_avoids_low_odds():
    from meclis.analysis import SINGLE_MIN_ODDS, rank_picks, select_single
    from meclis.config import load_settings

    s = load_settings()
    s.pick_mode = "deger"  # değer modu (isabet modu ayrı testte)
    payload = {"ready": True, "basis": "model", "quality": {"factor": 1.0}, "model_matches": {"home": 8, "away": 8},
               "min_team_matches": 4, "markets": [
                   # çok yüksek olasılık ama oran 1.18 → tekli için elenmeli
                   _mk_market("OU_GOALS", "ÜST", 0.5, 0.93, 1.18), _mk_market("OU_GOALS", "ALT", 0.5, 0.07, 6.0),
                   # 1X2'de değer: model 0.50, oran 2.40 (piyasa ~0.40)
                   _mk_market("1X2", "1", None, 0.50, 2.40), _mk_market("1X2", "X", None, 0.25, 3.40),
                   _mk_market("1X2", "2", None, 0.25, 3.10),
                   # oransız korner: adil oran seçimi, değer seçimlerinin ALTINDA
                   _mk_market("CORNERS_OU", "ÜST", 9.5, 0.60, None),
                   _mk_market("CARDS_OU", "ALT", 4.5, 0.85, None)]}  # adil oran 1.18 → elenir
    ranked = rank_picks(payload, s)
    assert ranked[0]["market"] == "1X2" and ranked[0]["selection"] == "1" and ranked[0]["kind"] == "değer"
    assert 0.40 < ranked[0]["probability"] < 0.50  # piyasaya doğru kalibre
    assert all((r.get("odds") or 1 / r["probability"]) >= SINGLE_MIN_ODDS for r in ranked)
    assert [r["market"] for r in ranked if r["kind"] != "değer"] == ["CORNERS_OU"]
    assert select_single(payload, s)["market"] == "1X2"


def test_isabet_mode_picks_most_likely_market_priced_at_least_150():
    from meclis.analysis import rank_picks
    from meclis.config import load_settings

    s = load_settings()
    s.pick_mode = "isabet"
    payload = {"ready": True, "basis": "model", "quality": {"factor": 1.0}, "model_matches": {"home": 8, "away": 8},
               "min_team_matches": 4, "markets": [
                   _mk_market("OU_GOALS", "ÜST", 0.5, 0.93, 1.18), _mk_market("OU_GOALS", "ALT", 0.5, 0.07, 6.0),
                   _mk_market("OU_GOALS", "ÜST", 2.5, 0.60, 1.70), _mk_market("OU_GOALS", "ALT", 2.5, 0.40, 2.15),
                   _mk_market("1X2", "1", None, 0.50, 2.40), _mk_market("1X2", "X", None, 0.25, 3.40),
                   _mk_market("1X2", "2", None, 0.25, 3.10)]}
    ranked = [r for r in rank_picks(payload, s) if r["kind"] == "isabet"]
    assert ranked and ranked[0]["market"] == "OU_GOALS" and ranked[0]["line"] == 2.5 and ranked[0]["selection"] == "ÜST"
    assert all(r["odds"] >= 1.50 and r["probability"] >= 0.50 for r in ranked)


def test_asian_handicap_market_and_settlement():
    from meclis.markets import settle_pick
    from meclis.model.goals import goal_markets, score_matrix

    ms = goal_markets(score_matrix(1.6, 1.0), 1.6, 1.0)
    ah = {(m["selection"], m["line"]): m["probability"] for m in ms if m["market"] == "AH"}
    one = {(m["selection"]): m["probability"] for m in ms if m["market"] == "1X2"}
    assert abs(ah[("1", -0.5)] - one["1"]) < 1e-9 and abs(ah[("1", -0.5)] + ah[("2", 0.5)] - 1) < 1e-9
    match = {"home_goals": 2, "away_goals": 1, "status": "bitti"}
    assert settle_pick("AH", "1", -1.5, match)[0] == "kaybetti"
    assert settle_pick("AH", "2", 1.5, match)[0] == "kazandi"


def test_bot_bulletin_vs_archive_no_overlap():
    from datetime import timedelta

    from meclis.bot import Bot
    from meclis.config import load_settings
    from meclis.store import SQLiteStore
    from meclis.timeutil import now_utc, to_iso

    s = load_settings()
    st = SQLiteStore(":memory:")
    b = Bot(st, s)
    now = now_utc()
    ko = to_iso(now + timedelta(hours=4))  # yayın penceresinde (≥3 saat önce)
    analyses, rows = [], []
    for i, (odds, edge) in enumerate([(1.70, 0.12), (1.80, 0.10), (1.65, 0.09), (2.10, 0.08), (1.90, 0.07),
                                      (2.20, 0.06), (1.75, 0.05), (1.60, 0.04), (1.55, 0.04), (1.58, 0.03)]):
        m = {"id": f"m{i}", "kickoff_at": ko, "league": "T1", "home_name": f"Ev{i}", "away_name": f"Dep{i}"}
        st.upsert("matches", [dict(m, status="planlandi", home_team_id=f"h{i}", away_team_id=f"a{i}")])
        p = (1 + edge) / odds
        bp = {"market": "1X2", "selection": "1", "line": None, "probability": p, "odds": odds, "fair_odds": 1 / p,
              "edge": edge, "confidence": edge, "kind": "değer"}
        a = {"best_pick": bp, "quality": {"score": 80, "factor": 1.0}, "lambdas": {"home": 1.5, "away": 1.0},
             "basis": "model", "scenarios": []}
        analyses.append((m, a))
        rows.append(b._bot_pick_row(m, a, bp, now))
    st.upsert("bot_picks", rows)
    rec, coupons = b._publish(analyses, now)
    preds = st.select("predictions", [])
    gk = {p["match_id"] for p in preds if p["tag"] == "gunun_karari"}
    mg = {p["match_id"] for p in preds if p["tag"] == "meclis_gorusu"}
    kb = {p["match_id"] for p in preds if p["tag"] == "karar_birligi"}
    assert 2 <= len(gk) <= 3 and mg and not (gk & mg) and not (kb & (gk | mg))  # bir maç günde tek üründe
    assert all(p.get("bot_pick_id") == p["match_id"] for p in preds if p["tag"] != "karar_birligi")
    c = [x for x in st.select("coupons", []) if x["tag"] == "gunun_karari"][0]
    assert 2.30 <= c["total_odds"] <= 4.00
    # yayımlanan maçın bot satırı kilitli: yeniden hesaplama üzerine yazamaz
    locked = st.get("bot_picks", id=next(iter(gk)))
    assert locked["status"] == "gunun_karari" and locked["locked_at"]
    st.upsert("bot_picks", [dict(rows[int(locked["id"][1:])], market="OU_GOALS", status="aday", locked_at=None)])
    assert st.get("bot_picks", id=locked["id"])["market"] == "1X2"
    # ham bülten: arşive girmeyenler dahil hepsi
    assert len(st.select("bot_picks", [])) == 10


def test_api_football_odds_parser_and_attach():
    from meclis.markets import attach_odds
    from meclis.sources.api_football import parse_odds_response

    def bm(i, vals):
        return {"id": i, "name": f"b{i}", "bets": vals}
    bets = lambda k: [{"id": 1, "values": [{"value": "Home", "odd": str(2.0 + k)}, {"value": "Draw", "odd": "3.4"},
                                            {"value": "Away", "odd": "3.9"}]},
                      {"id": 4, "values": [{"value": "Home -0.5", "odd": "2.1"}, {"value": "Away -0.5", "odd": "1.75"},
                                           {"value": "Home -0.25", "odd": "1.9"}, {"value": "Away -0.25", "odd": "1.95"}]},
                      {"id": 45, "values": [{"value": "Over 9.5", "odd": "1.9"}, {"value": "Under 9.5", "odd": "1.9"}]},
                      {"id": 12, "values": [{"value": "Home/Draw", "odd": "1.3"}, {"value": "Draw/Away", "odd": "1.8"},
                                            {"value": "Home/Away", "odd": "1.3"}]}]
    resp = [{"fixture": {"id": 7}, "bookmakers": [bm(1, bets(0)), bm(2, bets(0.1)), bm(3, bets(0.2))]}]
    o = parse_odds_response(resp)[7]
    assert o["1X2"]["1"] == 2.1 and "medyan(3)" in o["1X2"]["src"]
    assert "AH_-0.5" in o and "AH_-0.25" not in o and o["CORNERS_OU_9.5"]["ÜST"] == 1.9 and o["DC"]["X2"] == 1.8
    away = attach_odds({"market": "AH", "selection": "2", "line": 0.5, "probability": 0.6}, o)
    assert away["odds"] == 1.75
    cor = attach_odds({"market": "CORNERS_OU", "selection": "ALT", "line": 9.5, "probability": 0.6}, o)
    assert cor["odds"] == 1.9 and abs(cor["edge"] - 0.14) < 1e-6


def test_public_singles_exclude_same_day_coupon_legs():
    from meclis.trust import public_singles

    preds = [{"match_id": "g", "tag": "gunun_karari", "kickoff_at": "2026-10-19T17:00:00+00:00"},
             {"match_id": "g", "tag": "meclis_gorusu", "kickoff_at": "2026-10-19T17:00:00+00:00"},
             {"match_id": "x", "tag": "meclis_gorusu", "kickoff_at": "2026-10-19T17:00:00+00:00"}]
    assert [p["match_id"] for p in public_singles(preds)] == ["x"]


def test_dixon_coles_strength_prior_shifts_weak_league_opponents():
    from meclis.model.goals import fit_dixon_coles

    rows = []
    for i in range(12):  # A takımı zayıf ligde 'w*' rakiplerini 2-0 yener; B güçlü ligde 's*' rakiplerini 2-0 yener
        rows.append({"home": "CL:a", "away": f"X:w{i % 4}", "hg": 2, "ag": 0, "days_ago": i})
        rows.append({"home": "CL:b", "away": f"Y:s{i % 4}", "hg": 2, "ag": 0, "days_ago": i})
    rows.append({"home": "CL:a", "away": "CL:b", "hg": 1, "ag": 1, "days_ago": 1})
    pr = {f"X:w{i}": -0.3 for i in range(4)} | {f"Y:s{i}": 0.3 for i in range(4)}
    m = fit_dixon_coles(rows, prior=pr)
    m0 = fit_dixon_coles(rows)
    gap = lambda mm: mm.attack["CL:b"] - mm.attack["CL:a"]  # noqa: E731
    assert gap(m) > gap(m0) + 0.05


def test_assign_grid_follows_formation_and_positions():
    from meclis.xi import assign_grid

    ps = [{"name": f"D{i}", "position": "Defender"} for i in range(4)] + \
         [{"name": "K", "position": "Goalkeeper"}] + [{"name": f"M{i}", "position": "Midfielder"} for i in range(3)] + \
         [{"name": f"F{i}", "position": "Attacker"} for i in range(3)]
    f, out = assign_grid(ps, "4-3-3")
    assert f == "4-3-3" and out[0]["name"] == "K" and out[0]["grid"] == "1:1"
    assert [p["grid"] for p in out if p["name"].startswith("F")] == ["4:1", "4:2", "4:3"]
    f2, _ = assign_grid(ps, None)
    assert f2 == "4-3-3"


def test_rank_picks_blocks_absurd_edge_and_uses_backtest_weight():
    from types import SimpleNamespace

    from meclis.analysis import rank_picks

    mk = [{"market": "1X2", "selection": "1", "line": None, "probability": 0.80, "odds": 2.50},
          {"market": "1X2", "selection": "X", "line": None, "probability": 0.12, "odds": 3.40},
          {"market": "1X2", "selection": "2", "line": None, "probability": 0.08, "odds": 3.00}]
    pl = {"markets": [dict(m) for m in mk], "quality": {"factor": 1.0}, "basis": "model"}
    r = rank_picks(pl, SimpleNamespace(value_edge_min=0.03, pick_mode="deger"), True, annotate=True)
    assert not [x for x in r if x.get("kind") == "değer"]  # %25 üstü değer → yayımlanmaz
    assert pl["markets"][0]["deger"] is False
    mk = [{"market": "1X2", "selection": "1", "line": None, "probability": 0.55, "odds": 2.70},
          {"market": "1X2", "selection": "X", "line": None, "probability": 0.25, "odds": 3.40},
          {"market": "1X2", "selection": "2", "line": None, "probability": 0.20, "odds": 3.00}]
    pl2 = {"markets": [dict(m) for m in mk], "quality": {"factor": 1.0}, "basis": "model",
           "cal_params": {"1X2": {"w": 0.1, "roi": 0.02}}}
    r2 = rank_picks(pl2, SimpleNamespace(value_edge_min=0.03, pick_mode="deger"), True)
    assert r2 and r2[0]["calibration"]["kaynak"] == "geri test" and r2[0]["calibration"]["w"] == 0.1


def test_coupon_gate_waits_until_previous_day_18_tsi():
    from datetime import date, datetime, timezone

    from meclis.bot import coupon_gate

    g = coupon_gate(date(2026, 10, 29))
    assert g.astimezone(timezone.utc) == datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)


def test_registry_prefix_alias_unique_only():
    from meclis.pool import TeamRegistry

    r = TeamRegistry()
    for k in ("tranmererovers", "bristolcity", "bristolrovers", "barnet"):
        r.add("E3", k, k)
    assert r.resolve("E3", "Tranmere") == "tranmererovers"
    assert r.resolve("E3", "Bristol") == "bristol"  # iki aday: eşleşmez, yeni anahtar


def test_rescheduled_match_keeps_existing_id():
    from meclis.pool import merge_records

    ex = [{"id": "E3:2026-10-27:a:b", "league": "E3", "home_team_id": "E3:aaaaa", "away_team_id": "E3:bbbbb",
           "home_name": "Aaaaa", "away_name": "Bbbbb", "kickoff_at": "2026-10-27T00:00:00+00:00", "status": "ertelendi"}]
    rec = [{"source": "bsd", "league": "E3", "home_name": "Aaaaa", "away_name": "Bbbbb",
            "kickoff_at": "2026-10-30T19:30:00+00:00", "status": "planlandi"}]
    out = merge_records(rec, existing=ex)
    assert len(out) == 1 and out[0]["id"] == "E3:2026-10-27:a:b" and out[0]["status"] == "planlandi"


def test_bsd_odds_cadence():
    from datetime import datetime, timezone

    from meclis.sources.bsd import odds_due

    now = datetime(2026, 10, 28, 9, 20, tzinfo=timezone.utc)
    far = "2026-10-30T19:00:00+00:00"
    assert not odds_due(far, "2026-10-28T08:20:00+00:00", now)  # 1 saat önce alındı, maç uzak
    assert odds_due(far, "2026-10-28T05:00:00+00:00", now)
    assert odds_due("2026-10-28T14:00:00+00:00", "2026-10-28T07:00:00+00:00", now)  # yakın maç, 2+ saat


def test_motor_isotonic_and_guard():
    import random

    from meclis import motor

    random.seed(1)
    xs = [random.random() for _ in range(2000)]
    ys = [int(random.random() < x) for x in xs]
    iso = motor.pav(xs, ys)
    assert all(a[1] <= b[1] for a, b in zip(iso, iso[1:]))  # artan
    assert abs(motor.iso_apply(0.6, iso) - 0.6) < 0.08
    # koruma: piyasa mükemmel, model gürültü → model ağırlığı artmaz, mevcut korunur ya da w küçük kalır
    ms = []
    for i in range(400):
        pk = random.uniform(0.3, 0.7)
        y = int(random.random() < pk)
        ms.append({"t": f"2026-08-{1 + i % 28:02d}T{i % 24:02d}", "sels": [
            {"g": "BTTS", "sel": "VAR", "pm": random.random(), "pk": pk, "odds": 1 / pk, "y": y}]})
    ms.sort(key=lambda m: m["t"])
    prm, log = motor.learn(ms, None)
    assert prm["BTTS"].get("w", 0.35) <= 0.35
    assert motor.band_of(0.57) == "%55–60" and motor.band_of(0.72) == "%70+"
