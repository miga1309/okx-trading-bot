from __future__ import annotations

import logging


class StopSync:
    def __init__(self, bot: object, legacy_stop_engine) -> None:
        self.bot = bot
        self.legacy = legacy_stop_engine
        self.log = logging.getLogger("engine.stops")

    def ensure_exchange_stop(self, state) -> None:
        if self.legacy is None:
            return None
        self.log.info("ensure_exchange_stop inst_id=%s", getattr(state, "inst_id", ""), extra={"engine": "stops"})
        return self.legacy._ensure_exchange_stop(state)

    def sync_exchange_stop_if_needed(self, state) -> None:
        if self.legacy is None:
            return None
        return self.legacy._sync_exchange_stop_if_needed(state)

    def run_health_check(self, state, current_price: float) -> None:
        if self.legacy is None:
            return None
        return self.legacy._run_stop_health_check(state, current_price=current_price)
