from __future__ import annotations


class BalancePresenter:
    def present(self, snapshot: dict | None) -> dict:
        payload = dict(snapshot or {})
        balance = dict(payload.get('balance', {}) or {})
        history = list(payload.get('balance_history', []) or [])
        return {
            'balance': balance,
            'history_count': len(history),
            'latest_equity': float(balance.get('equity', 0.0) or 0.0),
        }
