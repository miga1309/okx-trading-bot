from __future__ import annotations


class HealthPresenter:
    def present(self, snapshot: dict | None) -> dict:
        payload = dict(snapshot or {})
        health = dict(payload.get('health', {}) or {})
        return {
            'engine': str(health.get('engine', '') or ''),
            'connectivity_state': str(health.get('connectivity_state', '') or ''),
            'components': dict(health.get('components', {}) or {}),
            'telegram_worker': str(health.get('telegram_worker', '') or ''),
        }
