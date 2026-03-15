
# === v074 DONCHIAN BREAKOUT FIX ======================================
# Turtle breakout must compare the signal candle against a channel
# built ONLY from previous candles (exclude signal candle).
# Also late breakout check should use previous CLOSE not HIGH/LOW.

def compute_donchian_channel(highs, lows, period):
    if len(highs) < period + 1:
        return None, None
    upper = max(highs[-(period+1):-1])
    lower = min(lows[-(period+1):-1])
    return upper, lower

def is_fresh_breakout(prev_close, upper, lower, direction):
    if direction == "long":
        return prev_close <= upper
    if direction == "short":
        return prev_close >= lower
    return False

# =====================================================================

# ============================================================
# OKX Turtle Bot
# Version: v078_phased_profit_diagnostics
# Date: 2026-03-15
#
# Changelog v078_phased_profit_diagnostics:
# - Fixed pyramid logic: add-unit now places a real same-side add order instead of going through close/finalize flow
# - Added phased diagnostics for pyramid blocking, re-entry checks and breakout quality to analysis exports
# - Slightly tightened profit protection on developed trends without disabling minimal Turtle entry mode
#
# Changelog v077_2_analysis_export_state_fix:
# - Fixed strategy-cycle crash in _save_state() by rebuilding visible open/closed collections before minute diagnostics logging
# - Kept the v077 analysis dialog and export modes intact while stabilizing runtime snapshots and system health logging
#
# Changelog v076_minimal_breakout_filters:\n# - Added two minimal anti-noise Turtle filters: close must hold beyond Donchian by 0.10 ATR and channel width must be at least 0.50 ATR\n# - Fresh breakout check in minimal mode now uses previous candle CLOSE instead of HIGH/LOW to avoid overblocking\n# - Fixed exported/app version to v076 and switched UI loader to ui_layout_v076\n#\n# Previous changelog:\n# Changelog v075_live_open_position_popup:
# - Open-position popup now loads current live candles instead of showing only the saved entry snapshot chart
# - Preserved entry context cards while switching the main chart in the popup to the current market state
# - Switched UI loader to ui_layout_v076
#
# Previous changelog:
# Changelog v074_informative_trade_popups:
# - Switched entry selection to a minimal Turtle mode: remove flat, volatility, trend and structure gating from new entries
# - Simplified breakout confirmation to classic Donchian logic on the last closed candle without body/close-quality overfilters
# - Kept only core protections: known problem instruments, cooldowns, profitable Turtle-20 skip rule and basic market-sanity checks
#
# Previous changelog:
# Changelog v071_timeframe_filter_profiles:
# - Added dedicated entry/filter profiles for 1m, 5m, 15m, 30m, 1H and 4H with separate volatility, flat, breakout and trend thresholds
# - Reworked liquidity profiles so each timeframe uses its own realistic market-quality requirements instead of one shared compromise
# - Added startup logging of the active timeframe filter profile for easier overnight diagnostics and tuning
#
# Previous changelog:
# Changelog v070_header_mode_collapsible_radar:
# - Moved UI MODE selector into the header to the right of UPTIME and removed it from Command Deck
# - Made Market Radar collapsible and collapsed by default to free vertical space for the terminal
# - Tightened Equity Pulse layout so the chart fits cleanly inside its panel
# - Softened 1m entry filters again (flat, liquidity, breakout buffer) so valid signals reach candidate stage more often
#
# Previous changelog:
# Changelog v068_available_markets_risk_radar:
# - Added explicit Available Markets metric in Risk Radar: how many pairs remain tradable after active bans/blocks
# - Separated Available Markets from READY count so GUI shows both universe-after-bans and truly entry-ready pairs
# - Switched UI loader to ui_layout_v068 and kept Balance Hub free of the duplicate formula row
#
# Previous changelog:
# Changelog v067_gui_terminal_popup_refresh:
#
# Changelog v067_gui_terminal_popup_refresh:
# - Softened ATR / flat gates again for 5m crypto so valid markets reach candidate stage more often
# - Added trade-ready universe metrics, periodic 15-minute logging, and exportable diagnostics for blocked vs available instruments
# - Surfaced signal-funnel stats in snapshots so GUI and exports can show where the strategy is dying
# - Unified Equity Curve styling with Market Radar green neon and hid the duplicate Balance Hub formula row
#
# Previous changelog:
# Changelog v064_filter_quality_rebalance:
# - Softened flat/structure over-filtering while keeping hard blocks for truly dead or toxic markets
# - Added hard rejection for late breakouts and improved breakout-candle quality requirements
# - Delayed break-even / trailing activation so new positions survive the entry candle and first normal pullback
# - Preserved factual entry price in trade exports and lifecycle context for cleaner post-test analytics
#
# Previous changelog:
# Changelog v063_filter_rebalance:
#
# Changelog v063_filter_rebalance:
# - Rebalanced 5m entry filters after overnight analysis export showed heavy over-filtering
# - Lowered the minimum ATR gate and softened dead-market thresholds to admit more valid breakouts
# - Removed the most aggressive flat-market blockers (repeated closes, inside bars, tiny bodies, micro-pullbacks)
# - Kept structure-risk protection while making the flat filter focus on truly dead or noisy ranges
# - Preserved the current v062_5 single-line Risk Radar UI module binding
#
# Previous changelog:
# Changelog v061_1:
# - Fixed Reload UI logging bridge by restoring a persistent _append_log_line adapter in MainWindow
# - Synced START/STOP button state with the real running engine after live UI rebuild
# - Hardened log appends during UI teardown/rebuild so Reload UI is fully seamless
#
# Previous changelog:
# Changelog v061:
# - Added a Reload UI button in the terminal header for safe live interface rebuilds
# - MainWindow now captures and restores key UI state when rebuilding the visual layer
# - UI loader now supports importlib.reload() and controlled teardown/rebuild without stopping the engine
#
# Previous changelog:
# Changelog v060:
# - Extracted the main GUI layout into external module ui_layout_v060.py as groundwork for hot-reloadable UI
# - MainWindow now builds the terminal through a UI dependency bridge instead of hardcoded in-file layout
# - Preserved v059 trading logic and security/export fixes while preparing v061 Reload UI header action
#
# Previous changelog:
# Changelog v059:
# - Removed the leverage control from Command Deck and fixed leverage to the configured default
# - Replaced separate START/STOP controls with one stateful toggle button
# - Removed duplicate account/timeframe cards from Analytics Matrix
# - Simplified Balance Hub and enlarged the lower trading tabs for FullHD work
# - Rebalanced vertical layout so the trading desk is much more visible
#
# Previous changelog:
# Changelog v057:
# - Tightened Turtle entry logic for 5m testing: breakout buffer, trend filter, volatility gate and smarter cooldown reuse
# - Enabled liquidity filter by default and reused existing flat/structure diagnostics before entry
# - Preserved v056 GUI and popup dialogs while improving candidate quality for further testing
#
# Previous changelog:
# Changelog v056:
# - Refined Market Radar into a clearer candidate/watch/risk scanner with candidate-aware statuses
# - Upgraded Turtle Signal Center to explain breakout, trend/ATR, liquidity and entry status more clearly
# - Kept popup entry/exit dialogs and prepared the new GUI to restyle them in later versions
#
# Previous changelog:
# Changelog v054_1_cyber_terminal_fullhd_patch:
# - Tightened FullHD vertical proportions so Command Deck action buttons stay visible at 1920x1080
# - Reduced header and panel spacing, lowered action-button heights, and slimmed the bottom glow band
# - Rebalanced main screen stretch factors to give more height to the three-column terminal area
# - Kept the restored branding: CYBERPUNK QUANT TRADING TERMINAL
# - Corrected displayed version strings to v054_1 across window title and header
#
# Previous changelog:
# Changelog v050_neon_panel_terminal:
# - Added live system health chips in the terminal header for API, ENGINE, STRATEGY and OKX
# - Promoted the cyber header into a richer operations bar with live status telemetry
# - Retained FullHD animated grid, radar, sparklines and neon flow band while keeping the trading engine intact
#
# Previous changelog:
# Changelog v049_real_cyber_terminal:
# - Added animated trading-grid background, radar sweep, pulsing turtle glyph and livelier market sparklines
# - Added animated scan/glow behavior in the lower neon flow band
#
# Previous changelog:
# Changelog v047_cyber_terminal:
# - Stabilized the v046 cyberpunk GUI on a working MainWindow base
# - Added custom neon radar and turtle glyph widgets to make the terminal closer to the approved mockup
# - Enhanced header, cards, buttons and panel styling for a more premium synthwave terminal look
# - Kept trading logic in the same file for safety; GUI/engine separation is planned as the next step
#
# Previous changelog:
# Changelog v046:
# - Rebuilt the GUI into a Cyberpunk Quant Trading Terminal layout with synthwave header and 1600x900 default size
# - Added dedicated panels: Balance Hub, Risk Radar, Market Radar, Turtle Signal Center and Activity Feed
# - Reorganized controls and analytics into a three-column command-center layout closer to the approved mockup
#
# Previous changelog:
# Changelog v043:
# - Expanded execution-risk monitoring to ATOM, MINA, XSR, LINK, BREV, QTUM and TSLA while keeping only USDC hard-banned
# - Added a liquidity-trap detector that studies recent top-of-book history before entry
# - Export/runtime diagnostics now capture unstable depth spikes instead of relying only on a single snapshot
#
# Previous changelog:
# Changelog v042_1:
# - Removed LINK, BREV, QTUM and TSLA from the hard-ban/problem lists
# - Left only ATOM and MINA in execution-risk monitoring for current testing
# - Kept exchange-driven compliance blocking intact while reducing manual pre-bans
#
# Previous changelog:
# Changelog v042:
# - Added execution-risk monitor for thin-book instruments like ATOM and MINA during demo-stage testing
# - Close requests are now verified against exchange positions before local close is recorded
# - Added temporary quarantine and diagnostics for markets with repeated entry-liquidity or exit-execution failures
# - Added execution-risk watchlist instead of hard-banning newly discovered suspect instruments before v1.0
#
# Previous changelog:
# Changelog v041:
# - Added the "Сдать анализы" button that builds a compact diagnostic ZIP for chat upload
# - Export now includes summary, trades, position journal, equity curve, engine events, signal audit and open-position snapshot
# - Added dedicated position journal logging for entries, stop tightening, unit adds and exits to improve post-test analysis
# - Reset теста now also clears analysis session artifacts and the position journal
#
# Previous changelog:
# Changelog v039:
# - Reworked trailing stop logic so it tightens from the best favorable price, not only from the last price snapshot
# - Added persistent peak/trough tracking for every position and profit-lock floors after trend development
# - Added trend-protection exit on deep pullback from peak R to reduce cases where a strong open trend turns into a losing close
# - Synced new trailing fields through exchange sync, state save/load, and trade lifecycle context
#
# Previous changelog:
# Changelog v038:
# - Added Telegram photo delivery of the main UI window every 15 minutes while the bot is running
# - Added periodic full-window screenshot capture from the GUI thread and delivery through Telegram bot
# - Increased main window height so the open-positions table can display 16 rows more comfortably
#
# Previous changelog:
# Changelog v037_1:
# - Added QTUM-USDT-SWAP and TSLA-USDT-SWAP to the same hidden/blocked lists as LINK and BREV
# - Suppressed these instruments in UI tables/log filtering just like existing problematic close-order symbols
#
# Previous changelog:
# Changelog v036:
# - Added position rotation when a new entry appears but the total slot limit is already reached
# - Rotation closes the weakest losing position with units below the max cap and opens the new candidate in its place
# - Rotation never selects the same instrument as the incoming candidate and writes dedicated audit/stats events
#
# Previous changelog:
# Changelog v035_1:
# - Adapted liquidity filter to each timeframe with dedicated thresholds for spread, top-of-book, side notional and 24h quote volume
# - Added liquidity profile diagnostics so audit/rejections show active per-timeframe limits
# - Liquidity score normalization now uses the active timeframe profile instead of static base thresholds
#
# Previous changelog:
# Changelog v034:
# - Added detailed signal-audit log for every scan cycle with rejection reasons, rankings and final entry decisions
# - Entry selection moved closer to classic Turtle: only fresh channel breakouts on the last closed candle are accepted
# - Candidate ranking now penalizes recently traded instruments and logs per-symbol diagnostics for analysis
# - Increased total open-position limit from 8 to 16
#
# Previous changelog:
# Changelog v033:
# - Added signal queue for each scan cycle: engine now collects all valid candidates first
# - Candidate queue is prioritized by Turtle system, breakout strength and liquidity before opening
# - Removed per-side open-position limit (4 long / 4 short); only total limit remains if configured
# - Added "Reset теста" button: stops bot, tries to close demo/live SWAP positions, clears local state/logs/contexts
#
# Previous changelog:
# Changelog v032_4:
# - Open-position entry context chart now shows Donchian curve for active side
# - Highlighted last 20/55 candles window for active Turtle system
# - Added colored LONG/SHORT header badge in open-position context dialog
#
# Previous changelog:
# Changelog v032_3:
# - Added independent balance poller that records account equity on its own interval
# - Main balance chart now shows real account equity instead of derived intraday PnL curve
# - Snapshot balances now come from the dedicated equity poller, decoupled from engine/snapshot timing
#
# Previous changelog:
# Changelog v032_2:
# - Reworked trade/context charts: event markers replace most helper lines
# - Added lifecycle segment highlight between ENTRY and EXIT
# - Shortened labels to E / A2 / A3 / A4 / X for better readability
# - Reduced chart clutter by keeping only key operational levels
#
# Previous changelog:
# Changelog v032:
# - Added trade lifecycle viewer for closed trades with double-click opening
# - Saved lifecycle context JSON for closed trades with entry, add, and exit markers
# - Added unified lifecycle candlestick chart covering entry to exit on one timeline
#
# Previous changelog:
# Changelog v031:
# - Added asynchronous market-data worker with shared ticker/candle cache
# - Engine now reuses prefetched market data before falling back to direct OKX requests
# - Prioritized cache refresh for open positions to reduce GUI and strategy lag
# - Added cache stats to snapshots for easier monitoring
#
# Previous changelog:
# Based on: main_v029_1.py
#
# Changelog:
# - Fixed open-position context handler: now opens EntryContextDialog instead of plain QMessageBox
# - Restored actual candlestick chart rendering in the entry-context popup
# - Kept all v029_1 layout and chart-area visibility fixes
# ============================================================

import csv
import importlib
import json
import logging
import math
import os
import sys
import threading
import time
import zipfile
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter, deque, defaultdict
import statistics
import traceback

from dotenv import load_dotenv
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPoint, QRect, QPointF, Qt, QThread, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPolygon, QPalette, QBrush, QRadialGradient, QLinearGradient, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QDialog,
    QSpinBox,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QSizePolicy,
)

import okx.Account as Account
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.Trade as Trade

from telegram_notifier import TelegramNotifier


class MarketDataCache:
    def __init__(self, gateway: "OkxGateway", cfg: BotConfig, log_callback=None):
        self.gateway = gateway
        self.cfg = cfg
        self.log_callback = log_callback
        self.lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.ticker_cache: Dict[str, dict] = {}
        self.ticker_ts: Dict[str, float] = {}
        self.candles_cache: Dict[tuple[str, str], List[List[float]]] = {}
        self.candles_ts: Dict[tuple[str, str], float] = {}
        self.ticker_history: Dict[str, deque] = {}
        self.error_count = 0
        self.last_error = ""
        self.last_cycle_at: Optional[float] = None
        self.last_log_at = 0.0
        self.fetch_count = 0

    def _log(self, message: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(message)
            except Exception:
                pass

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="MarketDataCache", daemon=True)
        self.thread.start()
        self._log("Асинхронный market-data worker запущен")

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.thread = None

    def _needed_candles_limit(self) -> int:
        base = max(
            int(getattr(self.cfg, "long_entry_period", 55) or 55),
            int(getattr(self.cfg, "short_entry_period", 20) or 20),
            int(getattr(self.cfg, "long_exit_period", 20) or 20),
            int(getattr(self.cfg, "short_exit_period", 10) or 10),
            int(getattr(self.cfg, "atr_period", 20) or 20),
            int(getattr(self.cfg, "flat_lookback_candles", 32) or 32),
            80,
        )
        return base + 8

    def _prioritized_instruments(self) -> List[str]:
        swap_ids = list(getattr(self.gateway, "swap_ids", []) or [])
        engine = getattr(self.gateway, "engine_ref", None)
        open_ids: List[str] = []
        blocked: set[str] = set()
        if engine is not None:
            try:
                open_ids = list(getattr(engine, "position_state", {}).keys())
                blocked = set(getattr(engine, "blocked_instruments", {}).keys())
            except Exception:
                open_ids = []
                blocked = set()
        seen = set()
        ordered: List[str] = []
        for inst_id in open_ids + swap_ids:
            if not inst_id or inst_id in seen or inst_id in blocked or is_hidden_instrument(inst_id):
                continue
            if inst_id in getattr(self.cfg, "blacklist", []):
                continue
            seen.add(inst_id)
            ordered.append(inst_id)
        return ordered

    def _run(self) -> None:
        while self.running:
            ordered = self._prioritized_instruments()
            limit = self._needed_candles_limit()
            bar = self.cfg.timeframe
            now = time.time()
            ttl = max(1.0, float(getattr(self.cfg, "market_data_cache_ttl_sec", 4.0) or 4.0))
            fetched_this_cycle = 0

            for inst_id in ordered:
                if not self.running:
                    break
                try:
                    ticker_fresh = (now - self.ticker_ts.get(inst_id, 0.0)) < ttl
                    candles_key = (inst_id, bar)
                    candles_fresh = (now - self.candles_ts.get(candles_key, 0.0)) < ttl
                    if not ticker_fresh:
                        ticker = self.gateway.fetch_ticker_data(inst_id)
                        self.put_ticker(inst_id, ticker)
                        fetched_this_cycle += 1
                    if not candles_fresh:
                        candles = self.gateway.fetch_candles(inst_id, bar, limit)
                        if candles:
                            self.put_candles(inst_id, bar, candles)
                            fetched_this_cycle += 1
                except Exception as exc:
                    self.error_count += 1
                    self.last_error = str(exc)
                time.sleep(max(0.02, float(getattr(self.cfg, "market_data_worker_sleep_sec", 0.12) or 0.12)))

            self.last_cycle_at = time.time()
            self.fetch_count += fetched_this_cycle
            log_every = max(10, int(getattr(self.cfg, "market_data_log_every_sec", 60) or 60))
            if self.last_cycle_at - self.last_log_at >= log_every:
                self.last_log_at = self.last_cycle_at
                self._log(
                    f"Market-data worker: instruments={len(ordered)}, fetched={fetched_this_cycle}, "
                    f"ticker_cache={len(self.ticker_cache)}, candle_cache={len(self.candles_cache)}, errors={self.error_count}"
                )
            if not ordered:
                time.sleep(0.25)

    def put_ticker(self, inst_id: str, ticker: dict) -> None:
        now_ts = time.time()
        snap = dict(ticker)
        bid_px = float(snap.get("bidPx") or 0.0)
        ask_px = float(snap.get("askPx") or 0.0)
        bid_sz = float(snap.get("bidSz") or 0.0)
        ask_sz = float(snap.get("askSz") or 0.0)
        mid = ((bid_px + ask_px) / 2.0) if bid_px > 0 and ask_px > 0 else 0.0
        spread_pct = (((ask_px - bid_px) / max(mid, 1e-12)) * 100.0) if mid > 0 else 0.0
        hist_item = {
            "ts": now_ts,
            "bid_px": bid_px,
            "ask_px": ask_px,
            "bid_sz": bid_sz,
            "ask_sz": ask_sz,
            "mid": mid,
            "spread_pct": spread_pct,
            "best_bid_notional": bid_px * bid_sz,
            "best_ask_notional": ask_px * ask_sz,
            "best_side_notional": min(bid_px * bid_sz, ask_px * ask_sz),
        }
        history_limit = max(6, int(getattr(self.cfg, "liquidity_history_lookback_points", 8) or 8) + 4)
        with self.lock:
            self.ticker_cache[inst_id] = snap
            self.ticker_ts[inst_id] = now_ts
            history = self.ticker_history.get(inst_id)
            if history is None or getattr(history, "maxlen", 0) != history_limit:
                history = deque(list(history or []), maxlen=history_limit)
                self.ticker_history[inst_id] = history
            history.append(hist_item)

    def get_ticker_history(self, inst_id: str, max_points: Optional[int] = None, max_age: Optional[float] = None) -> List[dict]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "liquidity_history_max_age_sec", 40.0) or 40.0)
        with self.lock:
            rows = list(self.ticker_history.get(inst_id, []))
        now_ts = time.time()
        if age_limit > 0:
            rows = [dict(row) for row in rows if (now_ts - float(row.get("ts", 0.0) or 0.0)) <= age_limit]
        else:
            rows = [dict(row) for row in rows]
        if max_points is not None and max_points > 0:
            rows = rows[-max_points:]
        return rows

    def put_candles(self, inst_id: str, bar: str, candles: List[List[float]]) -> None:
        with self.lock:
            self.candles_cache[(inst_id, bar)] = list(candles)
            self.candles_ts[(inst_id, bar)] = time.time()

    def get_ticker(self, inst_id: str, max_age: Optional[float] = None) -> Optional[dict]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "market_data_cache_ttl_sec", 4.0) or 4.0)
        with self.lock:
            ticker = self.ticker_cache.get(inst_id)
            ts = self.ticker_ts.get(inst_id, 0.0)
            if ticker and (time.time() - ts) <= age_limit:
                return dict(ticker)
        return None

    def get_candles(self, inst_id: str, bar: str, limit: int, max_age: Optional[float] = None) -> Optional[List[List[float]]]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "market_data_cache_ttl_sec", 4.0) or 4.0)
        key = (inst_id, bar)
        with self.lock:
            candles = self.candles_cache.get(key)
            ts = self.candles_ts.get(key, 0.0)
            if candles and len(candles) >= limit and (time.time() - ts) <= age_limit:
                return [list(row) for row in candles[-limit:]]
        return None

    def snapshot_stats(self) -> dict:
        return {
            "running": bool(self.running),
            "ticker_cache_size": len(self.ticker_cache),
            "ticker_history_size": len(self.ticker_history),
            "candles_cache_size": len(self.candles_cache),
            "fetch_count": int(self.fetch_count),
            "error_count": int(self.error_count),
            "last_error": self.last_error,
            "last_cycle_at": self.last_cycle_at,
        }


APP_DIR = Path(__file__).resolve().parent
APP_VERSION = "v078"
WINDOW_ICON_PATH = APP_DIR / "turtle_traders_icon_v3.png"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
TRADE_CSV = LOG_DIR / "trades.csv"
ENGINE_STATS_FILE = LOG_DIR / "engine_stats.jsonl"
SIGNAL_AUDIT_FILE = LOG_DIR / "signal_audit.jsonl"
APP_LOG = LOG_DIR / "app.log"
POSITION_JOURNAL_FILE = LOG_DIR / "position_journal.jsonl"
FILTER_DIAGNOSTICS_FILE = LOG_DIR / "filter_diagnostics.jsonl"
POSITION_SNAPSHOTS_FILE = LOG_DIR / "position_snapshots.jsonl"
SYSTEM_HEALTH_FILE = LOG_DIR / "system_health.jsonl"
PYRAMID_DIAGNOSTICS_FILE = LOG_DIR / "pyramid_diagnostics.jsonl"
REENTRY_DIAGNOSTICS_FILE = LOG_DIR / "reentry_diagnostics.jsonl"
BREAKOUT_QUALITY_FILE = LOG_DIR / "breakout_quality.jsonl"
ANALYSIS_EXPORT_DIR = LOG_DIR / "analysis_exports"
ANALYSIS_EXPORT_DIR.mkdir(exist_ok=True)
HIDDEN_INSTRUMENTS = set()
HIDDEN_PREFIXES = tuple()
EXECUTION_RISK_WATCHLIST = {"ATOM-USDT-SWAP", "MINA-USDT-SWAP", "XSR-USDT-SWAP", "LINK-USDT-SWAP", "BREV-USDT-SWAP", "QTUM-USDT-SWAP", "TSLA-USDT-SWAP"}
APP_START_TIME = time.time()


def is_hidden_instrument(inst_id: object) -> bool:
    value = str(inst_id or "").upper()
    return value in HIDDEN_INSTRUMENTS or any(value.startswith(prefix) for prefix in HIDDEN_PREFIXES)

STATE_FILE = LOG_DIR / "runtime_state.json"
ENTRY_CONTEXT_DIR = LOG_DIR / "entry_context"
ENTRY_CONTEXT_DIR.mkdir(exist_ok=True)
TRADE_CONTEXT_DIR = LOG_DIR / "trade_context"
TRADE_CONTEXT_DIR.mkdir(exist_ok=True)


TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "1D": 86400,
}

TIMEFRAME_LABELS = {
    "1m": "1 минута",
    "5m": "5 минут",
    "15m": "15 минут",
    "30m": "30 минут",
    "1H": "1 час",
    "1D": "1 день",
}


def format_clock(value: Optional[float]) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromtimestamp(value).strftime("%H:%M:%S")
    except Exception:
        return "—"


def format_time_string(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    if " " in text:
        tail = text.split(" ")[-1]
        if len(tail) >= 8:
            return tail[:8]
    if "T" in text:
        tail = text.split("T")[-1]
        if len(tail) >= 8:
            return tail[:8]
    return text[:8]




def format_duration(seconds: object) -> str:
    try:
        total = int(float(seconds or 0))
    except Exception:
        return "—"
    if total <= 0:
        return "—"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}ч {minutes:02d}м"
    if minutes > 0:
        return f"{minutes}м {secs:02d}с"
    return f"{secs}с"


def gradient_pnl_color(pnl_pct: float) -> QColor:
    if pnl_pct >= 10:
        return QColor(10, 120, 40)
    if pnl_pct >= 5:
        return QColor(20, 145, 55)
    if pnl_pct > 2:
        return QColor(40, 165, 70)
    if pnl_pct > 0:
        return QColor(85, 180, 95)
    if pnl_pct <= -10:
        return QColor(150, 20, 20)
    if pnl_pct <= -5:
        return QColor(176, 35, 35)
    if pnl_pct < -2:
        return QColor(200, 60, 60)
    if pnl_pct < 0:
        return QColor(220, 95, 95)
    return QColor(32, 32, 32)



def detect_is_dark_theme(app: QApplication) -> bool:
    palette = app.palette()
    window = palette.color(QPalette.ColorRole.Window)
    text = palette.color(QPalette.ColorRole.WindowText)
    return window.lightness() < text.lightness()


def build_app_stylesheet(is_dark: bool) -> str:
    if is_dark:
        return """
            QMainWindow, QWidget {
                background: #050816;
                color: #e6ecff;
                font-family: Segoe UI, Inter, Arial;
            }
            QFrame#CyberHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #081326, stop:0.38 #14103a, stop:0.7 #1d0b35, stop:1 #071f36);
                border: 1px solid #3b82f6;
                border-radius: 22px;
            }
            QLabel#CyberHeaderTitle {
                color: #edf6ff;
                font-size: 22px;
                font-weight: 900;
                letter-spacing: 2px;
                padding: 2px 8px 0 8px;
            }
            QLabel[chip="true"] {
                background: #08111f;
                border: 1px solid #1d4ed8;
                border-radius: 16px;
                color: #87f4ff;
                font-size: 12px;
                font-weight: 800;
                padding: 7px 12px;
                min-height: 20px;
            }
            QLabel[syschip="true"] {
                background: rgba(6, 14, 28, 0.82);
                border: 1px solid #21456f;
                border-radius: 14px;
                color: #d8f6ff;
                font-size: 11px;
                font-weight: 800;
                padding: 5px 10px;
            }
            QGroupBox {
                font-weight: 800;
                color: #70e1ff;
                border: none;
                border-radius: 18px;
                margin-top: 18px;
                padding-top: 18px;
                background: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 10px;
                color: #2adfff;
                background: transparent;
                font-size: 12px;
                font-weight: 900;
                text-transform: uppercase;
            }
            QLabel {
                color: #e6ecff;
                background: transparent;
            }
            QLabel[card="true"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #091321, stop:1 #0b1424);
                color: #eef6ff;
                border: 1px solid #1b3b63;
                border-radius: 16px;
                padding: 10px 12px;
            }
            QLabel[radarBadge="true"] {
                background: rgba(5, 19, 33, 0.88);
                color: #7dd3fc;
                border: 1px solid #21456f;
                border-radius: 12px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 900;
                letter-spacing: 1px;
            }
            QLabel[metricTitle="true"] {
                color: #7dd3fc;
                font-size: 11px;
                font-weight: 900;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            QLabel[metricValue="true"] {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 900;
            }
            QLabel[heroValue="true"] {
                color: #8cf6ff;
                font-size: 38px;
                font-weight: 900;
            }
            QComboBox, QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox, QTableView, QTableWidget {
                background: #08111f;
                color: #f8fafc;
                border: 1px solid #1b3b63;
                border-radius: 12px;
                selection-background-color: #ff3dd1;
                selection-color: #ffffff;
            }
            QComboBox {
                padding: 8px 34px 8px 12px;
                min-height: 18px;
                border: 1px solid #27548e;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #08111f, stop:1 #101a2d);
                font-weight: 800;
            }
            QComboBox:hover {
                border: 1px solid #67e8f9;
            }
            QComboBox:focus {
                border: 1px solid #00ffa8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #1b3b63;
                background: rgba(12, 26, 48, 0.85);
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #67e8f9;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #08111f;
                color: #e6ecff;
                border: 1px solid #27548e;
                border-radius: 12px;
                padding: 6px;
                selection-background-color: #10213d;
                selection-color: #00ffa8;
                outline: 0;
            }
            QScrollBar:vertical {
                background: rgba(8, 17, 31, 0.85);
                width: 12px;
                margin: 8px 2px 8px 2px;
                border: none;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #67e8f9, stop:1 #00ffa8);
                min-height: 28px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #8cf6ff, stop:1 #24ffb3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
                border: none;
            }
            QTextEdit#ActivityFeed {
                background: #060d18;
                border: 1px solid #1c325a;
                color: #8be9fd;
                border-radius: 16px;
            }
            QHeaderView::section {
                background: #101a2d;
                color: #8be9fd;
                border: 1px solid #1c325a;
                padding: 9px;
                font-weight: 800;
            }
            QTabWidget::pane {
                border: 1px solid #1c325a;
                background: #08111f;
                border-radius: 14px;
                top: -1px;
            }
            QTabBar::tab {
                background: #091221;
                color: #93a7c7;
                border: 1px solid #1c325a;
                border-bottom: none;
                padding: 11px 18px;
                margin-right: 4px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                font-weight: 800;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #10213d, stop:1 #1a1240);
                color: #67e8f9;
                border-color: #8b5cf6;
            }
            QPushButton {
                padding: 9px 14px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #18274a;
                border-color: #67e8f9;
            }
            QFrame#MarketPulseTile {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #08111f, stop:1 #10152c);
                border: 1px solid #274986;
                border-radius: 18px;
            }
            QPushButton#toggleBotButton[running="true"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4c0519, stop:1 #7f1d1d);
                border: 1px solid #ef4444;
                color: #ffffff;
            }
            QPushButton#toggleBotButton[running="false"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #03251d, stop:1 #064e3b);
                border: 1px solid #10b981;
                color: #ffffff;
            }
        """
    return """
        QMainWindow, QWidget { background: #f5f7fb; color: #111827; }
    """





class NeonPanel(QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(55)

    def _tick(self):
        self._pulse = (self._pulse + 0.08) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 12, -1, -1)
        pulse = (math.sin(self._pulse) + 1.0) * 0.5

        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(7, 16, 31, 236))
        bg.setColorAt(0.58, QColor(6, 12, 24, 238))
        bg.setColorAt(1.0, QColor(8, 18, 34, 236))
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 18, 18)

        border_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        border_grad.setColorAt(0.0, QColor(0, 224, 255, 180))
        border_grad.setColorAt(0.48, QColor(89, 115, 255, 125))
        border_grad.setColorAt(1.0, QColor(255, 61, 209, 170))
        for width, alpha in ((6, 20), (3, 38)):
            glow = QPen(QColor(0, 224, 255, alpha), width)
            painter.setPen(glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 18, 18)
        painter.setPen(QPen(QBrush(border_grad), 1.4))
        painter.drawRoundedRect(rect, 18, 18)

        corner = QColor(0, 238, 255, int(170 + pulse * 50))
        accent = QColor(255, 61, 209, int(120 + pulse * 55))
        painter.setPen(QPen(corner, 2))
        span = 26
        # top-left
        painter.drawLine(rect.left()+10, rect.top()+1, rect.left()+span, rect.top()+1)
        painter.drawLine(rect.left()+1, rect.top()+10, rect.left()+1, rect.top()+span)
        # top-right
        painter.drawLine(rect.right()-span, rect.top()+1, rect.right()-10, rect.top()+1)
        painter.drawLine(rect.right()-1, rect.top()+10, rect.right()-1, rect.top()+span)
        painter.setPen(QPen(accent, 2))
        # bottom-left
        painter.drawLine(rect.left()+1, rect.bottom()-span, rect.left()+1, rect.bottom()-10)
        painter.drawLine(rect.left()+10, rect.bottom()-1, rect.left()+span, rect.bottom()-1)
        # bottom-right
        painter.drawLine(rect.right()-span, rect.bottom()-1, rect.right()-10, rect.bottom()-1)
        painter.drawLine(rect.right()-1, rect.bottom()-span, rect.right()-1, rect.bottom()-10)

        title_rect = QRect(rect.left()+14, 0, max(180, min(rect.width()-28, 220)), 24)
        title_bg = QLinearGradient(title_rect.left(), title_rect.top(), title_rect.right(), title_rect.bottom())
        title_bg.setColorAt(0.0, QColor(4, 19, 38, 220))
        title_bg.setColorAt(1.0, QColor(15, 17, 43, 180))
        painter.setBrush(title_bg)
        painter.setPen(QPen(QColor(0, 224, 255, 120), 1))
        painter.drawRoundedRect(title_rect, 8, 8)
        painter.setPen(QColor(64, 227, 255))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect.adjusted(12,0,-12,0), int(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft), self.title().upper())


class AnimatedGridWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._pulse = 0.0
        self._particle_phase = 0.0
        self.mode = "idle"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_mode(self, mode: str):
        self.mode = str(mode or "idle").lower()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 1.6) % 64.0
        self._pulse = (self._pulse + 0.09) % (math.pi * 2.0)
        self._particle_phase = (self._particle_phase + 0.012) % 1.0
        self.update()

    def _mode_colors(self):
        if self.mode == "alert":
            return QColor(255, 77, 109, 50), QColor(255, 166, 0, 42)
        if self.mode == "trading":
            return QColor(0, 255, 163, 40), QColor(0, 224, 255, 36)
        return QColor(0, 224, 255, 24), QColor(255, 61, 209, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(3, 8, 20))
        bg.setColorAt(0.35, QColor(8, 11, 30))
        bg.setColorAt(0.68, QColor(20, 9, 38))
        bg.setColorAt(1.0, QColor(4, 23, 38))
        painter.fillRect(rect, bg)

        pulse = (math.sin(self._pulse) + 1.0) * 0.5
        grid_minor = QColor(40, 86, 150, int(26 + 12 * pulse))
        grid_major = QColor(30, 224, 255, int(30 + 20 * pulse))
        painter.setPen(QPen(grid_minor, 1))
        step = 28
        phase = int(self._phase)
        for x in range(-step, rect.width() + step, step):
            painter.drawLine(x + phase, 0, x + phase, rect.height())
        for y in range(-step, rect.height() + step, step):
            painter.drawLine(0, y + phase // 2, rect.width(), y + phase // 2)

        painter.setPen(QPen(grid_major, 1))
        major = step * 4
        for x in range(-major, rect.width() + major, major):
            painter.drawLine(x + phase, 0, x + phase, rect.height())
        for y in range(-major, rect.height() + major, major):
            painter.drawLine(0, y + phase // 2, rect.width(), y + phase // 2)

        c1, c2 = self._mode_colors()
        glow = QRadialGradient(QPointF(rect.width() * 0.72, rect.height() * 0.12), max(rect.width(), rect.height()) * 0.55)
        glow.setColorAt(0.0, c2)
        glow.setColorAt(0.35, c1)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)

        painter.setPen(QPen(QColor(0, 224, 255, 22), 2))
        paths = [
            [QPointF(rect.width()*0.12, rect.height()*0.30), QPointF(rect.width()*0.38, rect.height()*0.30), QPointF(rect.width()*0.52, rect.height()*0.54), QPointF(rect.width()*0.84, rect.height()*0.54)],
            [QPointF(rect.width()*0.10, rect.height()*0.74), QPointF(rect.width()*0.36, rect.height()*0.74), QPointF(rect.width()*0.52, rect.height()*0.54), QPointF(rect.width()*0.87, rect.height()*0.86)],
        ]
        for pts in paths:
            for a,b in zip(pts, pts[1:]):
                painter.drawLine(a,b)
            for idx,(a,b) in enumerate(zip(pts, pts[1:])):
                t=(self._particle_phase*1.35+idx*0.21)%1.0
                x=a.x()+(b.x()-a.x())*t
                y=a.y()+(b.y()-a.y())*t
                color=QColor(0,255,163,190) if self.mode!="alert" else QColor(255,77,109,190)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x,y), 3.5, 3.5)

        vignette = QRadialGradient(QPointF(rect.center()), max(rect.width(), rect.height()) * 0.82)
        vignette.setColorAt(0.72, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 85))
        painter.fillRect(rect, vignette)


class MiniSparklineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [0.0] * 24
        self.display_values = [0.0] * 24
        self.positive = True
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)
        self.setMinimumHeight(42)

    def _animate(self):
        if not self.display_values:
            self.display_values = list(self.values)
        self._phase = (self._phase + 0.18) % (math.pi * 2.0)
        target = self.values or [0.0] * 24
        if len(self.display_values) != len(target):
            self.display_values = list(target)
        else:
            updated = []
            for idx, (cur, tgt) in enumerate(zip(self.display_values, target)):
                drift = math.sin(self._phase + idx * 0.23) * 0.015
                updated.append(cur * 0.84 + tgt * 0.16 + drift)
            self.display_values = updated
        self.update()

    def set_series(self, values, positive=True):
        vals = [float(v) for v in (values or []) if v is not None]
        if not vals:
            vals = [0.0] * 24
        self.values = vals[-24:]
        if not self.display_values or len(self.display_values) != len(self.values):
            self.display_values = list(self.values)
        self.positive = bool(positive)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        values = self.display_values or self.values
        if not values:
            return
        line_color = QColor(0, 255, 163) if self.positive else QColor(255, 77, 79)
        glow_color = QColor(line_color.red(), line_color.green(), line_color.blue(), 65)
        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v += 1.0
            min_v -= 1.0
        step_x = rect.width() / max(1, len(values) - 1)

        def y_of(v):
            return rect.bottom() - ((v - min_v) / (max_v - min_v)) * rect.height()

        pts = [(rect.left() + i * step_x, y_of(v)) for i, v in enumerate(values)]
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)

        area = QPainterPath(path)
        area.lineTo(rect.right(), rect.bottom())
        area.lineTo(rect.left(), rect.bottom())
        area.closeSubpath()

        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, glow_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(area, grad)

        for width, alpha in ((7, 26), (4, 42)):
            painter.setPen(QPen(QColor(line_color.red(), line_color.green(), line_color.blue(), alpha), width))
            painter.drawPath(path)

        painter.setPen(QPen(line_color, 2))
        painter.drawPath(path)
        painter.setBrush(line_color)
        painter.setPen(Qt.PenStyle.NoPen)
        x, y = pts[-1]
        painter.drawEllipse(QPointF(x, y), 3.2, 3.2)


class MarketPulseTile(QFrame):
    def __init__(self, title="SCAN", parent=None):
        super().__init__(parent)
        self.setObjectName("MarketPulseTile")
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.lbl_symbol = QLabel(title)
        self.lbl_symbol.setStyleSheet("font-size: 16px; font-weight: 900; color: #dbeafe;")
        self.lbl_status = QLabel("WATCH")
        self.lbl_status.setProperty("radarBadge", "true")
        top.addWidget(self.lbl_symbol, 1)
        top.addWidget(self.lbl_status, 0)
        layout.addLayout(top)

        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(8)
        self.lbl_change = QLabel("+0.00%")
        self.lbl_change.setStyleSheet("font-size: 18px; font-weight: 900; color: #00ffa3;")
        self.lbl_score = QLabel("Score: 0")
        self.lbl_score.setStyleSheet("font-size: 11px; font-weight: 700; color: #93c5fd;")
        mid.addWidget(self.lbl_change)
        mid.addStretch(1)
        mid.addWidget(self.lbl_score)
        layout.addLayout(mid)

        self.lbl_reason = QLabel("Ожидание валидного сигнала")
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setStyleSheet("font-size: 11px; color: #9dd8ff; min-height: 30px;")
        layout.addWidget(self.lbl_reason)

        self.spark = MiniSparklineWidget()
        self.spark.setMinimumHeight(28)
        layout.addWidget(self.spark)

    def set_data(self, symbol: str, change_pct: float, values=None, status: str="WATCH", score: float=0.0, reason: str=""):
        symbol = str(symbol or "SCAN")
        short = symbol.replace("-USDT-SWAP", "").replace("-SWAP", "")
        status_text = str(status or "WATCH").upper()
        self.lbl_symbol.setText(short)
        self.lbl_status.setText(status_text)
        self.lbl_change.setText(f"{float(change_pct or 0.0):+,.2f}%")
        self.lbl_score.setText(f"Score: {float(score or 0.0):.0f}")
        reason_text = str(reason or "Ожидание валидного сигнала").strip()
        self.lbl_reason.setText(reason_text[:82])

        if status_text in {"LONG", "LONG CANDIDATE", "RUNNING"}:
            accent = "#00ffa3"
        elif status_text in {"SHORT", "SHORT CANDIDATE", "FILTERED", "RISK"}:
            accent = "#ff6b8a" if status_text.startswith("SHORT") else "#ffb347"
        else:
            accent = "#7dd3fc"

        self.lbl_status.setStyleSheet(
            f"background: rgba(5, 19, 33, 0.88); color: {accent}; border: 1px solid #21456f; border-radius: 12px; padding: 4px 8px; font-size: 10px; font-weight: 900; letter-spacing: 1px;"
        )
        change_color = "#00ffa3" if float(change_pct or 0.0) >= 0 else "#ff4d6d"
        self.lbl_change.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {change_color};")
        series = values or [float(change_pct or 0.0)] * 18
        self.spark.set_series(series, positive=float(change_pct or 0.0) >= 0)


class GlowBandWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series_a = [0.0] * 48
        self.series_b = [0.0] * 48
        self._offset = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(55)
        self.setMinimumHeight(28)

    def _animate(self):
        self._offset = (self._offset + 1.8) % 320.0
        self.update()

    def set_series(self, series_a=None, series_b=None):
        a = [float(v) for v in (series_a or []) if v is not None]
        b = [float(v) for v in (series_b or []) if v is not None]
        self.series_a = (a or [0.0] * 48)[-48:]
        self.series_b = (b or [0.0] * 48)[-48:]
        self.update()

    def _draw_line(self, painter, rect, values, line_color):
        if not values:
            return
        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v += 1.0
            min_v -= 1.0
        step_x = rect.width() / max(1, len(values) - 1)

        def y_of(v):
            return rect.bottom() - ((v - min_v) / (max_v - min_v)) * rect.height()

        pts = [(rect.left() + i * step_x, y_of(v)) for i, v in enumerate(values)]
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(rect.right(), rect.bottom())
        fill.lineTo(rect.left(), rect.bottom())
        fill.closeSubpath()
        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 96))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(fill, grad)
        painter.setPen(QPen(QColor(line_color.red(), line_color.green(), line_color.blue(), 40), 6))
        painter.drawPath(path)
        painter.setPen(QPen(line_color, 2))
        painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(8, 8, -8, -8)
        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(7, 12, 24))
        bg.setColorAt(0.5, QColor(11, 15, 34))
        bg.setColorAt(1.0, QColor(6, 18, 30))
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(47, 80, 147), 1))
        painter.drawRoundedRect(rect, 18, 18)

        scan_grad = QLinearGradient(rect.left() - 140 + self._offset, rect.top(), rect.left() + self._offset, rect.top())
        scan_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        scan_grad.setColorAt(0.5, QColor(0, 224, 255, 32))
        scan_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect.adjusted(1, 1, -1, -1), scan_grad)

        plot = rect.adjusted(12, 10, -12, -14)
        painter.setPen(QPen(QColor(39, 57, 88), 1, Qt.PenStyle.DashLine))
        for frac in (0.2, 0.5, 0.8):
            y = int(plot.top() + plot.height() * frac)
            painter.drawLine(plot.left(), y, plot.right(), y)
        self._draw_line(painter, plot, self.series_a, QColor(255, 61, 209))
        self._draw_line(painter, plot, self.series_b, QColor(0, 224, 255))
        painter.setPen(QColor(125, 211, 252))
        painter.drawText(rect.adjusted(16, 6, -16, -6), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), 'NEON FLOW BAND')

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(APP_LOG, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def recreate_trade_csv() -> None:
    with TRADE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time",
            "event",
            "inst_id",
            "side",
            "qty",
            "price",
            "atr",
            "stop_price",
            "system_name",
            "note",
        ])


def clear_json_directory(directory: Path) -> int:
    removed = 0
    directory.mkdir(exist_ok=True)
    for item in directory.glob("*.json"):
        try:
            item.unlink()
            removed += 1
        except Exception:
            pass
    return removed


def reset_local_runtime_files() -> dict:
    removed_entry = clear_json_directory(ENTRY_CONTEXT_DIR)
    removed_trade = clear_json_directory(TRADE_CONTEXT_DIR)

    if STATE_FILE.exists():
        try:
            STATE_FILE.unlink()
        except Exception:
            pass

    recreate_trade_csv()

    for file_path in (ENGINE_STATS_FILE, SIGNAL_AUDIT_FILE, POSITION_JOURNAL_FILE, POSITION_SNAPSHOTS_FILE, SYSTEM_HEALTH_FILE, PYRAMID_DIAGNOSTICS_FILE, REENTRY_DIAGNOSTICS_FILE, BREAKOUT_QUALITY_FILE, APP_LOG):
        try:
            file_path.write_text("", encoding="utf-8")
        except Exception:
            pass

    return {
        "entry_context_removed": removed_entry,
        "trade_context_removed": removed_trade,
    }




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
    decision_rows = _build_decision_trace_rows(signal_audit_rows, engine_event_rows, journal_rows)
    execution_rows = _build_execution_log_rows(engine_event_rows, journal_rows)
    risk_rows = _build_risk_event_rows(engine_event_rows, filter_rows)
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
    for name in ['closed_trades', 'open_positions_endstate', 'positions_lifecycle', 'entry_candidates', 'decision_trace', 'execution_log', 'risk_events', 'market_context_on_entry', 'system_health', 'pyramid_diagnostics', 'reentry_diagnostics', 'breakout_quality']:
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


def build_analysis_export_bundle(mode: str = 'full', snapshot: Optional[dict] = None, cfg: Optional["BotConfig"] = None) -> Path:
    mode = str(mode or 'full').lower()
    export_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dataset = _build_export_dataset(snapshot, cfg)
    if mode == 'hourly':
        hourly_dir = ANALYSIS_EXPORT_DIR / f'analysis_hourly_{export_ts}'
        hourly_dir.mkdir(parents=True, exist_ok=True)
        all_dts = []
        for key in ['positions_lifecycle', 'entry_candidates', 'decision_trace', 'execution_log', 'risk_events', 'system_health', 'pyramid_diagnostics', 'reentry_diagnostics', 'breakout_quality']:
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
                'pyramid_diagnostics': _rows_between(dataset['pyramid_diagnostics'], hour, nxt),
                'reentry_diagnostics': _rows_between(dataset['reentry_diagnostics'], hour, nxt),
                'breakout_quality': _rows_between(dataset['breakout_quality'], hour, nxt),
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

@dataclass
class BotConfig:
    api_key: str
    secret_key: str
    passphrase: str
    flag: str = "1"  # 0 = main, 1 = demo
    timeframe: str = "15m"
    td_mode: str = "isolated"
    leverage: int = 1
    scan_interval_sec: int = 5
    position_check_interval_sec: int = 2
    balance_refresh_sec: int = 5
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
    blacklist: List[str] = field(default_factory=lambda: ["USDC-USDT-SWAP"])
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
    breakout_buffer_atr: float = 0.10
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
    market_data_cache_ttl_sec: float = 4.0
    market_data_worker_sleep_sec: float = 0.12
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
    trend_stop_use_peak_pullback_exit: bool = True
    disable_trailing_on_entry_bar: bool = True
    breakeven_enabled: bool = True
    breakeven_min_hold_bars: int = 1
    breakeven_min_profit_atr: float = 0.8
    breakeven_min_locked_r: float = 0.5
    minimal_turtle_entry_mode: bool = True


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
    execution_risk_score: float = 0.0
    trailing_activated_at: str = ""
    breakeven_activated_at: str = ""


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


class EntryContextChartWidget(QWidget):
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


class EntryContextChartWidget(QWidget):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def _safe_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _price_to_y(self, price: float, min_price: float, max_price: float, top: int, height: int) -> int:
        if max_price <= min_price:
            return top + height // 2
        ratio = (price - min_price) / (max_price - min_price)
        return int(top + height - ratio * height)

    def _parse_candles(self):
        parsed = []
        for candle in self.payload.get("candles") or []:
            try:
                ts = int(candle[0])
                op = float(candle[1])
                hi = float(candle[2])
                lo = float(candle[3])
                cl = float(candle[4])
                parsed.append((ts, op, hi, lo, cl))
            except Exception:
                continue
        return parsed

    def _active_side(self) -> str:
        return str(self.payload.get("side") or "long").strip().lower()

    def _entry_period(self) -> int:
        try:
            return max(1, int(self.payload.get("entry_period") or 20))
        except Exception:
            return 20

    def _build_markers(self, candles):
        markers = []
        if not candles:
            return markers
        entry_price = self._safe_float(self.payload.get("entry_price"), 0.0)
        if entry_price > 0:
            markers.append({"kind": "entry", "label": "E", "index": max(0, len(candles) - 2), "price": entry_price})
        next_pyramid = self._safe_float(self.payload.get("next_pyramid_price"), 0.0)
        if next_pyramid > 0:
            markers.append({"kind": "next", "label": "N", "index": len(candles) - 1, "price": next_pyramid})
        return markers

    def _build_donchian_curve(self, candles):
        period = self._entry_period()
        side = self._active_side()
        curve = []
        if len(candles) <= 1:
            return curve
        for idx in range(len(candles)):
            start = max(0, idx - period)
            window = candles[start:idx]
            if not window:
                curve.append(None)
                continue
            try:
                value = max(float(c[2]) for c in window) if side == "long" else min(float(c[3]) for c in window)
            except Exception:
                value = None
            curve.append(value)
        return curve

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(760, 360)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, self.palette().window())

        candles = self._parse_candles()
        if not candles:
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "Нет сохранённых свечей для отображения")
            return

        left_pad, right_pad, top_pad, bottom_pad = 58, 88, 18, 28
        plot_left = rect.left() + left_pad
        plot_top = rect.top() + top_pad
        plot_width = max(40, rect.width() - left_pad - right_pad)
        plot_height = max(40, rect.height() - top_pad - bottom_pad)
        plot_right = plot_left + plot_width
        plot_bottom = plot_top + plot_height

        donchian_curve = self._build_donchian_curve(candles)
        prices = []
        for _, op, hi, lo, cl in candles:
            prices.extend([hi, lo, op, cl])
        for val in donchian_curve:
            if val is not None:
                prices.append(float(val))
        for val in (
            self._safe_float(self.payload.get("entry_price"), 0.0),
            self._safe_float(self.payload.get("stop_price"), 0.0),
            self._safe_float(self.payload.get("next_pyramid_price"), 0.0),
        ):
            if val > 0:
                prices.append(val)
        min_price = min(prices)
        max_price = max(prices)
        if max_price <= min_price:
            max_price = min_price + 1.0
        pad = (max_price - min_price) * 0.08
        min_price -= pad
        max_price += pad

        frame_pen = QPen(self.palette().mid().color())
        frame_pen.setWidth(1)
        painter.setPen(frame_pen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -2, -2), 10, 10)

        grid_pen = QPen(self.palette().mid().color())
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(5):
            y = plot_top + int(plot_height * i / 4)
            painter.drawLine(plot_left, y, plot_right, y)
        painter.drawRect(plot_left, plot_top, plot_width, plot_height)

        label_pen = QPen(self.palette().text().color())
        painter.setPen(label_pen)
        for i in range(5):
            price = max_price - (max_price - min_price) * i / 4
            y = plot_top + int(plot_height * i / 4)
            painter.drawText(rect.left() + 4, y + 4, f"{price:.6f}")

        n = len(candles)
        step_x = plot_width / max(1, n)
        body_w = max(3, min(14, int(step_x * 0.65)))
        bull_color = QColor(40, 167, 69)
        bear_color = QColor(220, 53, 69)
        wick_color = self.palette().text().color()
        x_coords = []

        highlight_period = min(self._entry_period(), len(candles))
        if highlight_period > 0:
            start_idx = max(0, len(candles) - highlight_period)
            hl_x1 = int(plot_left + step_x * start_idx)
            hl_x2 = int(plot_left + step_x * len(candles))
            shade = QColor(34, 197, 94, 28) if self._active_side() == "long" else QColor(239, 68, 68, 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRect(hl_x1, plot_top + 1, max(8, hl_x2 - hl_x1), plot_height - 1)

        for i, candle in enumerate(candles):
            _, op, hi, lo, cl = candle
            x = int(plot_left + step_x * i + step_x / 2)
            x_coords.append(x)
            y_hi = self._price_to_y(hi, min_price, max_price, plot_top, plot_height)
            y_lo = self._price_to_y(lo, min_price, max_price, plot_top, plot_height)
            y_op = self._price_to_y(op, min_price, max_price, plot_top, plot_height)
            y_cl = self._price_to_y(cl, min_price, max_price, plot_top, plot_height)
            painter.setPen(QPen(wick_color))
            painter.drawLine(x, y_hi, x, y_lo)
            top = min(y_op, y_cl)
            h = max(2, abs(y_cl - y_op))
            body_rect_x = int(x - body_w / 2)
            painter.fillRect(body_rect_x, top, body_w, h, bull_color if cl >= op else bear_color)
            painter.drawRect(body_rect_x, top, body_w, h)

        curve_color = QColor(22, 163, 74) if self._active_side() == "long" else QColor(220, 38, 38)
        curve_pen = QPen(curve_color, 2)
        curve_pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(curve_pen)
        prev_pt = None
        for idx, value in enumerate(donchian_curve):
            if value is None or idx >= len(x_coords):
                prev_pt = None
                continue
            point = (x_coords[idx], self._price_to_y(float(value), min_price, max_price, plot_top, plot_height))
            if prev_pt is not None:
                painter.drawLine(prev_pt[0], prev_pt[1], point[0], point[1])
            prev_pt = point

        def draw_hline(price, label, color, style=Qt.PenStyle.SolidLine):
            if price <= 0:
                return
            y = self._price_to_y(float(price), min_price, max_price, plot_top, plot_height)
            pen = QPen(color)
            pen.setStyle(style)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(plot_left, y, plot_right, y)
            painter.drawText(plot_right + 6, y + 4, label)

        draw_hline(self._safe_float(self.payload.get("entry_price"), 0.0), "Entry", QColor(30, 144, 255), Qt.PenStyle.DashLine)
        draw_hline(self._safe_float(self.payload.get("stop_price"), 0.0), "Stop", QColor(220, 53, 69), Qt.PenStyle.SolidLine)
        draw_hline(float(candles[-1][4]), "Now", QColor(255, 193, 7), Qt.PenStyle.DotLine)

        markers = self._build_markers(candles)
        for marker in markers:
            idx = int(marker.get("index", -1))
            if idx < 0 or idx >= len(x_coords):
                continue
            x = x_coords[idx]
            y = self._price_to_y(float(marker.get("price", 0.0) or candles[idx][4]), min_price, max_price, plot_top, plot_height)
            kind = str(marker.get("kind") or "")
            color = QColor(30, 144, 255) if kind == "entry" else QColor(255, 193, 7)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(x - 5, y - 5, 10, 10)
            painter.setPen(label_pen)
            painter.drawText(x + 7, max(plot_top + 12, y - 8), str(marker.get("label") or ""))

        painter.setPen(curve_color)
        painter.drawText(plot_left + 8, plot_top + 16, f"Donchian {self._entry_period()} ({'верхняя' if self._active_side() == 'long' else 'нижняя'})")
        painter.setPen(label_pen)

        try:
            first_ts = candles[0][0] / 1000
            last_ts = candles[-1][0] / 1000
            painter.setPen(label_pen)
            painter.drawText(plot_left, plot_bottom + 18, datetime.fromtimestamp(first_ts).strftime("%d.%m %H:%M"))
            painter.drawText(plot_right - 80, plot_bottom + 18, datetime.fromtimestamp(last_ts).strftime("%d.%m %H:%M"))
        except Exception:
            pass


class EntryContextDialog(QDialog):
    def __init__(self, payload: dict, context_file: str, parent=None, live_state: Optional[dict] = None):
        super().__init__(parent)
        self.payload = payload or {}
        self.context_file = context_file
        self.live_state = live_state or {}
        self.setWindowTitle(f"Позиция — {self.payload.get('inst_id', 'позиция')}")
        self.resize(1080, 820)
        self.setStyleSheet("""
            QDialog { background: #050816; color: #e6ecff; }
            QLabel { color: #e6ecff; }
            QFrame.sectionCard {
                background: #08111f;
                border: 1px solid #1b3b63;
                border-radius: 16px;
            }
            QFrame.metricCard {
                background: #091427;
                border: 1px solid #16365d;
                border-radius: 14px;
            }
            QLabel.sectionTitle {
                color: #9dd8ff;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }
            QLabel.metricTitle {
                color: #8bb5d9;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel.metricValue {
                color: #f8fbff;
                font-size: 16px;
                font-weight: 900;
            }
            QLabel.metricHint {
                color: #8aa6c2;
                font-size: 10px;
            }
            QPushButton {
                padding: 9px 16px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover { border-color: #67e8f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        side_value = str(self.payload.get('side', '—')).lower()
        side_text = 'LONG' if side_value == 'long' else ('SHORT' if side_value == 'short' else str(self.payload.get('side', '—')).upper())
        side_color = '#00FFA8' if side_value == 'long' else ('#FF3A5E' if side_value == 'short' else '#64748b')

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title = QLabel(f"{self.payload.get('inst_id', '—')} · {self.payload.get('system_name', '—')} · {self.payload.get('timeframe', '—')}")
        title.setStyleSheet("font-size: 17px; font-weight: 900; color: #edf6ff;")
        header_row.addWidget(title, 1)

        side_badge = QLabel(side_text)
        side_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_badge.setMinimumWidth(110)
        side_badge.setStyleSheet(
            f"font-size: 15px; font-weight: 900; color: #06111f; background: {side_color}; border: 1px solid #d6fff6; border-radius: 14px; padding: 7px 14px;"
        )
        header_row.addWidget(side_badge, 0)

        status_badge = QLabel("ACTIVE")
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setMinimumWidth(110)
        status_badge.setStyleSheet("font-size: 14px; font-weight: 900; color: #e8f7ff; background: #123657; border: 1px solid #3b82f6; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(status_badge, 0)
        layout.addLayout(header_row)

        summary = self._build_summary_row()
        layout.addLayout(summary)

        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(10)

        candles = self.payload.get("candles") or []
        chart_box = QFrame(self)
        chart_box.setObjectName("chartBox")
        chart_box.setProperty("class", "sectionCard")
        chart_box.setFrameShape(QFrame.Shape.StyledPanel)
        chart_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(6)

        chart_mode_label = "Текущий график" if bool(self.payload.get("live_chart")) else "График входа"
        chart_title = QLabel(f"{chart_mode_label} · свечей: {len(candles)}")
        chart_title.setProperty("class", "sectionTitle")
        chart_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        chart_layout.addWidget(chart_title)

        chart = EntryContextChartWidget(self.payload, chart_box)
        chart_layout.addWidget(chart, 1)
        body_row.addWidget(chart_box, 3)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(10)
        right_col.addWidget(self._build_entry_context_card())
        right_col.addWidget(self._build_live_status_card())
        right_col.addWidget(self._build_management_card())
        right_col.addStretch(1)
        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row, 1)

        footer_mode = "LIVE chart + entry context" if bool(self.payload.get("live_chart")) else "ENTRY snapshot"
        footer = QLabel(f"Контекст: {self.context_file}  |  {footer_mode}")
        footer.setStyleSheet("color: #6f8baa; font-size: 11px;")
        layout.addWidget(footer)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _build_summary_row(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        entry_price = self._num(self.payload.get('entry_price'))
        current_price = self._num(self.live_state.get('last_px')) or entry_price
        pnl_value = self._num(self.live_state.get('unrealized_pnl'))
        pnl_pct = self._num(self.live_state.get('pnl_pct'))
        units = int(self._num(self.live_state.get('units') or self.payload.get('units') or 1))
        duration = self._duration_from_times(self.payload.get('saved_at'), self.live_state.get('entry_time'))
        tiles = [
            ('Entry', self._fmt(entry_price), self._time_only(self.payload.get('saved_at'))),
            ('Current', self._fmt(current_price), f"PnL {self._fmt_signed(pnl_pct, suffix='%') }"),
            ('PnL', self._fmt_signed(pnl_value), self._fmt_signed(pnl_pct, suffix='%')),
            ('Units', str(units), f"Added {max(0, units-1)}"),
            ('Duration', duration, self._time_only(self.live_state.get('entry_time'))),
        ]
        for title, value, hint in tiles:
            row.addWidget(self._metric_card(title, value, hint), 1)
        return row

    def _build_entry_context_card(self):
        entry_period = self.payload.get('entry_period', '—')
        breakout_type = f"Turtle {entry_period}" if str(entry_period).isdigit() else str(self.payload.get('system_name', '—'))
        if breakout_type == 'Turtle —':
            breakout_type = str(self.payload.get('system_name', '—'))
        rows = [
            ('Вход', self._fmt(self.payload.get('entry_price'))),
            ('Время входа', self._fmt_dt(self.payload.get('saved_at'))),
            ('Пробой', breakout_type),
            ('ATR на входе', self._fmt(self.payload.get('atr'))),
            ('Стартовый стоп', self._fmt(self.payload.get('initial_stop_price') or self.payload.get('stop_price'))),
            ('След. добор', self._fmt(self.payload.get('next_pyramid_price'))),
            ('Канал', f"{self._fmt(self.payload.get('channel_low'))} → {self._fmt(self.payload.get('channel_high'))}"),
        ]
        return self._section_card('ENTRY CONTEXT', rows)

    def _build_live_status_card(self):
        last_px = self._num(self.live_state.get('last_px'))
        pnl = self._num(self.live_state.get('unrealized_pnl'))
        pnl_pct = self._num(self.live_state.get('pnl_pct'))
        rows = [
            ('Текущая цена', self._fmt(last_px)),
            ('PnL', self._fmt_signed(pnl)),
            ('PnL %', self._fmt_signed(pnl_pct, suffix='%')),
            ('Текущий стоп', self._fmt(self.live_state.get('stop_price'))),
            ('До стопа', self._fmt_signed(self.live_state.get('stop_distance_pct'), suffix='%')),
            ('ATR сейчас', self._fmt(self.live_state.get('atr'))),
            ('Сила движения', f"{self._num(self.live_state.get('trend_strength_atr')):.2f} ATR" if self.live_state else '—'),
        ]
        return self._section_card('LIVE STATUS', rows)

    def _build_management_card(self):
        rows = [
            ('Юнитов', str(int(self._num(self.live_state.get('units') or 1)))),
            ('Добавлено', str(max(0, int(self._num(self.live_state.get('units') or 1)) - 1))),
            ('Следующий добор', self._fmt(self.live_state.get('next_pyramid_price') or self.payload.get('next_pyramid_price'))),
            ('До добора', self._fmt_signed(self.live_state.get('pyramid_distance_pct'), suffix='%')),
            ('Риск сделки', self._fmt(self.payload.get('risk_amount_usdt'))),
            ('Номинал позиции', self._fmt(self.payload.get('position_notional_usdt'))),
            ('Режим', str(self.payload.get('trade_mode', '—'))),
        ]
        return self._section_card('TRADE MANAGEMENT', rows)

    def _section_card(self, title: str, rows: list[tuple[str, str]]):
        card = QFrame(self)
        card.setProperty('class', 'sectionCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel(title)
        lbl.setProperty('class', 'sectionTitle')
        layout.addWidget(lbl)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (name, value) in enumerate(rows):
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet('color: #86a9c9; font-size: 11px; font-weight: 700;')
            val_lbl = QLabel(value if str(value).strip() else '—')
            val_lbl.setStyleSheet('color: #f8fbff; font-size: 12px; font-weight: 800;')
            val_lbl.setWordWrap(True)
            grid.addWidget(name_lbl, i, 0)
            grid.addWidget(val_lbl, i, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card

    def _metric_card(self, title: str, value: str, hint: str = ''):
        card = QFrame(self)
        card.setProperty('class', 'metricCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setProperty('class', 'metricTitle')
        v = QLabel(value if str(value).strip() else '—')
        v.setProperty('class', 'metricValue')
        h = QLabel(hint if str(hint).strip() else ' ')
        h.setProperty('class', 'metricHint')
        lay.addWidget(t)
        lay.addWidget(v)
        lay.addWidget(h)
        return card

    @staticmethod
    def _num(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @classmethod
    def _fmt(cls, value) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return '—'

    @classmethod
    def _fmt_signed(cls, value, suffix: str = '') -> str:
        try:
            num = float(value)
            if suffix == '%':
                return f"{num:+.2f}%"
            return f"{num:+.4f}{suffix}"
        except Exception:
            return '—'

    @staticmethod
    def _fmt_dt(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%d.%m.%Y %H:%M:%S')
            except Exception:
                continue
        return txt

    @staticmethod
    def _time_only(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%H:%M:%S')
            except Exception:
                continue
        return txt[-8:]

    def _duration_from_times(self, entry_saved_at, live_entry_time) -> str:
        base = str(live_entry_time or entry_saved_at or '').strip()
        if not base:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                started = datetime.strptime(base, fmt)
                return format_duration(max(0, int((datetime.now() - started).total_seconds())))
            except Exception:
                continue
        return '—'


class TradeLifecycleChartWidget(QWidget):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def _safe_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _parse_candles(self):
        parsed = []
        for candle in self.payload.get("candles") or []:
            try:
                ts = int(candle[0]); op = float(candle[1]); hi = float(candle[2]); lo = float(candle[3]); cl = float(candle[4])
                parsed.append((ts, op, hi, lo, cl))
            except Exception:
                continue
        return parsed

    def _price_to_y(self, price: float, min_price: float, max_price: float, top: int, height: int) -> int:
        if max_price <= min_price:
            return top + height // 2
        ratio = (price - min_price) / (max_price - min_price)
        return int(top + height - ratio * height)

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(860, 420)

    def sizeHint(self):
        return self.minimumSizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, self.palette().window())
        candles = self._parse_candles()
        if not candles:
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "Нет сохранённых свечей по жизненному циклу сделки")
            return
        left_pad, right_pad, top_pad, bottom_pad = 60, 110, 22, 34
        plot_left = rect.left() + left_pad
        plot_top = rect.top() + top_pad
        plot_width = max(60, rect.width() - left_pad - right_pad)
        plot_height = max(60, rect.height() - top_pad - bottom_pad)
        plot_right = plot_left + plot_width
        plot_bottom = plot_top + plot_height
        prices=[]
        for _,op,hi,lo,cl in candles:
            prices.extend([op,hi,lo,cl])
        entry_price=self._safe_float(self.payload.get("entry_price"),0.0)
        exit_price=self._safe_float(self.payload.get("exit_price"),0.0)
        final_stop=self._safe_float(self.payload.get("final_stop_price"),0.0)
        for p in (entry_price,exit_price,final_stop):
            if p>0: prices.append(p)
        min_price=min(prices); max_price=max(prices)
        if max_price<=min_price: max_price=min_price+1.0
        pad=(max_price-min_price)*0.08
        min_price-=pad; max_price+=pad
        frame_pen = QPen(self.palette().mid().color()); frame_pen.setWidth(1); painter.setPen(frame_pen)
        painter.drawRoundedRect(rect.adjusted(1,1,-2,-2),10,10)
        grid_pen=QPen(self.palette().mid().color()); grid_pen.setStyle(Qt.PenStyle.DotLine); painter.setPen(grid_pen)
        for i in range(5):
            y=plot_top+int(plot_height*i/4); painter.drawLine(plot_left,y,plot_right,y)
        painter.drawRect(plot_left,plot_top,plot_width,plot_height)
        text_pen=QPen(self.palette().text().color()); painter.setPen(text_pen)
        for i in range(5):
            price=max_price-(max_price-min_price)*i/4; y=plot_top+int(plot_height*i/4); painter.drawText(rect.left()+4,y+4,f"{price:.6f}")
        n=len(candles); step_x=plot_width/max(1,n); body_w=max(3,min(14,int(step_x*0.65)))
        bull_color=QColor(40,167,69); bear_color=QColor(220,53,69); wick_color=self.palette().text().color()
        markers=list(self.payload.get("markers") or [])
        x_coords=[]
        entry_idx=next((int(m.get("index",-1)) for m in markers if str(m.get("kind"))=="entry"),-1)
        exit_idx=next((int(m.get("index",-1)) for m in markers if str(m.get("kind"))=="exit"),-1)
        if 0<=entry_idx<n and 0<=exit_idx<n and exit_idx>=entry_idx:
            start_x=int(plot_left+step_x*entry_idx); end_x=int(plot_left+step_x*(exit_idx+1))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(59,130,246,28)); painter.drawRect(start_x, plot_top+1, max(8,end_x-start_x), plot_height-1)
        for i,candle in enumerate(candles):
            _,op,hi,lo,cl=candle; x=int(plot_left+step_x*i+step_x/2); x_coords.append(x)
            y_hi=self._price_to_y(hi,min_price,max_price,plot_top,plot_height); y_lo=self._price_to_y(lo,min_price,max_price,plot_top,plot_height)
            y_op=self._price_to_y(op,min_price,max_price,plot_top,plot_height); y_cl=self._price_to_y(cl,min_price,max_price,plot_top,plot_height)
            painter.setPen(QPen(wick_color)); painter.drawLine(x,y_hi,x,y_lo)
            top=min(y_op,y_cl); h=max(2,abs(y_cl-y_op)); body_rect_x=int(x-body_w/2)
            painter.fillRect(body_rect_x, top, body_w, h, bull_color if cl>=op else bear_color); painter.drawRect(body_rect_x, top, body_w, h)
        def draw_hline(price,label,color,style=Qt.PenStyle.SolidLine):
            if price<=0: return
            y=self._price_to_y(price,min_price,max_price,plot_top,plot_height)
            pen=QPen(color); pen.setStyle(style); pen.setWidth(2); painter.setPen(pen); painter.drawLine(plot_left,y,plot_right,y); painter.drawText(plot_right+6,y+4,label)
        draw_hline(entry_price,'Entry',QColor(30,144,255),Qt.PenStyle.DashLine)
        draw_hline(final_stop,'Stop',QColor(220,53,69),Qt.PenStyle.SolidLine)
        if exit_price>0: draw_hline(exit_price,'Exit',QColor(255,193,7),Qt.PenStyle.DotLine)
        for marker in markers:
            idx=int(marker.get("index",-1))
            if idx<0 or idx>=len(x_coords): continue
            x=x_coords[idx]; price=self._safe_float(marker.get("price"),0.0); y=self._price_to_y(price if price>0 else candles[idx][4], min_price,max_price,plot_top,plot_height)
            kind=str(marker.get("kind") or '').lower(); label=str(marker.get("label") or '')
            color=QColor(32,201,151) if kind.startswith('add') else (QColor(255,193,7) if kind=='exit' else QColor(30,144,255))
            painter.setPen(QPen(color,2)); painter.setBrush(color); painter.drawEllipse(x-5,y-5,10,10); painter.setPen(text_pen); painter.drawText(x+7,max(plot_top+12,y-8),label)
        try:
            first_ts=candles[0][0]/1000; last_ts=candles[-1][0]/1000; painter.setPen(text_pen)
            painter.drawText(plot_left,plot_bottom+18,datetime.fromtimestamp(first_ts).strftime('%d.%m %H:%M'))
            painter.drawText(plot_right-84,plot_bottom+18,datetime.fromtimestamp(last_ts).strftime('%d.%m %H:%M'))
        except Exception:
            pass


class TradeLifecycleDialog(QDialog):
    def __init__(self, payload: dict, context_file: str, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.context_file = context_file
        self.setWindowTitle(f"Сделка — {self.payload.get('inst_id', 'сделка')}")
        self.resize(1120, 820)
        self.setStyleSheet("""
            QDialog { background: #050816; color: #e6ecff; }
            QLabel { color: #e6ecff; }
            QFrame.sectionCard {
                background: #08111f;
                border: 1px solid #1b3b63;
                border-radius: 16px;
            }
            QFrame.metricCard {
                background: #091427;
                border: 1px solid #16365d;
                border-radius: 14px;
            }
            QPushButton {
                padding: 9px 16px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover { border-color: #67e8f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        side_value = str(self.payload.get('side', '—')).lower()
        side_text = 'LONG' if side_value == 'long' else ('SHORT' if side_value == 'short' else str(self.payload.get('side', '—')).upper())
        side_color = '#00FFA8' if side_value == 'long' else ('#FF3A5E' if side_value == 'short' else '#64748b')

        header_row = QHBoxLayout()
        title = QLabel(f"{self.payload.get('inst_id', '—')} · {self.payload.get('system_name', '—')} · {self.payload.get('timeframe', '—')}")
        title.setStyleSheet("font-size: 17px; font-weight: 900; color: #edf6ff;")
        header_row.addWidget(title, 1)
        side_badge = QLabel(side_text)
        side_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_badge.setMinimumWidth(110)
        side_badge.setStyleSheet(f"font-size: 15px; font-weight: 900; color: #06111f; background: {side_color}; border: 1px solid #d6fff6; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(side_badge)
        status_badge = QLabel("CLOSED")
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setMinimumWidth(110)
        status_badge.setStyleSheet("font-size: 14px; font-weight: 900; color: #fff6e5; background: #473217; border: 1px solid #f59e0b; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(status_badge)
        layout.addLayout(header_row)

        summary = QHBoxLayout()
        summary.setSpacing(10)
        for title_text, value_text, hint_text in [
            ('Entry', self._fmt(self.payload.get('entry_price')), self._time_only(self.payload.get('entry_time'))),
            ('Exit', self._fmt(self.payload.get('exit_price')), self._time_only(self.payload.get('exit_time'))),
            ('PnL', self._fmt_signed(self.payload.get('pnl')), self._fmt_signed(self.payload.get('pnl_pct'), suffix='%')),
            ('Units', str(int(self._num(self.payload.get('units') or 1))), f"Adds {max(0, int(self._num(self.payload.get('units') or 1)) - 1)}"),
            ('Duration', format_duration(self._num(self.payload.get('duration_sec'), 0)), str(self.payload.get('reason', '—'))),
        ]:
            summary.addWidget(self._metric_card(title_text, value_text, hint_text), 1)
        layout.addLayout(summary)

        body_row = QHBoxLayout()
        body_row.setSpacing(10)

        chart_box = QFrame(self)
        chart_box.setProperty('class', 'sectionCard')
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(6)
        chart_title = QLabel(f"График сделки · свечей: {len(self.payload.get('candles') or [])}")
        chart_title.setStyleSheet('color: #9dd8ff; font-size: 13px; font-weight: 700;')
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(TradeLifecycleChartWidget(self.payload, chart_box), 1)
        body_row.addWidget(chart_box, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        right_col.addWidget(self._section_card('RESULT', [
            ('Вход', self._fmt(self.payload.get('entry_price'))),
            ('Выход', self._fmt(self.payload.get('exit_price'))),
            ('PnL', self._fmt_signed(self.payload.get('pnl'))),
            ('PnL %', self._fmt_signed(self.payload.get('pnl_pct'), suffix='%')),
            ('Причина', str(self.payload.get('reason', '—'))),
            ('Длительность', format_duration(self._num(self.payload.get('duration_sec'), 0))),
        ]))
        right_col.addWidget(self._section_card('ENTRY CONTEXT', [
            ('Пробой', str(self.payload.get('system_name', '—'))),
            ('ATR на входе', self._fmt(self.payload.get('entry_atr'))),
            ('Стартовый стоп', self._fmt(self.payload.get('start_stop_price'))),
            ('Канал выхода', self._fmt(self.payload.get('channel_exit_level'))),
            ('MFE / MAE', f"{self._fmt_signed(self.payload.get('mfe_pct'), suffix='%')} / {self._fmt_signed(self.payload.get('mae_pct'), suffix='%')}"),
            ('R multiple', self._fmt_signed(self.payload.get('mfe_r'))),
        ]))
        markers = self.payload.get('markers') or []
        marker_lines = []
        for marker in markers[:8]:
            label = str(marker.get('label') or '•')
            tm = str(marker.get('time') or '—')
            px = self._fmt(marker.get('price'))
            marker_lines.append((label, f"{tm} @ {px}"))
        right_col.addWidget(self._section_card('TIMELINE', marker_lines or [('События', 'нет сохранённых событий')]))
        right_col.addStretch(1)
        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row, 1)

        footer_mode = "LIVE chart + entry context" if bool(self.payload.get("live_chart")) else "ENTRY snapshot"
        footer = QLabel(f"Контекст: {self.context_file}  |  {footer_mode}")
        footer.setStyleSheet('color: #6f8baa; font-size: 11px;')
        layout.addWidget(footer)

        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _section_card(self, title: str, rows: list[tuple[str, str]]):
        card = QFrame(self)
        card.setProperty('class', 'sectionCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        hdr = QLabel(title)
        hdr.setStyleSheet('color: #9dd8ff; font-size: 12px; font-weight: 800;')
        lay.addWidget(hdr)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (name, value) in enumerate(rows):
            a = QLabel(name)
            a.setStyleSheet('color: #86a9c9; font-size: 11px; font-weight: 700;')
            b = QLabel(value if str(value).strip() else '—')
            b.setStyleSheet('color: #f8fbff; font-size: 12px; font-weight: 800;')
            b.setWordWrap(True)
            grid.addWidget(a, i, 0)
            grid.addWidget(b, i, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        return card

    def _metric_card(self, title: str, value: str, hint: str = ''):
        card = QFrame(self)
        card.setProperty('class', 'metricCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet('color: #8bb5d9; font-size: 11px; font-weight: 700;')
        v = QLabel(value if str(value).strip() else '—')
        v.setStyleSheet('color: #f8fbff; font-size: 16px; font-weight: 900;')
        h = QLabel(hint if str(hint).strip() else ' ')
        h.setStyleSheet('color: #8aa6c2; font-size: 10px;')
        lay.addWidget(t); lay.addWidget(v); lay.addWidget(h)
        return card

    @staticmethod
    def _num(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @classmethod
    def _fmt(cls, value) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return '—'

    @classmethod
    def _fmt_signed(cls, value, suffix: str = '') -> str:
        try:
            num = float(value)
            if suffix == '%':
                return f"{num:+.2f}%"
            return f"{num:+.4f}{suffix}"
        except Exception:
            return '—'

    @staticmethod
    def _time_only(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%H:%M:%S')
            except Exception:
                continue
        return txt[-8:]


class TradeLogger:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "time",
                        "event",
                        "inst_id",
                        "side",
                        "qty",
                        "price",
                        "atr",
                        "stop_price",
                        "system_name",
                        "note",
                    ]
                )

    def log(self, event: str, inst_id: str, side: str, qty: float, price: float, atr: float, stop_price: float, system_name: str, note: str = "") -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                event,
                inst_id,
                side,
                qty,
                price,
                atr,
                stop_price,
                system_name,
                note,
            ])


class EngineStatsLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(exist_ok=True)
        self.lock = threading.Lock()

    def log(self, event_type: str, **payload) -> None:
        event = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event_type,
        }
        event.update(self._normalize(payload))
        line = json.dumps(event, ensure_ascii=False)
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _normalize(self, value):
        if isinstance(value, dict):
            return {str(k): self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize(v) for v in value]
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)


class SignalAuditLogger(EngineStatsLogger):
    pass


class OkxGateway:
    COMPLIANCE_RESTRICTION_CODES = {"51155"}
    LOT_SIZE_ERROR_CODES = {"51121"}
    POSITION_LIMIT_ERROR_CODES = {"54031"}
    CLOSE_MARKET_LIMIT_ERROR_CODES = {"51108"}
    CLOSE_REQUIRES_PENDING_CANCEL_CODES = {"51115", "51117"}

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.account_api = Account.AccountAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.market_api = MarketData.MarketAPI(flag=cfg.flag)
        self.public_api = PublicData.PublicAPI(flag=cfg.flag)
        self.trade_api = Trade.TradeAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.instrument_cache: Dict[str, dict] = {}
        self.swap_ids: List[str] = []
        self.cache: Optional[MarketDataCache] = None
        self.engine_ref = None
        self.refresh_instruments()

    def refresh_instruments(self) -> None:
        resp = self.public_api.get_instruments(instType="SWAP")
        data = resp.get("data", [])
        self.instrument_cache = {x["instId"]: x for x in data if x.get("state") == "live"}
        self.swap_ids = sorted([
            inst_id for inst_id in self.instrument_cache
            if inst_id.endswith("-USDT-SWAP") and not is_hidden_instrument(inst_id)
        ])
        logging.info("Loaded %s swap instruments", len(self.swap_ids))

    def get_account_balance(self) -> dict:
        return self.account_api.get_account_balance()

    def get_positions(self) -> List[dict]:
        resp = self.account_api.get_positions(instType="SWAP")
        return resp.get("data", [])

    def attach_cache(self, cache: Optional[MarketDataCache]) -> None:
        self.cache = cache

    def fetch_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        # OKX returns newest first; convert to oldest -> newest and close only closed candles (skip newest forming candle).
        resp = self.market_api.get_candlesticks(instId=inst_id, bar=bar, limit=str(limit + 1))
        raw = resp.get("data", [])
        if len(raw) < limit + 1:
            return []
        closed = raw[1 : limit + 1]
        closed.reverse()
        candles: List[List[float]] = []
        for row in closed:
            candles.append([
                int(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]) if len(row) > 5 else 0.0,
            ])
        return candles

    def get_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        if self.cache is not None:
            cached = self.cache.get_candles(inst_id, bar, limit)
            if cached is not None:
                return cached
        candles = self.fetch_candles(inst_id, bar, limit)
        if candles and self.cache is not None:
            self.cache.put_candles(inst_id, bar, candles)
        return candles

    def fetch_ticker_data(self, inst_id: str) -> dict:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return data[0]

    def get_ticker_last(self, inst_id: str) -> float:
        data = self.get_ticker_data(inst_id)
        return float(data["last"])

    def get_ticker_data(self, inst_id: str) -> dict:
        if self.cache is not None:
            cached = self.cache.get_ticker(inst_id)
            if cached is not None:
                return cached
        data = self.fetch_ticker_data(inst_id)
        if self.cache is not None:
            self.cache.put_ticker(inst_id, data)
        return data

    def instrument_info(self, inst_id: str) -> dict:
        info = self.instrument_cache.get(inst_id)
        if not info:
            self.refresh_instruments()
            info = self.instrument_cache.get(inst_id)
        if not info:
            raise KeyError(f"Instrument not found: {inst_id}")
        return info

    def get_pending_orders(self, inst_id: str) -> List[dict]:
        try:
            resp = self.trade_api.get_order_list(instType="SWAP", instId=inst_id)
            return list(resp.get("data", []) or [])
        except Exception as exc:
            logging.warning("Failed to load pending orders for %s: %s", inst_id, exc)
            return []

    def cancel_pending_orders(self, inst_id: str) -> dict:
        pending = self.get_pending_orders(inst_id)
        payload = []
        for order in pending:
            ord_id = str(order.get("ordId") or "").strip()
            cl_ord_id = str(order.get("clOrdId") or "").strip()
            if not ord_id and not cl_ord_id:
                continue
            item = {"instId": inst_id}
            if ord_id:
                item["ordId"] = ord_id
            elif cl_ord_id:
                item["clOrdId"] = cl_ord_id
            payload.append(item)
        if not payload:
            return {"code": "0", "msg": "no_pending_orders", "count": 0, "data": []}
        resp = self.trade_api.cancel_multiple_orders(payload)
        resp["count"] = len(payload)
        return resp

    def get_pending_algo_orders(self, inst_id: str) -> List[dict]:
        rows: List[dict] = []
        seen: set[tuple[str, str]] = set()
        for ord_type in ("conditional", "oco", "trigger", "move_order_stop", "iceberg", "twap", "chase"):
            try:
                resp = self.trade_api.order_algos_list(ordType=ord_type, instType="SWAP", instId=inst_id)
                for row in list(resp.get("data", []) or []):
                    algo_id = str(row.get("algoId") or "").strip()
                    if not algo_id:
                        continue
                    key = (ord_type, algo_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
            except Exception:
                continue
        return rows

    def cancel_pending_algo_orders(self, inst_id: str) -> dict:
        pending = self.get_pending_algo_orders(inst_id)
        payload = []
        for row in pending:
            algo_id = str(row.get("algoId") or "").strip()
            if not algo_id:
                continue
            payload.append({
                "instId": inst_id,
                "algoId": algo_id,
            })
        if not payload:
            return {"code": "0", "msg": "no_pending_algo_orders", "count": 0, "data": []}
        resp = self.trade_api.cancel_algo_order(payload)
        resp["count"] = len(payload)
        return resp

    def cancel_pending_close_orders(self, inst_id: str) -> dict:
        normal = self.cancel_pending_orders(inst_id)
        algo = self.cancel_pending_algo_orders(inst_id)
        return {
            "code": "0" if normal.get("code") == "0" and algo.get("code") == "0" else "1",
            "msg": "pending_close_orders_cancelled" if normal.get("code") == "0" and algo.get("code") == "0" else "pending_close_orders_cancel_failed",
            "normal": normal,
            "algo": algo,
        }

    def close_position(self, inst_id: str, note: str = "", auto_cancel: bool = False) -> dict:
        logging.info("Closing position %s. %s", inst_id, note)
        use_auto_cancel = "true" if auto_cancel or bool(getattr(self.cfg, "auto_cancel_pending_close_orders", True)) else ""
        return self.trade_api.close_positions(instId=inst_id, mgnMode=self.cfg.td_mode, autoCxl=use_auto_cancel)

    def close_position_by_reduce_only(self, inst_id: str, side: str, qty: float) -> dict:
        info = self.instrument_info(inst_id)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)
        close_side = "sell" if side == "long" else "buy"
        remaining = max(0.0, float(qty or 0.0))
        filled = 0.0
        responses = []

        for _ in range(32):
            if remaining < min_sz:
                break
            chunk = remaining
            if max_mkt_sz > 0:
                chunk = min(chunk, max_mkt_sz)
            chunk = float(self.format_size(chunk, lot_sz) or 0.0)
            if chunk < min_sz:
                chunk = min_sz if remaining >= min_sz else 0.0
                chunk = float(self.format_size(chunk, lot_sz) or 0.0)
            if chunk <= 0:
                break
            resp = self.place_market_order(inst_id, close_side, chunk, reduce_only=True)
            responses.append(resp)
            if resp.get("code") != "0":
                return {"code": "1", "msg": "reduce_only_close_failed", "data": responses}
            remaining = max(0.0, remaining - chunk)
            filled += chunk
            if remaining < min_sz:
                break

        return {"code": "0", "msg": "reduce_only_close_ok", "filled": filled, "remaining": remaining, "data": responses}

    def format_size(self, qty: float, lot_sz: float) -> str:
        try:
            qty_dec = Decimal(str(qty))
            step_dec = Decimal(str(lot_sz))
            if step_dec <= 0:
                return format(qty_dec.normalize(), "f")
            units = (qty_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
            normalized = (units * step_dec).normalize()
            return format(normalized, "f")
        except (InvalidOperation, ValueError, TypeError):
            return str(qty)

    def place_market_order(self, inst_id: str, side: str, qty: float, reduce_only: bool = False) -> dict:
        info = self.instrument_info(inst_id)
        params = dict(
            instId=inst_id,
            tdMode=self.cfg.td_mode,
            side=side,
            posSide="net",
            ordType="market",
            sz=self.format_size(qty, float(info.get("lotSz") or 1.0)),
        )
        if reduce_only:
            params["reduceOnly"] = "true"
        logging.info("Placing order %s %s qty=%s", inst_id, side, qty)
        return self.trade_api.place_order(**params)


class TurtleEngine(QObject):
    snapshot = pyqtSignal(dict)
    log_line = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    entry_candidate = pyqtSignal(dict)

    def __init__(self, cfg: BotConfig):
        super().__init__()
        self.cfg = cfg
        self.gateway = OkxGateway(cfg)
        self.gateway.engine_ref = self
        self.market_data_cache = MarketDataCache(self.gateway, cfg, log_callback=self.log_line.emit)
        self.gateway.attach_cache(self.market_data_cache)
        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)
        self.signal_audit_logger = SignalAuditLogger(SIGNAL_AUDIT_FILE)
        self.position_journal_logger = EngineStatsLogger(POSITION_JOURNAL_FILE)
        self.position_snapshot_logger = EngineStatsLogger(POSITION_SNAPSHOTS_FILE)
        self.system_health_logger = EngineStatsLogger(SYSTEM_HEALTH_FILE)
        self.pyramid_diagnostics_logger = EngineStatsLogger(PYRAMID_DIAGNOSTICS_FILE)
        self.reentry_diagnostics_logger = EngineStatsLogger(REENTRY_DIAGNOSTICS_FILE)
        self.breakout_quality_logger = EngineStatsLogger(BREAKOUT_QUALITY_FILE)
        self.running = False
        self.lock = threading.Lock()
        self.position_state: Dict[str, PositionState] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.balance_history: List[dict] = []
        self.balance_lock = threading.Lock()
        self.latest_balance_snapshot: dict = {}
        self.balance_poller_running = False
        self.balance_poller_thread: Optional[threading.Thread] = None
        self._load_state()
        self.last_scan_started_at: Optional[float] = None
        self.last_scan_finished_at: Optional[float] = None
        self.last_positions_check_at: Optional[float] = None
        self.last_entry_scan_at: Optional[float] = None
        self.last_snapshot_emitted_at: Optional[float] = None
        self.last_position_snapshot_minute: Optional[str] = None
        self.last_system_health_minute: Optional[str] = None
        self.blocked_instruments: Dict[str, str] = {}
        self.temp_blocked_until: Dict[str, float] = {}
        self.close_retry_after: Dict[str, float] = {}
        self.recent_stopouts: Dict[str, dict] = {}
        self.illiquid_instruments: Dict[str, float] = {}
        self.illiquid_rejections: Dict[str, dict] = {}
        self.execution_risk_events: Dict[str, dict] = {}
        self.telegram = TelegramNotifier(
            enabled=cfg.telegram_enabled,
            bot_token=cfg.telegram_bot_token,
            chat_id=cfg.telegram_chat_id,
        )
        self._manual_entry_event = threading.Event()
        self._manual_entry_allowed = False
        self.scan_cycle_seq = 0
        self.recent_rotation_exits: Dict[str, float] = {}
        self.last_scan_candidates: List[dict] = []
        self.last_near_pass_candidates: List[dict] = []
        self.last_signal_funnel: Dict[str, int] = {}
        self.last_scan_cycle_id: int = 0
        self.last_trade_ready_metrics: Dict[str, object] = {}
        self.last_trade_ready_log_at: float = 0.0

    def _fmt_price(self, value: float) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return str(value)

    def _notify(self, text: str) -> None:
        try:
            self.telegram.send(text)
        except Exception as exc:
            logging.warning("Telegram notify failed: %s", exc)

    def _emit_snapshot_safe(self) -> None:
        try:
            self.emit_snapshot()
        except Exception as exc:
            logging.warning("Failed to emit immediate snapshot: %s", exc)

    def _append_balance_point_from_account(self, account: dict, point_time: Optional[datetime] = None) -> None:
        data = account.get("data", []) or []
        root = data[0] if data else {}
        details = root.get("details", []) or []
        detail = details[0] if details else {}

        balance_total = self._extract_total_usdt(account)
        balance_available = self._extract_available_usdt(account)
        frozen_value = float(detail.get("frozenBal") or 0.0)
        balance_used = frozen_value if frozen_value > 0 else max(balance_total - balance_available, 0.0)

        dt = point_time or datetime.now()
        point = {
            "time": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "balance_total": float(balance_total),
            "balance_available": float(balance_available),
            "balance_used": float(balance_used),
        }

        with self.balance_lock:
            self.latest_balance_snapshot = dict(point)
            if self.balance_history and str(self.balance_history[-1].get("time", "")) == point["time"]:
                self.balance_history[-1] = point
            else:
                self.balance_history.append(point)
                self.balance_history = self.balance_history[-2000:]

    def _balance_poller_loop(self) -> None:
        interval = max(1, int(getattr(self.cfg, "balance_refresh_sec", 5) or 5))
        while self.running and self.balance_poller_running:
            try:
                account = self.gateway.get_account_balance()
                self._append_balance_point_from_account(account)
            except Exception as exc:
                logging.warning("Balance poller failed: %s", exc)
                self.log_line.emit(f"Не удалось опросить баланс: {exc}")
            slept = 0.0
            while self.running and self.balance_poller_running and slept < interval:
                time.sleep(0.2)
                slept += 0.2

    def start_balance_poller(self) -> None:
        if self.balance_poller_running:
            return
        self.balance_poller_running = True
        self.balance_poller_thread = threading.Thread(target=self._balance_poller_loop, name="BalancePoller", daemon=True)
        self.balance_poller_thread.start()
        self.log_line.emit(f"Независимый опрос баланса запущен (каждые {max(1, int(getattr(self.cfg, 'balance_refresh_sec', 5) or 5))}с)")

    def stop_balance_poller(self) -> None:
        self.balance_poller_running = False
        thread = self.balance_poller_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self.balance_poller_thread = None

    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []
            self.latest_balance_snapshot = {}
            self.latest_balance_snapshot = {}
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "positions" in data:
                self.position_state = {k: PositionState(**v) for k, v in data.get("positions", {}).items()}
                self.closed_trades = [ClosedTrade(**x) for x in data.get("closed_trades", [])]
                self.balance_history = list(data.get("balance_history", []))[-2000:]
                self.latest_balance_snapshot = dict(self.balance_history[-1]) if self.balance_history else {}
            else:
                # backward compatibility with old file that stored only positions dict
                self.position_state = {k: PositionState(**v) for k, v in data.items()}
                self.closed_trades = []
                self.balance_history = []
                self.latest_balance_snapshot = {}
        except Exception as exc:
            logging.warning("Failed to load state: %s", exc)
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []
            self.latest_balance_snapshot = {}

    def _save_state(self) -> None:
        with self.balance_lock:
            balance_history_copy = list(self.balance_history[-2000:])

        visible_open_positions = []
        for inst_id, state in self.position_state.items():
            if is_hidden_instrument(inst_id):
                continue
            last_px = _safe_float(getattr(state, 'last_px', 0.0))
            avg_px = _safe_float(getattr(state, 'avg_px', 0.0))
            atr = _safe_float(getattr(state, 'atr', 0.0))
            pnl_pct = ((last_px - avg_px) / avg_px * 100.0) if avg_px > 0 and getattr(state, 'side', '') == 'long' else 0.0
            if avg_px > 0 and getattr(state, 'side', '') == 'short':
                pnl_pct = ((avg_px - last_px) / avg_px * 100.0)
            try:
                entry_ts = datetime.strptime(str(getattr(state, 'entry_time', '') or ''), '%Y-%m-%d %H:%M:%S').timestamp()
                position_age_sec = max(0, int(time.time() - entry_ts))
            except Exception:
                position_age_sec = 0
            visible_open_positions.append({
                'trade_id': str(getattr(state, 'trade_id', '') or ''),
                'inst_id': str(getattr(state, 'inst_id', inst_id) or inst_id),
                'side': str(getattr(state, 'side', '') or ''),
                'last_px': last_px,
                'avg_px': avg_px,
                'stop_price': _safe_float(getattr(state, 'stop_price', 0.0)),
                'next_pyramid_price': _safe_float(getattr(state, 'next_pyramid_price', 0.0)),
                'units': _safe_int(getattr(state, 'units', 0)),
                'qty': _safe_float(getattr(state, 'qty', 0.0)),
                'unrealized_pnl': _safe_float(getattr(state, 'unrealized_pnl', 0.0)),
                'pnl_pct': _safe_float(pnl_pct),
                'peak_pnl_pct': _safe_float(getattr(state, 'peak_pnl_pct', 0.0)),
                'mae_pct': _safe_float(getattr(state, 'mae_pct', 0.0)),
                'atr': atr,
                'position_age_sec': position_age_sec,
            })
        visible_closed_trades = [x for x in self.closed_trades if not is_hidden_instrument(getattr(x, 'inst_id', ''))]

        current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
        if current_minute != self.last_position_snapshot_minute:
            for row in visible_open_positions:
                self.position_snapshot_logger.log(
                    'POSITION_SNAPSHOT',
                    trade_id=row.get('trade_id', ''),
                    inst_id=row.get('inst_id', ''),
                    side=row.get('side', ''),
                    price=_safe_float(row.get('last_px', 0.0)),
                    avg_entry_price=_safe_float(row.get('avg_px', 0.0)),
                    stop_price=_safe_float(row.get('stop_price', 0.0)),
                    next_unit_level=_safe_float(row.get('next_pyramid_price', 0.0)),
                    units=_safe_int(row.get('units', 0)),
                    qty_total=_safe_float(row.get('qty', 0.0)),
                    pnl_usd=_safe_float(row.get('unrealized_pnl', 0.0)),
                    pnl_pct=_safe_float(row.get('pnl_pct', 0.0)),
                    mfe_pct=_safe_float(row.get('peak_pnl_pct', 0.0)),
                    mae_pct=_safe_float(row.get('mae_pct', 0.0)),
                    atr=_safe_float(row.get('atr', 0.0)),
                    position_age_sec=_safe_int(row.get('position_age_sec', 0)),
                    note='Минутный snapshot позиции',
                )
            self.last_position_snapshot_minute = current_minute
        if current_minute != self.last_system_health_minute:
            cache_stats = self.market_data_cache.snapshot_stats() if getattr(self, 'market_data_cache', None) else {}
            self.system_health_logger.log(
                'SYSTEM_HEALTH',
                open_positions=len(visible_open_positions),
                closed_trades=len(visible_closed_trades),
                loop_duration_sec=_safe_float(getattr(self, 'last_cycle_duration_sec', 0.0)),
                symbols_scanned=_safe_int(getattr(self, 'last_scan_universe_total', len(getattr(self.gateway, 'swap_ids', []) or []))),
                signals_found=_safe_int((getattr(self, 'last_signal_funnel', {}) or {}).get('candidates', 0)),
                signals_blocked=_safe_int((getattr(self, 'last_signal_funnel', {}) or {}).get('rejected', 0)),
                cache_errors=_safe_int((cache_stats or {}).get('error_count', 0)),
                cache_fetch_count=_safe_int((cache_stats or {}).get('fetch_count', 0)),
                available_after_bans=_safe_int(len([inst for inst in getattr(self.gateway, 'swap_ids', []) if inst not in self.blocked_instruments and not is_hidden_instrument(inst)])),
            )
            self.last_system_health_minute = current_minute

        payload = {
            "positions": {k: asdict(v) for k, v in self.position_state.items()},
            "closed_trades": [asdict(x) for x in self.closed_trades[-500:]],
            "balance_history": balance_history_copy,
        }
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.stats_logger.log(
            "bot_started",
            version=APP_VERSION,
            account=("main" if self.cfg.flag == "0" else "demo"),
            timeframe=self.cfg.timeframe,
            scan_interval_sec=self.cfg.scan_interval_sec,
            position_check_interval_sec=self.cfg.position_check_interval_sec,
            snapshot_interval_sec=self.cfg.snapshot_interval_sec,
            risk_per_trade_pct=self.cfg.risk_per_trade_pct,
            max_position_notional_pct=self.cfg.max_position_notional_pct,
            max_units_per_symbol=self.cfg.max_units_per_symbol,
            pyramid_scales=[
                1.0,
                self.cfg.pyramid_second_unit_scale,
                self.cfg.pyramid_third_unit_scale,
                self.cfg.pyramid_fourth_unit_scale,
            ],
            breakout_mode="classic_turtle",
            structure_filter_enabled=False,
            max_open_positions_total=self.cfg.max_open_positions_total,
            max_open_positions_per_side=self.cfg.max_open_positions_per_side,
            liquidity_filter_enabled=bool(getattr(self.cfg, "liquidity_filter_enabled", True)),
            blacklist=list(self.cfg.blacklist),
        )
        self.position_journal_logger.log("session_start", version=APP_VERSION, timeframe=self.cfg.timeframe, account=("main" if self.cfg.flag == "0" else "demo"))
        self.market_data_cache.start()
        self.start_balance_poller()
        self.status.emit("Бот запущен")
        tf_profile = self._timeframe_filter_profile()
        self.log_line.emit(f"Торговый движок запущен (шаг: {self.cfg.timeframe}, режим: {self.cfg.trade_mode})")
        self.log_line.emit(
            "Профиль фильтров: {label} | ATR>={atr:.3f}% | RANGE>={rng:.3f}% | CH/ATR>={car:.2f} | TREND>={trend:.2f} ATR | BUF={buf:.3f} ATR".format(
                label=tf_profile.get("label", self.cfg.timeframe),
                atr=float(tf_profile.get("min_atr_pct", 0.0)),
                rng=float(tf_profile.get("min_channel_range_pct", 0.0)),
                car=float(tf_profile.get("flat_min_channel_atr_ratio", 0.0)),
                trend=float(tf_profile.get("trend_slope_atr_min", 0.0)),
                buf=float(tf_profile.get("breakout_buffer_atr", 0.0)),
            )
        )
        self._notify("✅ OKX Turtle Bot запущен")
        self.run_loop()

    def stop(self) -> None:
        self.running = False
        self.market_data_cache.stop()
        self.stop_balance_poller()
        self.stats_logger.log(
            "bot_stopped",
            open_positions=len(self.position_state),
            closed_trades=len(self.closed_trades),
        )
        self.position_journal_logger.log("session_stop", open_positions=len(self.position_state), closed_trades=len(self.closed_trades))
        self.status.emit("Бот остановлен")
        self.log_line.emit("Получена команда остановки")
        self._notify("⛔ OKX Turtle Bot остановлен")

    def run_loop(self) -> None:
        while self.running:
            cycle_started_at = time.time()
            try:
                self.last_scan_started_at = cycle_started_at
                self.stats_logger.log(
                    "cycle_started",
                    open_positions=len(self.position_state),
                    blocked_instruments=len(self.blocked_instruments),
                    timeframe=self.cfg.timeframe,
                )
                self.sync_positions_from_exchange()
                self.scan_markets()
                self.manage_open_positions()
                self.emit_snapshot()
                self.last_scan_finished_at = time.time()
                self.stats_logger.log(
                    "cycle_finished",
                    duration_sec=round(self.last_scan_finished_at - cycle_started_at, 3),
                    open_positions=len(self.position_state),
                    closed_trades=len(self.closed_trades),
                )
            except Exception as exc:
                msg = f"Ошибка в цикле стратегии: {exc}"
                logging.exception(msg)
                self.stats_logger.log("cycle_error", error=str(exc))
                self.error.emit(msg)
                self.log_line.emit(msg)
                self._notify(f"⚠️ Ошибка в цикле стратегии\n\n{msg}")
            time.sleep(self.cfg.scan_interval_sec)

    def sync_positions_from_exchange(self) -> None:
        exchange_positions = self.gateway.get_positions()
        seen = set()
        changed = False
        for pos in exchange_positions:
            inst_id = pos.get("instId")
            pos_side = self._detect_side_from_pos(pos)
            if not inst_id or pos_side not in {"long", "short"}:
                continue
            seen.add(inst_id)
            qty = abs(float(pos.get("pos") or 0.0))
            if qty <= 0:
                continue
            avg_px = float(pos.get("avgPx") or 0.0)
            last_px = float(pos.get("markPx") or pos.get("last") or avg_px)
            upl = float(pos.get("upl") or 0.0)
            margin = float(pos.get("margin") or 0.0)
            current = self.position_state.get(inst_id)
            if current:
                current.qty = qty
                current.avg_px = avg_px
                current.last_px = last_px
                current.unrealized_pnl = upl
                current.margin = margin
                if float(getattr(current, "initial_stop_price", 0.0) or 0.0) <= 0.0 and float(getattr(current, "stop_price", 0.0) or 0.0) > 0.0:
                    current.initial_stop_price = float(current.stop_price)
                if float(getattr(current, "peak_price", 0.0) or 0.0) <= 0.0:
                    current.peak_price = max(last_px, avg_px)
                if float(getattr(current, "trough_price", 0.0) or 0.0) <= 0.0:
                    current.trough_price = min(last_px, avg_px)
            else:
                changed = True
                atr = self.compute_atr(inst_id)
                stop_price = avg_px - self.cfg.atr_stop_multiple * atr if pos_side == "long" else avg_px + self.cfg.atr_stop_multiple * atr
                next_pyramid = avg_px + self.cfg.add_unit_every_atr * atr if pos_side == "long" else avg_px - self.cfg.add_unit_every_atr * atr
                self.position_state[inst_id] = PositionState(
                    inst_id=inst_id,
                    side=pos_side,
                    qty=qty,
                    avg_px=avg_px,
                    last_px=last_px,
                    unrealized_pnl=upl,
                    margin=margin,
                    atr=atr,
                    stop_price=stop_price,
                    next_pyramid_price=next_pyramid,
                    entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    system_name="sync",
                    entry_period=self.cfg.long_entry_period if pos_side == "long" else self.cfg.short_entry_period,
                    exit_period=self.cfg.long_exit_period if pos_side == "long" else self.cfg.short_exit_period,
                    initial_stop_price=stop_price,
                    peak_price=max(last_px, avg_px),
                    trough_price=min(last_px, avg_px),
                    peak_unrealized_pnl=max(upl, 0.0),
                    peak_pnl_pct=0.0,
                    trade_id=_stable_trade_id(inst_id, pos_side, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
        removed = []
        for inst_id in list(self.position_state):
            if inst_id not in seen:
                removed.append(inst_id)
                prev_state = self.position_state.get(inst_id)
                if prev_state is not None and bool(getattr(prev_state, "close_pending", False)):
                    self._finalize_closed_trade(prev_state, float(getattr(prev_state, "last_px", 0.0) or getattr(prev_state, "avg_px", 0.0) or 0.0), "SYNC confirmed close after pending request")
                elif inst_id in self.position_state:
                    del self.position_state[inst_id]
                changed = True
        self._save_state()
        self.stats_logger.log(
            "positions_synced",
            exchange_positions=len(exchange_positions),
            tracked_positions=len(self.position_state),
            removed_positions=removed,
        )

    def _detect_side_from_pos(self, pos: dict) -> Optional[str]:
        pos_value = float(pos.get("pos") or 0.0)
        if pos_value > 0:
            return "long"
        if pos_value < 0:
            return "short"
        side = (pos.get("posSide") or "").lower()
        if side in {"long", "short"}:
            return side
        return None

    def _timeframe_seconds(self) -> int:
        tf = str(self.cfg.timeframe or "").strip().lower()
        mapping = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "12h": 43200,
            "1d": 86400,
        }
        return mapping.get(tf, 900)

    def _minimal_turtle_entry_mode(self) -> bool:
        return bool(getattr(self.cfg, "minimal_turtle_entry_mode", True))

    def _stopout_cooldown_seconds(self) -> int:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            bars = max(6, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 900:
            bars = max(5, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 3600:
            bars = max(4, int(self.cfg.cooldown_after_stop_bars) - 1)
        else:
            bars = max(3, int(self.cfg.cooldown_after_stop_bars) - 2)

        raw = tf_sec * bars
        raw = max(int(self.cfg.cooldown_min_seconds), raw)
        raw = min(int(self.cfg.cooldown_max_seconds), raw)
        return raw

    def _tf_entry_profile(self) -> dict:
        tf = str(self.cfg.timeframe or "5m").strip().lower()
        base = {
            "strict_min": 1.00,
            "strict_max": 1.00,
            "lookback_bonus": 1.00,
            "label": str(self.cfg.timeframe),
            "liquidity": {
                "max_spread_pct": float(self.cfg.liquidity_max_spread_pct),
                "min_top_book_usdt": float(self.cfg.liquidity_min_top_of_book_usdt),
                "min_side_notional_usdt": float(self.cfg.liquidity_min_side_notional_usdt),
                "min_24h_quote_volume": float(self.cfg.liquidity_min_24h_quote_volume),
                "max_last_mid_deviation_ratio": 0.0045,
                "soft_side_ratio": 0.45,
            },
        }

        profiles = {
            "1m": {
                "label": "1m",
                "strict_min": 0.72,
                "strict_max": 1.10,
                "lookback_bonus": 1.06,
                "liquidity": {
                    "max_spread_pct": 0.60,
                    "min_top_book_usdt": 90.0,
                    "min_side_notional_usdt": 220.0,
                    "min_24h_quote_volume": 180000.0,
                    "max_last_mid_deviation_ratio": 0.0080,
                    "soft_side_ratio": 0.32,
                },
            },
            "5m": {
                "label": "5m",
                "strict_min": 0.88,
                "strict_max": 1.04,
                "lookback_bonus": 1.10,
                "liquidity": {
                    "max_spread_pct": 0.32,
                    "min_top_book_usdt": 260.0,
                    "min_side_notional_usdt": 620.0,
                    "min_24h_quote_volume": 800000.0,
                    "max_last_mid_deviation_ratio": 0.0058,
                    "soft_side_ratio": 0.40,
                },
            },
            "15m": {
                "label": "15m",
                "strict_min": 1.00,
                "strict_max": 1.00,
                "lookback_bonus": 1.00,
                "liquidity": {
                    "max_spread_pct": 0.20,
                    "min_top_book_usdt": 1200.0,
                    "min_side_notional_usdt": 2500.0,
                    "min_24h_quote_volume": 2500000.0,
                    "max_last_mid_deviation_ratio": 0.0045,
                    "soft_side_ratio": 0.45,
                },
            },
            "30m": {
                "label": "30m",
                "strict_min": 1.08,
                "strict_max": 0.96,
                "lookback_bonus": 0.96,
                "liquidity": {
                    "max_spread_pct": 0.17,
                    "min_top_book_usdt": 1800.0,
                    "min_side_notional_usdt": 3800.0,
                    "min_24h_quote_volume": 4200000.0,
                    "max_last_mid_deviation_ratio": 0.0039,
                    "soft_side_ratio": 0.47,
                },
            },
            "1h": {
                "label": "1H",
                "strict_min": 1.18,
                "strict_max": 0.92,
                "lookback_bonus": 0.92,
                "liquidity": {
                    "max_spread_pct": 0.14,
                    "min_top_book_usdt": 2500.0,
                    "min_side_notional_usdt": 5500.0,
                    "min_24h_quote_volume": 6500000.0,
                    "max_last_mid_deviation_ratio": 0.0035,
                    "soft_side_ratio": 0.48,
                },
            },
            "4h": {
                "label": "4H",
                "strict_min": 1.30,
                "strict_max": 0.88,
                "lookback_bonus": 0.88,
                "liquidity": {
                    "max_spread_pct": 0.12,
                    "min_top_book_usdt": 3200.0,
                    "min_side_notional_usdt": 7000.0,
                    "min_24h_quote_volume": 9000000.0,
                    "max_last_mid_deviation_ratio": 0.0030,
                    "soft_side_ratio": 0.50,
                },
            },
        }
        return {**base, **profiles.get(tf, profiles["5m"])}

    def _timeframe_filter_profile(self) -> dict:
        tf = str(self.cfg.timeframe or "5m").strip().lower()
        profiles = {
            "1m": {
                "label": "1m",
                "min_channel_range_pct": 0.10,
                "min_atr_pct": 0.028,
                "flat_min_channel_atr_ratio": 0.90,
                "min_efficiency_ratio": 0.045,
                "max_direction_flip_ratio": 0.96,
                "flat_max_wick_to_range_ratio": 0.94,
                "trend_slope_atr_min": 0.045,
                "breakout_buffer_atr": 0.055,
                "breakout_min_body_atr": 0.12,
                "min_body_to_range_ratio": 0.16,
                "breakout_close_near_extreme_ratio": 0.16,
                "breakout_max_prebreak_distance_atr": 0.70,
                "breakout_max_distance_atr": 0.80,
                "preferred_breakout_distance_atr_min": 0.02,
                "preferred_breakout_distance_atr_max": 0.35,
                "quality_atr_good_min": 0.05,
                "quality_atr_good_max": 0.20,
                "quality_atr_ok_max": 0.35,
                "quality_channel_good_min": 1.10,
                "quality_channel_good_max": 4.20,
                "quality_channel_ok_max": 6.50,
                "quality_slope_bonus_from": 0.10,
            },
            "5m": {
                "label": "5m",
                "min_channel_range_pct": 0.22,
                "min_atr_pct": 0.055,
                "flat_min_channel_atr_ratio": 1.10,
                "min_efficiency_ratio": 0.075,
                "max_direction_flip_ratio": 0.88,
                "flat_max_wick_to_range_ratio": 0.90,
                "trend_slope_atr_min": 0.08,
                "breakout_buffer_atr": 0.08,
                "breakout_min_body_atr": 0.16,
                "min_body_to_range_ratio": 0.20,
                "breakout_close_near_extreme_ratio": 0.22,
                "breakout_max_prebreak_distance_atr": 0.55,
                "breakout_max_distance_atr": 0.62,
                "preferred_breakout_distance_atr_min": 0.04,
                "preferred_breakout_distance_atr_max": 0.30,
                "quality_atr_good_min": 0.10,
                "quality_atr_good_max": 0.32,
                "quality_atr_ok_max": 0.55,
                "quality_channel_good_min": 1.40,
                "quality_channel_good_max": 4.50,
                "quality_channel_ok_max": 7.00,
                "quality_slope_bonus_from": 0.16,
            },
            "15m": {
                "label": "15m",
                "min_channel_range_pct": 0.35,
                "min_atr_pct": 0.075,
                "flat_min_channel_atr_ratio": 1.25,
                "min_efficiency_ratio": 0.10,
                "max_direction_flip_ratio": 0.84,
                "flat_max_wick_to_range_ratio": 0.88,
                "trend_slope_atr_min": 0.10,
                "breakout_buffer_atr": 0.10,
                "breakout_min_body_atr": 0.20,
                "min_body_to_range_ratio": 0.22,
                "breakout_close_near_extreme_ratio": 0.25,
                "breakout_max_prebreak_distance_atr": 0.45,
                "breakout_max_distance_atr": 0.50,
                "preferred_breakout_distance_atr_min": 0.05,
                "preferred_breakout_distance_atr_max": 0.30,
                "quality_atr_good_min": 0.16,
                "quality_atr_good_max": 0.45,
                "quality_atr_ok_max": 0.80,
                "quality_channel_good_min": 1.60,
                "quality_channel_good_max": 4.50,
                "quality_channel_ok_max": 7.50,
                "quality_slope_bonus_from": 0.18,
            },
            "30m": {
                "label": "30m",
                "min_channel_range_pct": 0.50,
                "min_atr_pct": 0.090,
                "flat_min_channel_atr_ratio": 1.35,
                "min_efficiency_ratio": 0.11,
                "max_direction_flip_ratio": 0.82,
                "flat_max_wick_to_range_ratio": 0.86,
                "trend_slope_atr_min": 0.115,
                "breakout_buffer_atr": 0.12,
                "breakout_min_body_atr": 0.22,
                "min_body_to_range_ratio": 0.24,
                "breakout_close_near_extreme_ratio": 0.28,
                "breakout_max_prebreak_distance_atr": 0.42,
                "breakout_max_distance_atr": 0.46,
                "preferred_breakout_distance_atr_min": 0.06,
                "preferred_breakout_distance_atr_max": 0.28,
                "quality_atr_good_min": 0.20,
                "quality_atr_good_max": 0.60,
                "quality_atr_ok_max": 1.00,
                "quality_channel_good_min": 1.80,
                "quality_channel_good_max": 5.00,
                "quality_channel_ok_max": 8.00,
                "quality_slope_bonus_from": 0.20,
            },
            "1h": {
                "label": "1H",
                "min_channel_range_pct": 0.80,
                "min_atr_pct": 0.120,
                "flat_min_channel_atr_ratio": 1.55,
                "min_efficiency_ratio": 0.12,
                "max_direction_flip_ratio": 0.80,
                "flat_max_wick_to_range_ratio": 0.84,
                "trend_slope_atr_min": 0.13,
                "breakout_buffer_atr": 0.14,
                "breakout_min_body_atr": 0.24,
                "min_body_to_range_ratio": 0.26,
                "breakout_close_near_extreme_ratio": 0.30,
                "breakout_max_prebreak_distance_atr": 0.38,
                "breakout_max_distance_atr": 0.42,
                "preferred_breakout_distance_atr_min": 0.08,
                "preferred_breakout_distance_atr_max": 0.26,
                "quality_atr_good_min": 0.24,
                "quality_atr_good_max": 0.80,
                "quality_atr_ok_max": 1.20,
                "quality_channel_good_min": 2.00,
                "quality_channel_good_max": 5.50,
                "quality_channel_ok_max": 8.50,
                "quality_slope_bonus_from": 0.24,
            },
            "4h": {
                "label": "4H",
                "min_channel_range_pct": 1.30,
                "min_atr_pct": 0.180,
                "flat_min_channel_atr_ratio": 1.80,
                "min_efficiency_ratio": 0.14,
                "max_direction_flip_ratio": 0.78,
                "flat_max_wick_to_range_ratio": 0.82,
                "trend_slope_atr_min": 0.16,
                "breakout_buffer_atr": 0.18,
                "breakout_min_body_atr": 0.28,
                "min_body_to_range_ratio": 0.28,
                "breakout_close_near_extreme_ratio": 0.33,
                "breakout_max_prebreak_distance_atr": 0.34,
                "breakout_max_distance_atr": 0.38,
                "preferred_breakout_distance_atr_min": 0.10,
                "preferred_breakout_distance_atr_max": 0.24,
                "quality_atr_good_min": 0.30,
                "quality_atr_good_max": 1.20,
                "quality_atr_ok_max": 1.80,
                "quality_channel_good_min": 2.20,
                "quality_channel_good_max": 6.00,
                "quality_channel_ok_max": 9.00,
                "quality_slope_bonus_from": 0.28,
            },
        }
        profile = profiles.get(tf, profiles["5m"]).copy()
        profile["timeframe"] = str(self.cfg.timeframe)
        return profile


    def _clear_expired_runtime_blocks(self) -> None:
        now_ts = time.time()
        for mapping in (self.temp_blocked_until, self.illiquid_instruments, self.recent_rotation_exits):
            for inst_id, until_ts in list(mapping.items()):
                try:
                    if float(until_ts or 0.0) <= now_ts:
                        mapping.pop(inst_id, None)
                except Exception:
                    mapping.pop(inst_id, None)

    def _is_temporarily_blocked(self, inst_id: str) -> tuple[bool, str]:
        until_ts = float(self.temp_blocked_until.get(inst_id, 0.0) or 0.0)
        if until_ts <= 0:
            return False, ""
        now_ts = time.time()
        if until_ts <= now_ts:
            self.temp_blocked_until.pop(inst_id, None)
            return False, ""
        ttl = max(1, int(until_ts - now_ts))
        return True, f"temporary_quarantine_{ttl}s"

    def _register_execution_risk(self, inst_id: str, reason: str, stage: str = "runtime", severity: float = 1.0, quarantine: bool = False) -> None:
        now_ts = time.time()
        item = dict(self.execution_risk_events.get(inst_id, {}))
        repeats = int(item.get("count", 0)) + 1
        score = float(item.get("score", 0.0) or 0.0) + float(severity or 0.0)
        item.update({
            "count": repeats,
            "score": round(score, 3),
            "last_reason": str(reason or ""),
            "last_stage": str(stage or "runtime"),
            "last_ts": now_ts,
        })
        self.execution_risk_events[inst_id] = item
        state = self.position_state.get(inst_id)
        if state is not None:
            state.execution_risk_score = score
        should_quarantine = quarantine or repeats >= max(1, int(getattr(self.cfg, "execution_issue_repeats_for_quarantine", 2) or 2))
        if should_quarantine:
            hours = max(1, int(getattr(self.cfg, "execution_quarantine_hours", 6) or 6))
            until_ts = now_ts + hours * 3600
            self.temp_blocked_until[inst_id] = max(float(self.temp_blocked_until.get(inst_id, 0.0) or 0.0), until_ts)
            self.stats_logger.log(
                "execution_risk_quarantine",
                inst_id=inst_id,
                stage=stage,
                reason=reason,
                risk_score=round(score, 3),
                repeats=repeats,
                quarantine_hours=hours,
            )

    def _exchange_position_is_open(self, inst_id: str) -> bool:
        try:
            for pos in self.gateway.get_positions():
                if str(pos.get("instId") or "") != str(inst_id):
                    continue
                try:
                    if abs(float(pos.get("pos") or 0.0)) > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            return True
        return False

    def _block_illiquid_instrument(self, inst_id: str, reason: str) -> None:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            hours = 1
        elif tf_sec <= 900:
            hours = max(1, int(self.cfg.illiquid_block_hours))
        elif tf_sec <= 3600:
            hours = max(1, int(self.cfg.illiquid_block_hours) // 2 or 1)
        else:
            hours = 1

        until_ts = time.time() + hours * 3600
        self.illiquid_instruments[inst_id] = until_ts

        if inst_id not in self.temp_blocked_until or self.temp_blocked_until.get(inst_id, 0.0) < until_ts:
            self.temp_blocked_until[inst_id] = until_ts

        logging.info("%s: инструмент временно заблокирован как неликвидный на %sч (%s)", inst_id, hours, reason)

    def _register_illiquid_rejection(self, inst_id: str, reason: str) -> tuple[bool, str]:
        now_ts = time.time()
        data = self.illiquid_rejections.get(inst_id, {"count": 0, "last_reason": "", "last_ts": 0.0})

        gap_limit = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        if now_ts - float(data.get("last_ts", 0.0)) > gap_limit * 3:
            data["count"] = 0

        data["count"] = int(data.get("count", 0)) + 1
        data["last_reason"] = reason
        data["last_ts"] = now_ts
        self.illiquid_rejections[inst_id] = data

        repeats_for_ban = max(2, int(self.cfg.illiquid_repeats_for_ban))
        tf_sec = self._timeframe_seconds()

        effective_repeats = repeats_for_ban
        if tf_sec >= 3600:
            effective_repeats += 1

        if data["count"] >= effective_repeats:
            return True, f"{reason}; повторов={data['count']}"

        soft_cd = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        self.temp_blocked_until[inst_id] = max(self.temp_blocked_until.get(inst_id, 0.0), now_ts + soft_cd)
        return False, f"{reason}; мягкий пропуск {data['count']}/{effective_repeats}"

    def _liquidity_thresholds(self) -> dict:
        profile = self._tf_entry_profile()
        liq = dict(profile.get("liquidity") or {})
        return {
            "profile_label": str(profile.get("label") or self.cfg.timeframe),
            "max_spread_pct": float(liq.get("max_spread_pct") or self.cfg.liquidity_max_spread_pct),
            "min_top_book_usdt": float(liq.get("min_top_book_usdt") or self.cfg.liquidity_min_top_of_book_usdt),
            "min_side_notional_usdt": float(liq.get("min_side_notional_usdt") or self.cfg.liquidity_min_side_notional_usdt),
            "min_24h_quote_volume": float(liq.get("min_24h_quote_volume") or self.cfg.liquidity_min_24h_quote_volume),
            "max_last_mid_deviation_ratio": float(liq.get("max_last_mid_deviation_ratio") or 0.0045),
            "soft_side_ratio": float(liq.get("soft_side_ratio") or 0.45),
        }

    def _check_liquidity(self, inst_id: str, price: float) -> tuple[bool, str, dict]:
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception as exc:
            return False, f"нет ticker/ликвидности: {exc}", {}

        thresholds = self._liquidity_thresholds()

        bid_px = float(ticker.get("bidPx") or 0.0)
        ask_px = float(ticker.get("askPx") or 0.0)
        bid_sz = float(ticker.get("bidSz") or 0.0)
        ask_sz = float(ticker.get("askSz") or 0.0)
        vol_24h = float(ticker.get("volCcy24h") or ticker.get("vol24h") or 0.0)

        if bid_px <= 0 or ask_px <= 0:
            return False, "пустой bid/ask", {"profile_label": thresholds["profile_label"]}

        mid = (bid_px + ask_px) / 2.0
        spread_pct = ((ask_px - bid_px) / max(mid, 1e-12)) * 100.0

        best_bid_notional = bid_px * bid_sz
        best_ask_notional = ask_px * ask_sz
        best_side_notional = min(best_bid_notional, best_ask_notional)

        metrics = {
            "profile_label": thresholds["profile_label"],
            "liquidity_filter_enabled": bool(getattr(self.cfg, "liquidity_filter_enabled", True)),
            "spread_pct": spread_pct,
            "best_bid_notional": best_bid_notional,
            "best_ask_notional": best_ask_notional,
            "best_side_notional": best_side_notional,
            "vol_24h": vol_24h,
            "last_mid_deviation_ratio": abs(price - mid) / max(mid, 1e-12),
            "threshold_max_spread_pct": thresholds["max_spread_pct"],
            "threshold_min_top_book_usdt": thresholds["min_top_book_usdt"],
            "threshold_min_side_notional_usdt": thresholds["min_side_notional_usdt"],
            "threshold_min_24h_quote_volume": thresholds["min_24h_quote_volume"],
            "threshold_max_last_mid_deviation_ratio": thresholds["max_last_mid_deviation_ratio"],
            "threshold_soft_side_ratio": thresholds["soft_side_ratio"],
        }

        if not bool(getattr(self.cfg, "liquidity_filter_enabled", True)):
            return True, "liquidity_filter_disabled_for_test", metrics

        if spread_pct > thresholds["max_spread_pct"]:
            return False, (
                f"широкий спред {spread_pct:.3f}% > {thresholds['max_spread_pct']:.3f}% "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if best_bid_notional < thresholds["min_top_book_usdt"] or best_ask_notional < thresholds["min_top_book_usdt"]:
            return False, (
                f"слабый top-of-book {best_side_notional:.0f} USDT < {thresholds['min_top_book_usdt']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if best_side_notional < thresholds["min_side_notional_usdt"] * thresholds["soft_side_ratio"]:
            return False, (
                f"слишком тонкий стакан {best_side_notional:.0f} USDT < "
                f"{thresholds['min_side_notional_usdt'] * thresholds['soft_side_ratio']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if vol_24h > 0 and vol_24h < thresholds["min_24h_quote_volume"]:
            return False, (
                f"низкий 24h объём {vol_24h:.0f} < {thresholds['min_24h_quote_volume']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if metrics["last_mid_deviation_ratio"] > thresholds["max_last_mid_deviation_ratio"]:
            return False, (
                f"последняя цена далеко от mid {metrics['last_mid_deviation_ratio']:.4f} > "
                f"{thresholds['max_last_mid_deviation_ratio']:.4f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics

        history_metrics = {
            "liquidity_history_points": 0,
            "liquidity_history_median_side_usdt": best_side_notional,
            "liquidity_history_peak_side_usdt": best_side_notional,
            "liquidity_history_last_side_usdt": best_side_notional,
            "liquidity_history_max_spread_pct": spread_pct,
            "liquidity_history_stable_points": 1 if best_side_notional >= thresholds["min_side_notional_usdt"] else 0,
        }
        metrics.update(history_metrics)

        if bool(getattr(self.cfg, "liquidity_trap_detector_enabled", True)):
            history_rows = []
            try:
                history_rows = self.market_data_cache.get_ticker_history(
                    inst_id,
                    max_points=max(3, int(getattr(self.cfg, "liquidity_history_lookback_points", 8) or 8)),
                    max_age=float(getattr(self.cfg, "liquidity_history_max_age_sec", 40.0) or 40.0),
                )
            except Exception:
                history_rows = []
            if history_rows:
                side_series = [float(row.get("best_side_notional") or 0.0) for row in history_rows]
                spread_series = [float(row.get("spread_pct") or 0.0) for row in history_rows]
                peak_side = max(side_series) if side_series else best_side_notional
                median_side = float(statistics.median(side_series)) if side_series else best_side_notional
                latest_side = side_series[-1] if side_series else best_side_notional
                max_spread_hist = max(spread_series) if spread_series else spread_pct
                stable_points = sum(1 for value in side_series if value >= thresholds["min_side_notional_usdt"])
                metrics.update({
                    "liquidity_history_points": len(history_rows),
                    "liquidity_history_median_side_usdt": median_side,
                    "liquidity_history_peak_side_usdt": peak_side,
                    "liquidity_history_last_side_usdt": latest_side,
                    "liquidity_history_max_spread_pct": max_spread_hist,
                    "liquidity_history_stable_points": stable_points,
                })
                min_points = max(3, int(getattr(self.cfg, "liquidity_history_min_stable_points", 4) or 4))
                collapse_ratio = float(getattr(self.cfg, "liquidity_history_collapse_ratio", 0.35) or 0.35)
                median_ratio = float(getattr(self.cfg, "liquidity_history_median_ratio", 0.60) or 0.60)
                spread_blowout_mult = float(getattr(self.cfg, "liquidity_history_spread_blowout_mult", 1.8) or 1.8)
                trap_detected = (
                    len(history_rows) >= min_points
                    and peak_side >= thresholds["min_side_notional_usdt"]
                    and latest_side <= peak_side * collapse_ratio
                    and median_side <= thresholds["min_side_notional_usdt"] * median_ratio
                    and max_spread_hist >= thresholds["max_spread_pct"] * spread_blowout_mult
                )
                if trap_detected:
                    return False, (
                        f"мираж ликвидности: пик {peak_side:.0f} USDT, медиана {median_side:.0f}, "
                        f"последний стакан {latest_side:.0f}, max spread {max_spread_hist:.3f}% "
                        f"(профиль {thresholds['profile_label']})"
                    ), metrics

        return True, "ok", metrics

    def _register_stopout(self, state: PositionState, exit_price: float, reason: str) -> None:
        lower_reason = str(reason or "").lower()
        if "atr стоп" not in lower_reason:
            return
        cooldown_sec = self._stopout_cooldown_seconds()
        self.recent_stopouts[state.inst_id] = {
            "side": state.side,
            "exit_price": float(exit_price),
            "stop_price": float(state.stop_price),
            "atr": float(max(state.atr, 1e-12)),
            "until": time.time() + cooldown_sec,
            "reason": reason,
        }


    def _skip_profitable_turtle20_reentry(self, inst_id: str) -> tuple[bool, str]:
        """
        Ближе к классической Turtle:
        после прибыльной сделки по инструменту короткую систему Turtle 20 пропускаем.
        Turtle 55 остаётся активной.
        """
        for trade in reversed(self.closed_trades):
            if str(getattr(trade, "inst_id", "")) != str(inst_id):
                continue

            try:
                pnl_value = float(getattr(trade, "pnl", 0.0))
            except Exception:
                pnl_value = 0.0

            try:
                pnl_pct_value = float(getattr(trade, "pnl_pct", 0.0))
            except Exception:
                pnl_pct_value = 0.0

            if pnl_value > 0 or pnl_pct_value > 0:
                return True, f"последняя сделка по {inst_id} была прибыльной, Turtle 20 пропущен"
            return False, ""

        return False, ""



    def _rotation_cooldown_seconds(self) -> int:
        tf_sec = max(60, self._timeframe_seconds())
        return max(tf_sec, min(tf_sec * 3, 3600))

    def _is_rotation_recently_exited(self, inst_id: str) -> bool:
        until_ts = float(self.recent_rotation_exits.get(inst_id, 0.0) or 0.0)
        if until_ts <= 0:
            return False
        if until_ts <= time.time():
            self.recent_rotation_exits.pop(inst_id, None)
            return False
        return True

    def _position_pnl_pct(self, state: PositionState, last_px: Optional[float] = None) -> float:
        try:
            margin = float(getattr(state, "margin", 0.0) or 0.0)
        except Exception:
            margin = 0.0
        if margin > 0:
            try:
                return (float(getattr(state, "unrealized_pnl", 0.0) or 0.0) / margin) * 100.0
            except Exception:
                return 0.0
        try:
            avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        except Exception:
            avg_px = 0.0
        try:
            current_px = float(last_px if last_px is not None else getattr(state, "last_px", avg_px) or avg_px)
        except Exception:
            current_px = avg_px
        if avg_px <= 0:
            return 0.0
        if str(getattr(state, "side", "")).lower() == "long":
            return ((current_px - avg_px) / avg_px) * 100.0
        return ((avg_px - current_px) / avg_px) * 100.0

    def _rotation_candidate_reason(self, candidate: dict) -> str:
        return (
            f"{candidate.get('system_name', 'signal')} {candidate.get('side', '')} "
            f"{candidate.get('inst_id', '')} rank-new-entry"
        ).strip()

    def _pick_rotation_victim(self, incoming_candidate: dict) -> tuple[Optional[PositionState], str]:
        if not bool(getattr(self.cfg, "rotation_enabled", True)):
            return None, "rotation_disabled"
        total_slots = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)
        if total_slots <= 0 or len(self.position_state) < total_slots:
            return None, "slots_available"
        incoming_inst = str(incoming_candidate.get("inst_id") or "")
        threshold = max(1, int(getattr(self.cfg, "rotation_max_units_threshold", 3) or 3))
        require_negative = bool(getattr(self.cfg, "rotation_require_negative_pnl", True))
        pool = []
        for state in self.position_state.values():
            if str(state.inst_id) == incoming_inst:
                continue
            if int(getattr(state, "units", 1) or 1) > threshold:
                continue
            pnl_pct = self._position_pnl_pct(state)
            min_negative_pnl_pct = float(getattr(self.cfg, "rotation_min_negative_pnl_pct", 0.0) or 0.0)
            if require_negative and pnl_pct >= -abs(min_negative_pnl_pct):
                continue
            pool.append((state, pnl_pct))
        if not pool:
            if require_negative:
                return None, "нет убыточной позиции для ротации с допустимым числом юнитов"
            return None, "нет позиции для ротации с допустимым числом юнитов"
        pool.sort(key=lambda item: (int(getattr(item[0], "units", 1) or 1), float(item[1]), float(getattr(item[0], "unrealized_pnl", 0.0) or 0.0), str(item[0].inst_id)))
        victim, pnl_pct = pool[0]
        return victim, f"выбран {victim.inst_id}: units={victim.units}, pnl_pct={pnl_pct:.2f}%"

    def _try_rotate_for_candidate(self, candidate: dict, cycle_id: int, rank: int) -> bool:
        victim, pick_reason = self._pick_rotation_victim(candidate)
        if victim is None:
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "rotation_unavailable",
                rank=rank,
                reason=pick_reason,
                incoming_system=candidate.get("system_name"),
                incoming_side=candidate.get("side"),
            )
            return False
        try:
            ticker = self.gateway.get_ticker_data(victim.inst_id)
            close_price = float(ticker.get("markPx") or ticker.get("last") or victim.last_px or victim.avg_px)
        except Exception:
            close_price = float(victim.last_px or victim.avg_px or 0.0)
        if close_price <= 0:
            self._audit_signal(cycle_id, candidate["inst_id"], "rotation_failed", rank=rank, reason=f"{pick_reason}; цена закрытия недоступна")
            return False
        fresh_pnl_pct = self._position_pnl_pct(victim, last_px=close_price)
        min_negative_pnl_pct = float(getattr(self.cfg, "rotation_min_negative_pnl_pct", 0.0) or 0.0)
        if bool(getattr(self.cfg, "rotation_require_negative_pnl", True)) and fresh_pnl_pct >= -abs(min_negative_pnl_pct):
            reason = f"{pick_reason}; перед закрытием PnL восстановился до {fresh_pnl_pct:.2f}%"
            self.stats_logger.log(
                "rotation_aborted_recovered",
                cycle_id=cycle_id,
                rank=rank,
                victim_inst_id=victim.inst_id,
                incoming_inst_id=candidate["inst_id"],
                victim_pnl_pct=round(float(fresh_pnl_pct), 4),
                reason=reason,
            )
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "rotation_aborted_recovered",
                rank=rank,
                reason=reason,
                victim_inst_id=victim.inst_id,
                victim_pnl_pct=round(float(fresh_pnl_pct), 4),
            )
            return False
        rotation_reason = f"Ротация под новый сигнал {candidate['inst_id']}"
        self.stats_logger.log(
            "rotation_started",
            cycle_id=cycle_id,
            rank=rank,
            victim_inst_id=victim.inst_id,
            victim_side=victim.side,
            victim_units=victim.units,
            victim_unrealized_pnl=float(getattr(victim, "unrealized_pnl", 0.0) or 0.0),
            incoming_inst_id=candidate["inst_id"],
            incoming_side=candidate["side"],
            incoming_system_name=candidate["system_name"],
            pick_reason=pick_reason,
        )
        self._audit_signal(
            cycle_id,
            candidate["inst_id"],
            "rotation_started",
            rank=rank,
            incoming_side=candidate["side"],
            incoming_system=candidate["system_name"],
            victim_inst_id=victim.inst_id,
            victim_units=victim.units,
            pick_reason=pick_reason,
        )
        self.close_position(victim, close_price, rotation_reason)
        if victim.inst_id in self.position_state:
            self.stats_logger.log(
                "rotation_failed",
                cycle_id=cycle_id,
                rank=rank,
                victim_inst_id=victim.inst_id,
                incoming_inst_id=candidate["inst_id"],
                reason="victim_position_still_open_after_close_attempt",
            )
            self._audit_signal(cycle_id, candidate["inst_id"], "rotation_failed", rank=rank, reason="позиция для ротации не закрылась", victim_inst_id=victim.inst_id)
            return False
        self.recent_rotation_exits[victim.inst_id] = time.time() + self._rotation_cooldown_seconds()
        self.log_line.emit(
            f"Ротация: закрыта {victim.inst_id} ({victim.units} юн.) ради нового сигнала {candidate['inst_id']}"
        )
        self.stats_logger.log(
            "rotation_completed",
            cycle_id=cycle_id,
            rank=rank,
            victim_inst_id=victim.inst_id,
            incoming_inst_id=candidate["inst_id"],
            incoming_side=candidate["side"],
            incoming_system_name=candidate["system_name"],
        )
        self._audit_signal(
            cycle_id,
            candidate["inst_id"],
            "rotation_completed",
            rank=rank,
            victim_inst_id=victim.inst_id,
            incoming_side=candidate["side"],
            incoming_system=candidate["system_name"],
        )
        return True

    def _entry_side_limits_ok(self, side: str) -> tuple[bool, str]:
        total_open = len(self.position_state)
        same_side_open = sum(1 for p in self.position_state.values() if str(getattr(p, "side", "")) == str(side))

        max_total = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)
        max_same_side = int(getattr(self.cfg, "max_open_positions_per_side", 0) or 0)

        if max_total > 0 and total_open >= max_total:
            return False, f"достигнут лимит открытых позиций: {total_open}/{max_total}"

        if max_same_side > 0 and same_side_open >= max_same_side:
            return False, f"достигнут лимит позиций по стороне {side}: {same_side_open}/{max_same_side}"

        return True, ""

    def _log_pyramid_diagnostic(self, state: PositionState, event: str, **payload) -> None:
        try:
            base = {
                "trade_id": getattr(state, "trade_id", ""),
                "inst_id": state.inst_id,
                "side": state.side,
                "units": int(getattr(state, "units", 0) or 0),
                "qty": float(getattr(state, "qty", 0.0) or 0.0),
                "avg_px": float(getattr(state, "avg_px", 0.0) or 0.0),
                "stop_price": float(getattr(state, "stop_price", 0.0) or 0.0),
                "next_pyramid_price": float(getattr(state, "next_pyramid_price", 0.0) or 0.0),
                "atr": float(getattr(state, "atr", 0.0) or 0.0),
                "has_locked_break_even": bool(self._has_locked_break_even(state)) if getattr(state, "atr", 0.0) > 0 else False,
            }
            base.update(payload or {})
            self.pyramid_diagnostics_logger.log(event, **base)
        except Exception:
            pass

    def _log_reentry_diagnostic(self, inst_id: str, side: str, **payload) -> None:
        try:
            base = {"inst_id": inst_id, "side": side, "timeframe": self.cfg.timeframe}
            base.update(payload or {})
            self.reentry_diagnostics_logger.log("reentry_check", **base)
        except Exception:
            pass

    def _log_breakout_quality(self, inst_id: str, side: str, price: float, atr: float, system_name: str) -> None:
        try:
            candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(80, self.cfg.long_entry_period + 10)) or []
            if len(candles) < 2 or atr <= 0:
                self.breakout_quality_logger.log("breakout_quality", inst_id=inst_id, side=side, system_name=system_name, entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"), atr=atr, note="not_enough_data")
                return
            last = candles[-1]
            prev = candles[-2]
            entry_period = int(self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period)
            if len(candles) < entry_period + 1:
                self.breakout_quality_logger.log("breakout_quality", inst_id=inst_id, side=side, system_name=system_name, entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"), atr=atr, note="not_enough_channel_data")
                return
            window = candles[-(entry_period + 1):-1]
            highs = [float(c[2]) for c in window]
            lows = [float(c[3]) for c in window]
            upper = max(highs) if highs else 0.0
            lower = min(lows) if lows else 0.0
            level = upper if side == "long" else lower
            last_open = float(last[1]); last_high = float(last[2]); last_low = float(last[3]); last_close = float(last[4])
            candle_range = max(last_high - last_low, 1e-12)
            body = abs(last_close - last_open)
            beyond = ((last_close - level) / max(atr, 1e-12)) if side == "long" else ((level - last_close) / max(atr, 1e-12))
            dist = ((price - level) / max(atr, 1e-12)) if side == "long" else ((level - price) / max(atr, 1e-12))
            self.breakout_quality_logger.log(
                "breakout_quality",
                inst_id=inst_id, side=side, system_name=system_name, timeframe=self.cfg.timeframe,
                entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"),
                entry_price=round(float(price), 8), atr=round(float(atr), 8), breakout_level=round(level, 8),
                donchian_high=round(upper, 8), donchian_low=round(lower, 8),
                breakout_buffer_atr_actual=round(abs(price - level) / max(atr, 1e-12), 6),
                close_beyond_channel_atr=round(beyond, 6), channel_width_atr=round((upper - lower) / max(atr, 1e-12), 6),
                body_atr=round(body / max(atr, 1e-12), 6), body_to_range_ratio=round(body / candle_range, 6),
                distance_from_breakout_level_atr=round(dist, 6), fresh_breakout_true_false=bool(is_fresh_breakout(float(prev[4]), upper, lower, side)),
            )
        except Exception:
            pass

    def _recent_stopout_blocks_entry(self, inst_id: str, side: str, price: float) -> tuple[bool, str]:
        data = self.recent_stopouts.get(inst_id)
        if not data:
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=False, cooldown_blocked=False, recovery_blocked=False, final_decision_allow_true_false=True, final_reason="ok")
            return False, "ok"

        now_ts = time.time()
        until_ts = float(data.get("until", 0.0))
        if until_ts <= now_ts:
            self.recent_stopouts.pop(inst_id, None)
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, cooldown_expired=True, cooldown_blocked=False, recovery_blocked=False, final_decision_allow_true_false=True, final_reason="ok")
            return False, "ok"

        prev_side = str(data.get("side") or "")
        exit_price = float(data.get("exit_price") or 0.0)
        atr = float(max(data.get("atr") or 0.0, 1e-12))
        remain = max(1, int(until_ts - now_ts))
        distance = abs(price - exit_price)
        recovery_actual = distance / max(atr, 1e-12)

        if prev_side == side and distance < atr * self.cfg.reentry_recovery_atr:
            reason = (
                f"cooldown после ATR-стопа ещё активен {remain}s; "
                f"цена отошла только на {distance / atr:.2f} ATR"
            )
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, seconds_since_last_close=0, last_exit_reason=str(data.get("reason") or "stopout"), last_trade_pnl=float(data.get("pnl") or 0.0), cooldown_required_seconds=remain, cooldown_blocked=True, recovery_atr_required=float(self.cfg.reentry_recovery_atr), recovery_atr_actual=round(recovery_actual, 6), recovery_blocked=True, recent_trade_penalty=round(float(self._recent_trade_penalty(inst_id)), 6), final_decision_allow_true_false=False, final_reason=reason)
            return True, reason

        self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, seconds_since_last_close=0, last_exit_reason=str(data.get("reason") or "stopout"), last_trade_pnl=float(data.get("pnl") or 0.0), cooldown_required_seconds=remain, cooldown_blocked=False, recovery_atr_required=float(self.cfg.reentry_recovery_atr), recovery_atr_actual=round(recovery_actual, 6), recovery_blocked=False, recent_trade_penalty=round(float(self._recent_trade_penalty(inst_id)), 6), final_decision_allow_true_false=True, final_reason="ok")
        return False, "ok"

    def _audit_signal(self, cycle_id: int, inst_id: str, stage: str, **payload) -> None:
        if not bool(getattr(self.cfg, "signal_audit_enabled", True)):
            return
        try:
            payload = dict(payload or {})
            if payload.get("reason") and not payload.get("reject_code"):
                payload["reject_code"] = _classify_reason_code(payload.get("reason"))
            self.signal_audit_logger.log("signal_audit", cycle_id=cycle_id, inst_id=inst_id, stage=stage, timeframe=self.cfg.timeframe, **payload)
        except Exception as exc:
            logging.warning("Signal audit failed for %s: %s", inst_id, exc)

    def _ema_values(self, closes: List[float], period: int) -> List[float]:
        vals = [float(v) for v in (closes or [])]
        if not vals:
            return []
        period = max(1, int(period or 1))
        k = 2.0 / (period + 1.0)
        ema = vals[0]
        result = [ema]
        for value in vals[1:]:
            ema = value * k + ema * (1.0 - k)
            result.append(ema)
        return result

    def _trend_filter(self, candles: List[List[float]], side: str, atr: float, price: float) -> tuple[bool, str, dict]:
        closes = [float(c[4]) for c in (candles or []) if len(c) >= 5]
        if len(closes) < 55:
            return False, "недостаточно свечей для фильтра тренда", {}
        ema20 = self._ema_values(closes, 20)
        ema50 = self._ema_values(closes, 50)
        if len(ema50) < 6 or len(ema20) < 3:
            return False, "EMA тренда недоступна", {}
        slope = ema50[-1] - ema50[-5]
        slope_atr = slope / max(atr, 1e-12)
        spacing = (ema20[-1] - ema50[-1]) / max(price, 1e-12) * 100.0
        metrics = {
            "trend_slope_atr": round(slope_atr, 6),
            "trend_spacing_pct": round(spacing, 6),
            "ema20": round(float(ema20[-1]), 8),
            "ema50": round(float(ema50[-1]), 8),
        }
        slope_min = float(self._timeframe_filter_profile().get("trend_slope_atr_min", 0.10) or 0.10)
        metrics["trend_slope_threshold_atr"] = round(slope_min, 6)
        if side == "long":
            if ema20[-1] <= ema50[-1]:
                return False, "trend filter: EMA20 <= EMA50 для long", metrics
            if slope_atr <= slope_min:
                return False, f"trend filter: слабый наклон EMA50 {slope_atr:.2f} ATR < {slope_min:.2f} ATR для long", metrics
        else:
            if ema20[-1] >= ema50[-1]:
                return False, "trend filter: EMA20 >= EMA50 для short", metrics
            if slope_atr >= -slope_min:
                return False, f"trend filter: слабый наклон EMA50 {slope_atr:.2f} ATR > {-slope_min:.2f} ATR для short", metrics
        return True, "ok", metrics

    def _volatility_gate(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str, dict]:
        filter_profile = self._timeframe_filter_profile()
        atr_pct = (atr / max(price, 1e-12)) * 100.0
        window = candles[-min(len(candles), max(20, int(self.cfg.flat_lookback_candles))):]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        channel = (max(highs) - min(lows)) if highs and lows else 0.0
        channel_atr_ratio = channel / max(atr, 1e-12)
        min_atr_pct = float(filter_profile.get("min_atr_pct", getattr(self.cfg, "min_atr_pct", 0.0)) or 0.0)
        min_channel_atr_ratio = float(filter_profile.get("flat_min_channel_atr_ratio", getattr(self.cfg, "flat_min_channel_atr_ratio", 2.0)) or 2.0)
        metrics = {
            "atr_pct": round(atr_pct, 6),
            "channel_atr_ratio": round(channel_atr_ratio, 6),
            "threshold_min_atr_pct": round(min_atr_pct, 6),
            "threshold_min_channel_atr_ratio": round(min_channel_atr_ratio, 6),
            "filter_profile": str(filter_profile.get("label") or self.cfg.timeframe),
        }
        if atr_pct < min_atr_pct:
            return False, f"volatility filter: ATR {atr_pct:.3f}% < {min_atr_pct:.3f}% ({filter_profile.get('label')})", metrics
        if channel_atr_ratio < min_channel_atr_ratio:
            return False, f"volatility filter: channel/ATR {channel_atr_ratio:.2f} < {min_channel_atr_ratio:.2f} ({filter_profile.get('label')})", metrics
        return True, "ok", metrics

    def _recent_trade_penalty(self, inst_id: str) -> float:
        penalty = 0.0
        matched = 0
        for trade in reversed(self.closed_trades[-24:]):
            if str(getattr(trade, "inst_id", "")) != str(inst_id):
                continue
            matched += 1
            try:
                closed_at = datetime.strptime(str(getattr(trade, "time", "")), "%Y-%m-%d %H:%M:%S")
                minutes_ago = max(0.0, (datetime.now() - closed_at).total_seconds() / 60.0)
            except Exception:
                minutes_ago = 99999.0
            if minutes_ago <= 60:
                penalty += 1.6
            elif minutes_ago <= 180:
                penalty += 0.9
            elif minutes_ago <= 720:
                penalty += 0.45
            if matched >= 3:
                break
        return penalty

    def _make_signal_funnel(self) -> dict:
        return {
            "cycle_id": int(self.scan_cycle_seq),
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
            "opened": 0,
        }

    def _classify_rejection_bucket(self, reason: str) -> str:
        text = str(reason or "").lower()
        if "warmup" in text or "недостаточно свечей" in text or "atr недоступ" in text:
            return "warmup_rejected"
        if "flat filter" in text or "узкий диапазон" in text or "канал слишком мал" in text or "слабая структура диапазона" in text:
            return "flat_filter_rejected"
        if "structure filter" in text or "ложных выносов" in text or "плотная база" in text or "прилипла к центру" in text:
            return "structure_rejected"
        if "trend filter" in text or "ema20" in text or "ema50" in text:
            return "trend_rejected"
        if "liquidity" in text or "спред" in text or "стакан" in text or "top-of-book" in text or "объём" in text:
            return "liquidity_rejected"
        if "пробой" in text or "donchian" in text or "breakout" in text or "свеча" in text:
            return "breakout_rejected"
        return "other_rejected"

    def _register_near_pass_candidate(self, inst_id: str, side: str, system_name: str, score: float, reason: str, **payload) -> None:
        item = {
            "inst_id": inst_id,
            "side": side,
            "system_name": system_name,
            "near_pass_score": round(float(score or 0.0), 4),
            "reason": str(reason or ""),
        }
        item.update(payload)
        self.last_near_pass_candidates.append(item)

    def _bump_signal_funnel(self, bucket: str, amount: int = 1) -> None:
        if isinstance(getattr(self, "last_signal_funnel", None), dict) and bucket in self.last_signal_funnel:
            self.last_signal_funnel[bucket] = int(self.last_signal_funnel.get(bucket, 0) or 0) + int(amount or 0)

    def _emit_near_pass_diagnostics(self, cycle_id: int) -> None:
        top_n = max(1, int(getattr(self.cfg, "diagnostic_near_pass_top_n", 10) or 10))
        ranked = sorted(self.last_near_pass_candidates, key=lambda row: (-float(row.get("near_pass_score", 0.0)), str(row.get("inst_id", ""))))[:top_n]
        self.last_near_pass_candidates = ranked
        if not ranked:
            return
        self.log_line.emit("TOP NEAR-PASS CANDIDATES:")
        for idx, row in enumerate(ranked, start=1):
            message = (
                f"{idx:02d}. {row.get('inst_id')} {row.get('side')} {row.get('system_name')} | "
                f"score={float(row.get('near_pass_score', 0.0)):.3f} | {row.get('reason')}"
            )
            self.log_line.emit(message)
            self._audit_signal(cycle_id, str(row.get("inst_id") or "*"), "near_pass_candidate", rank=idx, side=row.get("side"), system_name=row.get("system_name"), near_pass_score=row.get("near_pass_score"), reason=row.get("reason"), breakout_distance_atr=row.get("breakout_distance_atr"), entry_period=row.get("entry_period"))

    def _collect_trade_ready_metrics(self) -> dict:
        self._clear_expired_runtime_blocks()
        universe = [inst_id for inst_id in list(getattr(self.gateway, "swap_ids", []) or []) if not is_hidden_instrument(inst_id)]
        universe_set = set(universe)
        blacklist = set(getattr(self.cfg, "blacklist", []) or []) & universe_set
        blocked = set(getattr(self, "blocked_instruments", {}).keys()) & universe_set
        temp_blocked = set()
        now_ts = time.time()
        for inst_id, until_ts in list(getattr(self, "temp_blocked_until", {}).items()):
            try:
                if float(until_ts or 0.0) > now_ts and inst_id in universe_set:
                    temp_blocked.add(inst_id)
            except Exception:
                continue
        illiquid = set()
        for inst_id, until_ts in list(getattr(self, "illiquid_instruments", {}).items()):
            try:
                if float(until_ts or 0.0) > now_ts and inst_id in universe_set:
                    illiquid.add(inst_id)
            except Exception:
                continue
        stopout = set()
        for inst_id, data in list(getattr(self, "recent_stopouts", {}).items()):
            try:
                if float((data or {}).get("until", 0.0) or 0.0) > now_ts and inst_id in universe_set:
                    stopout.add(inst_id)
            except Exception:
                continue
        execution_watch = set(getattr(self, "execution_risk_events", {}).keys()) & universe_set
        open_positions = set(getattr(self, "position_state", {}).keys()) & universe_set
        hard_blocked = blacklist | blocked | temp_blocked | illiquid | stopout
        available_after_bans = [inst_id for inst_id in universe if inst_id not in hard_blocked]
        eligible = list(available_after_bans)
        if not bool(getattr(self.cfg, "trade_ready_include_open_positions", False)):
            eligible = [inst_id for inst_id in eligible if inst_id not in open_positions]
        metrics = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scan_universe_total": len(universe),
            "blacklist_count": len(blacklist),
            "blocked_count": len(blocked),
            "temp_blocked_count": len(temp_blocked),
            "illiquid_count": len(illiquid),
            "stopout_cooldown_count": len(stopout),
            "hard_blocked_unique_count": len(hard_blocked),
            "execution_watchlist_count": len(execution_watch),
            "open_positions_count": len(open_positions),
            "available_after_bans_count": len(available_after_bans),
            "trade_ready_count": len(eligible),
        }
        return metrics

    def _maybe_log_trade_ready_metrics(self, force: bool = False) -> None:
        metrics = self._collect_trade_ready_metrics()
        self.last_trade_ready_metrics = dict(metrics)
        interval = max(60, int(getattr(self.cfg, "trade_ready_log_interval_sec", 900) or 900))
        now_ts = time.time()
        if force or (now_ts - float(getattr(self, "last_trade_ready_log_at", 0.0) or 0.0) >= interval):
            self.last_trade_ready_log_at = now_ts
            self.stats_logger.log("filter_diagnostics", **metrics, signal_funnel=dict(getattr(self, "last_signal_funnel", {}) or {}))

    def scan_markets(self) -> None:
        self._clear_expired_runtime_blocks()
        self.scan_cycle_seq += 1
        cycle_id = int(self.scan_cycle_seq)
        candidates = []
        rejected = 0
        skipped_prefilter = 0
        self.last_scan_cycle_id = cycle_id
        self.last_scan_candidates = []
        self.last_near_pass_candidates = []
        funnel = self._make_signal_funnel()
        self.last_signal_funnel = funnel

        self._audit_signal(cycle_id, "*", "cycle_started", open_positions=len(self.position_state), total_limit=int(getattr(self.cfg, "max_open_positions_total", 0) or 0))
        self._maybe_log_trade_ready_metrics(force=False)

        for inst_id in self.gateway.swap_ids:
            if not self.running:
                break
            blocked_now, blocked_reason = self._is_temporarily_blocked(inst_id)
            if inst_id in self.cfg.blacklist or inst_id in self.blocked_instruments or is_hidden_instrument(inst_id):
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason="blacklist_or_blocked")
                continue
            if blocked_now:
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason=blocked_reason)
                continue
            if inst_id in self.position_state:
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason="already_open")
                continue
            try:
                funnel["instruments_scanned"] += 1
                inst_candidates = self.evaluate_entry(inst_id, cycle_id=cycle_id)
                if inst_candidates:
                    candidates.extend(inst_candidates)
                else:
                    rejected += 1
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка анализа входа: {exc}")
                logging.warning("Entry eval failed for %s: %s", inst_id, exc)
                self._audit_signal(cycle_id, inst_id, "analysis_error", error=str(exc))

        if not candidates:
            self.last_signal_funnel = dict(funnel)
            self._emit_near_pass_diagnostics(cycle_id)
            self.stats_logger.log("signal_funnel", **self.last_signal_funnel)
            self._maybe_log_trade_ready_metrics(force=False)
            self.stats_logger.log("entry_candidates_ranked", cycle_id=cycle_id, total=0, opened=0, timeframe=self.cfg.timeframe, rejected=rejected, skipped_prefilter=skipped_prefilter)
            self._audit_signal(cycle_id, "*", "cycle_finished", candidates=0, opened=0, rejected=rejected, skipped_prefilter=skipped_prefilter, signal_funnel=self.last_signal_funnel)
            return

        def sort_key(item: dict):
            system_rank = 0 if int(item.get("entry_period", 0)) >= int(self.cfg.long_entry_period) else 1
            return (
                system_rank,
                -float(item.get("quality_score", 0.0)),
                -float(item.get("freshness_score", 0.0)),
                float(item.get("breakout_distance_atr", 0.0)),
                -float(item.get("liquidity_score", 0.0)),
                float(item.get("recent_trade_penalty", 0.0)),
                str(item.get("inst_id", "")),
            )

        candidates.sort(key=sort_key)
        self.last_scan_candidates = [dict(item) for item in candidates[:12]]
        funnel["candidates"] = len(candidates)
        top_n = max(1, int(getattr(self.cfg, "signal_audit_top_n", 12) or 12))
        funnel["ranked_candidates"] = min(len(candidates), top_n)
        for rank, candidate in enumerate(candidates[:top_n], start=1):
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "ranked_candidate",
                rank=rank,
                side=candidate.get("side"),
                system_name=candidate.get("system_name"),
                entry_period=candidate.get("entry_period"),
                breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4),
                liquidity_score=round(float(candidate.get("liquidity_score", 0.0)), 4),
                freshness_score=round(float(candidate.get("freshness_score", 0.0)), 4),
                recent_trade_penalty=round(float(candidate.get("recent_trade_penalty", 0.0)), 4),
                reason=candidate.get("reason"),
                quality_score=round(float(candidate.get("quality_score", 0.0)), 4),
            )

        opened = 0
        total_slots = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)

        for rank, candidate in enumerate(candidates, start=1):
            if not self.running:
                break
            if candidate["inst_id"] in self.position_state:
                self._audit_signal(cycle_id, candidate["inst_id"], "rank_skipped", rank=rank, reason="already_open_after_previous_fill")
                continue
            if total_slots > 0 and len(self.position_state) >= total_slots:
                rotation_ok = self._try_rotate_for_candidate(candidate, cycle_id=cycle_id, rank=rank)
                if not rotation_ok:
                    reason = f"достигнут общий лимит открытых позиций: {len(self.position_state)}/{total_slots}"
                    self.log_line.emit(f"{candidate['inst_id']}: вход пропущен — {reason}")
                    self.stats_logger.log("entry_rejected", cycle_id=cycle_id, inst_id=candidate["inst_id"], side=candidate["side"], price=candidate["price"], atr=candidate["atr"], system_name=candidate["system_name"], timeframe=self.cfg.timeframe, entry_period=candidate["entry_period"], exit_period=candidate["exit_period"], reason=reason)
                    self._audit_signal(cycle_id, candidate["inst_id"], "entry_skipped", rank=rank, reason=reason, side=candidate["side"], system_name=candidate["system_name"])
                    continue

            signal_payload = {
                "inst_id": candidate["inst_id"],
                "side": candidate["side"],
                "price": candidate["price"],
                "atr": candidate["atr"],
                "system_name": candidate["system_name"],
                "timeframe": self.cfg.timeframe,
                "entry_period": candidate["entry_period"],
                "exit_period": candidate["exit_period"],
                "reason": candidate["reason"],
                "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
            }
            self.stats_logger.log(
                "entry_signal",
                cycle_id=cycle_id,
                rank=rank,
                inst_id=candidate["inst_id"],
                side=candidate["side"],
                price=candidate["price"],
                atr=candidate["atr"],
                system_name=candidate["system_name"],
                timeframe=self.cfg.timeframe,
                entry_period=candidate["entry_period"],
                exit_period=candidate["exit_period"],
                reason=candidate["reason"],
                trade_mode=getattr(self.cfg, "trade_mode", "auto"),
                breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4),
                liquidity_score=round(float(candidate.get("liquidity_score", 0.0)), 4),
                freshness_score=round(float(candidate.get("freshness_score", 0.0)), 4),
                recent_trade_penalty=round(float(candidate.get("recent_trade_penalty", 0.0)), 4),
            )

            if getattr(self.cfg, "trade_mode", "auto") == "manual":
                if not self.request_manual_entry_approval(signal_payload):
                    self.stats_logger.log(
                        "entry_skipped_manual",
                        cycle_id=cycle_id,
                        rank=rank,
                        inst_id=candidate["inst_id"],
                        side=candidate["side"],
                        price=candidate["price"],
                        atr=candidate["atr"],
                        system_name=candidate["system_name"],
                        timeframe=self.cfg.timeframe,
                        reason=candidate["reason"],
                    )
                    self._audit_signal(cycle_id, candidate["inst_id"], "entry_skipped_manual", rank=rank, side=candidate["side"], system_name=candidate["system_name"])
                    continue

            opened_now = self.enter_position(candidate["inst_id"], candidate["side"], candidate["price"], candidate["atr"], candidate["system_name"])
            if not opened_now:
                funnel["entry_failed"] += 1
                self._audit_signal(cycle_id, candidate["inst_id"], "entry_failed", rank=rank, side=candidate["side"], system_name=candidate["system_name"])
                continue
            opened += 1
            funnel["orders_sent"] += 1
            funnel["opened"] += 1
            self._audit_signal(cycle_id, candidate["inst_id"], "entry_sent", rank=rank, side=candidate["side"], system_name=candidate["system_name"], breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4))

        self.last_signal_funnel = dict(funnel)
        self._emit_near_pass_diagnostics(cycle_id)
        self.stats_logger.log("signal_funnel", **self.last_signal_funnel)
        self._maybe_log_trade_ready_metrics(force=False)
        self.stats_logger.log("entry_candidates_ranked", cycle_id=cycle_id, total=len(candidates), opened=opened, timeframe=self.cfg.timeframe, rejected=rejected, skipped_prefilter=skipped_prefilter)
        self._audit_signal(cycle_id, "*", "cycle_finished", candidates=len(candidates), opened=opened, rejected=rejected, skipped_prefilter=skipped_prefilter, signal_funnel=self.last_signal_funnel)


    def evaluate_entry(self, inst_id: str, cycle_id: Optional[int] = None) -> list[dict]:
        profile = self._tf_entry_profile()
        max_entry_period = max(self.cfg.long_entry_period, self.cfg.short_entry_period)
        max_exit_period = max(self.cfg.long_exit_period, self.cfg.short_exit_period)

        warmup_extra = max(6, int(getattr(self.cfg, "atr_warmup_extra_candles", 10) or 10))
        min_history = max(max_entry_period, self.cfg.atr_period + warmup_extra, max_exit_period, self.cfg.flat_lookback_candles + 4, 55)
        lookback = int(max(max_entry_period, self.cfg.atr_period, max_exit_period, self.cfg.flat_lookback_candles, 55) * profile["lookback_bonus"]) + warmup_extra
        lookback = max(lookback, min_history)

        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback)
        if len(candles) < min_history:
            reason = f"ATR warmup: недостаточно свечей {len(candles)}/{min_history}"
            if cycle_id is not None:
                self._bump_signal_funnel("warmup_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason=reason)
            return []

        last = candles[-1]
        prev_candle = candles[-2] if len(candles) >= 2 else last
        price = float(last[4])
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            reason = "ATR warmup: цена или ATR недоступны после прогрева"
            if cycle_id is not None:
                self._bump_signal_funnel("warmup_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason=reason)
            return []

        if self._is_rotation_recently_exited(inst_id):
            if cycle_id is not None:
                self._audit_signal(cycle_id, inst_id, "rejected", reason="инструмент недавно закрыт ротацией, повторный вход временно заблокирован")
            return []

        minimal_turtle_mode = self._minimal_turtle_entry_mode()
        structure_penalty = 0.0
        structure_penalty_reason = ""
        structure_metrics = {"false_breakouts": 0, "dense_base": False, "center_glue": False, "penalty": 0.0}
        vol_metrics = {
            "atr_pct": round((atr / max(price, 1e-12)) * 100.0, 6),
            "channel_atr_ratio": 0.0,
            "threshold_min_atr_pct": 0.0,
            "threshold_min_channel_atr_ratio": 0.0,
        }
        liquidity_metrics = {"profile_label": self._liquidity_thresholds().get("profile_label", str(self.cfg.timeframe)), "liquidity_filter_enabled": not minimal_turtle_mode}
        if not minimal_turtle_mode:
            flat_market, flat_reason = self.is_flat_market(candles, price, atr)
            if flat_market:
                channel_window = candles[-min(len(candles), max(20, int(self.cfg.flat_lookback_candles))):]
                highs = [float(c[2]) for c in channel_window]
                lows = [float(c[3]) for c in channel_window]
                channel_atr_ratio = ((max(highs) - min(lows)) / max(atr, 1e-12)) if highs and lows else 0.0
                near_score = max(0.0, min(1.0, channel_atr_ratio / max(float(self.cfg.flat_min_channel_atr_ratio), 1e-12)))
                self._register_near_pass_candidate(inst_id, "both", "flat_filter", near_score, flat_reason, breakout_distance_atr=round(channel_atr_ratio, 4), entry_period=max_entry_period)
                if cycle_id is not None:
                    self._bump_signal_funnel("flat_filter_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"flat filter: {flat_reason}", price=price, atr=atr)
                return []

            structure_risk, structure_reason, structure_metrics = self._detect_structure_risk(candles, atr)
            structure_penalty = float((structure_metrics or {}).get("penalty", 0.0) or 0.0)
            structure_penalty_reason = str((structure_metrics or {}).get("penalty_reason", "") or "")
            if structure_risk:
                self._register_near_pass_candidate(inst_id, "both", "structure_filter", 0.55, structure_reason, entry_period=max_entry_period)
                if cycle_id is not None:
                    self._bump_signal_funnel("structure_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"structure filter: {structure_reason}", price=price, atr=atr, **structure_metrics)
                return []

            vol_ok, vol_reason, vol_metrics = self._volatility_gate(candles, price, atr)
            if not vol_ok:
                if cycle_id is not None:
                    self._bump_signal_funnel(self._classify_rejection_bucket(vol_reason))
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=vol_reason, price=price, atr=atr, **vol_metrics)
                return []

            liquid_ok, liquid_reason, liquidity_metrics = self._check_liquidity(inst_id, price)
            if not liquid_ok:
                if cycle_id is not None and bool(getattr(self.cfg, "signal_audit_log_all_rejections", True)):
                    self._bump_signal_funnel("liquidity_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"liquidity: {liquid_reason}", price=price, atr=atr, **{k: round(v, 6) if isinstance(v, float) else v for k, v in liquidity_metrics.items()})
                if inst_id in set(getattr(self.cfg, "execution_risk_watchlist", []) or []) or "top-of-book" in liquid_reason or "тонкий стакан" in liquid_reason or "пустой" in liquid_reason:
                    self._register_execution_risk(inst_id, liquid_reason, stage="entry_liquidity", severity=0.75, quarantine=False)
                logging.info("%s: пропуск входа, illiquidity-filter без бана (%s)", inst_id, liquid_reason)
                return []
        else:
            logging.debug("%s: minimal turtle mode active — non-Turtle entry filters are bypassed", inst_id)

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        last_high = float(last[2])
        last_low = float(last[3])
        prev_high = float(prev_candle[2])
        prev_low = float(prev_candle[3])

        systems = [
            {
                "name": "Turtle 20",
                "entry_period": int(self.cfg.short_entry_period),
                "exit_period": int(self.cfg.short_exit_period),
            },
            {
                "name": "Turtle 55",
                "entry_period": int(self.cfg.long_entry_period),
                "exit_period": int(self.cfg.long_exit_period),
            },
        ]

        signals = []
        for system in systems:
            entry_period = int(system["entry_period"])
            if entry_period <= 0:
                continue
            prev_window = candles[-entry_period - 1:-1]
            if len(prev_window) < entry_period:
                continue
            long_level = max(float(c[2]) for c in prev_window)
            short_level = min(float(c[3]) for c in prev_window)
            if last_high >= long_level and prev_high < long_level:
                signals.append({
                    "side": "long",
                    "level": long_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                    "freshness_score": max(0.0, (last_high - max(prev_high, long_level - atr * 0.01)) / max(atr, 1e-12)),
                })
            if last_low <= short_level and prev_low > short_level:
                signals.append({
                    "side": "short",
                    "level": short_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                    "freshness_score": max(0.0, (min(prev_low, short_level + atr * 0.01) - last_low) / max(atr, 1e-12)),
                })

        if not signals:
            if cycle_id is not None:
                self._bump_signal_funnel("breakout_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason="нет свежего пробоя Donchian на последней закрытой свече", price=price, atr=atr, last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8))
            return []

        signals.sort(key=lambda s: (-s["entry_period"], 0 if s["side"] == "long" else 1))

        candidates = []
        ticker = None
        active_liquidity = self._liquidity_thresholds()
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception:
            ticker = None
        bid_px = float((ticker or {}).get("bidPx") or 0.0)
        ask_px = float((ticker or {}).get("askPx") or 0.0)
        vol_24h = float((ticker or {}).get("volCcy24h") or (ticker or {}).get("vol24h") or 0.0)
        spread_pct = 0.0
        if bid_px > 0 and ask_px > 0:
            mid = (bid_px + ask_px) / 2.0
            if mid > 0:
                spread_pct = ((ask_px - bid_px) / mid) * 100.0
        liquidity_score = max(0.0, vol_24h / max(float(active_liquidity.get("min_24h_quote_volume") or 1.0), 1.0))
        if spread_pct > 0:
            liquidity_score += max(0.0, float(active_liquidity.get("max_spread_pct") or self.cfg.liquidity_max_spread_pct) / spread_pct)

        recent_trade_penalty = self._recent_trade_penalty(inst_id)
        self._log_reentry_diagnostic(inst_id, "scan", price=price, recent_trade_penalty=round(float(recent_trade_penalty), 6), recent_stopout_present=bool(self.recent_stopouts.get(inst_id)), final_decision_allow_true_false=True, final_reason="scan")

        for signal in signals:
            side = signal["side"]
            level = float(signal["level"])
            system_name = str(signal["system_name"])

            if side == "long" and cooldown_blocked_long:
                if cycle_id is not None:
                    self._bump_signal_funnel("other_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=cooldown_reason_long)
                logging.info("%s: %s long-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_long)
                continue
            if side == "short" and cooldown_blocked_short:
                if cycle_id is not None:
                    self._bump_signal_funnel("other_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=cooldown_reason_short)
                logging.info("%s: %s short-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_short)
                continue

            if minimal_turtle_mode:
                trend_ok, trend_reason, trend_metrics = True, "minimal_turtle_mode", {
                    "trend_slope_atr": 0.0,
                    "trend_spacing_pct": 0.0,
                    "ema20": 0.0,
                    "ema50": 0.0,
                    "trend_slope_threshold_atr": 0.0,
                }
            else:
                trend_ok, trend_reason, trend_metrics = self._trend_filter(candles, side, atr, price)
            if not trend_ok:
                slope_abs = abs(float(trend_metrics.get("trend_slope_atr", 0.0) or 0.0))
                near_score = max(0.0, min(1.0, slope_abs / 0.10))
                self._register_near_pass_candidate(inst_id, side, system_name, near_score, trend_reason, entry_period=signal["entry_period"])
                if cycle_id is not None:
                    self._bump_signal_funnel("trend_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=trend_reason, **trend_metrics)
                continue

            if int(signal["entry_period"]) == int(self.cfg.short_entry_period):
                skip_t20, skip_reason = self._skip_profitable_turtle20_reentry(inst_id)
                if skip_t20:
                    if cycle_id is not None:
                        self._bump_signal_funnel("other_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=skip_reason)
                    logging.info("%s: %s", inst_id, skip_reason)
                    continue

            ok, reason = self._confirm_breakout(candles, atr, side, level)
            if ok:
                breakout_distance = max(0.0, (price - level) / max(atr, 1e-12)) if side == "long" else max(0.0, (level - price) / max(atr, 1e-12))
                max_breakout_distance = float(getattr(self.cfg, "breakout_max_distance_atr", 0.50) or 0.50)
                if (not minimal_turtle_mode) and breakout_distance > max_breakout_distance:
                    late_reason = f"late breakout distance {breakout_distance:.2f} ATR > {max_breakout_distance:.2f} ATR"
                    self._register_near_pass_candidate(inst_id, side, system_name, 0.30, late_reason, breakout_distance_atr=round(breakout_distance, 4), entry_period=signal["entry_period"])
                    if cycle_id is not None:
                        self._bump_signal_funnel("breakout_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=late_reason, breakout_distance_atr=round(breakout_distance, 4))
                    logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, late_reason)
                    continue
                buffer_mult = 0.0 if minimal_turtle_mode else float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0)
                tf_sec_local = self._timeframe_seconds()
                if not minimal_turtle_mode:
                    if tf_sec_local <= 60:
                        buffer_mult *= 0.60
                    elif tf_sec_local <= 300:
                        buffer_mult *= 0.82
                entry_trigger_price = level + atr * buffer_mult if side == "long" else level - atr * buffer_mult
                quality_score = 0.0
                filter_profile = self._timeframe_filter_profile()
                preferred_min = float(filter_profile.get("preferred_breakout_distance_atr_min", getattr(self.cfg, "preferred_breakout_distance_atr_min", 0.05)) or 0.05)
                preferred_max = float(filter_profile.get("preferred_breakout_distance_atr_max", getattr(self.cfg, "preferred_breakout_distance_atr_max", 0.30)) or 0.30)
                if preferred_min <= breakout_distance <= preferred_max:
                    quality_score += 3.0
                elif breakout_distance < preferred_min:
                    quality_score += 1.2
                elif breakout_distance <= max_breakout_distance:
                    quality_score += 1.0
                atr_pct = float(vol_metrics.get("atr_pct", 0.0))
                if float(filter_profile.get("quality_atr_good_min", 0.18)) <= atr_pct <= float(filter_profile.get("quality_atr_good_max", 0.45)):
                    quality_score += 2.0
                elif float(filter_profile.get("quality_atr_good_max", 0.45)) < atr_pct <= float(filter_profile.get("quality_atr_ok_max", 0.80)):
                    quality_score += 1.0
                channel_ratio = float(vol_metrics.get("channel_atr_ratio", 0.0))
                if float(filter_profile.get("quality_channel_good_min", 1.6)) <= channel_ratio <= float(filter_profile.get("quality_channel_good_max", 4.5)):
                    quality_score += 2.0
                elif float(filter_profile.get("quality_channel_good_max", 4.5)) < channel_ratio <= float(filter_profile.get("quality_channel_ok_max", 7.5)):
                    quality_score += 0.8
                slope_atr = abs(float(trend_metrics.get("trend_slope_atr", 0.0) or 0.0))
                if slope_atr >= float(filter_profile.get("quality_slope_bonus_from", 0.18)):
                    quality_score += 1.0
                quality_score += min(2.0, float(signal.get("freshness_score", 0.0)))
                quality_score += min(1.0, liquidity_score / 8.0)
                quality_score -= recent_trade_penalty
                quality_score -= structure_penalty
                candidate = {
                    "inst_id": inst_id,
                    "side": side,
                    "price": price,
                    "entry_trigger_price": entry_trigger_price,
                    "atr": atr,
                    "system_name": system_name,
                    "entry_period": signal["entry_period"],
                    "exit_period": signal["exit_period"],
                    "reason": reason if not structure_penalty_reason else f"{reason}; structure penalty: {structure_penalty_reason}",
                    "breakout_distance_atr": breakout_distance,
                    "liquidity_score": liquidity_score,
                    "freshness_score": float(signal.get("freshness_score", 0.0)),
                    "recent_trade_penalty": recent_trade_penalty,
                    "liquidity_profile": str(active_liquidity.get("profile_label") or self.cfg.timeframe),
                    "trend_slope_atr": float(trend_metrics.get("trend_slope_atr", 0.0)),
                    "atr_pct": atr_pct,
                    "quality_score": round(quality_score, 6),
                    "structure_penalty": round(structure_penalty, 6),
                    "false_breakouts": int((structure_metrics or {}).get("false_breakouts", 0) or 0),
                    "dense_base": bool((structure_metrics or {}).get("dense_base", False)),
                    "center_glue": bool((structure_metrics or {}).get("center_glue", False)),
                }
                candidates.append(candidate)
                if cycle_id is not None:
                    self._bump_signal_funnel("candidates")
                self._audit_signal(cycle_id, inst_id, "candidate", side=side, system_name=system_name, entry_period=signal["entry_period"], breakout_distance_atr=round(breakout_distance, 4), liquidity_score=round(liquidity_score, 4), freshness_score=round(float(signal.get("freshness_score", 0.0)), 4), recent_trade_penalty=round(recent_trade_penalty, 4), liquidity_profile=str(active_liquidity.get("profile_label") or self.cfg.timeframe), reason=candidate.get("reason"), breakout_buffer_atr=float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0), entry_trigger_price=round(entry_trigger_price, 8), donchian_high=round(long_level, 8), donchian_low=round(short_level, 8), breakout_level=round(level, 8), last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8), distance_to_high=round((long_level - price) / max(atr, 1e-12), 6), distance_to_low=round((price - short_level) / max(atr, 1e-12), 6), quality_score=round(float(candidate.get("quality_score", 0.0)), 4), structure_penalty=round(float(candidate.get("structure_penalty", 0.0)), 4), false_breakouts=int(candidate.get("false_breakouts", 0) or 0), dense_base=bool(candidate.get("dense_base", False)), center_glue=bool(candidate.get("center_glue", False)), **trend_metrics, **vol_metrics)
                continue

            breakout_distance = max(0.0, (price - level) / max(atr, 1e-12)) if side == "long" else max(0.0, (level - price) / max(atr, 1e-12))
            near_score = max(0.0, 1.0 - min(1.0, abs(float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0) - breakout_distance)))
            self._register_near_pass_candidate(inst_id, side, system_name, near_score, reason, breakout_distance_atr=round(breakout_distance, 4), entry_period=signal["entry_period"])
            self.stats_logger.log(
                "entry_rejected",
                cycle_id=cycle_id,
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                entry_period=signal["entry_period"],
                exit_period=signal["exit_period"],
                reason=reason,
            )
            if cycle_id is not None:
                self._bump_signal_funnel("breakout_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=reason, donchian_high=round(long_level, 8), donchian_low=round(short_level, 8), breakout_level=round(level, 8), last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8), distance_to_high=round((long_level - price) / max(atr, 1e-12), 6), distance_to_low=round((price - short_level) / max(atr, 1e-12), 6))
            logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, reason)

        return candidates

    def _set_manual_entry_decision(self, allowed: bool) -> None:
        self._manual_entry_allowed = bool(allowed)
        self._manual_entry_event.set()

    def request_manual_entry_approval(self, payload: dict) -> bool:
        self._manual_entry_allowed = False
        self._manual_entry_event.clear()
        try:
            self.entry_candidate.emit(payload)
        except Exception as exc:
            logging.warning("Failed to emit manual entry candidate: %s", exc)
            return False

        wait_sec = 120
        self.log_line.emit(
            f"{payload.get('inst_id')}: найден сигнал {payload.get('system_name')} {payload.get('side')} — ожидание решения в ручном режиме"
        )
        approved = self._manual_entry_event.wait(wait_sec)
        if not approved:
            self.log_line.emit(f"{payload.get('inst_id')}: сигнал пропущен — не получено решение за {wait_sec}с")
            return False
        if not self._manual_entry_allowed:
            self.log_line.emit(f"{payload.get('inst_id')}: сигнал пропущен пользователем")
            return False
        self.log_line.emit(f"{payload.get('inst_id')}: сигнал подтверждён пользователем")
        return True

    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        profile = self._tf_entry_profile()
        filter_profile = self._timeframe_filter_profile()
        strict_min = profile["strict_min"]
        strict_max = profile["strict_max"]

        lookback = min(len(candles), max(10, int(self.cfg.flat_lookback_candles * profile["lookback_bonus"])))
        window = candles[-lookback:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        opens = [float(c[1]) for c in window]
        closes = [float(c[4]) for c in window]
        volumes = [float(c[5]) if len(c) > 5 else 0.0 for c in window]

        channel = max(highs) - min(lows)
        channel_range_pct = (channel / price) * 100.0 if price > 0 else 0.0
        atr_pct = (atr / price) * 100.0 if price > 0 else 0.0
        channel_atr_ratio = channel / max(atr, 1e-12)

        candle_ranges = [max(float(c[2]) - float(c[3]), 1e-12) for c in window]
        body_ratios = [abs(float(c[4]) - float(c[1])) / rng for c, rng in zip(window, candle_ranges)]
        wick_ratios = [1.0 - br for br in body_ratios]
        avg_wick_ratio = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0.0

        net_move = abs(closes[-1] - closes[0]) if len(closes) > 1 else 0.0
        travel = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / travel) if travel > 0 else 0.0

        directions = []
        for opn, cls in zip(opens, closes):
            delta = cls - opn
            if abs(delta) <= max(price * 0.00003, atr * 0.02, 1e-12):
                directions.append(0)
            else:
                directions.append(1 if delta > 0 else -1)

        flips = 0
        non_zero_dirs = [d for d in directions if d != 0]
        for i in range(1, len(non_zero_dirs)):
            if non_zero_dirs[i] != non_zero_dirs[i - 1]:
                flips += 1
        flip_ratio = flips / max(1, len(non_zero_dirs) - 1)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.72

        # Блокируем только действительно мёртвый рынок.
        min_channel_range_pct = float(filter_profile.get("min_channel_range_pct", self.cfg.min_channel_range_pct) or self.cfg.min_channel_range_pct)
        min_atr_pct = float(filter_profile.get("min_atr_pct", self.cfg.min_atr_pct) or self.cfg.min_atr_pct)
        min_channel_atr_ratio = float(filter_profile.get("flat_min_channel_atr_ratio", self.cfg.flat_min_channel_atr_ratio) or self.cfg.flat_min_channel_atr_ratio)
        max_flip_ratio = float(filter_profile.get("max_direction_flip_ratio", self.cfg.max_direction_flip_ratio) or self.cfg.max_direction_flip_ratio)
        max_wick_ratio = float(filter_profile.get("flat_max_wick_to_range_ratio", self.cfg.flat_max_wick_to_range_ratio) or self.cfg.flat_max_wick_to_range_ratio)
        min_efficiency_ratio = float(filter_profile.get("min_efficiency_ratio", self.cfg.min_efficiency_ratio) or self.cfg.min_efficiency_ratio)

        if channel_range_pct < min_channel_range_pct * 0.60 * strict_min:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}% < {min_channel_range_pct * 0.60 * strict_min:.3f}%"
        if atr_pct < min_atr_pct * 0.68 * strict_min:
            return True, f"крайне низкий ATR {atr_pct:.3f}% < {min_atr_pct * 0.68 * strict_min:.3f}%"
        if channel_atr_ratio < min_channel_atr_ratio * 0.76 * strict_min:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f} < {min_channel_atr_ratio * 0.76 * strict_min:.2f}"

        hard_flags = []
        soft_flags = []

        # Оставляем только реально токсичные признаки шума.
        if flip_ratio > max_flip_ratio * strict_max:
            hard_flags.append(f"пила {flip_ratio:.0%}")

        if avg_wick_ratio > max_wick_ratio * strict_max:
            soft_flags.append(f"много теней {avg_wick_ratio:.2f}")
        if efficiency_ratio < min_efficiency_ratio * strict_min:
            soft_flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if volume_dry:
            soft_flags.append("затухающий объём")

        if len(hard_flags) >= 1 and len(soft_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if len(hard_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if channel_atr_ratio < min_channel_atr_ratio * 0.88 * strict_min and efficiency_ratio < min_efficiency_ratio * 0.85 * strict_min:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"

    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str, dict]:
        if len(candles) < 12:
            return False, "ok", {"false_breakouts": 0, "dense_base": False, "center_glue": False, "penalty": 0.0}

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)
        false_breaks = 0
        if swing_span <= atr * (1.8 * strict_min):
            for i in range(2, len(window)):
                prev_high = max(float(c[2]) for c in window[:i])
                prev_low = min(float(c[3]) for c in window[:i])
                h = float(window[i][2])
                l = float(window[i][3])
                c = float(window[i][4])
                if h > prev_high and c <= prev_high:
                    false_breaks += 1
                if l < prev_low and c >= prev_low:
                    false_breaks += 1

        base_touches_high = 0
        base_touches_low = 0
        top = max(highs)
        bottom = min(lows)
        threshold = atr * (0.30 * strict_min)

        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1

        dense_base = base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * (2.4 * strict_min)
        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * (0.34 * strict_min))
        center_glue = close_cluster >= max(8, int(len(closes) * 0.74))

        penalty = 0.0
        penalty_reasons = []
        hard_reject_from = max(4, int(getattr(self.cfg, "structure_false_breakouts_hard_reject_from", 6) or 6))
        penalty_from = max(1, int(getattr(self.cfg, "structure_false_breakouts_penalty_from", 3) or 3))
        if false_breaks >= hard_reject_from:
            return True, f"серия ложных выносов ({false_breaks})", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": 3.0}
        if false_breaks >= penalty_from:
            penalty += min(3.0, (false_breaks - penalty_from + 1) * 0.75)
            penalty_reasons.append(f"ложные выносы {false_breaks}")
        if dense_base:
            if bool(getattr(self.cfg, "structure_dense_base_as_penalty", True)):
                penalty += 2.0
                penalty_reasons.append("плотная база")
            else:
                return True, "слишком плотная база", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": penalty}
        if center_glue:
            if bool(getattr(self.cfg, "structure_center_glue_as_penalty", True)):
                penalty += 1.5
                penalty_reasons.append("центр диапазона")
            else:
                return True, "цена прилипла к центру диапазона", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": penalty}

        metrics = {
            "false_breakouts": false_breaks,
            "dense_base": dense_base,
            "center_glue": center_glue,
            "penalty": round(penalty, 4),
            "penalty_reason": "; ".join(penalty_reasons) if penalty_reasons else "",
        }
        return False, "ok", metrics

    def _confirm_breakout(self, candles: list, atr: float, side: str, level: float) -> tuple[bool, str]:
        """
        v057:
        Свежий Turtle-пробой с буфером, нормальным телом свечи и закрытием ближе к экстремуму.
        Это режет ложные breakout-входы на 5m, но сохраняет классическую логику Donchian.
        """
        if not candles or len(candles) < 2:
            return False, "нет свечей"
        if atr <= 0:
            return False, "ATR недоступен"
        if side not in {"long", "short"}:
            return False, "неизвестная сторона"

        last = candles[-1]
        prev = candles[-2]
        last_open = float(last[1])
        last_high = float(last[2])
        last_low = float(last[3])
        last_close = float(last[4])
        prev_high = float(prev[2])
        prev_low = float(prev[3])
        body = abs(last_close - last_open)
        candle_range = max(last_high - last_low, 1e-12)

        if self._minimal_turtle_entry_mode():
            entry_period = int(self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period)
            if len(candles) < entry_period + 1:
                return False, "недостаточно свечей для Donchian-канала"

            window = candles[-(entry_period + 1):-1]
            highs = [float(c[2]) for c in window]
            lows = [float(c[3]) for c in window]
            if not highs or not lows:
                return False, "канал Donchian недоступен"

            upper = max(highs)
            lower = min(lows)
            channel_width_atr = (upper - lower) / max(atr, 1e-12)
            min_channel_width_atr = 0.50
            if channel_width_atr < min_channel_width_atr:
                return False, f"канал слишком узкий: {channel_width_atr:.2f} ATR < {min_channel_width_atr:.2f} ATR"

            prev_close = float(prev[4])
            close_buffer = 0.10 * atr

            if side == "long":
                if not is_fresh_breakout(prev_close, level, lower, "long"):
                    return False, "пробой не свежий: предыдущая свеча уже закрылась выше канала"
                if last_high < level:
                    return False, "нет пробоя уровня Donchian"
                if last_close <= level + close_buffer:
                    return False, f"закрытие не удержалось выше канала + {close_buffer / max(atr, 1e-12):.2f} ATR"
                return True, "classic_turtle_breakout_long_filtered"

            if not is_fresh_breakout(prev_close, upper, level, "short"):
                return False, "пробой не свежий: предыдущая свеча уже закрылась ниже канала"
            if last_low > level:
                return False, "нет пробоя уровня Donchian"
            if last_close >= level - close_buffer:
                return False, f"закрытие не удержалось ниже канала - {close_buffer / max(atr, 1e-12):.2f} ATR"
            return True, "classic_turtle_breakout_short_filtered"

        filter_profile = self._timeframe_filter_profile()
        breakout_buffer_mult = float(filter_profile.get("breakout_buffer_atr", getattr(self.cfg, "breakout_buffer_atr", 0.0)) or 0.0)
        breakout_buffer = max(atr * breakout_buffer_mult, abs(level) * 0.00004)
        min_body = atr * float(filter_profile.get("breakout_min_body_atr", getattr(self.cfg, "breakout_min_body_atr", 0.0)) or 0.0)
        min_body_ratio = float(filter_profile.get("min_body_to_range_ratio", getattr(self.cfg, "min_body_to_range_ratio", 0.0)) or 0.0)
        near_extreme = float(filter_profile.get("breakout_close_near_extreme_ratio", getattr(self.cfg, "breakout_close_near_extreme_ratio", 0.0)) or 0.0)
        max_prebreak_dist = float(filter_profile.get("breakout_max_prebreak_distance_atr", getattr(self.cfg, "breakout_max_prebreak_distance_atr", 999.0)) or 999.0)
        max_breakout_dist = float(filter_profile.get("breakout_max_distance_atr", getattr(self.cfg, "breakout_max_distance_atr", 999.0)) or 999.0)

        if side == "long":
            if prev_high >= level:
                return False, "пробой не свежий: предыдущая свеча уже была на уровне/выше канала"
            if (level - prev_high) / max(atr, 1e-12) > max_prebreak_dist:
                return False, "пробой слишком далёк от канала до сигнальной свечи"
            if last_high < level + breakout_buffer:
                return False, f"нет пробоя с буфером {breakout_buffer_mult:.2f} ATR"
            if min_body > 0 and body < min_body:
                return False, f"слишком маленькое тело свечи {body / max(atr, 1e-12):.2f} ATR"
            if min_body_ratio > 0 and (body / candle_range) < min_body_ratio:
                return False, f"тело свечи слишком мало к диапазону {body / candle_range:.2f} < {min_body_ratio:.2f}"
            if ((last_close - level) / max(atr, 1e-12)) > max_breakout_dist:
                return False, f"late breakout distance {(last_close - level) / max(atr, 1e-12):.2f} ATR > {max_breakout_dist:.2f} ATR"
            if near_extreme > 0 and (last_high - last_close) / candle_range > (1.0 - near_extreme):
                return False, "закрытие слишком далеко от верхнего экстремума"
            if last_close < level + breakout_buffer * 0.35:
                return False, "свеча не удержала пробой выше канала к закрытию"
            return True, "classic_turtle_buffered_breakout_long"

        if prev_low <= level:
            return False, "пробой не свежий: предыдущая свеча уже была на уровне/ниже канала"
        if (prev_low - level) / max(atr, 1e-12) > max_prebreak_dist:
            return False, "пробой слишком далёк от канала до сигнальной свечи"
        if last_low > level - breakout_buffer:
            return False, f"нет пробоя с буфером {breakout_buffer_mult:.2f} ATR"
        if min_body > 0 and body < min_body:
            return False, f"слишком маленькое тело свечи {body / max(atr, 1e-12):.2f} ATR"
        if min_body_ratio > 0 and (body / candle_range) < min_body_ratio:
            return False, f"тело свечи слишком мало к диапазону {body / candle_range:.2f} < {min_body_ratio:.2f}"
        if ((level - last_close) / max(atr, 1e-12)) > max_breakout_dist:
            return False, f"late breakout distance {(level - last_close) / max(atr, 1e-12):.2f} ATR > {max_breakout_dist:.2f} ATR"
        if near_extreme > 0 and (last_close - last_low) / candle_range > (1.0 - near_extreme):
            return False, "закрытие слишком далеко от нижнего экстремума"
        if last_close > level - breakout_buffer * 0.35:
            return False, "свеча не удержала пробой ниже канала к закрытию"
        return True, "classic_turtle_buffered_breakout_short"

    def _compute_turtle_regime(self) -> dict:
        probe_inst = "BTC-USDT-SWAP" if "BTC-USDT-SWAP" in self.gateway.swap_ids else (self.gateway.swap_ids[0] if self.gateway.swap_ids else "")
        if not probe_inst:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        try:
            candles = self.gateway.get_candles(
                probe_inst,
                self.cfg.timeframe,
                max(self.cfg.atr_period, self.cfg.long_entry_period, 32) + 8
            )
        except Exception:
            candles = []

        if len(candles) < max(self.cfg.atr_period + 2, 20):
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        price = float(candles[-1][4] or 0.0)
        if atr <= 0 or price <= 0:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        window = candles[-min(len(candles), max(20, self.cfg.flat_lookback_candles)):]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        channel = max(highs) - min(lows)
        channel_atr_ratio = channel / max(atr, 1e-12)
        atr_pct = (atr / price) * 100.0

        net_move = abs(closes[-1] - closes[0]) if len(closes) > 1 else 0.0
        travel = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / travel) if travel > 0 else 0.0

        center = (max(highs) + min(lows)) / 2.0
        breakout_pressure = abs(closes[-1] - center) / max(channel, 1e-12)

        score = 0
        if channel_atr_ratio >= 3.0:
            score += 1
        if efficiency_ratio >= 0.28:
            score += 1
        if atr_pct >= max(0.10, self.cfg.min_atr_pct * 0.75):
            score += 1
        if breakout_pressure >= 0.33:
            score += 1

        if score >= 3:
            label = "Трендовый"
        elif score == 2:
            label = "Нейтральный"
        else:
            label = "Флэт"

        return {
            "label": label,
            "score": score,
            "channel_atr_ratio": round(channel_atr_ratio, 2),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "atr_pct": round(atr_pct, 3),
            "instrument": probe_inst,
        }

    def calculate_atr_from_candles(self, candles: List[List[float]], period: int) -> float:
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            high = candles[i][2]
            low = candles[i][3]
            prev_close = candles[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        recent = trs[-period:]
        return sum(recent) / len(recent)

    def compute_atr(self, inst_id: str) -> float:
        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, self.cfg.atr_period + 5)
        return self.calculate_atr_from_candles(candles, self.cfg.atr_period)

    def _extract_available_usdt(self, account: dict) -> float:
        data = account.get("data", [])
        if not data:
            return 0.0
        root = data[0]
        details = root.get("details", []) or []
        for item in details:
            if str(item.get("ccy", "")).upper() == "USDT":
                for key in ("availBal", "availEq", "cashBal", "eq"):
                    try:
                        value = float(item.get(key) or 0.0)
                    except (TypeError, ValueError):
                        value = 0.0
                    if value > 0:
                        return value
        for key in ("availEq", "adjEq", "totalEq"):
            try:
                value = float(root.get(key) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value
        return 0.0

    def _extract_total_usdt(self, account: dict) -> float:
        data = account.get("data", [])
        if not data:
            return 0.0
        root = data[0]
        try:
            total = float(root.get("totalEq") or 0.0)
        except (TypeError, ValueError):
            total = 0.0
        if total > 0:
            return total
        return self._extract_available_usdt(account)

    def _extract_order_error(self, resp: dict) -> tuple[str, str]:
        data = resp.get("data", []) or []
        if not data:
            return str(resp.get("code") or ""), str(resp.get("msg") or "")
        first = data[0] or {}
        return str(first.get("sCode") or resp.get("code") or ""), str(first.get("sMsg") or resp.get("msg") or "")

    def _handle_order_rejection(self, inst_id: str, resp: dict, context: str = "ордер") -> None:
        code, message = self._extract_order_error(resp)
        safe_message = (message or "").strip()

        if code in OkxGateway.COMPLIANCE_RESTRICTION_CODES:
            self.blocked_instruments[inst_id] = message or "Local compliance restriction"
            if inst_id not in self.cfg.blacklist:
                self.cfg.blacklist.append(inst_id)
            self.log_line.emit(f"{inst_id}: исключён из сканирования из-за ограничений биржи ({code}: {safe_message})")
            logging.warning("Instrument %s blocked by exchange compliance: %s", inst_id, message)
            self._notify(
                f"🚫 Инструмент исключён биржей\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}"
            )
            return

        if code in OkxGateway.POSITION_LIMIT_ERROR_CODES:
            cooldown_sec = 6 * 60 * 60
            self.temp_blocked_until[inst_id] = time.time() + cooldown_sec
            self.blocked_instruments[inst_id] = safe_message or "Exchange open position limit reached"
            self.log_line.emit(f"{inst_id}: временно исключён из сканирования на 6 часов из-за лимита позиции биржи ({code}: {safe_message})")
            logging.warning("Instrument %s blocked by exchange position limit: %s", inst_id, message)
            self._notify(
                f"⚠️ Инструмент временно исключён\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}\n"
                f"Пауза: 6 часов"
            )
            return

        if code in OkxGateway.LOT_SIZE_ERROR_CODES:
            self.log_line.emit(f"{inst_id}: отклонение {context} из-за шага лота ({code}: {safe_message}). Инструмент пропущен до следующего цикла.")
            logging.warning("Lot size rejection for %s: %s", inst_id, message)
            self._notify(
                f"⚠️ Отклонение ордера по шагу лота\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}"
            )
            return

        self.stats_logger.log("order_rejected", inst_id=inst_id, context=context, code=code, reason=safe_message or str(resp))
        self.log_line.emit(f"{inst_id}: биржа отклонила {context}: {resp}")
        self._notify(
            f"⚠️ Биржа отклонила {context}\n\n"
            f"Инструмент: {inst_id}\n"
            f"Код: {code}\n"
            f"Причина: {safe_message or str(resp)}"
        )

    def enter_position(self, inst_id: str, side: str, price: float, atr: float, system_name: str) -> bool:
        account = self.gateway.get_account_balance()
        data = account.get("data", [])
        if not data:
            return False
        total_eq = self._extract_total_usdt(account)
        available_eq = self._extract_available_usdt(account)
        if total_eq <= 0 or available_eq <= 0:
            return False

        exposure_ok, exposure_reason = self._entry_side_limits_ok(side)
        if not exposure_ok:
            self.stats_logger.log(
                "entry_rejected",
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                reason=exposure_reason,
            )
            self.log_line.emit(f"{inst_id}: вход пропущен — {exposure_reason}")
            return False
        info = self.gateway.instrument_info(inst_id)
        ct_val = float(info.get("ctVal") or 1.0)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)

        risk_amount = total_eq * (self.cfg.risk_per_trade_pct / 100.0)
        risk_per_contract = atr * ct_val * self.cfg.atr_stop_multiple
        if risk_per_contract <= 0 or price <= 0 or ct_val <= 0:
            return False

        qty_by_risk = risk_amount / risk_per_contract
        max_notional = available_eq * (self.cfg.max_position_notional_pct / 100.0)
        qty_by_notional = max_notional / (price * ct_val)
        qty = min(qty_by_risk, qty_by_notional)
        if max_mkt_sz > 0:
            qty = min(qty, max_mkt_sz)
        qty = self.floor_to_step(qty, lot_sz)
        if qty < min_sz:
            return False

        order_side = "buy" if side == "long" else "sell"
        resp = self.gateway.place_market_order(inst_id, order_side, qty)
        if resp.get("code") != "0":
            self._handle_order_rejection(inst_id, resp, "ордер")
            return False

        stop_price = price - self.cfg.atr_stop_multiple * atr if side == "long" else price + self.cfg.atr_stop_multiple * atr
        next_pyramid = price + self.cfg.add_unit_every_atr * atr if side == "long" else price - self.cfg.add_unit_every_atr * atr
        if system_name == "Turtle 55":
            entry_period = self.cfg.long_entry_period
            exit_period = self.cfg.long_exit_period
        elif system_name == "Turtle 20":
            entry_period = self.cfg.short_entry_period
            exit_period = self.cfg.short_exit_period
        else:
            entry_period = self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period
            exit_period = self.cfg.long_exit_period if side == "long" else self.cfg.short_exit_period

        trade_id = _stable_trade_id(inst_id, side, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        position_notional_usdt = price * qty * ct_val
        entry_context_payload = self._build_entry_context_payload(
            inst_id, side, price, atr, stop_price, next_pyramid, system_name, qty,
            trade_id=trade_id,
            risk_amount_usdt=risk_amount,
            risk_per_contract=risk_per_contract,
            planned_risk_pct=float(self.cfg.risk_per_trade_pct),
            position_notional_usdt=position_notional_usdt,
            qty_by_risk=qty_by_risk,
            qty_by_notional=qty_by_notional,
        )
        entry_context_file = self._save_entry_context(entry_context_payload)

        state = PositionState(
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=price,
            last_px=price,
            unrealized_pnl=0.0,
            margin=0.0,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            base_unit_qty=qty,
            signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            units=1,
            system_name=system_name,
            entry_period=entry_period,
            exit_period=exit_period,
            entry_context_file=entry_context_file,
            initial_stop_price=stop_price,
            peak_price=price,
            trough_price=price,
            peak_unrealized_pnl=0.0,
            peak_pnl_pct=0.0,
            trade_id=trade_id,
            planned_risk_pct=float(self.cfg.risk_per_trade_pct),
            risk_amount_usdt=risk_amount,
            risk_per_contract=risk_per_contract,
            position_notional_usdt=position_notional_usdt,
        )
        self.position_state[inst_id] = state
        self.position_journal_logger.log("OPEN", trade_id=trade_id, inst_id=inst_id, side=side, price=price, stop_price=stop_price, qty=qty, units=1, atr=atr, system_name=system_name, planned_risk_pct=float(self.cfg.risk_per_trade_pct), risk_amount_usdt=risk_amount, risk_per_contract=risk_per_contract, position_notional_usdt=position_notional_usdt, note="Первичный вход")
        self._log_breakout_quality(inst_id, side, price, atr, system_name)
        self._save_state()
        self.stats_logger.log("position_opened", trade_id=trade_id, inst_id=inst_id, side=side, qty=qty, price=price, atr=atr, stop_price=stop_price, system_name=system_name, timeframe=self.cfg.timeframe, balance_total=total_eq, balance_available=available_eq, planned_risk_pct=float(self.cfg.risk_per_trade_pct), risk_amount_usdt=risk_amount, risk_per_contract=risk_per_contract, position_notional_usdt=position_notional_usdt)
        self.trade_logger.log("OPEN", inst_id, side, qty, price, atr, stop_price, system_name, "Первичный вход")
        self.log_line.emit(f"Открыта {side} позиция {inst_id}, qty={qty}, ATR={atr:.6f}, stop={stop_price:.6f}")
        self._notify(
            f"{'📈' if side == 'long' else '📉'} Открыта {side.upper()} позиция\n\n"
            f"Инструмент: {inst_id}\n"
            f"Цена входа: {self._fmt_price(price)}\n"
            f"Qty: {qty}\n"
            f"ATR: {self._fmt_price(atr)}\n"
            f"Стоп: {self._fmt_price(stop_price)}\n"
            f"Юнитов: 1\n"
            f"Система: {system_name}"
        )

    def _build_entry_context_payload(self, inst_id: str, side: str, price: float, atr: float, stop_price: float, next_pyramid: float, system_name: str, qty: float, trade_id: str = "", risk_amount_usdt: float = 0.0, risk_per_contract: float = 0.0, planned_risk_pct: float = 0.0, position_notional_usdt: float = 0.0, qty_by_risk: float = 0.0, qty_by_notional: float = 0.0) -> dict:
        candles_payload = []
        try:
            candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(80, self.cfg.long_entry_period + 10)) or []
            candles_payload = candles[-80:]
        except Exception as exc:
            logging.warning("Failed to capture candles for entry context %s: %s", inst_id, exc)

        entry_period = self.cfg.long_entry_period if system_name == "Turtle 55" else self.cfg.short_entry_period
        exit_period = self.cfg.long_exit_period if system_name == "Turtle 55" else self.cfg.short_exit_period

        channel_high = None
        channel_low = None
        try:
            if len(candles_payload) >= max(2, entry_period + 1):
                ref_window = candles_payload[-entry_period - 1:-1]
                channel_high = max(float(c[2]) for c in ref_window)
                channel_low = min(float(c[3]) for c in ref_window)
        except Exception:
            channel_high = None
            channel_low = None

        body_atr_at_entry = 0.0
        body_to_range_ratio_at_entry = 0.0
        close_near_extreme_ratio_at_entry = 0.0
        breakout_distance_atr = 0.0
        atr_pct_at_entry = (atr / max(price, 1e-12)) * 100.0 if price > 0 else 0.0
        if candles_payload:
            try:
                last = candles_payload[-1]
                lo = float(last[3]); hi = float(last[2]); op = float(last[1]); cl = float(last[4])
                rng = max(hi - lo, 1e-12)
                body = abs(cl - op)
                body_atr_at_entry = body / max(atr, 1e-12)
                body_to_range_ratio_at_entry = body / rng
                close_near_extreme_ratio_at_entry = ((hi - cl) / rng) if side == "long" else ((cl - lo) / rng)
                if side == "long" and channel_high is not None:
                    breakout_distance_atr = max(0.0, (price - float(channel_high)) / max(atr, 1e-12))
                elif side == "short" and channel_low is not None:
                    breakout_distance_atr = max(0.0, (float(channel_low) - price) / max(atr, 1e-12))
            except Exception:
                pass

        return {
            "version": APP_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trade_id": trade_id or _stable_trade_id(inst_id, side, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "inst_id": inst_id,
            "side": side,
            "timeframe": self.cfg.timeframe,
            "system_name": system_name,
            "entry_price": price,
            "entry_price_fact": price,
            "initial_stop_price": stop_price,
            "atr": atr,
            "stop_price": stop_price,
            "next_pyramid_price": next_pyramid,
            "qty": qty,
            "risk_amount_usdt": risk_amount_usdt,
            "risk_per_contract": risk_per_contract,
            "planned_risk_pct": planned_risk_pct,
            "position_notional_usdt": position_notional_usdt,
            "qty_by_risk": qty_by_risk,
            "qty_by_notional": qty_by_notional,
            "entry_period": entry_period,
            "exit_period": exit_period,
            "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
            "add_unit_every_atr": getattr(self.cfg, "add_unit_every_atr", 0.5),
            "channel_high": channel_high,
            "channel_low": channel_low,
            "breakout_distance_atr": breakout_distance_atr,
            "channel_atr_ratio": ((float(channel_high) - float(channel_low)) / max(atr, 1e-12)) if channel_high is not None and channel_low is not None else 0.0,
            "atr_pct_at_entry": atr_pct_at_entry,
            "body_atr_at_entry": body_atr_at_entry,
            "body_to_range_ratio_at_entry": body_to_range_ratio_at_entry,
            "close_near_extreme_ratio_at_entry": close_near_extreme_ratio_at_entry,
            "candles": candles_payload,
        }

    def _save_entry_context(self, payload: dict) -> str:
        try:
            safe_inst = str(payload.get("inst_id", "UNKNOWN")).replace("/", "_").replace(":", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = ENTRY_CONTEXT_DIR / f"{ts}_{safe_inst}_{payload.get('side', 'na')}.json"
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(file_path)
        except Exception as exc:
            logging.warning("Failed to save entry context for %s: %s", payload.get("inst_id"), exc)
            return ""

    def _position_initial_risk(self, state: PositionState) -> float:
        initial_stop = float(getattr(state, "initial_stop_price", 0.0) or 0.0)
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        if avg_px <= 0:
            return 0.0
        if initial_stop > 0:
            return max(abs(avg_px - initial_stop), 1e-12)
        atr = float(getattr(state, "atr", 0.0) or 0.0)
        mult = float(getattr(self.cfg, "atr_stop_multiple", 2.0) or 2.0)
        return max(atr * mult, 1e-12)

    def _position_r_multiple(self, state: PositionState, price: float) -> float:
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        if avg_px <= 0:
            return 0.0
        risk = self._position_initial_risk(state)
        move = (float(price) - avg_px) if str(getattr(state, "side", "")).lower() == "long" else (avg_px - float(price))
        return move / max(risk, 1e-12)

    def _update_position_extremes(self, state: PositionState, current_price: float) -> None:
        current_price = float(current_price or 0.0)
        if current_price <= 0:
            return
        if float(getattr(state, "peak_price", 0.0) or 0.0) <= 0.0:
            state.peak_price = max(current_price, float(getattr(state, "avg_px", current_price) or current_price))
        if float(getattr(state, "trough_price", 0.0) or 0.0) <= 0.0:
            state.trough_price = min(current_price, float(getattr(state, "avg_px", current_price) or current_price))

        if str(getattr(state, "side", "")).lower() == "long":
            state.peak_price = max(float(state.peak_price or current_price), current_price)
            state.trough_price = min(float(state.trough_price or current_price), current_price)
        else:
            state.peak_price = max(float(state.peak_price or current_price), current_price)
            state.trough_price = min(float(state.trough_price or current_price), current_price)

        current_upl = float(getattr(state, "unrealized_pnl", 0.0) or 0.0)
        if current_upl > float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0):
            state.peak_unrealized_pnl = current_upl
        current_pct = self._position_pnl_pct(state, last_px=current_price)
        if current_pct > float(getattr(state, "peak_pnl_pct", 0.0) or 0.0):
            state.peak_pnl_pct = current_pct

    def _trend_pullback_exit_reason(self, state: PositionState, current_price: float) -> str:
        if not bool(getattr(self.cfg, "trend_stop_use_peak_pullback_exit", True)):
            return ""
        activation_r = float(getattr(self.cfg, "trend_stop_activation_r", 0.80) or 0.80)
        max_pullback_r = float(getattr(self.cfg, "trend_stop_max_pullback_from_peak_r", 0.90) or 0.90)
        current_r = self._position_r_multiple(state, current_price)
        peak_anchor = float(getattr(state, "peak_price", 0.0) or 0.0) if state.side == "long" else float(getattr(state, "trough_price", 0.0) or 0.0)
        if peak_anchor <= 0:
            return ""
        peak_r = self._position_r_multiple(state, peak_anchor)
        if peak_r < activation_r:
            return ""
        if (peak_r - current_r) < max_pullback_r:
            return ""
        lock_floor_r = max(float(getattr(self.cfg, "trend_stop_min_locked_r", 0.35) or 0.35), peak_r - max_pullback_r)
        if current_r > lock_floor_r:
            return ""
        return f"Защита тренда: откат от пика {peak_r:.2f}R → {current_r:.2f}R"

    def manage_open_positions(self) -> None:
        self.stats_logger.log("positions_check_started", tracked_positions=len(self.position_state))
        for inst_id, state in list(self.position_state.items()):
            retry_after = self.close_retry_after.get(inst_id, 0.0)
            if retry_after and retry_after > time.time():
                continue
            try:
                self.update_and_maybe_exit_or_pyramid(state)
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка управления позицией: {exc}")
                logging.warning("Manage failed for %s: %s", inst_id, exc)


    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:
        candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 5)
        if not candles:
            return

        ticker = self.gateway.get_ticker_data(state.inst_id)
        current_price = float(ticker.get("markPx") or ticker.get("last") or state.last_px or state.avg_px)
        state.last_px = current_price

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr > 0:
            state.atr = atr

        prev_stop_price = float(state.stop_price or 0.0)
        prev_peak_upl = float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0)
        self._update_position_extremes(state, current_price)
        state.stop_price = self.trailing_stop(state, state.atr, current_price, candles=candles)
        stop_update_threshold = max(float(state.atr or 0.0) * 0.10, abs(float(current_price or 0.0)) * 0.0001, 1e-12)
        if abs(float(state.stop_price or 0.0) - prev_stop_price) >= stop_update_threshold:
            if not getattr(state, "trailing_activated_at", ""):
                state.trailing_activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not getattr(state, "breakeven_activated_at", ""):
                if state.side == "long" and float(state.stop_price or 0.0) >= float(state.avg_px or 0.0):
                    state.breakeven_activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elif state.side == "short" and float(state.stop_price or 0.0) <= float(state.avg_px or 0.0):
                    state.breakeven_activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.position_journal_logger.log(
                "TRAIL_UPDATE",
                trade_id=getattr(state, "trade_id", ""),
                inst_id=state.inst_id,
                side=state.side,
                price=current_price,
                prev_stop_price=prev_stop_price,
                stop_price=state.stop_price,
                qty=state.qty,
                units=state.units,
                unrealized_pnl=state.unrealized_pnl,
                peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0),
                note=f"Стоп подтянут на {abs(float(state.stop_price or 0.0) - prev_stop_price):.6f}",
            )
        elif float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0) > prev_peak_upl + max(25.0, abs(prev_peak_upl) * 0.08):
            self.position_journal_logger.log(
                "PEAK_PNL",
                trade_id=getattr(state, "trade_id", ""),
                inst_id=state.inst_id,
                side=state.side,
                price=current_price,
                stop_price=state.stop_price,
                qty=state.qty,
                units=state.units,
                unrealized_pnl=state.unrealized_pnl,
                peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0),
                note="Новый пик open PnL",
            )

        exit_window = candles[-state.exit_period:]
        exit_long_level = min(c[3] for c in exit_window)
        exit_short_level = max(c[2] for c in exit_window)

        stop_hit = (state.side == "long" and current_price <= state.stop_price) or (
            state.side == "short" and current_price >= state.stop_price
        )
        turtle_exit = (state.side == "long" and current_price <= exit_long_level) or (
            state.side == "short" and current_price >= exit_short_level
        )
        trend_pullback_reason = self._trend_pullback_exit_reason(state, current_price)

        if stop_hit:
            self.close_position(state, current_price, f"ATR стоп {self.cfg.atr_stop_multiple}N", candles=candles)
            return

        if trend_pullback_reason:
            self.close_position(state, current_price, trend_pullback_reason, candles=candles)
            return

        if turtle_exit:
            self.close_position(state, current_price, f"Канальный выход {state.exit_period} свечей", candles=candles)
            return

        self.try_pyramid(state, current_price, candles)
        self._save_state()

    def _entry_bar_closed(self, state: PositionState, candles: List[List[float]]) -> bool:
        if not candles:
            return False
        try:
            entry_ts = datetime.strptime(str(getattr(state, "entry_time", "")), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return False
        last_closed_ts = int(float(candles[-1][0])) / 1000.0
        return last_closed_ts >= entry_ts + self._timeframe_seconds()

    def _breakeven_ready(self, state: PositionState, atr: float, current_price: float, candles: List[List[float]]) -> bool:
        if not bool(getattr(self.cfg, "breakeven_enabled", True)):
            return False
        hold_bars = max(0, int(getattr(self.cfg, "breakeven_min_hold_bars", 1) or 1))
        if hold_bars > 0 and self._entry_bar_closed(state, candles):
            return True
        min_profit_atr = float(getattr(self.cfg, "breakeven_min_profit_atr", 0.8) or 0.8)
        move_atr = ((float(current_price) - float(state.avg_px)) / max(atr, 1e-12)) if state.side == "long" else ((float(state.avg_px) - float(current_price)) / max(atr, 1e-12))
        if move_atr >= min_profit_atr:
            return True
        current_r = self._position_r_multiple(state, current_price)
        return current_r >= float(getattr(self.cfg, "breakeven_min_locked_r", 0.5) or 0.5)

    def trailing_stop(self, state: PositionState, atr: float, last_close: float, candles: Optional[List[List[float]]] = None) -> float:
        if atr <= 0:
            return state.stop_price

        current_stop = float(getattr(state, "stop_price", 0.0) or 0.0)
        initial_stop = float(getattr(state, "initial_stop_price", 0.0) or 0.0)
        if current_stop <= 0.0:
            current_stop = initial_stop
        entry_bar_closed = self._entry_bar_closed(state, candles or [])
        if bool(getattr(self.cfg, "disable_trailing_on_entry_bar", True)) and not entry_bar_closed:
            return current_stop or initial_stop

        peak_anchor = float(getattr(state, "peak_price", 0.0) or 0.0) if state.side == "long" else float(getattr(state, "trough_price", 0.0) or 0.0)
        if peak_anchor <= 0:
            peak_anchor = float(last_close or state.last_px or state.avg_px or 0.0)

        peak_r = self._position_r_multiple(state, peak_anchor)
        stop_multiple = float(self.cfg.atr_stop_multiple)
        if state.units >= 2:
            stop_multiple = min(stop_multiple, 1.70)
        if state.units >= 3:
            stop_multiple = min(stop_multiple, 1.45)
        if state.units >= 4:
            stop_multiple = min(stop_multiple, float(getattr(self.cfg, "trend_stop_peak_atr_multiple_after_4_units", 1.20) or 1.20))
        if peak_r >= float(getattr(self.cfg, "trend_stop_activation_r", 1.20) or 1.20):
            stop_multiple = min(stop_multiple, float(getattr(self.cfg, "trend_stop_peak_atr_multiple", 1.60) or 1.60))

        initial_risk = self._position_initial_risk(state)
        lock_floor_r = 0.0
        activation_r = float(getattr(self.cfg, "trend_stop_activation_r", 1.20) or 1.20)
        if peak_r >= activation_r:
            lock_floor_r = max(lock_floor_r, float(getattr(self.cfg, "trend_stop_min_locked_r", 0.60) or 0.60))
        if peak_r >= 1.50:
            lock_floor_r = max(lock_floor_r, 0.70)
        if peak_r >= 2.00:
            lock_floor_r = max(lock_floor_r, 1.10)
        if state.units >= 4 and peak_r >= 1.00:
            lock_floor_r = max(lock_floor_r, 0.90)

        breakeven_ready = self._breakeven_ready(state, atr, last_close, candles or [])
        breakeven_floor = float(state.avg_px)

        if state.side == "long":
            candidate = peak_anchor - stop_multiple * atr
            floor_price = float(state.avg_px) + initial_risk * lock_floor_r
            if initial_stop > 0.0:
                candidate = max(candidate, initial_stop)
            if breakeven_ready:
                floor_price = max(floor_price, breakeven_floor)
            return max(current_stop, candidate, floor_price)

        candidate = peak_anchor + stop_multiple * atr
        floor_price = float(state.avg_px) - initial_risk * lock_floor_r
        if initial_stop > 0.0:
            candidate = min(candidate, initial_stop)
        if breakeven_ready:
            floor_price = min(floor_price, breakeven_floor)
        return min(current_stop, candidate, floor_price) if current_stop else min(candidate, floor_price)

    def _pyramid_unit_scale(self, current_units: int) -> float:
        if current_units <= 1:
            return self.cfg.pyramid_second_unit_scale
        if current_units == 2:
            return self.cfg.pyramid_third_unit_scale
        return self.cfg.pyramid_fourth_unit_scale

    def _has_locked_break_even(self, state: PositionState) -> bool:
        buffer = max(state.atr * self.cfg.pyramid_break_even_buffer_atr, state.avg_px * 0.0002)
        if state.side == "long":
            return state.stop_price >= state.avg_px + buffer
        return state.stop_price <= state.avg_px - buffer


    def _trend_confirms_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> tuple[bool, str]:
        if not candles:
            return False, "нет свечей для подтверждения"
        if state.atr <= 0:
            return False, "ATR недоступен"

        progress = abs(last_close - state.avg_px)
        if progress < state.atr * self.cfg.pyramid_min_progress_atr:
            return False, f"недостаточный прогресс {progress / state.atr:.2f} ATR"

        distance_to_stop = abs(last_close - state.stop_price)
        if distance_to_stop < state.atr * self.cfg.pyramid_min_stop_distance_atr:
            return False, f"слишком близко к стопу {distance_to_stop / state.atr:.2f} ATR"

        # Ближе к классической Turtle:
        # не требуем body-ratio, flat-check и микроструктурных подтверждений.
        return True, ""


    def _lock_profit_after_pyramid(self, state: PositionState, fill_price: float) -> None:
        if state.atr <= 0 or state.units <= 1:
            return

        self._update_position_extremes(state, fill_price)
        state.stop_price = self.trailing_stop(state, state.atr, fill_price)

        if state.side == "long":
            if state.units == 2:
                floor = state.avg_px + state.atr * 0.05
            elif state.units == 3:
                floor = state.avg_px + state.atr * 0.35
            else:
                floor = state.avg_px + state.atr * 0.70
            tightened = float(getattr(state, "peak_price", fill_price) or fill_price) - max(state.atr * 1.25, 1e-12)
            state.stop_price = max(float(state.stop_price), floor, tightened)
        else:
            if state.units == 2:
                floor = state.avg_px - state.atr * 0.05
            elif state.units == 3:
                floor = state.avg_px - state.atr * 0.35
            else:
                floor = state.avg_px - state.atr * 0.70
            tightened = float(getattr(state, "trough_price", fill_price) or fill_price) + max(state.atr * 1.25, 1e-12)
            if float(state.stop_price):
                state.stop_price = min(float(state.stop_price), floor, tightened)
            else:
                state.stop_price = min(floor, tightened)

    def try_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> None:
        if self.cfg.max_units_per_symbol > 0 and state.units >= self.cfg.max_units_per_symbol:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="max_units_reached", last_price=last_close)
            return
        if state.atr <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="position_not_eligible", last_price=last_close, note="atr_unavailable")
            return

        should_add = (state.side == "long" and last_close >= state.next_pyramid_price) or (
            state.side == "short" and last_close <= state.next_pyramid_price
        )
        distance_to_next = ((last_close - state.next_pyramid_price) / max(state.atr, 1e-12)) if state.side == "long" else ((state.next_pyramid_price - last_close) / max(state.atr, 1e-12))
        if not should_add:
            return

        if not self._has_locked_break_even(state):
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason="breakeven_not_locked", reason_code="breakeven_not_locked", last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="breakeven_not_locked", last_price=last_close, distance_to_next_add_atr=round(distance_to_next, 6), unrealized_r=round(self._position_r_multiple(state, last_close), 6), mfe_r=round(self._position_r_multiple(state, getattr(state, "peak_price", last_close) if state.side == "long" else getattr(state, "trough_price", last_close)), 6))
            self.log_line.emit(f"{state.inst_id}: добор пропущен — стоп ещё не зафиксировал breakeven")
            return

        allowed, reason = self._trend_confirms_pyramid(state, last_close, candles)
        if not allowed:
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason=reason, reason_code=_classify_reason_code(reason), last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            block_code = "trend_not_confirmed"
            if "прогресс" in reason:
                block_code = "progress_below_threshold"
            elif "стоп" in reason:
                block_code = "stop_distance_too_small"
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked=block_code, last_price=last_close, distance_to_next_add_atr=round(distance_to_next, 6), unrealized_r=round(self._position_r_multiple(state, last_close), 6), mfe_r=round(self._position_r_multiple(state, getattr(state, "peak_price", last_close) if state.side == "long" else getattr(state, "trough_price", last_close)), 6), note=reason)
            self.log_line.emit(f"{state.inst_id}: добор пропущен — {reason}")
            return

        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)
        scale = float(self._pyramid_unit_scale(state.units) or 1.0)
        add_qty = max(float(getattr(state, "base_unit_qty", 0.0) or 0.0) * scale, 0.0)
        if max_mkt_sz > 0:
            add_qty = min(add_qty, max_mkt_sz)
        add_qty = self.floor_to_step(add_qty, lot_sz)
        if add_qty < min_sz or add_qty <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="position_not_eligible", last_price=last_close, note="qty_below_min", proposed_qty=add_qty)
            return

        order_side = "buy" if state.side == "long" else "sell"
        resp = self.gateway.place_market_order(state.inst_id, order_side, add_qty)
        if resp.get("code") != "0":
            self._handle_order_rejection(state.inst_id, resp, "добор")
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason="order_rejected", reason_code=str(resp.get("code") or "order_rejected"), last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="order_rejected", last_price=last_close, note=str(resp), proposed_qty=add_qty)
            return

        fill_price = float(last_close)
        old_qty = float(state.qty)
        new_qty = old_qty + add_qty
        if new_qty <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="unknown", last_price=last_close, note="new_qty_non_positive")
            return

        state.avg_px = ((state.avg_px * old_qty) + (fill_price * add_qty)) / new_qty
        state.qty = new_qty
        state.last_px = fill_price
        state.units += 1
        state.position_notional_usdt = float(getattr(state, "position_notional_usdt", 0.0) or 0.0) + fill_price * add_qty * ct_val
        state.next_pyramid_price = fill_price + self.cfg.add_unit_every_atr * state.atr if state.side == "long" else fill_price - self.cfg.add_unit_every_atr * state.atr
        self._update_position_extremes(state, fill_price)
        self._lock_profit_after_pyramid(state, fill_price)

        self.position_journal_logger.log("ADD_UNIT", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=fill_price, stop_price=state.stop_price, qty=state.qty, add_qty=add_qty, units=state.units, atr=state.atr, next_pyramid_price=state.next_pyramid_price, note="Добор по Turtle")
        self.stats_logger.log("pyramid_added", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, qty=state.qty, add_qty=add_qty, price=fill_price, stop_price=state.stop_price, units=state.units, next_pyramid_price=state.next_pyramid_price)
        self.trade_logger.log("ADD", state.inst_id, state.side, add_qty, fill_price, state.atr, state.stop_price, state.system_name, f"Добор до {state.units} юнитов")
        self._log_pyramid_diagnostic(state, "pyramid_added", reason_blocked="", last_price=fill_price, add_qty=add_qty, distance_to_next_add_atr=round(distance_to_next, 6), unrealized_r=round(self._position_r_multiple(state, fill_price), 6), mfe_r=round(self._position_r_multiple(state, getattr(state, "peak_price", fill_price) if state.side == "long" else getattr(state, "trough_price", fill_price)), 6))
        self.log_line.emit(f"{state.inst_id}: добавлен юнит #{state.units}, qty+={add_qty}, новый stop={state.stop_price:.6f}")
        self._save_state()



    def _finalize_closed_trade(self, state: PositionState, price: float, reason: str, candles: Optional[List[List[float]]] = None) -> None:
        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)

        pnl = ((price - state.avg_px) * state.qty * ct_val) if state.side == "long" else ((state.avg_px - price) * state.qty * ct_val)

        estimated_notional = max(state.avg_px * state.qty * ct_val, 0.0)
        estimated_margin = estimated_notional / max(float(self.cfg.leverage or 1), 1.0)
        if estimated_margin > 0:
            pnl_pct = (pnl / estimated_margin) * 100.0
        else:
            pnl_pct = 0.0

        self.stats_logger.log("position_closed", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason, reason_code=_classify_reason_code(reason))
        self.trade_logger.log("CLOSE", state.inst_id, state.side, state.qty, price, state.atr, state.stop_price, state.system_name, reason)
        self.position_journal_logger.log("CLOSE", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=price, stop_price=state.stop_price, qty=state.qty, units=state.units, unrealized_pnl=state.unrealized_pnl, peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0), reason=reason, note="Выход из позиции")
        duration_sec = 0
        try:
            duration_sec = max(0, int((datetime.now() - datetime.strptime(state.entry_time, "%Y-%m-%d %H:%M:%S")).total_seconds()))
        except Exception:
            duration_sec = 0
        trade_context_payload = self._build_trade_lifecycle_payload(state, price, reason, pnl, pnl_pct, duration_sec, candles=candles)
        trade_context_file = self._save_trade_context(trade_context_payload)
        self.closed_trades.append(ClosedTrade(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inst_id=state.inst_id,
            side=state.side,
            qty=state.qty,
            entry_px=state.avg_px,
            exit_px=price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            units=state.units,
            system_name=state.system_name,
            reason=reason,
            duration_sec=duration_sec,
            trade_context_file=trade_context_file,
            trade_id=str(getattr(state, "trade_id", "") or trade_context_payload.get("trade_id") or ""),
        ))
        self.closed_trades = self.closed_trades[-500:]
        self.log_line.emit(f"Позиция {state.inst_id} закрыта. Причина: {reason}")
        self._register_stopout(state, price, reason)

        emoji = "✅" if pnl >= 0 else "❌"
        self._notify(
            f"{emoji} Позиция закрыта\n\n"
            f"Инструмент: {state.inst_id}\n"
            f"Сторона: {state.side.upper()}\n"
            f"Цена входа: {self._fmt_price(state.avg_px)}\n"
            f"Цена выхода: {self._fmt_price(price)}\n"
            f"PnL: {pnl:.4f}\n"
            f"PnL %: {pnl_pct:.2f}%\n"
            f"Юнитов: {state.units}\n"
            f"Причина: {reason}"
        )

        if state.inst_id in self.position_state:
            del self.position_state[state.inst_id]
            self.close_retry_after.pop(state.inst_id, None)
            self._save_state()
        self._emit_snapshot_safe()

    def close_position(self, state: PositionState, price: float, reason: str, candles: Optional[List[List[float]]] = None) -> None:
        resp = self.gateway.close_position(state.inst_id, reason, auto_cancel=True)
        if resp.get("code") != "0":
            code, message = self._extract_order_error(resp)
            safe_message = (message or resp.get("msg") or str(resp)).strip()

            if code in OkxGateway.CLOSE_REQUIRES_PENDING_CANCEL_CODES:
                cancel_resp = self.gateway.cancel_pending_close_orders(state.inst_id)
                self.log_line.emit(f"{state.inst_id}: перед закрытием отменяю pending close-orders ({code}: {safe_message})")
                self.stats_logger.log(
                    "close_pending_orders_cancel",
                    inst_id=state.inst_id,
                    side=state.side,
                    reason=reason,
                    exchange_code=code,
                    exchange_message=safe_message,
                    cancel_result=cancel_resp.get("msg", ""),
                    cancel_code=cancel_resp.get("code", ""),
                )
                retry_resp = self.gateway.close_position(state.inst_id, f"{reason} | retry_after_cancel", auto_cancel=True)
                if retry_resp.get("code") == "0":
                    resp = retry_resp
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    retry_code, retry_message = self._extract_order_error(retry_resp)
                    retry_safe_message = (retry_message or retry_resp.get("msg") or str(retry_resp)).strip()
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    self.log_line.emit(f"{state.inst_id}: повторное закрытие после отмены заявок не удалось: {retry_resp}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\n\n"
                        f"Инструмент: {state.inst_id}\n"
                        f"Причина: {safe_message}\n"
                        f"Повторная попытка: {retry_safe_message}"
                    )
                    return
            elif code in OkxGateway.CLOSE_MARKET_LIMIT_ERROR_CODES:
                fallback = self.gateway.close_position_by_reduce_only(state.inst_id, state.side, state.qty)
                if fallback.get("code") == "0":
                    self.log_line.emit(f"{state.inst_id}: позиция закрыта reduce-only ордерами из-за лимита market close")
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    self.log_line.emit(f"{state.inst_id}: ошибка закрытия reduce-only: {fallback}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\n\n"
                        f"Инструмент: {state.inst_id}\n"
                        f"Причина: {safe_message}\n"
                        f"Fallback: {fallback}"
                    )
                    return
            else:
                self.close_retry_after[state.inst_id] = time.time() + 60
                self.log_line.emit(f"{state.inst_id}: ошибка закрытия: {resp}")
                self._notify(
                    f"⚠️ Ошибка закрытия позиции\n\n"
                    f"Инструмент: {state.inst_id}\n"
                    f"Причина: {safe_message}"
                )
                return

        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)

        pnl = ((price - state.avg_px) * state.qty * ct_val) if state.side == "long" else ((state.avg_px - price) * state.qty * ct_val)

        estimated_notional = max(state.avg_px * state.qty * ct_val, 0.0)
        estimated_margin = estimated_notional / max(float(self.cfg.leverage or 1), 1.0)
        if estimated_margin > 0:
            pnl_pct = (pnl / estimated_margin) * 100.0
        else:
            pnl_pct = 0.0

        self.stats_logger.log("position_closed", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason, reason_code=_classify_reason_code(reason))
        self.trade_logger.log("CLOSE", state.inst_id, state.side, state.qty, price, state.atr, state.stop_price, state.system_name, reason)
        self.position_journal_logger.log("CLOSE", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=price, stop_price=state.stop_price, qty=state.qty, units=state.units, unrealized_pnl=state.unrealized_pnl, peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0), reason=reason, note="Выход из позиции")
        duration_sec = 0
        try:
            duration_sec = max(0, int((datetime.now() - datetime.strptime(state.entry_time, "%Y-%m-%d %H:%M:%S")).total_seconds()))
        except Exception:
            duration_sec = 0
        trade_context_payload = self._build_trade_lifecycle_payload(state, price, reason, pnl, pnl_pct, duration_sec, candles=candles)
        trade_context_file = self._save_trade_context(trade_context_payload)
        self.closed_trades.append(ClosedTrade(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inst_id=state.inst_id,
            side=state.side,
            qty=state.qty,
            entry_px=state.avg_px,
            exit_px=price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            units=state.units,
            system_name=state.system_name,
            reason=reason,
            duration_sec=duration_sec,
            trade_context_file=trade_context_file,
            trade_id=str(getattr(state, "trade_id", "") or trade_context_payload.get("trade_id") or ""),
        ))
        self.closed_trades = self.closed_trades[-500:]
        self.log_line.emit(f"Позиция {state.inst_id} закрыта. Причина: {reason}")
        self._register_stopout(state, price, reason)

        emoji = "✅" if pnl >= 0 else "❌"
        self._notify(
            f"{emoji} Позиция закрыта\n\n"
            f"Инструмент: {state.inst_id}\n"
            f"Сторона: {state.side.upper()}\n"
            f"Цена входа: {self._fmt_price(state.avg_px)}\n"
            f"Цена выхода: {self._fmt_price(price)}\n"
            f"PnL: {pnl:.4f}\n"
            f"PnL %: {pnl_pct:.2f}%\n"
            f"Юнитов: {state.units}\n"
            f"Причина: {reason}"
        )

        if state.inst_id in self.position_state:
            del self.position_state[state.inst_id]
            self.close_retry_after.pop(state.inst_id, None)
            self._save_state()
        self._emit_snapshot_safe()

    def _load_json_file(self, path_value: str) -> dict:
        try:
            path = Path(str(path_value or '').strip())
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Failed to load json context %s: %s", path_value, exc)
        return {}

    def _build_trade_lifecycle_payload(self, state: PositionState, exit_price: float, reason: str, pnl: float, pnl_pct: float, duration_sec: int, candles: Optional[List[List[float]]] = None) -> dict:
        entry_payload = self._load_json_file(getattr(state, 'entry_context_file', ''))
        entry_candles = list(entry_payload.get('candles') or [])

        tf_sec = max(60, self._timeframe_seconds())
        bars_in_trade = max(1, int(max(duration_sec, tf_sec) / tf_sec) + 6)
        desired_limit = min(320, max(96, bars_in_trade + 24, (state.entry_period or 0) + 24))

        trade_candles = list(candles or [])
        if len(trade_candles) < desired_limit:
            try:
                fetched = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, desired_limit) or []
                if fetched:
                    trade_candles = fetched
            except Exception as exc:
                logging.warning("Failed to fetch lifecycle candles for %s: %s", state.inst_id, exc)

        merged = []
        by_ts = {}
        for candle in entry_candles + trade_candles:
            try:
                ts = int(candle[0])
                by_ts[ts] = [int(candle[0]), float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4]), float(candle[5]) if len(candle) > 5 else 0.0]
            except Exception:
                continue
        for ts in sorted(by_ts):
            merged.append(by_ts[ts])

        entry_time_text = str(state.entry_time or entry_payload.get('saved_at') or '')
        exit_time_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            entry_dt = datetime.strptime(entry_time_text, "%Y-%m-%d %H:%M:%S")
            entry_ts_ms = int(entry_dt.timestamp() * 1000)
        except Exception:
            entry_ts_ms = int(merged[0][0]) if merged else 0

        try:
            exit_dt = datetime.strptime(exit_time_text, "%Y-%m-%d %H:%M:%S")
            exit_ts_ms = int(exit_dt.timestamp() * 1000)
        except Exception:
            exit_ts_ms = int(merged[-1][0]) if merged else 0

        if merged:
            before = [c for c in merged if int(c[0]) <= entry_ts_ms]
            after = [c for c in merged if int(c[0]) >= entry_ts_ms]
            merged = (before[-40:] if before else merged[:40]) + [c for c in after if c not in (before[-40:] if before else [])]
            merged = merged[-260:]

        def nearest_index(target_ts: int) -> int:
            if not merged:
                return -1
            best_idx = 0
            best_dist = abs(int(merged[0][0]) - target_ts)
            for idx, candle in enumerate(merged):
                dist = abs(int(candle[0]) - target_ts)
                if dist < best_dist:
                    best_idx = idx
                    best_dist = dist
            return best_idx

        markers = []
        entry_idx = nearest_index(entry_ts_ms)
        if entry_idx >= 0:
            markers.append({
                'kind': 'entry',
                'label': 'E',
                'index': entry_idx,
                'price': float(state.avg_px or entry_payload.get('entry_price') or 0.0),
                'time': entry_time_text,
            })

        add_step = float(entry_payload.get('add_unit_every_atr', self.cfg.add_unit_every_atr) or self.cfg.add_unit_every_atr)
        base_entry = float(entry_payload.get('entry_price') or state.avg_px or 0.0)
        entry_atr = float(entry_payload.get('atr') or state.atr or 0.0)
        if state.units > 1 and entry_atr > 0 and add_step > 0:
            for unit_no in range(2, int(state.units) + 1):
                add_price = base_entry + entry_atr * add_step * (unit_no - 1) if state.side == 'long' else base_entry - entry_atr * add_step * (unit_no - 1)
                found_idx = -1
                for idx in range(max(0, entry_idx), len(merged)):
                    hi = float(merged[idx][2])
                    lo = float(merged[idx][3])
                    if lo <= add_price <= hi:
                        found_idx = idx
                        break
                if found_idx >= 0:
                    markers.append({
                        'kind': f'add_{unit_no}',
                        'label': f'A{unit_no}',
                        'index': found_idx,
                        'price': add_price,
                        'time': datetime.fromtimestamp(int(merged[found_idx][0]) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    })

        exit_idx = nearest_index(exit_ts_ms)
        if exit_idx >= 0:
            markers.append({
                'kind': 'exit',
                'label': 'X',
                'index': exit_idx,
                'price': float(exit_price),
                'time': exit_time_text,
            })

        channel_exit_level = 0.0
        try:
            if merged and int(state.exit_period or 0) > 0:
                exit_window = merged[max(0, exit_idx - int(state.exit_period) + 1):exit_idx + 1] if exit_idx >= 0 else merged[-int(state.exit_period):]
                if exit_window:
                    channel_exit_level = min(float(c[3]) for c in exit_window) if state.side == 'long' else max(float(c[2]) for c in exit_window)
        except Exception:
            channel_exit_level = 0.0

        return {
            'version': APP_VERSION,
            'saved_at': exit_time_text,
            'trade_id': str(getattr(state, 'trade_id', '') or entry_payload.get('trade_id') or _stable_trade_id(state.inst_id, state.side, entry_time_text)),
            'inst_id': state.inst_id,
            'side': state.side,
            'timeframe': self.cfg.timeframe,
            'system_name': state.system_name,
            'entry_price': float(base_entry or state.avg_px or 0.0),
            'exit_price': float(exit_price),
            'entry_atr': float(entry_atr or state.atr or 0.0),
            'start_stop_price': float(entry_payload.get('stop_price') or 0.0),
            'final_stop_price': float(state.stop_price or 0.0),
            'channel_exit_level': float(channel_exit_level or 0.0),
            'initial_stop_price': float(getattr(state, 'initial_stop_price', 0.0) or entry_payload.get('stop_price') or 0.0),
            'peak_price': float(getattr(state, 'peak_price', 0.0) or 0.0),
            'trough_price': float(getattr(state, 'trough_price', 0.0) or 0.0),
            'peak_unrealized_pnl': float(getattr(state, 'peak_unrealized_pnl', 0.0) or 0.0),
            'qty': float(state.qty or 0.0),
            'units': int(state.units or 1),
            'pnl': float(pnl),
            'pnl_pct': float(pnl_pct),
            'reason': reason,
            'duration_sec': int(duration_sec or 0),
            'entry_time': entry_time_text,
            'exit_time': exit_time_text,
            'entry_context_file': str(getattr(state, 'entry_context_file', '') or ''),
            'planned_risk_pct': float(getattr(state, 'planned_risk_pct', 0.0) or entry_payload.get('planned_risk_pct') or 0.0),
            'risk_amount_usdt': float(getattr(state, 'risk_amount_usdt', 0.0) or entry_payload.get('risk_amount_usdt') or 0.0),
            'risk_per_contract': float(getattr(state, 'risk_per_contract', 0.0) or entry_payload.get('risk_per_contract') or 0.0),
            'position_notional_usdt': float(getattr(state, 'position_notional_usdt', 0.0) or entry_payload.get('position_notional_usdt') or 0.0),
            'trailing_activated_at': str(getattr(state, 'trailing_activated_at', '') or ''),
            'breakeven_activated_at': str(getattr(state, 'breakeven_activated_at', '') or ''),
            'breakout_distance_atr': float(entry_payload.get('breakout_distance_atr') or 0.0),
            'channel_atr_ratio': float(entry_payload.get('channel_atr_ratio') or 0.0),
            'atr_pct_at_entry': float(entry_payload.get('atr_pct_at_entry') or 0.0),
            'body_atr_at_entry': float(entry_payload.get('body_atr_at_entry') or 0.0),
            'body_to_range_ratio_at_entry': float(entry_payload.get('body_to_range_ratio_at_entry') or 0.0),
            'close_near_extreme_ratio_at_entry': float(entry_payload.get('close_near_extreme_ratio_at_entry') or 0.0),
            'candles': merged,
            'markers': markers,
        }

    def _save_trade_context(self, payload: dict) -> str:
        try:
            safe_inst = str(payload.get('inst_id', 'UNKNOWN')).replace('/', '_').replace(':', '_')
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = TRADE_CONTEXT_DIR / f"{ts}_{safe_inst}_{payload.get('side', 'na')}_trade.json"
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return str(file_path)
        except Exception as exc:
            logging.warning("Failed to save trade context for %s: %s", payload.get('inst_id'), exc)
            return ""

    def emit_snapshot(self) -> None:
        with self.balance_lock:
            latest_balance = dict(self.latest_balance_snapshot)
            balance_history_copy = list(self.balance_history[-2000:])

        if latest_balance:
            balance_total = float(latest_balance.get("balance_total", 0.0) or 0.0)
            balance_available = float(latest_balance.get("balance_available", 0.0) or 0.0)
            balance_used = float(latest_balance.get("balance_used", 0.0) or 0.0)
        else:
            bal = self.gateway.get_account_balance()
            self._append_balance_point_from_account(bal)
            with self.balance_lock:
                latest_balance = dict(self.latest_balance_snapshot)
                balance_history_copy = list(self.balance_history[-2000:])
            balance_total = float(latest_balance.get("balance_total", 0.0) or 0.0)
            balance_available = float(latest_balance.get("balance_available", 0.0) or 0.0)
            balance_used = float(latest_balance.get("balance_used", 0.0) or 0.0)


        open_positions = []
        for state in self.position_state.values():
            row = asdict(state)
            avg_px = float(state.avg_px or 0.0)
            last_px = float(state.last_px or 0.0)
            atr = float(state.atr or 0.0)
            margin = float(state.margin or 0.0)
            upl = float(state.unrealized_pnl or 0.0)

            if margin > 0:
                pnl_pct = (upl / margin) * 100.0
            else:
                pnl_pct = 0.0

            if last_px > 0:
                stop_distance_pct = ((last_px - state.stop_price) / last_px * 100.0) if state.side == "long" else ((state.stop_price - last_px) / last_px * 100.0)
                pyramid_distance_pct = ((state.next_pyramid_price - last_px) / last_px * 100.0) if state.side == "long" else ((last_px - state.next_pyramid_price) / last_px * 100.0)
                atr_pct = (atr / last_px * 100.0) if atr > 0 else 0.0
            else:
                stop_distance_pct = 0.0
                pyramid_distance_pct = 0.0
                atr_pct = 0.0

            row["pnl_pct"] = pnl_pct
            row["atr_pct"] = atr_pct
            row["stop_distance_pct"] = stop_distance_pct
            row["pyramid_distance_pct"] = pyramid_distance_pct
            row["trend_strength_atr"] = (abs(last_px - avg_px) / atr) if atr > 0 else 0.0
            row["added_units"] = max(0, int(state.units) - 1)
            open_positions.append(row)

        visible_open_positions = [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))]
        visible_closed_trades = [x for x in self.closed_trades if not is_hidden_instrument(x.inst_id)]

        open_pnl = sum(float(x.get("unrealized_pnl", 0.0)) for x in visible_open_positions)
        longs = sum(1 for x in visible_open_positions if x.get("side") == "long")
        shorts = sum(1 for x in visible_open_positions if x.get("side") == "short")
        avg_pnl_pct = sum(float(x.get("pnl_pct", 0.0)) for x in visible_open_positions) / len(visible_open_positions) if visible_open_positions else 0.0
        best_open = max((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        worst_open = min((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        realized_pnl = sum(x.pnl for x in visible_closed_trades)
        wins = sum(1 for x in visible_closed_trades if x.pnl > 0)
        losses = sum(1 for x in visible_closed_trades if x.pnl < 0)
        winrate = wins / len(visible_closed_trades) * 100.0 if visible_closed_trades else 0.0

        now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Изменение баланса за день и за 7 дней
        day_change_pct = 0.0
        week_change_pct = 0.0

        history_with_dt = []
        for item in balance_history_copy:
            try:
                dt = datetime.strptime(str(item.get("time", "")), "%Y-%m-%d %H:%M:%S")
                val = float(item.get("balance_total", 0.0))
                history_with_dt.append((dt, val))
            except Exception:
                continue

        if history_with_dt:
            history_with_dt.sort(key=lambda x: x[0])
            current_balance_for_change = history_with_dt[-1][1]

            day_cutoff = datetime.now() - timedelta(days=1)
            week_cutoff = datetime.now() - timedelta(days=7)

            day_candidates = [v for dt, v in history_with_dt if dt <= day_cutoff]
            week_candidates = [v for dt, v in history_with_dt if dt <= week_cutoff]

            if day_candidates and abs(day_candidates[-1]) > 1e-12:
                day_change_pct = ((current_balance_for_change - day_candidates[-1]) / day_candidates[-1]) * 100.0

            if week_candidates and abs(week_candidates[-1]) > 1e-12:
                week_change_pct = ((current_balance_for_change - week_candidates[-1]) / week_candidates[-1]) * 100.0

        # Использовано риска
        used_risk_pct = sum(
            max(0.0, float(pos.get("stop_distance_pct", 0.0)))
            for pos in visible_open_positions
        )
        max_risk_budget_pct = max(
            0.0,
            len(visible_open_positions) * float(self.cfg.risk_per_trade_pct or 0.0)
        )

        # Сделки сегодня / средняя длительность
        today_str = datetime.now().strftime("%Y-%m-%d")
        trades_today = 0
        durations_today = []
        for trade in visible_closed_trades:
            try:
                if str(trade.time).startswith(today_str):
                    trades_today += 1
                    durations_today.append(int(trade.duration_sec or 0))
            except Exception:
                continue
        avg_duration_sec = int(sum(durations_today) / len(durations_today)) if durations_today else 0

        turtle_regime = self._compute_turtle_regime()
        trade_ready_metrics = self._collect_trade_ready_metrics()
        self.last_trade_ready_metrics = dict(trade_ready_metrics)

        payload = {
            "timestamp": format_time_string(now_full),
            "engine": {
                "last_cycle_started": format_clock(self.last_scan_started_at),
                "last_cycle_finished": format_clock(self.last_scan_finished_at),
                "last_snapshot_emitted": format_time_string(now_full),
                "last_cycle_duration_sec": round(max(0.0, (self.last_scan_finished_at or time.time()) - (self.last_scan_started_at or time.time())), 3) if self.last_scan_started_at else 0.0,
                "scan_interval_sec": self.cfg.scan_interval_sec,
                "position_check_interval_sec": self.cfg.position_check_interval_sec,
                "snapshot_interval_sec": self.cfg.snapshot_interval_sec,
            },
            "balance_total": balance_total,
            "balance_available": balance_available,
            "balance_used": balance_used,
            "open_positions": [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))],
            "closed_trades": [asdict(x) for x in reversed([x for x in visible_closed_trades[-500:] if not is_hidden_instrument(x.inst_id)])],
            "analytics": {
                "trade_ready_count": int(trade_ready_metrics.get("trade_ready_count", 0) or 0),
                "available_after_bans_count": int(trade_ready_metrics.get("available_after_bans_count", 0) or 0),
                "scan_universe_total": int(trade_ready_metrics.get("scan_universe_total", 0) or 0),
                "blocked_total": int(trade_ready_metrics.get("hard_blocked_unique_count", 0) or 0),
                "open_pnl": open_pnl,
                "avg_open_pnl_pct": avg_pnl_pct,
                "best_open_pnl_pct": best_open,
                "worst_open_pnl_pct": worst_open,
                "long_count": longs,
                "short_count": shorts,
                "closed_count": len(visible_closed_trades),
                "realized_pnl": realized_pnl,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
                "day_change_pct": day_change_pct,
                "week_change_pct": week_change_pct,
                "used_risk_pct": used_risk_pct,
                "max_risk_budget_pct": max_risk_budget_pct,
                "trades_today": trades_today,
                "avg_duration_sec": avg_duration_sec,
                "turtle_regime_label": turtle_regime.get("label", "—"),
                "turtle_regime_score": turtle_regime.get("score", 0),
                "turtle_regime_channel_atr": turtle_regime.get("channel_atr_ratio", 0.0),
                "turtle_regime_efficiency": turtle_regime.get("efficiency_ratio", 0.0),
                "turtle_regime_atr_pct": turtle_regime.get("atr_pct", 0.0),
                "turtle_regime_instrument": turtle_regime.get("instrument", "—"),
            },
            "balance_history": balance_history_copy,
            "settings": {
                "account": "Основной" if self.cfg.flag == "0" else "Демо",
                "timeframe": self.cfg.timeframe,
                "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
                "risk_per_trade_pct": self.cfg.risk_per_trade_pct,
            },
            "market_data_cache": self.market_data_cache.snapshot_stats(),
            "signal_funnel": dict(self.last_signal_funnel or {}),
            "trade_ready_metrics": trade_ready_metrics,
        }
        self.last_snapshot_emitted_at = time.time()
        self.stats_logger.log(
            "snapshot",
            balance_total=balance_total,
            balance_available=balance_available,
            balance_used=balance_used,
            open_positions=len(visible_open_positions),
            closed_trades=len(visible_closed_trades),
            open_pnl=open_pnl,
            realized_pnl=realized_pnl,
            winrate=winrate,
            timeframe=self.cfg.timeframe,
            market_data_fetch_count=self.market_data_cache.fetch_count,
            market_data_errors=self.market_data_cache.error_count,
            trade_ready_count=int(trade_ready_metrics.get("trade_ready_count", 0) or 0),
            available_after_bans_count=int(trade_ready_metrics.get("available_after_bans_count", 0) or 0),
            scan_universe_total=int(trade_ready_metrics.get("scan_universe_total", 0) or 0),
        )
        self.snapshot.emit(payload)

    @staticmethod
    def floor_to_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        try:
            value_dec = Decimal(str(value))
            step_dec = Decimal(str(step))
            units = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
            return float(units * step_dec)
        except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
            return 0.0


class PositionTableModel(QAbstractTableModel):
    HEADERS = [
        "Инструмент",
        "Сторона",
        "Qty",
        "Последняя цена",
        "PnL",
        "PnL %",
        "ATR",
        "ATR %",
        "Стоп",
        "До стопа %",
        "След. добор",
        "До добора %",
        "Сила тренда",
        "Юнитов",
        "Система",
        "Вход",
    ]

    def __init__(self):
        super().__init__()
        self.rows: List[dict] = []

    def update_rows(self, rows: List[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        side_text = "🟢 LONG" if row.get("side") == "long" else "🔴 SHORT"
        values = [
            row.get("inst_id"),
            side_text,
            f"{row.get('qty', 0):.6f}",
            f"{row.get('last_px', 0):.6f}",
            f"{row.get('unrealized_pnl', 0):.4f}",
            f"{row.get('pnl_pct', 0):.2f}%",
            f"{row.get('atr', 0):.6f}",
            f"{row.get('atr_pct', 0):.2f}%",
            f"{row.get('stop_price', 0):.6f}",
            f"{row.get('stop_distance_pct', 0):.2f}%",
            f"{row.get('next_pyramid_price', 0):.6f}",
            f"{row.get('pyramid_distance_pct', 0):.2f}%",
            f"{row.get('trend_strength_atr', 0):.2f} ATR",
            str(int(row.get("units", 1))),
            row.get("system_name"),
            format_time_string(row.get("entry_time")),
        ]
        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]
        pnl_pct = float(row.get("pnl_pct", 0.0))
        if role == Qt.ItemDataRole.BackgroundRole:
            if pnl_pct > 0:
                if pnl_pct >= 10:
                    return QColor(200, 245, 210)
                if pnl_pct >= 5:
                    return QColor(220, 250, 228)
                return QColor(235, 255, 240)
            if pnl_pct < 0:
                if pnl_pct <= -10:
                    return QColor(248, 206, 206)
                if pnl_pct <= -5:
                    return QColor(252, 220, 220)
                return QColor(255, 236, 236)
            return QColor(255, 255, 255)
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (4, 5, 9, 11, 12):
                return gradient_pnl_color(
                    pnl_pct if index.column() in (4, 5, 12)
                    else -abs(float(row.get('stop_distance_pct' if index.column() == 9 else 'pyramid_distance_pct', 0.0)))
                )
            if index.column() == 1:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            return QColor(20, 20, 20)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() >= 2:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

class ClosedTradesTableModel(QAbstractTableModel):
    HEADERS = [
        "Время",
        "Инструмент",
        "Сторона",
        "Qty",
        "Вход",
        "Выход",
        "PnL",
        "PnL %",
        "Длительность",
        "Юнитов",
        "Система",
        "Причина",
    ]

    def __init__(self):
        super().__init__()
        self.rows: List[dict] = []

    def update_rows(self, rows: List[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        side_text = "🟢 LONG" if row.get("side") == "long" else "🔴 SHORT"
        values = [
            row.get("time"),
            row.get("inst_id"),
            side_text,
            f"{row.get('qty', 0):.6f}",
            f"{row.get('entry_px', 0):.6f}",
            f"{row.get('exit_px', 0):.6f}",
            f"{row.get('pnl', 0):.4f}",
            f"{row.get('pnl_pct', 0):.2f}%",
            format_duration(row.get("duration_sec", 0)),
            str(int(row.get("units", 1))),
            row.get("system_name"),
            row.get("reason"),
        ]
        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]
        pnl_pct = float(row.get("pnl_pct", 0.0))
        if role == Qt.ItemDataRole.BackgroundRole:
            if pnl_pct > 0:
                return QColor(232, 252, 236)
            if pnl_pct < 0:
                return QColor(255, 235, 235)
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (6, 7):
                return gradient_pnl_color(pnl_pct)
            if index.column() == 2:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            return QColor(20, 20, 20)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (3,4,5,6,7,8,9):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

class BalanceChartWidget(QWidget):
    STEP_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1H": 3600,
        "1D": 86400,
    }

    def __init__(self):
        super().__init__()
        self.points: List[dict] = []
        self.markers: List[dict] = []
        self.step_code = "1m"
        self.dark_theme = False
        self.setMinimumHeight(200)

    def update_points(self, points: List[dict], step_code: Optional[str] = None, markers: Optional[List[dict]] = None) -> None:
        self.points = points or []
        if markers is not None:
            self.markers = markers or []
        if step_code:
            self.step_code = step_code
        self.update()

    def set_step(self, step_code: str) -> None:
        self.step_code = step_code or "1m"
        self.update()

    def set_dark_theme(self, is_dark: bool) -> None:
        self.dark_theme = bool(is_dark)
        self.update()

    def _parse_dt(self, value: object) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                if fmt == "%H:%M:%S":
                    now = datetime.now()
                    dt = dt.replace(year=now.year, month=now.month, day=now.day)
                return dt
            except ValueError:
                continue
        return None

    def _bucket_points(self) -> List[dict]:
        if not self.points:
            return []
        step_sec = self.STEP_SECONDS.get(self.step_code, 60)
        parsed: List[Tuple[datetime, dict]] = []
        for point in self.points:
            dt = self._parse_dt(point.get("time"))
            if dt is None:
                continue
            parsed.append((dt, point))
        if not parsed:
            return []
        parsed.sort(key=lambda item: item[0])
        buckets: List[dict] = []
        bucket_start = None
        bucket_values: List[float] = []
        last_dt: Optional[datetime] = None
        for dt, point in parsed:
            ts = int(dt.timestamp())
            aligned_ts = ts - (ts % step_sec)
            aligned = datetime.fromtimestamp(aligned_ts)
            if bucket_start is None:
                bucket_start = aligned
            if aligned != bucket_start:
                if bucket_values:
                    buckets.append({
                        "time": bucket_start.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d"),
                        "value": bucket_values[-1],
                        "open": bucket_values[0],
                        "close": bucket_values[-1],
                        "high": max(bucket_values),
                        "low": min(bucket_values),
                        "samples": len(bucket_values),
                    })
                bucket_start = aligned
                bucket_values = []
            bucket_values.append(float(point.get("balance_total", 0.0)))
            last_dt = dt
        if bucket_values and bucket_start is not None:
            buckets.append({
                "time": bucket_start.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d"),
                "value": bucket_values[-1],
                "open": bucket_values[0],
                "close": bucket_values[-1],
                "high": max(bucket_values),
                "low": min(bucket_values),
                "samples": len(bucket_values),
            })
        if len(buckets) == 1 and last_dt is not None:
            buckets[0]["time"] = last_dt.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d")
        return buckets[-30:]

    def _display_equity_slots(self) -> Tuple[List[float], int, float, float, float, str]:
        bucketed = self._bucket_points()
        actual_count = len(bucketed)
        if actual_count <= 0:
            return [0.0] * 30, 0, 0.0, 0.0, 0.0, "ожидание"
        raw_values = [float(point.get("value", 0.0)) for point in bucketed]
        padded = ([raw_values[0]] * max(0, 30 - len(raw_values))) + raw_values
        padded = padded[-30:]
        current_balance = raw_values[-1] if raw_values else 0.0
        session_change = (raw_values[-1] - raw_values[0]) if len(raw_values) >= 2 else 0.0
        session_change_pct = (session_change / raw_values[0] * 100.0) if raw_values and abs(raw_values[0]) > 1e-12 else 0.0
        last_label = str(bucketed[-1].get("time", "—"))
        return padded, min(actual_count, 30), current_balance, session_change, session_change_pct, last_label

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(8, 8, -8, -8)

        bg_color = QColor(6, 12, 24) if self.dark_theme else QColor(255, 255, 255)
        border_color = QColor(33, 78, 142) if self.dark_theme else QColor(225, 228, 235)
        muted_color = QColor(124, 132, 145) if self.dark_theme else QColor(128, 128, 128)
        neon_green = QColor(0, 255, 168)
        pos_color = neon_green
        neg_color = QColor(239, 68, 68)
        grid_color = QColor(38, 45, 56) if self.dark_theme else QColor(234, 236, 240)

        if self.dark_theme:
            bg_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            bg_grad.setColorAt(0.0, QColor(5, 15, 30))
            bg_grad.setColorAt(1.0, QColor(12, 9, 28))
            painter.fillRect(outer, bg_grad)
            for width, alpha in ((8, 18), (4, 30)):
                painter.setPen(QPen(QColor(0, 224, 255, alpha), width))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, 16, 16)
        else:
            painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 14, 14)

        bucketed = self._bucket_points()
        equity_values, actual_count, current_balance, session_change, session_change_pct, last_label = self._display_equity_slots()
        visible_offset = max(0, len(equity_values) - len(bucketed))

        # OKX-like header
        header_rect = rect.adjusted(14, 10, -14, -rect.height() + 46)
        pnl_color = pos_color if session_change >= 0 else neg_color
        painter.setPen(pnl_color)
        header_font = painter.font()
        header_font.setPointSize(14)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.drawText(header_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_balance:.2f} USDT")

        sub_rect = rect.adjusted(14, 30, -14, -rect.height() + 60)
        sub_font = painter.font()
        sub_font.setPointSize(9)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        tail = last_label if actual_count > 0 else "ожидание данных"
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"Сессия {session_change:+.2f} USDT ({session_change_pct:+.2f}%)  ·  {tail}")

        plot = rect.adjusted(14, 64, -14, -18)

        min_val = min(equity_values)
        max_val = max(equity_values)
        span = max_val - min_val
        pad = max(span * 0.18, 0.5)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        baseline_value = equity_values[0] if equity_values else 0.0
        zero_y = value_to_y(baseline_value)

        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
        y_marks = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = int(plot.top() + plot.height() * frac)
            value = max_plot - (max_plot - min_plot) * frac
            y_marks.append((y, value))
            painter.drawLine(plot.left(), y, plot.right(), y)

        painter.setPen(muted_color)
        for y, value in y_marks:
            painter.drawText(plot.right() - 64, y - 2, f"{value:.2f}")

        painter.setPen(QPen(QColor(110, 118, 132), 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot.left(), zero_y, plot.right(), zero_y)

        step_x = plot.width() / max(1, (len(equity_values) - 1))
        x_positions = [plot.left() + i * step_x for i in range(len(equity_values))]
        line_points = [(int(x), value_to_y(val)) for x, val in zip(x_positions, equity_values)]
        line_color = neon_green
        area_color = QColor(line_color.red(), line_color.green(), line_color.blue(), 70)

        area = QPolygon()
        area.append(QPoint(line_points[0][0], zero_y))
        for x, y in line_points:
            area.append(QPoint(x, y))
        area.append(QPoint(line_points[-1][0], zero_y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(area_color)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(line_color, 2))
        for i in range(1, len(line_points)):
            painter.drawLine(line_points[i - 1][0], line_points[i - 1][1], line_points[i][0], line_points[i][1])

        last_x, last_y = line_points[-1]
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(last_x, last_y, 14)
        glow.setColorAt(0.0, QColor(0, 255, 168, 180))
        glow.setColorAt(1.0, QColor(0, 255, 168, 0))
        painter.setBrush(glow)
        painter.drawEllipse(last_x - 14, last_y - 14, 28, 28)
        painter.setBrush(line_color)
        painter.drawEllipse(last_x - 4, last_y - 4, 8, 8)

        # Маркеры закрытых сделок
        marker_index = {str(point.get("time")): visible_offset + i for i, point in enumerate(bucketed)}
        for marker in self.markers[-200:]:
            idx = marker_index.get(str(marker.get("bucket_time")))
            if idx is None or idx < 0 or idx >= len(line_points):
                continue
            x, y = line_points[idx]
            pnl = float(marker.get("pnl", 0.0))
            color = pos_color if pnl >= 0 else neg_color
            painter.setBrush(color)
            painter.drawEllipse(x - 2, y - 9, 4, 4)

        # Нижние подписи X
        painter.setPen(muted_color)
        if bucketed:
            raw_indices = [0, len(bucketed) // 2, len(bucketed) - 1]
            show_indices = []
            for raw_idx in raw_indices:
                shifted_idx = visible_offset + raw_idx
                if 0 <= shifted_idx < len(line_points):
                    show_indices.append((shifted_idx, raw_idx))
            for shifted_idx, raw_idx in show_indices:
                x = line_points[shifted_idx][0]
                label = str(bucketed[raw_idx].get("time", "—"))
                painter.drawText(x - 22, plot.bottom() + 16, label)


class WorkerThread(QThread):
    def __init__(self, engine: TurtleEngine):
        super().__init__()
        self.engine = engine

    def run(self) -> None:
        self.engine.start()



class LaunchConfigWidget(QWidget):
    start_requested = pyqtSignal(BotConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_trade_mode = "auto"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        self.account_combo = QComboBox()
        self.account_combo.addItem("Демо", "1")
        self.account_combo.addItem("Основной", "0")
        form.addRow("Аккаунт:", self.account_combo)

        self.timeframe_combo = QComboBox()
        for tf in ("1m", "5m", "15m", "30m", "1H", "4H"):
            self.timeframe_combo.addItem(tf, tf)
        idx = max(0, self.timeframe_combo.findData("5m"))
        self.timeframe_combo.setCurrentIndex(idx)
        form.addRow("Таймфрейм:", self.timeframe_combo)

        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(1)
        self.leverage_spin.hide()

        layout.addLayout(form)

    def set_trade_mode(self, mode: str) -> None:
        self.selected_trade_mode = "manual" if str(mode).lower() == "manual" else "auto"

    def build_config(self) -> BotConfig:
        load_dotenv()
        api_key = os.getenv("OKX_API_KEY", "").strip()
        secret_key = os.getenv("OKX_SECRET_KEY", "").strip()
        passphrase = os.getenv("OKX_PASSPHRASE", "").strip()
        if not api_key or not secret_key or not passphrase:
            raise ValueError("Не найдены OKX_API_KEY / OKX_SECRET_KEY / OKX_PASSPHRASE в .env")
        cfg = BotConfig(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            flag=str(self.account_combo.currentData() or "1"),
            timeframe=str(self.timeframe_combo.currentData() or "5m"),
            leverage=1,
            trade_mode=self.selected_trade_mode,
        )
        self.start_requested.emit(cfg)
        return cfg


class NeonRadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self._angle = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(35)

    def _animate(self):
        self._angle = (self._angle + 2.5) % 360.0
        self._pulse = (self._pulse + 0.11) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        center = QPointF(rect.center())
        radius = min(rect.width(), rect.height()) / 2
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        pulse = (math.sin(self._pulse) + 1.0) * 0.5
        for i, alpha in enumerate((120, 92, 66, 40)):
            r = radius * (1.0 - i * 0.18)
            grad = QRadialGradient(center, r)
            grad.setColorAt(0.0, QColor(70, 255, 231, alpha // 2))
            grad.setColorAt(0.55, QColor(54, 110, 255, alpha))
            grad.setColorAt(1.0, QColor(255, 67, 214, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, int(r), int(r))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for frac, color, w in ((1.00, QColor(65, 185, 255, 130), 2), (0.78, QColor(0, 255, 191, 120), 1), (0.56, QColor(255, 67, 214, 120), 1), (0.34, QColor(105, 245, 255, 120), 1)):
            r = radius * frac
            painter.setPen(QPen(color, w))
            painter.drawEllipse(center, int(r), int(r))

        painter.setPen(QPen(QColor(77, 170, 255, 70), 1))
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x2 = center.x() + math.cos(rad) * radius
            y2 = center.y() + math.sin(rad) * radius
            painter.drawLine(center, QPointF(x2, y2))

        sweep_angle = math.radians(self._angle)
        sweep = QPolygon([
            QPoint(int(center.x()), int(center.y())),
            QPoint(int(center.x() + math.cos(sweep_angle - 0.20) * radius), int(center.y() + math.sin(sweep_angle - 0.20) * radius)),
            QPoint(int(center.x() + math.cos(sweep_angle + 0.20) * radius), int(center.y() + math.sin(sweep_angle + 0.20) * radius)),
        ])
        sweep_grad = QRadialGradient(center, radius)
        sweep_grad.setColorAt(0.0, QColor(0, 255, 191, int(48 + 30 * pulse)))
        sweep_grad.setColorAt(1.0, QColor(0, 255, 191, 0))
        painter.setBrush(QBrush(sweep_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(sweep)

        painter.setPen(QPen(QColor(19, 255, 175, 170), 2))
        dynamic_angles = (
            (26 + self._angle * 0.35, 0.88),
            (141 + self._angle * 0.22, 0.62),
            (224 + self._angle * 0.18, 0.48),
        )
        for angle, frac in dynamic_angles:
            rad = math.radians(angle % 360.0)
            x2 = center.x() + math.cos(rad) * radius * frac
            y2 = center.y() + math.sin(rad) * radius * frac
            painter.drawLine(center, QPointF(x2, y2))
            painter.setBrush(QColor(19, 255, 175, 220))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(int(x2), int(y2)), 5, 5)
            painter.setPen(QPen(QColor(19, 255, 175, 170), 2))

        painter.setBrush(QColor(255, 67, 214, 190))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 7, 7)


class NeonGlyphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(150, 150)
        self._angle = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)

    def _animate(self):
        self._angle = (self._angle + 1.8) % 360.0
        self._pulse = (self._pulse + 0.12) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(8, 8, -8, -8)
        center = QPointF(outer.center())
        radius = min(outer.width(), outer.height()) / 2
        pulse = (math.sin(self._pulse) + 1.0) * 0.5

        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, QColor(0, 231, 255, int(65 + pulse * 24)))
        grad.setColorAt(0.45, QColor(23, 96, 255, 108))
        grad.setColorAt(0.78, QColor(255, 67, 214, 48))
        grad.setColorAt(1.0, QColor(255, 67, 214, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(outer, 28, 28)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(76, 227, 255, 190), 2))
        painter.drawEllipse(center, int(radius * 0.74), int(radius * 0.74))
        painter.setPen(QPen(QColor(255, 67, 214, 150), 2))
        painter.drawEllipse(center, int(radius * 0.52), int(radius * 0.52))

        painter.save()
        painter.translate(center)
        painter.rotate(self._angle)
        painter.setPen(QPen(QColor(88, 157, 255, 150), 1))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = math.cos(rad) * radius * 0.20
            y1 = math.sin(rad) * radius * 0.20
            x2 = math.cos(rad) * radius * 0.88
            y2 = math.sin(rad) * radius * 0.88
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

        shell = QPainterPath()
        shell.addEllipse(QPointF(center.x(), center.y()+radius*0.02), radius*0.32, radius*0.24)
        painter.setPen(QPen(QColor(0, 242, 255, 220), 2))
        painter.drawPath(shell)

        painter.setPen(QPen(QColor(0, 242, 255, 210), 2))
        painter.drawArc(int(center.x()-radius*0.22), int(center.y()-radius*0.10), int(radius*0.44), int(radius*0.32), 30*16, 120*16)
        painter.drawArc(int(center.x()-radius*0.18), int(center.y()-radius*0.02), int(radius*0.36), int(radius*0.22), 210*16, 120*16)
        painter.drawArc(int(center.x()-radius*0.14), int(center.y()-radius*0.11), int(radius*0.28), int(radius*0.20), 330*16, 120*16)

        painter.setPen(QPen(QColor(255, 67, 214, 190), 2))
        head = QPainterPath()
        head.addEllipse(QPointF(center.x(), center.y()-radius*0.30), radius*0.11, radius*0.08)
        painter.drawPath(head)
        painter.drawLine(QPointF(center.x(), center.y()-radius*0.23), QPointF(center.x(), center.y()-radius*0.08))
        for dx,dy in ((-0.23,-0.02),(0.23,-0.02),(-0.18,0.22),(0.18,0.22)):
            painter.drawLine(QPointF(center.x()+radius*(dx*0.6), center.y()+radius*(dy*0.6)), QPointF(center.x()+radius*dx, center.y()+radius*dy))

        painter.setBrush(QColor(0, 242, 255, int(160 + pulse * 50)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 8, 8)



class AnalysisExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Сдать анализы')
        self.setModal(True)
        self.setMinimumSize(420, 260)
        self.selected_mode = ''
        self.setStyleSheet(
            "QDialog { background:#07111f; color:#e6ecff; }"
            "QLabel#title { color:#8cf6ff; font-size:18px; font-weight:900; }"
            "QLabel#subtitle { color:#a9c6e8; font-size:11px; }"
            "QPushButton.modeBtn { text-align:left; padding:14px 16px; border-radius:14px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:800; }"
            "QPushButton.modeBtn:hover { border:1px solid #67e8f9; background:#13213a; }"
            "QPushButton.secondary { padding:8px 12px; border-radius:12px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:700; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        lbl_title = QLabel('Сдать анализы')
        lbl_title.setObjectName('title')
        layout.addWidget(lbl_title)
        lbl_sub = QLabel('Экспорт данных текущего запуска бота для анализа')
        lbl_sub.setObjectName('subtitle')
        layout.addWidget(lbl_sub)
        buttons = [
            ('quick', 'Быстрый отчёт', 'Короткая сводка по текущему запуску'),
            ('full', 'Глубокий разбор', 'Полный диагностический экспорт одним архивом'),
            ('hourly', 'Ночной разбор (по часам)', 'Полный экспорт с разбивкой по 1 часу'),
        ]
        for mode, title, hint in buttons:
            btn = QPushButton(f'{title}\n{hint}')
            btn.setProperty('class', 'modeBtn')
            btn.setProperty('className', 'modeBtn')
            btn.setObjectName('modeBtn')
            btn.setMinimumHeight(54)
            btn.clicked.connect(lambda _=False, m=mode: self._select(m))
            btn.setStyleSheet('text-align:left; padding:14px 16px; border-radius:14px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:800;')
            layout.addWidget(btn)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_open = QPushButton('Открыть папку экспорта')
        self.btn_open.setProperty('class', 'secondary')
        self.btn_close = QPushButton('Закрыть')
        self.btn_close.setProperty('class', 'secondary')
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_open)
        bottom.addWidget(self.btn_close)
        layout.addStretch(1)
        layout.addLayout(bottom)

    def _select(self, mode: str):
        self.selected_mode = mode
        self.accept()

class MainWindow(QMainWindow):

    start_requested = pyqtSignal(BotConfig)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — Cyberpunk Quant Trading Terminal Reload UI")
        self.resize(1920, 1080)
        self.setMinimumSize(1600, 900)

        self.engine = None
        self.worker = None
        self.current_cfg = None
        self.latest_snapshot = None
        self.table_model = PositionTableModel()
        self.closed_table_model = ClosedTradesTableModel()
        self._bot_running = False
        self._bot_started_ts = None
        self._snapshot_refresh_interval_sec = 2
        self._snapshot_countdown_sec = 0
        self._manual_dialog_open = False
        self._pending_manual_signal = None
        self._telegram_screenshot_timer = None
        self._telegram_screenshot_interval_ms = 15 * 60 * 1000
        self.selected_ui_mode = "balanced"
        self.market_radar_expanded = False
        self._ui_mode_profiles = {
            "performance": {"gui_ms": 1000, "panel_ms": 42, "grid_ms": 24, "spark_ms": 30, "band_ms": 42, "radar_ms": 30, "glyph_ms": 34},
            "balanced": {"gui_ms": 1500, "panel_ms": 55, "grid_ms": 33, "spark_ms": 40, "band_ms": 55, "radar_ms": 35, "glyph_ms": 40},
            "low": {"gui_ms": 4000, "panel_ms": 120, "grid_ms": 90, "spark_ms": 110, "band_ms": 140, "radar_ms": 110, "glyph_ms": 120},
        }

        self._build_ui()
        self._update_system_health_indicators()
        self.apply_system_theme()
        self._apply_ui_mode_to_controls(self.selected_ui_mode)
        self._update_terminal_mode()
        self._sync_market_radar_toggle()

    def _capture_ui_state(self) -> dict:
        state = {}
        try:
            if hasattr(self, "tabs") and self.tabs is not None:
                state["tab_index"] = int(self.tabs.currentIndex())
        except Exception:
            pass
        try:
            if hasattr(self, "balance_chart_step_combo") and self.balance_chart_step_combo is not None:
                state["balance_chart_step"] = self.balance_chart_step_combo.currentData()
        except Exception:
            pass
        try:
            if hasattr(self, "start_window") and self.start_window is not None:
                state["account_flag"] = self.start_window.account_combo.currentData()
                state["timeframe"] = self.start_window.timeframe_combo.currentData()
                state["trade_mode"] = getattr(self.start_window, "selected_trade_mode", "auto")
                state["ui_mode"] = getattr(self, "selected_ui_mode", "balanced")
                state["market_radar_expanded"] = bool(getattr(self, "market_radar_expanded", False))
        except Exception:
            pass
        try:
            if hasattr(self, "activity_feed") and self.activity_feed is not None:
                state["activity_feed_html"] = self.activity_feed.toHtml()
        except Exception:
            pass
        try:
            if hasattr(self, "log_text") and self.log_text is not None:
                state["system_log_text"] = self.log_text.toPlainText()
        except Exception:
            pass
        return state

    def _restore_ui_state(self, state: dict | None) -> None:
        state = dict(state or {})
        try:
            tf = state.get("timeframe")
            if tf is not None and hasattr(self, "start_window") and self.start_window is not None:
                idx = self.start_window.timeframe_combo.findData(tf)
                if idx >= 0:
                    self.start_window.timeframe_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            flag = state.get("account_flag")
            if flag is not None and hasattr(self, "start_window") and self.start_window is not None:
                idx = self.start_window.account_combo.findData(flag)
                if idx >= 0:
                    self.start_window.account_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            mode = state.get("trade_mode")
            if mode is not None and hasattr(self, "start_window") and self.start_window is not None:
                self.start_window.set_trade_mode(str(mode))
            if hasattr(self, "mode_switch_toggle"):
                self.mode_switch_toggle.setChecked(str(state.get("trade_mode", "auto")).lower() == "manual")
                self._sync_trade_mode_toggle()
        except Exception:
            pass
        try:
            ui_mode = str(state.get("ui_mode", getattr(self, "selected_ui_mode", "balanced")) or "balanced")
            self._apply_ui_mode_to_controls(ui_mode)
            self.market_radar_expanded = bool(state.get("market_radar_expanded", getattr(self, "market_radar_expanded", False)))
            if hasattr(self, "_sync_market_radar_toggle"):
                self._sync_market_radar_toggle()
        except Exception:
            pass
        try:
            step = state.get("balance_chart_step")
            if step is not None and hasattr(self, "balance_chart_step_combo") and self.balance_chart_step_combo is not None:
                idx = self.balance_chart_step_combo.findData(step)
                if idx >= 0:
                    self.balance_chart_step_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            if hasattr(self, "activity_feed") and self.activity_feed is not None and state.get("activity_feed_html"):
                self.activity_feed.setHtml(state["activity_feed_html"])
        except Exception:
            pass
        try:
            if hasattr(self, "log_text") and self.log_text is not None and state.get("system_log_text") is not None:
                self.log_text.setPlainText(state["system_log_text"])
        except Exception:
            pass
        try:
            if hasattr(self, "tabs") and self.tabs is not None:
                idx = int(state.get("tab_index", 0) or 0)
                idx = max(0, min(idx, self.tabs.count() - 1))
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            self._sync_engine_controls_after_ui_reload()
            self._update_system_health_indicators()
            self.apply_system_theme()
            if hasattr(self, "update_ui"):
                self.update_ui()
            self._sync_market_radar_toggle()
        except Exception:
            pass

    def toggle_market_radar(self) -> None:
        self.market_radar_expanded = not bool(getattr(self, "market_radar_expanded", False))
        self._sync_market_radar_toggle()

    def _sync_market_radar_toggle(self) -> None:
        expanded = bool(getattr(self, "market_radar_expanded", False))
        if hasattr(self, "market_radar_content") and self.market_radar_content is not None:
            self.market_radar_content.setVisible(expanded)
        if hasattr(self, "btn_market_radar_toggle") and self.btn_market_radar_toggle is not None:
            self.btn_market_radar_toggle.setText("MARKET RADAR ▲" if expanded else "MARKET RADAR ▼")
            self.btn_market_radar_toggle.setChecked(expanded)
        if hasattr(self, "market_radar_box") and self.market_radar_box is not None:
            self.market_radar_box.updateGeometry()

    def _append_log_line(self, message: str) -> None:
        try:
            self.append_log(message)
        except Exception:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                line = f"[{ts}] {message}"
                if hasattr(self, "log_text") and self.log_text is not None:
                    self.log_text.append(line)
                if hasattr(self, "activity_feed") and self.activity_feed is not None:
                    self.activity_feed.append(line)
            except Exception:
                pass

    def _sync_engine_controls_after_ui_reload(self) -> None:
        running = bool(self.worker and self.worker.isRunning()) or bool(self.engine and getattr(self.engine, "running", False)) or bool(self._bot_running)
        self._bot_running = running
        self._sync_toggle_button_state()
        try:
            if hasattr(self, "lbl_header_status_chip") and self.lbl_header_status_chip is not None:
                self.lbl_header_status_chip.setText("ENGINE: RUNNING" if running else "ENGINE: IDLE")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_status") and self.lbl_status is not None:
                self.lbl_status.setText("Статус: Бот запущен" if running else "Статус: Бот остановлен")
                self.lbl_status.setStyleSheet("color: #00ffa3; font-weight: 800;" if running else "color: #ff4d4f; font-weight: 800;")
        except Exception:
            pass
        try:
            if hasattr(self, "start_window") and self.start_window is not None:
                self.start_window.setEnabled(not running)
        except Exception:
            pass

    def _teardown_ui(self) -> None:
        try:
            if hasattr(self, "gui_timer") and self.gui_timer is not None:
                self.gui_timer.stop()
                self.gui_timer.deleteLater()
        except Exception:
            pass
        try:
            cw = self.centralWidget()
            if cw is not None:
                cw.setParent(None)
                cw.deleteLater()
        except Exception:
            pass

    def reload_ui(self) -> None:
        ui_state = self._capture_ui_state()
        try:
            module_name = getattr(self, "_ui_layout_module_name", "ui_layout_v078")
            if module_name in sys.modules:
                ui_module = importlib.reload(sys.modules[module_name])
            else:
                ui_module = importlib.import_module(module_name)
            self._teardown_ui()
            ui_module.build_main_window_ui(self, self._ui_dependencies())
            self._restore_ui_state(ui_state)
            self._append_log_line("[UI] Reload UI выполнен без остановки движка")
        except Exception as exc:
            try:
                self._append_log_line(f"[UI] Reload UI error: {exc}")
            except Exception:
                pass
            QMessageBox.warning(self, "Reload UI", f"Не удалось перезагрузить интерфейс: {exc}")

    def _set_health_chip(self, label_widget, name: str, state: str, detail: str = "") -> None:
        state_map = {
            "online": ("●", "#00ffa3"),
            "delay": ("●", "#ffb347"),
            "idle": ("●", "#7dd3fc"),
            "error": ("●", "#ff4d6d"),
        }
        dot, color = state_map.get(str(state).lower(), ("●", "#7dd3fc"))
        suffix = f"  {detail}" if detail else ""
        label_widget.setText(f"{dot} {name}{suffix}")
        label_widget.setProperty("syschip", "true")
        label_widget.setStyleSheet(f"color: {color}; font-weight: 900; background: rgba(6, 14, 28, 0.82); border: 1px solid #21456f; border-radius: 14px; padding: 5px 10px;")

    def _update_system_health_indicators(self) -> None:
        engine_state = "online" if self._bot_running else "idle"
        strategy_state = "online" if self._bot_running else "idle"
        okx_state = "online" if self.current_cfg is not None else "idle"
        api_state = "online" if self.current_cfg is not None else "idle"
        if self.latest_snapshot:
            engine_info = self.latest_snapshot.get("engine", {}) or {}
            cycle_dur = float(engine_info.get("last_cycle_duration_sec", 0.0) or 0.0)
            if cycle_dur >= 10.0:
                engine_state = "error"
            elif cycle_dur >= 5.0:
                engine_state = "delay"
            elif self._bot_running:
                engine_state = "online"
            md = self.latest_snapshot.get("market_data_cache", {}) or {}
            errors = int(md.get("error_count", 0) or 0)
            if errors > 0 and self._bot_running:
                api_state = "delay" if errors < 5 else "error"
            if self.latest_snapshot.get("settings"):
                okx_state = "online"
        for attr, args in {
            "lbl_sys_api": ("API", api_state, "REST"),
            "lbl_sys_engine": ("ENGINE", engine_state, "LIVE" if self._bot_running else "IDLE"),
            "lbl_sys_strategy": ("STRATEGY", strategy_state, (getattr(self.current_cfg, "trade_mode", "auto").upper() if self.current_cfg else "AUTO")),
            "lbl_sys_okx": ("OKX", okx_state, (getattr(self.current_cfg, "timeframe", "—") if self.current_cfg else "—")),
        }.items():
            if hasattr(self, attr):
                self._set_health_chip(getattr(self, attr), *args)
        self._update_terminal_mode()

    def _update_terminal_mode(self) -> None:
        mode = "idle"
        if self._bot_running:
            mode = "trading"
        if self.latest_snapshot:
            engine_info = self.latest_snapshot.get("engine", {}) or {}
            cycle_dur = float(engine_info.get("last_cycle_duration_sec", 0.0) or 0.0)
            if cycle_dur >= 10.0:
                mode = "alert"
            elif cycle_dur >= 5.0 and mode != "alert":
                mode = "trading"
        if hasattr(self, "bg_terminal"):
            self.bg_terminal.set_mode(mode)

    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))
        if hasattr(self, "balance_chart"):
            self.balance_chart.set_dark_theme(self._is_dark_theme)

    def eventFilter(self, watched, event) -> bool:
        if watched is QApplication.instance() and event.type() in {QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange, QEvent.Type.ThemeChange}:
            QTimer.singleShot(0, self.apply_system_theme)
        return super().eventFilter(watched, event)

    def _ui_dependencies(self) -> dict:
        return {
            "APP_VERSION": APP_VERSION,
            "AnimatedGridWidget": AnimatedGridWidget,
            "NeonPanel": NeonPanel,
            "MarketPulseTile": MarketPulseTile,
            "GlowBandWidget": GlowBandWidget,
            "LaunchConfigWidget": LaunchConfigWidget,
            "NeonRadarWidget": NeonRadarWidget,
            "NeonGlyphWidget": NeonGlyphWidget,
            "BalanceChartWidget": BalanceChartWidget,
        }

    def _build_ui(self) -> None:
        self._ui_layout_module_name = "ui_layout_v078"
        if self._ui_layout_module_name in sys.modules:
            ui_module = importlib.reload(sys.modules[self._ui_layout_module_name])
        else:
            ui_module = importlib.import_module(self._ui_layout_module_name)
        ui_module.build_main_window_ui(self, self._ui_dependencies())

    def show_open_position_context(self, index) -> None:
        try:
            row_idx = int(index.row())
            if row_idx < 0 or row_idx >= len(self.table_model.rows):
                return
            row = self.table_model.rows[row_idx]
            context_file = str(row.get("entry_context_file") or "").strip()
            if not context_file or not Path(context_file).exists():
                QMessageBox.information(self, "Контекст входа", "Для этой позиции ещё не найден сохранённый контекст входа.")
                return

            payload = json.loads(Path(context_file).read_text(encoding="utf-8"))
            live_payload = dict(payload)

            engine = getattr(self, "engine", None)
            inst_id = str(row.get("inst_id") or payload.get("inst_id") or "").strip()
            timeframe = str(payload.get("timeframe") or (getattr(getattr(engine, "cfg", None), "timeframe", "") if engine else "") or "5m").strip()
            current_candles = list(payload.get("candles") or [])
            desired_limit = max(120, len(current_candles) or 0)

            try:
                if engine is not None and inst_id:
                    fetched = engine.gateway.get_candles(inst_id, timeframe, desired_limit)
                    if fetched:
                        live_payload["candles"] = fetched
                        live_payload["live_chart"] = True
                        live_payload["chart_mode"] = "live"
            except Exception:
                live_payload["candles"] = current_candles

            if "candles" not in live_payload or not live_payload.get("candles"):
                live_payload["candles"] = current_candles

            live_payload["inst_id"] = inst_id or payload.get("inst_id")
            live_payload["timeframe"] = timeframe
            dlg = EntryContextDialog(live_payload, context_file, self, live_state=row)
            dlg.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Контекст входа", f"Не удалось открыть контекст входа: {exc}")
    def show_closed_trade_context(self, index) -> None:
        try:
            row_idx = int(index.row())
            if row_idx < 0 or row_idx >= len(self.closed_table_model.rows):
                return
            row = self.closed_table_model.rows[row_idx]
            context_file = str(row.get("trade_context_file") or "").strip()
            if not context_file or not Path(context_file).exists():
                QMessageBox.information(self, "Контекст закрытой сделки", "Для этой сделки ещё не найден сохранённый график жизненного цикла.")
                return
            payload = json.loads(Path(context_file).read_text(encoding="utf-8"))
            dlg = TradeLifecycleDialog(payload, context_file, self)
            dlg.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Контекст закрытой сделки", f"Не удалось открыть график закрытой сделки: {exc}")

    def _format_remaining(self, seconds_left: float) -> str:
        seconds_left = max(0, int(seconds_left))
        hours, rem = divmod(seconds_left, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours > 0:
            return f"{hours}ч {minutes:02d}м"
        if minutes > 0:
            return f"{minutes}м {seconds:02d}с"
        return f"{seconds}с"

    def _collect_blocked_rows(self) -> list[tuple[str, str, str, str]]:
        rows = []
        engine = self.engine
        if engine is None:
            return rows

        now_ts = time.time()

        blocked_map = getattr(engine, "blocked_instruments", {}) or {}
        temp_blocked = getattr(engine, "temp_blocked_until", {}) or {}
        illiquid_map = getattr(engine, "illiquid_instruments", {}) or {}
        stopouts = getattr(engine, "recent_stopouts", {}) or {}

        all_inst = set(blocked_map.keys()) | set(temp_blocked.keys()) | set(illiquid_map.keys()) | set(stopouts.keys())

        for inst_id in sorted(all_inst):
            base_reason = str(blocked_map.get(inst_id) or "").strip()

            if inst_id in illiquid_map:
                until_ts = float(illiquid_map.get(inst_id, 0.0) or 0.0)
                if until_ts > now_ts:
                    ttl = self._format_remaining(until_ts - now_ts)
                    rows.append((inst_id, "Неликвидный рынок", base_reason or "illiquidity-filter", ttl))
                    continue

            if inst_id in temp_blocked:
                until_ts = float(temp_blocked.get(inst_id, 0.0) or 0.0)
                if until_ts > now_ts:
                    ttl = self._format_remaining(until_ts - now_ts)
                    rows.append((inst_id, "Временный бан", base_reason or "exchange/temp block", ttl))
                    continue

            if inst_id in stopouts:
                data = stopouts.get(inst_id) or {}
                until_ts = float(data.get("until", 0.0) or 0.0)
                if until_ts > now_ts:
                    ttl = self._format_remaining(until_ts - now_ts)
                    reason = str(data.get("reason") or "cooldown after stop").strip()
                    rows.append((inst_id, "Cooldown после стопа", reason, ttl))
                    continue

            if inst_id in blocked_map:
                rows.append((inst_id, "Постоянный/биржевой бан", base_reason or "blocked", "—"))

        return rows

    def refresh_blocked_instruments_view(self) -> None:
        if not hasattr(self, "blocked_table"):
            return

        rows = self._collect_blocked_rows()

        if hasattr(self, "lbl_blocked_count"):
            self.lbl_blocked_count.setText(f"BLOCKS: {len(rows)}")
        if self.engine is not None:
            try:
                metrics = self.engine._collect_trade_ready_metrics()
                scan_total = int(metrics.get('scan_universe_total', 0) or 0)
                available_count = int(metrics.get('available_after_bans_count', 0) or 0)
                ready_count = int(metrics.get('trade_ready_count', 0) or 0)
                if hasattr(self, "lbl_available_markets"):
                    self.lbl_available_markets.setText(f"AVAIL: {available_count}/{scan_total}")
                if hasattr(self, "lbl_ready_count"):
                    self.lbl_ready_count.setText(f"READY: {ready_count}")
            except Exception:
                pass

        self.blocked_table.setRowCount(len(rows))

        for row_idx, (inst_id, block_type, reason, ttl) in enumerate(rows):
            values = [inst_id, block_type, reason, ttl]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.blocked_table.setItem(row_idx, col_idx, item)

        if not rows:
            self.blocked_table.setRowCount(1)
            self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 2, QTableWidgetItem("Активных блокировок нет"))
            self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))

    def _telegram_enabled_in_cfg(self, cfg: Optional[BotConfig]) -> bool:
        if cfg is None:
            return False
        return bool(getattr(cfg, "telegram_enabled", False) and getattr(cfg, "telegram_bot_token", "") and getattr(cfg, "telegram_chat_id", ""))

    def _stop_telegram_screenshot_timer(self) -> None:
        if self._telegram_screenshot_timer is not None:
            self._telegram_screenshot_timer.stop()
            self._telegram_screenshot_timer.deleteLater()
            self._telegram_screenshot_timer = None

    def _configure_telegram_screenshots(self, cfg: Optional[BotConfig]) -> None:
        self._stop_telegram_screenshot_timer()
        self.telegram_ui_notifier = None
        if not self._telegram_enabled_in_cfg(cfg):
            return
        try:
            self.telegram_ui_notifier = TelegramNotifier(
                enabled=True,
                bot_token=str(getattr(cfg, "telegram_bot_token", "") or "").strip(),
                chat_id=str(getattr(cfg, "telegram_chat_id", "") or "").strip(),
            )
            self._telegram_screenshot_timer = QTimer(self)
            self._telegram_screenshot_timer.timeout.connect(self.send_main_window_screenshot_to_telegram)
            self._telegram_screenshot_timer.start(self._telegram_screenshot_interval_ms)
            self.append_log("Telegram: автоскрин главного окна включён (каждые 15 минут)")
        except Exception as exc:
            self.telegram_ui_notifier = None
            self._stop_telegram_screenshot_timer()
            self.append_log(f"Telegram: не удалось включить автоскрин окна: {exc}")

    def send_main_window_screenshot_to_telegram(self) -> None:
        notifier = self.telegram_ui_notifier
        if notifier is None or not getattr(notifier, "enabled", False):
            return
        if not self.isVisible():
            return
        try:
            screenshot_dir = LOG_DIR / "telegram_ui_snapshots"
            screenshot_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = screenshot_dir / f"main_window_{ts}.png"
            pixmap = self.grab()
            if pixmap.isNull():
                raise RuntimeError("пустой pixmap")
            if not pixmap.save(str(file_path), "PNG"):
                raise RuntimeError("не удалось сохранить PNG")
            caption = f"OKX Turtle Bot {APP_VERSION} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            notifier.send_photo(str(file_path), caption=caption)
            self.append_log(f"Telegram: отправлен скрин главного окна {file_path.name}")
            try:
                snapshots = sorted(screenshot_dir.glob("main_window_*.png"))
                for old_file in snapshots[:-12]:
                    old_file.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as exc:
            self.append_log(f"Telegram: ошибка отправки скрина окна: {exc}")

    def _clear_ui_runtime_data(self) -> None:
        self.latest_snapshot = None
        self.table_model.update_rows([])
        self.closed_table_model.update_rows([])
        self.balance_chart.update_points([], self.balance_chart_step_combo.currentData() if hasattr(self, "balance_chart_step_combo") else "1m", markers=[])
        if hasattr(self, "log_text"):
            self.log_text.clear()
        self.lbl_positions.setText("Открытых позиций: 0")
        self.lbl_balance_summary.setText("Баланс: 0 | Использовано: 0 | Доступно: 0")
        self.lbl_open_pnl.setText("Open PnL: 0")
        self.lbl_realized.setText("Реализованный PnL: 0")
        self.lbl_closed_stats.setText("Закрытых сделок: 0")
        self.lbl_winrate.setText("Winrate: 0%")
        if hasattr(self, "lbl_balance_points") and self.lbl_balance_points is not None:
            self.lbl_balance_points.setText("Показано значений: 0/30")
        self.lbl_runtime.setText("Время работы: —")
        self.lbl_cycle_duration.setText("Цикл движка: —")
        if hasattr(self, 'lbl_balance_hero'): self.lbl_balance_hero.setText('BALANCE\n0 USDT')
        if hasattr(self, 'lbl_balance_used'): self.lbl_balance_used.setText('USED\n0 USDT')
        if hasattr(self, 'lbl_balance_available'): self.lbl_balance_available.setText('AVAILABLE\n0 USDT')
        if hasattr(self, 'lbl_balance_equity'): self.lbl_balance_equity.setText('')
        if hasattr(self, 'lbl_balance_formula'): self.lbl_balance_formula.setText('')
        if hasattr(self, 'lbl_available_markets'): self.lbl_available_markets.setText('AVAIL: 0/0')
        if hasattr(self, 'lbl_ready_count'): self.lbl_ready_count.setText('READY: 0')
        if hasattr(self, 'lbl_session_pnl'): self.lbl_session_pnl.setText('Session PnL: 0.00')
        if hasattr(self, 'lbl_header_status_chip'): self.lbl_header_status_chip.setText('ENGINE: IDLE')

    def _reset_remote_positions(self) -> tuple[int, list[str]]:
        cfg = self.current_cfg
        if cfg is None and self.engine is not None:
            cfg = self.engine.cfg
        if cfg is None:
            return 0, []
        gateway = OkxGateway(cfg)
        positions = gateway.get_positions()
        closed = 0
        errors = []
        for pos in positions:
            inst_id = str(pos.get("instId") or "").strip()
            if not inst_id:
                continue
            try:
                qty = abs(float(pos.get("pos") or 0.0))
            except Exception:
                qty = 0.0
            if qty <= 0:
                continue
            gateway.cancel_pending_close_orders(inst_id)
            resp = gateway.close_position(inst_id, "reset_test", auto_cancel=True)
            if resp.get("code") == "0":
                closed += 1
            else:
                errors.append(f"{inst_id}: {resp}")
        return closed, errors

    def reset_test_run(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset теста",
            "Остановить бота, попытаться закрыть все SWAP-позиции и очистить локальные логи/состояние?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        was_running = bool(self.worker and self.worker.isRunning())
        if was_running:
            self.stop_engine()

        closed = 0
        close_errors = []
        try:
            closed, close_errors = self._reset_remote_positions()
        except Exception as exc:
            close_errors = [str(exc)]

        reset_info = reset_local_runtime_files()

        if self.engine is not None:
            self.engine.position_state.clear()
            self.engine.closed_trades.clear()
            with self.engine.balance_lock:
                self.engine.balance_history.clear()
                self.engine.latest_balance_snapshot = {}
            for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections", "close_retry_after", "execution_risk_events"):
                data = getattr(self.engine, attr, None)
                if isinstance(data, dict):
                    data.clear()
            self.engine._save_state()

        self._clear_ui_runtime_data()
        self.refresh_blocked_instruments_view()
        if hasattr(self, "lbl_available_markets"):
            self.lbl_available_markets.setText("AVAIL: 0/0")
        if hasattr(self, "lbl_ready_count"):
            self.lbl_ready_count.setText("READY: 0")

        summary = (
            f"Reset теста выполнен: закрыто позиций {closed}, "
            f"удалено entry-context {reset_info['entry_context_removed']}, "
            f"trade-context {reset_info['trade_context_removed']}"
        )
        self.append_log(summary)
        if close_errors:
            self.append_log("Ошибки закрытия при reset: " + " | ".join(close_errors[:8]))

    def export_analysis_bundle(self) -> None:
        try:
            dialog = AnalysisExportDialog(self)
            dialog.btn_open.clicked.connect(lambda: os.startfile(str(ANALYSIS_EXPORT_DIR)) if os.name == 'nt' else None)
            if dialog.exec() != int(QDialog.DialogCode.Accepted):
                return
            mode = str(dialog.selected_mode or 'full').lower()
            archive_path = build_analysis_export_bundle(mode=mode, snapshot=self.latest_snapshot, cfg=self.current_cfg)
            self.append_log(f"Сдать анализы: режим={mode} | архив сохранён {archive_path}")
            QMessageBox.information(
                self,
                "Сдать анализы",
                "Диагностический архив готов.\n\n"
                f"Режим: {mode}\n"
                f"Путь: {archive_path}\n\n"
                "Его можно загружать в чат для разбора работы стратегии.",
            )
        except Exception as exc:
            self.append_log(f"Сдать анализы: ошибка экспорта: {exc}")
            QMessageBox.warning(self, "Сдать анализы", f"Не удалось собрать архив анализа: {exc}")

    def clear_ban_lists(self) -> None:
        if self.engine is None:
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
            if hasattr(self, "lbl_available_markets"):
                self.lbl_available_markets.setText("AVAIL: 0/0")
            if hasattr(self, "lbl_ready_count"):
                self.lbl_ready_count.setText("READY: 0")
            if hasattr(self, "blocked_table"):
                self.blocked_table.setRowCount(1)
                self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 2, QTableWidgetItem("Бан-лист очищен."))
                self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))
            self.append_log("Бан-лист очищен (движок ещё не запущен)")
            return

        for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections", "execution_risk_events"):
            data = getattr(self.engine, attr, None)
            if isinstance(data, dict):
                data.clear()

        self.refresh_blocked_instruments_view()
        self.append_log("Все заблокированные инструменты удалены из бан-листа")

    def set_pending_config(self, cfg: BotConfig) -> None:
        self.current_cfg = cfg
        account = "Основной" if cfg.flag == "0" else "Демо"
        self._apply_trade_mode_to_controls(getattr(cfg, "trade_mode", "auto"))
        self.append_log(f"Параметры обновлены: {account}, {cfg.timeframe}, режим: {getattr(cfg, 'trade_mode', 'auto')}")

    def _apply_trade_mode_to_controls(self, mode: str) -> None:
        normalized = "manual" if str(mode).lower() == "manual" else "auto"
        if hasattr(self, "mode_switch_toggle"):
            blocked = self.mode_switch_toggle.blockSignals(True)
            self.mode_switch_toggle.setChecked(normalized == "manual")
            self.mode_switch_toggle.setText("Режим: Ручной" if normalized == "manual" else "Режим: Авто")
            bg = "#b42318" if normalized == "manual" else "#157347"
            self.mode_switch_toggle.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: white; border: none; border-radius: 17px; padding: 6px 14px; font-weight: 700; }}"
                f"QPushButton:hover {{ opacity: 0.92; }}"
            )
            self.mode_switch_toggle.blockSignals(blocked)
        if hasattr(self, "start_window") and self.start_window is not None:
            self.start_window.set_trade_mode(normalized)

    def on_trade_mode_changed(self, *_args) -> None:
        mode = "manual" if (hasattr(self, "mode_switch_toggle") and self.mode_switch_toggle.isChecked()) else "auto"
        self._apply_trade_mode_to_controls(mode)
        if self.current_cfg is not None:
            self.current_cfg.trade_mode = mode
        if self.engine is not None and hasattr(self.engine, "cfg"):
            self.engine.cfg.trade_mode = mode
        if isinstance(getattr(self, "latest_snapshot", None), dict):
            self.latest_snapshot.setdefault("settings", {})
            self.latest_snapshot["settings"]["trade_mode"] = mode
        self.append_log(f"Режим торговли переключён: {'ручной' if mode == 'manual' else 'автоматический'}")

    def _normalize_ui_mode(self, mode: str) -> str:
        mode_norm = str(mode or "balanced").strip().lower()
        return mode_norm if mode_norm in self._ui_mode_profiles else "balanced"

    def _set_animation_timer_interval(self, widget, interval_ms: int) -> None:
        timer = getattr(widget, "_timer", None)
        if isinstance(timer, QTimer):
            timer.setInterval(max(20, int(interval_ms)))

    def _apply_ui_mode_profile(self, mode: str) -> None:
        mode_norm = self._normalize_ui_mode(mode)
        profile = self._ui_mode_profiles.get(mode_norm, self._ui_mode_profiles["balanced"])

        if hasattr(self, "gui_timer") and isinstance(self.gui_timer, QTimer):
            self.gui_timer.setInterval(max(500, int(profile["gui_ms"])))

        if hasattr(self, "bg_terminal"):
            self._set_animation_timer_interval(self.bg_terminal, profile["grid_ms"])
        if hasattr(self, "glow_band"):
            self._set_animation_timer_interval(self.glow_band, profile["band_ms"])
        if hasattr(self, "neon_radar"):
            self._set_animation_timer_interval(self.neon_radar, profile["radar_ms"])
        if hasattr(self, "neon_glyph"):
            self._set_animation_timer_interval(self.neon_glyph, profile["glyph_ms"])
        for panel in self.findChildren(NeonPanel):
            self._set_animation_timer_interval(panel, profile["panel_ms"])
        for tile in getattr(self, "market_tiles", []) or []:
            if hasattr(tile, "spark"):
                self._set_animation_timer_interval(tile.spark, profile["spark_ms"])

    def _apply_ui_mode_to_controls(self, mode: str, *, log_change: bool = False) -> None:
        mode_norm = self._normalize_ui_mode(mode)
        self.selected_ui_mode = mode_norm
        labels = {"performance": "PERFORMANCE", "balanced": "BALANCED", "low": "LOW"}
        if hasattr(self, "ui_mode_combo") and self.ui_mode_combo is not None:
            idx = self.ui_mode_combo.findData(mode_norm)
            if idx >= 0 and self.ui_mode_combo.currentIndex() != idx:
                blocked = self.ui_mode_combo.blockSignals(True)
                self.ui_mode_combo.setCurrentIndex(idx)
                self.ui_mode_combo.blockSignals(blocked)
        if hasattr(self, "lbl_ui_mode_hint") and self.lbl_ui_mode_hint is not None:
            self.lbl_ui_mode_hint.setText(f"UI MODE: {labels.get(mode_norm, mode_norm.upper())}")
        self._apply_ui_mode_profile(mode_norm)
        if log_change:
            self.append_log(f"GUI режим переключён: {labels.get(mode_norm, mode_norm.upper())}")

    def on_ui_mode_changed(self, *_args) -> None:
        mode = getattr(self, "selected_ui_mode", "balanced")
        if hasattr(self, "ui_mode_combo") and self.ui_mode_combo is not None:
            mode = str(self.ui_mode_combo.currentData() or mode)
        self._apply_ui_mode_to_controls(mode, log_change=True)

    def _human_side(self, side: str) -> str:
        side_norm = str(side or "").strip().lower()
        if side_norm == "long":
            return "Long"
        if side_norm == "short":
            return "Short"
        return side or "—"


    def on_entry_candidate(self, payload: dict) -> None:
        if self._manual_dialog_open:
            inst_id = str((payload or {}).get("inst_id") or "—")
            if self.engine is not None:
                self.engine._set_manual_entry_decision(False)
            self.append_log(f"{inst_id}: сигнал пропущен — уже открыто окно подтверждения ручного режима")
            return

        self._manual_dialog_open = True
        self._pending_manual_signal = dict(payload or {})
        inst_id = str(payload.get("inst_id") or "—")
        side = self._human_side(str(payload.get("side") or "—"))
        system_name = str(payload.get("system_name") or "—")
        price = float(payload.get("price") or 0.0)
        atr = float(payload.get("atr") or 0.0)
        timeframe = str(payload.get("timeframe") or "—")
        reason = str(payload.get("reason") or "signal")

        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Ручной режим: найден сигнал")
        box.setText("Найден новый сигнал для открытия позиции.")
        box.setInformativeText(
            f"Инструмент: {inst_id}\n"
            f"Направление: {side}\n"
            f"Система: {system_name}\n"
            f"Таймфрейм: {timeframe}\n"
            f"Цена: {price:.6f}\n"
            f"ATR: {atr:.6f}\n"
            f"Причина: {reason}"
        )
        trade_btn = box.addButton("Торгуем", QMessageBox.ButtonRole.AcceptRole)
        skip_btn = box.addButton("Пропускаем", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip_btn)
        box.setEscapeButton(skip_btn)
        box.setWindowModality(Qt.WindowModality.ApplicationModal)
        box.exec()

        allow = box.clickedButton() is trade_btn
        if self.engine is not None:
            self.engine._set_manual_entry_decision(allow)

        self.append_log(f"{inst_id}: ручной режим — {'торгуем' if allow else 'пропускаем'}")
        self._pending_manual_signal = None
        self._manual_dialog_open = False
        self._stop_telegram_screenshot_timer()

    def start_engine_from_controls(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            cfg = self.start_window.build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка параметров", str(exc))
            return
        self.current_cfg = cfg
        self.launch_engine(cfg)

    def _sync_toggle_button_state(self) -> None:
        if not hasattr(self, "toggle_button"):
            return
        if self._bot_running:
            self.toggle_button.setText("STOP BOT")
            self.toggle_button.setProperty("running", True)
        else:
            self.toggle_button.setText("START BOT")
            self.toggle_button.setProperty("running", False)
        self.toggle_button.style().unpolish(self.toggle_button)
        self.toggle_button.style().polish(self.toggle_button)
        self.toggle_button.update()

    def toggle_engine(self) -> None:
        if self.worker and self.worker.isRunning():
            self.stop_engine()
            return

        try:
            cfg = self.start_window.build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка параметров", str(exc))
            return

        self.current_cfg = cfg
        self.launch_engine(cfg)

    def launch_engine(self, cfg: BotConfig) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Уже запущен", "Сначала останови текущего бота")
            return
        self.current_cfg = cfg
        self._configure_telegram_screenshots(cfg)
        try:
            self.engine = TurtleEngine(cfg)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка запуска", str(exc))
            return
        self.engine.snapshot.connect(self.on_snapshot)
        self.engine.log_line.connect(self.append_log)
        self.engine.status.connect(self.on_status)
        self.engine.error.connect(self.on_error)
        self.engine.entry_candidate.connect(self.on_entry_candidate)
        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._snapshot_refresh_interval_sec = max(1, int(getattr(cfg, "snapshot_interval_sec", 2) or 2))
        self._apply_trade_mode_to_controls(getattr(cfg, "trade_mode", "auto"))
        self._snapshot_countdown_sec = 0
        self._bot_started_ts = time.time()
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
        self.append_log(f"Бот запущен пользователем (шаг: {cfg.timeframe})")
        self.append_log(f"Проверка параметров запуска: GUI={self.start_window.timeframe_combo.currentData()} | Config={cfg.timeframe}")
        self.append_log(f"Signal audit: {SIGNAL_AUDIT_FILE}")

    def stop_engine(self) -> None:
        if self.engine:
            self.engine._set_manual_entry_decision(False)
            self.engine.stop()
            self.append_log("Остановка запрошена")
        self._pending_manual_signal = None
        self._manual_dialog_open = False
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
            self.worker = None
        self._bot_running = False
        self._bot_started_ts = None
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
        if hasattr(self, "lbl_runtime"):
            self.lbl_runtime.setText("Время работы: —")


    def closeEvent(self, event) -> None:
        try:
            if self.engine or (self.worker and self.worker.isRunning()):
                self.stop_engine()
        finally:
            super().closeEvent(event)

    def request_snapshot(self) -> None:
        if self.engine and self.worker and self.worker.isRunning():
            try:
                self.engine.emit_snapshot()
                return
            except Exception as exc:
                self.append_log(f"Ошибка принудительного обновления таблицы: {exc}")
        if self.latest_snapshot:
            self.on_snapshot(self.latest_snapshot)

    def _update_refresh_countdown_label(self) -> None:
        return

    def _update_runtime_label(self) -> None:
        if not hasattr(self, "lbl_runtime"):
            return
        if self._bot_started_ts and self.engine and self.worker and self.worker.isRunning():
            elapsed = max(0, int(time.time() - self._bot_started_ts))
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)
            self.lbl_runtime.setText(f"Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self.lbl_runtime.setText("Время работы: —")

    def _on_gui_timer_tick(self) -> None:
        if self.engine and self.worker and self.worker.isRunning():
            self._snapshot_countdown_sec -= 1
            if self._snapshot_countdown_sec <= 0:
                self.request_snapshot()
                self.refresh_blocked_instruments_view()
                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        else:
            self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec

        self._update_runtime_label()

    def refresh_from_latest_snapshot(self) -> None:
        self.request_snapshot()

    def _top_engine_candidate(self) -> dict:
        candidates = []
        if self.engine is not None:
            try:
                candidates = list(getattr(self.engine, "last_scan_candidates", []) or [])
            except Exception:
                candidates = []
        return dict(candidates[0]) if candidates else {}

    def _market_tile_status(self, inst: str, candidate_map: dict, blocked: set, risky_exit: set) -> tuple[str, float, str]:
        if inst in candidate_map:
            item = candidate_map[inst]
            side = str(item.get("side") or "watch").lower()
            status = "LONG CANDIDATE" if side == "long" else "SHORT CANDIDATE"
            score = max(12.0, min(99.0, float(item.get("breakout_distance_atr", 0.0)) * 22.0 + float(item.get("liquidity_score", 0.0)) * 7.0 + float(item.get("freshness_score", 0.0)) * 18.0 - float(item.get("recent_trade_penalty", 0.0)) * 10.0))
            reason = f"{item.get('system_name', 'Turtle')} | {item.get('liquidity_profile', self.balance_chart_step_combo.currentData() if hasattr(self, 'balance_chart_step_combo') else 'scan')} | breakout armed"
            return status, score, reason
        if inst in risky_exit or inst in blocked:
            score = 36.0 if inst in risky_exit else 42.0
            reason = 'Liquidity / exit-risk watchlist' if inst in risky_exit else 'Temporarily blocked / restricted'
            return 'RISK', score, reason
        return 'WATCH', 14.0, 'Watching breakout / ATR / liquidity alignment'

    def on_snapshot(self, payload: dict) -> None:
        self.latest_snapshot = payload
        settings = payload.get("settings", {})
        analytics = payload.get("analytics", {})
        engine_info = payload.get("engine", {})
        open_positions = payload.get("open_positions", [])

        account_name = settings.get('account', '—')
        timeframe = settings.get('timeframe', '—')
        mode = settings.get('trade_mode', getattr(self.current_cfg, 'trade_mode', 'auto'))
        self._apply_trade_mode_to_controls(mode)

        self.lbl_account.setText(f"Аккаунт: {account_name}")
        self.lbl_timeframe.setText(f"Таймфрейм: {timeframe}")
        self.lbl_header_mode.setText(f"ACCOUNT: {account_name.upper()}")
        self.lbl_header_tf_chip.setText(f"TF: {timeframe}")
        self.lbl_header_pos_chip.setText(f"POS: {len(open_positions)}/{getattr(self.current_cfg, 'max_open_positions_total', 16) if self.current_cfg else 16}")

        bal_total = payload.get('balance_total', 0.0)
        bal_used = payload.get('balance_used', 0.0)
        bal_avail = payload.get('balance_available', 0.0)
        equity_total = float(analytics.get('equity_total', bal_total + analytics.get('open_pnl', 0.0)) or (bal_total + analytics.get('open_pnl', 0.0)))
        self.lbl_balance_hero.setText(f"BALANCE\n{bal_total:,.2f} USDT")
        self.lbl_balance_used.setText(f"USED\n{bal_used:,.2f} USDT")
        self.lbl_balance_available.setText(f"AVAILABLE\n{bal_avail:,.2f} USDT")
        self.lbl_balance_equity.setText('')
        self.lbl_balance_formula.setText('')
        self.lbl_balance_summary.setText(f"Баланс: {bal_total:.0f} | Использовано: {bal_used:.0f} | Доступно: {bal_avail:.0f}")
        self.lbl_session_pnl.setText(f"Session PnL: {analytics.get('realized_pnl', 0.0) + analytics.get('open_pnl', 0.0):+.2f} USDT")
        self.lbl_positions.setText(f"POS: {len(open_positions)}")
        ready_count = int(analytics.get('trade_ready_count', 0) or 0)
        available_after_bans = int(analytics.get('available_after_bans_count', 0) or 0)
        scan_total = int(analytics.get('scan_universe_total', 0) or 0)
        blocked_total = int(analytics.get('blocked_total', 0) or 0)
        if hasattr(self, 'lbl_blocked_count') and self.lbl_blocked_count is not None:
            self.lbl_blocked_count.setText(f"BLOCKS: {blocked_total}")
        if hasattr(self, 'lbl_available_markets') and self.lbl_available_markets is not None:
            self.lbl_available_markets.setText(f"AVAIL: {available_after_bans}/{scan_total}")
        if hasattr(self, 'lbl_ready_count') and self.lbl_ready_count is not None:
            self.lbl_ready_count.setText(f"READY: {ready_count}")

        cycle_duration = float(engine_info.get('last_cycle_duration_sec', 0.0) or 0.0)
        self.lbl_cycle_duration.setText(f"Цикл движка: {cycle_duration:.2f} сек")
        if cycle_duration > 10:
            self.lbl_cycle_duration.setStyleSheet("color: #ff4d4f; font-weight: 800;")
        elif cycle_duration >= 5:
            self.lbl_cycle_duration.setStyleSheet("color: #ff9f43; font-weight: 800;")
        else:
            self.lbl_cycle_duration.setStyleSheet("color: #00ffa3; font-weight: 800;")

        self.lbl_open_pnl.setText(f"Open PnL: {analytics.get('open_pnl', 0.0):+.4f}")
        self.lbl_avg_open.setText(f"Средний PnL %: {analytics.get('avg_open_pnl_pct', 0.0):+.2f}%")
        self.lbl_best.setText(f"Лучший PnL %: {analytics.get('best_open_pnl_pct', 0.0):+.2f}%")
        self.lbl_worst.setText(f"Худший PnL %: {analytics.get('worst_open_pnl_pct', 0.0):+.2f}%")
        self.lbl_long_short.setText(f"Long/Short: {analytics.get('long_count', 0)} / {analytics.get('short_count', 0)}")
        self.lbl_realized.setText(f"Реализованный PnL: {analytics.get('realized_pnl', 0.0):+.4f}")
        self.lbl_closed_stats.setText(f"Закрытых сделок: {analytics.get('closed_count', 0)}")
        self.lbl_winrate.setText(f"Winrate: {analytics.get('winrate', 0.0):.2f}%")
        if hasattr(self, 'lbl_balance_trend') and self.lbl_balance_trend is not None:
            self.lbl_balance_trend.setText(f"Изменение баланса: Сегодня {analytics.get('day_change_pct', 0.0):+.2f}% | 7 дней {analytics.get('week_change_pct', 0.0):+.2f}%")
        self.lbl_risk_panel.setText(f"Использовано риска: {analytics.get('used_risk_pct', 0.0):.2f}% / {analytics.get('max_risk_budget_pct', 0.0):.2f}%")
        self.lbl_trade_speed.setText(f"Сделок сегодня: {analytics.get('trades_today', 0)} | Средняя длительность: {format_duration(analytics.get('avg_duration_sec', 0))}")

        regime_label = analytics.get('turtle_regime_label', '—')
        regime_score = int(analytics.get('turtle_regime_score', 0) or 0)
        regime_inst = analytics.get('turtle_regime_instrument', '—')
        regime_channel = float(analytics.get('turtle_regime_channel_atr', 0.0) or 0.0)
        regime_eff = float(analytics.get('turtle_regime_efficiency', 0.0) or 0.0)
        regime_atr_pct = float(analytics.get('turtle_regime_atr_pct', 0.0) or 0.0)
        signal_funnel = payload.get('signal_funnel', {}) or {}
        top_candidate = self._top_engine_candidate()
        if top_candidate:
            cand_inst = str(top_candidate.get('inst_id', '—')).replace('-USDT-SWAP', '')
            cand_system = str(top_candidate.get('system_name', 'Turtle'))
            cand_side = str(top_candidate.get('side', 'watch')).upper()
            cand_breakout = float(top_candidate.get('breakout_distance_atr', 0.0) or 0.0)
            cand_liq = float(top_candidate.get('liquidity_score', 0.0) or 0.0)
            cand_profile = str(top_candidate.get('liquidity_profile', timeframe) or timeframe)
            cand_fresh = float(top_candidate.get('freshness_score', 0.0) or 0.0)
            entry_allowed = 'YES' if regime_label != 'Флэт' else 'WAIT'
            engine_score = min(4, max(1, regime_score + (1 if cand_breakout > 0.18 else 0)))
            self.lbl_turtle_regime.setText(f"Кандидат: {cand_inst} | {cand_system} {cand_side} | Entry allowed: {entry_allowed}")
            self.lbl_turtle_state_a.setText(f"BREAKOUT: {cand_system} | dist {cand_breakout:.2f} ATR | regime {regime_label}")
            self.lbl_turtle_state_b.setText(f"TREND / ATR: ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%")
            self.lbl_turtle_state_c.setText(f"LIQUIDITY: profile {cand_profile} | score {cand_liq:.1f} | fresh {cand_fresh:.2f} | ready {ready_count}")
            self.lbl_turtle_score.setText(f"ENTRY STATUS: {entry_allowed} | ENGINE SCORE {engine_score}/4 | CAND {int(signal_funnel.get('candidates', 0) or 0)}")
        else:
            entry_allowed = "YES" if regime_label == "Трендовый" and regime_score >= 3 else "NO"
            liquidity_pass = "PASS" if regime_label == "Трендовый" else ("WAIT" if regime_label == "Нейтральный" else "FILTERED")
            self.lbl_turtle_regime.setText(f"Кандидат: {regime_inst} | Режим: {regime_label} | Entry allowed: {entry_allowed}")
            self.lbl_turtle_state_a.setText(f"BREAKOUT: waiting for Donchian trigger | regime {regime_label}")
            self.lbl_turtle_state_b.setText(f"TREND / ATR: ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%")
            self.lbl_turtle_state_c.setText(f"LIQUIDITY: {liquidity_pass} | MODE {mode.upper()} | ready {ready_count} | {regime_inst.replace('-USDT-SWAP', '')}")
            self.lbl_turtle_score.setText(f"ENTRY STATUS: {entry_allowed} | ENGINE SCORE {regime_score}/4 | CAND {int(signal_funnel.get('candidates', 0) or 0)}")
        if regime_label == "Трендовый":
            turtle_style = "color: #00ffa3; font-weight: 800;"
        elif regime_label == "Нейтральный":
            turtle_style = "color: #ff9f43; font-weight: 800;"
        elif regime_label == "Флэт":
            turtle_style = "color: #ff4d4f; font-weight: 800;"
        else:
            turtle_style = ""
        for lbl in (self.lbl_turtle_regime, self.lbl_turtle_state_a, self.lbl_turtle_state_b, self.lbl_turtle_state_c, self.lbl_turtle_score):
            lbl.setStyleSheet(turtle_style)

        balance_history = payload.get('balance_history', [])
        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), [])
        if hasattr(self, "lbl_balance_step") and self.lbl_balance_step is not None:
            self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
        shown_points = len(self.balance_chart._bucket_points()) if hasattr(self.balance_chart, '_bucket_points') else 0
        if hasattr(self, "lbl_balance_points") and self.lbl_balance_points is not None:
            self.lbl_balance_points.setText(f"Показано значений: {shown_points}/30")

        pending_close = sum(1 for row in open_positions if row.get('close_pending'))
        self.lbl_close_pending.setText(f"Close pending: {pending_close}")
        md = payload.get('market_data_cache', {})
        exec_watch = len(getattr(self.engine, 'execution_risk_events', {}) or {}) if self.engine is not None else 0
        self.lbl_exec_watch.setText(f"Execution watchlist: {exec_watch}")

        header_status = 'RUNNING' if self._bot_running else 'IDLE'
        self.lbl_header_status_chip.setText(f"ENGINE: {header_status}")
        uptime_text = self.lbl_runtime.text().replace('Время работы: ', '')
        self.lbl_header_uptime_chip.setText(f"UPTIME: {uptime_text}")
        self._update_system_health_indicators()

        # market radar
        radar_rows = []
        blocked = set()
        candidate_map = {}
        if self.engine is not None:
            blocked.update(getattr(self.engine, 'blocked_instruments', {}).keys())
            blocked.update(getattr(self.engine, 'illiquid_instruments', {}).keys())
            blocked.update(getattr(self.engine, 'execution_risk_events', {}).keys())
            try:
                candidate_map = {str(item.get('inst_id')): dict(item) for item in list(getattr(self.engine, 'last_scan_candidates', []) or [])[:8] if item.get('inst_id')}
            except Exception:
                candidate_map = {}
        for row in sorted(open_positions, key=lambda x: abs(float(x.get('trend_strength_atr', 0.0))), reverse=True)[:6]:
            inst = row.get('inst_id', '—')
            pnl_pct = float(row.get('pnl_pct', 0.0) or 0.0)
            trend = float(row.get('trend_strength_atr', 0.0) or 0.0)
            status = 'LONG' if str(row.get('side', '')).lower() == 'long' else 'SHORT'
            score = min(99.0, abs(trend) * 20.0 + abs(pnl_pct) * 3.0)
            reason = f"Open position | trend {trend:.2f} ATR | pnl {pnl_pct:+.2f}%"
            radar_rows.append((inst, pnl_pct, trend, status, score, reason))
        fallback_watch = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'LINK-USDT-SWAP', 'ATOM-USDT-SWAP', 'MINA-USDT-SWAP']
        risky_exit = {'LINK-USDT-SWAP', 'ATOM-USDT-SWAP', 'MINA-USDT-SWAP', 'BREV-USDT-SWAP'}
        ordered_watch = list(candidate_map.keys()) + list((getattr(self.current_cfg, 'execution_risk_watchlist', []) if self.current_cfg else []) or []) + fallback_watch
        for inst in ordered_watch:
            if len(radar_rows) >= 6:
                break
            if not inst or any(r[0] == inst for r in radar_rows):
                continue
            status, score, reason = self._market_tile_status(inst, candidate_map, blocked, risky_exit)
            radar_rows.append((inst, 0.0, 0.0, status, score, reason))
        for idx, (tile, (inst, pnl_pct, trend, status, score, reason)) in enumerate(zip(self.market_tiles, radar_rows)):
            base = float(pnl_pct or 0.0)
            if inst in candidate_map:
                item = candidate_map[inst]
                impulse = float(item.get('breakout_distance_atr', 0.0) or 0.0) * 0.22 + float(item.get('freshness_score', 0.0) or 0.0) * 0.12
                values = [base * 0.15 + math.sin((j / 17.0) * math.pi * 1.25) * (0.18 + impulse) + impulse * (j / 17.0) for j in range(18)]
            elif status in {'LONG', 'SHORT'}:
                values = [base * 0.25 + ((j - 8) * 0.03) + trend * (0.04 if j % 2 == 0 else -0.02) for j in range(18)]
            else:
                values = [math.sin((j / 17.0) * math.pi * 1.8 + idx * 0.45) * 0.10 + (0.02 if status == 'WATCH' else -0.01) for j in range(18)]
            tile.set_data(inst, pnl_pct, values, status=status, score=score, reason=reason)

        band_source = []
        for point in balance_history[-48:]:
            try:
                band_source.append(float(point.get('balance_total', 0.0)))
            except Exception:
                continue
        if not band_source:
            band_source = [0.0] * 48
        pnl_band = []
        for row in open_positions[-48:]:
            try:
                pnl_band.append(float(row.get('pnl_pct', 0.0)))
            except Exception:
                continue
        if not pnl_band:
            pnl_band = [0.0] * max(12, min(48, len(band_source)))
        self.glow_band.set_series(band_source, pnl_band)

        self._apply_status_style(self.lbl_open_pnl, analytics.get('open_pnl', 0.0))
        self._apply_status_style(self.lbl_avg_open, analytics.get('avg_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_best, analytics.get('best_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_worst, analytics.get('worst_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_realized, analytics.get('realized_pnl', 0.0))
        self._apply_status_style(self.lbl_winrate, analytics.get('winrate', 0.0), percent=True)
        if hasattr(self, 'lbl_balance_trend') and self.lbl_balance_trend is not None:
            self._apply_status_style(self.lbl_balance_trend, analytics.get('day_change_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_session_pnl, analytics.get('realized_pnl', 0.0) + analytics.get('open_pnl', 0.0))

        self.apply_filters()

    def on_balance_chart_step_changed(self, *_args) -> None:
        if not self.latest_snapshot:
            return
        balance_history = self.latest_snapshot.get("balance_history", [])
        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), [])
        if hasattr(self, "lbl_balance_step") and self.lbl_balance_step is not None:
            self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
        if hasattr(self, "lbl_balance_points") and self.lbl_balance_points is not None:
            self.lbl_balance_points.setText(f"Показано значений: {len(self.balance_chart._bucket_points())}/30")

    def _apply_status_style(self, label: QLabel, value: float, percent: bool = False) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        if self._is_dark_theme:
            neutral = "#e5e7eb"
        else:
            neutral = "#202020"
        if numeric > 0:
            color = "#16a34a"
        elif numeric < 0:
            color = "#dc2626"
        else:
            color = neutral
        font_weight = "600" if percent or numeric != 0 else "500"
        card_style = label.property("card") == "true"
        extra = "background: transparent;"
        if card_style:
            extra = ""
        label.setStyleSheet(f"color: {color}; font-weight: {font_weight}; {extra}")

    def apply_filters(self) -> None:
        if not self.latest_snapshot:
            self.table_model.update_rows([])
            self.closed_table_model.update_rows([])
            return

        open_rows = [
            row for row in self.latest_snapshot.get("open_positions", [])
            if not is_hidden_instrument(row.get("inst_id"))
        ]
        open_rows.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
        self.table_model.update_rows(open_rows)

        closed_rows = [
            row for row in self.latest_snapshot.get("closed_trades", [])
            if not is_hidden_instrument(row.get("inst_id"))
        ]
        closed_rows.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
        self.closed_table_model.update_rows(closed_rows)

    def append_log(self, message: str) -> None:
        upper_message = str(message).upper()
        if False:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        if hasattr(self, "log_text") and self.log_text is not None:
            self.log_text.append(line)
        if hasattr(self, "activity_feed") and self.activity_feed is not None:
            color = '#8be9fd'
            if any(token in upper_message for token in ['LONG', 'OPEN', 'RUNNING', 'ЗАПУЩЕН', 'ПОДТВЕРЖДЁН']):
                color = '#00ffa3'
            elif any(token in upper_message for token in ['SHORT', 'STOP', 'ERROR', 'ОШИБКА', 'ОТКЛОНИЛА', 'ПРОПУЩЕН']):
                color = '#ff4d4f'
            elif any(token in upper_message for token in ['ADD', 'PYRAMID', 'ROTATION', 'RESET']):
                color = '#ff9f43'
            self.activity_feed.append(f'<span style="color:{color};">{line}</span>')
            doc2 = self.activity_feed.document()
            while doc2.blockCount() > 80:
                cursor2 = self.activity_feed.textCursor()
                cursor2.movePosition(cursor2.MoveOperation.Start)
                cursor2.select(cursor2.SelectionType.BlockUnderCursor)
                cursor2.removeSelectedText()
                cursor2.deleteChar()
        if hasattr(self, "log_text") and self.log_text is not None:
            doc = self.log_text.document()
            max_blocks = 400
            while doc.blockCount() > max_blocks:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()

    def on_status(self, message: str) -> None:
        self.lbl_status.setText(f"Статус: {message}")
        lower = message.lower()
        if "запущен" in lower:
            self._bot_running = True
            self.lbl_status.setStyleSheet("color: #00ffa3; font-weight: 800;")
            if hasattr(self, 'lbl_header_status_chip'): self.lbl_header_status_chip.setText('ENGINE: RUNNING')
        elif "остановлен" in lower:
            self._bot_running = False
            self.lbl_status.setStyleSheet("color: #ff4d4f; font-weight: 800;")
            if hasattr(self, 'lbl_header_status_chip'): self.lbl_header_status_chip.setText('ENGINE: STOPPED')
        else:
            self.lbl_status.setStyleSheet("")
        self._sync_toggle_button_state()
        self._update_system_health_indicators()
        self.append_log(message)

    def on_error(self, message: str) -> None:
        self.append_log(message)


def install_exception_logging() -> None:
    def _hook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)
        try:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Ошибка GUI")
            msg.setText(str(exc_value))
            msg.setDetailedText("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
            msg.exec()
        except Exception:
            pass
    sys.excepthook = _hook

def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    install_exception_logging()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
