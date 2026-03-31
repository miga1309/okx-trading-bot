from __future__ import annotations

import logging
from typing import Iterable


class PositionRegistry:
    def __init__(self, bot: object) -> None:
        self.bot = bot
        self.log = logging.getLogger("engine.positions")

    @property
    def open_positions(self) -> dict:
        return getattr(self.bot, "position_state", {})

    @property
    def closed_trades(self) -> list:
        return getattr(self.bot, "closed_trades", [])

    def open_count(self) -> int:
        return len(self.open_positions)

    def closed_count(self) -> int:
        return len(self.closed_trades)

    def list_open(self) -> list:
        return list(self.open_positions.values())

    def list_closed(self) -> list:
        return list(self.closed_trades)

    def get(self, inst_id: str):
        return self.open_positions.get(str(inst_id or ""))

    def contains(self, inst_id: str) -> bool:
        return self.get(inst_id) is not None

    def snapshot(self) -> dict:
        return {
            "open_positions": self.open_count(),
            "closed_trades": self.closed_count(),
            "symbols": sorted(str(k) for k in self.open_positions.keys()),
        }

    def record_sync(self, event: str, **payload) -> None:
        try:
            self.log.info("%s | %s", event, payload, extra={"engine": "positions"})
        except Exception:
            pass
