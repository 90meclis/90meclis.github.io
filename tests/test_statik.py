import json
from datetime import timedelta

from meclis import statik
from meclis.canli import run_static
from meclis.store import SQLiteStore
from meclis.timeutil import TR, now_utc, to_iso


def test_export_and_live_static(tmp_path):
    st = SQLiteStore()
    now = now_utc()
    ko = now - timedelta(minutes=30)
    st.upsert("matches", [{"id": "E0:2026:arsenal:chelsea", "league": "E0", "kickoff_at": to_iso(ko), "home_name": "Arsenal",
                           "away_name": "Chelsea", "home_team_id": "E0:arsenal", "away_team_id": "E0:chelsea",
                           "status": "planlandi", "source": "x", "season": "2026"}])
    statik.ANALYSES["E0:2026:arsenal:chelsea"] = {"match_id": "E0:2026:arsenal:chelsea", "markets": [{"market": "1X2"}]}
    statik.PAYLOADS["meclis:motor"] = {"ok": 1}
    log: list = []
    statik.export(st, log, out=tmp_path)
    d = ko.astimezone(TR).date().isoformat()
    g = json.loads((tmp_path / "gun" / f"{d}.json").read_text())
    assert g["maclar"][0]["home_name"] == "Arsenal" and "E0:2026:arsenal:chelsea" in g["analizler"]
    assert json.loads((tmp_path / "editoryal.json").read_text())["anahtarlar"]["meclis:motor"] == {"ok": 1}
    assert json.loads((tmp_path / "gunler.json").read_text())["gunler"][d]["E0"] == 1
    assert "predictions" in json.loads((tmp_path / "defter.json").read_text())

    ev = [{"ko": to_iso(ko), "home": "Arsenal", "away": "Chelsea", "canli": True, "bitti": False, "durum": "2. yarı",
           "dakika": "60'", "hg": 1, "ag": 0}]
    assert run_static(tmp_path, log, fetch=lambda day: ev, now=now) == 1
    c = json.loads((tmp_path / "canli.json").read_text())["maclar"]["E0:2026:arsenal:chelsea"]
    assert c["skor"] == "1-0"


def test_team_rows_matches_view_semantics():
    from datetime import datetime, timezone

    s0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    ms = [{"id": "m1", "league": "CL", "kickoff_at": "2026-10-01T19:00:00+00:00", "status": "bitti", "home_goals": 2,
           "away_goals": 1, "home_team_id": "E0:arsenal", "away_team_id": "SP1:real-madrid", "home_name": "Arsenal",
           "away_name": "Real Madrid"},
          {"id": "m0", "league": "E0", "kickoff_at": "2026-05-01T19:00:00+00:00", "status": "bitti", "home_goals": 0,
           "away_goals": 0, "home_team_id": "E0:arsenal", "away_team_id": "E0:x", "home_name": "Arsenal", "away_name": "X"}]
    st = [{"match_id": "m1", "side": "home", "corners": 7, "yellow": 2, "red": 1},
          {"match_id": "m1", "side": "away", "corners": 3, "yellow": 1, "red": None}]
    r = statik.team_rows(ms, st, s0)
    a = r["arsenal"]
    assert len(a) == 1 and a[0]["asama"] == "Lig aşaması" and a[0]["competition"] == "Avrupa"
    assert a[0]["corners_for"] == 7 and a[0]["cards_for"] == 3 and a[0]["cards_against"] == 1 and a[0]["btts"] is True
    assert r["real-madrid"][0]["goals_for"] == 1 and r["real-madrid"][0]["venue"] if "venue" in r["real-madrid"][0] else True
