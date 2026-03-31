from __future__ import annotations

import logging

from .execution_validator import ExecutionValidator
from .fill_processor import normalize_fill
from .order_builder import OrderBuilder


class ExecutionEngine:
    def __init__(self, *, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.gateway = getattr(bot, "gateway", None)
        self.validator = ExecutionValidator()
        self.builder = OrderBuilder()
        self.log = logging.getLogger("engine.execution")

    def place_market_order(self, *, inst_id: str, side: str, qty: float, reduce_only: bool = False) -> dict:
        self.validator.validate_qty(qty)
        self.validator.validate_side(side)
        request = self.builder.build_market_order(inst_id=inst_id, side=side, qty=qty, reduce_only=reduce_only)
        self.log.info(
            "place_market_order inst_id=%s side=%s qty=%s reduce_only=%s",
            request.inst_id,
            request.side,
            request.qty,
            request.reduce_only,
            extra={"engine": "execution"},
        )
        if self.gateway is None:
            raise RuntimeError("gateway is not available")
        response = self.gateway.place_market_order(request.inst_id, request.side, request.qty, reduce_only=request.reduce_only)
        return normalize_fill(response)

    def close_position(self, *, inst_id: str, side: str, qty: float) -> dict:
        self.validator.validate_qty(qty)
        self.validator.validate_side(side)
        if self.gateway is None:
            raise RuntimeError("gateway is not available")
        self.log.info("close_position_via_gateway inst_id=%s side=%s qty=%s", inst_id, side, qty, extra={"engine": "execution"})
        response = self.gateway.close_position_by_reduce_only(inst_id, side, qty)
        return normalize_fill(response)

    def reconcile_live_fill(self, inst_id: str, side: str, fallback_price: float, fallback_qty: float) -> tuple[float, float]:
        return self.bot._reconcile_live_fill(inst_id, side, fallback_price, fallback_qty)
