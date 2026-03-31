from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

KNOWN_PROBLEMATIC = [
    'BREV-USDT-SWAP',
    'ATOM-USDT-SWAP',
    'MINA-USDT-SWAP',
    'LINK-USDT-SWAP',
    'CRO-USDT-SWAP',
    'RAVE-USDT-SWAP',
    'ADA-USDT-SWAP',
]

@dataclass(slots=True)
class ScannerConfig:
    api_key: str = ''
    secret_key: str = ''
    passphrase: str = ''
    flag: str = '1'  # 0=main, 1=demo
    timeframe: str = '15m'
    history_days: int = 7
    output_root: Path = Path('scanner_runs')
    max_symbols: int | None = None
    save_candles: bool = True
    archive_output: bool = True
    enable_liquidity: bool = True
    liquidity_snapshots_per_symbol: int = 4
    liquidity_snapshot_pause_sec: float = 0.20
    orderbook_depth_size: int = 5
    sleep_between_symbols_sec: float = 0.05
    analysis_profile: str = 'balanced'
    candle_data_source: str = 'chart_candles'
    price_data_source: str = 'ticker_last'
    blacklist: List[str] = field(default_factory=lambda: ['USDC-USDT-SWAP'])
    known_problematic: List[str] = field(default_factory=lambda: list(KNOWN_PROBLEMATIC))
    require_private_auth_for_universe: bool = True
