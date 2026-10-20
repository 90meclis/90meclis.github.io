"""Yeni veri kaynaklarının ayrıştırıcıları, Elo önseli, boşluk doldurma birleştirmesi ve kaynak tohumu."""
import json
import math
import re
from pathlib import Path

import pytest

from meclis.model.elo import BLEND_WEIGHT, blend, fit_elo, run_elo
from meclis.pool import merge_records
from meclis.sources import footystats, oddspapi, openfootball, openligadb, sportdevs, sportmonks, wikidata
from meclis.sources.registry import SECRET_NAMES, SOURCES, key_state

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ ayrıştırıcılar
def test_openligadb_parse():
    data = [{"matchID": 7, "matchDateTimeUTC": "2026-10-18T13:30:00Z", "matchIsFinished": True,
             "team1": {"teamName": "FC Bayern München"}, "team2": {"teamName": "1. FC Köln"},
             "matchResults": [{"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
                              {"resultTypeID": 2, "pointsTeam1": 3, "pointsTeam2": 1}],
             "location": {"locationCity": "München", "locationStadium": "Allianz Arena"}},
            {"matchID": 8, "matchDateTimeUTC": "2026-10-25T13:30:00Z", "matchIsFinished": False,
             "team1": {"teamName": "A"}, "team2": {"teamName": "B"}, "matchResults": []}]
    out = openligadb.parse_matches(data, "D1", False)
    assert out[0]["home_goals"] == 3 and out[0]["ht_home_goals"] == 1 and out[0]["status"] == "bitti"
    assert out[0]["venue"] == "Allianz Arena" and out[0]["fill_only"] is False
    assert out[1]["status"] == "planlandi" and out[1]["home_goals"] is None
    assert openligadb.season_year(__import__("datetime").date(2026, 3, 1)) == 2025


def test_openfootball_parse_timezone():
    data = {"matches": [{"date": "2026-10-18", "time": "19:00", "team1": "Galatasaray", "team2": "Fenerbahçe",
                         "score": {"ft": [2, 2], "ht": [1, 0]}},
                        {"date": "2026-10-26", "team1": "A", "team2": "B"}]}
    out = openfootball.parse(data, "T1", "Europe/Istanbul")
    assert out[0]["kickoff_at"].startswith("2026-10-18T16:00") and out[0]["home_goals"] == 2
    assert out[0]["fill_only"] and out[1]["status"] == "planlandi"


def _b(**kw):
    return {k: {"value": str(v)} for k, v in kw.items()}


def test_wikidata_pick_skips_women_and_wrong_country_and_takes_latest():
    q = "http://www.wikidata.org/entity/"
    rows = [
        _b(item=q + "Q1", itemLabel="Trabzonspor Kadın", ord=1, country=q + "Q43", venueLabel="X"),
        _b(item=q + "Q2", itemLabel="Trabzonspor", ord=2, country=q + "Q43", venueLabel="Eski Stat",
           vstart="1951-01-01T00:00:00Z", coachLabel="Eski Hoca", cstart="2020-01-01T00:00:00Z"),
        _b(item=q + "Q2", itemLabel="Trabzonspor", ord=2, country=q + "Q43", venueLabel="Papara Park",
           vstart="2016-12-18T00:00:00Z", cap="41500", cityLabel="Trabzon", coord="Point(39.66 41.0)",
           coachLabel="Yeni Hoca", cstart="2026-06-01T00:00:00Z"),
        _b(item=q + "Q3", itemLabel="Trabzon FC", ord=3, country=q + "Q145", venueLabel="Y"),
    ]
    p = wikidata.pick(rows, "Q43")
    assert p["wikidata"] == "Q2" and p["stadium"] == "Papara Park" and p["capacity"] == 41500
    assert p["coach"] == "Yeni Hoca" and p["city"] == "Trabzon" and math.isclose(p["lat"], 41.0)
    assert wikidata.pick(rows[3:], "Q43") is None


def test_sportmonks_parse():
    f = {"id": 5, "league_id": 600, "state_id": 5, "starting_at_timestamp": 1792000000,
         "participants": [{"id": 1, "name": "Galatasaray", "meta": {"location": "home"}},
                          {"id": 2, "name": "Beşiktaş", "meta": {"location": "away"}}],
         "scores": [{"description": "CURRENT", "score": {"participant": "home", "goals": 2}},
                    {"description": "CURRENT", "score": {"participant": "away", "goals": 0}},
                    {"description": "1ST_HALF", "score": {"participant": "home", "goals": 1}},
                    {"description": "1ST_HALF", "score": {"participant": "away", "goals": 0}}],
         "statistics": [{"type_id": 34, "participant_id": 1, "data": {"value": 7}}],
         "venue": {"name": "RAMS Park", "city_name": "İstanbul"},
         "referees": [{"type_id": 6, "referee": {"common_name": "A. Hakem"}}]}
    out = sportmonks.parse_fixtures([f, {**f, "league_id": 999}])
    assert len(out) == 1 and out[0]["league"] == "T1" and out[0]["home_goals"] == 2
    assert out[0]["ht_home_goals"] == 1 and out[0]["referee"] == "A. Hakem" and out[0]["stats"]["home"]["corners"] == 7


def test_footystats_parse():
    smap = footystats.map_leagues([{"country": "England", "league_name": "Premier League",
                                    "season": [{"id": 15050, "year": 20262027}]}])
    assert smap == {15050: "E0"}
    m = {"id": 1, "competition_id": 15050, "home_name": "Arsenal", "away_name": "Chelsea", "date_unix": 1792000000,
         "status": "complete", "homeGoalCount": 1, "awayGoalCount": 1, "odds_ft_1": 2.0, "odds_ft_x": 3.4,
         "odds_ft_2": 3.8, "odds_ft_over25": 1.9, "odds_ft_under25": 1.95, "team_a_corners": 6, "team_b_corners": -1}
    out = footystats.parse_matches([m], smap)[0]
    assert out["odds"]["1X2"]["X"] == 3.4 and out["odds"]["OU_GOALS_2.5"]["ALT"] == 1.95
    assert out["stats"]["home"]["corners"] == 6 and out["stats"]["away"]["corners"] is None  # -1 = veri yok


def test_sportdevs_parse_and_league_filter():
    rows = [{"id": 1, "class_name": "England", "league_name": "Premier League", "home_team_name": "Arsenal",
             "away_team_name": "Chelsea", "start_time": "2026-10-18T14:00:00+00:00", "status_type": "finished",
             "home_team_score": {"current": 2, "period_1": 1}, "away_team_score": {"current": 0, "period_1": 0}},
            {"id": 2, "class_name": "England", "league_name": "Premier League 2", "home_team_name": "X",
             "away_team_name": "Y", "start_time": "2026-10-18T14:00:00+00:00"}]
    out = sportdevs.parse_matches(rows)
    assert len(out) == 1 and out[0]["league"] == "E0" and out[0]["home_goals"] == 2 and out[0]["ht_home_goals"] == 1


def test_oddspapi_parse():
    tmap = oddspapi.map_tournaments([{"tournamentId": 17, "tournamentSlug": "premier-league",
                                      "categorySlug": "england"}], ["E0"])
    assert tmap == {17: "E0"}
    pl = {"players": {"0": {"price": 2.1, "active": True}}}
    row = {"fixtureId": "f1", "tournamentId": 17, "participant1Id": 1, "participant2Id": 2,
           "startTime": "2026-10-25T14:00:00Z",
           "bookmakerOdds": {"pinnacle": {"markets": {"101": {"outcomes": {"101": pl, "102": pl, "103": pl}}}}}}
    out = oddspapi.parse_odds([row], tmap, {1: "Arsenal", 2: "Chelsea"})
    assert out[0]["odds"]["1X2"] == {"1": 2.1, "X": 2.1, "2": 2.1}


# ------------------------------------------------------------------ Elo
def _season(n_rounds=12):
    import random
    rnd = random.Random(3)
    teams = [f"t{i}" for i in range(10)]
    strength = {t: i / 9 for i, t in enumerate(teams)}
    rows, day = [], 400.0
    for _ in range(n_rounds):
        for i in range(0, 10, 2):
            sh = rnd.sample(teams, 10)
            for j in range(0, 10, 2):
                h, a = sh[j], sh[j + 1]
                lh, la = math.exp(0.2 + strength[h] - strength[a]), math.exp(strength[a] - strength[h])
                rows.append({"home": h, "away": a, "hg": min(6, int(rnd.expovariate(1 / lh))),
                             "ag": min(6, int(rnd.expovariate(1 / la))), "days_ago": day})
                day -= 0.5
    return rows


def test_elo_learns_strength_and_blend_is_bounded():
    rows = _season()
    model = fit_elo(rows)
    assert model.ratings["t9"] > model.ratings["t0"]
    lh, la = model.lambdas("t9", "t0")
    assert lh > la
    dc = (1.2, 1.0)
    bh, ba = blend(dc, (lh, la))
    assert min(dc[0], lh) <= bh <= max(dc[0], lh) and 0 < BLEND_WEIGHT < 1
    assert blend(dc, None) == dc and model.lambdas("t9", "yok") is None
    r, deltas, counts = run_elo(rows[:1], priors={rows[0]["home"]: 1700})
    assert deltas[0] > 0  # Club Elo önseli başlangıç puanını belirler


def test_elo_needs_enough_matches():
    with pytest.raises(ValueError):
        fit_elo(_season(1))


# ------------------------------------------------------------------ birleştirme
def _r(source, home, away, ko="2026-10-18T15:00:00+00:00", league="E0", **kw):
    return {"source": source, "league": league, "home_name": home, "away_name": away, "kickoff_at": ko, **kw}


def test_fill_only_never_creates_new_match_but_fills_gaps():
    recs = [_r("football-data.co.uk", "Brentford", "Liverpool", status="planlandi"),
            _r("openfootball", "Brentford F.C.", "FC Liverpool", "2026-10-18T14:00:00+00:00",
               status="bitti", home_goals=1, away_goals=2, fill_only=True),
            _r("openfootball", "Hayali Takım", "Başka Takım", status="bitti", home_goals=1, away_goals=0, fill_only=True)]
    from meclis.pool import TeamRegistry
    reg = TeamRegistry()
    out = merge_records(recs, reg)
    assert len(out) == 1 and out[0]["home_goals"] == 1 and out[0]["away_goals"] == 2
    assert any("Hayali" in u for u in reg.unmatched)


def test_odds_priority_prefers_dedicated_odds_feed():
    recs = [_r("football-data.co.uk", "Arsenal", "Chelsea", odds={"1X2": {"1": 2.0, "X": 3.0, "2": 4.0}}),
            _r("the-odds-api", "Arsenal", "Chelsea", odds={"1X2": {"1": 2.1, "X": 3.2, "2": 3.9}}),
            _r("api-football", "Arsenal", "Chelsea", odds={"1X2": {"1": 1.5, "X": 3.0, "2": 9.0}})]
    out = merge_records(recs)
    assert out[0]["odds"]["1X2"]["1"] == 2.1


def test_new_official_names_unify():
    from meclis.names import canonical_key as c
    for a, b in [("Brentford F.C.", "Brentford"), ("Athletic Club", "Athletic Bilbao"), ("Parma Calcio 1913", "Parma"),
                 ("FC Internazionale Milano", "Inter Milan"), ("Stade Rennais FC 1901", "Rennes"),
                 ("Deportivo A Coruña", "La Coruna"), ("Real Betis Balompié", "Betis"),
                 ("SC Paderborn 07", "Paderborn"), ("1. FSV Mainz 05", "Mainz"), ("FC Villareal", "Villarreal")]:
        assert c(a) == c(b), (a, b)


# ------------------------------------------------------------------ kayıt defteri / tohum / belgeler
def test_registry_seed_matches_schema_sql():
    sql = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    block = sql[sql.index("insert into sources ("):sql.index("on conflict (name)", sql.index("insert into sources ("))]
    for d in SOURCES:
        row = d.seed_row()
        assert f"('{d.name}', " in block, d.name
        assert row["license_note"].replace("'", "''") in block, d.name
        assert json.dumps(row["fills_fields"], ensure_ascii=False, separators=(",", ":")) in block, d.name
    assert len(re.findall(r"^\s+\('", block, re.M)) == len(SOURCES)


def test_every_key_is_passed_by_workflow_and_documented():
    wf = (ROOT / ".github" / "workflows" / "meclis.yml").read_text(encoding="utf-8")
    env_ex = (ROOT / ".env.example").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for k in SECRET_NAMES:
        assert f"secrets.{k}" in wf, k
        assert re.search(rf"^{k}=\s*$", env_ex, re.M), k  # örnek dosyada değer yok
        assert k in readme, k


def test_no_optional_wording_for_sources():
    for p in ["README.md", "docs/supabase-sema.md", "docs/kaynaklar.md", ".env.example", "views/tahmin_botu.py",
              "meclis/sources/odds_api.py"]:
        t = (ROOT / p).read_text(encoding="utf-8").lower()
        assert "opsiyonel" not in t and "optional" not in t, p
        assert "isteğe bağlı" not in t or p == "README.md", p


def test_key_state_never_returns_value():
    class S:
        thesportsdb_key = "123"
        keys = {"SPORTMONKS_KEY": "gizli-deger"}
    states = {d.name: key_state(d, S()) for d in SOURCES}
    assert states["sportmonks"] == "tanımlı" and states["footystats"] == "anahtar bekleniyor"
    assert states["openligadb"] == "gerekmez" and "gizli" not in json.dumps(states)


def test_met_norway_parse_nearest_hour():
    from meclis.sources import met_no

    data = {"properties": {"timeseries": [
        {"time": "2026-10-20T18:00:00Z", "data": {"instant": {"details": {"air_temperature": 11.2, "wind_speed": 5.0,
                                                                          "relative_humidity": 80}},
                                                  "next_1_hours": {"summary": {"symbol_code": "rain"},
                                                                   "details": {"precipitation_amount": 1.4}}}},
        {"time": "2026-10-20T19:00:00Z", "data": {"instant": {"details": {"air_temperature": 10.0}}}}]}}
    w = met_no.parse(data, "2026-10-20T18:15:00+00:00")
    assert w["temperature_c"] == 11.2 and w["wind_kmh"] == 18.0 and w["summary"] == "Yağmurlu"
    assert w["attribution"] == "Data from MET Norway"
    assert met_no.parse(data, "2026-10-25T18:00:00+00:00") is None
