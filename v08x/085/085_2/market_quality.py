
from __future__ import annotations

from typing import List, Sequence, Any
import statistics


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def analyze_sparse_candles(
    candles: Sequence[Sequence[Any]] | None,
    atr: float,
    short_period: int = 20,
    long_period: int = 55,
    short_threshold: int = 10,
    long_threshold: int = 27,
) -> dict:
    rows = list(candles or [])
    if not rows:
        return {
            "weak_20": 0,
            "weak_55": 0,
            "ratio_20": 0.0,
            "ratio_55": 0.0,
            "reject": False,
            "reason": "",
        }

    parsed = []
    vols = []
    for candle in rows:
        try:
            hi = float(candle[2]); lo = float(candle[3]); close = float(candle[4])
            vol = float(candle[5]) if len(candle) > 5 else 0.0
            parsed.append((hi, lo, close, vol))
            vols.append(max(vol, 0.0))
        except Exception:
            continue

    if not parsed:
        return {
            "weak_20": 0,
            "weak_55": 0,
            "ratio_20": 0.0,
            "ratio_55": 0.0,
            "reject": False,
            "reason": "",
        }

    median_vol = statistics.median(vols) if vols else 0.0
    atr_v = max(_safe_float(atr, 0.0), 1e-12)

    def count_weak(last_n: int) -> int:
        sample = parsed[-last_n:] if len(parsed) >= last_n else parsed
        weak = 0
        for hi, lo, close, vol in sample:
            rng = max(hi - lo, 0.0)
            weak_range = rng < atr_v * 0.15
            weak_vol = median_vol > 0 and vol < median_vol * 0.30
            near_empty = vol <= 0.0 or close <= 0.0
            if weak_range or weak_vol or near_empty:
                weak += 1
        return weak

    weak_20 = count_weak(short_period)
    weak_55 = count_weak(long_period)
    ratio_20 = weak_20 / max(1, min(short_period, len(parsed)))
    ratio_55 = weak_55 / max(1, min(long_period, len(parsed)))

    reject = False
    reason = ""
    if len(parsed) >= short_period and weak_20 >= short_threshold:
        reject = True
        reason = f"sparse candles {weak_20}/{short_period}"
    if len(parsed) >= long_period and weak_55 >= long_threshold:
        reject = True
        reason = f"sparse candles {weak_55}/{long_period}"

    return {
        "weak_20": weak_20,
        "weak_55": weak_55,
        "ratio_20": round(ratio_20, 6),
        "ratio_55": round(ratio_55, 6),
        "reject": reject,
        "reason": reason,
        "median_volume": round(median_vol, 8),
    }
