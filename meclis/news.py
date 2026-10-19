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


_STOP = {"ve", "ile", "bir", "bu", "da", "de", "mi", "için", "the", "a", "an", "of", "to", "in", "and", "on", "for",
         "is", "at", "after", "as", "with", "il", "la", "el", "di", "le", "les", "der", "die", "das"}


def _tokens(title: str) -> set[str]:
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", title.lower().replace("ı", "i"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 1 and w not in _STOP}


def normalize_url(url: str) -> str:
    """Aynı haberin farklı bağlantılarını eşler: şema/www/izleme parametreleri (utm_*, fbclid, ref…)/parça/son '/' atılır."""
    from urllib.parse import parse_qsl, urlencode, urlsplit

    if not url:
        return ""
    u = urlsplit(url.strip())
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("amp.")
    q = [(k, v) for k, v in parse_qsl(u.query) if not (k.lower().startswith("utm_") or k.lower() in {
        "fbclid", "gclid", "ref", "ref_src", "cmpid", "ito", "at_medium", "at_campaign", "ocid", "src", "amp"})]
    path = u.path.rstrip("/").removesuffix("/amp")
    return host + path + ("?" + urlencode(sorted(q)) if q else "")


def same_story(a: str, b: str) -> bool:
    """Başlık benzerliği: anlamlı kelimelerde Jaccard ≥ 0.6 ya da dizgi benzerliği ≥ 0.85."""
    from difflib import SequenceMatcher

    ta, tb = _tokens(a), _tokens(b)
    if ta and tb and len(ta & tb) / len(ta | tb) >= 0.6:
        return True
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.85


def dedup_news(items: list[dict], previous: list[dict] | None = None) -> tuple[list[dict], int]:
    """Aynı haberi veren farklı siteleri tek kayıtta birleştirir. Önceki kayıtla eşleşen haber, önceki kaydın
    kimliğini alır (yeni satır açılmaz). Birleşen kaynaklar 'sources_all', küme büyüklüğü 'cluster_size'."""
    canon: list[dict] = []
    dup = 0
    for p in previous or []:
        canon.append(dict(p, sources_all=list(p.get("sources_all") or [p.get("source")]), _prev=True))
    for it in sorted(items, key=lambda x: x.get("published_at") or ""):
        nu = normalize_url(it.get("link") or "")
        hit = next((c for c in canon if c["id"] == it["id"] or (nu and normalize_url(c.get("link") or "") == nu)
                    or _tokens(c["title"]) == _tokens(it["title"]) or same_story(c["title"], it["title"])), None)
        if hit is None:
            canon.append(dict(it, sources_all=[it.get("source")], cluster_size=1))
            continue
        if hit["id"] != it["id"]:
            dup += 1
        if it.get("source") not in hit["sources_all"]:
            hit["sources_all"].append(it.get("source"))
        hit["cluster_size"] = len(hit["sources_all"])
        hit["_touched"] = True
    out = []
    for c in canon:
        if c.pop("_prev", False) and not c.pop("_touched", False):
            continue  # değişmeyen eski kayıt yeniden yazılmaz
        c.pop("_touched", None)
        out.append(c)
    return out, dup


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
        lo, hi = now_utc() - timedelta(hours=6), now_utc() + timedelta(days=7)
        matches = store.select("matches", [("kickoff_at", "gte", to_iso(lo)), ("kickoff_at", "lt", to_iso(hi))])
    seen = {}
    for it in items:
        seen.setdefault(it["id"], it)
    try:  # son 2 günün kayıtlı haberleriyle de tekilleştir (aynı haber sonraki taramada yeni satır olmasın)
        prev = store.select("agenda", [("fetched_at", "gte", to_iso(now_utc() - timedelta(hours=48)))])
    except Exception:
        prev = []
    rows, n_dup = dedup_news(list(seen.values()), prev)
    rows = link_news(rows, matches)
    ts = to_iso(now_utc())
    for r in rows:
        r["fetched_at"] = ts
        lgs = {m["league"] for m in matches if m["id"] in set(r.get("match_ids") or [])}
        lgs |= {t.split(":", 1)[0] for t in r.get("team_ids") or []}
        r["leagues"] = sorted(lgs)
    if n_dup:
        log.append(f"ℹ️ {n_dup} tekrar eden haber (başlık benzerliği) tek kayıtta birleştirildi")
    store.upsert("agenda", rows)
    linked = sum(1 for r in rows if r["match_ids"])
    log.append(f"{len(rows)} haber kaydedildi, {linked} tanesi maçlara bağlandı")
    return {"news": len(rows), "linked": linked, "log": log}
