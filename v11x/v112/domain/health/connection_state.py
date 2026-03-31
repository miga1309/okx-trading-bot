from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConnectionState:
    state: str
    last_error: str
    components_down: list[str]

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "last_error": self.last_error,
            "components_down": list(self.components_down),
        }
