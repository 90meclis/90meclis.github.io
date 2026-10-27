"""ESPN herkese açık skor tablosu (anahtarsız, kotasız): yalnızca CANLI skor/dakika için.

Resmî sonuç ve sonuçlandırma bu kaynaktan YAPILMAZ (uzatma/penaltı skorları 90 dakikalık pazarlarla karışabilir);
onlar sonuç işinde birden çok kaynakla kesinleşir."""
from __future__ import annotations

from datetime import datetime

from .http import get

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
LIVE = {"STATUS_FIRST_HALF": "1. yarı", "STATUS_SECOND_HALF": "2. yarı", "STATUS_HALFTIME": "Devre arası",
        "STATUS_OVERTIME": "Uzatma", "STATUS_EXTRA_TIME": "Uzatma", "STATUS_END_OF_REGULATION": "90 dk bitti",
        "STATUS_SHOOTOUT": "Penaltılar", "STATUS_END_OF_EXTRATIME": "Uzatma bitti", "STATUS_IN_PROGRESS": "Oynanıyor"}
FINAL = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"}


def scoreboard(day: datetime) -> list[dict]:
    """O UTC gününün bütün futbol maçları: {ko, home, away, hg, ag, durum, dakika, bitti}."""
    r = get(URL, params={"dates": day.strftime("%Y%m%d"), "limit": 1000}, timeout=20, retries=1)
    if r.status_code != 200:
        return []
    out = []
    for e in (r.json() or {}).get("events") or []:
        try:
            c = e["competitions"][0]
            st = (c.get("status") or {}).get("type") or {}
            name = st.get("name") or ""
            t = {x["homeAway"]: x for x in c["competitors"]}
            out.append({"ko": e["date"], "home": t["home"]["team"]["displayName"], "away": t["away"]["team"]["displayName"],
                        "hg": int(t["home"].get("score") or 0), "ag": int(t["away"].get("score") or 0),
                        "durum": LIVE.get(name) or ("MS" if name in FINAL else None),
                        "dakika": (c.get("status") or {}).get("displayClock"), "bitti": name in FINAL,
                        "canli": name in LIVE})
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out
