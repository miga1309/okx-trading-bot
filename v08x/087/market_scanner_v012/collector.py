from __future__ import annotations

import time
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from . import __version__
from .analyzers import analyze_symbol
from .bot_universe import build_scanner_universe
from .config import ScannerConfig
from .exporters import archive_directory, write_csv, write_json
from .logging_utils import build_logger
from .sdk_client import OkxBotUniverseClient
from .time_utils import compute_window, dt_to_ms, expected_candles, utc_now

class MarketCollector:
    def __init__(self, config: ScannerConfig):
        self.config = config
        self.run_dir = self._prepare_run_dir()
        (self.run_dir / 'candles').mkdir(parents=True, exist_ok=True)
        self.logger = build_logger(self.run_dir / 'collector.log')
        self.client = OkxBotUniverseClient(
            api_key=self.config.api_key,
            secret_key=self.config.secret_key,
            passphrase=self.config.passphrase,
            flag=self.config.flag,
        )

    def _prepare_run_dir(self) -> Path:
        base = Path(self.config.output_root)
        base.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().strftime('%Y%m%d_%H%M%S')
        run_dir = base / f'market_scanner_v021_3_{stamp}'
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _safe_write_json(self, path: Path, payload: dict[str, Any] | list[Any]) -> None:
        try:
            write_json(path, payload)
        except Exception as exc:
            self.logger.error('FINALIZE_WARNING | json write failed | path=%s | error=%s', path, exc)

    def _safe_write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        try:
            write_csv(path, rows)
        except Exception as exc:
            self.logger.error('FINALIZE_WARNING | csv write failed | path=%s | error=%s', path, exc)

    def _collect_liquidity(self, symbol: str) -> tuple[list[dict[str, Any]], str | None]:
        if not self.config.enable_liquidity:
            return [], None
        rows: list[dict[str, Any]] = []
        last_error: str | None = None
        for snap_no in range(1, self.config.liquidity_snapshots_per_symbol + 1):
            try:
                book = self.client.get_orderbook(symbol, sz=self.config.orderbook_depth_size)
                bids = book.get('bids', []) or []
                asks = book.get('asks', []) or []
                if not bids or not asks:
                    rows.append({
                        'symbol': symbol,
                        'snapshot_no': snap_no,
                        'ts': book.get('ts'),
                        'spread_pct': None,
                        'best_bid_size': None,
                        'best_ask_size': None,
                        'top5_bid_size_sum': 0.0,
                        'top5_ask_size_sum': 0.0,
                        'depth_sum': 0.0,
                        'depth_imbalance': None,
                        'mid_price': None,
                    })
                else:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else None
                    spread_pct = ((best_ask - best_bid) / mid) if mid else None
                    bid_sizes = [float(x[1]) for x in bids[: self.config.orderbook_depth_size]]
                    ask_sizes = [float(x[1]) for x in asks[: self.config.orderbook_depth_size]]
                    bid_sum = sum(bid_sizes)
                    ask_sum = sum(ask_sizes)
                    depth_sum = bid_sum + ask_sum
                    imbalance = ((bid_sum - ask_sum) / depth_sum) if depth_sum else None
                    rows.append({
                        'symbol': symbol,
                        'snapshot_no': snap_no,
                        'ts': book.get('ts'),
                        'spread_pct': spread_pct,
                        'best_bid_size': float(bids[0][1]),
                        'best_ask_size': float(asks[0][1]),
                        'top5_bid_size_sum': bid_sum,
                        'top5_ask_size_sum': ask_sum,
                        'depth_sum': depth_sum,
                        'depth_imbalance': imbalance,
                        'mid_price': mid,
                    })
            except Exception as exc:
                last_error = str(exc)
                rows.append({
                    'symbol': symbol,
                    'snapshot_no': snap_no,
                    'ts': None,
                    'spread_pct': None,
                    'best_bid_size': None,
                    'best_ask_size': None,
                    'top5_bid_size_sum': None,
                    'top5_ask_size_sum': None,
                    'depth_sum': None,
                    'depth_imbalance': None,
                    'mid_price': None,
                })
            if snap_no < self.config.liquidity_snapshots_per_symbol and self.config.liquidity_snapshot_pause_sec > 0:
                time.sleep(self.config.liquidity_snapshot_pause_sec)
        return rows, last_error

    def run(self) -> dict[str, Any]:
        started_at = utc_now()
        run_started = perf_counter()
        start_dt, end_dt, has_open_boundary_candle = compute_window(self.config.history_days, self.config.timeframe)
        expected_count = expected_candles(start_dt, end_dt, self.config.timeframe)

        auth_info = self.client.verify_private_access()
        instruments = sorted(self.client.get_swap_instruments(require_private_auth=self.config.require_private_auth_for_universe), key=lambda x: x.get('instId') or '')
        raw_swap_universe = [str(x.get('instId')).upper() for x in instruments if x.get('instId')]
        universe_info = build_scanner_universe(raw_swap_universe, blacklist=self.config.blacklist)
        selected_ids = list(universe_info['analysis_universe'])
        if self.config.max_symbols is not None:
            selected_ids = selected_ids[: self.config.max_symbols]
        instrument_map = {str(x['instId']).upper(): x for x in instruments if x.get('instId')}
        selected = [instrument_map[x] for x in selected_ids if x in instrument_map]

        account_mode = 'demo' if self.config.flag == '1' else 'main'
        print(f"[v021_3] start | account_mode={account_mode} | timeframe={self.config.timeframe} | days={self.config.history_days}")
        print(
            f"[v021_3] source=v086_gateway_logic | candle_source={self.config.candle_data_source} | raw_swap_universe={len(raw_swap_universe)} | "
            f"trade_ready_universe={len(universe_info['trade_ready_universe'])} | "
            f"analysis_universe={len(universe_info['analysis_universe'])} | "
            f"hidden_but_analyzed={len(universe_info['hidden_but_analyzed'])} | selected={len(selected)}"
        )
        if universe_info['hidden_but_analyzed']:
            print(f"[v021_3] hidden pairs opened for scanner: {', '.join(universe_info['hidden_but_analyzed'])}")

        self._safe_write_json(self.run_dir / 'instrument_source.json', {
            'version': __version__,
            'source': 'okx_demo_swap_api',
            'account_mode': account_mode,
            'candle_data_source': self.config.candle_data_source,
            'private_api_verified': auth_info.get('private_api_verified'),
            'private_api_error': auth_info.get('private_api_error'),
            'price_data_source': self.config.price_data_source,
            'chart_mode_matched': True,
            **universe_info,
            **self.client.get_universe_source_meta(),
            'selected': selected_ids,
            'scanner_policy': {
                'hidden_pairs_are_analyzed': True,
                'hidden_pairs_are_not_trade_ready': True,
            },
        })
        self._safe_write_json(self.run_dir / 'excluded_from_trade_ready.json', {
            'hidden_in_bot': universe_info['hidden_in_bot'],
            'excluded_only_by_blacklist': universe_info['excluded_only_by_blacklist'],
            'excluded_from_trade_ready': universe_info['excluded_from_trade_ready'],
        })
        self._safe_write_csv(self.run_dir / 'symbols.csv', instruments)

        summary_rows: list[dict[str, Any]] = []
        market_stats_rows: list[dict[str, Any]] = []
        sparse_rows: list[dict[str, Any]] = []
        risk_rows: list[dict[str, Any]] = []
        request_rows: list[dict[str, Any]] = []
        liquidity_rows_all: list[dict[str, Any]] = []
        failed_symbols: list[str] = []
        symbol_errors: list[dict[str, Any]] = []
        processed_symbols = 0

        hidden_set = set(universe_info['hidden_but_analyzed'])
        trade_ready_set = set(universe_info['trade_ready_universe'])

        for idx, inst in enumerate(selected, start=1):
            symbol = str(inst['instId']).upper()
            print(f"[v021_3] [{idx}/{len(selected)}] {symbol} -> start")
            t0 = perf_counter()
            try:
                candles = self.client.get_history_candles(symbol, self.config.timeframe, self.config.history_days)
                candles_df = pd.DataFrame(candles, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']) if candles else pd.DataFrame(columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'quote_volume'])
                if self.config.save_candles:
                    candle_path = self.run_dir / 'candles' / f"{symbol.replace('/', '_')}_{self.config.timeframe}.csv"
                    candles_df.to_csv(candle_path, index=False)
                request_rows.append({
                    'symbol': symbol,
                    'timeframe': self.config.timeframe,
                    'history_days': self.config.history_days,
                    'expected_candles': expected_count,
                    'actual_candles': len(candles_df),
                    'coverage_pct': round(min(100.0, (len(candles_df) / expected_count) * 100.0), 2) if expected_count else 0.0,
                    'actual_start_ts': int(candles_df['ts'].min()) if not candles_df.empty else None,
                    'actual_end_ts': int(candles_df['ts'].max()) if not candles_df.empty else None,
                    'candle_data_source': self.config.candle_data_source,
                    'price_data_source': self.config.price_data_source,
                    'chart_mode_matched': True,
                })

                liquidity_rows, liquidity_error = self._collect_liquidity(symbol)
                liquidity_rows_all.extend(liquidity_rows)
                if liquidity_error:
                    symbol_errors.append({'symbol': symbol, 'stage': 'liquidity', 'error': liquidity_error})
                analysis = analyze_symbol(symbol, self.config.timeframe, candles_df, expected_count, liquidity_rows=liquidity_rows, profile=self.config.analysis_profile)
                analysis.summary['time_window_start'] = start_dt.isoformat()
                analysis.summary['time_window_end'] = end_dt.isoformat()
                analysis.summary['has_open_boundary_candle'] = has_open_boundary_candle
                analysis.summary['manually_hidden_in_bot'] = symbol in hidden_set
                analysis.summary['trade_ready_in_bot'] = (symbol in trade_ready_set) and analysis.summary.get('final_risk_class') != 'BLACKLIST_CANDIDATE'
                analysis.summary['scanner_included_even_if_hidden'] = symbol in hidden_set
                analysis.summary['risk_origin'] = self._risk_origin(analysis.summary)
                analysis.summary['candle_data_source'] = self.config.candle_data_source
                analysis.summary['price_data_source'] = self.config.price_data_source
                analysis.summary['chart_mode_matched'] = True
                market_stats = dict(analysis.market_stats)
                market_stats['manually_hidden_in_bot'] = symbol in hidden_set
                market_stats['trade_ready_in_bot'] = (symbol in trade_ready_set) and analysis.summary.get('final_risk_class') != 'BLACKLIST_CANDIDATE'
                market_stats['candle_data_source'] = self.config.candle_data_source
                market_stats['price_data_source'] = self.config.price_data_source
                market_stats['chart_mode_matched'] = True
                sparse_stats = dict(analysis.sparse_stats)
                sparse_stats['manually_hidden_in_bot'] = symbol in hidden_set
                sparse_stats['trade_ready_in_bot'] = (symbol in trade_ready_set) and analysis.summary.get('final_risk_class') != 'BLACKLIST_CANDIDATE'
                sparse_stats['candle_data_source'] = self.config.candle_data_source
                sparse_stats['price_data_source'] = self.config.price_data_source
                sparse_stats['chart_mode_matched'] = True
                market_stats_rows.append(market_stats)
                sparse_rows.append(sparse_stats)
                risk_rows.extend(analysis.risk_flags)
                summary_rows.append(analysis.summary)
                processed_symbols += 1
                dt = perf_counter() - t0
                print(f"[v021_3] [{idx}/{len(selected)}] {symbol} -> done | final={analysis.summary.get('final_risk_class')} | struct={analysis.summary.get('structure_risk_class')} | exec={analysis.summary.get('execution_risk_class')} | {dt:.1f}s")
            except Exception as exc:
                failed_symbols.append(symbol)
                symbol_errors.append({'symbol': symbol, 'stage': 'run', 'error': str(exc), 'traceback': traceback.format_exc(limit=3)})
                print(f"[v021_3] [{idx}/{len(selected)}] {symbol} -> ERROR: {exc}")
            if self.config.sleep_between_symbols_sec > 0:
                time.sleep(self.config.sleep_between_symbols_sec)

        summary_rows.sort(key=lambda x: (x['final_risk_class'], -float(x.get('final_market_score') or 0.0), x['symbol']))
        self._safe_write_csv(self.run_dir / 'market_stats.csv', market_stats_rows)
        self._safe_write_csv(self.run_dir / 'sparse_candle_stats.csv', sparse_rows)
        self._safe_write_csv(self.run_dir / 'risk_flags.csv', risk_rows)
        self._safe_write_csv(self.run_dir / 'symbol_request_stats.csv', request_rows)
        self._safe_write_csv(self.run_dir / 'market_summary.csv', summary_rows)
        self._safe_write_csv(self.run_dir / 'symbols_summary.csv', summary_rows)
        if liquidity_rows_all:
            self._safe_write_csv(self.run_dir / 'liquidity_snapshots.csv', liquidity_rows_all)

        safe_symbols = sorted([r['symbol'] for r in summary_rows if r['final_risk_class'] == 'SAFE'])
        caution_symbols = sorted([r['symbol'] for r in summary_rows if r['final_risk_class'] == 'CAUTION'])
        risky_symbols = sorted([r['symbol'] for r in summary_rows if r['final_risk_class'] == 'RISKY'])
        blacklist_symbols = sorted([r['symbol'] for r in summary_rows if r['final_risk_class'] == 'BLACKLIST_CANDIDATE'])
        execution_watchlist = sorted([r['symbol'] for r in summary_rows if bool(r.get('execution_watch'))])
        hidden_rows = [r for r in summary_rows if bool(r.get('manually_hidden_in_bot'))]
        known_problematic_set = {x.upper() for x in self.config.known_problematic}
        known_problematic_rows = [self._decorate_known_problematic(r) for r in summary_rows if str(r.get('symbol', '')).upper() in known_problematic_set]
        false_positive_rows = [self._decorate_false_positive(r) for r in summary_rows if self._is_false_positive_watch(r)]

        snapshot = {
            'meta': {
                'schema_version': 'v017',
                'scanner_name': 'Market Scanner',
                'scanner_version': __version__,
                'collector_version': __version__,
                'generated_at': utc_now().isoformat(),
                'account_mode': account_mode,
                'source': 'okx_demo_swap_api',
                'candle_data_source': self.config.candle_data_source,
                'price_data_source': self.config.price_data_source,
                'chart_mode_matched': True,
                'timeframe': self.config.timeframe,
                'history_days': self.config.history_days,
                'requested_symbols': len(selected),
                'processed_symbols': processed_symbols,
                'failed_symbols_count': len(failed_symbols),
                'liquidity_enabled': self.config.enable_liquidity,
                'liquidity_snapshots_per_symbol': self.config.liquidity_snapshots_per_symbol,
                'trade_ready_universe': len(universe_info['trade_ready_universe']),
                'analysis_universe': len(universe_info['analysis_universe']),
                'hidden_but_analyzed': len(universe_info['hidden_but_analyzed']),
            },
            'safe_symbols': safe_symbols,
            'caution_symbols': caution_symbols,
            'risky_symbols': risky_symbols,
            'blacklist_candidates': blacklist_symbols,
            'execution_watchlist': execution_watchlist,
            'symbol_details': {r['symbol']: r for r in summary_rows},
        }
        self._safe_write_json(self.run_dir / 'market_snapshot.json', snapshot)
        self._safe_write_json(self.run_dir / 'market_filter_snapshot.json', snapshot)
        self._safe_write_json(self.run_dir / 'watchlists.json', {
            'safe_symbols': safe_symbols,
            'caution_symbols': caution_symbols,
            'risky_symbols': risky_symbols,
            'blacklist_candidates': blacklist_symbols,
            'execution_watchlist': execution_watchlist,
            'manually_hidden_in_bot': sorted([r['symbol'] for r in hidden_rows]),
        })
        self._safe_write_json(self.run_dir / 'execution_watchlist.json', {
            'meta': {
                'scanner_version': __version__,
                'schema_version': 'v017',
                'generated_at': utc_now().isoformat(),
                'account_mode': account_mode,
                'source': 'okx_demo_swap_api',
                'candle_data_source': self.config.candle_data_source,
                'price_data_source': self.config.price_data_source,
                'chart_mode_matched': True,
                'timeframe': self.config.timeframe,
                'days': self.config.history_days,
                'profile': self.config.analysis_profile,
            },
            'symbols': execution_watchlist,
            'details': {r['symbol']: {
                'final_risk_class': r['final_risk_class'],
                'structure_risk_class': r['structure_risk_class'],
                'execution_risk_class': r['execution_risk_class'],
                'execution_risk_score': r.get('execution_risk_score'),
                'liquidity_domain_score': r.get('liquidity_domain_score'),
                'spread_mean': r.get('avg_spread_pct'),
                'spread_std': r.get('spread_std'),
                'depth_mean': r.get('avg_depth_sum'),
                'depth_std': r.get('depth_std'),
                'primary_reason': r.get('primary_reason'),
                'risk_reasons': r.get('reason_codes'),
                'manually_hidden_in_bot': bool(r.get('manually_hidden_in_bot')),
                'trade_ready_in_bot': bool(r.get('trade_ready_in_bot')),
            } for r in summary_rows if bool(r.get('execution_watch'))},
        })
        self._safe_write_json(self.run_dir / 'known_problematic_analysis.json', known_problematic_rows)
        self._safe_write_json(self.run_dir / 'hidden_instruments_analysis.json', hidden_rows)
        self._safe_write_json(self.run_dir / 'false_positive_watchlist.json', false_positive_rows)
        self._safe_write_json(self.run_dir / 'symbol_errors.json', symbol_errors)

        best_symbols = sorted(summary_rows, key=lambda x: (-float(x.get('final_market_score') or 0.0), x['symbol']))[:15]
        worst_symbols = sorted(summary_rows, key=lambda x: (float(x.get('final_market_score') or 0.0), x['symbol']))[:15]
        exec_risky = sorted([r for r in summary_rows if bool(r.get('execution_watch'))], key=lambda x: (-(float(x.get('execution_risk_score') or 0.0)), x['symbol']))[:15]
        summary_report = [
            f'Market Scanner v{__version__}',
            f'Account mode: {account_mode}',
            f'Source: v086_gateway_logic',
            f'Candle data source: {self.config.candle_data_source}',
            f'Price data source: {self.config.price_data_source}',
            f'Chart mode matched: True',
            f'Timeframe: {self.config.timeframe}',
            f'History days: {self.config.history_days}',
            f'Profile: {self.config.analysis_profile}',
            f'Raw swap universe: {len(raw_swap_universe)}',
            f'Trade-ready universe (bot): {len(universe_info["trade_ready_universe"])}',
            f'Analysis universe (scanner): {len(universe_info["analysis_universe"])}',
            f'Hidden but analyzed: {len(universe_info["hidden_but_analyzed"])}',
            f'Processed symbols: {processed_symbols}/{len(selected)}',
            f'Final classes: SAFE={len(safe_symbols)} | CAUTION={len(caution_symbols)} | RISKY={len(risky_symbols)} | BLACKLIST={len(blacklist_symbols)}',
            f'Execution watchlist: {len(execution_watchlist)}',
            '',
            'Hidden instruments opened for scanner:',
        ]
        summary_report.extend([f'- {x}' for x in universe_info['hidden_but_analyzed']] or ['- none'])
        summary_report.extend(['', 'Known problematic symbols:'])
        summary_report.extend([f"- {r['symbol']} | final={r['final_risk_class']} | structure={r['structure_risk_class']} | execution={r['execution_risk_class']} | origin={r['risk_origin']} | exec_score={r.get('execution_risk_score')} | primary={r.get('primary_reason') or '-'}" for r in known_problematic_rows] or ['- none'])
        summary_report.extend(['', 'Top healthiest symbols:'])
        summary_report.extend([f"- {r['symbol']} | final={r['final_risk_class']} | structure={r['structure_risk_class']} | execution={r['execution_risk_class']} | score={r.get('final_market_score')}" for r in best_symbols])
        summary_report.extend(['', 'Worst symbols:'])
        summary_report.extend([f"- {r['symbol']} | final={r['final_risk_class']} | structure={r['structure_risk_class']} | execution={r['execution_risk_class']} | score={r.get('final_market_score')} | primary={r.get('primary_reason') or '-'}" for r in worst_symbols])
        summary_report.extend(['', 'Top execution-risk symbols:'])
        summary_report.extend([f"- {r['symbol']} | final={r['final_risk_class']} | execution={r['execution_risk_class']} | exec={r.get('execution_risk_score')} | depth_mean={r.get('avg_depth_sum')} | spread_mean={r.get('avg_spread_pct')} | primary={r.get('primary_reason') or '-'}" for r in exec_risky])
        summary_report.extend(['', 'False-positive watchlist:'])
        summary_report.extend([f"- {r['symbol']} | final={r['final_risk_class']} | execution={r['execution_risk_class']} | exec={r.get('execution_risk_score')} | depth_mean={r.get('avg_depth_sum')} | spread_mean={r.get('avg_spread_pct')}" for r in false_positive_rows] or ['- none'])
        self.run_dir.joinpath('summary_report.txt').write_text('\n'.join(summary_report) + '\n', encoding='utf-8')

        finished_at = utc_now()
        archive_path = None
        if self.config.archive_output:
            archive_path = archive_directory(self.run_dir, f'market_scanner_v021_3_{finished_at.strftime("%Y%m%d_%H%M%S")}.zip')

        run_info = {
            'version': __version__,
            'started_at': started_at.isoformat(),
            'finished_at': finished_at.isoformat(),
            'runtime_sec': round(perf_counter() - run_started, 3),
            'account_mode': account_mode,
            'source': 'okx_demo_swap_api',
            'candle_data_source': self.config.candle_data_source,
            'price_data_source': self.config.price_data_source,
            'chart_mode_matched': True,
            'timeframe': self.config.timeframe,
            'days': self.config.history_days,
            'requested_symbols': len(selected),
            'processed_symbols': processed_symbols,
            'failed_symbols': failed_symbols,
            'failed_symbols_count': len(failed_symbols),
            'status': 'completed' if not failed_symbols else ('partial' if processed_symbols > 0 else 'failed'),
            'time_window_start': start_dt.isoformat(),
            'time_window_end': end_dt.isoformat(),
            'expected_candles_per_symbol': expected_count,
            'has_open_boundary_candle': has_open_boundary_candle,
            'liquidity_enabled': self.config.enable_liquidity,
            'liquidity_snapshots_per_symbol': self.config.liquidity_snapshots_per_symbol,
            'raw_swap_universe': len(raw_swap_universe),
            'trade_ready_universe': len(universe_info['trade_ready_universe']),
            'analysis_universe': len(universe_info['analysis_universe']),
            'hidden_but_analyzed': universe_info['hidden_but_analyzed'],
            'api_stats': {
                'http_requests_total': self.client.api_stats.http_requests_total,
                'http_error_count': self.client.api_stats.http_error_count,
                'backoff_events': self.client.api_stats.backoff_events,
            },
            'errors': symbol_errors,
            'archive_path': str(archive_path) if archive_path else None,
            'output_dir': str(self.run_dir),
        }
        self._safe_write_json(self.run_dir / 'run_info.json', run_info)
        print(f"[v021_3] complete | output={self.run_dir}")
        return {
            'output_dir': str(self.run_dir),
            'archive_path': str(archive_path) if archive_path else None,
            'processed_symbols': processed_symbols,
            'failed_symbols': failed_symbols,
            'run_info': run_info,
        }

    @staticmethod
    def _risk_origin(row: dict[str, Any]) -> str:
        s = row.get('structure_risk_class')
        e = row.get('execution_risk_class')
        f = row.get('final_risk_class')
        if f == 'SAFE':
            return 'healthy'
        if s in {'RISKY', 'BLACKLIST_CANDIDATE'} and e in {'RISKY', 'BLACKLIST_CANDIDATE'}:
            return 'structure+execution'
        if e in {'RISKY', 'BLACKLIST_CANDIDATE'}:
            return 'execution'
        if s in {'RISKY', 'BLACKLIST_CANDIDATE'}:
            return 'structure'
        return 'mixed'

    def _decorate_known_problematic(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload['risk_origin'] = self._risk_origin(payload)
        exec_score = float(payload.get('execution_risk_score') or 0.0)
        payload['execution_focus_strength'] = 'high' if exec_score >= 32 else ('medium' if exec_score >= 16 else 'low')
        payload['execution_strengthened_vs_v009_hint'] = exec_score >= 24 or payload.get('execution_risk_class') in {'RISKY', 'BLACKLIST_CANDIDATE'}
        return payload

    @staticmethod
    def _is_false_positive_watch(row: dict[str, Any]) -> bool:
        exec_score = float(row.get('execution_risk_score') or 0.0)
        avg_depth = float(row.get('avg_depth_sum') or 0.0)
        avg_spread = float(row.get('avg_spread_pct') or 0.0)
        structure_safeish = row.get('structure_risk_class') in {'SAFE', 'CAUTION'} and row.get('candle_viability_class') == 'PASS'
        execution_risky = row.get('execution_risk_class') in {'RISKY', 'BLACKLIST_CANDIDATE'}
        healthy_liquidity = avg_depth >= 900.0 and (avg_spread == 0.0 or avg_spread <= 0.012)
        unconfirmed = not bool(row.get('execution_confirmed'))
        return exec_score >= 20.0 and structure_safeish and execution_risky and healthy_liquidity and unconfirmed

    def _decorate_false_positive(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload['risk_origin'] = self._risk_origin(payload)
        payload['false_positive_reason'] = 'execution_risk_high_while_candles_pass_liquidity_healthy_and_unconfirmed'
        return payload
