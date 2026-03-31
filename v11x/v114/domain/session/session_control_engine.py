from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SessionControlEngine:
    event_bus: object
    logger: object
    state_store: object
    state: str = field(default="STOPPED")

    def _transition(self, new_state: str, **payload) -> None:
        self.state = str(new_state)
        row = {"state": self.state, "ts": datetime.now().isoformat(timespec="seconds")}
        row.update(payload)
        try:
            self.state_store.save(row)
        except Exception:
            pass
        try:
            self.logger.info("session_state=%s payload=%s", self.state, payload, extra={"engine": "session"})
        except Exception:
            pass
        try:
            self.event_bus.publish("session.state_changed", row)
        except Exception:
            pass

    def publish_runtime_bind(self, **payload) -> None:
        try:
            self.event_bus.publish("session.runtime_bound", dict(payload))
        except Exception:
            pass

    def transition_to_starting(self) -> None:
        self._transition("STARTING")

    def transition_to_running(self) -> None:
        self._transition("RUNNING")

    def transition_to_stopped(self, **payload) -> None:
        self._transition("STOPPED", **payload)

    def transition_to_resetting(self) -> None:
        self._transition("RESETTING")
