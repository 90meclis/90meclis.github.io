"""MET Norway Locationforecast 2.0 — birincil hava durumu kaynağı (anahtarsız, ticari kullanım serbest, CC BY 4.0).
Koşullar: tanıtıcı User-Agent zorunlu; aynı nokta için Expires süresine uyulur (biz maç başına 6 saatte bir sorarız);
atıf: "Data from MET Norway". 10 güne kadar saatlik tahmin."""
from __future__ import annotations

from ..timeutil import parse_dt
from .http import SourceError, get

SOURCE = "met-norway"
URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
UA = {"User-Agent": "90MeclisBot/1.0 +https://90meclis.github.io"}
ATTRIBUTION = "Data from MET Norway"

SYMBOL_TR = {"clearsky": "Açık", "fair": "Çoğunlukla açık", "partlycloudy": "Parçalı bulutlu", "cloudy": "Kapalı",
             "fog": "Sisli", "lightrain": "Hafif yağmur", "rain": "Yağmurlu", "heavyrain": "Şiddetli yağmur",
             "lightrainshowers": "Hafif sağanak", "rainshowers": "Sağanak", "heavyrainshowers": "Kuvvetli sağanak",
             "lightsnow": "Hafif kar", "snow": "Karlı", "heavysnow": "Yoğun kar", "sleet": "Karla karışık yağmur",
             "lightsleet": "Hafif karla karışık yağmur", "thunder": "Gök gürültülü", "rainandthunder": "Gök gürültülü yağmur"}


def parse(data: dict, kickoff_iso: str) -> dict | None:
    ts = ((data or {}).get("properties") or {}).get("timeseries") or []
    if not ts:
        return None
    ko = parse_dt(kickoff_iso)
    best = min(ts, key=lambda t: abs((parse_dt(t["time"]) - ko).total_seconds()))
    if abs((parse_dt(best["time"]) - ko).total_seconds()) > 6 * 3600:
        return None  # tahmin ufku dışında
    det = ((best.get("data") or {}).get("instant") or {}).get("details") or {}
    nxt = (best.get("data") or {}).get("next_1_hours") or (best.get("data") or {}).get("next_6_hours") or {}
    sym = ((nxt.get("summary") or {}).get("symbol_code") or "").split("_")[0]
    wind = det.get("wind_speed")
    return {"time_utc": best["time"], "temperature_c": det.get("air_temperature"),
            "precip_mm": (nxt.get("details") or {}).get("precipitation_amount"), "precip_prob": None,
            "wind_kmh": round(wind * 3.6, 1) if wind is not None else None, "humidity": det.get("relative_humidity"),
            "weather_code": sym or None, "summary": SYMBOL_TR.get(sym, sym or "—"), "attribution": ATTRIBUTION}


def match_weather(lat: float, lon: float, kickoff_iso: str) -> dict | None:
    r = get(URL, params={"lat": round(float(lat), 4), "lon": round(float(lon), 4)}, headers=UA)
    if r.status_code != 200:
        raise SourceError(f"MET Norway HTTP {r.status_code}")
    return parse(r.json(), kickoff_iso)
