from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExchangeGatewayFacade:
    adapter_name: str = "legacy.okx_gateway.OkxGateway"

    def describe(self) -> dict:
        return {"adapter": self.adapter_name, "stage": 1}
