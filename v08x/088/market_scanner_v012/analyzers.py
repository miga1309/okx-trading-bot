from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .time_utils import BAR_TO_SECONDS

@dataclass(slots=True)
class AnalyzerOutput:
    market_stats: dict[str, Any]
    sparse_stats: dict[str, Any]
    risk_flags: list[dict[str, Any]]
    summary: dict[str, Any]


def _severity_by_ratio(value: float, mild: float, severe: float) -> str:
    if value >= severe:
        return 'severe'
    if value >= mild:
        return 'medium'
    return 'low'


def _cluster_count(mask: pd.Series, min_len: int = 2) -> int:
    cnt = cur = 0
    for val in mask.astype(bool).tolist():
        if val:
            cur += 1
        else:
            if cur >= min_len:
                cnt += 1
            cur = 0
    if cur >= min_len:
        cnt += 1
    return cnt


def _max_streak(mask: pd.Series) -> int:
    best = cur = 0
    for val in mask.astype(bool).tolist():
        if val:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def summarize_liquidity(symbol: str, liquidity_rows: list[dict[str, Any]], profile: str = 'balanced') -> tuple[dict[str, Any], list[dict[str, Any]], list[str], float, str | None, str]:
    if not liquidity_rows:
        metrics = {
            'liquidity_enabled': False,
            'liquidity_snapshots': 0,
            'avg_spread_pct': None,
            'max_spread_pct': None,
            'spread_std': None,
            'avg_best_bid_size': None,
            'avg_best_ask_size': None,
            'avg_top5_bid_size_sum': None,
            'avg_top5_ask_size_sum': None,
            'avg_depth_sum': None,
            'depth_min': None,
            'depth_max': None,
            'depth_std': None,
            'depth_cv': None,
            'spread_cv': None,
            'depth_stability_score': None,
            'spread_stability_score': None,
            'liquidity_domain_score': None,
            'execution_risk_score': None,
            'execution_warning_flag': False,
            'execution_watch': False,
            'execution_risk_class': 'SAFE',
        }
        return metrics, [], [], 0.0, None, 'SAFE'

    df = pd.DataFrame(liquidity_rows)
    spread_series = pd.to_numeric(df['spread_pct'], errors='coerce').dropna()
    depth_series = pd.to_numeric(df['depth_sum'], errors='coerce').dropna()
    imb_series = pd.to_numeric(df['depth_imbalance'], errors='coerce').dropna()
    best_bid_series = pd.to_numeric(df['best_bid_size'], errors='coerce').dropna()
    best_ask_series = pd.to_numeric(df['best_ask_size'], errors='coerce').dropna()
    top5_bid_series = pd.to_numeric(df['top5_bid_size_sum'], errors='coerce').dropna()
    top5_ask_series = pd.to_numeric(df['top5_ask_size_sum'], errors='coerce').dropna()

    depth_raw = pd.to_numeric(df['depth_sum'], errors='coerce')
    best_bid_raw = pd.to_numeric(df['best_bid_size'], errors='coerce')
    best_ask_raw = pd.to_numeric(df['best_ask_size'], errors='coerce')
    top5_bid_raw = pd.to_numeric(df['top5_bid_size_sum'], errors='coerce')
    top5_ask_raw = pd.to_numeric(df['top5_ask_size_sum'], errors='coerce')
    spread_raw = pd.to_numeric(df['spread_pct'], errors='coerce')

    avg_spread = float(spread_series.mean()) if not spread_series.empty else None
    max_spread = float(spread_series.max()) if not spread_series.empty else None
    spread_std = float(spread_series.std(ddof=0)) if len(spread_series) > 1 else 0.0
    avg_depth = float(depth_series.mean()) if not depth_series.empty else None
    depth_std = float(depth_series.std(ddof=0)) if len(depth_series) > 1 else 0.0
    depth_min = float(depth_series.min()) if not depth_series.empty else None
    depth_max = float(depth_series.max()) if not depth_series.empty else None
    depth_cv = float(depth_std / avg_depth) if avg_depth and len(depth_series) > 1 else 0.0
    spread_cv = float(spread_std / avg_spread) if avg_spread and len(spread_series) > 1 else 0.0
    avg_best_bid = float(best_bid_series.mean()) if not best_bid_series.empty else None
    avg_best_ask = float(best_ask_series.mean()) if not best_ask_series.empty else None
    avg_top5_bid = float(top5_bid_series.mean()) if not top5_bid_series.empty else None
    avg_top5_ask = float(top5_ask_series.mean()) if not top5_ask_series.empty else None
    best_side_min = min(x for x in [avg_best_bid, avg_best_ask] if x is not None) if any(x is not None for x in [avg_best_bid, avg_best_ask]) else None
    best_side_max = max(x for x in [avg_best_bid, avg_best_ask] if x is not None) if any(x is not None for x in [avg_best_bid, avg_best_ask]) else None
    top5_side_min = min(x for x in [avg_top5_bid, avg_top5_ask] if x is not None) if any(x is not None for x in [avg_top5_bid, avg_top5_ask]) else None
    top5_side_max = max(x for x in [avg_top5_bid, avg_top5_ask] if x is not None) if any(x is not None for x in [avg_top5_bid, avg_top5_ask]) else None
    best_side_skew = float(best_side_max / max(best_side_min or 1e-9, 1e-9)) if best_side_max is not None and best_side_min is not None else 1.0
    top5_side_skew = float(top5_side_max / max(top5_side_min or 1e-9, 1e-9)) if top5_side_max is not None and top5_side_min is not None else 1.0
    best_side_depth_ratio = float(best_side_min / max(avg_depth or 1e-9, 1e-9)) if best_side_min is not None and avg_depth is not None else 0.0
    top5_side_depth_ratio = float(top5_side_min / max(avg_depth or 1e-9, 1e-9)) if top5_side_min is not None and avg_depth is not None else 0.0
    imbalance_flip_rate = 0.0
    if len(imb_series) > 1:
        signs = imb_series.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)).tolist()
        flips = sum(1 for i in range(1, len(signs)) if signs[i] != 0 and signs[i - 1] != 0 and signs[i] != signs[i - 1])
        imbalance_flip_rate = flips / max(1, len(signs) - 1)

    if profile == 'strict':
        depth_warn, depth_severe = 120, 35
        spread_warn, spread_severe = 0.008, 0.025
        cv_warn, cv_severe = 1.0, 1.8
    elif profile == 'research':
        depth_warn, depth_severe = 60, 15
        spread_warn, spread_severe = 0.02, 0.05
        cv_warn, cv_severe = 1.3, 2.0
    else:
        depth_warn, depth_severe = 90, 25
        spread_warn, spread_severe = 0.012, 0.03
        cv_warn, cv_severe = 1.1, 1.9

    valid_snapshots = max(1, int(depth_raw.notna().sum()))
    thin_threshold = max(depth_warn * 0.85, (avg_depth or 0.0) * 0.45)
    collapse_threshold = max(depth_severe, (avg_depth or 0.0) * 0.18) if avg_depth is not None else depth_severe
    best_floor_series = pd.concat([best_bid_raw, best_ask_raw], axis=1).min(axis=1, skipna=True)
    best_ceil_series = pd.concat([best_bid_raw, best_ask_raw], axis=1).max(axis=1, skipna=True)
    top5_floor_series = pd.concat([top5_bid_raw, top5_ask_raw], axis=1).min(axis=1, skipna=True)
    top5_ceil_series = pd.concat([top5_bid_raw, top5_ask_raw], axis=1).max(axis=1, skipna=True)
    best_skew_series = (best_ceil_series / best_floor_series.replace(0, pd.NA)).fillna(0.0)
    top5_skew_series = (top5_ceil_series / top5_floor_series.replace(0, pd.NA)).fillna(0.0)
    thin_mask_series = (depth_raw < thin_threshold).fillna(False)
    collapse_mask_series = (depth_raw < collapse_threshold).fillna(False)
    asym_mask_series = ((best_skew_series >= 6.0) & ((best_floor_series <= max(3.0, (avg_depth or 0.0) * 0.006)) | ((best_floor_series / max(avg_depth or 1e-9, 1e-9)) <= 0.004))).fillna(False)
    top5_weak_mask_series = ((top5_skew_series >= 4.0) & ((top5_floor_series <= max(18.0, (avg_depth or 0.0) * 0.03)) | ((top5_floor_series / max(avg_depth or 1e-9, 1e-9)) <= 0.025))).fillna(False)
    spread_wide_mask_series = (spread_raw > spread_warn).fillna(False)
    persistence_ok_mask = ((depth_raw >= max(depth_warn, (avg_depth or 0.0) * 0.60)) & (best_floor_series >= max(2.0, (avg_depth or 0.0) * 0.004)) & (top5_floor_series >= max(12.0, (avg_depth or 0.0) * 0.020))).fillna(False)
    liquidity_persistence = float(persistence_ok_mask.mean()) if valid_snapshots else 0.0
    anomaly_mask = (thin_mask_series | collapse_mask_series | asym_mask_series | top5_weak_mask_series | spread_wide_mask_series).fillna(False)
    pattern_repeat_score = round(float(anomaly_mask.mean()) * 100.0, 2) if valid_snapshots else 0.0
    conservative_side_depth = min(x for x in [top5_side_min or 0.0, (avg_depth or 0.0) * 0.35] if x is not None) if avg_depth is not None else 0.0
    impact_depth_estimate_01 = round(float(conservative_side_depth), 6)
    impact_depth_estimate_02 = round(float(min((avg_depth or 0.0) * 0.55, (top5_side_min or 0.0) * 1.6 if top5_side_min is not None else (avg_depth or 0.0) * 0.30)), 6)
    high_liquidity_market = bool((avg_depth or 0.0) >= 1200 and (avg_spread or 0.0) <= 0.003 and (depth_cv <= 1.25 if len(depth_series) > 1 else True))
    major_like_market = bool((avg_depth or 0.0) >= 1800 and (avg_spread or 0.0) <= 0.0025 and liquidity_persistence >= 0.50 and (depth_cv <= 1.05 if len(depth_series) > 1 else True))

    reasons: list[str] = []
    risk_flags: list[dict[str, Any]] = []

    def add_flag(flag: str, severity: str, reason: str, code: str) -> None:
        risk_flags.append({'symbol': symbol, 'flag': flag, 'severity': severity, 'reason': reason})
        if code not in reasons:
            reasons.append(code)

    score = 100.0
    if avg_spread is not None:
        score -= min(35.0, avg_spread * 1200.0)
        if avg_spread >= spread_warn:
            add_flag('WIDE_SPREAD', _severity_by_ratio(avg_spread, spread_warn, spread_severe), f'avg_spread_pct={avg_spread:.6f}', 'WIDE_SPREAD')
    if max_spread is not None:
        score -= min(12.0, max(0.0, max_spread - spread_warn * 0.66) * 500.0)
    if avg_depth is not None and avg_depth < depth_warn:
        score -= 12.0 if avg_depth >= depth_severe else 24.0
        add_flag('THIN_BOOK', 'severe' if avg_depth < depth_severe else 'medium', f'avg_depth_sum={avg_depth:.6f}', 'THIN_BOOK')
    if depth_min is not None and avg_depth is not None and depth_min < max(depth_severe, avg_depth * 0.18):
        score -= 8.0
        add_flag('MIN_DEPTH_COLLAPSE', 'severe' if depth_min < depth_severe else 'medium', f'depth_min={depth_min:.6f}, avg_depth={avg_depth:.6f}', 'MIN_DEPTH_COLLAPSE')

    if depth_cv > cv_warn:
        penalty = min(18.0, depth_cv * 12.0)
        if high_liquidity_market:
            penalty *= 0.35
        score -= penalty
        if not high_liquidity_market or depth_cv > cv_severe + 0.5:
            add_flag('DEPTH_INSTABILITY', 'severe' if depth_cv > cv_severe else 'medium', f'depth_cv={depth_cv:.4f}', 'DEPTH_INSTABILITY')
    if spread_cv > 0.6:
        score -= min(10.0, spread_cv * 10.0)

    thin_samples = int(thin_mask_series.sum()) if valid_snapshots else 0
    collapse_samples = int(collapse_mask_series.sum()) if valid_snapshots else 0
    asym_samples = int(asym_mask_series.sum()) if valid_snapshots else 0
    top5_weak_samples = int(top5_weak_mask_series.sum()) if valid_snapshots else 0
    flash_ratio = (depth_max / max(depth_min or 1e-9, 1e-9)) if depth_max is not None and depth_min is not None else 0.0
    flash_liquidity = False
    if len(depth_series) >= 3 and depth_min is not None and avg_depth is not None:
        flash_liquidity = (
            thin_samples >= max(2, len(depth_series) // 2)
            and flash_ratio > 10.0
            and depth_min < max(depth_warn, avg_depth * 0.22)
            and liquidity_persistence < 0.55
        )
        if high_liquidity_market and depth_min > avg_depth * 0.08:
            flash_liquidity = False
    if len(depth_series) >= 3 and thin_samples >= max(2, len(depth_series) // 2):
        penalty = 8.0 if not high_liquidity_market else 3.0
        score -= penalty
        if not high_liquidity_market:
            add_flag('DEPTH_FLASH_PATTERN', 'medium', f'thin_samples={thin_samples}/{len(depth_series)}', 'DEPTH_FLASH_PATTERN')
    if flash_liquidity:
        score -= 14.0
        add_flag('FLASH_LIQUIDITY_RISK', 'severe' if flash_ratio > 20 else 'medium', f'depth_min={depth_min:.6f}, depth_max={depth_max:.6f}, persistence={liquidity_persistence:.2f}', 'FLASH_LIQUIDITY_RISK')
    elif depth_cv > cv_warn and flash_ratio > 8.0 and not high_liquidity_market and liquidity_persistence < 0.60:
        score -= 8.0
        add_flag('FAKE_LIQUIDITY_SPIKE', 'severe' if flash_ratio > 20 else 'medium', f'depth_min={depth_min:.6f}, depth_max={depth_max:.6f}', 'FAKE_LIQUIDITY_SPIKE')

    if imbalance_flip_rate > 0.55:
        penalty = 6.0 if not high_liquidity_market else 2.0
        score -= penalty
        if not high_liquidity_market:
            add_flag('BOOK_INSTABILITY_HIGH', 'medium', f'imbalance_flip_rate={imbalance_flip_rate:.3f}', 'BOOK_INSTABILITY_HIGH')
    if avg_depth is not None and avg_spread is not None and avg_depth < depth_warn and avg_spread > spread_warn:
        score -= 10.0
        add_flag('FAKE_LIQUIDITY_PATTERN', 'medium', f'avg_depth_sum={avg_depth:.6f}, avg_spread_pct={avg_spread:.6f}', 'FAKE_LIQUIDITY_PATTERN')

    asym_thin = False
    if avg_depth is not None and best_side_min is not None and best_side_max is not None:
        asym_thin = best_side_skew >= 6.0 and (best_side_min <= max(3.0, avg_depth * 0.006) or best_side_depth_ratio <= 0.004)
        if asym_thin:
            penalty = 8.0 if not high_liquidity_market else 2.5
            if major_like_market and asym_samples < 2:
                penalty *= 0.35
            score -= penalty
            if (not high_liquidity_market and asym_samples >= 2) or best_side_skew >= 12.0:
                add_flag('ASYMMETRIC_THIN_BOOK', 'severe' if best_side_skew >= 12.0 else 'medium', f'best_side_min={best_side_min:.6f}, best_side_skew={best_side_skew:.3f}, repeats={asym_samples}', 'ASYMMETRIC_THIN_BOOK')

    top5_weak = False
    if avg_depth is not None and top5_side_min is not None and top5_side_max is not None and top5_side_skew >= 4.0:
        top5_weak = top5_side_min <= max(18.0, avg_depth * 0.03) or top5_side_depth_ratio <= 0.025
        if top5_weak:
            penalty = 7.0 if not high_liquidity_market else 2.0
            if major_like_market and top5_weak_samples < 2:
                penalty *= 0.35
            score -= penalty
            if (not high_liquidity_market and top5_weak_samples >= 2) or top5_side_skew >= 7.0:
                add_flag('ASYMMETRIC_DEPTH_WEAKNESS', 'severe' if top5_side_skew >= 7.0 else 'medium', f'top5_side_min={top5_side_min:.6f}, top5_side_skew={top5_side_skew:.3f}, repeats={top5_weak_samples}', 'ASYMMETRIC_DEPTH_WEAKNESS')

    very_low_top_repeats = int((best_floor_series <= 1.5).fillna(False).sum()) if valid_snapshots else 0
    if avg_depth is not None and best_side_min is not None and avg_depth >= 250 and best_side_min <= 1.5:
        penalty = 6.0 if not high_liquidity_market else 1.5
        if major_like_market and very_low_top_repeats < 2:
            penalty *= 0.35
        score -= penalty
        if (not high_liquidity_market and very_low_top_repeats >= 2) or best_side_min <= 0.5:
            add_flag('VERY_LOW_TOP_SIZE', 'severe' if best_side_min <= 0.5 else 'medium', f'best_side_min={best_side_min:.6f}, avg_depth_sum={avg_depth:.6f}, repeats={very_low_top_repeats}', 'VERY_LOW_TOP_SIZE')

    severe_confirmation_hits = 0
    if len(depth_series) >= 3:
        if thin_samples >= max(2, len(depth_series) // 2):
            severe_confirmation_hits += 1
        if collapse_samples >= 2:
            severe_confirmation_hits += 2
        if flash_liquidity:
            severe_confirmation_hits += 2
        if asym_samples >= 2:
            severe_confirmation_hits += 1
        if top5_weak_samples >= 2:
            severe_confirmation_hits += 1
        if very_low_top_repeats >= 2:
            severe_confirmation_hits += 1
    multi_snapshot_confirmed = severe_confirmation_hits
    if multi_snapshot_confirmed >= 4:
        execution_confidence = 'high'
    elif multi_snapshot_confirmed >= 2:
        execution_confidence = 'medium'
    else:
        execution_confidence = 'low'

    score = max(0.0, round(score, 2))
    execution_risk_score = round(100.0 - score, 2)
    depth_stability_score = round(max(0.0, 100.0 - min(100.0, depth_cv * 45.0)), 2)
    spread_stability_score = round(max(0.0, 100.0 - min(100.0, spread_cv * 70.0)), 2)
    severe_codes = {'THIN_BOOK', 'FAKE_LIQUIDITY_PATTERN', 'FLASH_LIQUIDITY_RISK', 'MIN_DEPTH_COLLAPSE', 'ASYMMETRIC_THIN_BOOK', 'ASYMMETRIC_DEPTH_WEAKNESS', 'VERY_LOW_TOP_SIZE'}
    execution_confirmed = multi_snapshot_confirmed >= 2
    execution_watch = execution_risk_score >= 28.0 or any(code in severe_codes for code in reasons)
    execution_warning_flag = execution_risk_score >= 16.0 or bool(reasons)
    if execution_risk_score >= 76 or (execution_confirmed and ('FLASH_LIQUIDITY_RISK' in reasons and 'ASYMMETRIC_THIN_BOOK' in reasons)) or (collapse_samples >= 2 and asym_samples >= 2):
        execution_risk_class = 'BLACKLIST_CANDIDATE'
    elif execution_confirmed and (execution_risk_score >= 28 or collapse_samples >= 2 or flash_liquidity or (asym_samples >= 2 and top5_weak_samples >= 2)):
        execution_risk_class = 'RISKY'
    elif execution_risk_score >= 14 or reasons:
        execution_risk_class = 'CAUTION'
    else:
        execution_risk_class = 'SAFE'
    primary_reason = reasons[0] if reasons else None
    metrics = {
        'liquidity_enabled': True,
        'liquidity_snapshots': len(liquidity_rows),
        'avg_spread_pct': _safe_round(avg_spread, 6),
        'max_spread_pct': _safe_round(max_spread, 6),
        'spread_std': _safe_round(spread_std, 6),
        'avg_best_bid_size': _safe_round(avg_best_bid, 6),
        'avg_best_ask_size': _safe_round(avg_best_ask, 6),
        'avg_top5_bid_size_sum': _safe_round(avg_top5_bid, 6),
        'avg_top5_ask_size_sum': _safe_round(avg_top5_ask, 6),
        'best_side_min': _safe_round(best_side_min, 6),
        'best_side_skew': _safe_round(best_side_skew, 6),
        'best_side_depth_ratio': _safe_round(best_side_depth_ratio, 8),
        'top5_side_min': _safe_round(top5_side_min, 6),
        'top5_side_skew': _safe_round(top5_side_skew, 6),
        'top5_side_depth_ratio': _safe_round(top5_side_depth_ratio, 8),
        'avg_depth_sum': _safe_round(avg_depth, 6),
        'depth_min': _safe_round(depth_min, 6),
        'depth_max': _safe_round(depth_max, 6),
        'depth_std': _safe_round(depth_std, 6),
        'depth_cv': _safe_round(depth_cv, 6),
        'spread_cv': _safe_round(spread_cv, 6),
        'depth_stability_score': depth_stability_score,
        'spread_stability_score': spread_stability_score,
        'liquidity_domain_score': score,
        'liquidity_persistence': round(liquidity_persistence, 6),
        'pattern_repeat_score': pattern_repeat_score,
        'impact_depth_estimate_0_1pct': impact_depth_estimate_01,
        'impact_depth_estimate_0_2pct': impact_depth_estimate_02,
        'execution_risk_score': execution_risk_score,
        'execution_warning_flag': execution_warning_flag,
        'execution_watch': execution_watch,
        'execution_risk_class': execution_risk_class,
        'flash_liquidity_risk': flash_liquidity,
        'execution_multi_snapshot_confirmed': execution_confirmed,
        'execution_confirmation_count': multi_snapshot_confirmed,
        'execution_confidence': execution_confidence,
    }
    return metrics, risk_flags, reasons, execution_risk_score, primary_reason, execution_risk_class


def analyze_symbol(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    expected_count: int,
    liquidity_rows: list[dict[str, Any]] | None = None,
    profile: str = 'balanced',
) -> AnalyzerOutput:
    work = df.copy()
    if work.empty:
        liquidity_metrics, liquidity_flags, liquidity_reasons, _liquidity_score, liquidity_primary_reason, execution_risk_class = summarize_liquidity(symbol, liquidity_rows or [], profile=profile)
        summary = {
            'symbol': symbol,
            'timeframe': timeframe,
            'days': None,
            'candles_count': 0,
            'candles_expected': expected_count,
            'candles_actual': 0,
            'coverage_pct': 0.0,
            'missing_intervals_count': expected_count,
            'max_gap_minutes': None,
            'actual_start_ts': None,
            'actual_end_ts': None,
            'time_window_start': None,
            'time_window_end': None,
            'has_open_boundary_candle': False,
            'avg_range_pct': 0.0,
            'atr_like': 0.0,
            'avg_volume': 0.0,
            'zero_volume_count': 0,
            'zero_volume_ratio': 0.0,
            'micro_range_count': 0,
            'micro_range_ratio': 0.0,
            'combined_sparse_ratio': 0.0,
            'sparse_cluster_count': 0,
            'largest_sparse_cluster': 0,
            'range_spike_count': 0,
            'range_spike_ratio': 0.0,
            'volume_spike_count': 0,
            'volume_spike_ratio': 0.0,
            'spike_cluster_count': 0,
            'candle_health_score': 0.0,
            'structure_stability_score': 0.0,
            'spike_risk_score': 0.0,
            'continuity_score': 0.0,
            'candle_domain_score': 0.0,
            'candle_viability_score': 0.0,
            'candle_viability_class': 'HARD_REJECT',
            'candle_reject_type': 'HARD',
            'filtered_by_candles': True,
            'candle_data_source': 'chart_candles',
        'reject_reason_primary': candle_reject_type,
            'price_data_source': 'ticker_last',
            'chart_mode_matched': True,
            'trap_market_candidate': False,
            'liquidity_domain_score': liquidity_metrics['liquidity_domain_score'],
            'execution_risk_score': liquidity_metrics['execution_risk_score'],
            'final_market_score': 0.0,
            'structure_risk_class': 'BLACKLIST_CANDIDATE',
            'execution_risk_class': execution_risk_class,
            'final_risk_class': 'BLACKLIST_CANDIDATE',
            'risk_class': 'BLACKLIST_CANDIDATE',
            'primary_reason': liquidity_primary_reason or 'NO_CANDLES',
            'secondary_reasons': '|'.join(liquidity_reasons),
            'reason_codes': '|'.join(['NO_CANDLES', *liquidity_reasons]),
            'incomplete_data': True,
            'incomplete_history': True,
            **liquidity_metrics,
        }
        return AnalyzerOutput(
            market_stats={'symbol': symbol, 'timeframe': timeframe, 'candles_count': 0},
            sparse_stats={'symbol': symbol, 'candles_count': 0},
            risk_flags=[{'symbol': symbol, 'flag': 'NO_CANDLES', 'severity': 'severe', 'reason': 'empty dataset'}, *liquidity_flags],
            summary=summary,
        )

    work['open'] = pd.to_numeric(work['open'], errors='coerce').fillna(0.0)
    work['high'] = pd.to_numeric(work['high'], errors='coerce').fillna(0.0)
    work['low'] = pd.to_numeric(work['low'], errors='coerce').fillna(0.0)
    work['close'] = pd.to_numeric(work['close'], errors='coerce').fillna(0.0)
    work['volume'] = pd.to_numeric(work['volume'], errors='coerce').fillna(0.0)
    if 'quote_volume' not in work.columns:
        work['quote_volume'] = work['close'] * work['volume']
    work['quote_volume'] = pd.to_numeric(work['quote_volume'], errors='coerce').fillna(0.0)
    work['range_abs'] = (work['high'] - work['low']).abs()
    work['range_pct'] = (work['range_abs'] / work['close'].replace(0, pd.NA)).fillna(0.0)
    work['body_abs'] = (work['close'] - work['open']).abs()
    work['body_noise_ratio'] = (work['body_abs'] / work['range_abs'].replace(0, pd.NA)).fillna(0.0)
    work['close_position_ratio'] = ((work['close'] - work['low']) / work['range_abs'].replace(0, pd.NA)).fillna(0.5)
    work['ret_abs'] = work['close'].pct_change().abs().fillna(0.0)

    avg_range_abs = float(work['range_abs'].mean()) if len(work) else 0.0
    avg_range_pct = float(work['range_pct'].mean()) if len(work) else 0.0
    median_range_abs = float(work['range_abs'].median()) if len(work) else 0.0
    median_volume = float(work['volume'].median()) if len(work) else 0.0
    atr_like = float(work['range_abs'].rolling(20, min_periods=1).mean().iloc[-1]) if len(work) else 0.0

    zero_volume_mask = work['volume'] <= 0
    micro_range_threshold = max(median_range_abs * 0.10, 1e-12)
    micro_range_mask = work['range_abs'] <= micro_range_threshold
    combined_sparse_mask = zero_volume_mask | micro_range_mask
    range_spike_threshold = max(median_range_abs * 3.0, 1e-12)
    volume_spike_threshold = max(median_volume * 5.0, 1e-12)
    range_spike_mask = work['range_abs'] >= range_spike_threshold
    volume_spike_mask = work['volume'] >= volume_spike_threshold
    gap_like_mask = work['ret_abs'] >= max(float(work['ret_abs'].median()) * 4.0, 0.01)
    wick_instability_score = float(((1.0 - work['body_noise_ratio']).clip(lower=0.0, upper=1.0)).mean() * 100.0)
    close_position_instability = float((work['close_position_ratio'] - 0.5).abs().mean() * 200.0)
    candle_body_noise_ratio = float(work['body_noise_ratio'].mean())
    abnormal_return_cluster_count = _cluster_count(gap_like_mask)

    candle_count = int(len(work))
    actual_start_ts = int(work['ts'].min()) if candle_count else None
    actual_end_ts = int(work['ts'].max()) if candle_count else None

    bar_ms = BAR_TO_SECONDS[timeframe] * 1000
    missing_intervals_count = 0
    max_gap_minutes = 0
    if candle_count >= 2:
        deltas = work['ts'].sort_values().diff().dropna()
        missing_steps = ((deltas / bar_ms).round().astype(int) - 1).clip(lower=0)
        missing_intervals_count = int(missing_steps.sum())
        max_gap_minutes = int(((deltas.max() - bar_ms) / 60000) if deltas.max() > bar_ms else 0)

    coverage_pct = round(min(100.0, (candle_count / expected_count) * 100.0), 2) if expected_count > 0 else 0.0

    zero_volume_ratio = float(zero_volume_mask.mean()) if candle_count else 0.0
    micro_range_ratio = float(micro_range_mask.mean()) if candle_count else 0.0
    combined_sparse_ratio = float(combined_sparse_mask.mean()) if candle_count else 0.0
    range_spike_ratio = float(range_spike_mask.mean()) if candle_count else 0.0
    volume_spike_ratio = float(volume_spike_mask.mean()) if candle_count else 0.0
    sparse_cluster_count = _cluster_count(combined_sparse_mask)
    spike_cluster_count = _cluster_count(range_spike_mask | volume_spike_mask)
    gap_like_move_ratio = float(gap_like_mask.mean()) if candle_count else 0.0

    candle_health_score = 100.0
    candle_health_score -= min(34.0, zero_volume_ratio * 90.0)
    candle_health_score -= min(20.0, micro_range_ratio * 60.0)
    candle_health_score -= min(24.0, combined_sparse_ratio * 85.0)
    candle_health_score -= min(8.0, gap_like_move_ratio * 50.0)

    structure_stability_score = 100.0
    structure_stability_score -= min(22.0, sparse_cluster_count * 3.0)
    structure_stability_score -= min(18.0, _max_streak(combined_sparse_mask) * 1.7)
    structure_stability_score -= min(18.0, (missing_intervals_count / max(expected_count, 1)) * 180.0)
    structure_stability_score -= min(8.0, abnormal_return_cluster_count * 2.0)

    spike_penalty = 0.0
    spike_penalty += min(12.0, range_spike_ratio * 100.0)
    spike_penalty += min(12.0, volume_spike_ratio * 70.0)
    spike_penalty += min(10.0, spike_cluster_count * 2.0)
    if combined_sparse_ratio >= 0.08 and (range_spike_ratio + volume_spike_ratio) >= 0.10:
        spike_penalty += 8.0
    spike_risk_score = max(0.0, 100.0 - spike_penalty)

    continuity_score = max(0.0, 100.0 - min(30.0, (missing_intervals_count / max(expected_count, 1)) * 260.0))
    candle_domain_score = round(
        candle_health_score * 0.40
        + structure_stability_score * 0.24
        + spike_risk_score * 0.18
        + continuity_score * 0.10
        + max(0.0, 100.0 - min(18.0, gap_like_move_ratio * 120.0 + close_position_instability * 0.08)) * 0.08,
        2,
    )

    reason_codes: list[str] = []
    risk_flags: list[dict[str, Any]] = []

    def add_flag(flag: str, severity: str, reason: str, code: str) -> None:
        risk_flags.append({'symbol': symbol, 'flag': flag, 'severity': severity, 'reason': reason})
        if code not in reason_codes:
            reason_codes.append(code)

    if zero_volume_ratio >= 0.12:
        sev = _severity_by_ratio(zero_volume_ratio, 0.12, 0.28)
        add_flag('ZERO_VOLUME', sev, f'zero_volume_ratio={zero_volume_ratio:.4f}', 'HIGH_ZERO_VOLUME_RATIO')
    if micro_range_ratio >= 0.16:
        sev = _severity_by_ratio(micro_range_ratio, 0.16, 0.33)
        add_flag('MICRO_RANGE', sev, f'micro_range_ratio={micro_range_ratio:.4f}', 'MICRO_RANGE_DOMINANCE')
    if combined_sparse_ratio >= 0.18 or sparse_cluster_count >= 4:
        sev = 'severe' if combined_sparse_ratio >= 0.30 else 'medium'
        add_flag('SPARSE_STRUCTURE', sev, f'combined_sparse_ratio={combined_sparse_ratio:.4f}, sparse_clusters={sparse_cluster_count}', 'SPARSE_CLUSTERS')
    if (range_spike_ratio >= 0.05 or volume_spike_ratio >= 0.15 or spike_cluster_count >= 4):
        ratio_sum = range_spike_ratio + volume_spike_ratio
        sev = 'severe' if ratio_sum >= 0.22 and combined_sparse_ratio >= 0.08 else 'medium'
        add_flag('VOLATILITY_SPIKES', sev, f'range_spike_ratio={range_spike_ratio:.4f}, volume_spike_ratio={volume_spike_ratio:.4f}, spike_clusters={spike_cluster_count}', 'SEVERE_SPIKE_CLUSTERS' if sev == 'severe' else 'ELEVATED_SPIKE_ACTIVITY')
    if missing_intervals_count > 0:
        add_flag('INCOMPLETE_HISTORY', 'medium' if missing_intervals_count < 5 else 'severe', f'missing_intervals_count={missing_intervals_count}', 'LOW_CANDLE_CONTINUITY')
    if gap_like_move_ratio >= 0.04 or abnormal_return_cluster_count >= 2:
        add_flag('ABNORMAL_RETURN_CLUSTERS', 'medium' if gap_like_move_ratio < 0.08 else 'severe', f'gap_like_move_ratio={gap_like_move_ratio:.4f}, clusters={abnormal_return_cluster_count}', 'ABNORMAL_RETURN_CLUSTERS')

    avg_quote_volume_usdt = float(work['quote_volume'].mean()) if candle_count else 0.0
    median_quote_volume_usdt = float(work['quote_volume'].median()) if candle_count else 0.0
    if candle_count:
        low_quote_volume_mask = (
            (work['quote_volume'] <= 0)
            | ((median_quote_volume_usdt > 0) & (work['quote_volume'] < median_quote_volume_usdt * 0.25))
            | (work['quote_volume'] < 5000.0)
        )
        low_quote_volume_ratio = float(low_quote_volume_mask.mean())
        quote_volume_continuity_score = round(max(0.0, 100.0 - low_quote_volume_ratio * 100.0), 2)
    else:
        low_quote_volume_ratio = 1.0
        quote_volume_continuity_score = 0.0

    if median_quote_volume_usdt < 5000.0 or low_quote_volume_ratio >= 0.70:
        volume_quality_class = 'LOW'
    elif median_quote_volume_usdt < 25000.0 or low_quote_volume_ratio >= 0.40:
        volume_quality_class = 'MIXED'
    else:
        volume_quality_class = 'GOOD'

    if volume_quality_class == 'LOW':
        add_flag('LOW_QUOTE_VOLUME', 'severe' if median_quote_volume_usdt < 5000.0 else 'medium', f'median_quote_volume_usdt={median_quote_volume_usdt:.2f}, low_ratio={low_quote_volume_ratio:.4f}', 'LOW_QUOTE_VOLUME_USDT')

    liquidity_metrics, liquidity_flags, liquidity_reasons, execution_risk_score, liquidity_primary_reason, execution_risk_class = summarize_liquidity(symbol, liquidity_rows or [], profile=profile)
    risk_flags.extend(liquidity_flags)
    for code in liquidity_reasons:
        if code not in reason_codes:
            reason_codes.append(code)

    liquidity_domain_score = liquidity_metrics['liquidity_domain_score'] if liquidity_metrics['liquidity_domain_score'] is not None else 100.0
    final_market_score = round(candle_domain_score * 0.58 + liquidity_domain_score * 0.42, 2)

    largest_sparse_cluster = _max_streak(combined_sparse_mask)
    severe_candle = combined_sparse_ratio >= 0.42 or zero_volume_ratio >= 0.46 or candle_domain_score < 34
    candle_viability_score = round(
        max(
            0.0,
            candle_domain_score
            - min(20.0, combined_sparse_ratio * 30.0)
            - min(12.0, zero_volume_ratio * 18.0)
            - min(16.0, largest_sparse_cluster * 0.35),
        ),
        2,
    )
    dead_reject_by_candles = bool(
        combined_sparse_ratio >= 0.45
        or zero_volume_ratio >= 0.35
        or (largest_sparse_cluster >= 20 and combined_sparse_ratio >= 0.30)
        or candle_viability_score <= 25.0
        or (combined_sparse_ratio >= 0.40 and zero_volume_ratio >= 0.25)
        or (volume_quality_class == 'LOW' and combined_sparse_ratio >= 0.36 and zero_volume_ratio >= 0.24)
    )
    spike_dead_reject_by_candles = bool(
        not dead_reject_by_candles and (
            (
                candle_viability_score < 52.0
                and combined_sparse_ratio >= 0.18
                and zero_volume_ratio >= 0.12
                and (range_spike_ratio >= 0.16 or volume_spike_ratio >= 0.22)
            )
            or (
                combined_sparse_ratio >= 0.22
                and zero_volume_ratio >= 0.10
                and spike_cluster_count >= 3
                and abnormal_return_cluster_count >= 8
            )
            or (
                largest_sparse_cluster >= 8
                and combined_sparse_ratio >= 0.16
                and (range_spike_ratio >= 0.18 or gap_like_move_ratio >= 0.10)
            )
            or (
                volume_quality_class == 'LOW'
                and combined_sparse_ratio >= 0.12
                and zero_volume_ratio >= 0.08
                and (range_spike_ratio >= 0.12 or volume_spike_ratio >= 0.18)
            )
        )
    )
    saw_reject_by_candles = bool(
        not dead_reject_by_candles and not spike_dead_reject_by_candles and (
            (
                candle_body_noise_ratio >= 0.58
                and close_position_instability >= 68.0
                and combined_sparse_ratio < 0.12
                and zero_volume_ratio < 0.06
                and range_spike_ratio >= 0.12
                and volume_quality_class != 'LOW'
            )
            or (
                wick_instability_score >= 78.0
                and candle_body_noise_ratio >= 0.52
                and gap_like_move_ratio >= 0.09
                and combined_sparse_ratio < 0.14
                and zero_volume_ratio < 0.08
                and volume_quality_class != 'LOW'
            )
            or (
                candle_body_noise_ratio >= 0.60
                and close_position_instability >= 70.0
                and gap_like_move_ratio >= 0.10
                and abnormal_return_cluster_count >= 14
                and volume_quality_class == 'GOOD'
            )
        )
    )
    unstable_warning_by_candles = bool(
        not dead_reject_by_candles and not spike_dead_reject_by_candles and not saw_reject_by_candles and (
            (range_spike_ratio >= 0.18 and volume_spike_ratio >= 0.18)
            or (gap_like_move_ratio >= 0.10 and abnormal_return_cluster_count >= 8)
            or (spike_cluster_count >= 4 and abnormal_return_cluster_count >= 10)
            or (candle_body_noise_ratio >= 0.40 and close_position_instability >= 54.0 and (range_spike_ratio >= 0.10 or gap_like_move_ratio >= 0.08))
            or (combined_sparse_ratio >= 0.08 and zero_volume_ratio >= 0.04 and candle_viability_score < 78.0)
            or (volume_quality_class in {'LOW', 'MIXED'} and range_spike_ratio >= 0.10 and volume_spike_ratio >= 0.12 and candle_viability_score < 82.0)
        )
    )
    filtered_by_candles = dead_reject_by_candles or spike_dead_reject_by_candles or saw_reject_by_candles
    if dead_reject_by_candles:
        structure_risk_class = 'BLACKLIST_CANDIDATE'
        candle_viability_class = 'DEAD_REJECT'
        candle_reject_type = 'DEAD'
        torn_reject_level = 'NONE'
        market_structure_class = 'DEAD'
    elif spike_dead_reject_by_candles:
        structure_risk_class = 'BLACKLIST_CANDIDATE'
        candle_viability_class = 'SPIKE_DEAD_REJECT'
        candle_reject_type = 'SPIKE_DEAD'
        torn_reject_level = 'NONE'
        market_structure_class = 'SPIKE_DEAD'
    elif saw_reject_by_candles:
        structure_risk_class = 'BLACKLIST_CANDIDATE'
        candle_viability_class = 'SAW_REJECT'
        candle_reject_type = 'SAW'
        torn_reject_level = 'NONE'
        market_structure_class = 'SAW'
    elif unstable_warning_by_candles:
        structure_risk_class = 'CAUTION'
        candle_viability_class = 'UNSTABLE_WARNING'
        candle_reject_type = 'UNSTABLE'
        torn_reject_level = 'NONE'
        market_structure_class = 'UNSTABLE'
    else:
        structure_risk_class = 'SAFE'
        candle_viability_class = 'PASS'
        candle_reject_type = 'NONE'
        torn_reject_level = 'NONE'
        market_structure_class = 'PASS'

    execution_confirmed = bool(liquidity_metrics.get('execution_multi_snapshot_confirmed'))
    execution_confidence = liquidity_metrics.get('execution_confidence')
    avg_depth_sum = float(liquidity_metrics.get('avg_depth_sum') or 0.0)
    avg_spread_pct = float(liquidity_metrics.get('avg_spread_pct') or 0.0)
    liquidity_persistence = float(liquidity_metrics.get('liquidity_persistence') or 0.0)
    major_like_market = avg_depth_sum >= 1800.0 and (avg_spread_pct == 0.0 or avg_spread_pct <= 0.0025) and liquidity_persistence >= 0.50

    execution_risk_score_raw = float(liquidity_metrics.get('execution_risk_score') or 0.0)
    if candle_viability_class == 'PASS' and major_like_market and execution_risk_class in {'RISKY', 'BLACKLIST_CANDIDATE'} and execution_risk_score_raw < 70.0:
        execution_risk_class = 'CAUTION'
    elif candle_viability_class == 'PASS' and not execution_confirmed and execution_risk_class in {'RISKY', 'BLACKLIST_CANDIDATE'} and execution_risk_score_raw < 50.0:
        execution_risk_class = 'CAUTION'
    elif candle_viability_class == 'PASS' and execution_risk_class == 'BLACKLIST_CANDIDATE' and execution_risk_score_raw < 84.0:
        execution_risk_class = 'RISKY'
    elif candle_viability_class == 'UNSTABLE_WARNING' and major_like_market and execution_risk_class == 'BLACKLIST_CANDIDATE' and execution_risk_score_raw < 76.0:
        execution_risk_class = 'RISKY'
    if execution_risk_class == 'SAFE':
        execution_risk_score = min(execution_risk_score, 13.99)
    elif execution_risk_class == 'CAUTION':
        execution_risk_score = min(max(execution_risk_score, 14.0), 27.99)
    elif execution_risk_class == 'RISKY':
        execution_risk_score = min(max(execution_risk_score, 28.0), 75.99)
    else:
        execution_risk_score = max(execution_risk_score, 76.0)
    liquidity_metrics['execution_risk_score'] = execution_risk_score
    liquidity_metrics['execution_risk_class'] = execution_risk_class
    extreme_execution_case = (execution_risk_class == 'BLACKLIST_CANDIDATE' and execution_risk_score >= 84.0 and execution_confirmed and not major_like_market)
    trap_market_candidate = bool(
        candle_viability_class in {'PASS', 'UNSTABLE_WARNING'}
        and execution_confirmed
        and not major_like_market
        and (
            (range_spike_ratio >= 0.22 and volume_spike_ratio >= 0.24 and gap_like_move_ratio >= 0.12)
            or (spike_cluster_count >= 5 and abnormal_return_cluster_count >= 14 and gap_like_move_ratio >= 0.10)
        )
        and execution_risk_class in {'RISKY', 'BLACKLIST_CANDIDATE'}
        and execution_risk_score >= 42.0
    )

    final_risk_class = 'SAFE'
    if dead_reject_by_candles or spike_dead_reject_by_candles or saw_reject_by_candles:
        final_risk_class = 'BLACKLIST_CANDIDATE'
    elif extreme_execution_case:
        final_risk_class = 'BLACKLIST_CANDIDATE'
    elif unstable_warning_by_candles:
        final_risk_class = 'RISKY' if execution_risk_class in {'RISKY', 'BLACKLIST_CANDIDATE'} or trap_market_candidate or final_market_score < 70 else 'CAUTION'
    elif execution_risk_class in {'RISKY', 'BLACKLIST_CANDIDATE'} and (execution_confirmed or execution_risk_score >= 32.0):
        final_risk_class = 'RISKY'
    elif execution_risk_class == 'CAUTION' or final_market_score < 70:
        final_risk_class = 'CAUTION'

    if major_like_market and candle_viability_class == 'PASS' and final_risk_class == 'BLACKLIST_CANDIDATE':
        final_risk_class = 'CAUTION'
    if major_like_market and candle_viability_class == 'PASS' and final_risk_class == 'RISKY' and execution_risk_score < 36.0:
        final_risk_class = 'CAUTION'

    if final_risk_class == 'SAFE':
        primary_reason = 'HEALTHY_MARKET'
        secondary_reasons = [r for r in reason_codes[:4]]
    else:
        primary_reason = reason_codes[0] if reason_codes else (liquidity_primary_reason or ('MODERATE_VOLATILITY' if final_risk_class == 'CAUTION' else 'UNCLASSIFIED_RISK'))
        secondary_reasons = [r for r in reason_codes[1:6]]

    market_stats = {
        'symbol': symbol,
        'timeframe': timeframe,
        'candles_count': candle_count,
        'period_start_ts': actual_start_ts,
        'period_end_ts': actual_end_ts,
        'avg_range_abs': round(avg_range_abs, 10),
        'median_range_abs': round(float(median_range_abs), 10),
        'avg_range_pct': round(avg_range_pct, 6),
        'median_range_pct': round(float(work['range_pct'].median()) if candle_count else 0.0, 6),
        'atr_like': round(atr_like, 10),
        'avg_volume': round(float(work['volume'].mean()) if candle_count else 0.0, 6),
        'median_volume': round(float(median_volume), 6),
        'avg_quote_volume_usdt': round(float(avg_quote_volume_usdt), 2),
        'median_quote_volume_usdt': round(float(median_quote_volume_usdt), 2),
        'low_quote_volume_ratio': round(float(low_quote_volume_ratio), 6),
        'quote_volume_continuity_score': round(float(quote_volume_continuity_score), 2),
        'volume_quality_class': volume_quality_class,
        'max_range_abs': round(float(work['range_abs'].max()) if candle_count else 0.0, 10),
        'max_range_pct': round(float(work['range_pct'].max()) if candle_count else 0.0, 6),
        'max_volume': round(float(work['volume'].max()) if candle_count else 0.0, 6),
        'range_spike_count': int(range_spike_mask.sum()),
        'range_spike_ratio': round(range_spike_ratio, 6),
        'volume_spike_count': int(volume_spike_mask.sum()),
        'volume_spike_ratio': round(volume_spike_ratio, 6),
        'spike_cluster_count': spike_cluster_count,
        'gap_like_move_ratio': round(gap_like_move_ratio, 6),
        'wick_instability_score': round(wick_instability_score, 2),
        'close_position_instability': round(close_position_instability, 2),
        'candle_body_noise_ratio': round(candle_body_noise_ratio, 6),
        'abnormal_return_cluster_count': abnormal_return_cluster_count,
        'candle_viability_score': candle_viability_score,
        'candle_viability_class': candle_viability_class,
        'candle_reject_type': candle_reject_type,
        'torn_reject_level': torn_reject_level,
        'market_structure_class': market_structure_class,
        'filtered_by_candles': filtered_by_candles,
        'candle_data_source': 'chart_candles',
        'reject_reason_primary': candle_reject_type,
        'price_data_source': 'ticker_last',
        'chart_mode_matched': True,
        'trap_market_candidate': trap_market_candidate,
        'liquidity_domain_score': liquidity_domain_score,
        'execution_risk_score': execution_risk_score,
        'structure_risk_class': structure_risk_class,
        'execution_risk_class': execution_risk_class,
        'final_risk_class': final_risk_class,
        'execution_confirmed': bool(liquidity_metrics.get('execution_multi_snapshot_confirmed')),
        'execution_confidence': liquidity_metrics.get('execution_confidence'),
    }
    sparse_stats = {
        'symbol': symbol,
        'candles_count': candle_count,
        'zero_volume_candles': int(zero_volume_mask.sum()),
        'zero_volume_ratio': round(zero_volume_ratio, 6),
        'micro_range_candles': int(micro_range_mask.sum()),
        'micro_range_ratio': round(micro_range_ratio, 6),
        'combined_sparse_candles': int(combined_sparse_mask.sum()),
        'combined_sparse_ratio': round(combined_sparse_ratio, 6),
        'sparse_cluster_count': sparse_cluster_count,
        'largest_sparse_cluster': largest_sparse_cluster,
        'max_zero_volume_streak': _max_streak(zero_volume_mask),
        'max_micro_range_streak': _max_streak(micro_range_mask),
    }
    summary = {
        'symbol': symbol,
        'timeframe': timeframe,
        'days': None,
        'candles_count': candle_count,
        'candles_expected': expected_count,
        'candles_actual': candle_count,
        'coverage_pct': coverage_pct,
        'missing_intervals_count': missing_intervals_count,
        'max_gap_minutes': max_gap_minutes,
        'actual_start_ts': actual_start_ts,
        'actual_end_ts': actual_end_ts,
        'time_window_start': None,
        'time_window_end': None,
        'has_open_boundary_candle': False,
        'avg_range_pct': round(avg_range_pct, 6),
        'atr_like': round(atr_like, 10),
        'avg_volume': round(float(work['volume'].mean()) if candle_count else 0.0, 6),
        'avg_quote_volume_usdt': round(float(avg_quote_volume_usdt), 2),
        'median_quote_volume_usdt': round(float(median_quote_volume_usdt), 2),
        'low_quote_volume_ratio': round(float(low_quote_volume_ratio), 6),
        'quote_volume_continuity_score': round(float(quote_volume_continuity_score), 2),
        'volume_quality_class': volume_quality_class,
        'zero_volume_count': int(zero_volume_mask.sum()),
        'zero_volume_ratio': round(zero_volume_ratio, 6),
        'micro_range_count': int(micro_range_mask.sum()),
        'micro_range_ratio': round(micro_range_ratio, 6),
        'combined_sparse_ratio': round(combined_sparse_ratio, 6),
        'sparse_cluster_count': sparse_cluster_count,
        'largest_sparse_cluster': largest_sparse_cluster,
        'range_spike_count': int(range_spike_mask.sum()),
        'range_spike_ratio': round(range_spike_ratio, 6),
        'volume_spike_count': int(volume_spike_mask.sum()),
        'volume_spike_ratio': round(volume_spike_ratio, 6),
        'spike_cluster_count': spike_cluster_count,
        'gap_like_move_ratio': round(gap_like_move_ratio, 6),
        'wick_instability_score': round(wick_instability_score, 2),
        'close_position_instability': round(close_position_instability, 2),
        'candle_body_noise_ratio': round(candle_body_noise_ratio, 6),
        'abnormal_return_cluster_count': abnormal_return_cluster_count,
        'candle_health_score': round(candle_health_score, 2),
        'structure_stability_score': round(structure_stability_score, 2),
        'spike_risk_score': round(spike_risk_score, 2),
        'continuity_score': round(continuity_score, 2),
        'candle_domain_score': candle_domain_score,
        'candle_viability_score': candle_viability_score,
        'candle_viability_class': candle_viability_class,
        'candle_reject_type': candle_reject_type,
        'torn_reject_level': torn_reject_level,
        'market_structure_class': market_structure_class,
        'filtered_by_candles': filtered_by_candles,
        'candle_data_source': 'chart_candles',
        'reject_reason_primary': candle_reject_type,
        'price_data_source': 'ticker_last',
        'chart_mode_matched': True,
        'trap_market_candidate': trap_market_candidate,
        'liquidity_domain_score': liquidity_domain_score,
        'execution_risk_score': execution_risk_score,
        'final_market_score': final_market_score,
        'structure_risk_class': structure_risk_class,
        'execution_risk_class': execution_risk_class,
        'final_risk_class': final_risk_class,
        'risk_class': final_risk_class,
        'primary_reason': primary_reason,
        'secondary_reasons': '|'.join(secondary_reasons),
        'reason_codes': '|'.join(reason_codes),
        'execution_confirmed': bool(liquidity_metrics.get('execution_multi_snapshot_confirmed')),
        'execution_confidence': liquidity_metrics.get('execution_confidence'),
        'incomplete_data': bool(candle_count == 0),
        'incomplete_history': bool(missing_intervals_count > 0 or coverage_pct < 100.0),
        **liquidity_metrics,
    }
    return AnalyzerOutput(market_stats=market_stats, sparse_stats=sparse_stats, risk_flags=risk_flags, summary=summary)
