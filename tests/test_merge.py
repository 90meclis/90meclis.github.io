from meclis.names import canonical_key, mentions_team, same_team
from meclis.pool import TeamRegistry, merge_records


def rec(source, home, away, ko, **kw):
    return {"source": source, "league": "T1", "home_name": home, "away_name": away, "kickoff_at": ko, **kw}


def test_turkish_names_unify_across_sources():
    assert canonical_key("İstanbul Başakşehir") == canonical_key("Buyuksehyr") == "basaksehir"
    assert canonical_key("Göztepe") == canonical_key("Goztep")
    assert canonical_key("Çorum") == canonical_key("Corum")
    assert same_team("Amed", "Amedspor")
    assert not same_team("Örnek Takım A", "Örnek Takım B")
    assert not same_team("Manchester City", "Manchester United")


def test_merge_fills_missing_fields_and_keeps_provenance():
    recs = [
        rec("football-data.co.uk", "Buyuksehyr", "Gaziantep", "2026-10-18T15:00:00+00:00",
            status="bitti", home_goals=2, away_goals=1, ht_home_goals=1, ht_away_goals=0,
            odds={"1X2": {"1": 1.9, "X": 3.4, "2": 4.0}},
            stats={"home": {"corners": 6, "shots_on_target": 5}, "away": {"corners": 3, "shots_on_target": 2}}),
        rec("thesportsdb", "İstanbul Başakşehir", "Gaziantep", "2026-10-18T16:00:00+00:00",
            status="bitti", home_goals=2, away_goals=1, venue="Başakşehir Fatih Terim Stadyumu",
            ext_ids={"tsdb": "1", "apif": 99}),
        rec("api-football", "Basaksehir", "Gaziantep FK", "2026-10-18T16:00:00+00:00",
            status="bitti", home_goals=2, away_goals=1, referee="Hakem X",
            stats={"home": {"goal_kicks": 7}, "away": {"goal_kicks": 9, "corners": 4}}),
    ]
    out = merge_records(recs)
    assert len(out) == 1
    m = out[0]
    assert m["venue"] and m["referee"] == "Hakem X" and m["ht_home_goals"] == 1
    assert m["kickoff_at"] == "2026-10-18T16:00:00+00:00"           # api-football önceliği
    assert m["sources"]["kickoff_at"] == "api-football"
    assert m["sources"]["venue"] == "thesportsdb"
    assert m["stats"]["home"]["corners"] == 6 and m["stats"]["home"]["goal_kicks"] == 7
    assert m["stats"]["away"]["corners"] == 4                          # öncelikli kaynak
    assert m["ext_ids"]["apif"] == 99 and m["odds"]["1X2"]["1"] == 1.9
    assert set(m["sources"]["_all"]) == {"football-data.co.uk", "thesportsdb", "api-football"}
    assert m["home_name"] == "Başakşehir"


def test_match_never_dropped_and_conflict_logged():
    recs = [
        rec("thesportsdb", "Trabzonspor", "Beşiktaş", "2026-10-19T17:00:00+00:00", status="planlandi"),
        rec("football-data.co.uk", "Trabzonspor", "Besiktas", "2026-10-19T17:00:00+00:00", status="planlandi"),
        rec("thesportsdb", "Takım Yok", "Bilinmeyen", "2026-10-19T17:00:00+00:00"),  # tek kaynak, eksik alanlı
        rec("api-football", "Fenerbahce", "Alanyaspor", "2026-10-17T16:00:00+00:00", status="bitti", home_goals=3, away_goals=0),
        rec("football-data.co.uk", "Fenerbahce", "Alanyaspor", "2026-10-17T16:00:00+00:00", status="bitti", home_goals=3, away_goals=1),
    ]
    out = merge_records(recs)
    assert len(out) == 3
    fb = next(m for m in out if "fenerbahce" in m["id"])
    assert fb["away_goals"] == 0 and fb["sources"]["_conflicts"]


def test_existing_id_reused_when_kickoff_moves():
    existing = [{"id": "T1:2026-10-19:trabzonspor:besiktas", "league": "T1", "home_team_id": "T1:trabzonspor",
                 "away_team_id": "T1:besiktas", "home_name": "Trabzonspor", "away_name": "Beşiktaş",
                 "kickoff_at": "2026-10-19T17:00:00+00:00", "status": "planlandi", "referee": "Eski Hakem"}]
    out = merge_records([rec("thesportsdb", "Trabzonspor", "Beşiktaş", "2026-10-20T10:00:00+00:00")], TeamRegistry(), existing)
    assert out[0]["id"] == existing[0]["id"] and out[0]["referee"] == "Eski Hakem"


def test_news_team_mention_with_turkish_suffix():
    assert mentions_team("Fenerbahçe'nin yıldızı sakatlandı", "Fenerbahce")
    assert mentions_team("Galatasaray'da ayrılık", "Galatasaray")
    assert not mentions_team("Beşiktaş kazandı", "Trabzonspor")
