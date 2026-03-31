from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, List, Optional


class PositionOrchestrator:
    """WS-first normalizer for live position/order events.

    Background WS callbacks only enqueue events here. Engine loop consumes and applies
    them on the main trading thread to avoid cross-thread mutation of runtime state.
    """

    def __init__(self, engine: Any):
        self.engine = engine
        self._queue: "queue.SimpleQueue[dict]" = queue.SimpleQueue()
        self._lock = threading.RLock()
        self._latest_positions: Dict[str, dict] = {}
        self._latest_orders: Dict[str, dict] = {}
        self._last_position_event_ts: Dict[str, float] = {}
        self._last_order_event_ts: Dict[str, float] = {}
        self._critical_until_ts: float = 0.0
        self._last_consume_ts: float = 0.0

    def enqueue_ws_event(self, channel: str, rows: List[dict], recv_ts: Optional[float] = None) -> None:
        payload = {
            "channel": str(channel or "").lower(),
            "rows": [dict(r or {}) for r in list(rows or [])],
            "recv_ts": float(recv_ts or time.time()),
        }
        self._queue.put(payload)

    def mark_position_critical(self, reason: str = "", duration_sec: float = 8.0) -> None:
        now = time.time()
        with self._lock:
            self._critical_until_ts = max(self._critical_until_ts, now + max(1.0, float(duration_sec or 0.0)))
        try:
            self.engine.stats_logger.log("WS_POSITION_CRITICAL", reason=str(reason or ""), critical_until_ts=round(self._critical_until_ts, 3))
        except Exception:
            pass

    def is_position_critical(self) -> bool:
        with self._lock:
            return time.time() < float(self._critical_until_ts or 0.0)

    def recent_position_event(self, inst_id: str, max_age_sec: float = 12.0) -> bool:
        inst = str(inst_id or "").upper()
        with self._lock:
            ts = float(self._last_position_event_ts.get(inst, 0.0) or 0.0)
        return ts > 0.0 and (time.time() - ts) <= max(1.0, float(max_age_sec or 0.0))

    def latest_position(self, inst_id: str) -> Optional[dict]:
        inst = str(inst_id or "").upper()
        with self._lock:
            row = dict(self._latest_positions.get(inst, {}) or {})
        return row or None

    def consume_pending_events(self, max_events: int = 500) -> int:
        consumed = 0
        while consumed < max_events:
            try:
                event = self._queue.get_nowait()
            except Exception:
                break
            self._apply_event(event)
            consumed += 1
        if consumed:
            self._last_consume_ts = time.time()
        return consumed

    def _apply_event(self, event: dict) -> None:
        channel = str(event.get("channel") or "").lower()
        rows = list(event.get("rows") or [])
        recv_ts = float(event.get("recv_ts") or time.time())
        if channel == "positions":
            self._apply_positions(rows, recv_ts)
        elif channel == "orders":
            self._apply_orders(rows, recv_ts)

    def _apply_positions(self, rows: List[dict], recv_ts: float) -> None:
        with self._lock:
            seen = set()
            for row in rows:
                inst_id = str((row or {}).get("instId") or "").upper()
                if not inst_id:
                    continue
                seen.add(inst_id)
                self._latest_positions[inst_id] = dict(row or {})
                self._last_position_event_ts[inst_id] = recv_ts
            # keep previous rows for instruments omitted by delta updates
        self.mark_position_critical("ws_positions", duration_sec=10.0)
        engine = self.engine
        for inst_id, state in list(getattr(engine, "position_state", {}).items()):
            row = self.latest_position(inst_id)
            if not row:
                continue
            try:
                qty = abs(float(row.get("pos") or 0.0))
            except Exception:
                qty = 0.0
            try:
                avg_px = float(row.get("avgPx") or 0.0)
            except Exception:
                avg_px = 0.0
            try:
                mark_px = float(row.get("markPx") or row.get("last") or avg_px or 0.0)
            except Exception:
                mark_px = avg_px
            if qty > 0:
                prior_qty = float(getattr(state, "qty", 0.0) or 0.0)
                state.qty = qty
                if avg_px > 0:
                    state.avg_px = avg_px
                if mark_px > 0:
                    state.last_px = mark_px
                if qty > prior_qty + 1e-12:
                    state.state_tag = "PYRAMID_CONFIRMED" if int(getattr(state, "units", 1) or 1) > 1 else "ENTRY_CONFIRMED"
                elif qty < max(0.0, prior_qty - 1e-12):
                    state.state_tag = "REDUCE_PENDING"
                else:
                    state.state_tag = "ACTIVE"
                try:
                    engine._reset_missing_exchange_tracking(state)
                    engine._finish_entry_recovery_window(state)
                except Exception:
                    pass

    def _apply_orders(self, rows: List[dict], recv_ts: float) -> None:
        with self._lock:
            for row in rows:
                item = dict(row or {})
                order_id = str(item.get("ordId") or item.get("clOrdId") or "").strip()
                inst_id = str(item.get("instId") or "").upper()
                if order_id:
                    self._latest_orders[order_id] = item
                if inst_id:
                    self._last_order_event_ts[inst_id] = recv_ts
        self.mark_position_critical("ws_orders", duration_sec=6.0)
        engine = self.engine
        for row in rows:
            inst_id = str((row or {}).get("instId") or "").upper()
            if not inst_id:
                continue
            state = getattr(engine, "position_state", {}).get(inst_id)
            ord_state = str((row or {}).get("state") or (row or {}).get("ordState") or "").lower()
            fill_sz = 0.0
            try:
                fill_sz = abs(float((row or {}).get("fillSz") or 0.0))
            except Exception:
                fill_sz = 0.0
            if state is None:
                continue
            if ord_state in {"filled", "partially_filled", "partially-filled"} or fill_sz > 0:
                if str(getattr(state, "state_tag", "")).upper() in {"ENTRY_SUBMITTED", "ENTRY_PARTIAL", "ENTRY_RECOVERING"}:
                    state.state_tag = "ENTRY_CONFIRMED"
                elif str(getattr(state, "state_tag", "")).upper() == "PYRAMID_PENDING":
                    state.state_tag = "PYRAMID_CONFIRMED"
            elif ord_state in {"canceled", "cancelled"}:
                if str(getattr(state, "close_pending", False)).lower() == "true":
                    state.state_tag = "ACTIVE"
