from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReconcileReport:
    open_positions: int = 0
    recovered_stops: int = 0
    connectivity_state: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "open_positions": self.open_positions,
            "recovered_stops": self.recovered_stops,
            "connectivity_state": self.connectivity_state,
            "notes": list(self.notes),
        }
