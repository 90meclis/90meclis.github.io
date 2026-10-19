from datetime import timedelta

import pytest

from meclis.store import SQLiteStore, StoreError
from meclis.timeutil import now_utc, to_iso


def setup_store(ko):
    st = SQLiteStore()
    st.upsert("matches", [{"id": "M", "league": "T1", "kickoff_at": ko, "home_team_id": "T1:a", "away_team_id": "T1:b",
                           "home_name": "A", "away_name": "B", "status": "planlandi"}])
    return st


def pred(ko, **kw):
    d = {"id": "p", "match_id": "M", "kickoff_at": ko, "tag": "meclis_gorusu", "market": "1X2", "selection": "1",
         "probability": .55, "odds": 2.0, "status": "bekliyor"}
    d.update(kw)
    return d


def test_insert_after_kickoff_rejected():
    ko = to_iso(now_utc() - timedelta(minutes=1))
    st = setup_store(ko)
    with pytest.raises(StoreError, match="başladı"):
        st.insert("predictions", [pred(ko)])


def test_kickoff_spoof_rejected():
    real = to_iso(now_utc() - timedelta(minutes=5))
    st = setup_store(real)
    with pytest.raises(StoreError):
        st.insert("predictions", [pred(to_iso(now_utc() + timedelta(hours=3)))])


def test_core_fields_locked_status_allowed_and_no_delete():
    ko = to_iso(now_utc() + timedelta(hours=1))
    st = setup_store(ko)
    st.insert("predictions", [pred(ko, recorded_at="2000-01-01T00:00:00+00:00")])
    p = st.get("predictions", id="p")
    assert p["recorded_at"] > "2020"  # istemcinin verdiği zaman yok sayılır
    for change in ({"odds": 3.0}, {"selection": "2"}, {"probability": .9}, {"recorded_at": "2030-01-01T00:00:00+00:00"}):
        with pytest.raises(StoreError, match="değiştirilemez"):
            st.update("predictions", change, [("id", "eq", "p")])
    st.update("predictions", {"status": "basladi"}, [("id", "eq", "p")])
    st.update("predictions", {"status": "kazandi", "profit": 1.0, "result_value": "1-0"}, [("id", "eq", "p")])
    with pytest.raises(StoreError, match="Sonuçlanmış"):
        st.update("predictions", {"status": "kaybetti"}, [("id", "eq", "p")])
    with pytest.raises(Exception):
        st.conn.execute("delete from predictions where id='p'")


def test_new_prediction_must_start_bekliyor():
    ko = to_iso(now_utc() + timedelta(hours=1))
    st = setup_store(ko)
    with pytest.raises(StoreError):
        st.insert("predictions", [pred(ko, status="kazandi")])


def test_coupon_after_first_kickoff_rejected():
    st = SQLiteStore()
    with pytest.raises(StoreError):
        st.insert("coupons", [{"id": "c", "coupon_date": "2026-10-19", "tag": "gunun_karari", "total_odds": 2.5,
                               "legs_count": 2, "first_kickoff_at": to_iso(now_utc() - timedelta(minutes=1)),
                               "status": "bekliyor"}])
