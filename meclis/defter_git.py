"""Değiştirilemez defterin git kopyası (main dalı, defter/ ve muhur/): yalnızca EKLEME yapılır.

* defter/tahminler.jsonl, defter/kuponlar.jsonl — her kilitli kayıt bir kez, kilitlendiği andaki alanlarıyla yazılır;
  var olan satır asla değiştirilmez.
* defter/sonuclar.jsonl — sonuç/durum değişiklikleri ayrı satır olarak eklenir (kayıt değil, olay günlüğü).
* muhur/manifest.json + muhur/kanonik.jsonl — Kanıt Mührü zinciri ve her mührün kanonik içeriği (yeniden doğrulanabilir).
Git geçmişi, hiçbir satırın sonradan değişmediğinin herkese açık kanıtıdır.

Kullanım: python -m meclis.defter_git [kök dizin]   (önce yeni kayıtları mühürler)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .muhur import seal_all, write_manifest

RESULT_FIELDS = ("status", "result_value", "profit", "closing_odds", "clv", "settled_at", "settlement_note")


def _ids(p: Path, key: str = "id") -> set:
    if not p.exists():
        return set()
    return {json.loads(line)[key] for line in p.read_text(encoding="utf-8").splitlines() if line.strip()}


def _append(p: Path, rows: list[dict]) -> int:
    if not rows:
        return 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    return len(rows)


def sync(store, root: str | Path = ".") -> dict:
    root = Path(root)
    s = seal_all(store)
    write_manifest(store, str(root / "muhur"))
    out = {"muhur_yeni": s["yeni"]}
    kp = root / "muhur" / "kanonik.jsonl"
    have = _ids(kp, "seq")
    out["kanonik"] = _append(kp, [{"seq": r["seq"], "ref_table": r["ref_table"], "ref_id": r["ref_id"], "kanonik": r["kanonik"],
                                   "icerik_sha256": r["icerik_sha256"], "sha256": r["sha256"]}
                                  for r in store.select("kanit_muhru", order="seq") if r["seq"] not in have])
    for table, fname, order in (("predictions", "tahminler.jsonl", "recorded_at"), ("coupons", "kuponlar.jsonl", "created_at")):
        p = root / "defter" / fname
        have = _ids(p)
        rows = store.select(table, order=order)
        out[fname] = _append(p, [{k: v for k, v in r.items() if k not in RESULT_FIELDS} for r in rows if r["id"] not in have])
        # sonuç olayları
        sp = root / "defter" / "sonuclar.jsonl"
        seen = set()
        if sp.exists():
            for line in sp.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    e = json.loads(line)
                    seen.add((e["tablo"], e["id"], e["status"]))
        ev = [{"tablo": table, "id": r["id"], **{k: r.get(k) for k in RESULT_FIELDS if k in r}}
              for r in rows if r.get("status") and r["status"] != "bekliyor" and (table, r["id"], r["status"]) not in seen]
        out[f"sonuc:{table}"] = _append(sp, ev)
    return out


if __name__ == "__main__":
    from .store import get_store

    print(sync(get_store(), sys.argv[1] if len(sys.argv) > 1 else "."))
