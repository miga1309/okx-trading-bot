from __future__ import annotations

import logging
from typing import Any


class ManualActions:
    def __init__(self, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.log = logging.getLogger("engine.positions")

    def preview_manual_add_units(self, inst_id: str, extra_units: int = 1) -> dict[str, Any]:
        state = self.registry.get(inst_id)
        if state is None:
            raise KeyError(f"Position not found for {inst_id}")
        extra_units = max(1, int(extra_units or 1))
        current_units = int(getattr(state, "units", 0) or 0)
        base_unit_qty = float(getattr(state, "base_unit_qty", 0.0) or 0.0)
        current_qty = float(getattr(state, "qty", 0.0) or 0.0)
        add_qty = base_unit_qty * extra_units if base_unit_qty > 0 else 0.0
        projected_qty = current_qty + add_qty
        projected_units = current_units + extra_units
        payload = {
            "inst_id": str(getattr(state, "inst_id", inst_id) or inst_id),
            "side": str(getattr(state, "side", "") or ""),
            "current_units": current_units,
            "extra_units": extra_units,
            "projected_units": projected_units,
            "base_unit_qty": base_unit_qty,
            "current_qty": current_qty,
            "add_qty": add_qty,
            "projected_qty": projected_qty,
            "avg_px": float(getattr(state, "avg_px", 0.0) or 0.0),
            "next_pyramid_price": float(getattr(state, "next_pyramid_price", 0.0) or 0.0),
            "stop_price": float(getattr(state, "stop_price", 0.0) or 0.0),
        }
        self.log.info("manual_add_preview=%s", payload, extra={"engine": "positions"})
        return payload
