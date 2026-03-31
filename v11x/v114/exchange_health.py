from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_exchange_ts_ms(value) -> Optional[datetime]:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        ts = float(text)
        if ts > 10_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


def classify_connectivity_state(components: dict) -> tuple[str, dict]:
    comp = dict(components or {})
    oks = {name: bool((item or {}).get("ok", False)) for name, item in comp.items()}
    up_count = sum(1 for v in oks.values() if v)
    last_error = ""
    for name, item in comp.items():
        if not bool((item or {}).get("ok", False)):
            err = str((item or {}).get("error") or "").strip()
            if err:
                last_error = f"{name}: {err}"
                break
    if comp and up_count == len(comp):
        state = "CONNECTED"
    elif up_count == 0:
        state = "DISCONNECTED"
    else:
        state = "DEGRADED"
    return state, {
        "components_down": [name for name, ok in oks.items() if not ok],
        "components_up": [name for name, ok in oks.items() if ok],
        "last_error": last_error,
    }


def summarize_connectivity_rows(rows: list[dict], components: dict | None = None, current_state: str = "") -> dict:
    incidents = [row for row in list(rows or []) if str(row.get("event") or "") == "CONNECTIVITY_INCIDENT_CLOSED"]
    total_degraded = 0.0
    total_disconnected = 0.0
    max_incident = 0.0
    error_types: dict[str, int] = {}
    components_errors: dict[str, int] = {}
    for row in list(rows or []):
        if str(row.get("event") or "") in {"CONNECTIVITY_STATE_CHANGED", "CONNECTIVITY_HEARTBEAT_SUMMARY"}:
            for name, item in dict(row.get("components") or {}).items():
                if not bool((item or {}).get("ok", False)):
                    et = str((item or {}).get("error_type") or "unknown")
                    error_types[et] = error_types.get(et, 0) + 1
                    components_errors[name] = components_errors.get(name, 0) + 1
    for row in incidents:
        dur = float(row.get("duration_sec", 0.0) or 0.0)
        peak = str(row.get("peak_state") or row.get("start_state") or "")
        if peak == "DISCONNECTED":
            total_disconnected += dur
        else:
            total_degraded += dur
        max_incident = max(max_incident, dur)
    comp = dict(components or {})
    state = str(current_state or "")
    if not state and comp:
        state, _ = classify_connectivity_state(comp)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_state": state or "IDLE",
        "incident_count": len(incidents),
        "recovery_count": len(incidents),
        "total_degraded_sec": round(total_degraded, 3),
        "total_disconnected_sec": round(total_disconnected, 3),
        "max_incident_sec": round(max_incident, 3),
        "error_types": error_types,
        "component_error_counts": components_errors,
        "components": comp,
        "components_down": [name for name, item in comp.items() if not bool((item or {}).get("ok", False))],
    }
