from datetime import timedelta

from meclis.markets import profit_for, settle_pick
from meclis.settlement import run_settlement
from meclis.store import SQLiteStore
from meclis.timeutil import now_utc, to_iso

R = {"status": "bitti", "home_goals": 2, "away_goals": 1, "ht_home_goals": 0, "ht_away_goals": 0,
     "home_corners": 6, "away_corners": 4, "home_cards": 2, "away_cards": 3, "home_shots_on_target": 5,
     "away_shots_on_target": 3, "home_goal_kicks": None, "away_goal_kicks": None}


def test_settle_rules():
    assert settle_pick("1X2", "1", None, R) == ("kazandi", "2-1")
    assert settle_pick("1X2", "X", None, R)[0] == "kaybetti"
    assert settle_pick("DC", "X2", None, R)[0] == "kaybetti"
    assert settle_pick("OU_GOALS", "ÜST", 2.5, R)[0] == "kazandi"
    assert settle_pick("OU_GOALS", "ÜST", 3.0, R)[0] == "iade"          # tam sayı çizgide eşitlik = iade
    assert settle_pick("BTTS", "VAR", None, R)[0] == "kazandi"
    assert settle_pick("HT_OU_GOALS", "ALT", 0.5, R)[0] == "kazandi"
    assert settle_pick("CORNERS_OU", "ÜST", 9.5, R)[0] == "kazandi"
    assert settle_pick("CARDS_OU", "ALT", 4.5, R)[0] == "kaybetti"
    assert settle_pick("SOT_OU", "ALT", 8.5, R)[0] == "kazandi"
    assert settle_pick("GOAL_KICKS_OU", "ÜST", 15.5, R) == (None, None)  # veri yok → açık kalır
    assert settle_pick("CS", "2-1", None, R)[0] == "kazandi"
    assert settle_pick("1X2", "1", None, {"status": "iptal"})[0] == "iade"


def test_profit():
    assert profit_for("kazandi", 1.8) == 0.8
    assert profit_for("kaybetti", 1.8) == -1
    assert profit_for("iade", 1.8) == 0
    assert profit_for("kazandi", None) is None  # adil oranla kâr hesaplanmaz


def _seed(store, ko):
    store.upsert("matches", [{"id": "T1:x", "league": "T1", "kickoff_at": ko, "home_team_id": "T1:a",
                              "away_team_id": "T1:b", "home_name": "A", "away_name": "B", "status": "planlandi"}])


def test_auto_settlement_end_to_end():
    st = SQLiteStore()
    ko = to_iso(now_utc() + timedelta(hours=2))
    _seed(st, ko)
    base = {"match_id": "T1:x", "kickoff_at": ko, "home_name": "A", "away_name": "B", "probability": .6,
            "status": "bekliyor", "stake": 1, "line": None}
    st.insert("predictions", [
        dict(base, id="p1", tag="meclis_gorusu", market="1X2", selection="1", odds=1.9),
        dict(base, id="p2", tag="meclis_gorusu", market="CORNERS_OU", selection="ÜST", line=9.5, odds=None),
        dict(base, id="p3", tag="meclis_gorusu", market="BTTS", selection="YOK", odds=2.1),
    ])
    later = now_utc() + timedelta(hours=5)
    st.update("matches", {"status": "bitti", "home_goals": 2, "away_goals": 1, "ht_home_goals": 1, "ht_away_goals": 0},
              [("id", "eq", "T1:x")])
    # korner verisi henüz yok → p2 açık kalmalı
    run_settlement(st, now=later)
    got = {p["id"]: p for p in st.select("predictions")}
    assert got["p1"]["status"] == "kazandi" and got["p1"]["profit"] == 0.9
    assert got["p3"]["status"] == "kaybetti" and got["p3"]["profit"] == -1
    assert got["p2"]["status"] == "basladi" and got["p2"]["settlement_note"] == "sonuç verisi bekleniyor"
    st.upsert("match_stats", [{"match_id": "T1:x", "side": "home", "team_id": "T1:a", "corners": 7},
                              {"match_id": "T1:x", "side": "away", "team_id": "T1:b", "corners": 4}])
    run_settlement(st, now=later)
    p2 = st.get("predictions", id="p2")
    assert p2["status"] == "kazandi" and p2["profit"] is None and p2["result_value"] == "7+4=11"
