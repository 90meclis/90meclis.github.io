from datetime import timedelta

from meclis import ayna
from meclis.ayna import Egress, Mirror
from meclis.timeutil import now_utc, to_iso


def _rows():
    t = now_utc()
    return [
        {"id": "a", "league": "E0", "kickoff_at": to_iso(t + timedelta(hours=1)), "home_goals": None, "updated_at": to_iso(t - timedelta(hours=5))},
        {"id": "b", "league": "SP1", "kickoff_at": to_iso(t - timedelta(days=1)), "home_goals": 2, "updated_at": to_iso(t - timedelta(hours=4))},
        {"id": "c", "league": "E0", "kickoff_at": to_iso(t - timedelta(days=2)), "home_goals": 0, "updated_at": to_iso(t - timedelta(hours=3))},
    ]


def test_mirror_filters_order_and_incremental(tmp_path, monkeypatch):
    monkeypatch.setenv("MECLIS_AYNA_DIR", str(tmp_path))
    calls = {"all": 0, "since": []}
    data = _rows()

    def fetch_all():
        calls["all"] += 1
        return [dict(r) for r in data]

    def fetch_since(since):
        calls["since"].append(since)
        return [dict(r) for r in data if r["updated_at"] > since]

    m = Mirror("matches", fetch_since, fetch_all)
    assert [r["id"] for r in m.select([("league", "eq", "E0")], order="kickoff_at")] == ["c", "a"]
    assert [r["id"] for r in m.select([], order="home_goals", desc=True)] == ["a", "b", "c"]  # null önce (desc)
    assert [r["id"] for r in m.select([("home_goals", "is_null", False), ("id", "in", ["b", "c", "z"])])] == ["b", "c"]
    assert m.select([("kickoff_at", "gte", to_iso(now_utc()))])[0]["id"] == "a"
    assert m.select([("league", "like", "S%")])[0]["id"] == "b"
    assert calls["all"] == 1
    # değişmeyen satır tespiti
    assert m.unchanged({"id": "b", "home_goals": 2, "updated_at": "x"})
    assert not m.unchanged({"id": "b", "home_goals": 3})
    m.save()

    # ikinci çalışma: diskten yüklenir, yalnızca değişen satır çekilir
    data[1] = dict(data[1], home_goals=5, updated_at=to_iso(now_utc()))
    m2 = Mirror("matches", fetch_since, fetch_all)
    got = m2.select([("id", "eq", "b")])
    assert got[0]["home_goals"] == 5 and calls["all"] == 1 and len(calls["since"]) == 1
    # dönen kopya aynayı bozmaz
    got[0]["home_goals"] = 99
    assert m2.select([("id", "eq", "b")])[0]["home_goals"] == 5


def test_mirror_apply_and_full_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("MECLIS_AYNA_DIR", str(tmp_path))
    data = _rows()
    n = {"all": 0}

    def fetch_all():
        n["all"] += 1
        return [dict(r) for r in data]

    m = Mirror("matches", lambda s: [], fetch_all)
    m.ensure()
    m.apply_upsert([{"id": "d", "league": "D1", "kickoff_at": to_iso(now_utc()), "updated_at": to_iso(now_utc())}])
    assert m.select([("league", "eq", "D1")])[0]["id"] == "d"
    m.full_at = to_iso(now_utc() - ayna.FULL_EVERY - timedelta(hours=1))
    m.save()
    m3 = Mirror("matches", lambda s: [], fetch_all)
    m3.ensure()
    assert n["all"] == 2  # 14 gün → tam yenileme (silinenler temizlenir)


def test_egress_meter():
    Egress.bytes.clear()
    Egress.add("matches", [{"id": "x" * 100}])
    assert Egress.total() > 100 and "matches" in Egress.top()


def test_two_phase_sync_fetches_only_changed(tmp_path, monkeypatch):
    monkeypatch.setenv("MECLIS_AYNA_DIR", str(tmp_path))
    data = _rows()
    got = {"rows": []}
    m = Mirror("matches", None, lambda: [dict(r) for r in data])
    m.ensure()
    m.save()
    t = to_iso(now_utc())
    data[0] = dict(data[0], home_goals=1, updated_at=t)
    keys = lambda since: [{"id": r["id"], "updated_at": r["updated_at"]} for r in data if r["updated_at"] > since]

    def rows(vals):
        got["rows"].append(vals)
        return [dict(r) for r in data if r["id"] in vals]

    m2 = Mirror("matches", None, lambda: [], fetch_keys=keys, fetch_rows=rows)
    assert m2.select([("id", "eq", "a")])[0]["home_goals"] == 1
    assert got["rows"] == [["a"]]  # b ve c (değişmemiş) yeniden çekilmedi
