from __future__ import annotations

import logging

from .stop_calculator import StopCalculator
from .stop_policy import resolve_stop_policy
from .stop_reconcile import StopReconcile
from .stop_sync import StopSync


class ModularStopEngine:
    def __init__(self, *, bot: object, registry, legacy_stop_engine=None) -> None:
        self.bot = bot
        self.registry = registry
        self.legacy = legacy_stop_engine
        self.calculator = StopCalculator()
        self.sync = StopSync(bot, legacy_stop_engine)
        self.reconcile = StopReconcile(bot, legacy_stop_engine)
        self.log = logging.getLogger("engine.stops")

    def snapshot(self, inst_id: str) -> dict:
        state = self.registry.get(inst_id)
        if state is None:
            return {}
        snapshot = self.calculator.build_snapshot(state)
        payload = snapshot.__dict__.copy()
        payload.update(resolve_stop_policy(state))
        return payload

    def ensure_exchange_stop(self, inst_id: str) -> None:
        state = self.registry.get(inst_id)
        if state is None:
            return None
        return self.sync.ensure_exchange_stop(state)

    def sync_exchange_stop_if_needed(self, inst_id: str) -> None:
        state = self.registry.get(inst_id)
        if state is None:
            return None
        return self.sync.sync_exchange_stop_if_needed(state)

    def run_health_check(self, inst_id: str, current_price: float) -> None:
        state = self.registry.get(inst_id)
        if state is None:
            return None
        return self.sync.run_health_check(state, current_price=current_price)

    def recover(self, inst_id: str) -> None:
        state = self.registry.get(inst_id)
        if state is None:
            return None
        return self.reconcile.recover(state)
