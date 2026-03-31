from __future__ import annotations

import argparse
from pathlib import Path

from .collector import MarketCollector
from .config import ScannerConfig
from .env_utils import load_env_file


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Market Scanner v021_3 using authenticated OKX demo SWAP universe')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--demo', action='store_true', help='Use OKX demo mode (default)')
    mode.add_argument('--prod', action='store_true', help='Use OKX main mode')
    p.add_argument('--timeframe', default='15m')
    p.add_argument('--days', type=int, default=7)
    p.add_argument('--max-symbols', type=int, default=None)
    p.add_argument('--snapshots', type=int, default=4)
    p.add_argument('--sleep-symbol', type=float, default=0.05)
    p.add_argument('--sleep-snapshot', type=float, default=0.20)
    p.add_argument('--output-dir', default='scanner_runs')
    p.add_argument('--env-file', default='.env')
    p.add_argument('--profile', type=str, default='balanced', choices=['balanced', 'strict', 'research'])
    p.add_argument('--no-archive', action='store_true')
    p.add_argument('--no-save-candles', action='store_true')
    p.add_argument('--disable-liquidity', action='store_true')
    return p


def main() -> int:
    args = build_parser().parse_args()
    env = load_env_file(args.env_file)
    cfg = ScannerConfig(
        api_key=env.get('OKX_API_KEY', ''),
        secret_key=env.get('OKX_SECRET_KEY', ''),
        passphrase=env.get('OKX_PASSPHRASE', ''),
        flag=env.get('OKX_FLAG', '0' if args.prod else '1'),
        timeframe=args.timeframe,
        history_days=args.days,
        output_root=Path(args.output_dir),
        max_symbols=args.max_symbols,
        save_candles=not args.no_save_candles,
        archive_output=not args.no_archive,
        enable_liquidity=not args.disable_liquidity,
        liquidity_snapshots_per_symbol=max(1, args.snapshots),
        liquidity_snapshot_pause_sec=max(0.0, args.sleep_snapshot),
        sleep_between_symbols_sec=max(0.0, args.sleep_symbol),
        analysis_profile=args.profile,
        candle_data_source='chart_candles',
        price_data_source='ticker_last',
    )
    MarketCollector(cfg).run()
    return 0
