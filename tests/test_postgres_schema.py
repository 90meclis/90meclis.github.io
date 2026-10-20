"""supabase/schema.sql'i GERÇEK bir PostgreSQL'de doğrular (isteğe bağlı).

Çalıştırmak için boş bir test veritabanı verin:
    MECLIS_TEST_PG_DSN="host=/tmp/pgt port=55432 user=postgres dbname=meclis_test" pytest tests/test_postgres_schema.py
DSN yoksa test atlanır. Uygulamanın Supabase'e (PostgREST) göndereceği satırlar, PostgREST'in kullandığı
json_populate_recordset ile aynı şekilde eklenir; böylece sütun adları/tipleri ve tetikleyiciler sınanır.
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import pytest

DSN = os.environ.get("MECLIS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="MECLIS_TEST_PG_DSN tanımlı değil")
ROOT = Path(__file__).resolve().parent.parent


class PGStore:
    """PostgREST davranışını taklit eden küçük test deposu (yalnızca testler için)."""

    def __new__(cls, conn):
        from meclis.store import PRIMARY_KEYS, StoreError, SupabaseStore

        class _PG(SupabaseStore):  # _clean (sütun süzgeci) Supabase ile birebir aynı
            kind = "postgres-test"

            def __init__(self, conn):
                self.conn = conn
                self.read_only = False

            def _rows(self, table, rows):
                return self._clean(rows, table)

            def _exec(self, sql, args=()):
                import psycopg2

                try:
                    with self.conn.cursor() as cur:
                        cur.execute(sql, args)
                        return cur.fetchall() if cur.description else None
                except psycopg2.Error as e:
                    raise StoreError(str(e).strip()) from e

            def upsert(self, table, rows):
                for r in self._rows(table, rows):
                    cols = list(r)
                    pk = PRIMARY_KEYS[table]
                    upd = [c for c in cols if c not in pk]
                    conflict = f"do update set {', '.join(f'{c}=excluded.{c}' for c in upd)}" if upd else "do nothing"
                    self._exec(f"insert into {table} ({','.join(cols)}) select {','.join(cols)} from "
                               f"json_populate_recordset(null::{table}, %s) on conflict ({','.join(pk)}) {conflict}",
                               (json.dumps([r]),))

            def insert(self, table, rows):
                for r in self._rows(table, rows):
                    cols = list(r)
                    self._exec(f"insert into {table} ({','.join(cols)}) select {','.join(cols)} from "
                               f"json_populate_recordset(null::{table}, %s)", (json.dumps([r]),))
                return rows

            def _where(self, filters):
                parts, args = [], []
                ops = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
                for col, op, val in filters:
                    if op == "in":
                        parts.append(f"{col}::text = any(%s)")
                        args.append([str(v) for v in val])
                    elif op == "is_null":
                        parts.append(f"{col} is {'' if val else 'not '}null")
                    else:
                        parts.append(f"{col} {ops[op]} %s")
                        args.append(val)
                return (" where " + " and ".join(parts)) if parts else "", args

            def select(self, table, filters=(), order=None, desc=False, limit=None):
                w, a = self._where(filters)
                sql = f"select to_jsonb(t) from {table} t{w}"
                if order:
                    sql += f" order by {order} {'desc' if desc else 'asc'}"
                if limit:
                    sql += f" limit {int(limit)}"
                return [r[0] for r in self._exec(sql, a)]

            def update(self, table, values, filters):
                v = self._rows(table, [values])[0]
                w, a = self._where(filters)
                sets = ", ".join(f"{c} = (json_populate_record(null::{table}, %s)).{c}" for c in v)
                self._exec(f"update {table} set {sets}{w}", [json.dumps(v)] * len(v) + a)

        return _PG(conn)


@pytest.fixture(scope="module")
def pg():
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("set timezone = 'UTC'")
        cur.execute("drop schema public cascade; create schema public;")
        for role in ("anon", "authenticated", "service_role"):
            cur.execute(f"do $$ begin if not exists (select 1 from pg_roles where rolname = '{role}') then "
                        f"create role {role} nologin; end if; end $$;")
        sql = (ROOT / "supabase" / "schema.sql").read_text()
        cur.execute(sql)
        cur.execute(sql)  # tekrar çalıştırılabilir olmalı
        cur.execute("grant usage on schema public to anon, authenticated, service_role; "
                    "grant all on all tables in schema public to anon, authenticated, service_role;")
    yield conn
    conn.close()


def test_six_core_tables_exist(pg):
    with pg.cursor() as cur:
        cur.execute("select table_name from information_schema.tables where table_schema='public'")
        names = {r[0] for r in cur.fetchall()}
    assert {"matches", "predictions", "injuries", "trends", "agenda", "sources"} <= names
    assert {"v_tutanak", "v_guven_haftalik", "v_guven_pazar"} <= names


def test_app_rows_fit_schema_and_triggers(pg):
    from meclis.markets import profit_for  # noqa: F401  (paket yüklenebiliyor mu)
    from meclis.bot import _prediction_row
    from meclis.store import SOURCES_SEED, StoreError
    from meclis.timeutil import now_utc, to_iso

    st = PGStore(pg)
    st.upsert("sources", SOURCES_SEED)
    ko = to_iso(now_utc() + timedelta(hours=3))
    m = {"id": "T1:test:a:b", "league": "T1", "season": "2627", "kickoff_at": ko, "home_team_id": "T1:a",
         "away_team_id": "T1:b", "home_name": "A", "away_name": "B", "status": "planlandi", "durum": "gelecek",
         "venue": "Stat", "city": "İstanbul", "ext_ids": {"tsdb": "1"}, "odds": {"1X2": {"1": 2.0, "X": 3.3, "2": 3.6}},
         "sources": {"_all": ["thesportsdb"], "kickoff_at": "thesportsdb"}, "missing_fields": ["referee"],
         "updated_at": to_iso(now_utc())}
    st.upsert("matches", [m])
    st.upsert("matches", [dict(m, referee="Hakem")])
    assert st.get("matches", id=m["id"])["referee"] == "Hakem"
    pick = {"market": "1X2", "selection": "1", "line": None, "probability": 0.55, "odds": 2.0,
            "odds_source": "football-data.co.uk", "edge": 0.1, "confidence": 0.6}
    row = _prediction_row(m, pick, "meclis_gorusu", "test gerekçe", scenario_note="senaryo", completeness=72.5)
    st.insert("predictions", [row])
    got = st.get("predictions", id=row["id"])
    assert got["status"] == "bekliyor" and got["recorded_at"] and float(got["fair_odds"]) == pytest.approx(1.818)
    with pytest.raises(StoreError, match="çekirdek"):
        st.update("predictions", {"odds": 2.5}, [("id", "eq", row["id"])])
    st.update("predictions", {"status": "kazandi", "profit": 1.0, "result_value": "2-1",
                              "settled_at": to_iso(now_utc())}, [("id", "eq", row["id"])])
    with pytest.raises(StoreError, match="Sonuçlanmış"):
        st.update("predictions", {"status": "iade"}, [("id", "eq", row["id"])])
    st.upsert("injuries", [{"id": "i1", "match_id": m["id"], "team_id": "T1:a", "team_name": "A", "player_name": "Oyuncu",
                            "injury_status": "kesin yok", "matches_played": 9, "key_matches": 8, "goal_contribution": 0.3,
                            "defensive_contribution": 0.0, "minutes_share": 0.9, "weight_score": 0.41, "is_key": True,
                            "source": "api-football"}])
    st.upsert("trends", [{"id": "T1:a:corners_o95", "team_id": "T1:a", "team_name": "A", "league": "T1",
                          "market": "korner", "condition": "toplam korner > 9.5", "streak": -2, "hits_last10": 6,
                          "match_values": [{"tarih": "2026-10-10", "rakip": "B", "yer": "E", "değer": 8}]}])
    st.upsert("agenda", [{"id": "n1", "title": "A'da sakatlık", "link": "https://ornek", "source": "rss",
                          "published_at": to_iso(now_utc()), "category": "sakatlık", "match_id": m["id"],
                          "match_ids": [m["id"]], "team_ids": ["T1:a"], "impact_note": "kadro zayıflayabilir"}])
    st.upsert("analysis_queue", [{"match_id": m["id"], "status": "bekliyor", "missing": ["ilk 11"], "attempts": 1,
                                  "last_attempt_at": to_iso(now_utc()), "note": "değer kuralını geçen seçim yok"}])
    with pg.cursor() as cur:
        cur.execute("set role anon")
        cur.execute("select count(*) from v_guven_haftalik")
        assert cur.fetchone()[0] == 1
        cur.execute("select count(*) from v_tutanak where status not in ('bekliyor','basladi','kazandi','kaybetti','iade')")
        assert cur.fetchone()[0] == 0  # yalnızca yayımlanan tahminler; eski 'karar_bekliyor' satırları yok
        cur.execute("select count(*) from sources")
        assert cur.fetchone()[0] == 0  # sources herkese açık değil
        cur.execute("reset role")
    with pytest.raises(StoreError):
        st._exec("delete from predictions")
    with pytest.raises(StoreError, match="başladı"):
        past = dict(m, id="T1:past:a:b", kickoff_at=to_iso(now_utc() - timedelta(minutes=1)))
        st.upsert("matches", [past])
        st.insert("predictions", [_prediction_row(past, pick, "meclis_gorusu", "geç")])


def test_public_views_exclude_singles_that_are_coupon_legs_and_count_coupon_once():
    """19.10.2026: Getafe/Parma hem Günün Kararı ayağı hem Meclis Görüşü idi — herkese açık görünümlerde
    o günün tekli satırı görünmez/sayılmaz; kupon tek kayıttır."""
    import psycopg2

    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute((ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8"))
        cur.execute("""
          insert into matches (id, league, kickoff_at, home_team_id, away_team_id, home_name, away_name) values
            ('VX:1','SP1', now()+interval '5 hours','a','b','Getafe','B'), ('VX:2','I1', now()+interval '5 hours','c','d','Parma','D');
          insert into coupons (id, coupon_date, tag, total_odds, joint_probability, legs_count, first_kickoff_at)
            values ('00000000-0000-0000-0000-0000000000aa', current_date, 'gunun_karari', 3.1, 0.35, 2, now()+interval '5 hours');
          insert into predictions (match_id, kickoff_at, tag, coupon_id, market, selection, probability, odds) values
            ('VX:1', now()+interval '5 hours','gunun_karari','00000000-0000-0000-0000-0000000000aa','1X2','1',0.6,1.8),
            ('VX:2', now()+interval '5 hours','gunun_karari','00000000-0000-0000-0000-0000000000aa','1X2','1',0.6,1.7),
            ('VX:1', now()+interval '5 hours','meclis_gorusu', null, 'OU_GOALS','ALT',0.6,1.8),
            ('VX:2', now()+interval '5 hours','meclis_gorusu', null, 'BTTS','YOK',0.6,1.9);""")
        cur.execute("select count(*) from v_tutanak where tag='meclis_gorusu' and home_name in ('Getafe','Parma')")
        assert cur.fetchone()[0] == 0
        cur.execute("select count(*) from v_arsiv where tag='meclis_gorusu' and home_name in ('Getafe','Parma')")
        assert cur.fetchone()[0] == 0
        cur.execute("select count(*) from v_kayit where id = '00000000-0000-0000-0000-0000000000aa'")
        assert cur.fetchone()[0] == 1
        cur.execute("select count(*) from v_kayit where id in (select id::text from predictions where match_id like 'VX:%')")
        assert cur.fetchone()[0] == 0  # ayaklar ve çakışan tekliler ayrı kayıt değil
    finally:
        conn.rollback()
        conn.close()
