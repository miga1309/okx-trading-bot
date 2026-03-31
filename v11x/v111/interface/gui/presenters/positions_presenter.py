from __future__ import annotations


class PositionsPresenter:
    def present(self, snapshot: dict | None) -> dict:
        payload = dict(snapshot or {})
        open_positions = list(payload.get('open_positions', []) or [])
        closed_trades = list(payload.get('closed_trades', []) or [])
        return {
            'open_positions': open_positions,
            'open_count': len(open_positions),
            'closed_trades': closed_trades,
            'closed_count': len(closed_trades),
        }
