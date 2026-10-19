"""Depolama katmanı.

* Supabase (SUPABASE_URL + SUPABASE_KEY varsa) — kalıcı, paylaşımlı önbellek ve defter.
* Yerel SQLite (Supabase yoksa) — yalnızca geliştirme içindir; aynı değiştirilemezlik
  kuralları SQLite tetikleyicileriyle de uygulanır.

Dört temel işlem: upsert, insert, select, update. Silme bilinçli olarak YOK.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from .timeutil import now_utc, to_iso

log = logging.getLogger(__name__)

JSON_COLS: dict[str, set[str]] = {
    "teams": {"aliases", "ext_ids"},
    "matches": {"ext_ids", "odds", "sources", "missing_fields"},
    "lineups": {"start_xi", "subs"},
    "weather": {"data"},
    "agenda": {"team_ids", "match_ids"},
    "trends": {"match_values"},
    "sources": {"fills_fields"},
    "analysis_queue": {"missing"},
    "analyses": {"payload"},
}
BOOL_COLS: dict[str, set[str]] = {"injuries": {"is_key"}, "source_status": {"ok"},
                                  "sources": {"requires_key", "is_active"}}

PRIMARY_KEYS: dict[str, list[str]] = {
    "teams": ["id"],
    "matches": ["id"],
    "match_stats": ["match_id", "side"],
    "players": ["team_id", "player_key"],
    "injuries": ["id"],
    "lineups": ["match_id", "side"],
    "weather": ["match_id"],
    "agenda": ["id"],
    "trends": ["id"],
    "sources": ["name"],
    "analysis_queue": ["match_id"],
    "analyses": ["match_id", "created_at"],
    "source_status": ["source"],
    "coupons": ["id"],
    "predictions": ["id"],
}


class StoreError(RuntimeError):
    pass


Filter = tuple[str, str, Any]  # (kolon, op, değer) op: eq, neq, gt, gte, lt, lte, in, is_null


class BaseStore:
    kind = "base"
    label = ""
    read_only = False

    def upsert(self, table: str, rows: list[dict]) -> None:
        raise NotImplementedError

    def insert(self, table: str, rows: list[dict]) -> list[dict]:
        raise NotImplementedError

    def select(self, table: str, filters: Iterable[Filter] = (), order: str | None = None,
               desc: bool = False, limit: int | None = None) -> list[dict]:
        raise NotImplementedError

    def update(self, table: str, values: dict, filters: Iterable[Filter]) -> None:
        raise NotImplementedError

    # Yardımcılar
    def get(self, table: str, **eq) -> dict | None:
        rows = self.select(table, [(k, "eq", v) for k, v in eq.items()], limit=1)
        return rows[0] if rows else None

    def set_source_status(self, source: str, ok: bool, message: str, add_calls: int = 0) -> None:
        today = now_utc().date().isoformat()
        cur = self.get("source_status", source=source) or {}
        calls = int(cur.get("calls_today") or 0) if cur.get("calls_date") == today else 0
        self.upsert("source_status", [{
            "source": source, "ok": ok, "message": message[:500], "calls_today": calls + add_calls,
            "calls_date": today, "updated_at": to_iso(now_utc()),
        }])


# ----------------------------------------------------------------------------
# SQLite
# ----------------------------------------------------------------------------
_SQLITE_SCHEMA = """
create table if not exists teams (id text primary key, league text not null, name text not null,
  aliases text default '[]', ext_ids text default '{}', stadium text, city text, lat real, lon real, coach text,
  capacity int, updated_at text);
create table if not exists matches (id text primary key, league text not null, season text, kickoff_at text not null,
  home_team_id text not null, away_team_id text not null, home_name text not null, away_name text not null,
  status text not null default 'planlandi' check (status in ('planlandi','basladi','bitti','ertelendi','iptal')),
  durum text not null default 'gelecek' check (durum in ('gelecek','canlı','bitti','ertelendi','iptal')),
  home_goals int, away_goals int, score text, ht_home_goals int, ht_away_goals int, venue text, referee text, city text,
  ext_ids text default '{}', odds text default '{}', sources text default '{}', missing_fields text default '[]',
  completeness real, updated_at text);
create index if not exists matches_kickoff_idx on matches (kickoff_at);
create table if not exists match_stats (match_id text not null, side text not null, team_id text not null,
  shots int, shots_on_target int, corners int, fouls int, yellow int, red int, goal_kicks int, xg real,
  possession real, source text, updated_at text, primary key (match_id, side));
create table if not exists players (team_id text not null, player_key text not null, name text not null,
  position text, minutes int, appearances int, lineups int, goals int, assists int, season text, source text, updated_at text,
  shirt_number int, stats_source text, primary key (team_id, player_key));
create table if not exists injuries (id text primary key, match_id text, team_id text not null, team_name text,
  player_name text not null, injury_status text, reason text, matches_played int, key_matches int,
  goal_contribution real, defensive_contribution real, minutes_share real, weight_score real, is_key int,
  source text, fetched_at text);
create table if not exists trends (id text primary key, team_id text not null, team_name text not null, league text not null,
  market text not null, condition text, streak int not null default 0, hits_last10 int, match_values text default '[]',
  updated_at text);
create table if not exists sources (name text primary key, api_key_secret text, key_storage text, daily_limit int,
  fills_fields text default '[]', requires_key int default 0, license_note text, is_active int default 1, updated_at text);
create table if not exists lineups (match_id text not null, side text not null, formation text, start_xi text default '[]',
  subs text default '[]', coach text, source text, updated_at text, lineup_status text, primary key (match_id, side));
create table if not exists weather (match_id text primary key, data text not null, source text, updated_at text);
create table if not exists agenda (id text primary key, title text not null, link text not null, source text,
  published_at text, summary text, category text, match_id text references matches(id) on delete set null,
  match_ids text default '[]', team_ids text default '[]', impact_note text, fetched_at text);
create table if not exists analysis_queue (match_id text primary key, status text not null default 'bekliyor'
  check (status in ('bekliyor','ertelendi','tamamlandi','yetismedi')), missing text default '[]', attempts int default 0,
  last_attempt_at text, next_retry_at text, note text);
create table if not exists analyses (match_id text not null, created_at text not null, model_version text,
  payload text not null, primary key (match_id, created_at));
create table if not exists source_status (source text primary key, ok int, message text, calls_today int default 0,
  calls_date text, updated_at text);
create table if not exists coupons (id text primary key, created_at text, coupon_date text not null,
  tag text not null check (tag in ('gunun_karari','karar_birligi')), total_odds real not null, joint_probability real,
  legs_count int not null, stake real not null default 1, first_kickoff_at text not null, odds_source text, model_version text, note text,
  status text not null default 'bekliyor' check (status in ('bekliyor','basladi','kazandi','kaybetti','iade')),
  profit real, settled_at text, settlement_note text);
create unique index if not exists coupons_one_per_day on coupons (coupon_date, tag);
create table if not exists predictions (id text primary key, recorded_at text, match_id text not null references matches(id),
  kickoff_at text not null, league text, home_name text, away_name text,
  tag text not null check (tag in ('meclis_gorusu','gunun_karari','karar_birligi')), coupon_id text references coupons(id),
  market text not null, selection text not null, line real, probability real not null check (probability between 0 and 1),
  odds real, odds_source text, fair_odds real, edge real, confidence real, stake real not null default 1, rationale text,
  scenario_note text, completeness real, model_version text, status text not null default 'bekliyor'
  check (status in ('bekliyor','basladi','kazandi','kaybetti','iade')),
  result_value text, profit real, closing_odds real, clv real, settled_at text, settlement_note text);
create unique index if not exists predictions_single_unique on predictions (match_id, market, selection, coalesce(line, -1))
  where tag = 'meclis_gorusu';
create unique index if not exists predictions_leg_unique on predictions (coupon_id, match_id) where coupon_id is not null;

create trigger if not exists predictions_bi before insert on predictions
begin
  select raise(abort, 'Maç bulunamadı') where (select kickoff_at from matches where id = new.match_id) is null;
  select raise(abort, 'kickoff_at maç kaydıyla uyuşmuyor')
    where (select kickoff_at from matches where id = new.match_id) <> new.kickoff_at;
  select raise(abort, 'Maç başladı: tahmin kaydı kapandı')
    where strftime('%Y-%m-%dT%H:%M:%S+00:00','now') >= new.kickoff_at;
  select raise(abort, 'Yeni tahmin yalnızca bekliyor durumuyla eklenebilir') where new.status <> 'bekliyor';
end;
create trigger if not exists predictions_ai after insert on predictions
begin
  update predictions set recorded_at = strftime('%Y-%m-%dT%H:%M:%S+00:00','now') where id = new.id;
end;
create trigger if not exists predictions_bu before update on predictions
when old.recorded_at is not null
begin
  select raise(abort, 'Sonuçlanmış tahmin değiştirilemez') where old.status in ('kazandi','kaybetti','iade');
  select raise(abort, 'Tahminin çekirdek alanları değiştirilemez; yalnızca durum/sonuç güncellenebilir')
  where new.id is not old.id or new.recorded_at is not old.recorded_at or new.match_id is not old.match_id
     or new.kickoff_at is not old.kickoff_at or new.tag is not old.tag or new.coupon_id is not old.coupon_id
     or new.market is not old.market or new.selection is not old.selection or new.line is not old.line
     or new.probability is not old.probability or new.odds is not old.odds or new.odds_source is not old.odds_source
     or new.fair_odds is not old.fair_odds or new.edge is not old.edge or new.confidence is not old.confidence
     or new.stake is not old.stake or new.rationale is not old.rationale or new.model_version is not old.model_version
     or new.scenario_note is not old.scenario_note or new.completeness is not old.completeness
     or new.league is not old.league or new.home_name is not old.home_name or new.away_name is not old.away_name;
end;
create trigger if not exists predictions_bd before delete on predictions
begin select raise(abort, 'Tahmin defteri kayıtları silinemez'); end;

create trigger if not exists coupons_bi before insert on coupons
begin
  select raise(abort, 'Kuponun ilk maçı başladı: kupon kaydı kapandı')
    where strftime('%Y-%m-%dT%H:%M:%S+00:00','now') >= new.first_kickoff_at;
  select raise(abort, 'Yeni kupon yalnızca bekliyor durumuyla eklenebilir') where new.status <> 'bekliyor';
end;
create trigger if not exists coupons_ai after insert on coupons
begin
  update coupons set created_at = strftime('%Y-%m-%dT%H:%M:%S+00:00','now') where id = new.id;
end;
create trigger if not exists coupons_bu before update on coupons
when old.created_at is not null
begin
  select raise(abort, 'Sonuçlanmış kupon değiştirilemez') where old.status in ('kazandi','kaybetti','iade');
  select raise(abort, 'Kuponun çekirdek alanları değiştirilemez')
  where new.id is not old.id or new.created_at is not old.created_at or new.coupon_date is not old.coupon_date
     or new.tag is not old.tag or new.total_odds is not old.total_odds
     or new.joint_probability is not old.joint_probability or new.legs_count is not old.legs_count
     or new.stake is not old.stake or new.first_kickoff_at is not old.first_kickoff_at
     or new.odds_source is not old.odds_source or new.model_version is not old.model_version or new.note is not old.note;
end;
create trigger if not exists coupons_bd before delete on coupons
begin select raise(abort, 'Kupon kayıtları silinemez'); end;
"""


def _encode(table: str, row: dict) -> dict:
    out = {}
    jc = JSON_COLS.get(table, set())
    bc = BOOL_COLS.get(table, set())
    for k, v in row.items():
        if k in jc and v is not None and not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False, default=str)
        elif k in bc and v is not None:
            v = 1 if v else 0
        out[k] = v
    return out


def _decode(table: str, row: dict) -> dict:
    jc = JSON_COLS.get(table, set())
    bc = BOOL_COLS.get(table, set())
    out = dict(row)
    for k in jc:
        if isinstance(out.get(k), str):
            try:
                out[k] = json.loads(out[k])
            except ValueError:
                pass
    for k in bc:
        if k in out and out[k] is not None:
            out[k] = bool(out[k])
    return out


class SQLiteStore(BaseStore):
    kind = "sqlite"

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.label = "Yerel SQLite" + (" (bellek)" if path == ":memory:" else f" ({path})")
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        self.conn.executescript(_SQLITE_SCHEMA)
        if path != ":memory:":
            self._migrate()
        seed_sources(self)

    def _migrate(self) -> None:
        """Eski yerel veritabanına şema aynasında olup dosyada olmayan sütunları ekler."""
        ref = sqlite3.connect(":memory:")
        ref.executescript(_SQLITE_SCHEMA)
        for t in PRIMARY_KEYS:
            have = self._cols(t)
            for cid, name, typ, notnull, default, pk in ref.execute(f"pragma table_info({t})"):
                if name not in have:
                    self.conn.execute(f"alter table {t} add column {name} {typ or ''}"
                                      + (f" default {default}" if default is not None else ""))
        ref.close()

    def _cols(self, table: str) -> set[str]:
        return {r[1] for r in self.conn.execute(f"pragma table_info({table})")}

    def upsert(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        pk = PRIMARY_KEYS[table]
        cols_ok = self._cols(table)
        with self._lock:
            try:
                self.conn.execute("begin")
                for row in rows:
                    r = {k: v for k, v in _encode(table, row).items() if k in cols_ok}
                    cols = list(r)
                    upd = [c for c in cols if c not in pk]
                    sql = (f"insert into {table} ({','.join(cols)}) values ({','.join('?' * len(cols))}) "
                           f"on conflict ({','.join(pk)}) do "
                           + (f"update set {','.join(f'{c}=excluded.{c}' for c in upd)}" if upd else "nothing"))
                    self.conn.execute(sql, [r[c] for c in cols])
                self.conn.execute("commit")
            except sqlite3.Error as e:
                self.conn.execute("rollback")
                raise StoreError(str(e)) from e

    def insert(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        cols_ok = self._cols(table)
        if table in ("predictions", "coupons"):
            cols_ok = cols_ok - {"created_at", "recorded_at"}  # sunucu saatini tetikleyici yazar
        with self._lock:
            try:
                self.conn.execute("begin")
                for row in rows:
                    r = {k: v for k, v in _encode(table, row).items() if k in cols_ok}
                    cols = list(r)
                    self.conn.execute(f"insert into {table} ({','.join(cols)}) values ({','.join('?' * len(cols))})",
                                      [r[c] for c in cols])
                self.conn.execute("commit")
            except sqlite3.Error as e:
                self.conn.execute("rollback")
                raise StoreError(str(e)) from e
        pk = PRIMARY_KEYS[table]
        out = []
        for row in rows:
            if all(k in row for k in pk):
                got = self.get(table, **{k: row[k] for k in pk})
                out.append(got or row)
            else:
                out.append(row)
        return out

    @staticmethod
    def _where(filters: Iterable[Filter]) -> tuple[str, list]:
        parts, args = [], []
        ops = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        for col, op, val in filters:
            if op == "in":
                vals = list(val)
                if not vals:
                    parts.append("0")
                    continue
                parts.append(f"{col} in ({','.join('?' * len(vals))})")
                args.extend(vals)
            elif op == "is_null":
                parts.append(f"{col} is null" if val else f"{col} is not null")
            else:
                parts.append(f"{col} {ops[op]} ?")
                args.append(1 if val is True else 0 if val is False else val)
        return (" where " + " and ".join(parts)) if parts else "", args

    def select(self, table, filters=(), order=None, desc=False, limit=None):
        where, args = self._where(filters)
        sql = f"select * from {table}{where}"
        if order:
            sql += f" order by {order} {'desc' if desc else 'asc'}"
        if limit:
            sql += f" limit {int(limit)}"
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [_decode(table, dict(r)) for r in rows]

    def update(self, table, values, filters):
        enc = _encode(table, values)
        where, args = self._where(filters)
        if not where:
            raise StoreError("Filtresiz güncelleme yapılamaz.")
        sets = ",".join(f"{k}=?" for k in enc)
        with self._lock:
            try:
                self.conn.execute(f"update {table} set {sets}{where}", list(enc.values()) + args)
            except sqlite3.Error as e:
                raise StoreError(str(e)) from e


# ----------------------------------------------------------------------------
# Supabase
# ----------------------------------------------------------------------------
def _no_nan(v):
    """NaN/Infinity geçerli JSON değildir (PostgREST reddeder) → null."""
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return None
    if isinstance(v, dict):
        return {k: _no_nan(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_no_nan(x) for x in v]
    return v


def key_is_read_only(key: str) -> bool:
    """Anahtarın anon/publishable olup olmadığını (doğrulamadan) anlar. Bilinmiyorsa yazılabilir varsayılır."""
    import os

    flag = (os.environ.get("SUPABASE_READONLY") or "").strip().lower()
    if flag in ("1", "true", "evet"):
        return True
    if flag in ("0", "false", "hayir", "hayır"):
        return False
    if key.startswith("sb_publishable_"):
        return True
    if key.startswith("sb_secret_"):
        return False
    parts = key.split(".")
    if len(parts) == 3:
        import base64

        try:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            return json.loads(base64.urlsafe_b64decode(pad)).get("role") == "anon"
        except Exception:
            return False
    return False


class SupabaseStore(BaseStore):
    kind = "supabase"

    def __init__(self, url: str, key: str, read_only: bool | None = None):
        from supabase import create_client

        self.client = create_client(url, key)
        self.read_only = key_is_read_only(key) if read_only is None else read_only
        self.label = "Supabase (salt okunur — anon anahtarı)" if self.read_only else "Supabase"

    def _guard(self, table: str) -> bool:
        """anon anahtarıyla yazma yapılamaz (RLS). Önbellek tabloları sessizce atlanır; defter tabloları hata verir."""
        if not self.read_only:
            return True
        if table in ("predictions", "coupons", "analysis_queue"):
            raise StoreError("Salt okunur bağlantı (anon anahtarı): tahmin defterine yalnızca service_role "
                             "anahtarıyla çalışan bot (GitHub Actions) yazabilir.")
        log.info("salt okunur: %s yazımı atlandı", table)
        return False

    _COLUMNS: dict[str, set[str]] = {}

    @classmethod
    def _known_cols(cls, table: str) -> set[str] | None:
        """Şema aynası (SQLite) ile aynı sütunlar; bilinmeyen anahtarlar PostgREST'e gönderilmez."""
        if not cls._COLUMNS:
            mirror = SQLiteStore()
            for t in PRIMARY_KEYS:
                cls._COLUMNS[t] = mirror._cols(t)
        return cls._COLUMNS.get(table) or None

    MISSING_COLUMNS: dict[str, set[str]] = {}

    def _drop_missing_column(self, table: str, err: Exception) -> bool:
        """PostgREST 'Could not find the 'x' column' (PGRST204) → sütun canlı şemada yok. supabase/schema.sql
        yeniden çalıştırılana kadar o sütun atlanır (veri kaybı değil, yalnızca o alan yazılmaz)."""
        import re as _re

        m = _re.search(r"Could not find the '([^']+)' column", str(err))
        if not m:
            return False
        col = m.group(1)
        miss = SupabaseStore.MISSING_COLUMNS.setdefault(table, set())
        if col in miss:
            return False
        miss.add(col)
        log.warning("Supabase şeması eski: %s.%s yok — supabase/schema.sql'i yeniden çalıştırın", table, col)
        return True

    def _clean(self, rows: list[dict], table: str | None = None) -> list[dict]:
        cols = self._known_cols(table) if table else None
        if table and cols and SupabaseStore.MISSING_COLUMNS.get(table):
            cols = cols - SupabaseStore.MISSING_COLUMNS[table]
        if table in ("predictions", "coupons") and cols:
            cols = cols - {"created_at", "recorded_at"}  # sunucu saatini tetikleyici yazar
        out = [_no_nan(json.loads(json.dumps(r, default=str))) for r in rows]
        return [{k: v for k, v in r.items() if k in cols} for r in out] if cols else out

    def upsert(self, table, rows):
        if not rows or not self._guard(table):
            return
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            for _ in range(4):  # canlı şema eskiyse bilinmeyen sütunu düşürüp yeniden dene
                try:
                    self.client.table(table).upsert(self._clean(chunk, table),
                                                    on_conflict=",".join(PRIMARY_KEYS[table])).execute()
                    break
                except Exception as e:
                    if not self._drop_missing_column(table, e):
                        raise StoreError(f"Supabase upsert hatası ({table}): {e}") from e

    def insert(self, table, rows):
        if not rows or not self._guard(table):
            return []
        try:
            res = self.client.table(table).insert(self._clean(rows, table)).execute()
            return res.data or []
        except Exception as e:
            raise StoreError(f"Supabase insert hatası ({table}): {e}") from e

    @staticmethod
    def _apply(q, filters):
        for col, op, val in filters:
            if op == "in":
                q = q.in_(col, list(val))
            elif op == "is_null":
                q = q.is_(col, "null") if val else q.not_.is_(col, "null")
            else:
                q = getattr(q, op)(col, val)
        return q

    def select(self, table, filters=(), order=None, desc=False, limit=None):
        filters = list(filters)
        if self.read_only and table == "source_status" and not getattr(self, "_no_status_view", False):
            # anon anahtarı source_status tablosunu okuyamaz (RLS); temizlenmiş mesajlı görünüm herkese açıktır
            try:
                return self._select_raw("v_kaynak_durumu", filters, order, desc, limit)
            except Exception:
                self._no_status_view = True  # görünüm henüz yok (schema.sql çalıştırılmadı)
        return self._select_raw(table, filters, order, desc, limit)

    def _select_raw(self, table, filters, order=None, desc=False, limit=None):
        out: list[dict] = []
        page = 1000
        start = 0
        try:
            while True:
                q = self._apply(self.client.table(table).select("*"), filters)
                if order:
                    q = q.order(order, desc=desc)
                end = start + page - 1
                if limit:
                    end = min(end, limit - 1)
                res = q.range(start, end).execute()
                data = res.data or []
                out.extend(data)
                if len(data) < (end - start + 1) or (limit and len(out) >= limit):
                    break
                start += page
        except Exception as e:
            raise StoreError(f"Supabase okuma hatası ({table}): {e}") from e
        return out[:limit] if limit else out

    def update(self, table, values, filters):
        filters = list(filters)
        if not filters:
            raise StoreError("Filtresiz güncelleme yapılamaz.")
        if not self._guard(table):
            return
        try:
            self._apply(self.client.table(table).update(self._clean([values], table)[0]), filters).execute()
        except Exception as e:
            raise StoreError(f"Supabase güncelleme hatası ({table}): {e}") from e


def _sources_seed() -> list[dict]:
    from .sources.registry import SOURCES

    return [src.seed_row() for src in SOURCES]


SOURCES_SEED = _sources_seed()


def seed_sources(store: "BaseStore") -> None:
    """Kaynak listesini idempotent olarak yazar (yeni kaynaklar eklenir, var olanlar güncellenir)."""
    have = {r["name"]: r for r in store.select("sources")}
    rows = [dict(r, updated_at=to_iso(now_utc())) for r in SOURCES_SEED
            if r["name"] not in have or any(have[r["name"]].get(k) != v for k, v in r.items())]
    if rows:
        store.upsert("sources", rows)


_STORE_CACHE: dict[str, BaseStore] = {}


def get_store(settings=None) -> BaseStore:
    from .config import load_settings

    s = settings or load_settings()
    if s.demo_mode:
        key = "demo"
        if key not in _STORE_CACHE:
            from .demo import build_demo_store

            _STORE_CACHE[key] = build_demo_store()
        return _STORE_CACHE[key]
    if s.supabase_enabled:
        key = f"sb:{s.supabase_url}"
        if key not in _STORE_CACHE:
            _STORE_CACHE[key] = SupabaseStore(s.supabase_url, s.supabase_key)
        return _STORE_CACHE[key]
    key = f"sqlite:{s.local_db_path}"
    if key not in _STORE_CACHE:
        _STORE_CACHE[key] = SQLiteStore(s.local_db_path)
    return _STORE_CACHE[key]
