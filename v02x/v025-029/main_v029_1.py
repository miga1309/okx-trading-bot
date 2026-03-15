# ============================================================
# OKX Turtle Bot
# Version: v029
# Date: 2026-03-12
# Based on: main_v028.py
#
# Changelog:
# - Built next major version on top of stable v028
# - Replaced plain text entry-context popup with chart dialog showing saved candles
# - Added Donchian breakout lines, entry/stop line, and Turtle unit-add levels in the popup
# - Kept persistent entry-context JSON and all v028 runtime improvements
# ============================================================

import csv
import json
import logging
import os
import sys
import threading
import time
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPoint, Qt, QThread, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPolygon, QPalette
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


APP_DIR = Path(__file__).resolve().parent
APP_VERSION = "v029_1"
WINDOW_ICON_PATH = APP_DIR / "turtle_traders_icon_v3.png"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
TRADE_CSV = LOG_DIR / "trades.csv"
ENGINE_STATS_FILE = LOG_DIR / "engine_stats.jsonl"
APP_LOG = LOG_DIR / "app.log"
HIDDEN_INSTRUMENTS = {"BREV-USDT-SWAP", "LINK-USDT-SWAP"}
HIDDEN_PREFIXES = ("BREV-",)

def is_hidden_instrument(inst_id: object) -> bool:
    value = str(inst_id or "").upper()
    return value in HIDDEN_INSTRUMENTS or any(value.startswith(prefix) for prefix in HIDDEN_PREFIXES)

STATE_FILE = LOG_DIR / "runtime_state.json"
ENTRY_CONTEXT_DIR = LOG_DIR / "entry_context"
ENTRY_CONTEXT_DIR.mkdir(exist_ok=True)


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
                background: #0f172a;
                color: #e5e7eb;
            }
            QGroupBox {
                font-weight: 700;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 10px;
                background: #111827;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #cbd5e1;
                background: #111827;
            }
            QLabel {
                color: #e5e7eb;
                background: transparent;
            }
            QLabel[card="true"] {
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 8px 10px;
            }
            QComboBox, QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox, QTableView {
                background: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 10px;
                selection-background-color: #1d4ed8;
                selection-color: #ffffff;
            }
            QComboBox {
                padding: 3px 7px;
                min-height: 24px;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                padding: 3px 7px;
                min-height: 24px;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
                background: #1f2937;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QComboBox QAbstractItemView {
                background: #111827;
                color: #f8fafc;
                selection-background-color: #1d4ed8;
                selection-color: #ffffff;
            }
            QTableView {
                gridline-color: #243041;
                alternate-background-color: #0b1220;
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
            }
            QTableView::item {
                padding: 4px;
            }
            QTextEdit {
                background: #0b1220;
                color: #e5e7eb;
                selection-background-color: #1d4ed8;
                selection-color: #ffffff;
                border: 1px solid #334155;
                border-radius: 12px;
            }
            QHeaderView::section {
                background: #1f2937;
                color: #cbd5e1;
                border: 1px solid #334155;
                padding: 6px;
                font-weight: 700;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background: #111827;
                border-radius: 12px;
            }
            QTabBar::tab {
                background: #172033;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-bottom: none;
                padding: 8px 14px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QTabBar::tab:selected {
                background: #1d4ed8;
                color: #ffffff;
            }
            QPushButton {
                padding: 6px 10px;
                border-radius: 10px;
                background: #1d4ed8;
                color: #ffffff;
                border: 1px solid #2563eb;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #1f2937;
                border-color: #334155;
            }
            QPushButton#toggleBotButton[running="true"] {
                background: #b91c1c;
                border: 1px solid #dc2626;
                color: #ffffff;
            }
            QPushButton#toggleBotButton[running="true"]:hover {
                background: #dc2626;
            }
            QPushButton#toggleBotButton[running="false"] {
                background: #059669;
                border: 1px solid #10b981;
                color: #ffffff;
            }
            QPushButton#toggleBotButton[running="false"]:hover {
                background: #10b981;
            }
        """
    return """
        QMainWindow, QWidget {
            background: #f3f6fb;
            color: #111827;
        }
        QGroupBox {
            font-weight: 700;
            color: #111827;
            border: 1px solid #d6dde8;
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 10px;
            background: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #334155;
            background: #ffffff;
        }
        QLabel {
            color: #111827;
            background: transparent;
        }
        QLabel[card="true"] {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d6dde8;
            border-radius: 12px;
            padding: 8px 10px;
        }
        QComboBox, QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox, QTableView {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d6dde8;
            border-radius: 10px;
            selection-background-color: #dbeafe;
            selection-color: #111827;
        }
        QComboBox {
            padding: 3px 7px;
            min-height: 24px;
        }
        QLineEdit, QDoubleSpinBox, QSpinBox {
            padding: 3px 7px;
            min-height: 24px;
        }
        QComboBox::drop-down {
            border: none;
            width: 26px;
            background: #eef2f7;
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #111827;
            selection-background-color: #dbeafe;
            selection-color: #111827;
        }
        QTableView {
            gridline-color: #e5e7eb;
            alternate-background-color: #f8fafc;
            background: #ffffff;
            color: #111827;
            border: 1px solid #d6dde8;
            border-radius: 12px;
        }
        QTableView::item {
            padding: 4px;
        }
        QTextEdit {
            background: #ffffff;
            color: #111827;
            selection-background-color: #dbeafe;
            selection-color: #111827;
            border: 1px solid #d6dde8;
            border-radius: 12px;
        }
        QHeaderView::section {
            background: #eff4fb;
            color: #1f2937;
            border: 1px solid #d6dde8;
            padding: 6px;
            font-weight: 700;
        }
        QTabWidget::pane {
            border: 1px solid #d6dde8;
            background: #ffffff;
            border-radius: 12px;
        }
        QTabBar::tab {
            background: #e8eef8;
            color: #334155;
            border: 1px solid #d6dde8;
            border-bottom: none;
            padding: 8px 14px;
            margin-right: 4px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }
        QTabBar::tab:selected {
            background: #2563eb;
            color: #ffffff;
        }
        QPushButton {
            padding: 6px 10px;
            border-radius: 10px;
            background: #2563eb;
            color: #ffffff;
            border: 1px solid #3b82f6;
            font-weight: 700;
        }
        QPushButton:hover {
            background: #3b82f6;
        }
        QPushButton:disabled {
            color: #9ba3af;
            background: #f6f7f9;
        }
        QPushButton#toggleBotButton[running="true"] {
            background: #dc2626;
            border: 1px solid #ef4444;
            color: #ffffff;
        }
        QPushButton#toggleBotButton[running="true"]:hover {
            background: #ef4444;
        }
        QPushButton#toggleBotButton[running="false"] {
            background: #059669;
            border: 1px solid #10b981;
            color: #ffffff;
        }
        QPushButton#toggleBotButton[running="false"]:hover {
            background: #10b981;
        }
    """
def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(APP_LOG, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


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
    balance_refresh_sec: int = 3
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
    min_channel_range_pct: float = 0.82
    min_atr_pct: float = 0.14
    min_body_to_range_ratio: float = 0.24
    min_efficiency_ratio: float = 0.15
    max_direction_flip_ratio: float = 0.72
    blacklist: List[str] = field(default_factory=lambda: ["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP", "LINK-USDT-SWAP"])

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    pyramid_second_unit_scale: float = 1.00
    pyramid_third_unit_scale: float = 1.00
    pyramid_fourth_unit_scale: float = 1.00
    pyramid_break_even_buffer_atr: float = 0.05
    pyramid_min_progress_atr: float = 0.45
    pyramid_min_body_ratio: float = 0.35
    pyramid_min_stop_distance_atr: float = 0.35
    breakout_buffer_atr: float = 0.00
    breakout_min_body_atr: float = 0.00
    breakout_close_near_extreme_ratio: float = 0.00
    breakout_min_range_expansion: float = 0.00
    breakout_max_prebreak_distance_atr: float = 999.0
    breakout_retest_invalid_ratio: float = 1.00
    breakout_volume_factor: float = 0.00
    flat_max_repeated_close_ratio: float = 0.68
    flat_max_inside_ratio: float = 0.74
    flat_max_wick_to_range_ratio: float = 0.72
    flat_min_channel_atr_ratio: float = 2.00
    flat_max_micro_pullback_ratio: float = 0.84
    cooldown_after_stop_bars: int = 6
    cooldown_min_seconds: int = 900
    cooldown_max_seconds: int = 21600
    reentry_recovery_atr: float = 0.90
    liquidity_max_spread_pct: float = 0.18
    liquidity_min_top_of_book_usdt: float = 1200.0
    liquidity_min_side_notional_usdt: float = 2500.0
    liquidity_min_24h_quote_volume: float = 2500000.0
    illiquid_block_hours: int = 2
    illiquid_soft_reject_cooldown_sec: int = 300
    illiquid_repeats_for_ban: int = 3
    max_open_positions_total: int = 8
    max_open_positions_per_side: int = 4


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

    def _calc_overlay_levels(self):
        payload = self.payload or {}
        candles = payload.get("candles") or []
        entry_price = self._safe_float(payload.get("entry_price"), 0.0)
        stop_price = self._safe_float(payload.get("stop_price"), 0.0)
        next_pyramid = self._safe_float(payload.get("next_pyramid_price"), 0.0)
        atr = self._safe_float(payload.get("atr"), 0.0)
        side = str(payload.get("side") or "long").lower()
        entry_period = int(payload.get("entry_period") or 0)
        add_unit_every_atr = self._safe_float(payload.get("add_unit_every_atr"), 0.5)

        channel_high = None
        channel_low = None
        if len(candles) >= max(2, entry_period + 1):
            ref_window = candles[-entry_period - 1:-1]
            try:
                channel_high = max(float(c[2]) for c in ref_window)
                channel_low = min(float(c[3]) for c in ref_window)
            except Exception:
                channel_high = None
                channel_low = None

        unit_levels = []
        if entry_price > 0 and atr > 0 and add_unit_every_atr > 0:
            step = atr * add_unit_every_atr
            sign = 1.0 if side == "long" else -1.0
            for idx in range(2, 5):
                unit_levels.append((idx, entry_price + sign * step * (idx - 1)))

        return {
            "entry_price": entry_price,
            "stop_price": stop_price,
            "next_pyramid": next_pyramid,
            "channel_high": channel_high,
            "channel_low": channel_low,
            "unit_levels": unit_levels,
            "side": side,
        }

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

        overlay = self._calc_overlay_levels()
        prices = []
        for _, op, hi, lo, cl in candles:
            prices.extend([hi, lo, op, cl])
        for key in ("entry_price", "stop_price", "next_pyramid", "channel_high", "channel_low"):
            val = overlay.get(key)
            if val is not None and val > 0:
                prices.append(float(val))
        for _, level in overlay.get("unit_levels", []):
            if level > 0:
                prices.append(float(level))
        if not prices:
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "Недостаточно данных для графика")
            return

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

        rendered = 0
        for i, candle in enumerate(candles):
            try:
                _, op, hi, lo, cl = candle
            except Exception:
                continue
            x = int(plot_left + step_x * i + step_x / 2)
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
            rendered += 1

        if rendered <= 1:
            line_pen = QPen(QColor(30, 144, 255))
            line_pen.setWidth(2)
            painter.setPen(line_pen)
            prev = None
            for i, (_, _op, _hi, _lo, cl) in enumerate(candles):
                x = int(plot_left + step_x * i + step_x / 2)
                y = self._price_to_y(cl, min_price, max_price, plot_top, plot_height)
                if prev is not None:
                    painter.drawLine(prev[0], prev[1], x, y)
                prev = (x, y)

        def draw_level(price, label, color, style=Qt.PenStyle.SolidLine):
            if price is None or price <= 0:
                return
            y = self._price_to_y(float(price), min_price, max_price, plot_top, plot_height)
            pen = QPen(color)
            pen.setStyle(style)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(plot_left, y, plot_right, y)
            painter.drawText(plot_right + 6, y + 4, label)

        accent = QColor(30, 144, 255)
        amber = QColor(255, 193, 7)
        purple = QColor(111, 66, 193)
        teal = QColor(32, 201, 151)

        draw_level(overlay.get("entry_price"), "Вход", accent)
        draw_level(overlay.get("stop_price"), "Стоп", bear_color)
        draw_level(overlay.get("next_pyramid"), "След. добор", amber, Qt.PenStyle.DashLine)
        if overlay.get("side") == "long":
            draw_level(overlay.get("channel_high"), "Пробой Donchian", purple, Qt.PenStyle.DotLine)
        else:
            draw_level(overlay.get("channel_low"), "Пробой Donchian", purple, Qt.PenStyle.DotLine)

        for idx, level in overlay.get("unit_levels", []):
            draw_level(level, f"Юнит {idx}", teal, Qt.PenStyle.DashDotLine)

        try:
            first_ts = candles[0][0] / 1000
            last_ts = candles[-1][0] / 1000
            painter.setPen(label_pen)
            painter.drawText(plot_left, plot_bottom + 18, datetime.fromtimestamp(first_ts).strftime("%d.%m %H:%M"))
            last_label = datetime.fromtimestamp(last_ts).strftime("%d.%m %H:%M")
            painter.drawText(plot_right - 80, plot_bottom + 18, last_label)
        except Exception:
            pass



class EntryContextDialog(QDialog):
    def __init__(self, payload: dict, context_file: str, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.context_file = context_file
        self.setWindowTitle(f"Контекст входа — {self.payload.get('inst_id', 'позиция')}")
        self.resize(980, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(
            f"{self.payload.get('inst_id', '—')} · {str(self.payload.get('side', '—')).upper()} · "
            f"{self.payload.get('system_name', '—')} · {self.payload.get('timeframe', '—')}"
        )
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        candles = self.payload.get("candles") or []
        chart_box = QFrame(self)
        chart_box.setFrameShape(QFrame.Shape.StyledPanel)
        chart_box.setFrameShadow(QFrame.Shadow.Raised)
        chart_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(8, 8, 8, 8)
        chart_layout.setSpacing(6)

        chart_title = QLabel(f"График входа · свечей: {len(candles)}")
        chart_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        chart_layout.addWidget(chart_title)

        chart = EntryContextChartWidget(self.payload, chart_box)
        chart_layout.addWidget(chart, 1)
        layout.addWidget(chart_box, 1)

        start_candle = "—"
        end_candle = "—"
        if candles:
            try:
                start_candle = datetime.fromtimestamp(int(candles[0][0]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                end_candle = datetime.fromtimestamp(int(candles[-1][0]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                start_candle = str(candles[0][0])
                end_candle = str(candles[-1][0])

        add_unit_every_atr = self.payload.get("add_unit_every_atr", 0.5)
        info = QTextEdit()
        info.setReadOnly(True)
        info.setMaximumHeight(210)
        info.setText(
            f"Инструмент: {self.payload.get('inst_id', '—')}\n"
            f"Сторона: {self.payload.get('side', '—')}\n"
            f"Система: {self.payload.get('system_name', '—')}\n"
            f"Таймфрейм: {self.payload.get('timeframe', '—')}\n"
            f"Цена входа: {float(self.payload.get('entry_price', 0.0)):.6f}\n"
            f"ATR: {float(self.payload.get('atr', 0.0)):.6f}\n"
            f"Стоп: {float(self.payload.get('stop_price', 0.0)):.6f}\n"
            f"Следующий добор: {float(self.payload.get('next_pyramid_price', 0.0)):.6f}\n"
            f"Шаг добора: {float(add_unit_every_atr):.2f} ATR\n"
            f"Qty базового юнита: {float(self.payload.get('qty', 0.0)):.6f}\n"
            f"Периоды Donchian: вход {self.payload.get('entry_period', '—')} / выход {self.payload.get('exit_period', '—')}\n"
            f"Режим: {self.payload.get('trade_mode', '—')}\n"
            f"Свечей сохранено: {len(candles)}\n"
            f"Диапазон свечей: {start_candle} → {end_candle}\n"
            f"Файл: {self.context_file}"
        )
        layout.addWidget(info, 0)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


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


class OkxGateway:
    COMPLIANCE_RESTRICTION_CODES = {"51155"}
    LOT_SIZE_ERROR_CODES = {"51121"}
    POSITION_LIMIT_ERROR_CODES = {"54031"}
    CLOSE_MARKET_LIMIT_ERROR_CODES = {"51108"}

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.account_api = Account.AccountAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.market_api = MarketData.MarketAPI(flag=cfg.flag)
        self.public_api = PublicData.PublicAPI(flag=cfg.flag)
        self.trade_api = Trade.TradeAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.instrument_cache: Dict[str, dict] = {}
        self.swap_ids: List[str] = []
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

    def get_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
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

    def get_ticker_last(self, inst_id: str) -> float:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return float(data[0]["last"])

    def get_ticker_data(self, inst_id: str) -> dict:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return data[0]

    def instrument_info(self, inst_id: str) -> dict:
        info = self.instrument_cache.get(inst_id)
        if not info:
            self.refresh_instruments()
            info = self.instrument_cache.get(inst_id)
        if not info:
            raise KeyError(f"Instrument not found: {inst_id}")
        return info

    def close_position(self, inst_id: str, note: str = "") -> dict:
        logging.info("Closing position %s. %s", inst_id, note)
        return self.trade_api.close_positions(instId=inst_id, mgnMode=self.cfg.td_mode)

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
        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)
        self.running = False
        self.lock = threading.Lock()
        self.position_state: Dict[str, PositionState] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.balance_history: List[dict] = []
        self._load_state()
        self.last_scan_started_at: Optional[float] = None
        self.last_scan_finished_at: Optional[float] = None
        self.last_positions_check_at: Optional[float] = None
        self.last_entry_scan_at: Optional[float] = None
        self.last_snapshot_emitted_at: Optional[float] = None
        self.blocked_instruments: Dict[str, str] = {}
        self.temp_blocked_until: Dict[str, float] = {}
        self.close_retry_after: Dict[str, float] = {}
        self.recent_stopouts: Dict[str, dict] = {}
        self.illiquid_instruments: Dict[str, float] = {}
        self.illiquid_rejections: Dict[str, dict] = {}
        self.telegram = TelegramNotifier(
            enabled=cfg.telegram_enabled,
            bot_token=cfg.telegram_bot_token,
            chat_id=cfg.telegram_chat_id,
        )
        self._manual_entry_event = threading.Event()
        self._manual_entry_allowed = False

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

    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "positions" in data:
                self.position_state = {k: PositionState(**v) for k, v in data.get("positions", {}).items()}
                self.closed_trades = [ClosedTrade(**x) for x in data.get("closed_trades", [])]
                self.balance_history = list(data.get("balance_history", []))[-2000:]
            else:
                # backward compatibility with old file that stored only positions dict
                self.position_state = {k: PositionState(**v) for k, v in data.items()}
                self.closed_trades = []
                self.balance_history = []
        except Exception as exc:
            logging.warning("Failed to load state: %s", exc)
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []

    def _save_state(self) -> None:
        payload = {
            "positions": {k: asdict(v) for k, v in self.position_state.items()},
            "closed_trades": [asdict(x) for x in self.closed_trades[-500:]],
            "balance_history": self.balance_history[-2000:],
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
            blacklist=list(self.cfg.blacklist),
        )
        self.status.emit("Бот запущен")
        self.log_line.emit(f"Торговый движок запущен (шаг: {self.cfg.timeframe}, режим: {self.cfg.trade_mode})")
        self._notify("✅ OKX Turtle Bot запущен")
        self.run_loop()

    def stop(self) -> None:
        self.running = False
        self.stats_logger.log(
            "bot_stopped",
            open_positions=len(self.position_state),
            closed_trades=len(self.closed_trades),
        )
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
                )
        removed = []
        for inst_id in list(self.position_state):
            if inst_id not in seen:
                removed.append(inst_id)
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
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:  # 1m/3m/5m
            return {
                "strict_min": 1.18,
                "strict_max": 0.88,
                "liquidity_min": 1.35,
                "liquidity_max_spread": 0.80,
                "lookback_bonus": 1.15,
            }
        if tf_sec <= 900:  # 15m
            return {
                "strict_min": 1.00,
                "strict_max": 1.00,
                "liquidity_min": 1.00,
                "liquidity_max_spread": 1.00,
                "lookback_bonus": 1.00,
            }
        if tf_sec <= 3600:  # 30m/1h
            return {
                "strict_min": 0.90,
                "strict_max": 1.08,
                "liquidity_min": 0.80,
                "liquidity_max_spread": 1.20,
                "lookback_bonus": 0.92,
            }
        return {  # 2h+
            "strict_min": 0.82,
            "strict_max": 1.18,
            "liquidity_min": 0.65,
            "liquidity_max_spread": 1.35,
            "lookback_bonus": 0.85,
        }

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

    def _check_liquidity(self, inst_id: str, price: float) -> tuple[bool, str]:
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception as exc:
            return False, f"нет ticker/ликвидности: {exc}"

        profile = self._tf_entry_profile()

        bid_px = float(ticker.get("bidPx") or 0.0)
        ask_px = float(ticker.get("askPx") or 0.0)
        bid_sz = float(ticker.get("bidSz") or 0.0)
        ask_sz = float(ticker.get("askSz") or 0.0)
        vol_24h = float(ticker.get("volCcy24h") or ticker.get("vol24h") or 0.0)

        if bid_px <= 0 or ask_px <= 0:
            return False, "пустой bid/ask"

        mid = (bid_px + ask_px) / 2.0
        spread_pct = ((ask_px - bid_px) / max(mid, 1e-12)) * 100.0

        max_spread_pct = self.cfg.liquidity_max_spread_pct * profile["liquidity_max_spread"]
        min_top_book = self.cfg.liquidity_min_top_of_book_usdt * profile["liquidity_min"]
        min_side_notional = self.cfg.liquidity_min_side_notional_usdt * profile["liquidity_min"]
        min_vol_24h = self.cfg.liquidity_min_24h_quote_volume * profile["liquidity_min"]

        best_bid_notional = bid_px * bid_sz
        best_ask_notional = ask_px * ask_sz

        if spread_pct > max_spread_pct:
            return False, f"широкий спред {spread_pct:.3f}%"
        if best_bid_notional < min_top_book or best_ask_notional < min_top_book:
            return False, f"слабый top-of-book {min(best_bid_notional, best_ask_notional):.0f} USDT"
        if min(best_bid_notional, best_ask_notional) < min_side_notional * 0.45:
            return False, f"слишком тонкий стакан {min(best_bid_notional, best_ask_notional):.0f} USDT"
        if vol_24h > 0 and vol_24h < min_vol_24h:
            return False, f"низкий 24h объём {vol_24h:.0f}"
        if abs(price - mid) / max(mid, 1e-12) > 0.0045:
            return False, "последняя цена далеко от mid"

        return True, "ok"

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

    def _recent_stopout_blocks_entry(self, inst_id: str, side: str, price: float) -> tuple[bool, str]:
        data = self.recent_stopouts.get(inst_id)
        if not data:
            return False, "ok"

        now_ts = time.time()
        if float(data.get("until", 0.0)) <= now_ts:
            self.recent_stopouts.pop(inst_id, None)
            return False, "ok"

        prev_side = str(data.get("side") or "")
        exit_price = float(data.get("exit_price") or 0.0)
        atr = float(max(data.get("atr") or 0.0, 1e-12))

        # Если пытаемся войти в ту же сторону слишком близко к свежему stop-out — блокируем.
        if prev_side == side:
            distance = abs(price - exit_price)
            if distance < atr * self.cfg.reentry_recovery_atr:
                remain = max(1, int(data["until"] - now_ts))
                return True, (
                    f"cooldown после ATR-стопа ещё активен {remain}s; "
                    f"цена отошла только на {distance / atr:.2f} ATR"
                )

        return False, "ok"

    def scan_markets(self) -> None:
        for inst_id in self.gateway.swap_ids:
            if not self.running:
                break
            if inst_id in self.cfg.blacklist or inst_id in self.blocked_instruments or is_hidden_instrument(inst_id):
                continue
            if inst_id in self.position_state:
                continue
            try:
                self.evaluate_entry(inst_id)
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка анализа входа: {exc}")
                logging.warning("Entry eval failed for %s: %s", inst_id, exc)


    def evaluate_entry(self, inst_id: str) -> None:
        profile = self._tf_entry_profile()
        max_entry_period = max(self.cfg.long_entry_period, self.cfg.short_entry_period)
        max_exit_period = max(self.cfg.long_exit_period, self.cfg.short_exit_period)

        lookback = int(max(
            max_entry_period,
            self.cfg.atr_period,
            max_exit_period,
            self.cfg.flat_lookback_candles,
        ) * profile["lookback_bonus"]) + 8

        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback)
        if len(candles) < lookback:
            return

        last = candles[-1]
        price = float(last[4])
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            return

        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            logging.info("%s: пропуск входа, illiquidity-filter без бана (%s)", inst_id, liquid_reason)
            return

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        last_high = float(last[2])
        last_low = float(last[3])

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

            # Классический Turtle-подход:
            if last_high >= long_level:
                signals.append({
                    "side": "long",
                    "level": long_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                })

            if last_low <= short_level:
                signals.append({
                    "side": "short",
                    "level": short_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                })

        if not signals:
            return

        # Приоритет у Turtle 55
        signals.sort(key=lambda s: (-s["entry_period"], 0 if s["side"] == "long" else 1))

        for signal in signals:
            side = signal["side"]
            level = float(signal["level"])
            system_name = str(signal["system_name"])

            if side == "long" and cooldown_blocked_long:
                logging.info("%s: %s long-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_long)
                continue

            if side == "short" and cooldown_blocked_short:
                logging.info("%s: %s short-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_short)
                continue

            # После прибыльной сделки Turtle 20 пропускаем, Turtle 55 оставляем.
            if int(signal["entry_period"]) == int(self.cfg.short_entry_period):
                skip_t20, skip_reason = self._skip_profitable_turtle20_reentry(inst_id)
                if skip_t20:
                    logging.info("%s: %s", inst_id, skip_reason)
                    continue

            ok, reason = self._confirm_breakout(candles, atr, side, level)
            if ok:
                signal_payload = {
                    "inst_id": inst_id,
                    "side": side,
                    "price": price,
                    "atr": atr,
                    "system_name": system_name,
                    "timeframe": self.cfg.timeframe,
                    "entry_period": signal["entry_period"],
                    "exit_period": signal["exit_period"],
                    "reason": reason,
                    "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
                }
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side=side,
                    price=price,
                    atr=atr,
                    system_name=system_name,
                    timeframe=self.cfg.timeframe,
                    entry_period=signal["entry_period"],
                    exit_period=signal["exit_period"],
                    reason=reason,
                    trade_mode=getattr(self.cfg, "trade_mode", "auto"),
                )
                if getattr(self.cfg, "trade_mode", "auto") == "manual":
                    if not self.request_manual_entry_approval(signal_payload):
                        self.stats_logger.log(
                            "entry_skipped_manual",
                            inst_id=inst_id,
                            side=side,
                            price=price,
                            atr=atr,
                            system_name=system_name,
                            timeframe=self.cfg.timeframe,
                            reason=reason,
                        )
                        return
                self.enter_position(inst_id, side, price, atr, system_name)
                return

            self.stats_logger.log(
                "entry_rejected",
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
            logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, reason)

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

        repeated_close_ratio = 0.0
        if len(closes) > 1:
            unchanged = sum(
                1 for i in range(1, len(closes))
                if abs(closes[i] - closes[i - 1]) <= max(price * 0.00005, atr * 0.03, 1e-12)
            )
            repeated_close_ratio = unchanged / (len(closes) - 1)

        candle_ranges = [max(float(c[2]) - float(c[3]), 1e-12) for c in window]
        body_ratios = [abs(float(c[4]) - float(c[1])) / rng for c, rng in zip(window, candle_ranges)]
        avg_body_ratio = sum(body_ratios) / len(body_ratios) if body_ratios else 0.0
        wick_ratios = [1.0 - br for br in body_ratios]
        avg_wick_ratio = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0.0

        inside_count = 0
        for i in range(1, len(window)):
            if window[i][2] <= window[i - 1][2] and window[i][3] >= window[i - 1][3]:
                inside_count += 1
        inside_ratio = inside_count / max(1, len(window) - 1)

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

        micro_pullbacks = 0
        for i in range(2, len(closes)):
            prev_move = closes[i - 1] - closes[i - 2]
            curr_move = closes[i] - closes[i - 1]
            if abs(prev_move) > 0 and abs(curr_move) > 0 and (prev_move > 0 > curr_move or prev_move < 0 < curr_move):
                if abs(curr_move) <= abs(prev_move) * 1.10:
                    micro_pullbacks += 1
        micro_pullback_ratio = micro_pullbacks / max(1, len(closes) - 2)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.75

        # совсем мёртвый рынок
        if channel_range_pct < self.cfg.min_channel_range_pct * 0.68 * strict_min:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}%"
        if atr_pct < self.cfg.min_atr_pct * 0.70 * strict_min:
            return True, f"крайне низкий ATR {atr_pct:.3f}%"
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * 0.82 * strict_min:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f}"

        hard_flags = []
        soft_flags = []

        if repeated_close_ratio >= self.cfg.flat_max_repeated_close_ratio * strict_max:
            hard_flags.append(f"повторяющиеся закрытия {repeated_close_ratio:.0%}")
        if inside_ratio >= self.cfg.flat_max_inside_ratio * strict_max:
            hard_flags.append(f"inside-bars {inside_ratio:.0%}")
        if flip_ratio > self.cfg.max_direction_flip_ratio * strict_max:
            hard_flags.append(f"пила {flip_ratio:.0%}")
        if micro_pullback_ratio > self.cfg.flat_max_micro_pullback_ratio * strict_max:
            hard_flags.append(f"микроретесты {micro_pullback_ratio:.0%}")

        if avg_body_ratio < self.cfg.min_body_to_range_ratio * strict_min:
            soft_flags.append(f"маленькие тела {avg_body_ratio:.2f}")
        if avg_wick_ratio > self.cfg.flat_max_wick_to_range_ratio * strict_max:
            soft_flags.append(f"много теней {avg_wick_ratio:.2f}")
        if efficiency_ratio < self.cfg.min_efficiency_ratio * strict_min:
            soft_flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if volume_dry:
            soft_flags.append("затухающий объём")

        score = len(hard_flags) * 2 + len(soft_flags)

        if score >= 4:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if len(hard_flags) >= 1 and len(soft_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * strict_min and efficiency_ratio < self.cfg.min_efficiency_ratio * 1.08 * strict_min:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"

    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str]:
        if len(candles) < 12:
            return False, "ok"

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)

        if swing_span <= atr * (1.8 * strict_min):
            false_breaks = 0
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
            if false_breaks >= 3:
                return True, f"серия ложных выносов ({false_breaks})"

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

        if base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * (2.4 * strict_min):
            return True, "слишком плотная база"

        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * (0.34 * strict_min))
        if close_cluster >= max(8, int(len(closes) * 0.74)):
            return True, "цена прилипла к центру диапазона"

        return False, "ok"


    def _confirm_breakout(self, candles: list, atr: float, side: str, level: float) -> tuple[bool, str]:
        """
        v025_2:
        Совместимый stub.
        Подтверждение пробоя сведено к самому факту выхода за канал.
        """
        if not candles:
            return False, "нет свечей"
        if atr <= 0:
            return False, "ATR недоступен"
        if side not in {"long", "short"}:
            return False, "неизвестная сторона"
        return True, "classic_turtle_breakout"

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

    def enter_position(self, inst_id: str, side: str, price: float, atr: float, system_name: str) -> None:
        account = self.gateway.get_account_balance()
        data = account.get("data", [])
        if not data:
            return
        total_eq = self._extract_total_usdt(account)
        available_eq = self._extract_available_usdt(account)
        if total_eq <= 0 or available_eq <= 0:
            return

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
            return
        info = self.gateway.instrument_info(inst_id)
        ct_val = float(info.get("ctVal") or 1.0)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)

        risk_amount = total_eq * (self.cfg.risk_per_trade_pct / 100.0)
        risk_per_contract = atr * ct_val * self.cfg.atr_stop_multiple
        if risk_per_contract <= 0 or price <= 0 or ct_val <= 0:
            return

        qty_by_risk = risk_amount / risk_per_contract
        max_notional = available_eq * (self.cfg.max_position_notional_pct / 100.0)
        qty_by_notional = max_notional / (price * ct_val)
        qty = min(qty_by_risk, qty_by_notional)
        if max_mkt_sz > 0:
            qty = min(qty, max_mkt_sz)
        qty = self.floor_to_step(qty, lot_sz)
        if qty < min_sz:
            return

        order_side = "buy" if side == "long" else "sell"
        resp = self.gateway.place_market_order(inst_id, order_side, qty)
        if resp.get("code") != "0":
            self._handle_order_rejection(inst_id, resp, "ордер")
            return

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

        entry_context_payload = self._build_entry_context_payload(inst_id, side, price, atr, stop_price, next_pyramid, system_name, qty)
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
        )
        self.position_state[inst_id] = state
        self._save_state()
        self.stats_logger.log("position_opened", inst_id=inst_id, side=side, qty=qty, price=price, atr=atr, stop_price=stop_price, system_name=system_name, timeframe=self.cfg.timeframe, balance_total=total_eq, balance_available=available_eq)
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

    def _build_entry_context_payload(self, inst_id: str, side: str, price: float, atr: float, stop_price: float, next_pyramid: float, system_name: str, qty: float) -> dict:
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

        return {
            "version": APP_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "inst_id": inst_id,
            "side": side,
            "timeframe": self.cfg.timeframe,
            "system_name": system_name,
            "entry_price": price,
            "atr": atr,
            "stop_price": stop_price,
            "next_pyramid_price": next_pyramid,
            "qty": qty,
            "entry_period": entry_period,
            "exit_period": exit_period,
            "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
            "add_unit_every_atr": getattr(self.cfg, "add_unit_every_atr", 0.5),
            "channel_high": channel_high,
            "channel_low": channel_low,
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

        state.stop_price = self.trailing_stop(state, state.atr, current_price)

        exit_window = candles[-state.exit_period:]
        exit_long_level = min(c[3] for c in exit_window)
        exit_short_level = max(c[2] for c in exit_window)

        stop_hit = (state.side == "long" and current_price <= state.stop_price) or (
            state.side == "short" and current_price >= state.stop_price
        )
        turtle_exit = (state.side == "long" and current_price <= exit_long_level) or (
            state.side == "short" and current_price >= exit_short_level
        )

        # v025_3:
        # ATR-стоп больше не игнорируем даже при символическом плюсе.
        if stop_hit:
            self.close_position(state, current_price, f"ATR стоп {self.cfg.atr_stop_multiple}N")
            return

        if turtle_exit:
            self.close_position(state, current_price, f"Канальный выход {state.exit_period} свечей")
            return

        self.try_pyramid(state, current_price, candles)
        self._save_state()

    def trailing_stop(self, state: PositionState, atr: float, last_close: float) -> float:
        if atr <= 0:
            return state.stop_price

        # v025_3:
        # После доборов не перетягиваем стоп слишком агрессивно.
        stop_multiple = float(self.cfg.atr_stop_multiple)
        if state.units >= 4:
            stop_multiple = min(stop_multiple, 1.80)
        elif state.units >= 3:
            stop_multiple = min(stop_multiple, 1.90)
        elif state.units >= 2:
            stop_multiple = min(stop_multiple, 2.00)

        if state.side == "long":
            candidate = last_close - stop_multiple * atr
            return max(state.stop_price, candidate)

        candidate = last_close + stop_multiple * atr
        return min(state.stop_price, candidate)

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

        # v025_3:
        # Сохраняем идею защиты прибыли, но не душим тренд слишком близким стопом.
        if state.side == "long":
            if state.units == 2:
                floor = state.avg_px - state.atr * 0.15
            elif state.units == 3:
                floor = state.avg_px + state.atr * 0.05
            else:
                floor = state.avg_px + state.atr * 0.20

            tightened = fill_price - max(state.atr * 1.80, 1e-12)
            state.stop_price = max(state.stop_price, floor, tightened)
        else:
            if state.units == 2:
                floor = state.avg_px + state.atr * 0.15
            elif state.units == 3:
                floor = state.avg_px - state.atr * 0.05
            else:
                floor = state.avg_px - state.atr * 0.20

            tightened = fill_price + max(state.atr * 1.80, 1e-12)
            state.stop_price = min(state.stop_price, floor, tightened)

    def try_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> None:
        if self.cfg.max_units_per_symbol > 0 and state.units >= self.cfg.max_units_per_symbol:
            return
        if state.atr <= 0:
            return
        should_add = (state.side == "long" and last_close >= state.next_pyramid_price) or (
            state.side == "short" and last_close <= state.next_pyramid_price
        )
        if not should_add:
            return

        allowed, reason = self._trend_confirms_pyramid(state, last_close, candles)
        if not allowed:
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason=reason, last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            self.log_line.emit(f"{state.inst_id}: добор пропущен — {reason}")
            return

        info = self.gateway.instrument_info(state.inst_id)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)

        base_unit_qty = float(state.base_unit_qty or 0.0)
        if base_unit_qty <= 0:
            base_unit_qty = float(state.qty or 0.0)
        if base_unit_qty <= 0:
            return

        scale = self._pyramid_unit_scale(state.units)
        add_qty = self.floor_to_step(base_unit_qty * scale, lot_sz)
        if max_mkt_sz > 0:
            add_qty = min(add_qty, self.floor_to_step(max_mkt_sz, lot_sz))
        if add_qty < min_sz:
            self.log_line.emit(
                f"{state.inst_id}: добор пропущен, допустимый размер меньше minSz "
                f"(base={base_unit_qty}, scale={scale}, maxMktSz={max_mkt_sz}, minSz={min_sz})"
            )
            return

        projected_total_qty = state.qty + add_qty
        if projected_total_qty <= 0:
            return
        projected_avg_px = ((state.avg_px * state.qty) + (last_close * add_qty)) / projected_total_qty

        # v025:
        # Убрано жёсткое требование сохранять 5%/10%/15% прибыли после добора.
        # Оно фактически блокировало pyramiding на большинстве инструментов.

        order_side = "buy" if state.side == "long" else "sell"
        attempt_qty = add_qty
        resp = None
        while attempt_qty >= min_sz:
            resp = self.gateway.place_market_order(state.inst_id, order_side, attempt_qty)
            if resp.get("code") == "0":
                add_qty = attempt_qty
                break

            code, message = self._extract_order_error(resp)
            safe_message = (message or "").strip()
            if code != "51202":
                self._handle_order_rejection(state.inst_id, resp, "добор")
                return

            next_qty = self.floor_to_step(attempt_qty / 2.0, lot_sz)
            if next_qty >= min_sz and next_qty < attempt_qty:
                self.log_line.emit(
                    f"{state.inst_id}: добор {attempt_qty} отклонён по лимиту market-ордера "
                    f"(51202), пробую меньший размер {next_qty}"
                )
                attempt_qty = next_qty
                continue

            self.log_line.emit(
                f"{state.inst_id}: добор не выполнен — даже уменьшенный объём превышает лимит "
                f"market-ордера ({safe_message})"
            )
            return

        if not resp or resp.get("code") != "0":
            return

        old_qty = state.qty
        prev_trigger_price = float(state.next_pyramid_price)
        state.qty += add_qty
        state.avg_px = ((state.avg_px * old_qty) + (last_close * add_qty)) / state.qty
        state.units += 1
        state.next_pyramid_price = (
            prev_trigger_price + self.cfg.add_unit_every_atr * state.atr
            if state.side == "long"
            else prev_trigger_price - self.cfg.add_unit_every_atr * state.atr
        )
        self._lock_profit_after_pyramid(state, last_close)
        added_units = max(0, state.units - 1)
        total_profit_pct = (
            ((last_close - state.avg_px) / state.avg_px * 100.0)
            if state.side == "long"
            else ((state.avg_px - last_close) / state.avg_px * 100.0)
        )
        self.stats_logger.log(
            "pyramid_added",
            inst_id=state.inst_id,
            side=state.side,
            add_qty=add_qty,
            total_qty=state.qty,
            units=state.units,
            added_units=added_units,
            fill_price=last_close,
            avg_price=state.avg_px,
            stop_price=state.stop_price,
            scale=scale,
            total_profit_pct=total_profit_pct,
            required_profit_pct=added_units * 5.0,
        )
        self.trade_logger.log(
            "PYRAMID",
            state.inst_id,
            state.side,
            add_qty,
            last_close,
            state.atr,
            state.stop_price,
            state.system_name,
            f"Добавлен unit #{state.units} scale={scale} total_profit_pct={total_profit_pct:.2f}%",
        )
        self.log_line.emit(
            f"{state.inst_id}: добавлен unit #{state.units}, qty+={add_qty}, "
            f"scale={scale:.2f}, pnl={total_profit_pct:.2f}%, "
            f"следующий добор={self._fmt_price(state.next_pyramid_price)}, "
            f"новый стоп={self._fmt_price(state.stop_price)}"
        )
        self._notify(
            f"➕ Добавлен юнит\n\n"
            f"Инструмент: {state.inst_id}\n"
            f"Сторона: {state.side.upper()}\n"
            f"Добавлено qty: {add_qty}\n"
            f"Всего qty: {state.qty}\n"
            f"Юнитов: {state.units}\n"
            f"Scale: {scale:.2f}\n"
            f"Новый стоп: {self._fmt_price(state.stop_price)}\n"
            f"Цена: {self._fmt_price(last_close)}"
        )
        self._save_state()
        self._emit_snapshot_safe()

    def close_position(self, state: PositionState, price: float, reason: str) -> None:
        resp = self.gateway.close_position(state.inst_id, reason)
        if resp.get("code") != "0":
            code, message = self._extract_order_error(resp)
            safe_message = (message or resp.get("msg") or str(resp)).strip()
            if code in OkxGateway.CLOSE_MARKET_LIMIT_ERROR_CODES:
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

        self.stats_logger.log("position_closed", inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason)
        self.trade_logger.log("CLOSE", state.inst_id, state.side, state.qty, price, state.atr, state.stop_price, state.system_name, reason)
        duration_sec = 0
        try:
            duration_sec = max(0, int((datetime.now() - datetime.strptime(state.entry_time, "%Y-%m-%d %H:%M:%S")).total_seconds()))
        except Exception:
            duration_sec = 0
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

    def emit_snapshot(self) -> None:
        bal = self.gateway.get_account_balance()
        data = bal.get("data", [{}])
        details = data[0].get("details", [{}]) if data else [{}]
        detail = details[0] if details else {}

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
        for item in self.balance_history:
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

        balance_total = float(data[0].get("totalEq") or 0.0) if data else 0.0
        balance_available = float(detail.get("availBal") or 0.0)
        frozen_value = float(detail.get("frozenBal") or 0.0)
        balance_used = frozen_value if frozen_value > 0 else max(balance_total - balance_available, 0.0)
        balance_point = {
            "time": now_full,
            "balance_total": balance_total,
            "balance_available": balance_available,
            "balance_used": balance_used,
        }
        last_point = self.balance_history[-1] if self.balance_history else None
        if (
            last_point
            and str(last_point.get("time", "")) == now_full
        ):
            self.balance_history[-1] = balance_point
        else:
            self.balance_history.append(balance_point)
        self.balance_history = self.balance_history[-2000:]
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
            "balance_history": self.balance_history[-2000:],
            "settings": {
                "account": "Основной" if self.cfg.flag == "0" else "Демо",
                "timeframe": self.cfg.timeframe,
                "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
                "risk_per_trade_pct": self.cfg.risk_per_trade_pct,
            },
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
        self.setMinimumHeight(220)

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

    def _display_pnl_slots(self) -> Tuple[List[float], int, float, float, str]:
        bucketed = self._bucket_points()
        actual_count = len(bucketed)
        if actual_count <= 0:
            return [0.0] * 30, 0, 0.0, 0.0, "ожидание"
        raw_values = [float(point.get("value", 0.0)) for point in bucketed]
        base_value = raw_values[0]
        pnl_actual = [v - base_value for v in raw_values]
        padded = ([0.0] * max(0, 30 - len(pnl_actual))) + pnl_actual
        padded = padded[-30:]
        current_pnl = pnl_actual[-1] if pnl_actual else 0.0
        current_pct = (current_pnl / base_value * 100.0) if abs(base_value) > 1e-12 else 0.0
        last_label = str(bucketed[-1].get("time", "—"))
        return padded, min(actual_count, 30), current_pnl, current_pct, last_label

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(8, 8, -8, -8)

        bg_color = QColor(12, 14, 18) if self.dark_theme else QColor(255, 255, 255)
        border_color = QColor(32, 37, 45) if self.dark_theme else QColor(225, 228, 235)
        muted_color = QColor(124, 132, 145) if self.dark_theme else QColor(128, 128, 128)
        pos_color = QColor(35, 199, 104)
        neg_color = QColor(239, 68, 68)
        grid_color = QColor(38, 45, 56) if self.dark_theme else QColor(234, 236, 240)

        painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 14, 14)

        bucketed = self._bucket_points()
        pnl_values, actual_count, current_pnl, current_pct, last_label = self._display_pnl_slots()
        visible_offset = max(0, len(pnl_values) - len(bucketed))

        # OKX-like header
        header_rect = rect.adjusted(16, 12, -16, -rect.height() + 56)
        pnl_color = pos_color if current_pnl >= 0 else neg_color
        painter.setPen(pnl_color)
        header_font = painter.font()
        header_font.setPointSize(15)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.drawText(header_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_pnl:+.2f} USDT")

        sub_rect = rect.adjusted(16, 36, -16, -rect.height() + 72)
        sub_font = painter.font()
        sub_font.setPointSize(10)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        tail = last_label if actual_count > 0 else "ожидание данных"
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_pct:+.2f}%  ·  {tail}")

        plot = rect.adjusted(18, 78, -18, -24)

        min_val = min(min(pnl_values), 0.0)
        max_val = max(max(pnl_values), 0.0)
        span = max_val - min_val
        pad = max(span * 0.18, 0.5)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        zero_y = value_to_y(0.0)

        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
        y_marks = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = int(plot.top() + plot.height() * frac)
            value = max_plot - (max_plot - min_plot) * frac
            y_marks.append((y, value))
            painter.drawLine(plot.left(), y, plot.right(), y)

        painter.setPen(muted_color)
        for y, value in y_marks:
            painter.drawText(plot.right() - 56, y - 2, f"{value:+.2f}")

        painter.setPen(QPen(QColor(110, 118, 132), 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot.left(), zero_y, plot.right(), zero_y)

        step_x = plot.width() / max(1, (len(pnl_values) - 1))
        x_positions = [plot.left() + i * step_x for i in range(len(pnl_values))]
        line_points = [(int(x), value_to_y(val)) for x, val in zip(x_positions, pnl_values)]
        line_color = pos_color if current_pnl >= 0 else neg_color
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


class StartWindow(QWidget):
    start_requested = pyqtSignal(BotConfig)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — параметры запуска")
        self.setMinimumWidth(520)
        self.selected_trade_mode = "auto"
        self._build_ui()
        self.apply_system_theme()

    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))

    def eventFilter(self, watched, event) -> bool:
        if watched is QApplication.instance() and event.type() in {QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange, QEvent.Type.ThemeChange}:
            QTimer.singleShot(0, self.apply_system_theme)
        return super().eventFilter(watched, event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.account_combo = QComboBox()
        self.account_combo.addItems(["Основной", "Демо"])
        self.account_combo.setCurrentIndex(1)
        form.addRow("Аккаунт:", self.account_combo)

        self.timeframe_combo = QComboBox()
        for code, label in TIMEFRAME_LABELS.items():
            self.timeframe_combo.addItem(f"{label} ({code})", code)
        self.timeframe_combo.setCurrentIndex(2)
        form.addRow("Шаг свечей:", self.timeframe_combo)

        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setDecimals(2)
        self.risk_spin.setRange(0.1, 5.0)
        self.risk_spin.setValue(1.0)
        self.risk_spin.setSuffix(" %")
        self.risk_spin.hide()

        defaults_hint = QLabel(
            "Параметры стратегии зафиксированы под Turtle v021: S1 20/10, S2 55/20, ATR 20, стоп 2N, усиленный anti-flat / anti-fake-breakout."
        )
        defaults_hint.setWordWrap(True)
        form.addRow("Стратегия:", defaults_hint)

        layout.addLayout(form)

        hint = QLabel(
            "Ключи API читаются из файла .env. Для демо обязательно используйте demo API key. "
            "В OKX демо-запросы должны идти в simulated trading окружение."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.start_button = None

    def set_trade_mode(self, mode: str) -> None:
        self.selected_trade_mode = "manual" if str(mode).lower() == "manual" else "auto"

    def build_config(self) -> BotConfig:
        load_dotenv(APP_DIR / ".env")
        api_key = os.getenv("OKX_API_KEY", "")
        secret_key = os.getenv("OKX_SECRET_KEY", "")
        passphrase = os.getenv("OKX_PASSPHRASE", "")
        telegram_enabled = os.getenv("TELEGRAM_ENABLED", "0").strip() == "1"
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        if not all([api_key, secret_key, passphrase]):
            raise RuntimeError("Создай файл .env рядом с main.py и заполни OKX_API_KEY / OKX_SECRET_KEY / OKX_PASSPHRASE")

        return BotConfig(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            flag="0" if self.account_combo.currentIndex() == 0 else "1",
            timeframe=self.timeframe_combo.currentData(),
            trade_mode=self.selected_trade_mode,
            risk_per_trade_pct=1.0,
            scan_interval_sec=5,
            position_check_interval_sec=2,
            snapshot_interval_sec=2,
            gui_refresh_ms=1000,
            long_entry_period=55,
            short_entry_period=20,
            long_exit_period=20,
            short_exit_period=10,
            atr_period=20,
            atr_stop_multiple=2.0,
            max_units_per_symbol=4,
            pyramid_second_unit_scale=1.0,
            pyramid_third_unit_scale=1.0,
            pyramid_fourth_unit_scale=1.0,
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            blacklist=["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP", "LINK-USDT-SWAP"],
        )

    def _emit_start(self) -> None:
        cfg = self.build_config()
        self.start_requested.emit(cfg)


class MainWindow(QMainWindow):
    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        stylesheet = build_app_stylesheet(self._is_dark_theme)
        self.setStyleSheet(stylesheet)
        if hasattr(self, "balance_chart") and self.balance_chart is not None:
            self.balance_chart.set_dark_theme(self._is_dark_theme)
        if hasattr(self, "table") and self.table is not None:
            self.table.viewport().update()
        if hasattr(self, "closed_table") and self.closed_table is not None:
            self.closed_table.viewport().update()
        if hasattr(self, "start_window") and self.start_window is not None:
            self.start_window.setStyleSheet(stylesheet)

    def eventFilter(self, watched, event) -> bool:
        app = QApplication.instance()
        event_type = event.type() if event is not None else None
        theme_events = {QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange}
        if hasattr(QEvent.Type, "ThemeChange"):
            theme_events.add(QEvent.Type.ThemeChange)
        if watched is app and event_type in theme_events:
            QTimer.singleShot(0, self.apply_system_theme)
        return super().eventFilter(watched, event)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION}")
        if WINDOW_ICON_PATH.exists():
            icon = QIcon(str(WINDOW_ICON_PATH))
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)
        self.setMinimumSize(1480, 930)
        self.engine: Optional[TurtleEngine] = None
        self.worker: Optional[WorkerThread] = None
        self.table_model = PositionTableModel()
        self.closed_table_model = ClosedTradesTableModel()
        self.latest_snapshot: Optional[dict] = None
        self.current_cfg: Optional[BotConfig] = None
        self._snapshot_refresh_interval_sec = 2
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._bot_running = False
        self._last_banlist_render: str = ""
        self._is_dark_theme = False
        self._bot_started_ts: Optional[float] = None
        self._pending_manual_signal: Optional[dict] = None
        self._manual_dialog_open = False
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.start_window = StartWindow()
        self.start_window.start_requested.connect(self.set_pending_config)
        self.start_window.setMaximumHeight(120)
        layout.addWidget(self.start_window, stretch=0)

        top_panels = QHBoxLayout()
        top_panels.setSpacing(6)

        metrics_box = QGroupBox("Статистика")
        metrics_layout = QGridLayout(metrics_box)
        self.lbl_status = QLabel("Статус: ожидание запуска")
        self.lbl_account = QLabel("Аккаунт: —")
        self.lbl_timeframe = QLabel("Таймфрейм: —")
        self.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_runtime = QLabel("Время работы: —")
        self.lbl_cycle_duration = QLabel("Цикл движка: —")
        self.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
        self.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
        self.lbl_trade_speed = QLabel("Сделок сегодня: 0 | Средняя длительность: —")
        labels = [
            self.lbl_status,
            self.lbl_account,
            self.lbl_timeframe,
            self.lbl_balance_summary,
            self.lbl_positions,
            self.lbl_runtime,
            self.lbl_cycle_duration,
            self.lbl_balance_trend,
            self.lbl_risk_panel,
            self.lbl_trade_speed,
        ]
        metrics_layout.setContentsMargins(6, 6, 6, 6)
        metrics_layout.setHorizontalSpacing(6)
        metrics_layout.setVerticalSpacing(4)

        for lbl in labels:
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)

        # v025_1:
        # Делаем строку баланса заметно шире, чтобы "Баланс / Использовано / Доступно"
        # не сжимались при длинных числах.
        self.lbl_balance_summary.setMinimumWidth(420)
        self.lbl_balance_summary.setWordWrap(False)

        metrics_layout.addWidget(self.lbl_status, 0, 0)
        metrics_layout.addWidget(self.lbl_account, 0, 1)
        metrics_layout.addWidget(self.lbl_timeframe, 0, 2)

        metrics_layout.addWidget(self.lbl_balance_summary, 1, 0, 1, 2)
        metrics_layout.addWidget(self.lbl_positions, 1, 2)

        metrics_layout.addWidget(self.lbl_runtime, 2, 0)
        metrics_layout.addWidget(self.lbl_cycle_duration, 2, 1)
        metrics_layout.addWidget(self.lbl_balance_trend, 2, 2)

        metrics_layout.addWidget(self.lbl_risk_panel, 3, 0, 1, 2)
        metrics_layout.addWidget(self.lbl_trade_speed, 3, 2)
        balance_chart_header = QGridLayout()
        balance_chart_header.setContentsMargins(0, 2, 0, 2)
        balance_chart_header.setHorizontalSpacing(10)
        balance_chart_header.setVerticalSpacing(6)
        self.lbl_balance_chart_title = QLabel("PnL за сегодня")
        self.lbl_balance_chart_title.setProperty("card", "true")
        self.lbl_balance_chart_title.setMinimumHeight(36)
        balance_chart_header.addWidget(self.lbl_balance_chart_title, 0, 0)
        self.balance_chart_step_combo = QComboBox()
        self.balance_chart_step_combo.addItem("1 минута", "1m")
        self.balance_chart_step_combo.addItem("5 минут", "5m")
        self.balance_chart_step_combo.addItem("15 минут", "15m")
        self.balance_chart_step_combo.addItem("30 минут", "30m")
        self.balance_chart_step_combo.addItem("1 час", "1H")
        self.balance_chart_step_combo.addItem("1 день", "1D")
        self.balance_chart_step_combo.setCurrentIndex(0)
        self.balance_chart_step_combo.setMinimumWidth(150)
        self.balance_chart_step_combo.currentIndexChanged.connect(self.on_balance_chart_step_changed)
        balance_chart_header.addWidget(self.balance_chart_step_combo, 0, 1)
        self.lbl_balance_step = QLabel("Шаг: 1m")
        self.lbl_balance_step.setProperty("card", "true")
        self.lbl_balance_step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_balance_step.setMinimumHeight(36)
        balance_chart_header.addWidget(self.lbl_balance_step, 0, 2)
        self.lbl_balance_points = QLabel("Показано значений: 0/30")
        self.lbl_balance_points.setProperty("card", "true")
        self.lbl_balance_points.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_balance_points.setMinimumHeight(36)
        balance_chart_header.addWidget(self.lbl_balance_points, 0, 3)
        balance_chart_header.setColumnStretch(0, 2)
        balance_chart_header.setColumnStretch(1, 0)
        balance_chart_header.setColumnStretch(2, 1)
        balance_chart_header.setColumnStretch(3, 1)
        metrics_layout.addLayout(balance_chart_header, 5, 0, 1, 3)
        self.balance_chart = BalanceChartWidget()
        self.balance_chart.setMinimumHeight(180)
        self.balance_chart.setMaximumHeight(240)
        metrics_layout.addWidget(self.balance_chart, 6, 0, 1, 3)
        top_panels.addWidget(metrics_box, 4)

        analytics_box = QGroupBox("Блок аналитики")
        analytics_layout = QGridLayout(analytics_box)
        self.lbl_open_pnl = QLabel("Open PnL: 0")
        self.lbl_avg_open = QLabel("Средний PnL %: 0")
        self.lbl_best = QLabel("Лучший PnL %: 0")
        self.lbl_worst = QLabel("Худший PnL %: 0")
        self.lbl_long_short = QLabel("Long/Short: 0 / 0")
        self.lbl_realized = QLabel("Реализованный PnL: 0")
        self.lbl_closed_stats = QLabel("Закрытых сделок: 0")
        self.lbl_winrate = QLabel("Winrate: 0%")
        self.lbl_turtle_regime = QLabel("Turtle-индикатор: —")

        analytics_layout.setContentsMargins(6, 6, 6, 6)
        analytics_layout.setHorizontalSpacing(6)
        analytics_layout.setVerticalSpacing(4)

        analytics_cards = [
            self.lbl_open_pnl,
            self.lbl_avg_open,
            self.lbl_best,
            self.lbl_worst,
            self.lbl_long_short,
            self.lbl_realized,
            self.lbl_closed_stats,
            self.lbl_winrate,
        ]
        for lbl in analytics_cards:
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)

        self.lbl_turtle_regime.setProperty("card", "true")
        self.lbl_turtle_regime.setMinimumHeight(30)
        self.lbl_turtle_regime.setMaximumHeight(38)
        self.lbl_turtle_regime.setMinimumWidth(420)
        self.lbl_turtle_regime.setWordWrap(False)

        analytics_layout.addWidget(self.lbl_open_pnl, 0, 0)
        analytics_layout.addWidget(self.lbl_avg_open, 0, 1)
        analytics_layout.addWidget(self.lbl_best, 1, 0)
        analytics_layout.addWidget(self.lbl_worst, 1, 1)
        analytics_layout.addWidget(self.lbl_long_short, 2, 0)
        analytics_layout.addWidget(self.lbl_realized, 2, 1)
        analytics_layout.addWidget(self.lbl_closed_stats, 3, 0)
        analytics_layout.addWidget(self.lbl_winrate, 3, 1)

        # v025_1:
        # Turtle-индикатор делаем шире во всю строку.
        analytics_layout.addWidget(self.lbl_turtle_regime, 4, 0, 1, 2)

        top_panels.addWidget(analytics_box, 2)
        layout.addLayout(top_panels, stretch=0)

        self.filter_text = None
        self.filter_side = None
        self.filter_pnl = None

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.toggle_button = QPushButton("Запустить бота")
        self.toggle_button.setObjectName("toggleBotButton")
        self.toggle_button.clicked.connect(self.toggle_engine)
        button_row.addWidget(self.toggle_button)


        self.lbl_blocked_count = QLabel("Блокировок: 0")
        self.lbl_blocked_count.setProperty("card", "true")
        self.lbl_blocked_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(self.lbl_blocked_count)

        self.mode_switch_toggle = QPushButton()
        self.mode_switch_toggle.setCheckable(True)
        self.mode_switch_toggle.clicked.connect(self.on_trade_mode_changed)
        self.mode_switch_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_switch_toggle.setMinimumWidth(170)
        self.mode_switch_toggle.setMinimumHeight(34)
        button_row.addWidget(self.mode_switch_toggle)

        self.btn_clear_bans = QPushButton("Сбросить бан-лист")
        self.btn_clear_bans.clicked.connect(self.clear_ban_lists)
        button_row.addWidget(self.btn_clear_bans)

        button_row.addStretch(1)
        layout.addLayout(button_row, stretch=0)

        self.tabs = QTabWidget()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.show_open_position_context)
        self.tabs.addTab(self.table, "Открытые позиции")

        self.closed_table = QTableView()
        self.closed_table.setModel(self.closed_table_model)
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.closed_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.closed_table, "Закрытые сделки")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.tabs.addTab(self.log_text, "Лог работы")

        self.blocked_table = QTableWidget()
        self.blocked_table.setColumnCount(4)
        self.blocked_table.setHorizontalHeaderLabels(["Инструмент", "Тип", "Причина", "Осталось"])
        self.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.blocked_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.blocked_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.blocked_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.blocked_table, "Бан-лист")

        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, stretch=14)

        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self._on_gui_timer_tick)
        self.gui_timer.start(1000)

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
            candles = payload.get("candles") or []
            start_candle = candles[0][0] if candles else "—"
            end_candle = candles[-1][0] if candles else "—"
            text = (
                f"Инструмент: {payload.get('inst_id', '—')}\n"
                f"Сторона: {payload.get('side', '—')}\n"
                f"Система: {payload.get('system_name', '—')}\n"
                f"Таймфрейм: {payload.get('timeframe', '—')}\n"
                f"Цена входа: {float(payload.get('entry_price', 0.0)):.6f}\n"
                f"ATR: {float(payload.get('atr', 0.0)):.6f}\n"
                f"Стоп: {float(payload.get('stop_price', 0.0)):.6f}\n"
                f"Следующий добор: {float(payload.get('next_pyramid_price', 0.0)):.6f}\n"
                f"Qty базового юнита: {float(payload.get('qty', 0.0)):.6f}\n"
                f"Периоды Donchian: вход {payload.get('entry_period', '—')} / выход {payload.get('exit_period', '—')}\n"
                f"Режим: {payload.get('trade_mode', '—')}\n"
                f"Свечей сохранено: {len(candles)}\n"
                f"Диапазон свечей: {start_candle} → {end_candle}\n\n"
                f"Файл: {context_file}"
            )
            QMessageBox.information(self, "Контекст входа", text)
        except Exception as exc:
            QMessageBox.warning(self, "Контекст входа", f"Не удалось открыть контекст входа: {exc}")

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
            self.lbl_blocked_count.setText(f"Блокировок: {len(rows)}")

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

    def clear_ban_lists(self) -> None:
        if self.engine is None:
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
            if hasattr(self, "blocked_table"):
                self.blocked_table.setRowCount(1)
                self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 2, QTableWidgetItem("Бан-лист очищен."))
                self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))
            self.append_log("Бан-лист очищен (движок ещё не запущен)")
            return

        for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections"):
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

    def _sync_toggle_button_state(self) -> None:
        if not hasattr(self, "toggle_button"):
            return
        if self._bot_running:
            self.toggle_button.setText("Остановить бота")
            self.toggle_button.setProperty("running", True)
        else:
            self.toggle_button.setText("Запустить бота")
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

    def on_snapshot(self, payload: dict) -> None:
        self.latest_snapshot = payload
        self.lbl_account.setText(f"Аккаунт: {payload['settings']['account']}")
        self.lbl_timeframe.setText(f"Таймфрейм: {payload['settings']['timeframe']}")
        mode = payload.get('settings', {}).get('trade_mode', getattr(self.current_cfg, 'trade_mode', 'auto'))
        self._apply_trade_mode_to_controls(mode)
        self.lbl_balance_summary.setText(
            f"Баланс: {payload['balance_total']:.0f} | "
            f"Использовано: {payload.get('balance_used', 0.0):.0f} | "
            f"Доступно: {payload['balance_available']:.0f}"
        )
        self.lbl_positions.setText(f"Открытых позиций: {len(payload['open_positions'])}")
        engine_info = payload.get("engine", {})
        cycle_duration = float(engine_info.get('last_cycle_duration_sec', 0.0) or 0.0)
        self.lbl_cycle_duration.setText(f"Цикл движка: {cycle_duration:.2f} сек")
        if cycle_duration > 10:
            self.lbl_cycle_duration.setStyleSheet("color: #b42318; font-weight: 700;")
        elif cycle_duration >= 5:
            self.lbl_cycle_duration.setStyleSheet("color: #b26a00; font-weight: 700;")
        else:
            self.lbl_cycle_duration.setStyleSheet("color: #0b7a28; font-weight: 700;")

        analytics = payload.get("analytics", {})
        self.lbl_open_pnl.setText(f"Open PnL: {analytics.get('open_pnl', 0.0):.4f}")
        self.lbl_avg_open.setText(f"Средний PnL %: {analytics.get('avg_open_pnl_pct', 0.0):.2f}%")
        self.lbl_best.setText(f"Лучший PnL %: {analytics.get('best_open_pnl_pct', 0.0):.2f}%")
        self.lbl_worst.setText(f"Худший PnL %: {analytics.get('worst_open_pnl_pct', 0.0):.2f}%")
        self.lbl_long_short.setText(f"Long/Short: {analytics.get('long_count', 0)} / {analytics.get('short_count', 0)}")
        self.lbl_realized.setText(f"Реализованный PnL: {analytics.get('realized_pnl', 0.0):.4f}")
        self.lbl_closed_stats.setText(f"Закрытых сделок: {analytics.get('closed_count', 0)}")
        self.lbl_winrate.setText(f"Winrate: {analytics.get('winrate', 0.0):.2f}% ({analytics.get('wins', 0)}/{max(1, analytics.get('closed_count', 0))})")
        self.lbl_balance_trend.setText(f"Изменение баланса: Сегодня {analytics.get('day_change_pct', 0.0):+.2f}% | 7 дней {analytics.get('week_change_pct', 0.0):+.2f}%")
        self.lbl_risk_panel.setText(f"Использовано риска: {analytics.get('used_risk_pct', 0.0):.2f}% / {analytics.get('max_risk_budget_pct', 0.0):.2f}%")
        self.lbl_trade_speed.setText(f"Сделок сегодня: {analytics.get('trades_today', 0)} | Средняя длительность: {format_duration(analytics.get('avg_duration_sec', 0))}")

        regime_label = analytics.get('turtle_regime_label', '—')
        regime_score = analytics.get('turtle_regime_score', 0)
        regime_inst = analytics.get('turtle_regime_instrument', '—')
        regime_channel = analytics.get('turtle_regime_channel_atr', 0.0)
        regime_eff = analytics.get('turtle_regime_efficiency', 0.0)
        regime_atr_pct = analytics.get('turtle_regime_atr_pct', 0.0)
        self.lbl_turtle_regime.setText(
            f"Turtle-индикатор: {regime_label} | score {regime_score}/4 | "
            f"{regime_inst} | ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%"
        )
        if regime_label == "Трендовый":
            self.lbl_turtle_regime.setStyleSheet("color: #16a34a; font-weight: 700;")
        elif regime_label == "Нейтральный":
            self.lbl_turtle_regime.setStyleSheet("color: #d97706; font-weight: 700;")
        elif regime_label == "Флэт":
            self.lbl_turtle_regime.setStyleSheet("color: #dc2626; font-weight: 700;")
        else:
            self.lbl_turtle_regime.setStyleSheet("")

        self._apply_status_style(self.lbl_open_pnl, analytics.get('open_pnl', 0.0))
        self._apply_status_style(self.lbl_avg_open, analytics.get('avg_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_best, analytics.get('best_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_worst, analytics.get('worst_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_realized, analytics.get('realized_pnl', 0.0))
        self._apply_status_style(self.lbl_winrate, analytics.get('winrate', 0.0), percent=True)
        self._apply_status_style(self.lbl_balance_trend, analytics.get('day_change_pct', 0.0), percent=True)
        balance_history = payload.get('balance_history', [])
        closed_markers = []
        for trade in payload.get('closed_trades', []):
            ts = str(trade.get('time', ''))
            if len(ts) >= 19:
                bucket_time = ts[11:19] if self.balance_chart_step_combo.currentData() != '1D' else ts[5:10]
            else:
                bucket_time = ts
            closed_markers.append({'bucket_time': bucket_time, 'pnl': trade.get('pnl', 0.0)})
        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
        shown_points = len(self.balance_chart._bucket_points()) if hasattr(self.balance_chart, '_bucket_points') else 0
        self.lbl_balance_points.setText(f"Показано значений: {shown_points}/30")

        self.apply_filters()

    def on_balance_chart_step_changed(self, *_args) -> None:
        if not self.latest_snapshot:
            return
        balance_history = self.latest_snapshot.get("balance_history", [])
        closed_markers = []
        for trade in self.latest_snapshot.get('closed_trades', []):
            ts = str(trade.get('time', ''))
            bucket_time = ts[11:19] if self.balance_chart_step_combo.currentData() != '1D' and len(ts) >= 19 else (ts[5:10] if len(ts) >= 10 else ts)
            closed_markers.append({'bucket_time': bucket_time, 'pnl': trade.get('pnl', 0.0)})
        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
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
        if "BREV-" in upper_message or "LINK-USDT" in upper_message:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {message}")
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
            self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 700;")
        elif "остановлен" in lower:
            self._bot_running = False
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 700;")
        else:
            self.lbl_status.setStyleSheet("")
        self._sync_toggle_button_state()
        self.append_log(message)

    def on_error(self, message: str) -> None:
        self.append_log(message)

def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
