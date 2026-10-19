from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
TR = ZoneInfo("Europe/Istanbul")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def parse_dt(value) -> datetime | None:
    if value is None or value == "" or (isinstance(value, float) and value != value) or str(value).lower() in ("nan", "nat", "none"):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso(value) -> str | None:
    dt = parse_dt(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00") if dt else None


def tr_str(value, fmt: str = "%d.%m.%Y %H:%M") -> str:
    dt = parse_dt(value)
    return dt.astimezone(TR).strftime(fmt) if dt else "—"


def tr_date(value) -> date | None:
    dt = parse_dt(value)
    return dt.astimezone(TR).date() if dt else None


def day_bounds_utc(d: date) -> tuple[str, str]:
    start = datetime(d.year, d.month, d.day, tzinfo=TR)
    return to_iso(start), to_iso(start + timedelta(days=1))
