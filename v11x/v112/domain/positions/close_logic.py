from __future__ import annotations

import logging
from typing import Optional


class CloseLogic:
    def __init__(self, bot: object) -> None:
        self.bot = bot
        self.log = logging.getLogger("engine.positions")

    def close_position(self, state, price: float, reason: str, candles: Optional[list] = None) -> None:
        self.log.info(
            "close_position_request inst_id=%s reason=%s price=%s",
            getattr(state, "inst_id", ""),
            reason,
            price,
            extra={"engine": "positions"},
        )
        return self.bot.close_position(state, price, reason, candles=candles)

    def finalize_closed_trade(self, state, price: float, reason: str, candles: Optional[list] = None) -> None:
        return self.bot._finalize_closed_trade(state, price, reason, candles=candles)
