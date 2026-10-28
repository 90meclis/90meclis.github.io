"""Yerel ayna (egress tasarrufu): sık ve tamamen okunan tablolar (matches, match_stats) her çalışmada Supabase'ten
baştan okunmaz. Ayna dosyası GitHub Actions önbelleğinde işler arasında taşınır; her çalışma yalnızca son
eşitlemeden beri değişen satırları çeker (updated_at > filigran − örtüşme). Bütün yazmalar updated_at damgalar,
böylece başka işlerin yazdıkları da bir sonraki eşitlemede gelir. Silinen satırlar (yalnızca bakım betikleri siler)
14 günde bir tam yenilemeyle temizlenir.

Sorgular aynada Python'da çalışır (eq, neq, gt, gte, lt, lte, in, is_null, like) — çağıranlar değişmez."""
from __future__ import annotations

import fnmatch
import gzip
import json
import logging
import os
import threading
from datetime import timedelta
from pathlib import Path

from .timeutil import now_utc, parse_dt, to_iso

log = logging.getLogger(__name__)

MIRRORED = {"matches": ("id",), "match_stats": ("match_id", "side"), "teams": ("id",), "lineups": ("match_id", "side"),
            "players": ("team_id", "player_key"), "player_matches": ("match_id", "player_id")}
# updated_at sütunu olmayan tablo: yazan iş, yazdığı satırların en küçük kickoff_at değerini bir yazma günlüğüne
# (source_status 'ayna:<tablo>') ekler; okuyan, son eşitlemesinden sonraki günlük kayıtlarının penceresini çeker.
LOG_MODE = {"player_matches": "kickoff_at"}
OVERLAP = timedelta(hours=2)
FULL_EVERY = timedelta(days=14)
VERSION = 1


def ayna_dir() -> Path:
    return Path(os.environ.get("MECLIS_AYNA_DIR", ".ayna"))


def _cmp_val(col: str, v):
    if v is None:
        return None
    if col.endswith("_at") and isinstance(v, str):
        d = parse_dt(v)
        return d if d else v
    return v


def _match(row: dict, filters) -> bool:
    for col, op, val in filters:
        v = row.get(col)
        if op == "eq":
            if _cmp_val(col, v) != _cmp_val(col, val) and str(v) != str(val):
                return False
        elif op == "neq":
            if _cmp_val(col, v) == _cmp_val(col, val):
                return False
        elif op in ("gt", "gte", "lt", "lte"):
            a, b = _cmp_val(col, v), _cmp_val(col, val)
            if a is None or b is None:
                return False
            try:
                ok = {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
            except TypeError:
                ok = {"gt": str(a) > str(b), "gte": str(a) >= str(b), "lt": str(a) < str(b), "lte": str(a) <= str(b)}[op]
            if not ok:
                return False
        elif op == "in":
            if v not in set(val):
                return False
        elif op == "is_null":
            if (v is None) != bool(val):
                return False
        elif op in ("like", "ilike"):
            pat = str(val).replace("%", "*").replace("_", "?")
            s = "" if v is None else str(v)
            if not (fnmatch.fnmatchcase(s, pat) if op == "like" else fnmatch.fnmatch(s.lower(), pat.lower())):
                return False
        else:
            raise ValueError(f"aynada desteklenmeyen filtre: {op}")
    return True


def _copy(r: dict) -> dict:
    return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in r.items()}


class Mirror:
    def __init__(self, table: str, fetch_since, fetch_all, read_log=None, fetch_keys=None, fetch_rows=None):
        """fetch_since(iso) → updated_at > iso satırları (günlük kipinde: kickoff_at ≥ iso); fetch_all() → bütün
        tablo; read_log() → günlük kipinde [{"at","min"}]."""
        self.read_log = read_log
        self._fetch_keys, self._fetch_rows = fetch_keys, fetch_rows
        self.synced_at: str | None = None
        self.table, self.keys = table, MIRRORED[table]
        self._fetch_since, self._fetch_all = fetch_since, fetch_all
        self.rows: dict[tuple, dict] = {}
        self.watermark: str | None = None
        self.full_at: str | None = None
        self.ready = False
        self.dirty = False
        self.lock = threading.RLock()
        self.pulled = 0  # bu çalışmada sunucudan gelen satır

    def path(self) -> Path:
        return ayna_dir() / f"{self.table}.json.gz"

    def key(self, r: dict) -> tuple:
        return tuple(r.get(k) for k in self.keys)

    def _load(self) -> None:
        p = self.path()
        if not p.exists():
            return
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("v") != VERSION:
                return
            self.rows = {self.key(r): r for r in d["rows"]}
            self.watermark, self.full_at = d.get("watermark"), d.get("full_at")
            self.synced_at = d.get("synced_at")
        except Exception as e:  # bozuk dosya: tam yenileme
            log.warning("ayna okunamadı (%s): %s", self.table, e)
            self.rows, self.watermark, self.full_at = {}, None, None

    def _bump(self, rows: list[dict]) -> None:
        for r in rows:
            u = r.get("updated_at")
            if u and (self.watermark is None or parse_dt(u) > parse_dt(self.watermark)):
                self.watermark = to_iso(u)

    def ensure(self) -> None:
        with self.lock:
            if self.ready:
                return
            self._load()
            now = now_utc()
            full = not self.rows or not self.full_at or now - parse_dt(self.full_at) > FULL_EVERY or \
                (self.table not in LOG_MODE and not self.watermark)
            if full:
                rows = self._fetch_all()
                self.rows = {self.key(r): r for r in rows}
                self.full_at = to_iso(now)
                self.watermark = None
                self._bump(rows)
                self.pulled += len(rows)
            elif self.table in LOG_MODE:
                ents = [e for e in (self.read_log() if self.read_log else []) or []
                        if e.get("min") and (not self.synced_at or parse_dt(e["at"]) > parse_dt(self.synced_at) - OVERLAP)]
                rows = self._fetch_since(min(to_iso(e["min"]) for e in ents)) if ents else []
                for r in rows:
                    self.rows[self.key(r)] = r
                self.pulled += len(rows)
            else:
                since = to_iso(parse_dt(self.watermark) - OVERLAP)
                if self._fetch_keys and self._fetch_rows:
                    ks = self._fetch_keys(since)
                    stale = [k for k in ks if not self._same_stamp(k)]
                    self._bump(ks)
                    vals = sorted({str(k[self.keys[0]]) for k in stale})
                    rows = self._fetch_rows(vals) if vals else []
                else:
                    rows = self._fetch_since(since)
                for r in rows:
                    self.rows[self.key(r)] = r
                self._bump(rows)
                self.pulled += len(rows)
            self.synced_at = to_iso(now)
            self.ready = True
            self.dirty = True

    def _same_stamp(self, k: dict) -> bool:
        cur = self.rows.get(self.key(k))
        if cur is None or not cur.get("updated_at") or not k.get("updated_at"):
            return False
        return parse_dt(cur["updated_at"]) == parse_dt(k["updated_at"])

    def select(self, filters, order=None, desc=False, limit=None) -> list[dict]:
        self.ensure()
        with self.lock:
            out = [r for r in self.rows.values() if _match(r, filters)]
        if order:
            nn = [r for r in out if r.get(order) is not None]
            nulls = [r for r in out if r.get(order) is None]
            nn.sort(key=lambda r: _cmp_val(order, r.get(order)), reverse=desc)
            out = nn + nulls if not desc else nulls + nn  # PostgREST: asc → nulls last, desc → nulls first
        if limit:
            out = out[:limit]
        return [_copy(r) for r in out]

    def unchanged(self, row: dict) -> bool:
        """Yazılacak satır aynadakiyle (updated_at hariç) aynı mı? Aynıysa yazılmaz (yazma+yeniden okuma tasarrufu)."""
        if not self.ready:
            return False
        cur = self.rows.get(self.key(row))
        if cur is None:
            return False
        for k, v in row.items():
            if k == "updated_at":
                continue
            a = cur.get(k)
            if a == v:
                continue
            if k.endswith("_at") and a and v and parse_dt(a) == parse_dt(v):
                continue
            if isinstance(v, float) and isinstance(a, (int, float)) and abs(a - v) < 1e-9:
                continue
            return False
        return True

    def apply_upsert(self, rows: list[dict]) -> None:
        if not self.ready:
            return
        with self.lock:
            for r in rows:
                k = self.key(r)
                self.rows[k] = {**self.rows.get(k, {}), **r}
            self.dirty = True

    def apply_update(self, values: dict, filters) -> None:
        if not self.ready:
            return
        with self.lock:
            for k, r in self.rows.items():
                if _match(r, filters):
                    r.update(values)
            self.dirty = True

    def save(self) -> None:
        if not self.ready or not self.dirty:
            return
        p = self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with self.lock:
            d = {"v": VERSION, "table": self.table, "watermark": self.watermark, "full_at": self.full_at,
                 "synced_at": self.synced_at,
                 "saved_at": to_iso(now_utc()), "rows": list(self.rows.values())}
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"), default=str)
        os.replace(tmp, p)
        self.dirty = False


# ----------------------------------------------------------------------------- egress ölçer
class Egress:
    """Supabase'ten gelen yanıt baytları (JSON gövdesinin yaklaşık boyutu), tablo başına."""
    bytes: dict[str, int] = {}
    lock = threading.Lock()

    @classmethod
    def add(cls, table: str, data) -> None:
        try:
            n = len(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).encode())
        except Exception:
            n = 0
        with cls.lock:
            cls.bytes[table] = cls.bytes.get(table, 0) + n + 300  # +başlıklar

    @classmethod
    def total(cls) -> int:
        return sum(cls.bytes.values())

    @classmethod
    def top(cls, k: int = 4) -> str:
        return ", ".join(f"{t} {b / 1e6:.1f}" for t, b in sorted(cls.bytes.items(), key=lambda x: -x[1])[:k])


def frozen_analysis(store, match_id: str) -> dict | None:
    """Kilitli/yayımlanmış maçın analizi değişmez (yeniden hesaplanmaz): bir kez okunur, aynada saklanır."""
    import hashlib

    p = ayna_dir() / "analiz" / (hashlib.sha1(match_id.encode()).hexdigest() + ".json.gz")
    if p.exists():
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    rows = store.select("analyses", [("match_id", "eq", match_id)], order="created_at", desc=True, limit=1)
    a = rows[0]["payload"] if rows else None
    if a is not None and getattr(store, "kind", "") == "supabase":
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(p, "wt", encoding="utf-8") as f:
                json.dump(a, f, ensure_ascii=False, default=str)
        except Exception:
            pass
    return a
