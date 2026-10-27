"""Kopya maç/takım kayıtlarını birleştirir (yedekli). Kullanım: python scripts/kopya_birlestir.py [--uygula]
1) Erteleme kopyaları: aynı lig + ev + deplasman, ±10 gün, en az biri oynanmamış → tek kayıt.
2) Takım ad kopyaları: aynı ligde 'tranmere' / 'tranmererovers' gibi yalnızca kulüp ekiyle ayrılan iki takım → tek takım.
Yayımlanmış tahmine bağlı maç ASLA silinmez (o kayıt korunur). Silinen her satır backup_2026_10_20_yanlis_birlesme'ye
(tablo, anahtar, satir) yazılır; geri dönüş için oradan okunabilir."""
import json
import os
import sys
from collections import defaultdict
from datetime import timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meclis.pool import _CLUB_TAILS  # noqa: E402
from meclis.timeutil import parse_dt  # noqa: E402

URL = os.environ["SUPABASE_URL"] + "/rest/v1/"
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BACKUP = "backup_2026_10_20_yanlis_birlesme"
MATCH_TABLES = ["lineups", "player_matches", "bot_picks", "analyses", "analysis_queue", "weather", "match_stats",
                "odds_snapshots", "injuries", "agenda"]
TEAM_TABLES = ["player_matches", "match_stats", "players", "injuries", "trends"]
APPLY = "--uygula" in sys.argv


def get(table, q=""):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}{table}?{q}", headers={**H, "Range": f"{off}-{off + 999}"}, timeout=60)
        r.raise_for_status()
        rows = r.json()
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def backup(table, key, rows):
    if rows and APPLY:
        r = requests.post(URL + BACKUP, headers=H, data=json.dumps(
            [{"tablo": table, "anahtar": key, "satir": x} for x in rows], default=str), timeout=60)
        r.raise_for_status()


def delete(table, q):
    if APPLY:
        requests.delete(f"{URL}{table}?{q}", headers=H, timeout=60).raise_for_status()


def patch(table, q, vals):
    if APPLY:
        r = requests.patch(f"{URL}{table}?{q}", headers=H, data=json.dumps(vals), timeout=60)
        if r.status_code >= 300:
            return False
    return True


def drop_match(mid, keep):
    for t in MATCH_TABLES:
        col = "id" if t == "bot_picks" else "match_id"
        rows = get(t, f"{col}=eq.{mid}") if t != "bot_picks" else get(t, f"match_id=eq.{mid}")
        if not rows:
            continue
        backup(t, mid, rows)
        if t in ("odds_snapshots", "injuries", "agenda", "weather", "lineups") and \
                patch(t, f"match_id=eq.{mid}", {"match_id": keep}):
            continue  # veri kalıcı kayda taşındı
        delete(t, f"match_id=eq.{mid}")
    m = get("matches", f"id=eq.{mid}")
    backup("matches", mid, m)
    delete("matches", f"id=eq.{mid}")


def score(m, nstats, published):
    return (m["id"] in published, m.get("status") == "bitti", m.get("home_goals") is not None, nstats.get(m["id"], 0),
            m.get("updated_at") or "")


def main():
    published = {p["match_id"] for p in get("predictions", "select=match_id")}
    teams = get("teams")
    tpl = defaultdict(set)
    for t in teams:
        tpl[t["league"]].add(t["id"].split(":", 1)[1])
    # 2) takım ad kopyaları
    team_map = {}
    for lg, ks in tpl.items():
        for k in ks:
            for tail in _CLUB_TAILS:
                if len(k) >= 5 and k + tail in ks:
                    team_map[f"{lg}:{k}"] = f"{lg}:{k}{tail}"
    print("takım kopyaları:", team_map)
    ms = get("matches", "select=id,league,home_team_id,away_team_id,kickoff_at,status,home_goals,updated_at")
    nstats = defaultdict(int)
    for s in get("match_stats", "select=match_id"):
        nstats[s["match_id"]] += 1
    for m in ms:  # takım kimliğini kalıcı olana çevir (karşılaştırma için)
        m["h"], m["a"] = team_map.get(m["home_team_id"], m["home_team_id"]), team_map.get(m["away_team_id"], m["away_team_id"])
    g = defaultdict(list)
    for m in ms:
        g[(m["league"], m["h"], m["a"])].append(m)
    drops = []
    for v in g.values():
        if len(v) < 2:
            continue
        v.sort(key=lambda m: m["kickoff_at"])
        clusters, cur = [], [v[0]]
        for m in v[1:]:
            if parse_dt(m["kickoff_at"]) - parse_dt(cur[-1]["kickoff_at"]) <= timedelta(days=10):
                cur.append(m)
            else:
                clusters.append(cur)
                cur = [m]
        clusters.append(cur)
        for c in clusters:
            if len(c) < 2 or sum(1 for m in c if m.get("status") == "bitti") > 1:
                continue  # iki oynanmış maç: gerçekten iki ayrı karşılaşma olabilir, dokunma
            keep = max(c, key=lambda m: score(m, nstats, published))
            for m in c:
                if m is keep:
                    continue
                if m["id"] in published:
                    print("  ⚠️ yayımlanmış kayıt, silinmez:", m["id"])
                    continue
                drops.append((m["id"], keep["id"]))
    print(f"silinecek kopya maç: {len(drops)}")
    for d in drops[:60]:
        print("  ", d[0], "→", d[1])
    if not APPLY:
        print("(deneme — uygulamak için --uygula)")
        return
    for mid, keep in drops:
        drop_match(mid, keep)
    # takım kopyaları: maçları ve takım tablolarını kalıcı kimliğe çevir, takım satırını yedekle + sil, adı alias yap
    for old, new in team_map.items():
        for col in ("home_team_id", "away_team_id"):
            patch("matches", f"{col}=eq.{old}", {col: new})
        for t in TEAM_TABLES:
            rows = get(t, f"team_id=eq.{old}")
            if rows:
                backup(t, old, rows)
                if not patch(t, f"team_id=eq.{old}", {"team_id": new}):
                    delete(t, f"team_id=eq.{old}")
        oldrow = get("teams", f"id=eq.{old}")
        newrow = get("teams", f"id=eq.{new}")
        backup("teams", old, oldrow)
        if newrow and oldrow:
            al = list(newrow[0].get("aliases") or [])
            if isinstance(al, str):
                al = json.loads(al or "[]")
            for a in [oldrow[0]["name"], old.split(":", 1)[1]] + list(oldrow[0].get("aliases") or []):
                if a not in al:
                    al.append(a)
            patch("teams", f"id=eq.{new}", {"aliases": al})
        delete("teams", f"id=eq.{old}")
    print("uygulandı")


if __name__ == "__main__":
    main()
