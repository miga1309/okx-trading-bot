import csv
import json
import logging
import sys
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette

APP_DIR = Path(__file__).resolve().parent
APP_VERSION = "v0.21"
WINDOW_ICON_PATH = APP_DIR / "turtle_traders_icon_v3.png"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
TRADE_CSV = LOG_DIR / "trades.csv"
ENGINE_STATS_FILE = LOG_DIR / "engine_stats.jsonl"
APP_LOG = LOG_DIR / "app.log"
HIDDEN_INSTRUMENTS = {"BREV-USDT-SWAP"}
HIDDEN_PREFIXES = ("BREV-",)
STATE_FILE = LOG_DIR / "runtime_state.json"
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

def is_hidden_instrument(inst_id: object) -> bool:
    value = str(inst_id or "").upper()
    return value in HIDDEN_INSTRUMENTS or any(value.startswith(prefix) for prefix in HIDDEN_PREFIXES)

def format_clock(dt: Optional[datetime]) -> str:
    if not dt:
        return "--:--:--"
    try:
        return dt.strftime("%H:%M:%S")
    except Exception:
        return "--:--:--"

def format_time_string(value: object, default: str = "--:--:--") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except Exception:
            pass
    if " " in text:
        maybe_time = text.split(" ")[-1]
        if len(maybe_time) >= 8:
            return maybe_time[:8]
    if "T" in text:
        maybe_time = text.split("T")[-1]
        if len(maybe_time) >= 8:
            return maybe_time[:8]
    if len(text) >= 8 and text[2] == ":" and text[5] == ":":
        return text[:8]
    return default

def format_duration(seconds: int) -> str:
    try:
        total = int(max(0, seconds))
    except Exception:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}д {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def gradient_pnl_color(pnl_pct: float) -> QColor:
    try:
        value = float(pnl_pct)
    except Exception:
        value = 0.0

    if abs(value) < 1e-9:
        return QColor(255, 255, 255)

    if value > 0:
        intensity = min(1.0, value / 5.0)
        r = int(255 * (1.0 - intensity * 0.55))
        g = 255
        b = int(255 * (1.0 - intensity * 0.75))
        return QColor(r, g, b)

    intensity = min(1.0, abs(value) / 5.0)
    r = 255
    g = int(255 * (1.0 - intensity * 0.75))
    b = int(255 * (1.0 - intensity * 0.75))
    return QColor(r, g, b)

def detect_is_dark_theme() -> bool:
    app = QApplication.instance()
    if app is None:
        return False
    pal = app.palette()
    window_color = pal.color(QPalette.ColorRole.Window)
    return window_color.lightness() < 128

def build_app_stylesheet(dark: bool) -> str:
    if dark:
        return """
        QWidget {
            background-color: #1e1e1e;
            color: #e6e6e6;
            font-size: 12px;
        }
        QMainWindow {
            background-color: #1e1e1e;
        }
        QGroupBox {
            border: 1px solid #3a3a3a;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            background-color: #252526;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #ffffff;
        }
        QLabel {
            color: #e6e6e6;
        }
        QPushButton {
            background-color: #2d2d30;
            border: 1px solid #3f3f46;
            border-radius: 4px;
            padding: 6px 10px;
            color: #ffffff;
        }
        QPushButton:hover {
            background-color: #3a3a3f;
        }
        QPushButton:pressed {
            background-color: #45454a;
        }
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #7a7a7a;
            border: 1px solid #333333;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
            background-color: #2b2b2b;
            color: #f0f0f0;
            border: 1px solid #4c4c4c;
            border-radius: 4px;
            padding: 4px;
            selection-background-color: #4c78ff;
        }
        QComboBox QAbstractItemView {
            background-color: #2b2b2b;
            color: #f0f0f0;
            selection-background-color: #4c78ff;
            border: 1px solid #4c4c4c;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #ffffff;
            padding: 6px;
            border: 1px solid #444444;
            font-weight: bold;
        }
        QTableView {
            background-color: #1f1f1f;
            alternate-background-color: #262626;
            gridline-color: #3a3a3a;
            selection-background-color: #3d5a80;
            selection-color: #ffffff;
            border: 1px solid #3a3a3a;
        }
        QTextEdit {
            background-color: #1f1f1f;
        }
        QTabWidget::pane {
            border: 1px solid #3a3a3a;
            background-color: #1e1e1e;
        }
        QTabBar::tab {
            background: #2d2d30;
            color: #dddddd;
            padding: 8px 12px;
            border: 1px solid #3a3a3a;
            border-bottom: none;
            min-width: 80px;
        }
        QTabBar::tab:selected {
            background: #1e1e1e;
            color: #ffffff;
        }
        QTabBar::tab:hover {
            background: #38383d;
        }
        """
    return """
    QWidget {
        background-color: #f6f7fb;
        color: #202124;
        font-size: 12px;
    }
    QMainWindow {
        background-color: #f6f7fb;
    }
    QGroupBox {
        border: 1px solid #d0d7de;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        background-color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
        color: #202124;
    }
    QLabel {
        color: #202124;
    }
    QPushButton {
        background-color: #ffffff;
        border: 1px solid #c9ced6;
        border-radius: 4px;
        padding: 6px 10px;
        color: #202124;
    }
    QPushButton:hover {
        background-color: #f0f3f8;
    }
    QPushButton:pressed {
        background-color: #e7ebf3;
    }
    QPushButton:disabled {
        background-color: #f5f5f5;
        color: #a0a0a0;
        border: 1px solid #dddddd;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
        background-color: #ffffff;
        color: #202124;
        border: 1px solid #c9ced6;
        border-radius: 4px;
        padding: 4px;
        selection-background-color: #b8d6ff;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #202124;
        selection-background-color: #b8d6ff;
        border: 1px solid #c9ced6;
    }
    QHeaderView::section {
        background-color: #eef2f7;
        color: #202124;
        padding: 6px;
        border: 1px solid #d6dbe3;
        font-weight: bold;
    }
    QTableView {
        background-color: #ffffff;
        alternate-background-color: #f8fbff;
        gridline-color: #e3e8ef;
        selection-background-color: #d6e8ff;
        selection-color: #202124;
        border: 1px solid #d0d7de;
    }
    QTextEdit {
        background-color: #ffffff;
    }
    QTabWidget::pane {
        border: 1px solid #d0d7de;
        background-color: #f6f7fb;
    }
    QTabBar::tab {
        background: #e9eef5;
        color: #202124;
        padding: 8px 12px;
        border: 1px solid #d0d7de;
        border-bottom: none;
        min-width: 80px;
    }
    QTabBar::tab:selected {
        background: #ffffff;
        color: #111111;
    }
    QTabBar::tab:hover {
        background: #dde6f2;
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
    max_position_notional_pct: float = 2.0
    long_entry_period: int = 55
    short_entry_period: int = 20
    long_exit_period: int = 20
    short_exit_period: int = 10
    atr_period: int = 20
    atr_stop_multiple: float = 2.0
    add_unit_every_atr: float = 0.5
    max_units_per_symbol: int = 0
    snapshot_interval_sec: int = 2
    gui_refresh_ms: int = 1000
    flat_lookback_candles: int = 36
    min_channel_range_pct: float = 1.0
    min_atr_pct: float = 0.18
    min_body_to_range_ratio: float = 0.28
    min_efficiency_ratio: float = 0.18
    max_direction_flip_ratio: float = 0.65
    blacklist: List[str] = field(default_factory=lambda: ["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP"])

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    use_pos_side: bool = False
    pyramid_second_unit_scale: float = 0.75
    pyramid_third_unit_scale: float = 0.50
    pyramid_fourth_unit_scale: float = 0.25
    pyramid_break_even_buffer_atr: float = 0.05
    pyramid_min_progress_atr: float = 0.60
    pyramid_min_body_ratio: float = 0.35
    pyramid_min_stop_distance_atr: float = 0.80


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