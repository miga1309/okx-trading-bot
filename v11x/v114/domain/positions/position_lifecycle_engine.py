from __future__ import annotations

import logging
from typing import Optional

from .close_logic import CloseLogic
from .closed_trades_writer import ClosedTradesWriter
from .manual_actions import ManualActions


class PositionLifecycleEngine:
    def __init__(self, *, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.close_logic = CloseLogic(bot)
        self.manual_actions = ManualActions(bot, registry)
        self.closed_writer = ClosedTradesWriter(bot, registry)
        self.log = logging.getLogger("engine.positions")

    def sync_positions_from_exchange(self) -> None:
        self.log.info("sync_positions_from_exchange_requested", extra={"engine": "positions"})
        return self.bot.sync_positions_from_exchange()

    def close_position(self, state, price: float, reason: str, candles: Optional[list] = None) -> None:
        return self.close_logic.close_position(state, price, reason, candles=candles)

    def finalize_closed_trade(self, state, price: float, reason: str, candles: Optional[list] = None) -> None:
        return self.close_logic.finalize_closed_trade(state, price, reason, candles=candles)

    def save_state(self) -> None:
        self.bot._save_state()

    def load_state(self) -> None:
        self.bot._load_state()

    def snapshot(self) -> dict:
        snap = self.registry.snapshot()
        snap.update({
            "pending_entries": len(getattr(self.bot, "pending_entries", {}) or {}),
            "connectivity_state": str(getattr(self.bot, "exchange_connectivity_state", "") or ""),
        })
        return snap
