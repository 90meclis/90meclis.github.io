"""Yaklaşan maçların veri kapsamı (lig bazında) — `python -m meclis durum` ve arayüz için."""
from __future__ import annotations

from datetime import timedelta

from .teamnews import fresh_injuries, is_confirmed
from .timeutil import now_utc, to_iso

COLS = [("maç", None), ("1X2 oran", "o1x2"), ("A/Ü 2.5", "ou25"), ("KG", "btts"), ("hakem", "ref"),
        ("stadyum", "venue"), ("eksik listesi", "inj"), ("ilk 11 (2 taraf)", "lu")]


def upcoming_coverage(store, leagues: list[str], days: int = 7) -> dict[str, dict]:
    now = now_utc()
    ms = store.select("matches", [("kickoff_at", "gte", to_iso(now)), ("kickoff_at", "lt", to_iso(now + timedelta(days=days))),
                                  ("league", "in", leagues)])
    ms = [m for m in ms if m.get("status") in ("planlandi", None)]
    ids = [m["id"] for m in ms]
    lus: dict[str, list] = {}
    for i in range(0, len(ids), 100):
        for r in store.select("lineups", [("match_id", "in", ids[i:i + 100])]):
            lus.setdefault(r["match_id"], []).append(r)
    st_ok = set()
    for i in range(0, len(ids), 100):
        for r in store.select("source_status", [("source", "in", [f"injuries:{x}" for x in ids[i:i + 100]])]):
            if r.get("ok"):
                st_ok.add(r["source"].split(":", 1)[1])
    out = {lg: {k or "maç": 0 for _, k in COLS} | {"tahmini": 0, "resmi": 0, "eksik kaydı": 0} for lg in leagues}
    for m in ms:
        c = out[m["league"]]
        o = m.get("odds") or {}
        c["maç"] += 1
        c["o1x2"] += 1 if o.get("1X2") else 0
        c["ou25"] += 1 if o.get("OU_GOALS_2.5") else 0
        c["btts"] += 1 if o.get("BTTS") else 0
        c["ref"] += 1 if m.get("referee") else 0
        c["venue"] += 1 if m.get("venue") else 0
        c["inj"] += 1 if m["id"] in st_ok else 0
        c["eksik kaydı"] += len(fresh_injuries(store, m["id"])) if m["id"] in st_ok else 0
        sides = {r["side"] for r in lus.get(m["id"], [])}
        c["lu"] += 1 if len(sides) == 2 else 0
        c["resmi"] += sum(1 for r in lus.get(m["id"], []) if is_confirmed(r))
        c["tahmini"] += sum(1 for r in lus.get(m["id"], []) if not is_confirmed(r))
    return out


def format_coverage(cov: dict[str, dict]) -> list[str]:
    head = ["lig"] + [n for n, _ in COLS] + ["eksik kaydı"]
    lines = [" | ".join(head)]
    for lg, c in cov.items():
        lines.append(" | ".join([lg] + [str(c[k or "maç"]) for _, k in COLS] + [str(c["eksik kaydı"])]))
    return lines
