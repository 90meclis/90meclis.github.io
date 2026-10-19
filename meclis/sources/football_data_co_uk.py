"""football-data.co.uk — anahtarsız, ücretsiz CSV dosyaları.

* Sezon dosyaları: sonuçlar + şut, isabetli şut, korner, faul, kart, (varsa) xG ve bahis oranları.
* fixtures.csv: önümüzdeki maçlar ve piyasa oranları (1X2, 2.5 Alt/Üst, Asya handikabı).
Saatler İngiltere yerel saatidir (Europe/London) ve UTC'ye çevrilir.
Kaynak gösterimi: "Data: football-data.co.uk".
"""
from __future__ import annotations

import io
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from ..timeutil import to_iso
from .http import cached_text

SOURCE = "football-data.co.uk"
BASE = "https://www.football-data.co.uk"
LONDON = ZoneInfo("Europe/London")


def season_code(d: date) -> str:
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def season_label(code: str) -> str:
    return f"20{code[:2]}-20{code[2:]}"


def _num(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
            return None
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def _int(v):
    f = _num(v)
    return int(f) if f is not None else None


def _kickoff(date_s: str, time_s) -> str | None:
    date_s = str(date_s).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(date_s, fmt)
            break
        except ValueError:
            d = None
    if d is None:
        return None
    hh, mm = 15, 0
    if isinstance(time_s, str) and ":" in time_s:
        hh, mm = (int(x) for x in time_s.split(":")[:2])
    local = d.replace(hour=hh, minute=mm, tzinfo=LONDON)
    return to_iso(local)


def _odds(row: dict) -> dict:
    out: dict = {}

    def pick(*cols):
        for c in cols:
            v = _num(row.get(c))
            if v and v > 1.0:
                return v, c
        return None, None

    h, ch = pick("AvgH", "B365H", "PSH")
    d, _ = pick("AvgD", "B365D", "PSD")
    a, _ = pick("AvgA", "B365A", "PSA")
    if h and d and a:
        out["1X2"] = {"1": h, "X": d, "2": a, "src": f"{SOURCE}:{'Avg' if ch == 'AvgH' else ch[:-1]}"}
    o, co = pick("Avg>2.5", "B365>2.5", "P>2.5")
    u, _ = pick("Avg<2.5", "B365<2.5", "P<2.5")
    if o and u:
        out["OU_GOALS_2.5"] = {"ÜST": o, "ALT": u, "src": f"{SOURCE}:{co.split('>')[0]}"}
    hc, _ = pick("AvgCH", "B365CH", "PSCH")
    dc, _ = pick("AvgCD", "B365CD", "PSCD")
    ac, _ = pick("AvgCA", "B365CA", "PSCA")
    if hc and dc and ac:
        out["1X2_closing"] = {"1": hc, "X": dc, "2": ac}
    oc, _ = pick("AvgC>2.5", "B365C>2.5")
    uc, _ = pick("AvgC<2.5", "B365C<2.5")
    if oc and uc:
        out["OU_GOALS_2.5_closing"] = {"ÜST": oc, "ALT": uc}
    return out


def parse_csv(text: str, league_hint: str | None = None, season: str | None = None) -> list[dict]:
    if not text.strip():
        return []
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="skip")
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
    recs = []
    for row in df.to_dict("records"):
        league = (row.get("Div") or league_hint or "").strip()
        if not league or not row.get("HomeTeam"):
            continue
        ko = _kickoff(row.get("Date", ""), row.get("Time"))
        if not ko:
            continue
        hg, ag = _int(row.get("FTHG")), _int(row.get("FTAG"))
        finished = hg is not None and ag is not None
        rec = {
            "source": SOURCE,
            "league": league,
            "season": season,
            "kickoff_at": ko,
            "home_name": row["HomeTeam"].strip(),
            "away_name": row["AwayTeam"].strip(),
            "status": "bitti" if finished else "planlandi",
            "home_goals": hg, "away_goals": ag,
            "ht_home_goals": _int(row.get("HTHG")), "ht_away_goals": _int(row.get("HTAG")),
            "referee": (row.get("Referee") or "").strip() or None,
            "odds": _odds(row),
            "stats": None,
        }
        if finished:
            rec["stats"] = {
                "home": {"shots": _int(row.get("HS")), "shots_on_target": _int(row.get("HST")),
                         "corners": _int(row.get("HC")), "fouls": _int(row.get("HF")),
                         "yellow": _int(row.get("HY")), "red": _int(row.get("HR")), "xg": _num(row.get("HxG"))},
                "away": {"shots": _int(row.get("AS")), "shots_on_target": _int(row.get("AST")),
                         "corners": _int(row.get("AC")), "fouls": _int(row.get("AF")),
                         "yellow": _int(row.get("AY")), "red": _int(row.get("AR")), "xg": _num(row.get("AxG"))},
            }
        recs.append(rec)
    return recs


def fetch_season(league: str, code: str, ttl: int = 6 * 3600) -> list[dict]:
    text = cached_text(f"{BASE}/mmz4281/{code}/{league}.csv", ttl)
    return parse_csv(text, league, season_label(code))


def fetch_fixtures(leagues: list[str], ttl: int = 2 * 3600) -> list[dict]:
    text = cached_text(f"{BASE}/fixtures.csv", ttl)
    return [r for r in parse_csv(text) if r["league"] in leagues]
