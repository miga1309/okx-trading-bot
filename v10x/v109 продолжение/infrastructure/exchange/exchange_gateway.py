from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExchangeGatewayFacade:
    adapter_name: str = "legacy.okx_gateway.OkxGateway"
    stage: int = 2
    runtime_gateway: Any = field(default=None, repr=False)

    def bind_runtime_gateway(self, runtime_gateway: Any) -> None:
        self.runtime_gateway = runtime_gateway

    def is_bound(self) -> bool:
        return self.runtime_gateway is not None

    def describe(self) -> dict:
        return {"adapter": self.adapter_name, "stage": self.stage, "bound": self.is_bound()}
