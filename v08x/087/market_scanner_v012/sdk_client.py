from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from okx_gateway import OkxGateway
from trade_models import BotConfig
from .bot_universe import is_hidden_instrument
from .time_utils import BAR_TO_SECONDS, compute_window, dt_to_ms


@dataclass(slots=True)
class ApiStats:
    http_requests_total: int = 0
    http_error_count: int = 0
    backoff_events: int = 0


class OkxBotUniverseClient:
    def __init__(self, api_key: str, secret_key: str, passphrase: str, flag: str = '1'):
        cfg = BotConfig(api_key=api_key, secret_key=secret_key, passphrase=passphrase, flag=str(flag))
        self.gateway = OkxGateway(cfg, hidden_checker=is_hidden_instrument)
        self.cfg = cfg
        self.api_stats = ApiStats()
        self.private_api_verified = False
        self.private_api_error: str | None = None

    def verify_private_access(self) -> dict[str, Any]:
        self.api_stats.http_requests_total += 1
        try:
            resp = self.gateway.get_account_balance()
            code = str(resp.get('code', '0'))
            ok = code in {'0', ''}
            self.private_api_verified = ok
            self.private_api_error = None if ok else str(resp.get('msg') or 'private_api_error')
        except Exception as exc:
            self.api_stats.http_error_count += 1
            self.private_api_verified = False
            self.private_api_error = str(exc)
        return {
            'private_api_verified': self.private_api_verified,
            'private_api_error': self.private_api_error,
            'account_mode': 'demo' if str(self.cfg.flag) == '1' else 'main',
        }

    def get_swap_instruments(self, require_private_auth: bool = True) -> list[dict[str, Any]]:
        auth_info = self.verify_private_access()
        if require_private_auth and not auth_info['private_api_verified']:
            raise RuntimeError(f"Private OKX account check failed: {auth_info['private_api_error'] or 'unknown error'}")
        self.api_stats.http_requests_total += 1
        self.gateway.refresh_instruments()
        rows = []
        for inst_id, row in self.gateway.instrument_cache.items():
            if str(inst_id).upper().endswith('-USDT-SWAP') and row.get('state') == 'live':
                rows.append(row)
        return sorted(rows, key=lambda x: str(x.get('instId') or ''))

    def get_orderbook(self, inst_id: str, sz: int = 5) -> dict[str, Any]:
        self.api_stats.http_requests_total += 1
        try:
            resp = self.gateway.market_api.get_orderbook(instId=inst_id, sz=str(sz))
            data = resp.get('data', []) or []
            return data[0] if data else {'bids': [], 'asks': [], 'ts': None}
        except Exception:
            self.api_stats.http_error_count += 1
            self.api_stats.backoff_events += 1
            raise

    def get_history_candles(self, inst_id: str, bar: str, history_days: int) -> list[list[Any]]:
        """Load candles from the same REST endpoint family as the chart view.

        We intentionally use /market/candles (chart candles) instead of
        /market/history-candles so the scanner follows the same OHLCV stream
        the user sees on the exchange chart. Only fully confirmed candles are kept.
        """
        start_dt, end_dt, _ = compute_window(history_days, bar)
        start_ms = dt_to_ms(start_dt)
        end_ms = dt_to_ms(end_dt)
        bar_ms = BAR_TO_SECONDS[bar] * 1000
        after = str(end_ms + bar_ms)
        requests_count = 0
        safe_limit = max(10, math.ceil((history_days * 24 * 60 * 60) / (BAR_TO_SECONDS[bar] * 300)) + 10)
        all_rows: list[list[Any]] = []
        seen_batch_keys: set[tuple[int, int]] = set()
        while True:
            self.api_stats.http_requests_total += 1
            try:
                resp = self.gateway.market_api.get_candlesticks(instId=inst_id, bar=bar, after=after, limit='300')
            except Exception:
                self.api_stats.http_error_count += 1
                self.api_stats.backoff_events += 1
                raise
            batch = resp.get('data', []) or []
            requests_count += 1
            if not batch:
                break
            raw_ts = [int(r[0]) for r in batch if r]
            if not raw_ts:
                break
            batch_key = (min(raw_ts), max(raw_ts))
            if batch_key in seen_batch_keys:
                break
            seen_batch_keys.add(batch_key)
            parsed = []
            for r in batch:
                if len(r) < 6:
                    continue
                ts = int(r[0])
                confirm = str(r[8]) if len(r) > 8 else '1'
                if confirm != '1':
                    continue
                if ts < start_ms or ts >= end_ms:
                    continue
                quote_volume = r[7] if len(r) > 7 else None
                if quote_volume in (None, '', '0', 0):
                    try:
                        quote_volume = float(r[4]) * float(r[5])
                    except Exception:
                        quote_volume = 0
                parsed.append([ts, r[1], r[2], r[3], r[4], r[5], quote_volume])
            all_rows.extend(parsed)
            raw_min_ts = min(raw_ts)
            if raw_min_ts <= start_ms or requests_count >= safe_limit:
                break
            after = str(raw_min_ts)
            time.sleep(0.01)
        unique: dict[int, list[Any]] = {}
        for row in all_rows:
            unique[int(row[0])] = row
        return [unique[k] for k in sorted(unique)]

    def get_universe_source_meta(self) -> dict[str, Any]:
        return {
            'universe_source': 'okx_api_demo_swap',
            'universe_source_notes': 'Loaded from authenticated OKX SWAP instruments using provided API credentials',
            'private_api_verified': self.private_api_verified,
            'private_api_error': self.private_api_error,
            'account_mode': 'demo' if str(self.cfg.flag) == '1' else 'main',
        }

    def get_candle_source_meta(self) -> dict[str, Any]:
        return {
            'candle_data_source': 'chart_candles',
            'price_data_source': 'ticker_last',
            'chart_mode_matched': True,
            'chart_endpoint': '/api/v5/market/candles',
            'chart_endpoint_notes': 'confirmed chart candles only',
            'account_mode': 'demo' if str(self.cfg.flag) == '1' else 'main',
            'private_api_verified': self.private_api_verified,
            'private_api_error': self.private_api_error,
        }
