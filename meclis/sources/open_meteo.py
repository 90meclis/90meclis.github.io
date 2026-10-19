"""Open-Meteo — anahtarsız hava durumu ve yer kodlama (geocoding). Ticari olmayan kullanım ücretsiz."""
from __future__ import annotations

from ..timeutil import parse_dt
from .http import SourceError, get

SOURCE = "open-meteo"

WMO_TR = {0: "Açık", 1: "Çoğunlukla açık", 2: "Parçalı bulutlu", 3: "Kapalı", 45: "Sisli", 48: "Kırağılı sis",
          51: "Hafif çisenti", 53: "Çisenti", 55: "Yoğun çisenti", 61: "Hafif yağmur", 63: "Yağmurlu",
          65: "Şiddetli yağmur", 66: "Dondurucu yağmur", 67: "Şiddetli dondurucu yağmur", 71: "Hafif kar",
          73: "Karlı", 75: "Yoğun kar", 77: "Kar taneleri", 80: "Sağanak", 81: "Kuvvetli sağanak",
          82: "Şiddetli sağanak", 85: "Kar sağanağı", 86: "Yoğun kar sağanağı", 95: "Gök gürültülü fırtına",
          96: "Dolu ihtimalli fırtına", 99: "Şiddetli dolulu fırtına"}


def geocode(query: str) -> dict | None:
    r = get("https://geocoding-api.open-meteo.com/v1/search", params={"name": query, "count": 1, "language": "tr"})
    if r.status_code != 200:
        raise SourceError(f"Open-Meteo geocoding HTTP {r.status_code}")
    res = (r.json() or {}).get("results") or []
    if not res:
        return None
    x = res[0]
    return {"lat": x["latitude"], "lon": x["longitude"], "name": x.get("name"), "country": x.get("country")}


def match_weather(lat: float, lon: float, kickoff_iso: str) -> dict | None:
    ko = parse_dt(kickoff_iso)
    day = ko.date().isoformat()
    r = get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "timezone": "UTC", "start_date": day, "end_date": day,
        "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,relative_humidity_2m,weather_code",
    })
    if r.status_code != 200:
        raise SourceError(f"Open-Meteo HTTP {r.status_code}: {r.text[:120]}")
    h = (r.json() or {}).get("hourly") or {}
    times = h.get("time") or []
    if not times:
        return None
    target = ko.strftime("%Y-%m-%dT%H:00")
    idx = times.index(target) if target in times else min(range(len(times)), key=lambda i: abs(i - ko.hour))
    code = (h.get("weather_code") or [None])[idx]
    return {
        "time_utc": times[idx], "temperature_c": (h.get("temperature_2m") or [None])[idx],
        "precip_prob": (h.get("precipitation_probability") or [None])[idx],
        "precip_mm": (h.get("precipitation") or [None])[idx],
        "wind_kmh": (h.get("wind_speed_10m") or [None])[idx],
        "humidity": (h.get("relative_humidity_2m") or [None])[idx],
        "weather_code": code, "summary": WMO_TR.get(code, "—"),
    }
