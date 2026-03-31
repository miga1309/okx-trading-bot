
from __future__ import annotations

from typing import Any

SYNC_INTERVAL_ACTIVE_POSITIONS = 10
SYNC_INTERVAL_IDLE = 60

def get_dynamic_sync_interval(open_positions_count: int) -> int:
    try:
        return SYNC_INTERVAL_ACTIVE_POSITIONS if int(open_positions_count) > 0 else SYNC_INTERVAL_IDLE
    except Exception:
        return SYNC_INTERVAL_IDLE

def turtle_exit_period_from_system(system_name: str) -> int:
    name = str(system_name or "").strip().lower()
    if "55" in name:
        return 20
    if "20" in name:
        return 10
    return 10

def derive_sync_status(
    stop_state: str = "",
    exchange_stop_status: str = "",
    position_health_state: str = "",
    close_pending: bool = False,
) -> str:
    stop_state = str(stop_state or "").upper()
    exchange_stop_status = str(exchange_stop_status or "").upper()
    position_health_state = str(position_health_state or "").upper()

    if bool(close_pending):
        return "CLOSE_PENDING"
    if position_health_state in {"POSITION_GHOST", "GHOST"}:
        return "POSITION_GHOST"
    if stop_state in {"MISSING", "UNVERIFIED", "REJECTED"} or exchange_stop_status in {"MISSING", "ERROR", "REJECTED"}:
        return "STOP_MISSING"
    if position_health_state not in {"", "HEALTHY"}:
        return "SYNC_DRIFT"
    return "SYNC_OK"

def determine_hybrid_stop_mode(system_name: str, units: Any, pnl_pct: Any, peak_pnl_pct: Any = 0.0) -> str:
    name = str(system_name or "").strip().lower()
    try:
        units_i = int(units or 0)
    except Exception:
        units_i = 0
    try:
        pnl = float(pnl_pct or 0.0)
    except Exception:
        pnl = 0.0
    try:
        peak = float(peak_pnl_pct or 0.0)
    except Exception:
        peak = 0.0

    # Conservative transition: the position starts with ATR protection and
    # moves into Turtle Donchian handling only after some progress.
    threshold = 0.35 if "20" in name else 0.50
    if units_i >= 2 or pnl >= threshold or peak >= threshold:
        return "DONCHIAN_ACTIVE"
    return "ATR_INITIAL"

def classify_trend_hold_state(hybrid_stop_mode: str, units: Any, pnl_pct: Any, peak_pnl_pct: Any = 0.0) -> str:
    try:
        units_i = int(units or 0)
    except Exception:
        units_i = 0
    try:
        pnl = float(pnl_pct or 0.0)
    except Exception:
        pnl = 0.0
    try:
        peak = float(peak_pnl_pct or 0.0)
    except Exception:
        peak = 0.0

    mode = str(hybrid_stop_mode or "")
    if mode == "DONCHIAN_ACTIVE" and (units_i >= 2 or peak >= 1.0 or pnl >= 0.75):
        return "TREND_HOLD"
    if mode == "DONCHIAN_ACTIVE":
        return "TREND_ACTIVE"
    return "INITIAL_RISK"
