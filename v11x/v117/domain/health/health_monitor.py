from __future__ import annotations

import logging

from .connection_state import ConnectionState
from .exchange_probe import probe_from_components


class HealthMonitor:
    def __init__(self, *, bot: object) -> None:
        self.bot = bot
        self.log = logging.getLogger("engine.health")

    def run_check(self, force: bool = False) -> dict:
        components = self.bot._maybe_run_exchange_health_check(force=force)
        state, detail = probe_from_components(components)
        snapshot = ConnectionState(
            state=state,
            last_error=str(detail.get("last_error", "") or ""),
            components_down=list(detail.get("components_down", []) or []),
        )
        self.log.info("health_snapshot=%s", snapshot.to_dict(), extra={"engine": "health"})
        return snapshot.to_dict()

    def complete_recovery_if_needed(self) -> None:
        return self.bot._complete_recovery_if_needed()
