from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StopComputation:
    inst_id: str
    current_stop: float
    exchange_stop: float
    desired_stop_mode: str
    active_stop_mode: str


class StopCalculator:
    def build_snapshot(self, state) -> StopComputation:
        return StopComputation(
            inst_id=str(getattr(state, "inst_id", "") or ""),
            current_stop=float(getattr(state, "stop_price", 0.0) or 0.0),
            exchange_stop=float(getattr(state, "exchange_stop_price", 0.0) or 0.0),
            desired_stop_mode=str(getattr(state, "desired_stop_mode", "") or ""),
            active_stop_mode=str(getattr(state, "active_stop_mode", "") or ""),
        )
