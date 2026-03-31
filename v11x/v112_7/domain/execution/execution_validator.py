from __future__ import annotations


class ExecutionValidator:
    def validate_qty(self, qty: float) -> None:
        if float(qty or 0.0) <= 0.0:
            raise ValueError("qty must be > 0")

    def validate_side(self, side: str) -> None:
        if str(side or "").lower() not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
