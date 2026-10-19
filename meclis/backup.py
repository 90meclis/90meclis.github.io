"""Gece yedeği: değiştirilemez defterin (predictions, coupons) ve maç havuzunun dışa aktarımı.

Supabase Free otomatik yedek almaz. Bu iş tabloları JSON (tam) ve CSV (düz) olarak bir klasöre yazar; GitHub Actions
iş akışı klasörü depodaki `backups` dalına commit'ler. Böylece (1) defterin ikinci kopyası olur, (2) depoda düzenli
commit olduğu için GitHub 60 gün hareketsizlikte zamanlanmış işleri kapatmaz.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .timeutil import now_utc, to_iso

TABLES = ("predictions", "coupons", "matches", "odds_snapshots", "leagues")


def export_all(store, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts, log = {}, []
    for t in TABLES:
        try:
            rows = store.select(t, order=None)
        except Exception as e:
            log.append(f"⚠️ yedek: {t} okunamadı: {e}")
            continue
        rows = sorted(rows, key=lambda r: json.dumps([r.get(k) for k in ("id", "match_id", "taken_at", "code")], default=str))
        (out / f"{t}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        cols = sorted({k for r in rows for k in r})
        with open(out / f"{t}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: (json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v)
                            for k, v in r.items()})
        counts[t] = len(rows)
    meta = {"exported_at": to_iso(now_utc()), "counts": counts}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log.append("Yedek: " + ", ".join(f"{t} {n}" for t, n in counts.items()) + f" → {out}")
    return {"counts": counts, "log": log}
