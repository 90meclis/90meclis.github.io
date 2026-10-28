"""28.10.2026 kurtarma: Supabase (402, egress kotası) erişilemez. Yeni SQLite veritabanı şu kaynaklardan kurulur:

* backups dalı d32255b (27.10 01:45 UTC): matches, odds_snapshots, leagues  → takımlar maçlardan türetilir
* Kanıt Mührü manifestosu (muhur/manifest.json): 31 mührün kimlik/özetleri (kanonik içerik Supabase'te kaldı)
* 27.10 19:09 UTC yayın işinin günlüğü (run 40566516390) + 27.10 23:27 UTC canlı site ekran görüntüleri:
  28 Ekim'in Günün Kararı, Karar Birliği ve 8 Meclis Görüşü'nün maç / pazar / oran / olasılık (yüzde, yuvarlanmış)

Kullanım: python scripts/kurtarma_2026_10_28.py <yedek-dizini> <çıktı.db>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from meclis.store import SQLiteStore  # noqa: E402

NOTE = ("Kurtarıldı (28.10.2026): Supabase 402 kısıtı nedeniyle asıl kayıt okunamadı; maç/pazar/oran 27.10 yayın günlüğü "
        "ve canlı site görüntüsünden, olasılık yüzde olarak (yuvarlanmış) alındı.")
REC = "2026-10-27T19:19:00+00:00"  # sitede 'Kilitli · 27.10.2026 22:19 TSİ'

# seq → (ref_id, tablo) manifestten; içerik: günlük sırası = mühür sırası (28 Ekim kartlarındaki 'Mühürlü #n' ile doğrulandı)
P28 = [  # seq, match_id, home, away, kickoff, market, selection, line, odds, prob, tag, coupon_seq
    (2, "B26:2026-10-28:ifkgoteborg:djurgardens", "IFK Göteborg", "Djurgårdens IF", "2026-10-28T18:00:00+00:00", "OU_GOALS", "ALT", 3.5, 1.50, 0.62, "gunun_karari", 1),
    (3, "B26:2026-10-28:brommapojkarna:hacken", "IF Brommapojkarna", "BK Häcken", "2026-10-28T18:00:00+00:00", "OU_GOALS", "ÜST", 2.5, 1.50, 0.61, "gunun_karari", 1),
    (4, "SC0:2026-10-28:dundee:kilmarnock", "Dundee", "Kilmarnock", "2026-10-28T19:45:00+00:00", "OU_GOALS", "ALT", 3.5, 1.52, 0.61, "gunun_karari", 1),
    (5, "SC0:2026-10-28:hearts:rangers", "Hearts", "Rangers", "2026-10-28T20:00:00+00:00", "BTTS", "VAR", None, 1.53, 0.61, "meclis_gorusu", None),
    (6, "I1:2026-10-28:venezia:inter", "Venezia FC", "Inter", "2026-10-28T17:30:00+00:00", "BTTS", "VAR", None, 1.55, 0.62, "meclis_gorusu", None),
    (7, "I2:2026-10-28:pisa:palermo", "Pisa", "Palermo", "2026-10-28T18:00:00+00:00", "BTTS", "VAR", None, 1.56, 0.61, "meclis_gorusu", None),
    (8, "SC0:2026-10-28:stmirren:hibernian", "St Mirren", "Hibernian", "2026-10-28T19:45:00+00:00", "BTTS", "VAR", None, 1.56, 0.58, "meclis_gorusu", None),
    (9, "SC0:2026-10-28:celtic:dundeeunited", "Celtic", "Dundee United", "2026-10-28T19:45:00+00:00", "BTTS", "VAR", None, 1.61, 0.57, "meclis_gorusu", None),
    (10, "B26:2026-10-28:halmstads:malmoff", "Halmstads BK", "Malmö FF", "2026-10-28T18:00:00+00:00", "OU_GOALS", "ÜST", 2.5, 1.59, 0.57, "meclis_gorusu", None),
    (11, "B40:2026-10-28:manchestercity:brighton", "Manchester City", "Brighton & Hove Albion", "2026-10-28T19:30:00+00:00", "BTTS", "VAR", None, 1.51, 0.61, "meclis_gorusu", None),
    (12, "B91:2026-10-28:carlisleunited:harrogatetown", "Carlisle United", "Harrogate Town", "2026-10-28T19:45:00+00:00", "OU_GOALS", "ALT", 3.5, 1.52, 0.61, "meclis_gorusu", None),
    (14, "SC0:2026-10-28:hearts:rangers", "Hearts", "Rangers", "2026-10-28T20:00:00+00:00", "BTTS", "VAR", None, 1.53, 0.61, "karar_birligi", 13),
    (15, "I1:2026-10-28:venezia:inter", "Venezia FC", "Inter", "2026-10-28T17:30:00+00:00", "BTTS", "VAR", None, 1.55, 0.62, "karar_birligi", 13),
    (16, "I2:2026-10-28:pisa:palermo", "Pisa", "Palermo", "2026-10-28T18:00:00+00:00", "BTTS", "VAR", None, 1.56, 0.61, "karar_birligi", 13),
]
C28 = {1: ("gunun_karari", 3.42, 0.231, 3, "2026-10-28T18:00:00+00:00"),
       13: ("karar_birligi", 3.70, 0.230, 3, "2026-10-28T17:30:00+00:00")}
# 29 Ekim (mühür 17–31): içerik kurtarılamadı; günlükte yalnızca tekli maç/pazar ve kupon toplam oranları var
LOST29 = {
    "kuponlar": [{"seq": 17, "tur": "Günün Kararı", "toplam_oran": 3.38, "bacak": 3},
                 {"seq": 29, "tur": "Karar Birliği", "toplam_oran": 2.29, "bacak": 2}],
    "tekliler_gunlukten": [
        {"seq": 21, "mac": "FC Dallas – Columbus Crew", "secim": "KG Var"},
        {"seq": 22, "mac": "Red Bull Bragantino – Chapecoense", "secim": "Toplam Gol 3.5 Alt"},
        {"seq": 23, "mac": "Remo – Botafogo", "secim": "KG Var"},
        {"seq": 24, "mac": "Inter Miami CF – FC Cincinnati", "secim": "Toplam Gol 3.5 Üst"},
        {"seq": 25, "mac": "Charlotte FC – CF Montréal", "secim": "KG Var"},
        {"seq": 26, "mac": "St.Louis City – Portland Timbers", "secim": "MS 1 (St.Louis City)"},
        {"seq": 27, "mac": "New England Revolution – New York Red Bulls", "secim": "MS 1 (New England Revolution)"},
        {"seq": 28, "mac": "Santos – Palmeiras", "secim": "KG Var"}],
    "kayip": "Kupon bacakları (mühür 18–20, 30–31), tekli oran/olasılıkları ve 31 kaydın kanonik içeriği (zaman damgası "
             "mikrosaniyesi, 6 haneli olasılık) Supabase'te kaldı; içerik özetleri (icerik_sha256) bu yüzden yeniden "
             "hesaplanıp doğrulanamıyor. Mühür zinciri (manifest kökü) olduğu gibi korunur ve yeni kayıtlar ona eklenir.",
}


def main(bk: str, out: str) -> None:
    bk_dir = Path(bk)
    p = Path(out)
    if p.exists():
        p.unlink()
    st = SQLiteStore(str(p))
    for t in ("leagues", "matches", "odds_snapshots"):
        rows = json.loads((bk_dir / f"{t}.json").read_text(encoding="utf-8"))
        for i in range(0, len(rows), 2000):
            st.upsert(t, rows[i:i + 2000])
        print(t, len(rows))
    ms = json.loads((bk_dir / "matches.json").read_text(encoding="utf-8"))
    teams: dict[str, dict] = {}
    for m in sorted(ms, key=lambda m: m["kickoff_at"]):
        for side in ("home", "away"):
            tid = m[f"{side}_team_id"]
            teams[tid] = {"id": tid, "league": tid.split(":")[0] if ":" in tid else m["league"], "name": m[f"{side}_name"],
                          "updated_at": m.get("updated_at")}
    st.upsert("teams", list(teams.values()))
    print("teams", len(teams))
    man = json.loads(Path(__file__).resolve().parents[1].joinpath("muhur/manifest.json").read_text(encoding="utf-8"))
    by_seq = {r["seq"]: r for r in man["muhurler"]}
    prev = "0" * 64
    seals = []
    for r in man["muhurler"]:
        seals.append({"ref_table": r["ref_table"], "ref_id": r["ref_id"], "seq": r["seq"], "icerik_sha256": r["icerik_sha256"],
                      "sha256": r["sha256"], "onceki_sha256": prev, "muhurlendi_at": r["muhurlendi_at"],
                      "kanonik": "KAYIP — Supabase 402 kısıtı; kanonik içerik kurtarılamadı (bkz. defter/kurtarma-2026-10-28.json)"})
        prev = r["sha256"]
    st.upsert("kanit_muhru", seals)
    for seq, (tag, tot, jp, n, first) in C28.items():
        st.insert("coupons", [{"id": by_seq[seq]["ref_id"], "created_at": REC, "coupon_date": "2026-10-28", "tag": tag,
                               "total_odds": tot, "joint_probability": jp, "legs_count": n, "first_kickoff_at": first,
                               "odds_source": "piyasa", "model_version": "kurtarildi", "note": NOTE}])
    from meclis.markets import pick_label  # noqa: F401  (etiket kontrolü)

    for seq, mid, h, a, ko, mk, sel, line, odds, prob, tag, cseq in P28:
        if not st.get("matches", id=mid):
            raise SystemExit(f"maç yok: {mid}")
        st.conn.execute("update matches set kickoff_at=? where id=?", (ko, mid))
        st.insert("predictions", [{"id": by_seq[seq]["ref_id"], "recorded_at": REC, "match_id": mid, "kickoff_at": ko,
                                   "league": mid.split(":")[0], "home_name": h, "away_name": a, "tag": tag,
                                   "coupon_id": by_seq[cseq]["ref_id"] if cseq else None, "market": mk, "selection": sel,
                                   "line": line, "probability": prob, "odds": odds, "odds_source": "piyasa",
                                   "fair_odds": round(1 / prob, 2), "model_version": "kurtarildi", "rationale": NOTE}])
    # ekleme tetikleyicileri kayıt zamanını "şimdi" yapar; asıl kilit zamanı geri yazılır (tetikleyiciler bir sonraki
    # açılışta şemadan yeniden kurulur)
    st.conn.executescript(f"""drop trigger if exists predictions_bu; drop trigger if exists coupons_bu;
        update predictions set recorded_at = '{REC}'; update coupons set created_at = '{REC}';""")
    st.upsert("source_status", [{"source": "kurtarma:2026-10-28", "ok": 1, "message": json.dumps(LOST29, ensure_ascii=False),
                                 "updated_at": "2026-10-28T15:30:00+00:00"}])
    st.conn.execute("vacuum")
    print("ok", p, p.stat().st_size)
    Path(Path(out).parent, "kurtarma-2026-10-28.json").write_text(json.dumps(
        {"not": NOTE, "28_ekim": [dict(zip(("seq", "match_id", "home", "away", "kickoff_at", "market", "selection", "line",
                                            "odds", "probability", "tag", "coupon_seq"), r)) for r in P28],
         "28_ekim_kuponlar": {k: dict(zip(("tag", "total_odds", "joint_probability", "legs", "first_kickoff_at"), v))
                              for k, v in C28.items()},
         "29_ekim": LOST29}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
