from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from ..config import DATA_DIR

USER_AGENT = "90Meclis/1.0 (futbol analiz uygulamasi; acik kaynak; kisisel kullanim)"
CACHE_DIR = DATA_DIR / "cache"


class SourceError(RuntimeError):
    pass


def get(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float = 25,
        retries: int = 2) -> requests.Response:
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 429:
                raise SourceError(f"İstek limiti aşıldı (429). {(r.text or '')[:160]}")
            if r.status_code >= 500:
                raise SourceError(f"Sunucu hatası {r.status_code}")
            return r
        except (requests.RequestException, SourceError) as e:
            last = e
            if "429" in str(e):  # istek limiti: yeniden denemek kotayı daha da yakar ve işi bekletir
                break
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise SourceError(f"{url} erişilemedi: {last}")


def cached_text(url: str, ttl_seconds: int, **kw) -> str:
    """Disk önbellekli GET (CSV gibi büyük ve seyrek değişen dosyalar için)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1((url + json.dumps(kw.get("params") or {}, sort_keys=True)).encode()).hexdigest()
    path = Path(CACHE_DIR / f"{key}.txt")
    if path.exists() and time.time() - path.stat().st_mtime < ttl_seconds:
        return path.read_text(encoding="utf-8")
    r = get(url, **kw)
    if r.status_code != 200:
        if path.exists():
            return path.read_text(encoding="utf-8")
        raise SourceError(f"{url} -> HTTP {r.status_code}")
    text = r.content.decode("utf-8-sig", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text
