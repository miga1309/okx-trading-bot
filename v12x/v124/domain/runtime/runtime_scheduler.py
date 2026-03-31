from __future__ import annotations

import time
from typing import Any


class RuntimeScheduler:
    def __init__(self, engine: Any):
        self.engine = engine
        self.mode = "IDLE"
        self.mode_since_ts = time.time()

    def current_mode(self) -> str:
        engine = self.engine
        orchestrator = getattr(engine, "position_orchestrator", None)
        if bool(getattr(engine, "_stop_requested", False)):
            return "STOPPING"
        if bool(getattr(engine, "position_cycle_active", False)):
            return "POSITION_CRITICAL"
        if orchestrator is not None and bool(orchestrator.is_position_critical()):
            return "POSITION_CRITICAL"
        if bool(getattr(engine, "exchange_recovery_pending", False)):
            return "RECONCILE_ACTIVE"
        if bool(getattr(engine, "running", False)):
            return "TRADING_ACTIVE"
        return "IDLE"

    def refresh(self) -> str:
        new_mode = self.current_mode()
        if new_mode != self.mode:
            self.mode = new_mode
            self.mode_since_ts = time.time()
            try:
                self.engine.stats_logger.log("RUNTIME_MODE_CHANGED", mode=new_mode)
            except Exception:
                pass
        return self.mode

    def scanner_pause_required(self) -> bool:
        mode = self.refresh()
        return mode in {"POSITION_CRITICAL", "RECONCILE_ACTIVE", "STOPPING"}
