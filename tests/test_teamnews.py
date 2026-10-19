"""Kadro / sakat-cezalı / ilk 11 havuzu ve API-Football geçmiş veri doldurma testleri (ağ yok, sahte kaynaklar)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from meclis.config import Settings
from meclis.model.injuries import find_player, player_importance
from meclis.sources import bsd as B
from meclis.sources import wikipedia as W
from meclis.sources.http import SourceError
from meclis.store import SQLiteStore
from meclis.timeutil import now_utc, to_iso

WIKITEXT = """
== History ==
{{Fs player|no=99|pos=FW|name=[[Eski Efsane]]}}
== Players ==
=== Current squad ===
{{Fs start}}
{{Fs player|no=1|nat=TUR|pos=GK|name=[[Uğurcan Çakır]]}}
{{Fs player|no= 9|nat=NGA|pos=FW|name=[[Victor Osimhen (footballer)|Victor Osimhen]]|other=<small>on loan from [[Napoli]]</small>}}
{{Fs player|no=10|nat=TUR|pos=MF|name=Barış Alper Yılmaz}}
{{Fs end}}
=== Out on loan ===
{{Fs player|no=—|nat=TUR|pos=DF|name=[[Kiralık Oyuncu]]|other=at [[Göztepe]]}}
== Reserve team ==
{{Fs player|no=50|pos=MF|name=Genç Oyuncu}}
"""


def test_wikipedia_parse_first_team_only():
    sq = W.parse_squad(WIKITEXT)
    assert [p["name"] for p in sq] == ["Uğurcan Çakır", "Victor Osimhen", "Barış Alper Yılmaz"]
    assert sq[0]["position"] == "Goalkeeper" and sq[1]["number"] == 9 and sq[2]["position"] == "Midfielder"


def test_bsd_league_codes_and_parsers():
    assert B.league_code("Turkey", "Trendyol Super Lig") == "T1"
    assert B.league_code("Germany", "Bundesliga") == "D1"
    assert B.league_code("Germany", "2. Bundesliga") is None
    assert B.league_code("Austria", "Austrian Bundesliga") is None
    assert B.league_code("Brazil", "Brasileirão Serie A") is None
    assert B.league_code("Spain", "Copa del Rey") is None
    ev = B.parse_events([{"id": 7, "league_id": 3, "home_team": "Galatasaray", "away_team": "Fenerbahce",
                          "home_team_id": 11, "away_team_id": 12, "event_date": "2026-10-24T17:00:00Z",
                          "status": "notstarted", "home_score": None, "away_score": None}], {3: "T1"})
    assert ev[0]["status"] == "planlandi" and ev[0]["ext_ids"] == {"bsd": 7, "bsd_home": 11, "bsd_away": 12}
    pred = B.parse_lineups({"lineup_status": "predicted", "lineups": {
        "home": {"formation": "4-2-3-1", "confidence": 0.8, "players": [{"name": "A", "position": "G", "jersey_number": 1,
                                                                          "ai_score": 0.9}], "substitutes": []}},
        "unavailable_players": {"home": [{"id": 5, "name": "Sakat Oyuncu", "status": "injured", "reason": "Knee"}],
                                "away": [{"id": 6, "name": "Cezalı Oyuncu", "status": "suspended", "reason": "Red card"}]}})
    assert pred["status"] == "tahmini" and pred["lineups"]["home"]["start_xi"][0]["ai_score"] == 0.9
    assert pred["unavailable"]["home"][0]["kind"].startswith("kesin yok")
    assert pred["unavailable"]["away"][0]["kind"] == "cezalı"
    none = B.parse_lineups({"lineup_status": "unavailable", "lineups": None, "unavailable_players": None})
    assert none["status"] is None and none["unavailable"] is None
    sq = B.parse_squad({"players": [{"id": 1, "name": "X", "availability": "doubtful", "injury_type": "Hamstring"},
                                    {"id": 2, "name": "Y", "availability": "available"}]})
    assert sq[0]["kind"] == "şüpheli" and sq[1]["kind"] is None


def test_find_player_initial_and_surname():
    ps = [{"name": "Ömer Toprak"}, {"name": "Emre Toprak"}, {"name": "Mauro Icardi"}, {"name": "Vinícius Júnior"}]
    assert find_player("Ö. Toprak", ps)["name"] == "Ömer Toprak"
    assert find_player("E. Toprak", ps)["name"] == "Emre Toprak"
    assert find_player("M. Icardi", ps)["name"] == "Mauro Icardi"
    assert find_player("Biri Başka", ps) is None


def test_importance_unknown_when_player_has_no_stats():
    team = [{"name": "A", "minutes": 900, "goals": 5, "assists": 1, "lineups": 10, "position": "Attacker"},
            {"name": "B", "minutes": None, "position": "Defender"}]
    assert player_importance(team[1], team)["known"] is False
    assert player_importance(team[1], team)["importance"] == pytest.approx(0.15)
    assert player_importance(team[0], team)["known"] is True


# ---------------------------------------------------------------------- havuz
class FakeBSD:
    available = True

    def __init__(self, lineup):
        self._lineup = lineup
        self.calls = 0

    def lineups(self, event_id):
        self.calls += 1
        return self._lineup

    def squad(self, team_id):
        return [{"name": "Kadro Sakat", "kind": "kesin yok (sakat)", "reason": "Ankle"}] if team_id == 11 else []


def _pool(lineup, kickoff_in=timedelta(hours=20)):
    from meclis.pool import DataPool

    store = SQLiteStore(":memory:")
    s = Settings(leagues=["T1"])
    pool = DataPool(store, s)
    pool.bsd = FakeBSD(lineup)
    ko = now_utc() + kickoff_in
    m = {"id": "T1:x:galatasaray:fenerbahce", "league": "T1", "kickoff_at": to_iso(ko), "season": "2026",
         "home_team_id": "T1:galatasaray", "away_team_id": "T1:fenerbahce", "home_name": "Galatasaray",
         "away_name": "Fenerbahçe", "status": "planlandi", "durum": "gelecek",
         "ext_ids": {"bsd": 7, "bsd_home": 11, "bsd_away": 12}}
    store.upsert("matches", [m])
    ts = to_iso(now_utc())
    store.upsert("players", [
        {"team_id": "T1:galatasaray", "player_key": "k:sakatoyuncu", "name": "Sakat Oyuncu", "position": "Attacker",
         "minutes": 900, "lineups": 10, "goals": 8, "assists": 2, "season": "2026", "source": "wikipedia", "updated_at": ts},
        {"team_id": "T1:galatasaray", "player_key": "k:yedek", "name": "Yedek", "position": "Defender",
         "minutes": 100, "lineups": 1, "goals": 0, "assists": 0, "season": "2026", "source": "wikipedia", "updated_at": ts}])
    return pool, store, m


def test_injuries_from_bsd_weighted_and_known_even_if_empty():
    lu = B.parse_lineups({"lineup_status": "predicted", "lineups": {}, "unavailable_players": {
        "home": [{"id": 5, "name": "Sakat Oyuncu", "status": "injured", "reason": "Knee"}], "away": []}})
    pool, store, m = _pool(lu)
    rows, known = pool.injuries(m)
    assert known and len(rows) == 1
    r = rows[0]
    assert r["team_id"] == "T1:galatasaray" and r["source"] == "bsd" and r["is_key"] and r["weight_score"] > 0.5
    # boş liste de "biliniyor" demektir (bildirilen eksik yok)
    lu2 = B.parse_lineups({"lineup_status": "predicted", "lineups": {}, "unavailable_players": {"home": [], "away": []}})
    pool2, _, m2 = _pool(lu2)
    rows2, known2 = pool2.injuries(m2)
    assert known2 and rows2 == []


def test_injuries_fall_back_to_bsd_squad_availability():
    lu = B.parse_lineups({"lineup_status": "unavailable", "lineups": None, "unavailable_players": None})
    pool, store, m = _pool(lu)
    rows, known = pool.injuries(m)
    assert known and [r["player_name"] for r in rows] == ["Kadro Sakat"] and rows[0]["source"] == "bsd (kadro)"


def test_no_injury_source_means_unknown_not_empty():
    pool, store, m = _pool(None)
    pool.bsd.available = False
    rows, known = pool.injuries(m)
    assert rows == [] and known is False


def test_predicted_lineup_is_stored_but_not_counted_as_announced():
    from meclis.teamnews import is_confirmed

    lu = B.parse_lineups({"lineup_status": "predicted", "lineups": {
        "home": {"formation": "4-3-3", "players": [{"name": "A"}], "substitutes": []},
        "away": {"formation": "4-4-2", "players": [{"name": "B"}], "substitutes": []}}, "unavailable_players": None})
    pool, store, m = _pool(lu)
    rows = pool.lineups(m)
    assert len(rows) == 2 and not any(is_confirmed(r) for r in rows)
    assert all(r["lineup_status"] == "tahmini" for r in store.select("lineups"))
    # resmî ilk 11 gelince tahmini ezer
    pool.bsd._lineup = B.parse_lineups({"lineup_status": "confirmed", "lineups": {
        "home": {"formation": "4-3-3", "players": [{"name": "A"}], "substitutes": []},
        "away": {"formation": "4-4-2", "players": [{"name": "C"}], "substitutes": []}}, "unavailable_players": None})
    store.update("lineups", {"updated_at": to_iso(now_utc() - timedelta(hours=5))}, [("match_id", "eq", m["id"])])
    rows = pool.lineups(m)
    assert all(is_confirmed(r) for r in rows) and {r["side"]: r["start_xi"][0]["name"] for r in rows}["away"] == "C"


def test_current_players_prefers_latest_squad_batch():
    from meclis.teamnews import current_players

    old, new = to_iso(now_utc() - timedelta(days=9)), to_iso(now_utc())
    rows = [{"player_key": "k:ayrilan", "name": "Ayrılan", "updated_at": old},
            {"player_key": "k:kalan", "name": "Kalan", "updated_at": new},
            {"player_key": "apif:1:2024", "name": "K. Eski", "season": "2024", "updated_at": old}]
    assert [r["name"] for r in current_players(rows)] == ["Kalan"]
    assert [r["name"] for r in current_players(rows[2:])] == ["K. Eski"]


def test_refresh_squads_merges_wikipedia_with_apif_history(monkeypatch):
    pool, store, m = _pool(None)
    pool.bsd.available = False
    store.upsert("teams", [{"id": "T1:galatasaray", "league": "T1", "name": "Galatasaray", "ext_ids": {"wikidata": "Q1"}},
                           {"id": "T1:fenerbahce", "league": "T1", "name": "Fenerbahçe", "ext_ids": {}}])
    store.upsert("players", [{"team_id": "T1:galatasaray", "player_key": "apif:9:2024", "name": "U. Çakır",
                              "position": "Goalkeeper", "minutes": 3000, "appearances": 34, "lineups": 34, "goals": 0,
                              "assists": 0, "season": "2024", "source": "api-football", "updated_at": to_iso(now_utc())}])
    monkeypatch.setattr(W, "enwiki_titles", lambda q: {"Q1": "Galatasaray S.K. (football)"})
    monkeypatch.setattr(W, "team_squad", lambda name, hint=None: (W.parse_squad(WIKITEXT), hint or name)
                        if name.startswith("Galata") else ([], None))
    st = pool.news.refresh_squads()
    assert st["wikipedia"] == 1 and st["failed"] == ["Fenerbahçe"]
    cur = pool.news.team_players("T1:galatasaray")
    gk = next(p for p in cur if p["name"] == "Uğurcan Çakır")
    assert gk["minutes"] == 3000 and gk["stats_source"] == "api-football 2024" and gk["shirt_number"] == 1
    assert next(p for p in cur if p["name"] == "Victor Osimhen")["minutes"] is None  # istatistik yok → bilinmiyor


# ---------------------------------------------------------------------- API-Football
class _Resp:
    def __init__(self, data, code=200):
        self._d, self.status_code = data, code

    def json(self):
        return self._d


def test_apif_marks_blocked_season_and_stops_calling(monkeypatch):
    from meclis.sources import api_football as A

    calls = []

    def fake_get(url, params=None, headers=None, **kw):
        calls.append(params)
        return _Resp({"errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."},
                      "response": []})

    monkeypatch.setattr(A, "get", fake_get)
    monkeypatch.setattr(A, "MIN_INTERVAL", 0)
    store = SQLiteStore(":memory:")
    api = A.ApiFootball("x", store)
    with pytest.raises(SourceError):
        api.season_fixtures("T1", 2026)
    assert api.season_blocked(2026) and not api.season_blocked(2024)
    with pytest.raises(SourceError):
        api.season_fixtures("T1", 2026)
    assert len(calls) == 1  # ikinci kez istek atılmadı


class FakeApif:
    available = True

    def __init__(self, store, budget=6):
        self.store, self.daily_budget, self.n = store, budget, 0

    def calls_today(self):
        return self.n

    def season_blocked(self, season):
        return False

    def season_fixtures(self, league, season):
        self.n += 1
        return [{"source": "api-football", "league": league, "kickoff_at": f"{season}-09-01T17:00:00+00:00",
                 "season": str(season), "home_name": "Galatasaray", "away_name": "Fenerbahce", "status": "bitti",
                 "home_goals": 1, "away_goals": 0, "ext_ids": {"apif": 100 + season, "apif_home": 645, "apif_away": 611}}]

    def team_players_page(self, team_apif, season, page):
        self.n += 1
        if team_apif != 645:
            return [], 1
        return [{"player_key": str(page), "name": f"P. Oyuncu{page}", "position": "Attacker", "minutes": 900 * page,
                 "appearances": 10, "lineups": 9, "goals": page, "assists": 0}], 5  # 5 sayfa ama ücretsiz plan ≤3

    def season_injuries(self, league, season):
        self.n += 1
        return [{"player_name": "P. Oyuncu3", "player_id": 3, "team_apif": 645, "team_name": "Galatasaray",
                 "kind": "Missing Fixture", "reason": "Knee", "fixture_apif": 100 + season}]


def test_backfill_is_budgeted_and_resumable():
    from meclis.backfill import Backfill, task_key
    from meclis.pool import DataPool

    store = SQLiteStore(":memory:")
    pool = DataPool(store, Settings(leagues=["T1"]))
    pool.apif = FakeApif(store, budget=3)  # rezerv 0 → bugün 3 istek
    r1 = Backfill(pool, reserve=0, seasons=(2024,)).run()
    assert r1["calls"] == 3 and store.get("source_status", source=task_key("T1", 2024, "fixtures"))["ok"]
    assert "takim=1/2 sayfa=2" in store.get("source_status", source=task_key("T1", 2024, "players"))["message"]
    pool.apif.daily_budget, pool.apif.n = 4, 0  # ertesi gün: sayfa 2-3 (en fazla 3) + sakatlıklar
    r2 = Backfill(pool, reserve=0, seasons=(2024,)).run()
    assert r2["pending"] == 0 and r2["calls"] == 3
    inj = store.select("injuries")
    assert len(inj) == 1 and inj[0]["match_id"] and inj[0]["weight_score"] > 0.5
    assert len([p for p in store.select("players") if p["season"] == "2024"]) == 3
    assert store.select("predictions") == []  # defter tablosuna dokunulmaz


def test_thesportsdb_and_sportdevs_lineup_parsers():
    from meclis.sources.sportdevs import parse_lineups as sd
    from meclis.sources.thesportsdb import parse_lineup as ts

    out = ts([{"strPlayer": "A", "strHome": "Yes", "strSubstitute": "No", "strPosition": "Goalkeeper"},
              {"strPlayer": "B", "strHome": "No", "strSubstitute": "No"},
              {"strPlayer": "C", "strHome": "No", "strSubstitute": "Yes"}])
    assert {o["side"]: len(o["start_xi"]) for o in out} == {"home": 1, "away": 1}
    rows = sd([{"id": 1, "confirmed": True, "home_team": {"formation": "4-4-2", "players": [
        {"player_name": "X", "shirt_number": 9, "position": "F", "substitute": False},
        {"player_name": "Y", "substitute": True}]}, "away_team": {}}])
    assert rows[0]["confirmed"] and rows[0]["start_xi"][0]["name"] == "X" and rows[0]["subs"][0]["name"] == "Y"


def test_apif_date_window_injuries_single_call_per_day(monkeypatch):
    """Ücretsiz plan: dün/bugün/yarın için günün tüm sakatlıkları tek istekte; aynı gündeki ikinci maç istek atmaz."""
    from meclis.sources import api_football as A

    calls = []
    d = now_utc().date().isoformat()

    def fake_get(url, params=None, headers=None, **kw):
        calls.append((url.rsplit("/", 1)[-1], dict(params or {})))
        if "injuries" in url:
            return _Resp({"errors": [], "paging": {"total": 1}, "response": [
                {"player": {"id": 1, "name": "M. Icardi", "type": "Missing Fixture", "reason": "Knee"},
                 "team": {"id": 645, "name": "Galatasaray"}, "fixture": {"id": 555}, "league": {"id": 203}},
                {"player": {"id": 2, "name": "Başka Lig", "type": "Missing Fixture"}, "team": {"id": 1},
                 "fixture": {"id": 999}, "league": {"id": 9999}}]})
        return _Resp({"errors": [], "response": [
            {"fixture": {"id": 555, "date": f"{d}T17:00:00+00:00", "status": {"short": "NS"}},
             "league": {"id": 203, "season": 2026}, "teams": {"home": {"id": 645, "name": "Galatasaray"},
                                                             "away": {"id": 611, "name": "Fenerbahce"}},
             "goals": {}, "score": {}},
            {"fixture": {"id": 777, "date": f"{d}T17:00:00+00:00", "status": {"short": "NS"}},
             "league": {"id": 9999, "season": 2026}, "teams": {"home": {"id": 1, "name": "X"}, "away": {"id": 2, "name": "Y"}},
             "goals": {}, "score": {}}]})

    monkeypatch.setattr(A, "get", fake_get)
    monkeypatch.setattr(A, "MIN_INTERVAL", 0)
    pool, store, m = _pool(None, kickoff_in=timedelta(hours=3))
    pool.bsd.available = False
    pool.apif = A.ApiFootball("x", store)
    fx = pool.apif.fixtures_by_date(now_utc().date(), ["T1"])
    assert len(fx) == 1 and fx[0]["ext_ids"]["apif"] == 555 and fx[0]["season"] == "2026"
    m["ext_ids"] = {"apif": 555, "apif_home": 645, "apif_away": 611}
    store.upsert("matches", [m])
    m2 = dict(m, id="T1:x:diger", ext_ids={"apif": 556})
    rows, known = pool.injuries(m)
    rows2, known2 = pool.injuries(m2)
    assert known and known2 and [r["player_name"] for r in rows] == ["M. Icardi"] and rows2 == []
    ko_day = m["kickoff_at"][:10]
    assert [c[0] for c in calls].count("injuries") == 1 and calls[-1][1] == {"date": ko_day}


def test_apif_team_query_ignores_other_clubs_stats():
    from meclis.sources.api_football import parse_player

    it = {"player": {"id": 9, "name": "U. Çakır"}, "statistics": [
        {"team": {"id": 998, "name": "Trabzonspor"}, "league": {"id": 203}, "games": {"minutes": 2880, "appearences": 32}}]}
    p = parse_player(it, team_apif=645)
    assert p["minutes"] is None and p["no_team_stats"]
    it["statistics"].append({"team": {"id": 645}, "league": {"id": 203}, "games": {"minutes": 90, "appearences": 1},
                             "goals": {"total": 0}})
    assert parse_player(it, team_apif=645)["minutes"] == 90


def test_bsd_odds_and_stats_parsers():
    from meclis.sources import bsd
    o = bsd.parse_odds({"odds": {"home_win": 1.9, "draw": 3.32, "away_win": 4.13, "over_25_goals": 2.24,
                                 "under_25_goals": 1.64, "over_15_goals": None, "under_15_goals": 2.85,
                                 "btts_yes": 1.98, "btts_no": 1.74}})
    assert o["1X2"]["1"] == 1.9 and o["OU_GOALS_2.5"]["ÜST"] == 2.24 and o["BTTS"]["VAR"] == 1.98
    assert "OU_GOALS_1.5" not in o
    assert bsd.parse_odds({"odds": {"home_win": None, "draw": None, "away_win": None}}) == {}
    st = bsd.parse_stats({"stats": {"home": {"total_shots": 13, "shots_on_target": 8, "corner_kicks": 4,
                                             "expected_goals": 2.35, "ball_possession": 38, "yellow_cards": 1},
                                    "away": {"xg": {"actual": None}, "total_shots": None}}})
    assert st == {"home": {"shots": 13, "shots_on_target": 8, "corners": 4, "yellow": 1, "xg": 2.35,
                           "possession": 38.0}}


def test_btts_market_odds_attached():
    from meclis.markets import attach_odds
    p = attach_odds({"market": "BTTS", "selection": "VAR", "line": None, "probability": 0.55},
                    {"BTTS": {"VAR": 1.98, "YOK": 1.74, "src": "bsd:konsensüs"}})
    assert p["odds"] == 1.98 and p["odds_source"] == "bsd:konsensüs"


def test_bsd_aliases():
    from meclis.names import canonical_key
    assert canonical_key("Borussia M'gladbach") == "gladbach"
    assert canonical_key("Amed Sportif Faaliyetler") == "amedspor"
    assert canonical_key("Real Racing Club") == "santander"


def test_news_dedup_by_title_similarity():
    from meclis.news import dedup_news, same_story

    a = {"id": "1", "title": "Galatasaray'da Icardi sakatlandı, derbide yok", "source": "A", "published_at": "2026-10-19T08:00:00+00:00"}
    b = {"id": "2", "title": "Galatasaray'da Icardi sakatlandı derbide yok!", "source": "B", "published_at": "2026-10-19T09:00:00+00:00"}
    c = {"id": "3", "title": "Fenerbahçe yeni teknik direktörünü açıkladı", "source": "A", "published_at": "2026-10-19T10:00:00+00:00"}
    assert same_story(a["title"], b["title"]) and not same_story(a["title"], c["title"])
    rows, dup = dedup_news([a, b, c])
    assert dup == 1 and len(rows) == 2
    g = next(r for r in rows if r["id"] == "1")
    assert g["cluster_size"] == 2 and set(g["sources_all"]) == {"A", "B"}
    # önceki taramadaki kayıtla eşleşen haber yeni satır açmaz
    rows2, dup2 = dedup_news([dict(b, id="9")], previous=[g])
    assert [r["id"] for r in rows2] == ["1"] and dup2 == 1


def test_bsd_league_discovery_filters():
    from meclis.leagues import from_bsd

    raw = [{"id": 96, "name": "Austrian Bundesliga", "country": "Austria", "is_women": False, "is_active": True,
            "current_season": {"end_date": "2027-06-30"}},
           {"id": 1, "name": "Premier League", "country": "England"},  # çekirdekte var
           {"id": 64, "name": "UEFA Nations League", "country": "Europe"},  # milli takım
           {"id": 72, "name": "NWSL", "country": "USA", "is_women": True},
           {"id": 44, "name": "Coupe de France", "country": "France", "current_season": {"end_date": "2026-06-30"}},
           {"id": 43, "name": "DFB Pokal", "country": "Germany", "current_season": {"end_date": "2027-06-30"}}]
    rows = {r["code"]: r for r in from_bsd(raw, "2026-10-20T00:00:00+00:00")}
    assert set(rows) == {"B96", "B43"}
    assert rows["B96"]["country"] == "Avusturya" and not rows["B96"]["cup"] and rows["B43"]["cup"]


def test_closing_odds_from_own_snapshot():
    from meclis.settlement import closing_odds
    from meclis.store import SQLiteStore

    st = SQLiteStore(":memory:")
    st.upsert("teams", [{"id": "T1:a", "league": "T1", "name": "A"}, {"id": "T1:b", "league": "T1", "name": "B"}])
    m = {"id": "T1:x", "league": "T1", "kickoff_at": "2026-10-20T17:00:00+00:00", "home_team_id": "T1:a",
         "away_team_id": "T1:b", "home_name": "A", "away_name": "B", "status": "bitti", "odds": {}}
    st.upsert("matches", [m])
    st.upsert("odds_snapshots", [
        {"match_id": "T1:x", "taken_at": "2026-10-20T13:00:00+00:00", "kickoff_at": m["kickoff_at"], "odds": {"BTTS": {"VAR": 1.9}}},
        {"match_id": "T1:x", "taken_at": "2026-10-20T15:00:00+00:00", "kickoff_at": m["kickoff_at"], "odds": {"BTTS": {"VAR": 1.8}}},
        {"match_id": "T1:x", "taken_at": "2026-10-20T18:00:00+00:00", "kickoff_at": m["kickoff_at"], "odds": {"BTTS": {"VAR": 1.2}}}])
    p = {"match_id": "T1:x", "market": "BTTS", "selection": "VAR", "line": None, "kickoff_at": m["kickoff_at"]}
    o, src = closing_odds(m, p, st)
    assert o == 1.8 and "kendi" in src


def test_season_players_bench_gap_and_with_without():
    from meclis.model.injuries import player_importance
    from meclis.season import parse_player_stats, team_season_players
    from meclis.teamnews import current_players

    team = "T1:a"
    ms, pm = [], []
    for i in range(6):
        mid = f"T1:m{i}"
        star_plays = i < 3
        m = {"id": mid, "home_team_id": team, "away_team_id": "T1:b", "home_name": "A", "away_name": "B",
             "kickoff_at": f"2026-09-0{i + 1}T18:00:00+00:00", "home_goals": 3 if star_plays else 0, "away_goals": 1}
        ms.append(m)
        lu = {"lineups": {"home": {"team_id": 1, "players": [{"id": 10, "name": "Yıldız Forvet", "position": "F"},
                                                             {"id": 11, "name": "Diğer Forvet", "position": "F"}],
                                   "substitutes": [{"id": 12, "name": "Yedek Forvet", "position": "F"}]}}}
        st = {"player_stats": [{"player_id": 10, "team_id": 1, "minutes_played": 90 if star_plays else 0, "goals": 1 if star_plays else 0},
                               {"player_id": 11, "team_id": 1, "minutes_played": 90},
                               {"player_id": 12, "team_id": 1, "minutes_played": 10 if star_plays else 90}]}
        pm += parse_player_stats(lu, st, m)
    assert len(pm) == 18 and pm[0]["team_id"] == team
    sp = {p["name"]: p for p in team_season_players(pm, ms, team)}
    star = sp["Yıldız Forvet"]
    assert star["minutes"] == 270 and star["goals"] == 3
    assert star["d"] is not None and star["d"] > 0.5  # var/yok farkı: onunla +2, onsuz −1 averaj
    assert star["r"] is not None and star["r"] >= 0  # yedek açığı hesaplandı
    squad = [{"player_key": "k:yildizforvet", "name": "Yıldız Forvet", "position": "Forvet", "updated_at": "2026-10-19T00:00:00+00:00"},
             {"player_key": "k:yenitransfer", "name": "Yeni Transfer", "position": "Forvet", "updated_at": "2026-10-19T00:00:00+00:00"}]
    cur = {p["name"]: p for p in current_players(squad, list(sp.values()))}
    assert cur["Yıldız Forvet"]["stats_source"].startswith("bsd 2026/27")
    assert cur["Yeni Transfer"]["minutes"] == 0  # bu sezon oynamadı = bilinen sıfır
    imp = player_importance(cur["Yıldız Forvet"], list(cur.values()))
    assert "d" in imp["components"] and "r" in imp["components"]


def test_backup_export(tmp_path):
    import json

    from meclis.backup import export_all
    from meclis.store import SQLiteStore

    st = SQLiteStore(":memory:")
    st.upsert("teams", [{"id": "T1:a", "league": "T1", "name": "A"}, {"id": "T1:b", "league": "T1", "name": "B"}])
    st.upsert("matches", [{"id": "T1:x", "league": "T1", "kickoff_at": "2026-10-20T17:00:00+00:00", "home_team_id": "T1:a",
                           "away_team_id": "T1:b", "home_name": "A", "away_name": "B", "odds": {"1X2": {"1": 2.0}}}])
    r = export_all(st, tmp_path)
    assert r["counts"]["matches"] == 1
    assert json.loads((tmp_path / "matches.json").read_text())[0]["odds"]["1X2"]["1"] == 2.0
    assert (tmp_path / "predictions.csv").exists() and (tmp_path / "meta.json").exists()
