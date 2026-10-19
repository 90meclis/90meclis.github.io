"""Gündem Masası: sabah haber taraması (RSS) ve haberlerin o günün maçlarına bağlanması."""
from __future__ import annotations

from datetime import timedelta

from .names import mentions_team
from .sources.rss import fetch_feed
from .timeutil import now_utc, to_iso


def link_news(items: list[dict], matches: list[dict]) -> list[dict]:
    """Takım adı eşleşmesiyle haberleri maçlara bağlar (aksan ve Türkçe ek duyarsız)."""
    for it in items:
        text = f"{it['title']} {it.get('summary') or ''}"
        teams, mids = set(it.get("team_ids") or []), set(it.get("match_ids") or [])
        for m in matches:
            hit = False
            for side in ("home", "away"):
                if mentions_team(text, m[f"{side}_name"]):
                    teams.add(m[f"{side}_team_id"])
                    hit = True
            if hit:
                mids.add(m["id"])
        it["team_ids"], it["match_ids"] = sorted(teams), sorted(mids)
        it["match_id"] = it["match_ids"][0] if it["match_ids"] else None
        it["impact_note"] = impact_note(it, [m for m in matches if m["id"] in mids])
    return items


IMPACT = {
    "sakatlık": "Eksik okumasını etkileyebilir: Maç Merkezi'nde Eksik Etkisi'ni ve ilk 11'i kontrol et.",
    "teknik direktör": "Teknik direktör kararı/değişikliği: ilk maçlarda form verisi daha az güvenilir olabilir.",
    "transfer": "Kadro değişikliği: yeni oyuncu henüz model geçmişinde yok.",
    "kadro": "Kadro haberi: açıklanan ilk 11 ile tahmin varsayımlarını karşılaştır.",
}


def impact_note(item: dict, linked: list[dict]) -> str | None:
    if not linked:
        return None
    m = linked[0]
    base = IMPACT.get(item.get("category"), "Maç öncesi gündem; doğrudan model girdisi değil.")
    more = f" (+{len(linked) - 1} maç)" if len(linked) > 1 else ""
    return f"{m['home_name']} – {m['away_name']}{more}: {base}"


def scan_news(store, settings, matches: list[dict] | None = None) -> dict:
    items, log = [], []
    for url in settings.news_feeds:
        try:
            got = fetch_feed(url)
            items += got
            log.append(f"✅ {url}: {len(got)} haber")
        except Exception as e:
            log.append(f"⚠️ {url}: {e}")
    if matches is None:
        lo, hi = now_utc() - timedelta(hours=6), now_utc() + timedelta(hours=48)
        matches = store.select("matches", [("kickoff_at", "gte", to_iso(lo)), ("kickoff_at", "lt", to_iso(hi))])
    seen = {}
    for it in items:
        seen.setdefault(it["id"], it)
    rows = link_news(list(seen.values()), matches)
    ts = to_iso(now_utc())
    for r in rows:
        r["fetched_at"] = ts
    store.upsert("agenda", rows)
    linked = sum(1 for r in rows if r["match_ids"])
    log.append(f"{len(rows)} haber kaydedildi, {linked} tanesi maçlara bağlandı")
    return {"news": len(rows), "linked": linked, "log": log}
