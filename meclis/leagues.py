"""Ligleri kaynaklardan dinamik keşfetme.

Sabit liste (config.LEAGUES) kimlikleri doğrulanmış çekirdek ligleri tutar. Bunlara ek olarak BSD'nin /leagues/
listesindeki bütün etkin kulüp ligleri ve kupaları otomatik eklenir (kod: ``B<bsd_id>``). Milli takım turnuvaları,
gençlik ve kadın ligleri ile hazırlık maçları alınmaz: modelimiz kulüp maçları içindir.

Keşfedilen ligler ``leagues`` tablosuna (herkese açık okuma) yazılır; böylece arayüz ve site, BSD anahtarı olmadan
lig adlarını gösterebilir. Tablo yoksa (şema güncellenmediyse) keşif yine çalışır, yalnızca ad kaydı atlanır.
"""
from __future__ import annotations

import re

from .config import LEAGUES, League

_SKIP = re.compile(r"(world cup|qualification|nations league|euro 20|asian cup|africa cup|copa america|gold cup|"
                   r"friendl|u1\d|u2\d|youth|women|liga f\b|nwsl|super cup|supercup)", re.I)
_CUP = re.compile(r"(cup|pokal|copa|coppa|ta[cç]a|coupe|puchar|libertadores|sudamericana|champions league|"
                  r"europa league|conference league|emperor|carabao)", re.I)
_CONTINENTS = {"Europe", "Africa", "Asia", "South America", "North America", "Oceania", "World", "International"}

COUNTRY_TR = {
    "Angola": "Angola", "Argentina": "Arjantin", "Australia": "Avustralya", "Austria": "Avusturya",
    "Belgium": "Belçika", "Brazil": "Brezilya", "Bulgaria": "Bulgaristan", "China": "Çin", "Colombia": "Kolombiya",
    "Czech Republic": "Çekya", "Denmark": "Danimarka", "England": "İngiltere", "Finland": "Finlandiya",
    "France": "Fransa", "Germany": "Almanya", "Greece": "Yunanistan", "Italy": "İtalya", "Japan": "Japonya",
    "Mexico": "Meksika", "Morocco": "Fas", "Netherlands": "Hollanda", "Nigeria": "Nijerya", "Norway": "Norveç",
    "Poland": "Polonya", "Portugal": "Portekiz", "Romania": "Romanya", "Saudi Arabia": "Suudi Arabistan",
    "Scotland": "İskoçya", "South Korea": "Güney Kore", "Spain": "İspanya", "Sweden": "İsveç",
    "Switzerland": "İsviçre", "Tunisia": "Tunus", "Turkey": "Türkiye", "USA": "ABD", "Europe": "Avrupa",
    "Africa": "Afrika", "Asia": "Asya", "South America": "Güney Amerika", "North America": "Kuzey Amerika",
}


def from_bsd(raw: list[dict], today_iso: str) -> list[dict]:
    """BSD /leagues/ sonucunu lig satırlarına çevirir (çekirdek listede olanlar atlanır)."""
    known = {lg.bsd_id for lg in LEAGUES.values() if lg.bsd_id}
    out = []
    for x in raw or []:
        bid, name = x.get("id"), str(x.get("name") or "")
        if not bid or bid in known or x.get("is_women") or x.get("is_active") is False or _SKIP.search(name):
            continue
        cs = x.get("current_season") or {}
        if cs.get("end_date") and str(cs["end_date"]) < today_iso[:10]:
            continue  # sezonu bitmiş (ör. eski turnuva)
        country = str(x.get("country") or "")
        out.append({"code": f"B{int(bid)}", "name": name, "country": COUNTRY_TR.get(country, country),
                    "bsd_id": int(bid), "cup": bool(_CUP.search(name)) or country in _CONTINENTS,
                    "season_start": cs.get("start_date"), "source": "bsd"})
    return out


def register(rows: list[dict]) -> list[str]:
    """Satırları config.LEAGUES'e ekler; eklenen kodları döndürür."""
    codes = []
    for r in rows:
        code = r["code"]
        if code not in LEAGUES:
            LEAGUES[code] = League(code, r["name"], r.get("country") or "", None, None, None, r.get("bsd_id"),
                                   fdcuk=False, cup=bool(r.get("cup")))
        codes.append(code)
    return codes


def discover(store, settings, bsd=None) -> list[str]:
    """BSD'den ligleri keşfeder, kaydeder ve settings.leagues'e ekler. Hata olursa kayıtlı listeyi kullanır."""
    from .timeutil import now_utc, to_iso

    if not getattr(settings, "auto_leagues", False) or settings.demo_mode:
        return []
    rows: list[dict] = []
    if bsd is not None and bsd.available and not getattr(store, "read_only", False):
        try:
            raw, path = [], "/leagues/"
            params = {"limit": 50, "offset": 0}
            for _ in range(10):
                d = bsd._get(path, params)
                raw += d.get("results") or []
                if not d.get("next"):
                    break
                params["offset"] += 50
            rows = from_bsd(raw, to_iso(now_utc()))
            try:
                store.upsert("leagues", [{k: r[k] for k in ("code", "name", "country", "bsd_id", "cup", "source")}
                                         for r in rows])
            except Exception:
                pass  # leagues tablosu yok: ad kaydı atlanır
        except Exception:
            rows = []
    if not rows:
        rows = load_known(store, register_only=False)
    codes = register(rows)
    for c in codes:
        if c not in settings.leagues:
            settings.leagues.append(c)
    return codes


def load_known(store, register_only: bool = True) -> list[dict]:
    """Kayıtlı (keşfedilmiş) ligleri okur ve LEAGUES'e ekler — arayüz için (anahtar gerekmez)."""
    try:
        rows = [r for r in store.select("leagues") if str(r.get("code", "")).startswith("B")]
    except Exception:
        rows = []
    if register_only:
        register(rows)
    return rows
