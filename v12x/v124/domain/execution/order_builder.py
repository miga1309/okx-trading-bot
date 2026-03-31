from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderRequest:
    inst_id: str
    side: str
    qty: float
    reduce_only: bool = False
    order_type: str = "market"


class OrderBuilder:
    def build_market_order(self, *, inst_id: str, side: str, qty: float, reduce_only: bool = False) -> OrderRequest:
        return OrderRequest(inst_id=str(inst_id), side=str(side), qty=float(qty), reduce_only=bool(reduce_only), order_type="market")
