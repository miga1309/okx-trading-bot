from app.runtime_support_parts.base import *
from app.runtime_support_parts.theme import *
from app.runtime_support_parts.logging_support import *

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




def _reconstruct_open_positions_from_lifecycle(lifecycle_rows: List[dict], closed_rows: List[dict], known_open_positions: List[dict]) -> List[dict]:
    known_by_trade: Dict[str, dict] = {}
    for row in (known_open_positions or []):
        trade_id = str(row.get('trade_id', '') or '').strip()
        if trade_id:
            known_by_trade[trade_id] = dict(row)

    closed_ids = {str(row.get('trade_id', '') or '').strip() for row in (closed_rows or []) if str(row.get('trade_id', '') or '').strip()}
    latest_by_trade: Dict[str, dict] = {}
    latest_by_inst_side: Dict[tuple, dict] = {}

    def _event_rank(event_type: str) -> int:
        mapping = {
            'OPEN': 1,
            'POSITION_OPENED': 1,
            'ADD_UNIT': 2,
            'PYRAMID_ADD': 2,
            'PYRAMID_ADDED': 2,
            'TRAIL_UPDATE': 3,
            'MOVE_STOP': 3,
            'SNAPSHOT': 4,
        }
        return mapping.get(str(event_type or '').upper(), 0)

    for row in sorted((lifecycle_rows or []), key=lambda r: (str(r.get('timestamp', '') or ''), _event_rank(r.get('event_type', '')))):
        event_type = str(row.get('event_type', '') or '').upper()
        trade_id = str(row.get('trade_id', '') or '').strip()
        inst_id = str(row.get('inst_id', '') or '').strip()
        side = str(row.get('side', '') or '').strip()
        key = (inst_id, side)
        if event_type == 'CLOSE':
            if trade_id:
                latest_by_trade.pop(trade_id, None)
                closed_ids.add(trade_id)
            latest_by_inst_side.pop(key, None)
            continue
        if event_type not in {'OPEN', 'POSITION_OPENED', 'ADD_UNIT', 'PYRAMID_ADD', 'PYRAMID_ADDED', 'TRAIL_UPDATE', 'MOVE_STOP', 'SNAPSHOT'}:
            continue
        candidate = {
            'trade_id': trade_id or str((known_by_trade.get(trade_id) or {}).get('trade_id', '') or ''),
            'inst_id': inst_id,
            'side': side,
            'entry_time': str((known_by_trade.get(trade_id) or {}).get('entry_time', '') or ''),
            'avg_px': _safe_float(row.get('avg_entry_price', 0.0)),
            'last_px': _safe_float(row.get('price', 0.0)),
            'stop_price': _safe_float(row.get('stop_price', 0.0)),
            'next_pyramid_price': _safe_float(row.get('next_unit_level', 0.0)),
            'units': _safe_int(row.get('units', 1), 1),
            'qty': _safe_float(row.get('qty_total', 0.0)),
            'unrealized_pnl': _safe_float(row.get('pnl_usd', 0.0)),
            'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
            'peak_unrealized_pnl': _safe_float(row.get('peak_unrealized_pnl', 0.0)),
            'peak_pnl_pct': _safe_float(row.get('mfe_pct', 0.0)),
            'atr': _safe_float(row.get('atr', 0.0)),
            'position_age_sec': _safe_int(row.get('position_age_sec', 0)),
            'close_pending': False,
            'timestamp': str(row.get('timestamp', '') or ''),
        }
        if trade_id:
            latest_by_trade[trade_id] = candidate
        latest_by_inst_side[key] = candidate

    reconstructed: Dict[str, dict] = {}
    for trade_id, row in latest_by_trade.items():
        if trade_id and trade_id not in closed_ids:
            reconstructed[trade_id] = row
    if not reconstructed:
        for row in latest_by_inst_side.values():
            trade_id = str(row.get('trade_id', '') or '').strip()
            if trade_id and trade_id in closed_ids:
                continue
            reconstructed[trade_id or f"{row.get('inst_id','')}|{row.get('side','')}"] = row

    ordered = sorted(reconstructed.values(), key=lambda r: str(r.get('timestamp', '') or ''))
    return [{k: v for k, v in row.items() if k != 'timestamp'} for row in ordered]


def _reconstruct_closed_trades_from_lifecycle(closed_rows: List[dict], lifecycle_rows: List[dict]) -> List[dict]:
    existing_ids = {str(row.get('trade_id', '') or '').strip() for row in (closed_rows or []) if str(row.get('trade_id', '') or '').strip()}
    opens: Dict[str, dict] = {}
    augmented = list(closed_rows or [])
    for row in sorted((lifecycle_rows or []), key=lambda r: str(r.get('timestamp', '') or '')):
        trade_id = str(row.get('trade_id', '') or '').strip()
        if not trade_id:
            continue
        event_type = str(row.get('event_type', '') or '').upper()
        if event_type in {'OPEN', 'POSITION_OPENED'}:
            opens[trade_id] = dict(row)
            continue
        if event_type == 'CLOSE' and trade_id not in existing_ids:
            opened = opens.get(trade_id, {})
            augmented.append({
                'trade_id': trade_id,
                'time': str(row.get('timestamp', '') or ''),
                'inst_id': str(row.get('inst_id', '') or opened.get('inst_id', '') or ''),
                'side': str(row.get('side', '') or opened.get('side', '') or ''),
                'qty': _safe_float(opened.get('qty_total', row.get('qty_total', 0.0))),
                'entry_px': _safe_float(opened.get('avg_entry_price', 0.0)),
                'exit_px': _safe_float(row.get('price', 0.0)),
                'pnl': _safe_float(row.get('pnl_usd', 0.0)),
                'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
                'duration_sec': _safe_int(row.get('position_age_sec', 0)),
                'units': _safe_int(row.get('units', opened.get('units', 1)), 1),
                'system_name': '',
                'reason': str(row.get('reason', '') or ''),
                'trade_context_file': '',
            })
            existing_ids.add(trade_id)
    return augmented
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


def _build_export_dataset(snapshot: Optional[dict], cfg: Optional["BotConfig"]):
    runtime_state = _safe_json_load(STATE_FILE, {})
    positions_state = {k: v for k, v in dict(runtime_state.get('positions', {}) or {}).items() if not is_hidden_instrument(k)}
    closed_state = [x for x in list(runtime_state.get('closed_trades', []) or []) if not is_hidden_instrument(x.get('inst_id'))]
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
    pyramid_diag_rows = _read_jsonl_rows(PYRAMID_DIAGNOSTICS_FILE)
    reentry_diag_rows = _read_jsonl_rows(REENTRY_DIAGNOSTICS_FILE)
    breakout_quality_rows = _read_jsonl_rows(BREAKOUT_QUALITY_FILE)
    stop_engine_rows = _read_jsonl_rows(STOP_ENGINE_FILE)
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
        })

    equity_rows = [{
        'time': item.get('time', ''),
        'balance_total': _safe_float(item.get('balance_total', 0.0)),
        'balance_available': _safe_float(item.get('balance_available', 0.0)),
        'balance_used': _safe_float(item.get('balance_used', 0.0)),
    } for item in balance_history]

    entry_candidate_rows = _build_entry_candidate_rows(signal_audit_rows)
    lifecycle_rows = _build_position_lifecycle_rows(journal_rows, position_snapshot_rows)
    closed_rows = _reconstruct_closed_trades_from_lifecycle(closed_rows, lifecycle_rows)
    decision_rows = _build_decision_trace_rows(signal_audit_rows, engine_event_rows, journal_rows)
    execution_rows = _build_execution_log_rows(engine_event_rows, journal_rows)
    risk_rows = _build_risk_event_rows(engine_event_rows, filter_rows)
    existing_trade_export_ids = {str(row.get('trade_id', '') or '').strip() for row in trades_export_rows if str(row.get('trade_id', '') or '').strip()}
    for row in closed_rows:
        trade_id = str(row.get('trade_id', '') or '').strip()
        if trade_id and trade_id not in existing_trade_export_ids:
            trades_export_rows.append({
                'trade_id': trade_id,
                'time': row.get('time', ''),
                'inst_id': row.get('inst_id', ''),
                'side': row.get('side', ''),
                'qty': _safe_float(row.get('qty', 0.0)),
                'entry_px': _safe_float(row.get('entry_px', 0.0)),
                'exit_px': _safe_float(row.get('exit_px', 0.0)),
                'pnl': _safe_float(row.get('pnl', 0.0)),
                'pnl_pct': _safe_float(row.get('pnl_pct', 0.0)),
                'duration_sec': _safe_int(row.get('duration_sec', 0)),
                'units': _safe_int(row.get('units', 1), 1),
                'system_name': row.get('system_name', ''),
                'reason': row.get('reason', ''),
                'close_reason_code': _classify_reason_code(row.get('reason', '')),
                'entry_atr': 0.0,
                'initial_stop_price': 0.0,
                'final_stop_price': 0.0,
                'peak_price': 0.0,
                'trough_price': 0.0,
                'peak_unrealized_pnl': 0.0,
                'channel_exit_level': 0.0,
                'planned_risk_pct': 0.0,
                'risk_amount_usdt': 0.0,
                'risk_per_contract': 0.0,
                'position_notional_usdt': 0.0,
                'mfe_abs': 0.0,
                'mfe_pct': 0.0,
                'mfe_r': 0.0,
                'mae_abs': 0.0,
                'mae_pct': 0.0,
                'mae_r': 0.0,
                'entry_context_file': '',
                'trade_context_file': str(row.get('trade_context_file', '') or ''),
            })
            existing_trade_export_ids.add(trade_id)
    reconstructed_open_positions = _reconstruct_open_positions_from_lifecycle(lifecycle_rows, closed_rows, open_positions)
    if len(reconstructed_open_positions) > len(open_positions):
        open_positions = reconstructed_open_positions
    open_endstate_rows = _build_open_positions_endstate_rows(open_positions)
    market_context_rows = _build_market_context_rows(trades_export_rows)
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
        'open_positions_count': len(open_endstate_rows),
        'closed_trades_count': len(trades_export_rows),
        'realized_pnl': _safe_float(analytics.get('realized_pnl', 0.0)),
        'open_pnl': _safe_float(analytics.get('open_pnl', sum(_safe_float(row.get('unrealized_pnl', 0.0)) for row in open_endstate_rows))),
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
        'market_context_on_entry': market_context_rows,
        'system_health': system_health_rows,
        'pyramid_diagnostics': pyramid_diag_rows,
        'reentry_diagnostics': reentry_diag_rows,
        'breakout_quality': breakout_quality_rows,
        'stop_engine': stop_engine_rows,
        'open_positions': open_positions,
    }


def _write_export_mode(export_dir: Path, dataset: dict, mode: str) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    _write_json(export_dir / 'metadata.json', dataset['metadata'])
    _write_json(export_dir / 'summary.json', dataset['summary'])
    if mode == 'quick':
        _write_csv(export_dir / 'balance_timeline.csv', ['time', 'balance_total', 'balance_available', 'balance_used'], dataset['balance_timeline'])
        _write_csv(export_dir / 'closed_trades.csv', sorted({k for row in dataset['closed_trades'] for k in row.keys()} or {'trade_id'}), dataset['closed_trades'])
        _write_csv(export_dir / 'open_positions_endstate.csv', sorted({k for row in dataset['open_positions_endstate'] for k in row.keys()} or {'trade_id'}), dataset['open_positions_endstate'])
        return
    _write_csv(export_dir / 'balance_timeline.csv', ['time', 'balance_total', 'balance_available', 'balance_used'], dataset['balance_timeline'])
    for name in ['closed_trades', 'open_positions_endstate', 'positions_lifecycle', 'entry_candidates', 'decision_trace', 'execution_log', 'risk_events', 'market_context_on_entry', 'system_health', 'pyramid_diagnostics', 'reentry_diagnostics', 'breakout_quality', 'stop_engine']:
        rows = dataset[name]
        headers = sorted({k for row in rows for k in row.keys()} or {'timestamp'})
        _write_csv(export_dir / f'{name}.csv', headers, rows)
    _write_json(export_dir / 'open_positions_snapshot.json', {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(dataset['open_positions']),
        'positions': dataset['open_positions'],
    })
    secret_hits = _scan_export_files_for_secrets(export_dir)
    if secret_hits:
        _write_json(export_dir / 'secret_scan_alert.json', {'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'hits': secret_hits})
