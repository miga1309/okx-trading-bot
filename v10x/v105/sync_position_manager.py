
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
from typing import Any, Sequence


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _stable_trade_id(inst_id: str, side: str, stamp: str) -> str:
    return f"{str(inst_id or '').strip()}::{str(side or '').strip()}::{str(stamp or '').strip()}"




def _infer_units_from_journal(inst_id: str, pos_side: str, qty: float, journal_file: str | Path | None = None) -> tuple[int, float]:
    path = Path(journal_file) if journal_file else None
    if path is None or not path.exists():
        return 0, 0.0

    inst_id = str(inst_id or "").strip().upper()
    pos_side = str(pos_side or "").strip().lower()
    matched: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                row_inst = str(row.get("inst_id") or row.get("symbol") or "").strip().upper()
                if row_inst != inst_id:
                    continue
                row_side = str(row.get("side") or row.get("pos_side") or "").strip().lower()
                if row_side and pos_side and row_side != pos_side:
                    continue
                matched.append(row)
    except Exception:
        return 0, 0.0

    if not matched:
        return 0, 0.0

    explicit_units = 0
    explicit_bases: list[float] = []
    add_events = 0
    entry_seen = False
    qty_candidates: list[float] = []

    for row in matched:
        event = str(row.get("event") or row.get("action") or "").strip().upper()
        units_val = _safe_int(row.get("units", row.get("unit_count", 0)), 0)
        if units_val > explicit_units:
            explicit_units = units_val
        base_val = _safe_float(row.get("base_unit_qty", row.get("unit_qty", 0.0)), 0.0)
        if base_val > 0:
            explicit_bases.append(base_val)
        row_qty = _safe_float(row.get("qty", row.get("position_qty", row.get("filled_qty", 0.0))), 0.0)
        if row_qty > 0:
            qty_candidates.append(row_qty)
        if event in {"ENTRY_FILLED", "POSITION_OPENED", "OPEN", "ENTRY_OPENED", "SYNC_POSITION_OPENED"}:
            entry_seen = True
        if event in {"ADD_UNIT", "PYRAMID_ADD", "UNIT_ADDED", "ADD", "PYRAMID"}:
            add_events += 1

    inferred_units = explicit_units
    if inferred_units <= 0 and (entry_seen or add_events > 0):
        inferred_units = 1 + add_events

    inferred_base = min(explicit_bases) if explicit_bases else 0.0
    qty = _safe_float(qty, 0.0)
    if inferred_base <= 0 and inferred_units > 0 and qty > 0:
        inferred_base = qty / max(1, inferred_units)
    if inferred_units <= 0 and inferred_base > 0 and qty > 0:
        inferred_units = max(1, int(round(qty / inferred_base)))
    if inferred_units <= 0 and qty > 0 and qty_candidates:
        min_qty = min(x for x in qty_candidates if x > 0) if any(x > 0 for x in qty_candidates) else 0.0
        if min_qty > 0:
            inferred_units = max(1, int(round(qty / min_qty)))
            if inferred_base <= 0:
                inferred_base = min_qty

    return max(0, inferred_units), max(0.0, inferred_base)

def restore_sync_position_state(state, cfg, inst_id: str, pos_side: str, avg_px: float, last_px: float, qty: float, atr: float, journal_file: str | Path | None = None) -> list[str]:
    restored: list[str] = []

    system_name = str(getattr(state, "system_name", "") or "").strip()
    if system_name.lower() == "sync" or not system_name:
        system_name = "Turtle 20"
        state.system_name = system_name
        restored.append("system_name")

    entry_period = _safe_int(getattr(state, "entry_period", 0), 0)
    if entry_period <= 0:
        entry_period = 55 if "55" in system_name else 20
        state.entry_period = entry_period
        restored.append("entry_period")

    exit_period = _safe_int(getattr(state, "exit_period", 0), 0)
    if exit_period <= 0:
        exit_period = 20 if "55" in system_name else 10
        state.exit_period = exit_period
        restored.append("exit_period")

    if _safe_float(getattr(state, "atr", 0.0), 0.0) <= 0 and atr > 0:
        state.atr = float(atr)
        restored.append("atr")

    if not str(getattr(state, "trade_id", "") or "").strip():
        stamp = str(getattr(state, "entry_time", "") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        state.trade_id = _stable_trade_id(inst_id, pos_side, stamp)
        restored.append("trade_id")

    if not str(getattr(state, "entry_time", "") or "").strip():
        state.entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        restored.append("entry_time")

    current_units = max(0, _safe_int(getattr(state, "units", 0), 0))
    current_base_unit_qty = _safe_float(getattr(state, "base_unit_qty", 0.0), 0.0)
    inferred_journal_units, inferred_journal_base = _infer_units_from_journal(inst_id, pos_side, qty, journal_file)

    if current_base_unit_qty > 0 and qty > 0:
        inferred_from_base = max(1, int(round(float(qty) / float(current_base_unit_qty))))
        if inferred_from_base > current_units:
            state.units = inferred_from_base
            current_units = inferred_from_base
            restored.append("units")

    if current_units <= 0 and inferred_journal_units > 0:
        state.units = inferred_journal_units
        current_units = inferred_journal_units
        restored.append("units")

    if current_base_unit_qty <= 0 and inferred_journal_base > 0:
        state.base_unit_qty = inferred_journal_base
        current_base_unit_qty = inferred_journal_base
        restored.append("base_unit_qty")

    if current_units <= 0:
        state.units = 1
        current_units = 1
        restored.append("units")

    if current_base_unit_qty <= 0 and qty > 0:
        units = max(1, _safe_int(getattr(state, "units", 1), 1))
        state.base_unit_qty = float(qty) / float(units)
        current_base_unit_qty = float(getattr(state, "base_unit_qty", 0.0) or 0.0)
        restored.append("base_unit_qty")

    atr_val = max(_safe_float(getattr(state, "atr", atr), atr), 0.0)
    if _safe_float(getattr(state, "stop_price", 0.0), 0.0) <= 0 and avg_px > 0 and atr_val > 0:
        state.stop_price = avg_px - cfg.atr_stop_multiple * atr_val if pos_side == "long" else avg_px + cfg.atr_stop_multiple * atr_val
        restored.append("stop_price")

    if _safe_float(getattr(state, "initial_stop_price", 0.0), 0.0) <= 0 and _safe_float(getattr(state, "stop_price", 0.0), 0.0) > 0:
        state.initial_stop_price = float(getattr(state, "stop_price", 0.0))
        restored.append("initial_stop_price")

    if _safe_float(getattr(state, "next_pyramid_price", 0.0), 0.0) <= 0 and avg_px > 0 and atr_val > 0:
        units = max(1, _safe_int(getattr(state, "units", 1), 1))
        dist = float(cfg.add_unit_every_atr) * atr_val * units
        state.next_pyramid_price = avg_px + dist if pos_side == "long" else avg_px - dist
        restored.append("next_pyramid_price")

    if not str(getattr(state, "stop_state", "") or "").strip() and _safe_float(getattr(state, "stop_price", 0.0), 0.0) > 0:
        state.stop_state = "ACTIVE"
        restored.append("stop_state")

    if not str(getattr(state, "position_health_state", "") or "").strip():
        state.position_health_state = "HEALTHY"
        restored.append("position_health_state")

    if not str(getattr(state, "entry_context_file", "") or "").strip():
        setattr(state, "sync_restored_context", True)
        restored.append("sync_restored_context")

    state.avg_px = float(avg_px or getattr(state, "avg_px", 0.0) or 0.0)
    state.last_px = float(last_px or getattr(state, "last_px", 0.0) or 0.0)
    state.qty = float(qty or getattr(state, "qty", 0.0) or 0.0)
    return restored


def build_sync_popup_payload(engine, row: dict, journal_file: str | Path) -> dict:
    inst_id = str(row.get("inst_id") or "").strip()
    side = str(row.get("side") or "long").strip().lower()
    entry_period = _safe_int(row.get("entry_period", 20), 20)
    timeframe = str(getattr(getattr(engine, "cfg", None), "timeframe", "") or "5m")
    desired_limit = 80 if entry_period >= 55 else 60
    candles = []
    try:
        if engine is not None and inst_id:
            candles = list(engine.gateway.get_candles(inst_id, timeframe, desired_limit) or [])
    except Exception:
        candles = []

    extra_markers = []
    try:
        path = Path(journal_file)
        if path.exists():
            rows = []
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
            trade_id = str(row.get("trade_id") or "").strip()
            matched = [r for r in rows if str(r.get("inst_id") or "").strip() == inst_id and (not trade_id or str(r.get("trade_id") or "").strip() == trade_id)]
            add_rows = [r for r in matched if str(r.get("event") or "").strip() == "ADD_UNIT"]
            for idx, item in enumerate(add_rows[-3:], start=2):
                price = _safe_float(item.get("price", 0.0), 0.0)
                if price > 0:
                    extra_markers.append({"kind": "add", "label": f"U{idx}", "index": max(0, len(candles) - 1 - (len(add_rows[-3:]) - idx + 1)), "price": price})
    except Exception:
        extra_markers = []

    system_name = str(row.get("system_name") or "Turtle 20")
    return {
        "version": "SYNC_RESTORED_CONTEXT",
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "inst_id": inst_id,
        "side": side,
        "timeframe": timeframe,
        "entry_period": entry_period,
        "exit_period": 20 if "55" in system_name else 10,
        "system_name": system_name,
        "entry_price": _safe_float(row.get("avg_px", 0.0), 0.0),
        "current_price": _safe_float(row.get("last_px", 0.0), 0.0),
        "stop_price": _safe_float(row.get("stop_price", 0.0), 0.0),
        "next_pyramid_price": _safe_float(row.get("next_pyramid_price", 0.0), 0.0),
        "entry_atr": _safe_float(row.get("atr", 0.0), 0.0),
        "qty": _safe_float(row.get("qty", 0.0), 0.0),
        "units": _safe_int(row.get("units", 1), 1),
        "trade_id": str(row.get("trade_id") or ""),
        "candles": candles,
        "live_chart": True,
        "chart_mode": "live",
        "sync_restored_context": True,
        "context_source": "SYNC_RESTORED_CONTEXT",
        "extra_markers": extra_markers,
    }
