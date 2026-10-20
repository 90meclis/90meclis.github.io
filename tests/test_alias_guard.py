"""Yanlış takım birleştirme koruması (Trabzonspor→Samsunspor, Konyaspor→Alanyaspor, Worthing→Tamworth vakaları)."""
from meclis.pool import TeamRegistry, _similar, learn_aliases


def test_generic_suffix_is_not_similarity():
    for a, b in [("trabzonspor", "samsunspor"), ("konyaspor", "alanyaspor"), ("worthing", "tamworth"),
                 ("scunthorpeunited", "southendunited"), ("istanbulspor", "vanspor"), ("osters", "ostersunds")]:
        assert not _similar(a, b), (a, b)


def test_real_variants_still_similar():
    for a, b in [("hearts", "heartofmidlothian"), ("spgijon", "sportinggijon"), ("forsittard", "fortunasittard"),
                 ("oldham", "oldhamathletic"), ("bristolrvs", "bristolrovers"), ("guimaraes", "vitoriaguimaraes")]:
        assert _similar(a, b), (a, b)


def test_prune_conflicting_stored_alias():
    reg = TeamRegistry()
    reg.add("T1", "trabzonspor", "Trabzonspor")
    reg.add("T1", "samsunspor", "Samsunspor", ["trabzonspor"])
    reg.add("SP1", "barcelona", "Barcelona", ["barca"])
    dropped = reg.prune_conflicting()
    assert ("T1", "trabzonspor", "samsunspor") in dropped
    assert reg._alias("T1", "trabzonspor") == "trabzonspor"
    assert reg._alias("SP1", "barca") == "barcelona"


def test_same_source_names_never_merged():
    reg = TeamRegistry()
    recs = [
        {"league": "T1", "kickoff_at": "2026-08-31T17:00:00Z", "home_name": "Amedspor", "away_name": "Trabzonspor", "source": "a"},
        {"league": "T1", "kickoff_at": "2026-08-31T17:00:00Z", "home_name": "Amedspor", "away_name": "Samsunspor", "source": "b"},
        {"league": "T1", "kickoff_at": "2026-08-30T17:00:00Z", "home_name": "Samsunspor", "away_name": "Rizespor", "source": "a"},
    ]
    learn_aliases(recs, reg)
    assert not reg.learned.get("T1")
