"""Statik veri dışa aktarımı (egress tasarrufu): site, her ziyaretçide Supabase'i okumak yerine işlerin ürettiği
JSON dosyalarını okur (depodaki `veri` dalı → raw.githubusercontent.com). Dosyalar Supabase'i yeniden OKUMADAN
üretilir: maçlar yerel aynadan, analizler/editoryal bu çalışmada yazılanlardan, defter (tahmin + kupon) önceki
dosyaya bu çalışmadaki yazmalar uygulanarak. Defter günde bir kez (gece) ve dosya yoksa tam okunur.

Dosyalar: defter.json, editoryal.json, gunler.json, gun/<YYYY-MM-DD>.json, canli.json (meclis.canli_statik).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .timeutil import TR, now_utc, parse_dt, to_iso

LITE = ("ready", "basis", "markets", "scenarios", "model_matches", "min_team_matches", "lambdas", "injury_effect",
        "form", "top_scores")
MATCH_COLS = ("id", "league", "kickoff_at", "home_team_id", "away_team_id", "home_name", "away_name", "home_goals",
              "away_goals", "score", "ht_home_goals", "ht_away_goals", "status", "durum", "venue", "referee", "city",
              "odds", "missing_fields", "completeness", "updated_at", "season")
KEEP_DAYS = 14

_lock = threading.Lock()
ANALYSES: dict[str, dict] = {}   # bu çalışmada yazılan maç analizleri (hafif alanlar)
PAYLOADS: dict[str, dict] = {}   # meclis:bulten:D, meclis:not:D, meclis:motor
OPS: list[tuple] = []            # defter yazmaları: ("ins", tablo, satırlar) | ("upd", tablo, değerler, filtreler)


def statik_dir() -> Path | None:
    d = os.environ.get("MECLIS_STATIK_DIR")
    return Path(d) if d else None


# ---- store kancaları ------------------------------------------------------------------------------------------
def note_upsert(table: str, rows: list[dict]) -> None:
    if table != "analyses":
        return
    with _lock:
        for r in rows:
            mid, p = str(r.get("match_id") or ""), r.get("payload")
            if not isinstance(p, dict):
                continue
            if mid.startswith("meclis:"):
                PAYLOADS[mid] = p
            else:
                ANALYSES[mid] = {"match_id": mid, "created_at": r.get("created_at"), **{k: p.get(k) for k in LITE}}


def note_insert(table: str, rows: list[dict]) -> None:
    if table in ("predictions", "coupons") and rows:
        with _lock:
            OPS.append(("ins", table, [dict(r) for r in rows]))


def note_update(table: str, values: dict, filters) -> None:
    if table in ("predictions", "coupons"):
        with _lock:
            OPS.append(("upd", table, dict(values), list(filters)))


# ---- yardımcılar ----------------------------------------------------------------------------------------------
def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    tmp.replace(p)


def _day_bounds(d) -> tuple[str, str]:
    s = datetime(d.year, d.month, d.day, tzinfo=TR)
    return to_iso(s), to_iso(s + timedelta(days=1))


def _tr_today():
    return now_utc().astimezone(TR).date()


# ---- dışa aktarım ---------------------------------------------------------------------------------------------
def export(store, log: list, full_defter: bool = False, out: Path | None = None) -> None:
    out = out or statik_dir()
    if out is None:
        log.append("Statik veri: MECLIS_STATIK_DIR yok — atlandı (yalnızca GitHub Actions'ta üretilir).")
        return
    out.mkdir(parents=True, exist_ok=True)
    now = now_utc()
    stamp = to_iso(now)
    n_def = _defter(store, out, full_defter, stamp)
    n_ed = _editoryal(store, out, stamp)
    n_days = _days(store, out, stamp)
    n_tk = _teams(store, out, stamp)
    log.append(f"Statik veri (veri dalı): defter {n_def}, editoryal {n_ed} anahtar, {n_days} gün dosyası, "
               f"{n_tk} takım dosyası.")


def _defter(store, out: Path, full: bool, stamp: str) -> str:
    from .ayna import _match

    p = out / "defter.json"
    cur = _read(p) or {}
    tam = parse_dt(cur.get("tam")) if cur.get("tam") else None
    if full or not cur or not tam or now_utc() - tam > timedelta(hours=26):
        preds = store.select("predictions", order="kickoff_at", desc=True)
        cps = store.select("coupons", order="coupon_date", desc=True)
        cur = {"tam": stamp, "predictions": preds, "coupons": cps}
        how = "tam okuma"
    else:
        how = "artımlı"
        with _lock:
            ops = list(OPS)
        if not ops:
            return f"{len(cur.get('predictions') or [])} tahmin (değişmedi)"
        for op in ops:
            rows = cur.setdefault(op[1], [])
            if op[0] == "ins":
                ids = {r.get("id") for r in op[2]}
                rows[:] = [r for r in rows if r.get("id") not in ids] + op[2]
            else:
                for r in rows:
                    if _match(r, op[3]):
                        r.update(op[2])
        cur["predictions"].sort(key=lambda r: str(r.get("kickoff_at") or ""), reverse=True)
        cur.setdefault("coupons", []).sort(key=lambda r: str(r.get("coupon_date") or ""), reverse=True)
    cur["uretildi"] = stamp
    _write(p, cur)
    return f"{len(cur['predictions'])} tahmin/{len(cur['coupons'])} kupon ({how})"


def _editoryal(store, out: Path, stamp: str) -> int:
    p = out / "editoryal.json"
    cur = _read(p)
    if cur is None:  # ilk üretim: son günlerin bülten/not kayıtları bir kez okunur
        cur = {"anahtarlar": {}}
        t = _tr_today()
        keys = ["meclis:motor"] + [f"meclis:{k}:{(t + timedelta(days=i)).isoformat()}"
                                   for i in range(-KEEP_DAYS, 2) for k in ("bulten", "not")]
        for i in range(0, len(keys), 30):
            for r in store.select("analyses", [("match_id", "in", keys[i:i + 30])], order="created_at"):
                cur["anahtarlar"][r["match_id"]] = r["payload"]
    with _lock:
        cur["anahtarlar"].update(PAYLOADS)
    lo = (_tr_today() - timedelta(days=KEEP_DAYS)).isoformat()
    cur["anahtarlar"] = {k: v for k, v in cur["anahtarlar"].items()
                         if k == "meclis:motor" or k.rsplit(":", 1)[-1] >= lo}
    cur["uretildi"] = stamp
    _write(p, cur)
    return len(cur["anahtarlar"])


def _days(store, out: Path, stamp: str) -> int:
    t = _tr_today()
    lo_all, _ = _day_bounds(t - timedelta(days=KEEP_DAYS))
    _, hi_all = _day_bounds(t + timedelta(days=10))
    ms = store.select("matches", [("kickoff_at", "gte", lo_all), ("kickoff_at", "lt", hi_all)], order="kickoff_at")
    counts: dict[str, dict[str, int]] = {}
    by_day: dict[str, list[dict]] = {}
    for m in ms:
        d = parse_dt(m["kickoff_at"]).astimezone(TR).date().isoformat()
        counts.setdefault(d, {})
        counts[d][m["league"]] = counts[d].get(m["league"], 0) + 1
        by_day.setdefault(d, []).append({k: m.get(k) for k in MATCH_COLS})
    _write(out / "gunler.json", {"uretildi": stamp, "gunler": counts})
    n = 0
    gdir = out / "gun"
    for i in range(-2, 4):
        d = (t + timedelta(days=i)).isoformat()
        rows = by_day.get(d, [])
        prev = _read(gdir / f"{d}.json") or {}
        an = {k: v for k, v in (prev.get("analizler") or {}).items() if any(m["id"] == k for m in rows)}
        with _lock:
            for m in rows:
                if m["id"] in ANALYSES:
                    an[m["id"]] = ANALYSES[m["id"]]
        _write(gdir / f"{d}.json", {"uretildi": stamp, "gun": d, "maclar": rows, "analizler": an})
        n += 1
    if gdir.exists():  # eski gün dosyaları silinir (site o günler için canlı okumaya düşer)
        lo = (t - timedelta(days=KEEP_DAYS)).isoformat()
        for f in gdir.glob("*.json"):
            if f.stem < lo:
                f.unlink()
    return n


def team_rows(matches: list[dict], stats: list[dict], s0: datetime) -> dict[str, list[dict]]:
    """v_takim_mac_istatistik'in Python karşılığı (aynı sütunlar), takım slug'ına göre."""
    st = {(r["match_id"], r["side"]): r for r in stats}
    out: dict[str, list[dict]] = {}

    def n(r, k):
        return None if r is None else r.get(k)

    for m in matches:
        if m.get("status") != "bitti" or m.get("home_goals") is None:
            continue
        ko = parse_dt(m["kickoff_at"])
        if ko < s0:
            continue
        comp = "Avrupa" if m["league"] in ("CL", "EL", "ECL") else "Lig"
        if comp == "Lig":
            asama = "Lig"
        elif ko < s0.replace(month=9, day=1):
            asama = "Ön eleme/play-off"
        elif ko < s0.replace(year=s0.year + 1, month=2, day=1):
            asama = "Lig aşaması"
        else:
            asama = "Eleme turları"
        hg, ag = m["home_goals"], m["away_goals"]
        for side in ("home", "away"):
            me, op = st.get((m["id"], side)), st.get((m["id"], "away" if side == "home" else "home"))
            h = side == "home"
            tid = m["home_team_id"] if h else m["away_team_id"]
            slug = (tid or "").split(":")[1] if tid and ":" in tid else ""

            def cards(r):
                return None if r is None or r.get("yellow") is None else r["yellow"] + (r.get("red") or 0)

            out.setdefault(slug, []).append({
                "match_id": m["id"], "kickoff_at": m["kickoff_at"], "league": m["league"], "competition": comp,
                "side": side, "team_id": tid, "team_slug": slug,
                "team_name": m["home_name"] if h else m["away_name"], "opponent": m["away_name"] if h else m["home_name"],
                "goals_for": hg if h else ag, "goals_against": ag if h else hg,
                "ht_for": m.get("ht_home_goals") if h else m.get("ht_away_goals"),
                "ht_against": m.get("ht_away_goals") if h else m.get("ht_home_goals"),
                "btts": bool(hg and ag and hg > 0 and ag > 0) if hg is not None and ag is not None else None,
                "corners_for": n(me, "corners"), "corners_against": n(op, "corners"),
                "cards_for": cards(me), "cards_against": cards(op),
                "shots_for": n(me, "shots"), "shots_against": n(op, "shots"),
                "sot_for": n(me, "shots_on_target"), "sot_against": n(op, "shots_on_target"),
                "goal_kicks_for": n(me, "goal_kicks"), "goal_kicks_against": n(op, "goal_kicks"),
                "fouls_for": n(me, "fouls"), "fouls_against": n(op, "fouls"),
                "xg_for": n(me, "xg"), "xg_against": n(op, "xg"), "asama": asama})
    return out


def _teams(store, out: Path, stamp: str) -> int:
    """Önümüzdeki günlerde oynayacak takımların bu sezonki maç satırları (takim/<slug>.json) — yerel aynadan."""
    now = now_utc()
    s0 = datetime(now.year if now.month >= 7 else now.year - 1, 7, 1, tzinfo=now.tzinfo)
    t = _tr_today()
    lo, _ = _day_bounds(t - timedelta(days=1))
    _, hi = _day_bounds(t + timedelta(days=3))
    fx = store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", hi)])
    need = {(x or "").split(":", 1)[1] for m in fx for x in (m.get("home_team_id"), m.get("away_team_id"))
            if x and ":" in x}
    if not need:
        return 0
    ms = store.select("matches", [("kickoff_at", "gte", to_iso(s0)), ("status", "eq", "bitti")])
    ids = {m["id"] for m in ms}
    stats = [r for r in store.select("match_stats") if r["match_id"] in ids]
    rows = team_rows(ms, stats, s0)
    tdir = out / "takim"
    n = 0
    for slug in need:
        _write(tdir / f"{slug}.json", {"uretildi": stamp, "slug": slug,
                                       "satirlar": sorted(rows.get(slug, []), key=lambda r: r["kickoff_at"], reverse=True)})
        n += 1
    if tdir.exists():  # artık oynamayacak takımların dosyaları 3 gün sonra silinir
        for f in tdir.glob("*.json"):
            if f.stem in need:
                continue
            u = (_read(f) or {}).get("uretildi")
            if not u or now - parse_dt(u) > timedelta(days=3):
                f.unlink()
    return n
