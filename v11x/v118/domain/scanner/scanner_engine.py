from __future__ import annotations

import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any

from infrastructure.logging.logger_factory import get_engine_logger


class ScannerEngine:
    def __init__(self, *, bot: object) -> None:
        self.bot = bot
        self.runtime = getattr(bot, 'market_scanner', None)
        self.log = get_engine_logger('scanner')

    def initialize_universe(self, symbols: list[str]) -> None:
        if self.runtime is None:
            return None
        self.runtime.initialize_universe(symbols)
        self.log.info('scanner_universe_initialized size=%s', len(symbols), extra={'engine': 'scanner'})
        return None

    def run_chunk(self, chunk_size: int | None = None) -> int:
        if self.runtime is None:
            return 0
        processed = int(self.runtime.run_chunk(chunk_size=chunk_size) or 0)
        self.log.info('scanner_chunk_processed count=%s', processed, extra={'engine': 'scanner'})
        return processed

    def refresh_for_entry(self, inst_id: str, force: bool = False) -> dict:
        if self.runtime is None:
            return {}
        status = self.runtime.refresh_for_entry(inst_id, force=force)
        payload = self._status_to_dict(status)
        self.log.info('scanner_refresh_for_entry inst_id=%s admitted=%s filter=%s', inst_id, payload.get('admitted'), payload.get('filter_type'), extra={'engine': 'scanner'})
        return payload

    def allows_entry(self, inst_id: str) -> tuple[bool, str, dict]:
        if self.runtime is None:
            return False, 'scanner_runtime_missing', {}
        allowed, reason, status = self.runtime.allows_entry(inst_id)
        payload = self._status_to_dict(status)
        self.log.info('scanner_allows_entry inst_id=%s allowed=%s reason=%s', inst_id, allowed, reason, extra={'engine': 'scanner'})
        return bool(allowed), str(reason), payload

    def summary(self) -> dict:
        statuses = []
        if self.runtime is not None:
            statuses = [self._status_to_dict(item) for item in list(getattr(self.runtime, 'status_by_symbol', {}).values())]
        now = time.time()
        ready = sum(1 for item in statuses if not item.get('pending') and not item.get('failed'))
        admitted = sum(1 for item in statuses if item.get('admitted'))
        blocked = sum(1 for item in statuses if not item.get('pending') and not item.get('failed') and not item.get('admitted'))
        failed = sum(1 for item in statuses if item.get('failed'))
        stale = 0
        if self.runtime is not None:
            for item in statuses:
                updated_at = float(item.get('updated_at', 0.0) or 0.0)
                ttl = float(getattr(getattr(self.bot, 'cfg', None), 'scanner_status_ttl_sec', 90) or 90)
                if updated_at > 0.0 and ttl > 0.0 and (now - updated_at) > ttl:
                    stale += 1
        summary = {
            'total': len(statuses),
            'ready': ready,
            'admitted': admitted,
            'blocked': blocked,
            'failed': failed,
            'pending': sum(1 for item in statuses if item.get('pending')),
            'stale': stale,
            'hard_blocked': len(getattr(self.runtime, 'hard_blocked', set()) or set()) if self.runtime is not None else 0,
        }
        self.log.info('scanner_summary=%s', summary, extra={'engine': 'scanner'})
        return summary

    def snapshot(self, inst_id: str | None = None) -> dict:
        if self.runtime is None:
            return {'summary': self.summary(), 'statuses': []}
        if inst_id:
            return self._status_to_dict(self.runtime.get_status(inst_id))
        statuses = [self._status_to_dict(item) for item in list(getattr(self.runtime, 'status_by_symbol', {}).values())]
        return {'summary': self.summary(), 'statuses': statuses}

    def _status_to_dict(self, status: Any) -> dict:
        if status is None:
            return {}
        if is_dataclass(status):
            return asdict(status)
        if hasattr(status, '__dict__'):
            return dict(status.__dict__)
        return {'value': status}
