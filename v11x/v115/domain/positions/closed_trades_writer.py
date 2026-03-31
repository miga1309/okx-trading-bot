from __future__ import annotations

import logging


class ClosedTradesWriter:
    def __init__(self, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.log = logging.getLogger("engine.positions")

    def append_if_missing(self, trade) -> bool:
        trade_id = str(getattr(trade, "trade_id", "") or "")
        inst_id = str(getattr(trade, "inst_id", "") or "")
        time_val = str(getattr(trade, "time", "") or "")
        for existing in self.registry.list_closed():
            if trade_id and str(getattr(existing, "trade_id", "") or "") == trade_id:
                return False
            if not trade_id and inst_id and time_val and str(getattr(existing, "inst_id", "") or "") == inst_id and str(getattr(existing, "time", "") or "") == time_val:
                return False
        self.registry.closed_trades.append(trade)
        self.log.info("closed_trade_registered trade_id=%s inst_id=%s", trade_id, inst_id, extra={"engine": "positions"})
        return True
