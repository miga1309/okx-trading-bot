from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

EXECUTION_RISK_WATCHLIST = {"ATOM-USDT-SWAP", "MINA-USDT-SWAP", "XSR-USDT-SWAP", "LINK-USDT-SWAP", "BREV-USDT-SWAP", "QTUM-USDT-SWAP", "TSLA-USDT-SWAP"}

@dataclass
class BotConfig:
    api_key: str
    secret_key: str
    passphrase: str
    flag: str = "1"  # 0 = main, 1 = demo
    timeframe: str = "15m"
    td_mode: str = "isolated"
    leverage: int = 5
    scan_interval_sec: int = 5
    position_check_interval_sec: int = 2
    balance_refresh_sec: int = 15
    risk_per_trade_pct: float = 1.0
    max_position_notional_pct: float = 3.5
    long_entry_period: int = 55
    short_entry_period: int = 20
    long_exit_period: int = 20
    short_exit_period: int = 10
    atr_period: int = 20
    atr_stop_multiple: float = 2.0
    add_unit_every_atr: float = 0.5
    max_units_per_symbol: int = 4
    trade_mode: str = "auto"
    snapshot_interval_sec: int = 2
    gui_refresh_ms: int = 1000
    flat_lookback_candles: int = 32
    min_channel_range_pct: float = 0.60
    min_atr_pct: float = 0.07
    min_body_to_range_ratio: float = 0.22
    min_efficiency_ratio: float = 0.10
    max_direction_flip_ratio: float = 0.82
    blacklist: List[str] = field(default_factory=lambda: ["BREV-USDT-SWAP"])
    execution_risk_watchlist: List[str] = field(default_factory=lambda: sorted(EXECUTION_RISK_WATCHLIST))
    execution_issue_repeats_for_quarantine: int = 2
    execution_quarantine_hours: int = 6
    execution_close_verify_delay_sec: float = 0.8
    execution_close_pending_retry_sec: int = 45

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    pyramid_second_unit_scale: float = 1.00
    pyramid_third_unit_scale: float = 1.00
    pyramid_fourth_unit_scale: float = 1.00
    pyramid_break_even_buffer_atr: float = 0.05
    pyramid_min_progress_atr: float = 0.25
    pyramid_min_body_ratio: float = 0.35
    pyramid_min_stop_distance_atr: float = 0.35
    breakout_buffer_atr: float = 0.03
    breakout_min_body_atr: float = 0.20
    breakout_close_near_extreme_ratio: float = 0.25
    breakout_min_range_expansion: float = 0.00
    breakout_max_prebreak_distance_atr: float = 0.45
    breakout_retest_invalid_ratio: float = 1.00
    breakout_volume_factor: float = 0.00
    breakout_max_distance_atr: float = 0.50
    preferred_breakout_distance_atr_min: float = 0.05
    preferred_breakout_distance_atr_max: float = 0.30
    flat_max_repeated_close_ratio: float = 0.84
    flat_max_inside_ratio: float = 0.90
    flat_max_wick_to_range_ratio: float = 0.88
    flat_min_channel_atr_ratio: float = 1.15
    flat_max_micro_pullback_ratio: float = 0.98
    structure_false_breakouts_penalty_from: int = 3
    structure_false_breakouts_hard_reject_from: int = 6
    structure_dense_base_as_penalty: bool = True
    structure_center_glue_as_penalty: bool = True
    cooldown_after_stop_bars: int = 4
    cooldown_min_seconds: int = 900
    cooldown_max_seconds: int = 21600
    reentry_recovery_atr: float = 1.10
    liquidity_max_spread_pct: float = 0.18
    liquidity_min_top_of_book_usdt: float = 1200.0
    liquidity_min_side_notional_usdt: float = 2500.0
    liquidity_min_24h_quote_volume: float = 2500000.0
    liquidity_filter_enabled: bool = True
    illiquid_block_hours: int = 2
    illiquid_soft_reject_cooldown_sec: int = 300
    illiquid_repeats_for_ban: int = 3
    max_open_positions_total: int = 16
    max_open_positions_per_side: int = 0
    rotation_enabled: bool = True
    rotation_max_units_threshold: int = 3
    rotation_require_negative_pnl: bool = True
    rotation_min_negative_pnl_pct: float = 0.0
    auto_cancel_pending_close_orders: bool = True
    signal_audit_enabled: bool = True
    signal_audit_top_n: int = 12
    signal_audit_log_all_rejections: bool = True
    diagnostic_near_pass_top_n: int = 10
    atr_warmup_extra_candles: int = 10
    signal_funnel_enabled: bool = True
    trade_ready_log_interval_sec: int = 900
    trade_ready_include_open_positions: bool = False
    scanner_enabled: bool = True
    scanner_chunk_size: int = 10
    scanner_history_days: int = 1
    scanner_rescan_interval_sec: int = 3600
    scanner_refresh_interval_sec: int = 6
    scanner_symbol_pause_sec: float = 0.05
    scanner_deep_checks_enabled: bool = True
    scanner_liquidity_snapshots: int = 3
    scanner_liquidity_pause_sec: float = 0.30
    scanner_orderbook_depth: int = 5
    scanner_profile: str = "balanced"
    scanner_long_tf: str = "15m"
    scanner_fast_tf: str = "5m"
    scanner_long_candles: int = 120
    scanner_fast_candles: int = 96
    scanner_popup_tf: str = "15m"
    scanner_popup_candles: int = 64
    scanner_trade_window_minutes: int = 15
    scanner_trade_limit: int = 100
    scanner_orderbook_snapshots: int = 1
    scanner_orderbook_pause_sec: float = 0.25
    scanner_recheck_after_sec: int = 86400
    scanner_status_ttl_sec: int = 90
    scanner_entry_force_refresh: bool = True
    scanner_bad_market_cooldown_sec: int = 1800
    scanner_failed_refresh_cooldown_sec: int = 120
    scanner_dead_atr_ratio_max: float = 0.0015
    scanner_dead_active_ratio_max: float = 0.20
    scanner_dead_spike_ratio_min: float = 4.0
    scanner_dead_follow_through_max: float = 0.5
    scanner_dead_trade_count_per_min_max: float = 6.0
    scanner_dead_zero_trade_ratio_min: float = 0.70
    scanner_dead_gap_p95_min_sec: float = 1800.0
    scanner_dead_spread_bps_min: float = 50.0
    scanner_dead_depth_usdt_max: float = 500.0
    scanner_saw_adx_max: float = 18.0
    scanner_saw_flip_rate_min: float = 0.58
    scanner_saw_efficiency_max: float = 0.20
    scanner_saw_false_breakout_min: float = 0.65
    scanner_saw_center_reversion_min: float = 0.35
    scanner_saw_autocorr_max: float = -0.05
    scanner_saw_adx_period: int = 14
    scanner_saw_er_window: int = 20
    scanner_ripping_atr_ratio_min: float = 0.0
    scanner_ripping_range_cv_min: float = 1.5
    scanner_ripping_jump_ratio_min: float = 15.0
    scanner_ripping_burst_trade_ratio_min: float = 0.75
    scanner_ripping_trade_size_cv_min: float = 3.5
    scanner_ripping_gap_p95_min_sec: float = 25.0
    scanner_ripping_spread_cv_min: float = 0.10
    scanner_ripping_depth_cv_min: float = 0.20
    scanner_ripping_depth_usdt_max: float = 1200.0
    scanner_ws_grace_period_sec: float = 180.0
    ws_enabled: bool = True
    ws_public_enabled: bool = True
    ws_private_enabled: bool = True
    ws_public_url: str = ""
    ws_private_url: str = ""
    ws_ping_interval_sec: float = 20.0
    ws_stale_after_sec: float = 35.0
    ws_subscribe_chunk: int = 20
    ws_books_enabled: bool = True
    ws_mark_price_enabled: bool = True
    ws_candles_enabled: bool = True
    ws_algo_orders_enabled: bool = True
    ws_book_channel: str = "books5"
    ws_book_depth_levels: int = 5
    ws_candle_timeframes: List[str] = field(default_factory=list)
    ws_shortlist_limit: int = 24
    ws_active_positions_limit: int = 16
    ws_book_stale_after_sec: float = 8.0
    ws_candle_stale_after_sec: float = 20.0
    ws_book_min_side_notional_usdt: float = 2500.0
    ws_book_max_spread_bps: float = 30.0
    ws_book_liquidity_hole_ratio: float = 0.22
    ws_book_ripping_spread_cv_min: float = 0.30
    ws_book_ripping_depth_cv_min: float = 0.45
    market_data_cache_ttl_sec: float = 12.0
    market_data_ticker_ttl_sec: float = 12.0
    market_data_candle_ttl_sec: float = 20.0
    market_data_worker_sleep_sec: float = 0.22
    market_data_log_every_sec: int = 60
    liquidity_trap_detector_enabled: bool = True
    liquidity_history_lookback_points: int = 8
    liquidity_history_min_stable_points: int = 4
    liquidity_history_max_age_sec: float = 40.0
    liquidity_history_collapse_ratio: float = 0.35
    liquidity_history_median_ratio: float = 0.60
    liquidity_history_spread_blowout_mult: float = 1.8
    trend_stop_activation_r: float = 0.90
    trend_stop_peak_atr_multiple: float = 1.30
    trend_stop_peak_atr_multiple_after_4_units: float = 1.20
    trend_stop_max_pullback_from_peak_r: float = 0.65
    trend_stop_min_locked_r: float = 0.60
    trend_stop_use_peak_pullback_exit: bool = False
    disable_trailing_on_entry_bar: bool = True
    breakeven_enabled: bool = False
    breakeven_min_hold_bars: int = 1
    breakeven_min_profit_atr: float = 0.8
    breakeven_min_locked_r: float = 0.5
    minimal_turtle_entry_mode: bool = True
    exchange_protective_stop_enabled: bool = True
    exchange_stop_sync_interval_sec: int = 30
    exchange_stop_min_move_atr: float = 0.15
    exchange_stop_min_move_pct: float = 0.0002
    exchange_stop_retry_attempts: int = 2
    exchange_stop_retry_delay_sec: float = 0.35
    exchange_stop_action_cooldown_sec: float = 2.5
    exchange_stop_snapshot_ttl_sec: float = 1.0
    bootstrap_stop_buffer_pct: float = 0.07
    initial_stop_abort_failures: int = 4
    stop_health_missing_confirmations: int = 3
    stop_health_confirmations_for_atr_switch: int = 2
    reentry_cooldown_bars: int = 3
    protective_reentry_cooldown_bars: int = 5
    same_price_reentry_atr: float = 0.20
    max_entry_distance_atr_hard: float = 1.50
    max_breakout_body_atr: float = 3.50
    stop_confirm_timeout_sec: float = 3.0
    initial_stop_verify_delay_sec: float = 8.0
    initial_stop_verify_attempts: int = 10
    positions_snapshot_ttl_sec: float = 4.0
    account_snapshot_ttl_sec: float = 10.0
    post_entry_recovery_sec: float = 20.0
    missing_exchange_finalize_count: int = 3
    initial_stop_verify_delay_between_attempts_sec: float = 0.4
    loss_streak_limit: int = 3
    quarantine_minutes: int = 60
    early_invalid_bars: int = 0
    early_invalid_move_atr: float = 0.0

@dataclass
class PendingEntry:
    pending_entry_id: str
    inst_id: str
    side: str
    strategy_tag: str
    planned_qty: float
    planned_entry_price: float
    filled_qty_current: float = 0.0
    avg_fill_price_current: float = 0.0
    entry_order_id: str = ""
    execution_mode: str = "market"
    created_at: str = ""
    status: str = "NEW"
    expected_atr: float = 0.0
    expected_stop_price: float = 0.0
    liquidity_check_result: str = ""
    retry_count: int = 0
    timeout_at: str = ""
    max_slippage_pct: float = 0.0
    planned_unit_count: int = 1

@dataclass
class PositionState:
    inst_id: str
    side: str  # long / short
    qty: float
    avg_px: float
    last_px: float
    unrealized_pnl: float
    margin: float
    atr: float
    stop_price: float
    next_pyramid_price: float
    entry_time: str
    base_unit_qty: float = 0.0
    units: int = 1
    system_name: str = ""
    entry_period: int = 0
    exit_period: int = 0
    signal_time: str = ""
    entry_context_file: str = ""
    initial_stop_price: float = 0.0
    bootstrap_stop_price: float = 0.0
    peak_price: float = 0.0
    trough_price: float = 0.0
    peak_unrealized_pnl: float = 0.0
    peak_pnl_pct: float = 0.0
    trade_id: str = ""
    planned_risk_pct: float = 0.0
    risk_amount_usdt: float = 0.0
    risk_per_contract: float = 0.0
    position_notional_usdt: float = 0.0
    close_pending: bool = False
    close_requested_at: str = ""
    close_attempts: int = 0
    last_close_error: str = ""
    missing_on_exchange_count: int = 0
    missing_on_exchange_since: str = ""
    missing_on_exchange_last_seen_price: float = 0.0
    execution_risk_score: float = 0.0
    trailing_activated_at: str = ""
    breakeven_activated_at: str = ""
    exchange_stop_algo_id: str = ""
    exchange_stop_price: float = 0.0
    exchange_stop_qty: float = 0.0
    exchange_stop_full_position: bool = False
    exchange_stop_last_update: str = ""
    exchange_stop_status: str = ""
    exchange_stop_last_sync_ts: float = 0.0
    exchange_stop_last_error_code: str = ""
    exchange_stop_last_error_msg: str = ""
    exchange_stop_trigger_type: str = "mark"
    last_requested_stop_px: float = 0.0
    last_confirmed_stop_px: float = 0.0
    stop_last_action_ts: float = 0.0
    stop_action_in_flight: bool = False
    stop_action_kind: str = ""
    stop_action_target_px: float = 0.0
    stop_action_started_ts: float = 0.0
    stop_snapshot_cache_ts: float = 0.0
    stop_snapshot_cache_rows: List[dict] = field(default_factory=list)
    exchange_stop_last_update_method: str = ""
    exchange_stop_desync: bool = False
    exchange_stop_desync_reason: str = ""
    stop_recovery_in_progress: bool = False
    stop_recovery_started_ts: float = 0.0
    stop_recovery_failures: int = 0
    stop_recovery_attempts: int = 0
    initial_stop_verified: bool = False
    initial_stop_verify_failures: int = 0
    initial_stop_set_ts: float = 0.0
    initial_stop_verify_due_ts: float = 0.0
    stop_strategy_last_candle_ts: int = 0
    pyramid_strategy_last_candle_ts: int = 0
    stop_health_last_check_ts: float = 0.0
    local_protective_exit_pending: bool = False
    local_protective_exit_reason: str = ""
    planned_entry_px: float = 0.0
    actual_entry_px: float = 0.0
    entry_slippage_pct: float = 0.0
    entry_execution_mode: str = "market"
    stop_state: str = "UNVERIFIED"
    stop_verified_at: str = ""
    position_health_state: str = "HEALTHY"
    pyramiding_block_reason: str = ""
    active_stop_mode: str = "BOOTSTRAP"
    desired_stop_mode: str = "BOOTSTRAP"
    stop_mode_since_ts: float = 0.0
    stop_transition_reason: str = ""
    stop_health_confirm_count: int = 0
    stop_health_missing_count: int = 0
    stop_attach_attempts: int = 0
    breakout_id: str = ""
    breakout_level: float = 0.0
    breakout_candle_ts: str = ""
    breakout_distance_atr: float = 0.0
    breakout_body_atr: float = 0.0
    state_tag: str = "ACTIVE"
    entry_recovery_until_ts: float = 0.0
    entry_recovery_started_ts: float = 0.0

@dataclass
class ClosedTrade:
    time: str
    inst_id: str
    side: str
    qty: float
    entry_px: float
    exit_px: float
    pnl: float
    pnl_pct: float
    units: int
    system_name: str
    reason: str
    duration_sec: int = 0
    trade_context_file: str = ""
    trade_id: str = ""
    stop_confirmed: bool = False
    stop_state: str = ""
    position_health_state: str = ""
    block_reason: str = ""
    entry_distance_atr: float = 0.0
