"""Kanıt Mührü: kilitli her tahmin ve kuponun SHA-256 mührü + zincir (her mühür bir öncekinin özetini içerir).

Kanonik içerik = değişmez alanlar, anahtar sırasına göre JSON (ayırıcılar ',' ':' , ensure_ascii=False).
Doğrulama: aynı alanlarla sha256(kanonik) yeniden hesaplanır; zincir kök özeti manifest dosyasına yazılır ve her gece
depoya commit edilir (muhur/manifest.json) — kaydın sonradan değişmediğinin herkese açık kanıtı.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .timeutil import now_utc, to_iso

PRED_FIELDS = ("id", "recorded_at", "match_id", "kickoff_at", "home_name", "away_name", "tag", "coupon_id", "market",
               "selection", "line", "probability", "odds", "odds_source", "edge", "model_version")
COUPON_FIELDS = ("id", "created_at", "coupon_date", "tag", "total_odds", "joint_probability", "legs_count",
                 "first_kickoff_at", "odds_source", "model_version")


def _norm(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


def canonical(row: dict, fields) -> str:
    return json.dumps({k: _norm(row.get(k)) for k in fields}, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def seal_all(store) -> dict:
    have = {(r["ref_table"], r["ref_id"]) for r in store.select("kanit_muhru")}
    last = store.select("kanit_muhru", order="seq", desc=True, limit=1)
    prev, seq = (last[0]["sha256"], int(last[0]["seq"])) if last else ("0" * 64, 0)
    rows = []
    items = [("coupons", r, COUPON_FIELDS, r.get("created_at")) for r in store.select("coupons")] + \
            [("predictions", r, PRED_FIELDS, r.get("recorded_at")) for r in store.select("predictions")]
    for tbl, r, f, ts in sorted(items, key=lambda x: str(x[3] or "")):
        if (tbl, r["id"]) in have:
            continue
        c = canonical(r, f)
        h = sha(prev + sha(c))  # zincir: önceki mühür + bu kaydın özeti
        seq += 1
        rows.append({"ref_table": tbl, "ref_id": r["id"], "seq": seq, "icerik_sha256": sha(c), "sha256": h,
                     "onceki_sha256": prev, "kanonik": c, "muhurlendi_at": to_iso(now_utc())})
        prev = h
    for i in range(0, len(rows), 200):
        store.upsert("kanit_muhru", rows[i:i + 200])
    return {"yeni": len(rows), "kok": prev, "toplam": seq}


def write_manifest(store, out_dir: str) -> dict:
    rows = store.select("kanit_muhru", order="seq")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    man = {"aciklama": "90 Meclis Kanıt Mührü — her satır: sha256(önceki_mühür + sha256(kanonik kayıt)). "
                       "Kök, zincirin son mührüdür.",
           "olusturuldu": to_iso(now_utc()), "kayit": len(rows), "kok": rows[-1]["sha256"] if rows else None,
           "muhurler": [{k: r[k] for k in ("seq", "ref_table", "ref_id", "icerik_sha256", "sha256", "muhurlendi_at")}
                        for r in rows]}
    Path(out_dir, "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"kayit": len(rows), "kok": man["kok"]}
