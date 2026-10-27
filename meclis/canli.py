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
