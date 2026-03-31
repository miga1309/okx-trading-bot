from __future__ import annotations


def resolve_stop_policy(state) -> dict:
    return {
        "inst_id": str(getattr(state, "inst_id", "") or ""),
        "desired_stop_mode": str(getattr(state, "desired_stop_mode", "") or ""),
        "active_stop_mode": str(getattr(state, "active_stop_mode", "") or ""),
        "stop_state": str(getattr(state, "stop_state", "") or ""),
        "exchange_stop_status": str(getattr(state, "exchange_stop_status", "") or ""),
    }
