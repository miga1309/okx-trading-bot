from __future__ import annotations


def latest_equity_snapshot(bot: object) -> dict:
    return dict(getattr(bot, "latest_balance_snapshot", {}) or {})
