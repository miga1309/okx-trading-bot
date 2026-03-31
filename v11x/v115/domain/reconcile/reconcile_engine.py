from __future__ import annotations

import logging

from .reconcile_positions import ReconcilePositions
from .reconcile_report import ReconcileReport
from .reconcile_stops import ReconcileStops


class ReconcileEngine:
    def __init__(self, *, bot: object, registry, stop_engine) -> None:
        self.bot = bot
        self.registry = registry
        self.positions = ReconcilePositions(bot, registry)
        self.stops = ReconcileStops(stop_engine)
        self.log = logging.getLogger("engine.reconcile")

    def run_startup_reconcile(self) -> dict:
        self.positions.sync_from_exchange()
        recovered_stops = self.stops.recover_for_open_positions(self.registry)
        report = ReconcileReport(
            open_positions=self.registry.open_count(),
            recovered_stops=recovered_stops,
            connectivity_state=str(getattr(self.bot, "exchange_connectivity_state", "") or ""),
            notes=[],
        )
        self.log.info("startup_reconcile=%s", report.to_dict(), extra={"engine": "reconcile"})
        return report.to_dict()
