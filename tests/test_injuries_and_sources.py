import pytest

from meclis.model.injuries import injury_adjustment, player_importance, team_absence_impact
from meclis.sources.football_data_co_uk import parse_csv, season_code
from meclis.sources.odds_api import parse_events

PLAYERS = [
    {"name": "Golcü Oyuncu", "position": "Attacker", "minutes": 900, "lineups": 10, "goals": 8, "assists": 2},
    {"name": "Yedek Forvet", "position": "Attacker", "minutes": 120, "lineups": 0, "goals": 0, "assists": 0},
    {"name": "Stoper Bir", "position": "Defender", "minutes": 880, "lineups": 10, "goals": 0, "assists": 0},
    {"name": "Kaleci", "position": "Goalkeeper", "minutes": 900, "lineups": 10, "goals": 0, "assists": 0},
    {"name": "Orta Saha", "position": "Midfielder", "minutes": 700, "lineups": 8, "goals": 2, "assists": 6},
]


def test_key_player_weighs_more():
    star = player_importance(PLAYERS[0], PLAYERS)
    bench = player_importance(PLAYERS[1], PLAYERS)
    assert star["is_key"] and not bench["is_key"]
    assert star["importance"] > 3 * bench["importance"]
    doubt = player_importance(PLAYERS[0], PLAYERS, "şüpheli")
    assert doubt["importance"] == pytest.approx(star["importance"] * 0.5, abs=1e-3)
    unknown = player_importance(None, PLAYERS)
    assert unknown["known"] is False and unknown["importance"] == 0.15


def test_tee_bands_and_multipliers():
    star = player_importance(PLAYERS[0], PLAYERS)
    gk = player_importance(PLAYERS[3], PLAYERS)
    assert team_absence_impact([])["tee"] == 0
    one = team_absence_impact([star])
    two = team_absence_impact([star, gk])
    assert 0 < one["tee"] < two["tee"] <= 100
    assert one["attack_mult"] < 1 and two["defence_mult"] > 1
    adj = injury_adjustment([star, gk], [])
    assert adj["home_mult"] < 1 and adj["away_mult"] > 1
    assert adj["home_band"] in ("Hissedilir", "Ciddi", "Ağır")


CSV = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,"
    "AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5,AvgCH,AvgCD,AvgCA\n"
    "T1,14/08/2026,19:30,Galatasaray,Corum,2,2,D,0,0,D,20,8,9,3,11,6,8,1,1,0,0,1,1.3,5.5,9.0,1.5,2.5,1.28,5.6,9.5\n"
    "T1,20/10/2026,17:00,Besiktas,Goztep,,,,,,,,,,,,,,,,,,,1.8,3.6,4.2,1.9,1.9,,,\n"
)


def test_fdcuk_parser():
    recs = parse_csv(CSV)
    assert len(recs) == 2
    done, fut = recs
    assert done["status"] == "bitti" and done["home_goals"] == 2 and done["ht_home_goals"] == 0
    assert done["kickoff_at"] == "2026-08-14T18:30:00+00:00"  # İngiltere yaz saati → UTC
    assert done["stats"]["home"]["corners"] == 8 and done["stats"]["away"]["red"] == 1
    assert done["odds"]["1X2"]["1"] == 1.3 and done["odds"]["1X2_closing"]["1"] == 1.28
    assert fut["status"] == "planlandi" and fut["stats"] is None and fut["odds"]["OU_GOALS_2.5"]["ÜST"] == 1.9
    assert season_code(__import__("datetime").date(2026, 10, 19)) == "2627"


def test_odds_api_parser():
    ev = [{"id": "e1", "commence_time": "2026-10-20T17:00:00Z", "home_team": "Besiktas JK", "away_team": "Goztepe",
           "bookmakers": [{"key": "pinnacle", "markets": [
               {"key": "h2h", "outcomes": [{"name": "Besiktas JK", "price": 1.8}, {"name": "Goztepe", "price": 4.4},
                                           {"name": "Draw", "price": 3.7}]},
               {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5},
                                              {"name": "Under", "price": 1.9, "point": 2.5}]}]},
               {"key": "unibet", "markets": [{"key": "h2h", "outcomes": [
                   {"name": "Besiktas JK", "price": 1.7}, {"name": "Goztepe", "price": 4.6}, {"name": "Draw", "price": 3.5}]}]}]}]
    r = parse_events(ev, "T1")[0]
    assert r["odds"]["1X2"]["1"] == pytest.approx(1.75) and r["odds"]["1X2_pinnacle"]["2"] == 4.4
    assert r["odds"]["OU_GOALS_2.5"]["ALT"] == 1.9 and r["kickoff_at"] == "2026-10-20T17:00:00+00:00"
