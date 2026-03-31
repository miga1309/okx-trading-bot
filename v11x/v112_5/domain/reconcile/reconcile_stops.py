from __future__ import annotations

import logging


class ReconcileStops:
    def __init__(self, stop_engine) -> None:
        self.stop_engine = stop_engine
        self.log = logging.getLogger("engine.reconcile")

    def recover_for_open_positions(self, registry) -> int:
        recovered = 0
        for state in list(registry.list_open()):
            inst_id = str(getattr(state, "inst_id", "") or "")
            if not inst_id:
                continue
            try:
                self.stop_engine.recover(inst_id)
                recovered += 1
            except Exception:
                self.log.exception("stop_reconcile_failed inst_id=%s", inst_id, extra={"engine": "reconcile"})
        return recovered
