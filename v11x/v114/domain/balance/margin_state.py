from __future__ import annotations


def margin_snapshot(bot: object) -> dict:
    snap = dict(getattr(bot, "latest_balance_snapshot", {}) or {})
    return {
        "balance": float(snap.get("balance", 0.0) or 0.0),
        "available": float(snap.get("available", 0.0) or 0.0),
        "used_margin": float(snap.get("used_margin", 0.0) or 0.0),
        "equity": float(snap.get("equity", 0.0) or 0.0),
    }
