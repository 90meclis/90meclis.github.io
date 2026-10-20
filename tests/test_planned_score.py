from meclis.sources.api_football import parse_fixture
from meclis.sources.football_data_org import FootballDataOrg


def test_apif_planned_has_no_score():
    f = {"fixture": {"id": 1, "date": "2026-10-21T18:00:00+00:00", "status": {"short": "NS"}, "venue": {}},
         "teams": {"home": {"id": 1, "name": "Levante"}, "away": {"id": 2, "name": "Athletic Club"}},
         "goals": {"home": 0, "away": 0}, "score": {"halftime": {"home": 0, "away": 0}}, "league": {"id": 140}}
    r = parse_fixture(f, "SP1", 2026)
    assert r["home_goals"] is None and r["ht_home_goals"] is None and r["status"] == "planlandi"
    f["fixture"]["status"]["short"] = "FT"
    assert parse_fixture(f, "SP1", 2026)["home_goals"] == 0


def test_fdorg_planned_has_no_score():
    m = {"competition": {"code": "PD"}, "utcDate": "2026-10-21T18:00:00Z", "status": "TIMED",
         "homeTeam": {"id": 88, "shortName": "Levante"}, "awayTeam": {"id": 77, "shortName": "Athletic"},
         "score": {"fullTime": {"home": 0, "away": 0}, "halfTime": {"home": 0, "away": 0}}}
    r = FootballDataOrg._rec(m)
    assert r is not None and r["home_goals"] is None and r["ht_away_goals"] is None
