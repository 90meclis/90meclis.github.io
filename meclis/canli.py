"""Canlı skor: başlamış ve bitmemiş maçların skoru/dakikası (Maç Merkezi için). Sık ve hafif çalışır;
kotalı kaynak kullanmaz. Resmî sonuç (status='bitti', goller) yalnızca sonuç işinde yazılır."""
from __future__ import annotations

from datetime import timedelta

from . import names
from .pool import _similar
from .timeutil import now_utc, parse_dt, to_iso


def _same(a: str, b: str) -> bool:
    ka, kb = names.canonical_key(a), names.canonical_key(b)
    return ka == kb or names.same_team(ka, kb) or _similar(ka, kb)


def pair(m: dict, events: list[dict]) -> dict | None:
    ko = parse_dt(m["kickoff_at"])
    best = None
    for e in events:
        eko = parse_dt(e["ko"])
        if not eko or abs((eko - ko).total_seconds()) > 20 * 60:
            continue
        if _same(m["home_name"], e["home"]) and _same(m["away_name"], e["away"]):
            if best:  # iki aday: belirsiz → yazma
                return None
            best = e
    return best


def run(store, log: list, fetch=None) -> int:
    from .sources import espn

    fetch = fetch or espn.scoreboard
    now = now_utc()
    ms = [m for m in store.select("matches", [("kickoff_at", "gte", to_iso(now - timedelta(hours=3))),
                                              ("kickoff_at", "lte", to_iso(now + timedelta(minutes=5)))])
          if m.get("status") in ("planlandi", "basladi", None) and not str(m.get("league", "")).startswith("Y")]
    if not ms:
        log.append("ℹ️ canlı: oynanan maç yok")
        return 0
    days = sorted({(parse_dt(m["kickoff_at"])).date() for m in ms})
    events: list[dict] = []
    for d in days:
        events += fetch(parse_dt(d.isoformat() + "T12:00:00Z"))
    n = 0
    for m in ms:
        e = pair(m, events)
        if not e or not (e["canli"] or e["bitti"]):
            continue
        src = dict(m.get("sources") or {})
        src["_canli"] = {"kaynak": "ESPN", "durum": e["durum"], "dakika": e["dakika"], "skor": f"{e['hg']}-{e['ag']}",
                         "at": to_iso(now), "bitti": e["bitti"]}
        store.update("matches", {"score": f"{e['hg']}-{e['ag']}", "durum": "canlı", "sources": src},
                     [("id", "eq", m["id"])])
        n += 1
    log.append(f"✅ canlı: {n}/{len(ms)} maçın skoru güncellendi (ESPN, {len(events)} etkinlik)")
    return n


def run_static(out_dir, log: list, fetch=None, now=None) -> int:
    """Supabase'siz canlı skor: maç listesi statik gün dosyalarından okunur, sonuç `canli.json`'a yazılır
    (site bu dosyayı Maç Merkezi'ne bindirir). Veritabanına hiçbir okuma/yazma yapılmaz (egress 0)."""
    import json
    from pathlib import Path

    from .sources import espn
    from .timeutil import TR

    fetch = fetch or espn.scoreboard
    out = Path(out_dir)
    now = now or now_utc()
    t = now.astimezone(TR).date()
    ms: list[dict] = []
    for d in (t - timedelta(days=1), t):
        try:
            ms += json.loads((out / "gun" / f"{d.isoformat()}.json").read_text(encoding="utf-8")).get("maclar") or []
        except Exception:
            pass
    lo, hi = now - timedelta(hours=3), now + timedelta(minutes=5)
    ms = [m for m in ms if lo <= parse_dt(m["kickoff_at"]) <= hi and m.get("status") in ("planlandi", "basladi", None)
          and not str(m.get("league", "")).startswith("Y")]
    p = out / "canli.json"
    try:
        prev = json.loads(p.read_text(encoding="utf-8")).get("maclar") or {}
    except Exception:
        prev = {}
    keep = {k: v for k, v in prev.items() if parse_dt(v.get("at")) and now - parse_dt(v["at"]) < timedelta(hours=4)}
    n = 0
    events: list[dict] = []
    if ms:
        for d in sorted({parse_dt(m["kickoff_at"]).date() for m in ms}):
            events += fetch(parse_dt(d.isoformat() + "T12:00:00Z"))
        for m in ms:
            e = pair(m, events)
            if not e or not (e["canli"] or e["bitti"]):
                continue
            keep[m["id"]] = {"kaynak": "ESPN", "durum": e["durum"], "dakika": e["dakika"], "skor": f"{e['hg']}-{e['ag']}",
                             "at": to_iso(now), "bitti": e["bitti"]}
            n += 1
    out.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"uretildi": to_iso(now), "maclar": keep}, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    log.append(f"✅ canlı (statik): {n}/{len(ms)} maç güncellendi (ESPN, {len(events)} etkinlik); Supabase egress 0")
    return n


if __name__ == "__main__":  # python -m meclis.canli <veri-dizini>
    import sys

    _log: list = []
    run_static(sys.argv[1] if len(sys.argv) > 1 else "statik", _log)
    print("\n".join(_log))
