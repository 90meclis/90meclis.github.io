"""Telegram / X paylaşım TASLAKLARI. Yalnızca taslak üretilir ve saklanır; hiçbir şey otomatik paylaşılmaz."""
from __future__ import annotations

from .markets import pick_label
from .timeutil import now_utc, to_iso, tr_str


def _odds(x) -> str:
    return f"{float(x):.2f}".replace(".", ",") if x else "—"


def build_drafts(store, day_lo: str, day_hi: str) -> int:
    preds = store.select("predictions", [("kickoff_at", "gte", day_lo), ("kickoff_at", "lt", day_hi)])
    coupons = {c["id"]: c for c in store.select("coupons", [("first_kickoff_at", "gte", day_lo), ("first_kickoff_at", "lt", day_hi)])}
    seals = {r["ref_id"]: r["sha256"] for r in store.select("kanit_muhru", [("ref_id", "in", [p["id"] for p in preds] + list(coupons))])} \
        if preds or coupons else {}
    rows = []
    now = to_iso(now_utc())
    for cid, c in coupons.items():
        legs = [p for p in preds if p.get("coupon_id") == cid]
        if not legs:
            continue
        title = "Günün Kararı" if c["tag"] == "gunun_karari" else "Karar Birliği"
        lines = [f"🏛️ {title} — {c['coupon_date']}"]
        for p in legs:
            lines.append(f"• {p['home_name']} – {p['away_name']} ({tr_str(p['kickoff_at'])}): "
                         f"{pick_label(p['market'], p['selection'], p.get('line'), p['home_name'], p['away_name'])} @ {_odds(p.get('odds'))}")
        lines.append(f"Toplam oran: {_odds(c.get('total_odds'))}")
        seal = seals.get(cid)
        lines.append(f"🔒 Kilit: {str(c.get('created_at'))[:16]} UTC" + (f" · Mühür {seal[:12]}…" if seal else ""))
        lines.append("Kayıt herkese açık, silinmez: 90meclis.github.io")
        txt = "\n".join(lines)
        for plat in ("telegram", "x"):
            t = txt if plat == "telegram" else txt[:280]
            rows.append({"id": f"{plat}:{c['tag']}:{cid}", "platform": plat, "tur": c["tag"], "ref_id": cid, "metin": t,
                         "durum": "taslak", "olusturuldu": now})
    for p in preds:
        if p["tag"] != "meclis_gorusu":
            continue
        lab = pick_label(p["market"], p["selection"], p.get("line"), p["home_name"], p["away_name"])
        seal = seals.get(p["id"])
        txt = (f"🏛️ Meclis Görüşü\n{p['home_name']} – {p['away_name']} ({tr_str(p['kickoff_at'])})\n{lab} @ {_odds(p.get('odds'))}"
               + (f" · değer {float(p['edge']) * 100:+.1f}%" if p.get("edge") is not None else "")
               + f"\n🔒 Kilit: {str(p.get('recorded_at'))[:16]} UTC" + (f" · Mühür {seal[:12]}…" if seal else "")
               + "\nKayıt herkese açık, silinmez: 90meclis.github.io")
        for plat in ("telegram", "x"):
            rows.append({"id": f"{plat}:meclis_gorusu:{p['id']}", "platform": plat, "tur": "meclis_gorusu", "ref_id": p["id"],
                         "metin": txt if plat == "telegram" else txt[:280], "durum": "taslak", "olusturuldu": now})
    if rows:
        store.upsert("paylasim_taslaklari", rows)
    return len(rows)
