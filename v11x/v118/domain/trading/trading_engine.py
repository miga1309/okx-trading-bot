from __future__ import annotations

from typing import Any

from infrastructure.logging.logger_factory import get_engine_logger


class TradingEngine:
    def __init__(self, *, bot: object, registry: object | None = None, scanner_engine: object | None = None) -> None:
        self.bot = bot
        self.registry = registry
        self.scanner_engine = scanner_engine
        self.log = get_engine_logger('trading')

    def snapshot(self) -> dict[str, Any]:
        position_count = 0
        if self.registry is not None and hasattr(self.registry, 'open_count'):
            try:
                position_count = int(self.registry.open_count())
            except Exception:
                position_count = 0
        elif hasattr(self.bot, 'position_state'):
            position_count = len(getattr(self.bot, 'position_state', {}) or {})
        payload = {
            'trade_mode': str(getattr(getattr(self.bot, 'cfg', None), 'trade_mode', 'auto') or 'auto'),
            'pending_entries': len(getattr(self.bot, 'pending_entries', {}) or {}),
            'last_scan_cycle_id': int(getattr(self.bot, 'last_scan_cycle_id', 0) or 0),
            'last_signal_funnel': dict(getattr(self.bot, 'last_signal_funnel', {}) or {}),
            'last_scan_candidates': list(getattr(self.bot, 'last_scan_candidates', []) or []),
            'last_near_pass_candidates': list(getattr(self.bot, 'last_near_pass_candidates', []) or []),
            'open_positions': position_count,
        }
        self.log.info('trading_snapshot mode=%s pending=%s open=%s', payload['trade_mode'], payload['pending_entries'], payload['open_positions'], extra={'engine': 'trading'})
        return payload

    def set_trade_mode(self, mode: str) -> str:
        normalized = 'manual' if str(mode).lower() == 'manual' else 'auto'
        cfg = getattr(self.bot, 'cfg', None)
        if cfg is not None:
            cfg.trade_mode = normalized
        self.log.info('trading_mode_changed mode=%s', normalized, extra={'engine': 'trading'})
        return normalized

    def request_manual_entry_approval(self, payload: dict) -> bool:
        fn = getattr(self.bot, 'request_manual_entry_approval', None)
        if callable(fn):
            result = bool(fn(payload))
            self.log.info('manual_entry_approval_requested allowed=%s inst_id=%s', result, str((payload or {}).get('inst_id', '')), extra={'engine': 'trading'})
            return result
        self.log.warning('manual_entry_approval_handler_missing', extra={'engine': 'trading'})
        return False

    def set_manual_entry_decision(self, allow: bool) -> None:
        fn = getattr(self.bot, '_set_manual_entry_decision', None)
        if callable(fn):
            fn(bool(allow))
            self.log.info('manual_entry_decision_set allow=%s', bool(allow), extra={'engine': 'trading'})

    def scanner_gate(self, inst_id: str) -> tuple[bool, str, dict]:
        if self.scanner_engine is None:
            return True, 'scanner_not_bound', {}
        return self.scanner_engine.allows_entry(inst_id)
