"""Club Elo — eskiden anahtarsız CSV API (api.clubelo.com). Eylül 2026'dan beri kimlik doğrulama istiyor.
CLUBELO_KEY tanımlıysa Authorization başlığıyla denenir; başarısızsa Meclis Elo (iç hesap) kullanılır.
Web sayfaları KAZINMAZ."""
from __future__ import annotations

import csv
import io
from datetime import date

from .http import SourceError, get

SOURCE = "clubelo"
BASE = "http://api.clubelo.com"
COUNTRY = {"T1": "TUR", "E0": "ENG", "E1": "ENG", "SP1": "ESP", "I1": "ITA", "D1": "GER", "F1": "FRA",
           "N1": "NED", "P1": "POR"}


def parse_csv(text: str) -> list[dict]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            rows.append({"club": r["Club"], "country": r["Country"], "level": r.get("Level"), "elo": float(r["Elo"])})
        except (KeyError, ValueError, TypeError):
            continue
    return rows


def ratings(d: date, key: str | None = None) -> list[dict]:
    headers = {"Authorization": f"Bearer {key}"} if key else None
    r = get(f"{BASE}/{d.isoformat()}", headers=headers, timeout=15, retries=0)
    if r.status_code != 200 or "Club" not in r.text[:200]:
        raise SourceError(f"Club Elo API erişilemedi (HTTP {r.status_code}); API kimlik doğrulama istiyor")
    return parse_csv(r.text)
