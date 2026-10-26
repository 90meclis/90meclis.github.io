from meclis.senaryo import build_film


def _payload():
    return {"home": "Ev FK", "away": "Dep SK",
            "lambdas": {"home": 1.6, "away": 1.0, "base_home": 1.7, "base_away": 1.0, "rho": -0.05, "ht_ratio": 0.44},
            "count_info": {"corners": {"home": 5.5, "away": 4.0, "total": 9.5}, "cards": {"home": 2.0, "away": 2.4, "total": 4.4}},
            "predicted_xi": {"home": {"players": [{"name": "Golcü A", "position": "F", "score": 0.9},
                                                  {"name": "Orta B", "position": "M", "score": 0.95}]}},
            "injury_effect": {"home_mult": 0.94, "away_mult": 1.0, "home_missing": [{"name": "Yıldız C", "importance": 0.4}]},
            "weather": {"temperature_c": 12, "wind_kmh": 18},
            "best_pick": {"market": "OU_GOALS", "selection": "ÜST", "line": 2.5, "probability": 0.55}}


def test_film_scenarios_partition_and_fields():
    f = build_film(_payload(), {"venue": "Test Stadı", "referee": "Hakem D"},
                   {"venue_split": {"home": {"n": 4, "gf": 2.0, "ga": 0.75, "cf": 6.1}}, "rest": {"home": 4.0}})
    ana = [s for s in f["liste"] if s["tur"] == "ana"]
    assert 0.97 <= sum(s["olasilik"] for s in ana) <= 1.0001
    s = ana[0]
    assert len(s["perde"]) == 5 and s["perde"][0]["dakika"] == "0–15′" and "Test Stadı" in s["perde"][0]["metin"]
    assert s["final_skor"] and s["skorlar"] and s["meclis_secimi"]["durum"] in ("kazanır", "kaybeder", "belirsiz")
    assert any("iç sahada 4 maçta" in d for d in s["dayanaklar"])
    assert f["eksik_etkisi"] and f["eksik_etkisi"]["eksikler_oynasaydi"]["1X2"]["1"] > f["eksik_etkisi"]["eksiklerle"]["1X2"]["1"]


def test_seal_chain_is_deterministic_and_verifiable(tmp_path):
    from meclis.muhur import COUPON_FIELDS, canonical, seal_all, sha, write_manifest
    from meclis.store import SQLiteStore

    from datetime import timedelta

    from meclis.timeutil import now_utc

    # sabit tarih kullanılmaz: kupon kaydı ilk maç başlamadan önce olmalı (tetikleyici), yoksa test takvime bağlı düşer
    ko = (now_utc() + timedelta(days=2)).replace(microsecond=0)
    st = SQLiteStore(":memory:")
    st.insert("coupons", [{"id": "c1", "created_at": (ko - timedelta(hours=10)).isoformat(),
                           "coupon_date": ko.date().isoformat(), "tag": "gunun_karari", "total_odds": 2.5,
                           "legs_count": 2, "first_kickoff_at": ko.isoformat(), "stake": 1, "status": "bekliyor"}])
    r = seal_all(st)
    assert r["yeni"] == 1 and seal_all(st)["yeni"] == 0
    row = st.select("kanit_muhru")[0]
    c = canonical(st.select("coupons")[0], COUPON_FIELDS)
    assert row["sha256"] == sha("0" * 64 + sha(c))
    assert write_manifest(st, str(tmp_path))["kok"] == row["sha256"]


def test_registry_never_maps_distinct_clubs_with_shared_suffix():
    from meclis.pool import TeamRegistry, _similar

    for a, b in (("trabzonspor", "samsunspor"), ("konyaspor", "alanyaspor"), ("worthing", "tamworth"),
                 ("scunthorpeunited", "southendunited"), ("istanbulspor", "vanspor")):
        assert not _similar(a, b)
    reg = TeamRegistry()
    reg.add("T1", "samsunspor", "Samsunspor", aliases=["trabzonspor"])  # zehirli eski takma ad
    reg.add("T1", "trabzonspor", "Trabzonspor")
    reg.prune_conflicting()
    assert reg.resolve("T1", "Trabzonspor") == "trabzonspor"


def test_lineup_with_grid_bsd_pos():
    from meclis.xi import with_grid

    xi = [{"pos": "G", "name": "K"}] + [{"pos": "D", "name": f"D{i}"} for i in range(4)] + \
         [{"pos": "M", "name": f"M{i}"} for i in range(5)] + [{"pos": "F", "name": "F"}]
    row = with_grid({"match_id": "x", "side": "home", "formation": "4-2-3-1", "start_xi": xi})
    grids = [p["grid"] for p in row["start_xi"]]
    assert grids[0] == "1:1" and grids[1:5] == ["2:1", "2:2", "2:3", "2:4"] and grids[-1] == "5:1"
    assert row["start_xi"][0]["pos"] == "G" and "position" not in row["start_xi"][0]
    keep = with_grid({"start_xi": [{"name": "a", "grid": "1:1"}]})
    assert keep["start_xi"][0]["grid"] == "1:1"
