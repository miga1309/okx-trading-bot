from __future__ import annotations
from position_reconciler import get_dynamic_sync_interval as reconciler_dynamic_sync_interval

import csv
import json
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

from trade_models import BotConfig
from exchange_health import summarize_connectivity_rows

@dataclass
class ExportBundleContext:
    app_version: str
    state_file: Path
    engine_stats_file: Path
    signal_audit_file: Path
    position_journal_file: Path
    position_snapshots_file: Path
    system_health_file: Path
    connectivity_log_file: Path
    pyramid_diagnostics_file: Path
    reentry_diagnostics_file: Path
    breakout_quality_file: Path
    stop_engine_file: Path
    traceback_error_file: Path
    analysis_export_dir: Path

APP_VERSION = ""
STATE_FILE = Path(".")
ENGINE_STATS_FILE = Path(".")
SIGNAL_AUDIT_FILE = Path(".")
POSITION_JOURNAL_FILE = Path(".")
POSITION_SNAPSHOTS_FILE = Path(".")
SYSTEM_HEALTH_FILE = Path(".")
CONNECTIVITY_LOG_FILE = Path(".")
PYRAMID_DIAGNOSTICS_FILE = Path(".")
REENTRY_DIAGNOSTICS_FILE = Path(".")
BREAKOUT_QUALITY_FILE = Path(".")
STOP_ENGINE_FILE = Path(".")
TRACEBACK_ERROR_FILE = Path(".")
ANALYSIS_EXPORT_DIR = Path(".")

def _apply_context(ctx: ExportBundleContext) -> None:
    global APP_VERSION, STATE_FILE, ENGINE_STATS_FILE, SIGNAL_AUDIT_FILE, POSITION_JOURNAL_FILE
    global POSITION_SNAPSHOTS_FILE, SYSTEM_HEALTH_FILE, CONNECTIVITY_LOG_FILE, PYRAMID_DIAGNOSTICS_FILE
    global REENTRY_DIAGNOSTICS_FILE, BREAKOUT_QUALITY_FILE, STOP_ENGINE_FILE, TRACEBACK_ERROR_FILE, ANALYSIS_EXPORT_DIR
    APP_VERSION = ctx.app_version
    STATE_FILE = ctx.state_file
    ENGINE_STATS_FILE = ctx.engine_stats_file
    SIGNAL_AUDIT_FILE = ctx.signal_audit_file
    POSITION_JOURNAL_FILE = ctx.position_journal_file
    POSITION_SNAPSHOTS_FILE = ctx.position_snapshots_file
    SYSTEM_HEALTH_FILE = ctx.system_health_file
    CONNECTIVITY_LOG_FILE = ctx.connectivity_log_file
    PYRAMID_DIAGNOSTICS_FILE = ctx.pyramid_diagnostics_file
    REENTRY_DIAGNOSTICS_FILE = ctx.reentry_diagnostics_file
    BREAKOUT_QUALITY_FILE = ctx.breakout_quality_file
    STOP_ENGINE_FILE = ctx.stop_engine_file
    TRACEBACK_ERROR_FILE = ctx.traceback_error_file
    ANALYSIS_EXPORT_DIR = ctx.analysis_export_dir

def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)

def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)

def _safe_json_load(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _read_jsonl_rows(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows


def _write_csv(path: Path, headers: List[str], rows: List[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _write_jsonl(path: Path, rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def _classify_reason_code(reason: object) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "unknown"
    mapping = [
        ("manual", "manual_skip"),
        ("лиимит", "position_limit"),
        ("лимит", "position_limit"),
        ("already_open", "already_open"),
        ("blacklist", "blacklist"),
        ("blocked", "blacklist"),
        ("cooldown", "cooldown"),
        ("atr-стоп", "stopout_cooldown"),
        ("atr стоп", "stopout_cooldown"),
        ("недостаточно свечей", "not_enough_candles"),
        ("нет свежего пробоя", "no_fresh_breakout"),
        ("пробой не свежий", "stale_breakout"),
        ("нет пробоя", "no_breakout"),
        ("вернулась под", "breakout_failed_close"),
        ("вернулась над", "breakout_failed_close"),
        ("liquidity", "liquidity_filter"),
        ("широкий спред", "liquidity_spread"),
        ("top-of-book", "liquidity_top_book"),
        ("тонкий стакан", "liquidity_orderbook"),
        ("24h объём", "liquidity_volume"),
        ("последняя цена далеко от mid", "liquidity_mid_deviation"),
        ("turtle 20", "turtle20_skip_after_profit"),
        ("rotation", "rotation_block"),
        ("ротац", "rotation_block"),
        ("blacklist_or_blocked", "blacklist"),
        ("already_open_after_previous_fill", "already_open"),
    ]
    for token, code in mapping:
        if token in text:
            return code
    return text[:64].replace(" ", "_")


def _compute_mfe_mae_from_context(context_payload: dict) -> dict:
    candles = list(context_payload.get("candles") or [])
    side = str(context_payload.get("side") or "").lower()
    entry_price = _safe_float(context_payload.get("entry_price", 0.0))
    entry_atr = _safe_float(context_payload.get("entry_atr", context_payload.get("atr", 0.0)))
    initial_stop_price = _safe_float(context_payload.get("initial_stop_price", context_payload.get("start_stop_price", 0.0)))
    if entry_price <= 0 or not candles:
        return {"mfe_abs": 0.0, "mfe_pct": 0.0, "mfe_r": 0.0, "mae_abs": 0.0, "mae_pct": 0.0, "mae_r": 0.0}
    highs=[]; lows=[]
    for candle in candles:
        try:
            highs.append(float(candle[2]))
            lows.append(float(candle[3]))
        except Exception:
            continue
    if not highs or not lows:
        return {"mfe_abs": 0.0, "mfe_pct": 0.0, "mfe_r": 0.0, "mae_abs": 0.0, "mae_pct": 0.0, "mae_r": 0.0}
    risk = abs(entry_price - initial_stop_price)
    if risk <= 0 and entry_atr > 0:
        risk = entry_atr * 2.0
    risk = max(risk, 1e-12)
    if side == "short":
        mfe_abs = max(0.0, entry_price - min(lows))
        mae_abs = max(0.0, max(highs) - entry_price)
    else:
        mfe_abs = max(0.0, max(highs) - entry_price)
        mae_abs = max(0.0, entry_price - min(lows))
    return {
        "mfe_abs": mfe_abs,
        "mfe_pct": (mfe_abs / entry_price) * 100.0 if entry_price > 0 else 0.0,
        "mfe_r": mfe_abs / risk,
        "mae_abs": mae_abs,
        "mae_pct": (mae_abs / entry_price) * 100.0 if entry_price > 0 else 0.0,
        "mae_r": mae_abs / risk,
    }


def _stable_trade_id(inst_id: str, side: str, timestamp_text: str) -> str:
    safe_inst = str(inst_id or "UNK").replace("/", "_").replace(":", "_")
    safe_side = str(side or "na").lower()
    safe_ts = str(timestamp_text or datetime.now().strftime("%Y%m%d_%H%M%S")).replace("-", "").replace(":", "").replace(" ", "_")
    return f"{safe_ts}_{safe_inst}_{safe_side}"


SENSITIVE_EXPORT_KEYS = {
    "api_key",
    "secret_key",
    "passphrase",
    "telegram_bot_token",
    "telegram_chat_id",
    "bot_token",
    "token",
    "secret",
    "password",
    "webhook_url",
}


def _sanitize_for_export(value, parent_key: str = ""):
    key_norm = str(parent_key or "").strip().lower()
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.strip().lower() in SENSITIVE_EXPORT_KEYS:
                clean[key_str] = "***REDACTED***"
            else:
                clean[key_str] = _sanitize_for_export(item, key_str)
        return clean
    if isinstance(value, list):
        return [_sanitize_for_export(item, parent_key) for item in value]
    if key_norm in SENSITIVE_EXPORT_KEYS:
        return "***REDACTED***"
    return value


def _export_strategy_config(cfg: Optional["BotConfig"]) -> dict:
    if cfg is None:
        return {}
    source = asdict(cfg)
    whitelist = {
        "flag", "timeframe", "td_mode", "leverage", "scan_interval_sec", "position_check_interval_sec",
        "balance_refresh_sec", "risk_per_trade_pct", "max_position_notional_pct",
        "long_entry_period", "short_entry_period", "long_exit_period", "short_exit_period", "atr_period",
        "atr_stop_multiple", "add_unit_every_atr", "max_units_per_symbol", "trade_mode",
        "snapshot_interval_sec", "gui_refresh_ms", "flat_lookback_candles", "min_channel_range_pct",
        "min_atr_pct", "min_body_to_range_ratio", "min_efficiency_ratio", "max_direction_flip_ratio",
        "blacklist", "execution_risk_watchlist", "execution_issue_repeats_for_quarantine",
        "execution_quarantine_hours", "execution_close_verify_delay_sec", "execution_close_pending_retry_sec",
        "telegram_enabled", "pyramid_second_unit_scale", "pyramid_third_unit_scale", "pyramid_fourth_unit_scale",
        "pyramid_break_even_buffer_atr", "pyramid_min_progress_atr", "pyramid_min_body_ratio",
        "pyramid_min_stop_distance_atr", "breakout_buffer_atr", "breakout_min_body_atr",
        "breakout_close_near_extreme_ratio", "breakout_min_range_expansion", "breakout_max_prebreak_distance_atr",
        "breakout_max_distance_atr", "preferred_breakout_distance_atr_min", "preferred_breakout_distance_atr_max",
        "breakout_retest_invalid_ratio", "breakout_volume_factor", "flat_max_repeated_close_ratio",
        "flat_max_inside_ratio", "flat_max_wick_to_range_ratio", "flat_min_channel_atr_ratio",
        "flat_max_micro_pullback_ratio", "cooldown_after_stop_bars", "cooldown_min_seconds",
        "cooldown_max_seconds", "reentry_recovery_atr", "liquidity_max_spread_pct",
        "liquidity_min_top_of_book_usdt", "liquidity_min_side_notional_usdt",
        "liquidity_min_24h_quote_volume", "liquidity_filter_enabled", "illiquid_block_hours",
        "illiquid_soft_reject_cooldown_sec", "illiquid_repeats_for_ban", "max_open_positions_total",
        "max_open_positions_per_side", "rotation_enabled", "rotation_max_units_threshold",
        "rotation_require_negative_pnl", "rotation_min_negative_pnl_pct", "auto_cancel_pending_close_orders",
        "signal_audit_enabled", "signal_audit_top_n", "signal_audit_log_all_rejections",
        "market_data_cache_ttl_sec", "market_data_worker_sleep_sec", "market_data_log_every_sec",
        "liquidity_trap_detector_enabled", "liquidity_history_lookback_points",
        "liquidity_history_min_stable_points", "liquidity_history_max_age_sec",
        "liquidity_history_collapse_ratio", "liquidity_history_median_ratio",
        "liquidity_history_spread_blowout_mult", "trend_stop_activation_r", "trend_stop_peak_atr_multiple",
        "trend_stop_peak_atr_multiple_after_4_units", "trend_stop_max_pullback_from_peak_r",
        "trend_stop_min_locked_r", "trend_stop_use_peak_pullback_exit",
        "diagnostic_near_pass_top_n", "atr_warmup_extra_candles", "signal_funnel_enabled",
        "trade_ready_log_interval_sec", "trade_ready_include_open_positions",
    }
    safe = {key: source.get(key) for key in whitelist if key in source}
    return _sanitize_for_export(safe)


def _compute_signal_funnel(signal_audit_rows: List[dict], engine_event_rows: List[dict]) -> dict:
    funnel = {
        "cycles": 0,
        "instruments_scanned": 0,
        "prefilter_skipped": 0,
        "warmup_rejected": 0,
        "flat_filter_rejected": 0,
        "structure_rejected": 0,
        "trend_rejected": 0,
        "liquidity_rejected": 0,
        "breakout_rejected": 0,
        "other_rejected": 0,
        "candidates": 0,
        "ranked_candidates": 0,
        "orders_sent": 0,
        "entry_failed": 0,
        "manual_skipped": 0,
        "positions_opened": 0,
        "entry_signals": 0,
    }
    for row in signal_audit_rows:
        stage = str(row.get("stage") or "")
        reason = str(row.get("reason") or "").lower()
        if stage == "cycle_started":
            funnel["cycles"] += 1
        elif stage == "prefilter_skipped":
            funnel["prefilter_skipped"] += 1
        elif stage == "candidate":
            funnel["candidates"] += 1
        elif stage == "ranked_candidate":
            funnel["ranked_candidates"] += 1
        elif stage == "entry_sent":
            funnel["orders_sent"] += 1
        elif stage == "entry_failed":
            funnel["entry_failed"] += 1
        elif stage == "entry_skipped_manual":
            funnel["manual_skipped"] += 1
        elif stage == "rejected":
            funnel["instruments_scanned"] += 1
            if "warmup" in reason or "недостаточно свечей" in reason or "atr недоступ" in reason:
                funnel["warmup_rejected"] += 1
            elif "flat filter" in reason or "узкий диапазон" in reason or "канал слишком мал" in reason or "слабая структура диапазона" in reason:
                funnel["flat_filter_rejected"] += 1
            elif "structure filter" in reason or "ложных выносов" in reason or "плотная база" in reason or "прилипла к центру" in reason:
                funnel["structure_rejected"] += 1
            elif "trend filter" in reason or "ema20" in reason or "ema50" in reason:
                funnel["trend_rejected"] += 1
            elif "liquidity" in reason or "спред" in reason or "стакан" in reason or "top-of-book" in reason or "объём" in reason:
                funnel["liquidity_rejected"] += 1
            elif "пробой" in reason or "donchian" in reason or "свеча" in reason or "breakout" in reason:
                funnel["breakout_rejected"] += 1
            else:
                funnel["other_rejected"] += 1
    for row in engine_event_rows:
        event = str(row.get("event") or "")
        if event == "position_opened":
            funnel["positions_opened"] += 1
        elif event == "entry_signal":
            funnel["entry_signals"] += 1
    return funnel


def _scan_export_files_for_secrets(export_dir: Path) -> List[str]:
    hits: List[str] = []
    patterns = [
        "api_key", "secret_key", "passphrase", "telegram_bot_token", "telegram_chat_id",
        "bot_token", "token=", "xoxb-", "Bearer ",
    ]
    for file_path in export_dir.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() not in {".json", ".txt", ".csv", ".log"}:
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        content_lower = content.lower()
        for pattern in patterns:
            if pattern.lower() in content_lower and "***redacted***" not in content_lower:
                hits.append(f"{file_path.name}:{pattern}")
                break
    return hits

def _parse_export_dt(value: object) -> Optional[datetime]:
    txt = str(value or '').strip()
    if not txt:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%H:%M:%S'):
        try:
            dt = datetime.strptime(txt, fmt)
            if fmt == '%H:%M:%S':
                now = datetime.now()
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
            return dt
        except Exception:
            continue
    return None


def _hour_bucket_label(dt: datetime) -> str:
    return f"{dt:%H}_{(dt + timedelta(hours=1)):%H}"


def _row_dt(row: dict) -> Optional[datetime]:
    return _parse_export_dt(row.get('ts') or row.get('time') or row.get('timestamp'))


def _rows_between(rows: List[dict], start_dt: Optional[datetime], end_dt: Optional[datetime]) -> List[dict]:
    if start_dt is None and end_dt is None:
        return list(rows)
    result = []
    for row in rows:
        dt = _row_dt(row)
        if dt is None:
            continue
        if start_dt is not None and dt < start_dt:
            continue
        if end_dt is not None and dt >= end_dt:
            continue
        result.append(dict(row))
    return result


def _position_row_key(row: dict) -> str:
    return str(row.get('trade_id') or row.get('inst_id') or row.get('symbol') or row.get('ts') or '')


def _build_open_positions_endstate_rows(open_positions: List[dict]) -> List[dict]:
    rows = []
    for row in (open_positions or []):
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'entry_time': row.get('entry_time', ''),
            'avg_px': _safe_float(row.get('avg_px', 0.0)),
            'last_px': _safe_float(row.get('last_px', 0.0)),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'next_unit_level': _safe_float(row.get('next_pyramid_price', row.get('next_unit_level', 0.0))),
            'units': _safe_int(row.get('units', 1), 1),
            'qty': _safe_float(row.get('qty', 0.0)),
            'unrealized_pnl': _safe_float(row.get('unrealized_pnl', 0.0)),
            'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
            'peak_unrealized_pnl': _safe_float(row.get('peak_unrealized_pnl', 0.0)),
            'peak_pnl_pct': _safe_float(row.get('peak_pnl_pct', 0.0)),
            'atr': _safe_float(row.get('atr', 0.0)),
            'position_age_sec': _safe_int(row.get('position_age_sec', row.get('age_sec', 0))),
            'close_pending': bool(row.get('close_pending', False)),
        })
    return rows


def _build_position_lifecycle_rows(journal_rows: List[dict], snapshot_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in journal_rows:
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'event_type': row.get('event', ''),
            'price': _safe_float(row.get('price', 0.0)),
            'avg_entry_price': _safe_float(row.get('avg_px', row.get('entry_px', 0.0))),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'next_unit_level': _safe_float(row.get('next_pyramid_price', row.get('next_unit_level', 0.0))),
            'units': _safe_int(row.get('units', 0)),
            'qty_total': _safe_float(row.get('qty', 0.0)),
            'pnl_usd': _safe_float(row.get('unrealized_pnl', row.get('pnl', 0.0))),
            'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
            'mfe_pct': _safe_float(row.get('mfe_pct', 0.0)),
            'mae_pct': _safe_float(row.get('mae_pct', 0.0)),
            'atr': _safe_float(row.get('atr', 0.0)),
            'position_age_sec': _safe_int(row.get('position_age_sec', 0)),
            'reason_code': row.get('reason_code', _classify_reason_code(row.get('reason'))),
            'reason': row.get('reason', row.get('note', '')),
        })
    for row in snapshot_rows:
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'event_type': 'SNAPSHOT',
            'price': _safe_float(row.get('price', 0.0)),
            'avg_entry_price': _safe_float(row.get('avg_entry_price', 0.0)),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'next_unit_level': _safe_float(row.get('next_unit_level', 0.0)),
            'units': _safe_int(row.get('units', 0)),
            'qty_total': _safe_float(row.get('qty_total', 0.0)),
            'pnl_usd': _safe_float(row.get('pnl_usd', 0.0)),
            'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
            'mfe_pct': _safe_float(row.get('mfe_pct', 0.0)),
            'mae_pct': _safe_float(row.get('mae_pct', 0.0)),
            'atr': _safe_float(row.get('atr', 0.0)),
            'position_age_sec': _safe_int(row.get('position_age_sec', 0)),
            'reason_code': '',
            'reason': row.get('note', 'Минутный snapshot позиции'),
        })
    rows.sort(key=lambda item: (str(item.get('timestamp') or ''), str(item.get('inst_id') or '')))
    return rows


def _build_entry_candidate_rows(signal_audit_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in signal_audit_rows:
        stage = str(row.get('stage') or '')
        if stage not in {'candidate', 'ranked_candidate', 'rejected', 'entry_sent', 'entry_failed', 'entry_skipped_manual'}:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'cycle_id': row.get('cycle_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'stage': stage,
            'system_name': row.get('system_name', ''),
            'price': _safe_float(row.get('price', row.get('last_price', 0.0))),
            'breakout_level': _safe_float(row.get('breakout_level', row.get('channel_level', 0.0))),
            'atr': _safe_float(row.get('atr', 0.0)),
            'signal_detected': stage in {'candidate', 'ranked_candidate', 'entry_sent', 'entry_failed'},
            'passed_filters': stage not in {'rejected'},
            'reject_code': row.get('reject_code', _classify_reason_code(row.get('reason'))),
            'reason': row.get('reason', ''),
            'liquidity_score': _safe_float(row.get('liquidity_score', 0.0)),
            'breakout_distance_atr': _safe_float(row.get('breakout_distance_atr', 0.0)),
            'freshness_score': _safe_float(row.get('freshness_score', 0.0)),
            'recent_trade_penalty': _safe_float(row.get('recent_trade_penalty', 0.0)),
        })
    return rows


def _build_decision_trace_rows(signal_audit_rows: List[dict], engine_event_rows: List[dict], journal_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in signal_audit_rows:
        stage = str(row.get('stage') or '')
        decision_type = {
            'candidate': 'ENTRY_CHECK',
            'ranked_candidate': 'ENTRY_RANK',
            'rejected': 'ENTRY_CHECK',
            'entry_sent': 'ENTRY_EXECUTION',
            'entry_failed': 'ENTRY_EXECUTION',
            'entry_skipped_manual': 'ENTRY_CHECK',
        }.get(stage)
        if not decision_type:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'decision_type': decision_type,
            'stage': stage,
            'condition': row.get('reason', stage),
            'condition_result': stage not in {'rejected', 'entry_failed'},
            'action_taken': stage in {'entry_sent'},
            'reason_code': row.get('reject_code', _classify_reason_code(row.get('reason'))),
            'reason_text': row.get('reason', ''),
            'context_json_short': json.dumps(_sanitize_for_export({
                'score': row.get('score'),
                'liquidity_score': row.get('liquidity_score'),
                'breakout_distance_atr': row.get('breakout_distance_atr'),
                'freshness_score': row.get('freshness_score'),
            }), ensure_ascii=False),
        })
    for row in engine_event_rows:
        event = str(row.get('event') or '')
        if event not in {'pyramid_skipped', 'pyramid_added', 'position_opened', 'position_closed', 'rotation_started', 'rotation_completed', 'rotation_failed', 'order_rejected', 'entry_skipped_manual', 'entry_skipped'}:
            continue
        decision_type = 'RISK_CHECK'
        if event.startswith('pyramid_'):
            decision_type = 'ADD_UNIT_CHECK'
        elif event in {'position_closed'}:
            decision_type = 'EXIT_CHECK'
        elif event in {'position_opened'}:
            decision_type = 'ENTRY_EXECUTION'
        elif event.startswith('rotation_'):
            decision_type = 'ROTATION_CHECK'
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'decision_type': decision_type,
            'stage': event,
            'condition': row.get('reason', event),
            'condition_result': event not in {'pyramid_skipped', 'rotation_failed', 'order_rejected', 'entry_skipped', 'entry_skipped_manual'},
            'action_taken': event in {'pyramid_added', 'position_opened', 'position_closed', 'rotation_completed'},
            'reason_code': row.get('reason_code', _classify_reason_code(row.get('reason'))),
            'reason_text': row.get('reason', ''),
            'context_json_short': json.dumps(_sanitize_for_export({
                'units': row.get('units'),
                'last_price': row.get('last_price'),
                'next_pyramid_price': row.get('next_pyramid_price'),
                'retry_after_sec': row.get('retry_after_sec'),
            }), ensure_ascii=False),
        })
    for row in journal_rows:
        event = str(row.get('event') or '')
        if event not in {'TRAIL_UPDATE', 'CLOSE_PENDING', 'PEAK_PNL'}:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'decision_type': 'STOP_MOVE_CHECK' if event == 'TRAIL_UPDATE' else 'EXIT_CHECK',
            'stage': event,
            'condition': row.get('note', event),
            'condition_result': True,
            'action_taken': True,
            'reason_code': row.get('reason_code', _classify_reason_code(row.get('reason'))),
            'reason_text': row.get('reason', row.get('note', '')),
            'context_json_short': json.dumps(_sanitize_for_export({
                'price': row.get('price'),
                'prev_stop_price': row.get('prev_stop_price'),
                'stop_price': row.get('stop_price'),
                'peak_unrealized_pnl': row.get('peak_unrealized_pnl'),
            }), ensure_ascii=False),
        })
    rows.sort(key=lambda item: (str(item.get('timestamp') or ''), str(item.get('inst_id') or '')))
    return rows


def _build_execution_log_rows(engine_event_rows: List[dict], journal_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in engine_event_rows:
        event = str(row.get('event') or '')
        if event not in {'order_rejected', 'position_opened', 'position_closed', 'close_pending_exchange'}:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'action': event,
            'side': row.get('side', ''),
            'qty': _safe_float(row.get('qty', 0.0)),
            'price': _safe_float(row.get('price', row.get('last_price', 0.0))),
            'response_code': row.get('code', row.get('reason_code', '')),
            'response_message': row.get('reason', row.get('msg', '')),
            'latency_ms': _safe_float(row.get('latency_ms', 0.0)),
            'success': event not in {'order_rejected'},
        })
    for row in journal_rows:
        event = str(row.get('event') or '')
        if event not in {'OPEN', 'CLOSE', 'CLOSE_PENDING'}:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'action': event,
            'side': row.get('side', ''),
            'qty': _safe_float(row.get('qty', 0.0)),
            'price': _safe_float(row.get('price', 0.0)),
            'response_code': row.get('reason_code', ''),
            'response_message': row.get('reason', row.get('note', '')),
            'latency_ms': _safe_float(row.get('latency_ms', 0.0)),
            'success': True,
        })
    rows.sort(key=lambda item: (str(item.get('timestamp') or ''), str(item.get('inst_id') or '')))
    return rows


def _build_risk_event_rows(engine_event_rows: List[dict], filter_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    interesting = {'rotation_started', 'rotation_completed', 'rotation_failed', 'rotation_unavailable', 'close_pending_exchange', 'entry_skipped_manual', 'entry_skipped', 'order_rejected', 'filter_diagnostics'}
    for row in engine_event_rows:
        event = str(row.get('event') or '')
        if event not in interesting:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'inst_id': row.get('inst_id', ''),
            'event_type': event,
            'reason_code': row.get('reason_code', _classify_reason_code(row.get('reason'))),
            'details': row.get('reason', ''),
        })
    for row in filter_rows:
        rows.append({
            'timestamp': row.get('ts', ''),
            'inst_id': row.get('inst_id', ''),
            'event_type': 'filter_diagnostics',
            'reason_code': '',
            'details': json.dumps(_sanitize_for_export(row), ensure_ascii=False),
        })
    rows.sort(key=lambda item: (str(item.get('timestamp') or ''), str(item.get('inst_id') or '')))
    return rows


def _build_market_context_rows(trade_rows: List[dict]) -> List[dict]:
    rows = []
    for row in trade_rows:
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'entry_time': row.get('time', ''),
            'entry_price': _safe_float(row.get('entry_px', 0.0)),
            'entry_atr': _safe_float(row.get('entry_atr', 0.0)),
            'initial_stop_price': _safe_float(row.get('initial_stop_price', 0.0)),
            'planned_risk_pct': _safe_float(row.get('planned_risk_pct', 0.0)),
            'risk_amount_usdt': _safe_float(row.get('risk_amount_usdt', 0.0)),
            'position_notional_usdt': _safe_float(row.get('position_notional_usdt', 0.0)),
            'mfe_pct': _safe_float(row.get('mfe_pct', 0.0)),
            'mae_pct': _safe_float(row.get('mae_pct', 0.0)),
        })
    return rows


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')



def _group_rows_by_trade(rows: List[dict], key_name: str = 'trade_id') -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for row in rows:
        key = str(row.get(key_name, '') or '').strip()
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def _build_market_risk_scores(risk_rows: List[dict], stop_engine_rows: List[dict]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for row in risk_rows:
        inst = str(row.get('inst_id', '') or '').strip()
        if not inst:
            continue
        event = str(row.get('event_type', '') or '')
        delta = 1.0
        if event in {'order_rejected', 'rotation_failed'}:
            delta = 2.0
        elif event in {'close_pending_exchange', 'filter_diagnostics'}:
            delta = 1.5
        scores[inst] = scores.get(inst, 0.0) + delta
    for row in stop_engine_rows:
        inst = str(row.get('inst_id', '') or '').strip()
        if not inst:
            continue
        event = str(row.get('event', '') or '')
        delta = 0.0
        if event in {'STOP_ERROR', 'STOP_MISSING'}:
            delta = 2.0
        elif event in {'STOP_REJECTED'}:
            delta = 2.5
        elif event in {'STOP_MOVED'}:
            delta = 0.25
        if delta:
            scores[inst] = scores.get(inst, 0.0) + delta
    return {k: round(v, 2) for k, v in scores.items()}


def _extract_trade_diagnostics(
    trades_export_rows: List[dict],
    lifecycle_rows: List[dict],
    stop_engine_rows: List[dict],
    risk_rows: List[dict],
) -> List[dict]:
    lifecycle_by_trade = _group_rows_by_trade(lifecycle_rows)
    stop_by_inst: Dict[str, List[dict]] = {}
    for row in stop_engine_rows:
        inst = str(row.get('inst_id', '') or '').strip()
        if inst:
            stop_by_inst.setdefault(inst, []).append(row)
    market_risk_scores = _build_market_risk_scores(risk_rows, stop_engine_rows)

    diagnostics: List[dict] = []
    for trade in trades_export_rows:
        trade_id = str(trade.get('trade_id', '') or '')
        inst_id = str(trade.get('inst_id', '') or '')
        side = str(trade.get('side', '') or '')
        pnl_pct = _safe_float(trade.get('pnl_pct', 0.0))
        mfe_pct = _safe_float(trade.get('mfe_pct', 0.0))
        mae_pct = _safe_float(trade.get('mae_pct', 0.0))
        early_exit_gap_pct = round(max(0.0, mfe_pct - max(0.0, pnl_pct)), 6)
        early_exit_flag = bool(pnl_pct > 0 and mfe_pct >= max(2.0, pnl_pct * 1.5) and early_exit_gap_pct >= 2.0)

        trade_events = lifecycle_by_trade.get(trade_id, [])
        unit_add_events = sum(1 for row in trade_events if str(row.get('event_type', '') or '') in {'ADD_UNIT', 'PYRAMID_ADD', 'pyramid_added'})
        stop_move_events = sum(1 for row in trade_events if str(row.get('event_type', '') or '') in {'TRAIL_UPDATE', 'MOVE_STOP'})

        inst_stop_events = stop_by_inst.get(inst_id, [])
        last_stop_reason = ''
        for row in reversed(inst_stop_events):
            reason = str(row.get('reason') or row.get('event') or '').strip()
            if reason:
                last_stop_reason = reason
                break

        market_risk_score = _safe_float(market_risk_scores.get(inst_id, 0.0))
        diagnostics.append({
            'trade_id': trade_id,
            'inst_id': inst_id,
            'side': side,
            'pnl_pct': pnl_pct,
            'mfe_pct': mfe_pct,
            'mae_pct': mae_pct,
            'early_exit_flag': early_exit_flag,
            'early_exit_gap_pct': early_exit_gap_pct,
            'unit_add_events': unit_add_events,
            'stop_move_events': stop_move_events,
            'last_stop_move_reason': last_stop_reason,
            'market_risk_score': market_risk_score,
        })
    return diagnostics


def _calc_trade_analysis_rows(
    trades_export_rows: List[dict],
    lifecycle_rows: List[dict],
    stop_engine_rows: List[dict],
    risk_rows: List[dict],
    entry_candidate_rows: List[dict],
) -> List[dict]:
    lifecycle_by_trade = _group_rows_by_trade(lifecycle_rows)
    stop_by_inst: Dict[str, List[dict]] = {}
    for row in stop_engine_rows:
        inst = str(row.get('inst_id', '') or '').strip()
        if inst:
            stop_by_inst.setdefault(inst, []).append(row)
    market_risk_scores = _build_market_risk_scores(risk_rows, stop_engine_rows)

    rows: List[dict] = []
    for trade in trades_export_rows:
        trade_id = str(trade.get('trade_id', '') or '').strip()
        inst_id = str(trade.get('inst_id', '') or '').strip()
        pnl = _safe_float(trade.get('pnl', 0.0))
        pnl_pct = _safe_float(trade.get('pnl_pct', 0.0))
        mfe_pct = _safe_float(trade.get('mfe_pct', 0.0))
        mae_pct = _safe_float(trade.get('mae_pct', 0.0))
        mfe_r = _safe_float(trade.get('mfe_r', 0.0))
        mae_r = _safe_float(trade.get('mae_r', 0.0))
        units = _safe_int(trade.get('units', 1), 1)
        duration_sec = _safe_int(trade.get('duration_sec', 0), 0)

        trend_capture_ratio = round((pnl_pct / max(mfe_pct, 1e-12)) if mfe_pct > 0 else 0.0, 6)
        exit_efficiency = round((pnl / max(_safe_float(trade.get('peak_unrealized_pnl', 0.0)), 1e-12)) if _safe_float(trade.get('peak_unrealized_pnl', 0.0)) > 0 else 0.0, 6)
        early_exit_gap_pct = round(max(0.0, mfe_pct - max(0.0, pnl_pct)), 6)
        early_exit_flag = bool(pnl_pct > 0 and mfe_pct >= max(2.0, pnl_pct * 1.5) and early_exit_gap_pct >= 2.0)

        trade_events = lifecycle_by_trade.get(trade_id, [])
        unit_add_events = [row for row in trade_events if str(row.get('event_type', '') or '') in {'ADD_UNIT', 'PYRAMID_ADD', 'pyramid_added'}]
        stop_move_events = [row for row in trade_events if str(row.get('event_type', '') or '') in {'TRAIL_UPDATE', 'MOVE_STOP'}]

        pyramid_effect_score = round((pnl_pct / max(units, 1)), 6)
        if units <= 1:
            pyramid_effect_label = 'no_pyramid'
        elif pnl_pct > 0 and trend_capture_ratio >= 0.45:
            pyramid_effect_label = 'helped'
        elif pnl_pct < 0:
            pyramid_effect_label = 'hurt'
        else:
            pyramid_effect_label = 'neutral'

        last_stop_reason = ''
        stop_rejects = 0
        stop_errors = 0
        for row in stop_by_inst.get(inst_id, []):
            event = str(row.get('event') or '').strip()
            if event == 'STOP_REJECTED':
                stop_rejects += 1
            if event in {'STOP_ERROR', 'STOP_MISSING'}:
                stop_errors += 1
            reason = str(row.get('reason') or row.get('msg') or event).strip()
            if reason:
                last_stop_reason = reason

        entry_quality = 'unknown'
        entry_type = str(trade.get('system_name', '') or '')
        trend_strength = round(max(mfe_r, 0.0), 6)
        if mfe_r >= 2.5:
            entry_quality = 'strong'
        elif mfe_r >= 1.0:
            entry_quality = 'normal'
        elif mfe_r > 0:
            entry_quality = 'weak'

        stop_efficiency = round((trend_capture_ratio * 0.6 + (0.4 if len(stop_move_events) > 0 else 0.2)), 6)
        market_risk_score = _safe_float(market_risk_scores.get(inst_id, 0.0))

        rows.append({
            'trade_id': trade_id,
            'inst_id': inst_id,
            'side': trade.get('side', ''),
            'entry_type': entry_type,
            'entry_quality': entry_quality,
            'trend_strength_r': trend_strength,
            'mfe_pct': mfe_pct,
            'mae_pct': mae_pct,
            'mfe_r': mfe_r,
            'mae_r': mae_r,
            'realized_pnl': pnl,
            'realized_pnl_pct': pnl_pct,
            'trend_capture_ratio': trend_capture_ratio,
            'exit_reason': trade.get('close_reason_code', trade.get('reason', '')),
            'exit_efficiency': exit_efficiency,
            'early_exit_flag': early_exit_flag,
            'early_exit_gap_pct': early_exit_gap_pct,
            'units': units,
            'unit_add_count': len(unit_add_events),
            'pyramid_effect_score': pyramid_effect_score,
            'pyramid_effect_label': pyramid_effect_label,
            'stop_move_count': len(stop_move_events),
            'last_stop_move_reason': last_stop_reason,
            'stop_efficiency': stop_efficiency,
            'stop_rejects_for_symbol': stop_rejects,
            'stop_errors_for_symbol': stop_errors,
            'market_risk_score': market_risk_score,
            'duration_sec': duration_sec,
        })
    return rows


def _calc_market_analysis_rows(
    trades_export_rows: List[dict],
    risk_rows: List[dict],
    stop_engine_rows: List[dict],
    entry_candidate_rows: List[dict],
) -> List[dict]:
    symbols = set()
    for rows in (trades_export_rows, risk_rows, stop_engine_rows, entry_candidate_rows):
        for row in rows:
            inst = str(row.get('inst_id', '') or '').strip()
            if inst:
                symbols.add(inst)

    market_risk_scores = _build_market_risk_scores(risk_rows, stop_engine_rows)
    out_rows: List[dict] = []
    for inst in sorted(symbols):
        trades = [row for row in trades_export_rows if str(row.get('inst_id', '') or '').strip() == inst]
        risks = [row for row in risk_rows if str(row.get('inst_id', '') or '').strip() == inst]
        stops = [row for row in stop_engine_rows if str(row.get('inst_id', '') or '').strip() == inst]
        entries = [row for row in entry_candidate_rows if str(row.get('inst_id', '') or '').strip() == inst]

        wins = sum(1 for row in trades if _safe_float(row.get('pnl', 0.0)) > 0)
        losses = sum(1 for row in trades if _safe_float(row.get('pnl', 0.0)) < 0)
        rejected = sum(1 for row in entries if str(row.get('stage', '') or '') == 'rejected')
        candidates = sum(1 for row in entries if str(row.get('stage', '') or '') in {'candidate', 'ranked_candidate'})
        stop_rejects = sum(1 for row in stops if str(row.get('event', '') or '') == 'STOP_REJECTED')
        stop_errors = sum(1 for row in stops if str(row.get('event', '') or '') in {'STOP_ERROR', 'STOP_MISSING'})
        close_pending = sum(1 for row in risks if str(row.get('event_type', '') or '') == 'close_pending_exchange')
        order_rejected = sum(1 for row in risks if str(row.get('event_type', '') or '') == 'order_rejected')
        out_rows.append({
            'inst_id': inst,
            'trades_count': len(trades),
            'wins': wins,
            'losses': losses,
            'realized_pnl': round(sum(_safe_float(row.get('pnl', 0.0)) for row in trades), 8),
            'avg_pnl_pct': round((sum(_safe_float(row.get('pnl_pct', 0.0)) for row in trades) / max(1, len(trades))), 6),
            'entry_candidates': candidates,
            'entry_rejections': rejected,
            'stop_rejects': stop_rejects,
            'stop_errors': stop_errors,
            'close_pending_events': close_pending,
            'order_rejected_events': order_rejected,
            'market_risk_score': _safe_float(market_risk_scores.get(inst, 0.0)),
        })
    return out_rows


def _build_position_reconcile_rows(open_positions: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in open_positions or []:
        stop_state = str(row.get('stop_state', '') or '')
        exchange_stop_status = str(row.get('exchange_stop_status', '') or '')
        position_health_state = str(row.get('position_health_state', '') or '')
        close_pending = bool(row.get('close_pending', False))
        sync_status = str(row.get('sync_status', '') or '')
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'qty': _safe_float(row.get('qty', 0.0)),
            'avg_px': _safe_float(row.get('avg_px', 0.0)),
            'last_px': _safe_float(row.get('last_px', 0.0)),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'exchange_stop_status': exchange_stop_status,
            'stop_state': stop_state,
            'position_health_state': position_health_state,
            'close_pending': close_pending,
            'sync_status': sync_status,
        })
    return rows


def _build_sync_drift_rows(open_positions: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in open_positions or []:
        sync_status = str(row.get('sync_status', '') or '')
        if sync_status in {'SYNC_DRIFT', 'STOP_MISSING', 'CLOSE_PENDING'}:
            rows.append({
                'trade_id': row.get('trade_id', ''),
                'inst_id': row.get('inst_id', ''),
                'side': row.get('side', ''),
                'sync_status': sync_status,
                'stop_state': row.get('stop_state', ''),
                'exchange_stop_status': row.get('exchange_stop_status', ''),
                'position_health_state': row.get('position_health_state', ''),
                'close_pending': bool(row.get('close_pending', False)),
            })
    return rows

def _build_position_sync_status_rows(open_positions: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in open_positions or []:
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'sync_status': row.get('sync_status', 'SYNC_OK'),
            'stop_state': row.get('stop_state', ''),
            'exchange_stop_status': row.get('exchange_stop_status', ''),
            'position_health_state': row.get('position_health_state', ''),
            'close_pending': bool(row.get('close_pending', False)),
            'qty': _safe_float(row.get('qty', 0.0)),
            'avg_px': _safe_float(row.get('avg_px', 0.0)),
            'last_px': _safe_float(row.get('last_px', 0.0)),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
        })
    return rows


def _turtle_exit_period_from_system(system_name: str) -> int:
    name = str(system_name or "").strip().lower()
    if "55" in name:
        return 20
    if "20" in name:
        return 10
    return 10


def _infer_hybrid_stop_mode(row: dict) -> str:
    units = _safe_int(row.get('units', 1), 1)
    mfe_r = _safe_float(row.get('mfe_r', 0.0))
    pnl_pct = _safe_float(row.get('realized_pnl_pct', row.get('pnl_pct', 0.0)))
    if units >= 2 or mfe_r >= 0.5 or pnl_pct >= 0.35:
        return 'DONCHIAN_ACTIVE'
    return 'ATR_INITIAL'


def _build_trend_capture_rows(trade_analysis_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in trade_analysis_rows:
        system_name = str(row.get('entry_type', '') or '')
        exit_period = _turtle_exit_period_from_system(system_name)
        mfe_r = _safe_float(row.get('mfe_r', 0.0))
        trend_capture_ratio = _safe_float(row.get('trend_capture_ratio', 0.0))
        realized_r = round(mfe_r * trend_capture_ratio, 6)
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': system_name,
            'turtle_exit_period': exit_period,
            'hybrid_stop_mode': _infer_hybrid_stop_mode(row),
            'trend_strength_r': _safe_float(row.get('trend_strength_r', 0.0)),
            'trend_move_r': mfe_r,
            'realized_r': realized_r,
            'trend_capture_ratio': trend_capture_ratio,
            'exit_efficiency': _safe_float(row.get('exit_efficiency', 0.0)),
            'early_exit_flag': bool(row.get('early_exit_flag', False)),
            'early_exit_gap_pct': _safe_float(row.get('early_exit_gap_pct', 0.0)),
            'units': _safe_int(row.get('units', 1), 1),
            'realized_pnl_pct': _safe_float(row.get('realized_pnl_pct', 0.0)),
            'mfe_pct': _safe_float(row.get('mfe_pct', 0.0)),
            'exit_reason': row.get('exit_reason', ''),
        })
    return rows


def _build_position_stop_regime_rows(open_positions: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in open_positions or []:
        system_name = str(row.get('system_name', '') or '')
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': system_name,
            'turtle_exit_period': _turtle_exit_period_from_system(system_name),
            'hybrid_stop_mode': 'DONCHIAN_ACTIVE' if _safe_int(row.get('units', 1), 1) >= 2 else 'ATR_INITIAL',
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'exchange_stop_status': row.get('exchange_stop_status', ''),
            'sync_status': row.get('sync_status', 'SYNC_OK'),
            'qty': _safe_float(row.get('qty', 0.0)),
            'avg_px': _safe_float(row.get('avg_px', 0.0)),
            'last_px': _safe_float(row.get('last_px', 0.0)),
        })
    return rows

def _build_position_runtime_regime_rows(open_positions: List[dict]) -> List[dict]:
    rows: List[dict] = []
    default_reconciler = reconciler_dynamic_sync_interval(len(open_positions or []))
    for row in open_positions or []:
        system_name = str(row.get('system_name', '') or '')
        stop_state = str(row.get('stop_state', '') or '')
        exchange_stop_status = str(row.get('exchange_stop_status', '') or '')
        position_health_state = str(row.get('position_health_state', '') or '')
        close_pending = bool(row.get('close_pending', False))
        pnl_pct = _safe_float(row.get('pnl_pct', 0.0))
        peak_pnl_pct = _safe_float(row.get('peak_pnl_pct', 0.0))
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': system_name,
            'turtle_exit_period': _safe_int(row.get('turtle_exit_period', _turtle_exit_period_from_system(system_name)), _turtle_exit_period_from_system(system_name)),
            'hybrid_stop_mode': row.get('hybrid_stop_mode', _infer_hybrid_stop_mode(row)),
            'trend_hold_state': row.get('trend_hold_state', ''),
            'sync_status': row.get('sync_status', derive_sync_status(stop_state=stop_state, exchange_stop_status=exchange_stop_status, position_health_state=position_health_state, close_pending=close_pending)),
            'reconciler_interval_sec': _safe_int(row.get('reconciler_interval_sec', default_reconciler), default_reconciler),
            'position_age_sec': _safe_int(row.get('position_age_sec', row.get('age_sec', 0)), 0),
            'qty': _safe_float(row.get('qty', 0.0)),
            'avg_px': _safe_float(row.get('avg_px', 0.0)),
            'last_px': _safe_float(row.get('last_px', 0.0)),
            'pnl_pct': pnl_pct,
            'peak_pnl_pct': peak_pnl_pct,
        })
    return rows


def _build_trend_hold_analysis_rows(trend_capture_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in trend_capture_rows or []:
        mode = str(row.get('hybrid_stop_mode', '') or '')
        trend_move_r = _safe_float(row.get('trend_move_r', 0.0))
        realized_r = _safe_float(row.get('realized_r', 0.0))
        trend_hold_state = 'TREND_HOLD' if mode == 'DONCHIAN_ACTIVE' and trend_move_r >= 1.0 else ('TREND_ACTIVE' if mode == 'DONCHIAN_ACTIVE' else 'INITIAL_RISK')
        rows.append({
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': row.get('system_name', ''),
            'hybrid_stop_mode': mode,
            'trend_hold_state': trend_hold_state,
            'trend_move_r': trend_move_r,
            'realized_r': realized_r,
            'retained_r_share': round((realized_r / max(trend_move_r, 1e-12)) if trend_move_r > 0 else 0.0, 6),
            'early_exit_flag': bool(row.get('early_exit_flag', False)),
            'exit_reason': row.get('exit_reason', ''),
            'units': _safe_int(row.get('units', 1), 1),
        })
    return rows

def _build_sync_bootstrap_rows(journal_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in journal_rows:
        if str(row.get('event') or '') != 'SYNC_BOOTSTRAP':
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': row.get('system_name', ''),
            'units_restored': _safe_int(row.get('units', 0), 0),
            'stop_restored': bool(row.get('stop_restored', False)),
            'pyramid_restored': bool(row.get('pyramid_restored', False)),
            'restored_fields': row.get('restored_fields', ''),
        })
    return rows


def _build_market_quality_rows(filter_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in filter_rows:
        reason = str(row.get('reason') or '')
        if 'sparse candles' not in reason and 'liquidity' not in reason and 'спред' not in reason and 'стакан' not in reason and 'мираж ликвидности' not in reason:
            continue
        rows.append({
            'timestamp': row.get('ts', ''),
            'inst_id': row.get('inst_id', ''),
            'reason': reason,
            'stage': row.get('stage', ''),
            'sparse_20': _safe_int(row.get('sparse_20', 0), 0),
            'sparse_55': _safe_int(row.get('sparse_55', 0), 0),
            'sparse_ratio_20': _safe_float(row.get('sparse_ratio_20', 0.0)),
            'sparse_ratio_55': _safe_float(row.get('sparse_ratio_55', 0.0)),
            'spread_pct': _safe_float(row.get('spread_pct', 0.0)),
            'best_side_notional': _safe_float(row.get('best_side_notional', 0.0)),
            'vol_24h': _safe_float(row.get('vol_24h', 0.0)),
        })
    return rows



def _build_blocked_entries_rows(entry_candidate_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in entry_candidate_rows:
        stage = str(row.get('stage') or '').strip().lower()
        if stage != 'rejected':
            continue
        rows.append({
            'ts': row.get('ts', ''),
            'cycle_id': row.get('cycle_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'system_name': row.get('system_name', ''),
            'stage': row.get('stage', ''),
            'block_reason': row.get('reject_code') or _classify_reason_code(row.get('reason')),
            'reason': row.get('reason', ''),
            'price': _safe_float(row.get('price', 0.0)),
            'atr': _safe_float(row.get('atr', 0.0)),
        })
    return rows


def _build_stop_failures_rows(stop_engine_rows: List[dict]) -> List[dict]:
    bad_events = {'STOP_REJECTED', 'STOP_ERROR', 'STOP_MISSING', 'STOP_CONFIRM_TIMEOUT', 'STOP_CANCEL_ERROR'}
    rows: List[dict] = []
    for row in stop_engine_rows:
        event = str(row.get('event') or '').strip()
        if event not in bad_events:
            continue
        rows.append({
            'ts': row.get('ts', row.get('time', '')),
            'trade_id': row.get('trade_id', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'event': event,
            'requested_stop': _safe_float(row.get('requested_stop', 0.0)),
            'current_price': _safe_float(row.get('current_price', 0.0)),
            'error_code': row.get('error_code', row.get('code', '')),
            'error_msg': row.get('error_msg', row.get('msg', row.get('reason', ''))),
            'response': json.dumps(_sanitize_for_export(row.get('response', {})), ensure_ascii=False),
        })
    return rows


def _build_reentry_blocks_rows(reentry_diag_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in reentry_diag_rows:
        if not (bool(row.get('cooldown_blocked')) or bool(row.get('recovery_blocked')) or not bool(row.get('final_decision_allow_true_false', True))):
            continue
        rows.append({
            'ts': row.get('ts', row.get('time', '')),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'price': _safe_float(row.get('price', 0.0)),
            'cooldown_blocked': bool(row.get('cooldown_blocked')),
            'recovery_blocked': bool(row.get('recovery_blocked')),
            'block_reason': row.get('final_reason', row.get('reason', '')),
            'last_exit_reason': row.get('last_exit_reason', ''),
            'last_trade_pnl': _safe_float(row.get('last_trade_pnl', 0.0)),
        })
    return rows


def _calc_trend_metrics(trades_export_rows: List[dict]) -> dict:
    ordered = sorted(trades_export_rows, key=lambda row: _safe_float(row.get('pnl', 0.0)), reverse=True)
    top5 = ordered[:5]
    top10 = ordered[:10]
    total_positive = sum(max(_safe_float(row.get('pnl', 0.0)), 0.0) for row in trades_export_rows)
    top10_positive = sum(max(_safe_float(row.get('pnl', 0.0)), 0.0) for row in top10)
    return {
        'top_5_pnl': round(sum(_safe_float(row.get('pnl', 0.0)) for row in top5), 6),
        'top_10_share_pct': round((top10_positive / max(total_positive, 1e-12)) * 100.0, 6) if total_positive > 0 else 0.0,
        'trades_with_2_units': len([row for row in trades_export_rows if _safe_int(row.get('units', 1), 1) >= 2]),
        'trades_with_4_units': len([row for row in trades_export_rows if _safe_int(row.get('units', 1), 1) >= 4]),
        'avg_hold_time_profitable': round(sum(_safe_int(row.get('duration_sec', 0), 0) for row in trades_export_rows if _safe_float(row.get('pnl', 0.0)) > 0) / max(1, len([1 for row in trades_export_rows if _safe_float(row.get('pnl', 0.0)) > 0])), 6),
    }


def _calc_qa_checks(trades_export_rows: List[dict], blocked_entries_rows: List[dict], stop_failures_rows: List[dict]) -> dict:
    trades_count = max(1, len(trades_export_rows))
    fast_trades = len([row for row in trades_export_rows if _safe_int(row.get('duration_sec', 0), 0) < 60])
    stop_confirmed = len([row for row in trades_export_rows if bool(row.get('stop_confirmed'))])
    fast_ratio = fast_trades / trades_count * 100.0
    loop_ratio = len(blocked_entries_rows) / trades_count * 100.0
    stop_confirm_ratio = stop_confirmed / trades_count * 100.0
    checks = {
        'fast_trades_lt_60sec_pct': round(fast_ratio, 4),
        'blocked_entries_pct_of_closed_trades': round(loop_ratio, 4),
        'stop_confirmed_pct': round(stop_confirm_ratio, 4),
        'stop_failures_count': len(stop_failures_rows),
    }
    fails = []
    if fast_ratio > 20.0:
        fails.append('fast_trades_gt_20pct')
    if loop_ratio > 10.0:
        fails.append('blocked_entries_gt_10pct_of_closed')
    if stop_confirm_ratio < 90.0:
        fails.append('stop_confirmed_lt_90pct')
    checks['pass'] = not fails
    checks['fail_reasons'] = fails
    return checks

def _build_export_dataset(snapshot: Optional[dict], cfg: Optional["BotConfig"]):
    runtime_state = _safe_json_load(STATE_FILE, {})
    positions_state = dict(runtime_state.get('positions', {}) or {})
    closed_state = list(runtime_state.get('closed_trades', []) or [])
    balance_history = list((snapshot or {}).get('balance_history') or runtime_state.get('balance_history', []) or [])
    summary_snapshot = dict(snapshot or {})
    settings = dict(summary_snapshot.get('settings') or {})
    analytics = dict(summary_snapshot.get('analytics') or {})
    open_positions = list(summary_snapshot.get('open_positions') or [])
    closed_rows = list(summary_snapshot.get('closed_trades') or closed_state)
    if not open_positions and positions_state:
        open_positions = list(positions_state.values())
    if not settings and cfg is not None:
        settings = {
            'account': 'Основной' if getattr(cfg, 'flag', '1') == '0' else 'Демо',
            'timeframe': getattr(cfg, 'timeframe', '—'),
            'trade_mode': getattr(cfg, 'trade_mode', 'auto'),
        }
    if not analytics and closed_rows:
        wins = sum(1 for row in closed_rows if _safe_float(row.get('pnl', 0.0)) > 0)
        losses = sum(1 for row in closed_rows if _safe_float(row.get('pnl', 0.0)) < 0)
        realized = sum(_safe_float(row.get('pnl', 0.0)) for row in closed_rows)
        analytics = {
            'closed_count': len(closed_rows),
            'wins': wins,
            'losses': losses,
            'winrate': (wins / len(closed_rows) * 100.0) if closed_rows else 0.0,
            'realized_pnl': realized,
            'open_pnl': sum(_safe_float(row.get('unrealized_pnl', 0.0)) for row in open_positions),
        }
    journal_rows = _read_jsonl_rows(POSITION_JOURNAL_FILE)
    engine_event_rows = _read_jsonl_rows(ENGINE_STATS_FILE)
    signal_audit_rows = _read_jsonl_rows(SIGNAL_AUDIT_FILE)
    position_snapshot_rows = _read_jsonl_rows(POSITION_SNAPSHOTS_FILE)
    system_health_rows = _read_jsonl_rows(SYSTEM_HEALTH_FILE)
    connectivity_rows = _read_jsonl_rows(CONNECTIVITY_LOG_FILE)
    pyramid_diag_rows = _read_jsonl_rows(PYRAMID_DIAGNOSTICS_FILE)
    reentry_diag_rows = _read_jsonl_rows(REENTRY_DIAGNOSTICS_FILE)
    breakout_quality_rows = _read_jsonl_rows(BREAKOUT_QUALITY_FILE)
    stop_engine_rows = _read_jsonl_rows(STOP_ENGINE_FILE)
    traceback_error_rows = _read_jsonl_rows(TRACEBACK_ERROR_FILE)
    filter_rows = [row for row in engine_event_rows if str(row.get('event') or '') == 'filter_diagnostics']

    trade_context_cache = {}
    trades_export_rows: List[dict] = []
    for row in closed_rows:
        context_path = Path(str(row.get('trade_context_file') or '').strip())
        context_payload = {}
        if context_path:
            key = str(context_path)
            if key not in trade_context_cache:
                trade_context_cache[key] = _safe_json_load(context_path, {}) if context_path.exists() else {}
            context_payload = trade_context_cache.get(key, {}) or {}
        metrics = _compute_mfe_mae_from_context(context_payload)
        trade_id = str(context_payload.get('trade_id') or row.get('trade_id') or _stable_trade_id(row.get('inst_id', ''), row.get('side', ''), row.get('time', '')))
        trades_export_rows.append({
            'trade_id': trade_id,
            'time': row.get('time', ''),
            'inst_id': row.get('inst_id', ''),
            'side': row.get('side', ''),
            'qty': _safe_float(row.get('qty', 0.0)),
            'entry_px': _safe_float(context_payload.get('entry_price', row.get('entry_px', 0.0))),
            'exit_px': _safe_float(row.get('exit_px', 0.0)),
            'pnl': _safe_float(row.get('pnl', 0.0)),
            'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
            'duration_sec': _safe_int(row.get('duration_sec', 0)),
            'units': _safe_int(row.get('units', 1), 1),
            'system_name': row.get('system_name', ''),
            'reason': row.get('reason', ''),
            'close_reason_code': _classify_reason_code(row.get('reason', '')),
            'entry_atr': _safe_float(context_payload.get('entry_atr', 0.0)),
            'initial_stop_price': _safe_float(context_payload.get('initial_stop_price', context_payload.get('start_stop_price', 0.0))),
            'final_stop_price': _safe_float(context_payload.get('final_stop_price', 0.0)),
            'peak_price': _safe_float(context_payload.get('peak_price', 0.0)),
            'trough_price': _safe_float(context_payload.get('trough_price', 0.0)),
            'peak_unrealized_pnl': _safe_float(context_payload.get('peak_unrealized_pnl', 0.0)),
            'channel_exit_level': _safe_float(context_payload.get('channel_exit_level', 0.0)),
            'planned_risk_pct': _safe_float(context_payload.get('planned_risk_pct', 0.0)),
            'risk_amount_usdt': _safe_float(context_payload.get('risk_amount_usdt', 0.0)),
            'risk_per_contract': _safe_float(context_payload.get('risk_per_contract', 0.0)),
            'position_notional_usdt': _safe_float(context_payload.get('position_notional_usdt', 0.0)),
            'mfe_abs': round(metrics['mfe_abs'], 8),
            'mfe_pct': round(metrics['mfe_pct'], 6),
            'mfe_r': round(metrics['mfe_r'], 6),
            'mae_abs': round(metrics['mae_abs'], 8),
            'mae_pct': round(metrics['mae_pct'], 6),
            'mae_r': round(metrics['mae_r'], 6),
            'entry_context_file': str(context_payload.get('entry_context_file', row.get('entry_context_file', ''))),
            'trade_context_file': str(context_path) if context_path else '',
            'stop_confirmed': bool(context_payload.get('stop_confirmed', row.get('stop_confirmed', False))),
            'stop_state': str(context_payload.get('stop_state', row.get('stop_state', ''))),
            'exchange_stop_status': str(context_payload.get('exchange_stop_status', '')),
            'position_health_state': str(context_payload.get('position_health_state', row.get('position_health_state', ''))),
            'block_reason': str(context_payload.get('pyramiding_block_reason', row.get('block_reason', ''))),
            'entry_distance_atr': _safe_float(context_payload.get('breakout_distance_atr', row.get('entry_distance_atr', 0.0))),
            'breakout_id': str(context_payload.get('breakout_id', '')),
        })

    equity_rows = [{
        'time': item.get('time', ''),
        'balance_total': _safe_float(item.get('balance_total', 0.0)),
        'balance_available': _safe_float(item.get('balance_available', 0.0)),
        'balance_used': _safe_float(item.get('balance_used', 0.0)),
    } for item in balance_history]

    entry_candidate_rows = _build_entry_candidate_rows(signal_audit_rows)
    lifecycle_rows = _build_position_lifecycle_rows(journal_rows, position_snapshot_rows)
    decision_rows = _build_decision_trace_rows(signal_audit_rows, engine_event_rows, journal_rows)
    execution_rows = _build_execution_log_rows(engine_event_rows, journal_rows)
    risk_rows = _build_risk_event_rows(engine_event_rows, filter_rows)
    sync_bootstrap_rows = _build_sync_bootstrap_rows(journal_rows)
    market_quality_rows = _build_market_quality_rows(filter_rows)
    open_endstate_rows = _build_open_positions_endstate_rows(open_positions)
    market_context_rows = _build_market_context_rows(trades_export_rows)
    trade_diagnostics_rows = _extract_trade_diagnostics(
        trades_export_rows,
        lifecycle_rows,
        stop_engine_rows,
        risk_rows,
    )
    trade_analysis_rows = _calc_trade_analysis_rows(
        trades_export_rows,
        lifecycle_rows,
        stop_engine_rows,
        risk_rows,
        entry_candidate_rows,
    )
    market_analysis_rows = _calc_market_analysis_rows(
        trades_export_rows,
        risk_rows,
        stop_engine_rows,
        entry_candidate_rows,
    )
    position_reconcile_rows = _build_position_reconcile_rows(open_positions)
    sync_drift_rows = _build_sync_drift_rows(open_positions)
    position_sync_status_rows = _build_position_sync_status_rows(open_positions)
    trend_capture_rows = _build_trend_capture_rows(trade_analysis_rows)
    position_stop_regime_rows = _build_position_stop_regime_rows(open_positions)
    position_runtime_regime_rows = _build_position_runtime_regime_rows(open_positions)
    trend_hold_analysis_rows = _build_trend_hold_analysis_rows(trend_capture_rows)
    blocked_entries_rows = _build_blocked_entries_rows(entry_candidate_rows)
    stop_failures_rows = _build_stop_failures_rows(stop_engine_rows)
    reentry_blocks_rows = _build_reentry_blocks_rows(reentry_diag_rows)
    trend_metrics = _calc_trend_metrics(trades_export_rows)
    qa_checks = _calc_qa_checks(trades_export_rows, blocked_entries_rows, stop_failures_rows)
    signal_funnel = _compute_signal_funnel(signal_audit_rows, engine_event_rows)
    reject_counter = Counter(row.get('reject_code') or _classify_reason_code(row.get('reason')) for row in entry_candidate_rows if str(row.get('stage') or '') == 'rejected')
    close_reason_counter = Counter(row.get('close_reason_code') or _classify_reason_code(row.get('reason')) for row in trades_export_rows)
    units_added = sum(1 for row in lifecycle_rows if str(row.get('event_type') or '') in {'ADD_UNIT', 'PYRAMID_ADD', 'pyramid_added'})
    stop_moves = sum(1 for row in lifecycle_rows if str(row.get('event_type') or '') in {'TRAIL_UPDATE', 'MOVE_STOP'})
    summary_payload = {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': APP_VERSION,
        'account': settings.get('account', '—'),
        'timeframe': settings.get('timeframe', getattr(cfg, 'timeframe', '—') if cfg is not None else '—'),
        'trade_mode': settings.get('trade_mode', getattr(cfg, 'trade_mode', 'auto') if cfg is not None else 'auto'),
        'balance_total': _safe_float((summary_snapshot or {}).get('balance_total', 0.0)),
        'balance_available': _safe_float((summary_snapshot or {}).get('balance_available', 0.0)),
        'balance_used': _safe_float((summary_snapshot or {}).get('balance_used', 0.0)),
        'open_positions_count': len(open_positions),
        'closed_trades_count': len(closed_rows),
        'realized_pnl': _safe_float(analytics.get('realized_pnl', 0.0)),
        'open_pnl': _safe_float(analytics.get('open_pnl', 0.0)),
        'winrate': _safe_float(analytics.get('winrate', 0.0)),
        'wins': _safe_int(analytics.get('wins', 0)),
        'losses': _safe_int(analytics.get('losses', 0)),
        'signal_funnel': signal_funnel,
        'signals_detected': len([row for row in entry_candidate_rows if bool(row.get('signal_detected'))]),
        'signals_rejected': int(reject_counter.total()),
        'units_added': units_added,
        'stop_moves': stop_moves,
        'execution_errors': len([row for row in execution_rows if not bool(row.get('success'))]),
        'pyramid_diagnostics_summary': {
            'attempts': len(pyramid_diag_rows),
            'added': len([row for row in pyramid_diag_rows if str(row.get('event') or '') == 'pyramid_added']),
            'blocked_by_reason': dict(Counter(str(row.get('reason_blocked') or '') for row in pyramid_diag_rows if str(row.get('reason_blocked') or ''))),
        },
        'reentry_diagnostics_summary': {
            'checks': len(reentry_diag_rows),
            'blocked_cooldown': len([row for row in reentry_diag_rows if bool(row.get('cooldown_blocked'))]),
            'blocked_recovery': len([row for row in reentry_diag_rows if bool(row.get('recovery_blocked'))]),
        },
        'breakout_quality_summary': {
            'rows': len(breakout_quality_rows),
            'minimal_mode_rows': len([row for row in breakout_quality_rows if str(row.get('entry_mode') or '') == 'minimal']),
        },
        'stop_engine_summary': {
            'rows': len(stop_engine_rows),
            'placed': len([row for row in stop_engine_rows if str(row.get('event') or '') == 'STOP_PLACED']),
            'moved': len([row for row in stop_engine_rows if str(row.get('event') or '') == 'STOP_MOVED']),
            'triggered': len([row for row in stop_engine_rows if str(row.get('event') or '') == 'STOP_TRIGGERED']),
            'errors': len([row for row in stop_engine_rows if str(row.get('event') or '') == 'STOP_ERROR']),
            'missing': len([row for row in stop_engine_rows if str(row.get('event') or '') == 'STOP_MISSING']),
        },
        'rejections_by_code': dict(reject_counter),
        'close_reasons_count': dict(close_reason_counter),
        'problem_symbols': sorted({row.get('inst_id', '') for row in risk_rows if row.get('inst_id')}),
        'early_exit_flags': len([row for row in trade_diagnostics_rows if bool(row.get('early_exit_flag'))]),
        'avg_early_exit_gap_pct': round((sum(_safe_float(row.get('early_exit_gap_pct', 0.0)) for row in trade_diagnostics_rows) / max(1, len(trade_diagnostics_rows))), 6),
        'avg_market_risk_score': round((sum(_safe_float(row.get('market_risk_score', 0.0)) for row in trade_diagnostics_rows) / max(1, len(trade_diagnostics_rows))), 4),
        'avg_trend_capture_ratio': round((sum(_safe_float(row.get('trend_capture_ratio', 0.0)) for row in trade_analysis_rows) / max(1, len(trade_analysis_rows))), 6),
        'avg_exit_efficiency': round((sum(_safe_float(row.get('exit_efficiency', 0.0)) for row in trade_analysis_rows) / max(1, len(trade_analysis_rows))), 6),
        'markets_traded': len([row for row in market_analysis_rows if _safe_int(row.get('trades_count', 0), 0) > 0]),
        'high_risk_markets': len([row for row in market_analysis_rows if _safe_float(row.get('market_risk_score', 0.0)) >= 5.0]),
        'sync_drift_events': len(sync_drift_rows),
        'ghost_positions': len([row for row in position_sync_status_rows if str(row.get('sync_status', '') or '') == 'POSITION_GHOST']),
        'positions_with_confirmed_stop': len([row for row in position_reconcile_rows if str(row.get('stop_state', '') or '') in {'ACTIVE', 'CONFIRMED'}]),
        'avg_realized_r': round((sum(_safe_float(row.get('realized_r', 0.0)) for row in trend_capture_rows) / max(1, len(trend_capture_rows))), 6),
        'avg_trend_move_r': round((sum(_safe_float(row.get('trend_move_r', 0.0)) for row in trend_capture_rows) / max(1, len(trend_capture_rows))), 6),
        'donchian_active_positions': len([row for row in position_stop_regime_rows if str(row.get('hybrid_stop_mode', '') or '') == 'DONCHIAN_ACTIVE']),
        'trend_hold_positions': len([row for row in position_runtime_regime_rows if str(row.get('trend_hold_state', '') or '') == 'TREND_HOLD']),
        'avg_retained_r_share': round((sum(_safe_float(row.get('retained_r_share', 0.0)) for row in trend_hold_analysis_rows) / max(1, len(trend_hold_analysis_rows))), 6),
        'sync_bootstrap_events': len(sync_bootstrap_rows),
        'market_quality_blocks': len(market_quality_rows),
        'trend_metrics': trend_metrics,
        'qa_checks': qa_checks,
        'blocked_entries_count': len(blocked_entries_rows),
        'stop_failures_count': len(stop_failures_rows),
        'reentry_blocks_count': len(reentry_blocks_rows),
        'traceback_errors_count': len(traceback_error_rows),
    }
    metadata_payload = {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': APP_VERSION,
        'settings': _sanitize_for_export(settings),
        'bot_config': _sanitize_for_export(asdict(cfg) if cfg is not None else {}),
        'strategy_config': _export_strategy_config(cfg),
        'current_run': 'from_start_to_export',
    }
    return {
        'settings': settings,
        'summary': summary_payload,
        'metadata': metadata_payload,
        'balance_timeline': equity_rows,
        'closed_trades': trades_export_rows,
        'open_positions_endstate': open_endstate_rows,
        'positions_lifecycle': lifecycle_rows,
        'entry_candidates': entry_candidate_rows,
        'decision_trace': decision_rows,
        'execution_log': execution_rows,
        'risk_events': risk_rows,
        'market_quality_analysis': market_quality_rows,
        'sync_bootstrap_log': sync_bootstrap_rows,
        'market_context_on_entry': market_context_rows,
        'trade_diagnostics': trade_diagnostics_rows,
        'trade_analysis': trade_analysis_rows,
        'market_analysis': market_analysis_rows,
        'position_reconcile_history': position_reconcile_rows,
        'position_sync_status': position_sync_status_rows,
        'position_stop_regime': position_stop_regime_rows,
        'position_runtime_regime': position_runtime_regime_rows,
        'trend_capture_analysis': trend_capture_rows,
        'trend_hold_analysis': trend_hold_analysis_rows,
        'sync_drift_events': sync_drift_rows,
        'system_health': system_health_rows,
        'connectivity_log': connectivity_rows,
        'connectivity_summary': summarize_connectivity_rows(connectivity_rows),
        'pyramid_diagnostics': pyramid_diag_rows,
        'reentry_diagnostics': reentry_diag_rows,
        'breakout_quality': breakout_quality_rows,
        'stop_engine': stop_engine_rows,
        'traceback_errors': traceback_error_rows,
        'blocked_entries': blocked_entries_rows,
        'stop_failures': stop_failures_rows,
        'reentry_blocks': reentry_blocks_rows,
        'open_positions': open_positions,
    }


def _write_export_mode(export_dir: Path, dataset: dict, mode: str) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    _write_json(export_dir / 'metadata.json', dataset['metadata'])
    _write_json(export_dir / 'summary.json', dataset['summary'])
    if mode != 'quick':
        _write_json(export_dir / 'connectivity_summary.json', dataset.get('connectivity_summary', {}))
        _write_jsonl(export_dir / 'connectivity_log.jsonl', dataset.get('connectivity_log', []))
    if mode == 'quick':
        _write_csv(export_dir / 'balance_timeline.csv', ['time', 'balance_total', 'balance_available', 'balance_used'], dataset['balance_timeline'])
        _write_csv(export_dir / 'closed_trades.csv', sorted({k for row in dataset['closed_trades'] for k in row.keys()} or {'trade_id'}), dataset['closed_trades'])
        _write_csv(export_dir / 'open_positions_endstate.csv', sorted({k for row in dataset['open_positions_endstate'] for k in row.keys()} or {'trade_id'}), dataset['open_positions_endstate'])
        return
    _write_csv(export_dir / 'balance_timeline.csv', ['time', 'balance_total', 'balance_available', 'balance_used'], dataset['balance_timeline'])
    for name in ['closed_trades', 'open_positions_endstate', 'positions_lifecycle', 'entry_candidates', 'decision_trace', 'execution_log', 'risk_events', 'market_quality_analysis', 'sync_bootstrap_log', 'market_context_on_entry', 'trade_diagnostics', 'trade_analysis', 'market_analysis', 'position_reconcile_history', 'position_sync_status', 'position_stop_regime', 'position_runtime_regime', 'trend_capture_analysis', 'trend_hold_analysis', 'sync_drift_events', 'system_health', 'connectivity_log', 'pyramid_diagnostics', 'reentry_diagnostics', 'breakout_quality', 'stop_engine', 'traceback_errors', 'blocked_entries', 'stop_failures', 'reentry_blocks']:
        rows = dataset[name]
        headers = sorted({k for row in rows for k in row.keys()} or {'timestamp'})
        _write_csv(export_dir / f'{name}.csv', headers, rows)
    _write_json(export_dir / 'open_positions_snapshot.json', {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(dataset['open_positions']),
        'positions': dataset['open_positions'],
    })
    _write_jsonl(export_dir / 'traceback_errors.jsonl', dataset.get('traceback_errors', []))
    secret_hits = _scan_export_files_for_secrets(export_dir)
    if secret_hits:
        _write_json(export_dir / 'secret_scan_alert.json', {'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'hits': secret_hits})

def build_analysis_export_bundle(ctx: ExportBundleContext, mode: str = 'full', snapshot: Optional[dict] = None, cfg: Optional["BotConfig"] = None) -> Path:
    _apply_context(ctx)
    mode = str(mode or 'full').lower()
    export_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dataset = _build_export_dataset(snapshot, cfg)
    if mode == 'hourly':
        hourly_dir = ANALYSIS_EXPORT_DIR / f'analysis_hourly_{export_ts}'
        hourly_dir.mkdir(parents=True, exist_ok=True)
        all_dts = []
        for key in ['positions_lifecycle', 'entry_candidates', 'decision_trace', 'execution_log', 'risk_events', 'system_health', 'connectivity_log', 'pyramid_diagnostics', 'reentry_diagnostics', 'breakout_quality', 'stop_engine', 'traceback_errors']:
            for row in dataset[key]:
                dt = _row_dt(row)
                if dt is not None:
                    all_dts.append(dt)
        for row in dataset['balance_timeline']:
            dt = _row_dt(row)
            if dt is not None:
                all_dts.append(dt)
        if not all_dts:
            all_dts = [datetime.now()]
        start_hour = min(all_dts).replace(minute=0, second=0, microsecond=0)
        end_hour = max(all_dts).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        created = 0
        hour = start_hour
        while hour < end_hour:
            nxt = hour + timedelta(hours=1)
            label = _hour_bucket_label(hour)
            hour_folder = hourly_dir / f'analysis_{label}'
            hour_dataset = {
                'metadata': dict(dataset['metadata']),
                'summary': dict(dataset['summary']),
                'balance_timeline': _rows_between(dataset['balance_timeline'], hour, nxt),
                'closed_trades': [row for row in dataset['closed_trades'] if (lambda dt: dt is not None and hour <= dt < nxt)(_parse_export_dt(row.get('time')))],
                'open_positions_endstate': [row for row in dataset['open_positions_endstate'] if _position_row_key(row) in {_position_row_key(r) for r in _rows_between(dataset['positions_lifecycle'], hour, nxt)}],
                'positions_lifecycle': _rows_between(dataset['positions_lifecycle'], hour, nxt),
                'entry_candidates': _rows_between(dataset['entry_candidates'], hour, nxt),
                'decision_trace': _rows_between(dataset['decision_trace'], hour, nxt),
                'execution_log': _rows_between(dataset['execution_log'], hour, nxt),
                'risk_events': _rows_between(dataset['risk_events'], hour, nxt),
                'market_context_on_entry': [row for row in dataset['market_context_on_entry'] if (lambda dt: dt is not None and hour <= dt < nxt)(_parse_export_dt(row.get('entry_time')))],
                'system_health': _rows_between(dataset['system_health'], hour, nxt),
                'connectivity_log': _rows_between(dataset['connectivity_log'], hour, nxt),
                'connectivity_summary': summarize_connectivity_rows(_rows_between(dataset['connectivity_log'], hour, nxt)),
                'pyramid_diagnostics': _rows_between(dataset['pyramid_diagnostics'], hour, nxt),
                'reentry_diagnostics': _rows_between(dataset['reentry_diagnostics'], hour, nxt),
                'breakout_quality': _rows_between(dataset['breakout_quality'], hour, nxt),
                'traceback_errors': _rows_between(dataset['traceback_errors'], hour, nxt),
                'open_positions': dataset['open_positions'],
            }
            hour_dataset['summary'] = dict(hour_dataset['summary'])
            hour_dataset['summary'].update({
                'hour_window_start': hour.strftime('%Y-%m-%d %H:%M:%S'),
                'hour_window_end': nxt.strftime('%Y-%m-%d %H:%M:%S'),
                'hour_closed_trades': len(hour_dataset['closed_trades']),
                'hour_signals': len(hour_dataset['entry_candidates']),
                'hour_decisions': len(hour_dataset['decision_trace']),
            })
            _write_export_mode(hour_folder, hour_dataset, 'full')
            _write_json(hour_folder / 'hour_summary.json', hour_dataset['summary'])
            last_pos = {}
            for row in hour_dataset['positions_lifecycle']:
                if str(row.get('event_type') or '') == 'SNAPSHOT':
                    last_pos[_position_row_key(row)] = row
            _write_json(hour_folder / 'state_snapshot.json', {
                'hour_window_start': hour.strftime('%Y-%m-%d %H:%M:%S'),
                'hour_window_end': nxt.strftime('%Y-%m-%d %H:%M:%S'),
                'open_positions': list(last_pos.values()),
            })
            zip_path = hourly_dir / f'analysis_{label}.zip'
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(hour_folder.iterdir()):
                    if file_path.is_file():
                        zf.write(file_path, arcname=file_path.name)
            created += 1
            hour = nxt
        _write_json(hourly_dir / 'night_summary.json', dataset['summary'])
        return hourly_dir
    export_dir = ANALYSIS_EXPORT_DIR / f'analysis_{mode}_{export_ts}'
    _write_export_mode(export_dir, dataset, mode)
    zip_path = ANALYSIS_EXPORT_DIR / f'analysis_{mode}_{export_ts}.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(export_dir.iterdir()):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.name)
    return zip_path
