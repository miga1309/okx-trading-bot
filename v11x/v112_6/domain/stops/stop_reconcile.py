from __future__ import annotations

import logging


class StopReconcile:
    def __init__(self, bot: object, legacy_stop_engine) -> None:
        self.bot = bot
        self.legacy = legacy_stop_engine
        self.log = logging.getLogger("engine.stops")

    def recover(self, state) -> None:
        if self.legacy is None:
            return None
        inst_id = str(getattr(state, "inst_id", "") or "")
        self.log.info("stop_recovery_requested inst_id=%s", inst_id, extra={"engine": "stops"})
        current_price = float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        candles = []
        try:
            gateway = getattr(self.bot, "gateway", None)
            cfg = getattr(self.bot, "cfg", None)
            if gateway is not None and hasattr(gateway, "get_candles") and inst_id:
                timeframe = str(getattr(cfg, "timeframe", "5m") or "5m")
                candles = list(gateway.get_candles(inst_id, timeframe, 120) or [])
        except Exception:
            self.log.exception("stop_recovery_candles_failed inst_id=%s", inst_id, extra={"engine": "stops"})
            candles = []
        if hasattr(self.bot, "_run_stop_recovery"):
            return self.bot._run_stop_recovery(state, current_price, candles, reason="runtime_bundle")
        return self.legacy._run_stop_recovery(state, current_price, candles, reason="runtime_bundle")
