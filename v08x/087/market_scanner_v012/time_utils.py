
from __future__ import annotations

from datetime import datetime, timedelta, timezone

BAR_TO_SECONDS = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1H': 3600,
    '2H': 7200,
    '4H': 14400,
    '6H': 21600,
    '12H': 43200,
    '1D': 86400,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def floor_to_bar(dt: datetime, timeframe: str) -> datetime:
    sec = BAR_TO_SECONDS[timeframe]
    ts = int(dt.timestamp())
    floored = ts - (ts % sec)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def compute_window(days: int, timeframe: str) -> tuple[datetime, datetime, bool]:
    now = utc_now()
    end = floor_to_bar(now, timeframe)
    start = end - timedelta(days=days)
    return start, end, False


def expected_candles(start: datetime, end: datetime, timeframe: str) -> int:
    sec = BAR_TO_SECONDS[timeframe]
    span = max(0, int((end - start).total_seconds()))
    return span // sec


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def ms_to_iso(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).isoformat()
