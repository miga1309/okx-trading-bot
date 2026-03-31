# Auto-extracted from app/legacy_runtime.py during one-iteration runtime split
# === CHANGELOG HEADER ===
# Version: v107
# Date: 2026-03-24
# Changes: hardened close reconciliation so missing exchange positions are finalized into Closed Trades instead of disappearing, unified close finalization through one path, and downgraded transient market-data socket noise to temporary warnings.
# === END CHANGELOG HEADER ===
SYNC_INTERVAL_ACTIVE_POSITIONS = 10
SYNC_INTERVAL_IDLE = 60

def get_dynamic_sync_interval(open_positions_count: int) -> int:
    try:
        return reconciler_dynamic_sync_interval(open_positions_count)
    except Exception:
        return SYNC_INTERVAL_IDLE

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

import csv
import importlib
import json
import logging
import math
import faulthandler
import os
import re
import sys
import threading
import time
import zipfile
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple
from collections import Counter, deque, defaultdict
from tempfile import NamedTemporaryFile
import statistics
import traceback

from dotenv import load_dotenv
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPoint, QRect, QPointF, Qt, QThread, QTimer, pyqtSignal, pyqtSlot, QEvent
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

from integration.telegram.notifier import TelegramNotifier, ensure_queue_layout, resolve_log_file, resolve_pid_file, resolve_status_file, resolve_offset_file

from common.trade_models import BotConfig, PendingEntry, PositionState, ClosedTrade
from engine.analytics.diagnostics_logging import TradeLogger, EngineStatsLogger, SignalAuditLogger
from engine.exchange.market_data_cache import MarketDataCache
from infrastructure.exchange.okx_gateway import OkxGateway
from interface.gui.dialogs.legacy_popups import EntryContextDialog, TradeLifecycleDialog, ScannerReviewDialog
from analysis.export_bundle import ExportBundleContext, build_analysis_export_bundle
from domain.health.exchange_health import classify_connectivity_state, summarize_connectivity_rows, parse_exchange_ts_ms
from domain.reconcile.position_reconciler import (
    derive_sync_status,
    determine_hybrid_stop_mode,
    classify_trend_hold_state,
    turtle_exit_period_from_system,
    get_dynamic_sync_interval as reconciler_dynamic_sync_interval,
)
from domain.reconcile.sync_position_manager import restore_sync_position_state, build_sync_popup_payload
from domain.scanner.market_quality import analyze_sparse_candles, InstrumentHealthTracker
from domain.scanner.market_scanner_runtime import MarketScannerRuntime
from infrastructure.exchange.okx_ws_manager import OkxWsManager
from engine.stops.legacy_stop_engine import StopEngine
from domain.runtime.runtime_engine_bundle import RuntimeEngineBundle
from domain.runtime.stage3_engine_bundle import Stage3EngineBundle




APP_DIR = Path(__file__).resolve().parent
APP_VERSION = os.getenv("OKX_TURTLE_RUNTIME_VERSION", "v111")
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
CONNECTIVITY_LOG_FILE = LOG_DIR / "connectivity_log.jsonl"
PYRAMID_DIAGNOSTICS_FILE = LOG_DIR / "pyramid_diagnostics.jsonl"
REENTRY_DIAGNOSTICS_FILE = LOG_DIR / "reentry_diagnostics.jsonl"
BREAKOUT_QUALITY_FILE = LOG_DIR / "breakout_quality.jsonl"
STOP_ENGINE_FILE = LOG_DIR / "stop_engine.jsonl"
CRASH_LOG = LOG_DIR / "crash.log"
TRACEBACK_ERROR_FILE = LOG_DIR / "traceback_errors.jsonl"
HEARTBEAT_FILE = LOG_DIR / "heartbeat.jsonl"
TELEGRAM_RUNTIME_DIR = APP_DIR / "runtime"
TELEGRAM_QUEUE_DIR = TELEGRAM_RUNTIME_DIR / "telegram_queue"
TELEGRAM_WORKER_LOG_FILE = LOG_DIR / "telegram_worker.log"
TELEGRAM_WORKER_PID_FILE = TELEGRAM_RUNTIME_DIR / "telegram_worker.pid"
TELEGRAM_STATUS_FILE = TELEGRAM_RUNTIME_DIR / "telegram_status.json"
TELEGRAM_OFFSET_FILE = TELEGRAM_RUNTIME_DIR / "telegram_updates_offset.txt"
TELEGRAM_CHART_IMAGE_FILE = TELEGRAM_RUNTIME_DIR / "telegram_chart_latest.jpg"
TELEGRAM_WORKER_EXE_FILE = APP_DIR / "telegram_worker.exe"
TELEGRAM_WORKER_SCRIPT_FILE = APP_DIR / "run_telegram_worker.py"
TELEGRAM_HARD_DISABLED = False
ANALYSIS_EXPORT_DIR = LOG_DIR / "analysis_exports"
ANALYSIS_EXPORT_DIR.mkdir(exist_ok=True)
STATE_FILE = LOG_DIR / "runtime_state.json"
SCANNER_VALIDATION_LOG_FILE = LOG_DIR / "scanner_validation_log.csv"
SCANNER_VALIDATION_STATE_FILE = LOG_DIR / "scanner_validation_state.json"
SCANNER_RESULTS_FILE = LOG_DIR / "scanner_results.jsonl"
EXECUTION_LOG_FILE = LOG_DIR / "execution_log.jsonl"

EXPORT_BUNDLE_CONTEXT = ExportBundleContext(
    app_version=APP_VERSION,
    state_file=STATE_FILE,
    engine_stats_file=ENGINE_STATS_FILE,
    signal_audit_file=SIGNAL_AUDIT_FILE,
    position_journal_file=POSITION_JOURNAL_FILE,
    position_snapshots_file=POSITION_SNAPSHOTS_FILE,
    system_health_file=SYSTEM_HEALTH_FILE,
    connectivity_log_file=CONNECTIVITY_LOG_FILE,
    pyramid_diagnostics_file=PYRAMID_DIAGNOSTICS_FILE,
    reentry_diagnostics_file=REENTRY_DIAGNOSTICS_FILE,
    breakout_quality_file=BREAKOUT_QUALITY_FILE,
    stop_engine_file=STOP_ENGINE_FILE,
    traceback_error_file=TRACEBACK_ERROR_FILE,
    analysis_export_dir=ANALYSIS_EXPORT_DIR,
)

NIGHT_TEST_HARD_BLOCK_INSTRUMENTS = {"BREV-USDT-SWAP"}
HIDDEN_INSTRUMENTS = set(NIGHT_TEST_HARD_BLOCK_INSTRUMENTS)
HIDDEN_PREFIXES = tuple()
EXECUTION_RISK_WATCHLIST = {"ATOM-USDT-SWAP", "MINA-USDT-SWAP", "XSR-USDT-SWAP", "LINK-USDT-SWAP", "BREV-USDT-SWAP", "QTUM-USDT-SWAP", "TSLA-USDT-SWAP", "RAVE-USDT-SWAP", "CRO-USDT-SWAP", "ADA-USDT-SWAP"}
APP_START_TIME = time.time()


def _version_sort_key(name: str) -> tuple:
    value = str(name or '').lower().lstrip('v')
    parts = re.split(r'[^0-9]+', value)
    nums = [int(p) for p in parts if p.isdigit()]
    return tuple(nums) if nums else (0,)


def _find_previous_runtime_state_candidates() -> List[Path]:
    candidates: List[Path] = []
    parent = APP_DIR.parent
    try:
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            if child.resolve() == APP_DIR.resolve():
                continue
            if not child.name.lower().startswith('v'):
                continue
            state_path = child / 'logs' / 'runtime_state.json'
            if state_path.exists():
                candidates.append(state_path)
    except Exception:
        return []
    candidates.sort(key=lambda p: (_version_sort_key(p.parent.parent.name), p.stat().st_mtime), reverse=True)
    return candidates


def _load_runtime_state_payload(state_path: Path) -> dict:
    data = json.loads(state_path.read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else {}


def _migrate_previous_runtime_state_if_needed() -> Optional[dict]:
    if STATE_FILE.exists():
        return None
    for candidate in _find_previous_runtime_state_candidates():
        try:
            data = _load_runtime_state_payload(candidate)
            if not data:
                continue
            payload = dict(data)
            payload.setdefault('migrated_from', str(candidate))
            LOG_DIR.mkdir(exist_ok=True)
            STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return payload
        except Exception:
            continue
    return None


def _backup_runtime_state_file(reason: str) -> Optional[Path]:
    if not STATE_FILE.exists():
        return None
    try:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_reason = re.sub(r'[^a-zA-Z0-9_\-]+', '_', str(reason or 'issue')).strip('_') or 'issue'
        backup_path = LOG_DIR / f"runtime_state_{safe_reason}_{ts}.bak.json"
        shutil.copy2(STATE_FILE, backup_path)
        return backup_path
    except Exception:
        return None


def _coerce_state_mapping(value: object) -> Optional[dict]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        return dict(parsed) if isinstance(parsed, dict) else None
    return None


def _restore_position_state_map(raw_positions: object) -> tuple[Dict[str, PositionState], List[str]]:
    restored: Dict[str, PositionState] = {}
    issues: List[str] = []
    if not isinstance(raw_positions, dict):
        issues.append(f'positions_container_invalid:{type(raw_positions).__name__}')
        return restored, issues
    for inst_id, payload in raw_positions.items():
        inst_key = str(inst_id or '').upper().strip()
        if not inst_key or is_hidden_instrument(inst_key):
            continue
        mapping = _coerce_state_mapping(payload)
        if mapping is None:
            issues.append(f'position_payload_invalid:{inst_key}:{type(payload).__name__}')
            continue
        mapping.setdefault('inst_id', inst_key)
        try:
            restored[inst_key] = PositionState(**mapping)
        except Exception as exc:
            issues.append(f'position_payload_rejected:{inst_key}:{exc}')
    return restored, issues


def _restore_closed_trades(raw_closed_trades: object) -> tuple[List[ClosedTrade], List[str]]:
    restored: List[ClosedTrade] = []
    issues: List[str] = []
    if raw_closed_trades is None:
        return restored, issues
    if not isinstance(raw_closed_trades, list):
        issues.append(f'closed_trades_container_invalid:{type(raw_closed_trades).__name__}')
        return restored, issues
    for idx, payload in enumerate(raw_closed_trades):
        mapping = _coerce_state_mapping(payload)
        if mapping is None:
            issues.append(f'closed_trade_payload_invalid:{idx}:{type(payload).__name__}')
            continue
        inst_id = str(mapping.get('inst_id') or '').upper().strip()
        if inst_id and is_hidden_instrument(inst_id):
            continue
        try:
            restored.append(ClosedTrade(**mapping))
        except Exception as exc:
            issues.append(f'closed_trade_payload_rejected:{idx}:{exc}')
    return restored, issues
