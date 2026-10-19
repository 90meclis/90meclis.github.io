"""Ücretsiz RSS akışları (TRT Haber Spor, AA Spor, Fotomaç, BBC Sport). Yalnızca başlık, özet ve bağlantı
saklanır; haberin tamamı kopyalanmaz, kullanıcı kaynağa yönlendirilir."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import feedparser

from ..timeutil import to_iso
from .http import get

CATEGORIES = {
    "sakatlık": ["sakat", "sakatlı", "yaralan", "ameliyat", "tedavi", "kadroda yok", "forma giyemeyecek",
                 "cezalı", "kırmızı kart cezası", "injury", "injured", "ruled out", "hamstring", "doubt",
                 "suspended", "suspension"],
    "teknik direktör": ["teknik direktör", "teknik adam", "hoca", "görevden alındı", "istifa", "yollar ayrıldı",
                        "manager", "head coach", "sacked", "appointed"],
    "transfer": ["transfer", "imza", "sözleşme", "kiralık", "bonservis", "anlaştı", "signs", "signing",
                 "loan", "deal", "contract"],
    "kadro": ["ilk 11", "kadro", "muhtemel 11", "lineup", "team news", "squad"],
}


def categorize(text: str) -> str:
    t = (text or "").lower()
    for cat, words in CATEGORIES.items():
        if any(w in t for w in words):
            return cat
    return "genel"


def _clean_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch_feed(url: str) -> list[dict]:
    r = get(url, timeout=20)
    if r.status_code != 200:
        return []
    feed = feedparser.parse(r.content)
    src = (feed.feed.get("title") or url)[:80]
    out = []
    for e in feed.entries[:100]:
        link = e.get("link") or ""
        title = _clean_html(e.get("title") or "")
        if not link or not title:
            continue
        pub = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                pub = to_iso(datetime(*e[k][:6], tzinfo=timezone.utc))
                break
        summary = _clean_html(e.get("summary") or "")[:400]
        out.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:20], "title": title, "link": link, "source": src,
            "published_at": pub, "summary": summary, "category": categorize(f"{title} {summary}"),
        })
    return out
