"""Sitenin bütün okumaları için statik sorgu dosyaları (`veri` dalı, q/ dizini).

Site Supabase'e hiç gitmez: web/src/lib/statikdb.ts, PostgREST benzeri sorguları (select/eq/in/gte/lt/like/or/not/
order/range) bu dosyalar üzerinde tarayıcıda çalıştırır. Dosyalar yerel SQLite veritabanından üretilir; bölümleme:

  matches/gun/<TSİ günü>.json   (bugün −14 … +10)          matches/lig/<lig>.json (bu sezon, sources hariç)
  matches/sezon.json            (bu sezon, hafif sütunlar)  matches/idx.json  {maç kimliği: gün}
  <maça bağlı tablo>/gun/<gün>.json  (match_stats, lineups, weather, injuries, odds_snapshots, analyses [hafif],
                                      v_bot_tarama, v_dinlenme, v_oran_hareketi)
  analyses/mac/<kimlik>.json (yakın günlerin tam analizi) · analyses/meclis.json (bülten/not/motor)
  v_takim_mac_istatistik/takim/<slug>.json, /lig/<lig>.json · trends/<lig>.json · tekil dosyalar (<tablo>.json)
Dosya adlarında güvenli kodlama: [A-Za-z0-9._-] dışındaki her karakter '~<onaltılık kod>' olur (TS ile aynı).
"""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .timeutil import TR, now_utc, parse_dt, to_iso

PER_MATCH = ("match_stats", "lineups", "weather", "injuries", "odds_snapshots")
LIGHT = ("id", "league", "season", "kickoff_at", "home_team_id", "away_team_id", "home_name", "away_name", "home_goals",
         "away_goals", "score", "ht_home_goals", "ht_away_goals", "status", "durum", "venue", "referee", "city",
         "completeness", "updated_at")
LITE = ("ready", "basis", "markets", "scenarios", "model_matches", "min_team_matches", "lambdas", "injury_effect", "form",
        "top_scores", "kickoff_at", "league", "home", "away")


def fkey(s: str) -> str:
    return "".join(c if (c.isascii() and (c.isalnum() or c in "._-")) else f"~{ord(c):x}" for c in str(s))


def tr_day(iso) -> str:
    return parse_dt(iso).astimezone(TR).date().isoformat()


class W:
    def __init__(self, root: Path):
        self.root = root
        self.n = 0
        self.bytes = 0

    def put(self, rel: str, rows) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        s = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
        p.write_text(s, encoding="utf-8")
        self.n += 1
        self.bytes += len(s)


def export_q(store, out: Path, log: list) -> None:
    from .statik import team_rows

    now = now_utc()
    q = out / "q"
    if q.exists():
        shutil.rmtree(q)
    w = W(q)
    s0 = datetime(now.year if now.month >= 7 else now.year - 1, 7, 1, tzinfo=now.tzinfo)
    t = now.astimezone(TR).date()
    d_lo, d_hi = (t - timedelta(days=14)).isoformat(), (t + timedelta(days=10)).isoformat()

    ms = store.select("matches", [("kickoff_at", "gte", to_iso(s0))], order="kickoff_at")
    idx, by_day, by_lg = {}, defaultdict(list), defaultdict(list)
    for m in ms:
        d = tr_day(m["kickoff_at"])
        if d > d_hi:
            continue
        idx[m["id"]] = d
        if d >= d_lo:
            by_day[d].append(m)
        by_lg[m["league"]].append({k: v for k, v in m.items() if k != "sources"})
    w.put("matches/idx.json", idx)
    for d, rows in by_day.items():
        w.put(f"matches/gun/{d}.json", rows)
    for lg, rows in by_lg.items():
        w.put(f"matches/lig/{fkey(lg)}.json", rows)
    w.put("matches/sezon.json", [{k: m.get(k) for k in LIGHT} for m in ms if idx.get(m["id"])])

    ids = set(idx)
    for tb in PER_MATCH:
        groups = defaultdict(list)
        team_inj = []
        for r in store.select(tb):
            mid = r.get("match_id")
            if tb == "injuries" and not mid:
                if r.get("fetched_at") and now - parse_dt(r["fetched_at"]) < timedelta(days=30):
                    team_inj.append(r)
                continue
            if mid in ids:
                groups[idx[mid]].append(r)
        for d, rows in groups.items():
            w.put(f"{tb}/gun/{d}.json", rows)
        if tb == "injuries":
            w.put("injuries/takim.json", team_inj)

    # analizler: maç başına en son kayıt
    latest: dict[str, dict] = {}
    for r in store.select("analyses", order="created_at"):
        latest[r["match_id"]] = r
    meclis = [r for k, r in latest.items() if k.startswith("meclis:")]
    w.put("analyses/meclis.json", meclis)
    lite_days, scan_days = defaultdict(list), defaultdict(list)
    near_lo, near_hi = (t - timedelta(days=3)).isoformat(), (t + timedelta(days=4)).isoformat()
    for mid, r in latest.items():
        d = idx.get(mid)
        if not d:
            continue
        p = r.get("payload") or {}
        lite_days[d].append({"match_id": mid, "created_at": r["created_at"], "model_version": r.get("model_version"),
                             "payload": {k: p.get(k) for k in LITE}})
        if near_lo <= d <= near_hi:
            w.put(f"analyses/mac/{fkey(mid)}.json", [r])
        if parse_dt(p.get("kickoff_at") or "2000-01-01T00:00:00+00:00") > now - timedelta(hours=3):
            for x in p.get("markets") or []:
                scan_days[d].append({
                    "match_id": mid, "created_at": r["created_at"], "kickoff_at": p.get("kickoff_at"), "league": p.get("league"),
                    "home_name": p.get("home"), "away_name": p.get("away"), "basis": p.get("basis"),
                    "market": x.get("market"), "selection": x.get("selection"), "line": x.get("line"),
                    "p_model": x.get("probability"), "p_kal": x.get("p_kal"), "p_piyasa": x.get("p_piyasa"),
                    "odds": x.get("odds"), "odds_source": x.get("odds_source"), "fair_odds": x.get("fair_odds"),
                    "edge": x.get("edge_kal") if x.get("edge_kal") is not None else x.get("edge"),
                    "deger": bool(x.get("deger")), "secildi": bool(x.get("secildi")), "neden": x.get("neden")})
    for d, rows in lite_days.items():
        w.put(f"analyses/gun/{d}.json", rows)
    for d, rows in scan_days.items():
        w.put(f"v_bot_tarama/gun/{d}.json", rows)

    # takım sezon satırları (v_takim_mac_istatistik)
    done = [m for m in ms if m.get("status") == "bitti"]
    dids = {m["id"] for m in done}
    stats = [r for r in store.select("match_stats") if r["match_id"] in dids]
    tr_rows = team_rows(done, stats, s0)
    by_lg2 = defaultdict(list)
    for slug, rows in tr_rows.items():
        w.put(f"v_takim_mac_istatistik/takim/{fkey(slug)}.json", rows)
        for r in rows:
            by_lg2[r["league"]].append(r)
    for lg, rows in by_lg2.items():
        w.put(f"v_takim_mac_istatistik/lig/{fkey(lg)}.json", rows)

    # puan durumu (lig) ve Avrupa lig aşaması
    def table(rows, key):
        agg = {}
        for r in rows:
            k = (r["league"], r[key])
            a = agg.setdefault(k, {"league": r["league"], key: r[key], "team_name": r["team_name"], "o": 0, "g": 0, "b": 0,
                                   "m": 0, "ag": 0, "yg": 0})
            a["o"] += 1
            gf, ga = r["goals_for"] or 0, r["goals_against"] or 0
            a["g" if gf > ga else "b" if gf == ga else "m"] += 1
            a["ag"] += gf
            a["yg"] += ga
        out = []
        for a in agg.values():
            a["av"] = a["ag"] - a["yg"]
            a["puan"] = 3 * a["g"] + a["b"]
            out.append(a)
        for lg in {a["league"] for a in out}:
            rs = sorted([a for a in out if a["league"] == lg], key=lambda a: (-a["puan"], -a["av"], -a["ag"]))
            prev, rank = None, 0
            for i, a in enumerate(rs, 1):
                k = (a["puan"], a["av"], a["ag"])
                if k != prev:
                    rank, prev = i, k
                a["sira"] = rank
        return out

    allrows = [r for rows in tr_rows.values() for r in rows]
    w.put("v_puan_durumu.json", table(allrows, "team_id"))
    w.put("v_avrupa_puan_durumu.json", table([r for r in allrows if r["competition"] == "Avrupa" and r["asama"] == "Lig aşaması"],
                                              "team_slug"))

    # dinlenme + oran hareketi (yakın maçlar)
    last_by_slug = defaultdict(list)
    for r in allrows:
        last_by_slug[r["team_slug"]].append(parse_dt(r["kickoff_at"]))
    rest_days = defaultdict(list)
    for m in ms:
        ko = parse_dt(m["kickoff_at"])
        if not (now - timedelta(hours=3) < ko < now + timedelta(days=8)):
            continue
        for side in ("home", "away"):
            tid = m[f"{side}_team_id"] or ""
            slug = tid.split(":", 1)[1] if ":" in tid else ""
            prev = [x for x in last_by_slug.get(slug, []) if x < ko]
            rest_days[idx.get(m["id"], tr_day(m["kickoff_at"]))].append({
                "match_id": m["id"], "kickoff_at": m["kickoff_at"], "side": side, "team_name": m[f"{side}_name"],
                "dinlenme_gun": round((ko - max(prev)).total_seconds() / 86400, 1) if prev else None,
                "son14_mac": sum(1 for x in prev if x >= ko - timedelta(days=14))})
    for d, rows in rest_days.items():
        w.put(f"v_dinlenme/gun/{d}.json", rows)
    snaps = defaultdict(list)
    for r in store.select("odds_snapshots", order="taken_at"):
        snaps[r["match_id"]].append(r)
    mv_days = defaultdict(list)
    for mid, rs in snaps.items():
        if mid not in idx:
            continue
        mv_days[idx[mid]].append({"match_id": mid, "kickoff_at": rs[0]["kickoff_at"], "acilis": rs[0]["odds"],
                                  "acilis_zamani": rs[0]["taken_at"], "guncel": rs[-1]["odds"],
                                  "guncel_zamani": rs[-1]["taken_at"], "goruntu": len(rs)})
    for d, rows in mv_days.items():
        w.put(f"v_oran_hareketi/gun/{d}.json", rows)

    # tekil tablolar
    w.put("teams.json", store.select("teams", order="name"))
    w.put("leagues.json", store.select("leagues"))
    w.put("predictions.json", store.select("predictions", order="kickoff_at", desc=True))
    w.put("coupons.json", store.select("coupons", order="coupon_date", desc=True))
    w.put("analysis_queue.json", store.select("analysis_queue"))
    w.put("agenda.json", store.select("agenda", [("published_at", "gte", to_iso(now - timedelta(days=21)))],
                                      order="published_at", desc=True))
    trends = defaultdict(list)
    for r in store.select("trends"):
        trends[r["league"]].append(r)
    for lg, rows in trends.items():
        w.put(f"trends/{fkey(lg)}.json", rows)
    sims = store.select("sezon_simulasyonu")
    for lg in {r["league"] for r in sims}:
        rs = sorted([r for r in sims if r["league"] == lg], key=lambda r: r.get("ort_sira") or 99)
        for i, r in enumerate(rs, 1):
            r["tahmini_sira"] = i
    w.put("v_sezon_simulasyonu.json", sims)
    w.put("v_kanit_muhru.json", store.select("kanit_muhru", order="seq"))
    w.put("v_bot_bulten.json", [dict(r, arsiv_durumu=r.get("status")) for r in
                                store.select("bot_picks", [("kickoff_at", "gte", to_iso(now - timedelta(hours=3)))])])
    w.put("v_model_backtest.json", [dict(r, harman_agirligi=r.get("w_opt"), deger_secim_sayisi=r.get("n_value"),
                                         deger_isabet=r.get("hit_value"), deger_roi=r.get("roi_value"),
                                         kalibrasyon=r.get("calib"), canli_agirlik=r.get("w_live"), ll_canli=r.get("ll_live"),
                                         brier_canli=r.get("brier_live")) for r in store.select("model_backtest")])
    st = {r["source"]: r for r in store.select("source_status")}
    sis = []
    for job, hrs in (("yayin", 3), ("sonuclandir", 6), ("gundem", 12), ("gecmis", 30)):
        main = st.get(f"is:{job}") or {}
        oks = [r["updated_at"] for k, r in st.items() if k.startswith(f"is:{job}:") and r.get("ok") and r.get("updated_at")]
        last = max(oks) if oks else None
        sis.append({"is_adi": job, "beklenen_saat": hrs, "son_calisma": main.get("updated_at"), "son_ok": main.get("ok"),
                    "son_mesaj": main.get("message"), "son_basari": last,
                    "gecikti": (not last) or now - parse_dt(last) > timedelta(hours=hrs)})
    w.put("v_sistem_durumu.json", sis)
    w.put("_meta.json", {"uretildi": to_iso(now), "gun_ilk": d_lo, "gun_son": d_hi, "sezon_basi": to_iso(s0), "dosya": w.n})
    log.append(f"Statik sorgu dosyaları: {w.n} dosya, {w.bytes / 1e6:.1f} MB (q/)")
