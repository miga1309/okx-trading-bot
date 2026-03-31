from __future__ import annotations

import logging

from .equity_tracker import latest_equity_snapshot
from .margin_state import margin_snapshot


class BalanceEngine:
    def __init__(self, *, bot: object) -> None:
        self.bot = bot
        self.gateway = getattr(bot, "gateway", None)
        self.log = logging.getLogger("engine.balance")

    def get_snapshot(self, force: bool = False) -> dict:
        if self.gateway is None:
            return latest_equity_snapshot(self.bot)
        response = self.gateway.get_account_balance(force=force)
        data = list((response or {}).get("data", []) or [])
        details = list((data[0] or {}).get("details", []) or []) if data else []
        usdt_row = next((row for row in details if str(row.get("ccy") or "").upper() == "USDT"), dict(details[0]) if details else {})
        snapshot = {
            "balance": float(usdt_row.get("cashBal", 0.0) or 0.0),
            "available": float(usdt_row.get("availBal", 0.0) or 0.0),
            "used_margin": float(usdt_row.get("frozenBal", 0.0) or 0.0),
            "equity": float(usdt_row.get("eq", 0.0) or 0.0),
        }
        self.bot.latest_balance_snapshot = dict(snapshot)
        self.log.info("balance_snapshot=%s", snapshot, extra={"engine": "balance"})
        return snapshot

    def get_margin_state(self) -> dict:
        return margin_snapshot(self.bot)
