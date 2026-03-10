import logging
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Optional

from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QIcon
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
    QSpinBox,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from dotenv import load_dotenv

from app_core import (
    APP_VERSION,
    TIMEFRAME_LABELS,
    WINDOW_ICON_PATH,
    BotConfig,
    build_app_stylesheet,
    detect_is_dark_theme,
    format_clock,
)
from engine import TurtleEngine
from gui_models import ClosedTradesTableModel, PositionTableModel
from gui_widgets import BalanceChartWidget, WorkerThread

class StartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Traders Bot {APP_VERSION} — запуск")
        self.resize(560, 620)

        self._dark_theme = detect_is_dark_theme()
        self.setStyleSheet(build_app_stylesheet(self._dark_theme))

        layout = QVBoxLayout(self)

        form_box = QGroupBox("Параметры запуска")
        form = QFormLayout(form_box)

        load_dotenv()

        self.api_key = QLineEdit()
        self.api_key.setText(os.getenv("OKX_API_KEY", "").strip())

        self.secret_key = QLineEdit()
        self.secret_key.setText(os.getenv("OKX_SECRET_KEY", "").strip())

        self.passphrase = QLineEdit()
        self.passphrase.setText(os.getenv("OKX_PASSPHRASE", "").strip())

        self.flag = QComboBox()
        self.flag.addItems(["1", "0"])
        self.flag.setCurrentText(os.getenv("OKX_FLAG", "1").strip() or "1")

        self.timeframe = QComboBox()
        self.timeframe.addItems(["1m", "5m", "15m", "30m", "1H", "1D"])
        self.timeframe.setCurrentText(os.getenv("BOT_TIMEFRAME", "15m").strip() or "15m")

        self.leverage = QSpinBox()
        self.leverage.setRange(1, 100)
        self.leverage.setValue(int(os.getenv("BOT_LEVERAGE", "1") or 1))

        self.scan_interval = QSpinBox()
        self.scan_interval.setRange(1, 3600)
        self.scan_interval.setValue(int(os.getenv("BOT_SCAN_INTERVAL_SEC", "5") or 5))

        self.position_check_interval = QSpinBox()
        self.position_check_interval.setRange(1, 3600)
        self.position_check_interval.setValue(int(os.getenv("BOT_POSITION_CHECK_INTERVAL_SEC", "2") or 2))

        self.balance_refresh_sec = QSpinBox()
        self.balance_refresh_sec.setRange(1, 3600)
        self.balance_refresh_sec.setValue(int(os.getenv("BOT_BALANCE_REFRESH_SEC", "3") or 3))

        self.snapshot_interval_sec = QSpinBox()
        self.snapshot_interval_sec.setRange(1, 3600)
        self.snapshot_interval_sec.setValue(int(os.getenv("BOT_SNAPSHOT_INTERVAL_SEC", "2") or 2))

        self.gui_refresh_ms = QSpinBox()
        self.gui_refresh_ms.setRange(100, 10000)
        self.gui_refresh_ms.setSingleStep(100)
        self.gui_refresh_ms.setValue(int(os.getenv("BOT_GUI_REFRESH_MS", "1000") or 1000))

        self.risk_pct = QDoubleSpinBox()
        self.risk_pct.setRange(0.01, 100.0)
        self.risk_pct.setDecimals(2)
        self.risk_pct.setValue(float(os.getenv("BOT_RISK_PER_TRADE_PCT", "1.0") or 1.0))

        self.max_pos_pct = QDoubleSpinBox()
        self.max_pos_pct.setRange(0.01, 100.0)
        self.max_pos_pct.setDecimals(2)
        self.max_pos_pct.setValue(float(os.getenv("BOT_MAX_POSITION_NOTIONAL_PCT", "2.0") or 2.0))

        self.long_entry = QSpinBox()
        self.long_entry.setRange(2, 500)
        self.long_entry.setValue(int(os.getenv("BOT_LONG_ENTRY_PERIOD", "55") or 55))

        self.short_entry = QSpinBox()
        self.short_entry.setRange(2, 500)
        self.short_entry.setValue(int(os.getenv("BOT_SHORT_ENTRY_PERIOD", "20") or 20))

        self.long_exit = QSpinBox()
        self.long_exit.setRange(2, 500)
        self.long_exit.setValue(int(os.getenv("BOT_LONG_EXIT_PERIOD", "20") or 20))

        self.short_exit = QSpinBox()
        self.short_exit.setRange(2, 500)
        self.short_exit.setValue(int(os.getenv("BOT_SHORT_EXIT_PERIOD", "10") or 10))

        self.atr_period = QSpinBox()
        self.atr_period.setRange(2, 500)
        self.atr_period.setValue(int(os.getenv("BOT_ATR_PERIOD", "20") or 20))

        self.atr_stop_multiple = QDoubleSpinBox()
        self.atr_stop_multiple.setRange(0.1, 20.0)
        self.atr_stop_multiple.setDecimals(2)
        self.atr_stop_multiple.setValue(float(os.getenv("BOT_ATR_STOP_MULTIPLE", "2.0") or 2.0))

        self.add_unit_every_atr = QDoubleSpinBox()
        self.add_unit_every_atr.setRange(0.1, 20.0)
        self.add_unit_every_atr.setDecimals(2)
        self.add_unit_every_atr.setValue(float(os.getenv("BOT_ADD_UNIT_EVERY_ATR", "0.5") or 0.5))

        self.max_units_per_symbol = QSpinBox()
        self.max_units_per_symbol.setRange(0, 20)
        self.max_units_per_symbol.setValue(int(os.getenv("BOT_MAX_UNITS_PER_SYMBOL", "4") or 4))

        self.flat_lookback_candles = QSpinBox()
        self.flat_lookback_candles.setRange(5, 500)
        self.flat_lookback_candles.setValue(int(os.getenv("BOT_FLAT_LOOKBACK_CANDLES", "36") or 36))

        self.min_channel_range_pct = QDoubleSpinBox()
        self.min_channel_range_pct.setRange(0.0, 100.0)
        self.min_channel_range_pct.setDecimals(3)
        self.min_channel_range_pct.setValue(float(os.getenv("BOT_MIN_CHANNEL_RANGE_PCT", "1.0") or 1.0))

        self.min_atr_pct = QDoubleSpinBox()
        self.min_atr_pct.setRange(0.0, 100.0)
        self.min_atr_pct.setDecimals(3)
        self.min_atr_pct.setValue(float(os.getenv("BOT_MIN_ATR_PCT", "0.18") or 0.18))

        self.min_body_to_range_ratio = QDoubleSpinBox()
        self.min_body_to_range_ratio.setRange(0.0, 1.0)
        self.min_body_to_range_ratio.setDecimals(3)
        self.min_body_to_range_ratio.setValue(float(os.getenv("BOT_MIN_BODY_TO_RANGE_RATIO", "0.28") or 0.28))

        self.min_efficiency_ratio = QDoubleSpinBox()
        self.min_efficiency_ratio.setRange(0.0, 1.0)
        self.min_efficiency_ratio.setDecimals(3)
        self.min_efficiency_ratio.setValue(float(os.getenv("BOT_MIN_EFFICIENCY_RATIO", "0.18") or 0.18))

        self.max_direction_flip_ratio = QDoubleSpinBox()
        self.max_direction_flip_ratio.setRange(0.0, 1.0)
        self.max_direction_flip_ratio.setDecimals(3)
        self.max_direction_flip_ratio.setValue(float(os.getenv("BOT_MAX_DIRECTION_FLIP_RATIO", "0.65") or 0.65))

        self.telegram_enabled = QComboBox()
        self.telegram_enabled.addItems(["false", "true"])
        self.telegram_enabled.setCurrentText((os.getenv("TELEGRAM_ENABLED", "false").strip() or "false").lower())

        self.telegram_bot_token = QLineEdit()
        self.telegram_bot_token.setText(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())

        self.telegram_chat_id = QLineEdit()
        self.telegram_chat_id.setText(os.getenv("TELEGRAM_CHAT_ID", "").strip())

        self.pyramid_second_unit_scale = QDoubleSpinBox()
        self.pyramid_second_unit_scale.setRange(0.0, 10.0)
        self.pyramid_second_unit_scale.setDecimals(3)
        self.pyramid_second_unit_scale.setValue(float(os.getenv("BOT_PYRAMID_SECOND_UNIT_SCALE", "0.75") or 0.75))

        self.pyramid_third_unit_scale = QDoubleSpinBox()
        self.pyramid_third_unit_scale.setRange(0.0, 10.0)
        self.pyramid_third_unit_scale.setDecimals(3)
        self.pyramid_third_unit_scale.setValue(float(os.getenv("BOT_PYRAMID_THIRD_UNIT_SCALE", "0.50") or 0.50))

        self.pyramid_fourth_unit_scale = QDoubleSpinBox()
        self.pyramid_fourth_unit_scale.setRange(0.0, 10.0)
        self.pyramid_fourth_unit_scale.setDecimals(3)
        self.pyramid_fourth_unit_scale.setValue(float(os.getenv("BOT_PYRAMID_FOURTH_UNIT_SCALE", "0.25") or 0.25))

        self.pyramid_break_even_buffer_atr = QDoubleSpinBox()
        self.pyramid_break_even_buffer_atr.setRange(0.0, 10.0)
        self.pyramid_break_even_buffer_atr.setDecimals(3)
        self.pyramid_break_even_buffer_atr.setValue(float(os.getenv("BOT_PYRAMID_BREAK_EVEN_BUFFER_ATR", "0.05") or 0.05))

        self.pyramid_min_progress_atr = QDoubleSpinBox()
        self.pyramid_min_progress_atr.setRange(0.0, 10.0)
        self.pyramid_min_progress_atr.setDecimals(3)
        self.pyramid_min_progress_atr.setValue(float(os.getenv("BOT_PYRAMID_MIN_PROGRESS_ATR", "0.60") or 0.60))

        self.pyramid_min_body_ratio = QDoubleSpinBox()
        self.pyramid_min_body_ratio.setRange(0.0, 1.0)
        self.pyramid_min_body_ratio.setDecimals(3)
        self.pyramid_min_body_ratio.setValue(float(os.getenv("BOT_PYRAMID_MIN_BODY_RATIO", "0.35") or 0.35))

        self.pyramid_min_stop_distance_atr = QDoubleSpinBox()
        self.pyramid_min_stop_distance_atr.setRange(0.0, 10.0)
        self.pyramid_min_stop_distance_atr.setDecimals(3)
        self.pyramid_min_stop_distance_atr.setValue(float(os.getenv("BOT_PYRAMID_MIN_STOP_DISTANCE_ATR", "0.80") or 0.80))

        form.addRow("OKX API Key:", self.api_key)
        form.addRow("OKX Secret Key:", self.secret_key)
        form.addRow("OKX Passphrase:", self.passphrase)
        form.addRow("OKX Flag (1 demo / 0 real):", self.flag)
        form.addRow("Таймфрейм:", self.timeframe)
        form.addRow("Плечо:", self.leverage)
        form.addRow("Скан рынка, сек:", self.scan_interval)
        form.addRow("Проверка позиций, сек:", self.position_check_interval)
        form.addRow("Обновление баланса, сек:", self.balance_refresh_sec)
        form.addRow("Snapshot, сек:", self.snapshot_interval_sec)
        form.addRow("GUI refresh, мс:", self.gui_refresh_ms)
        form.addRow("Риск на сделку, %:", self.risk_pct)
        form.addRow("Макс. размер позиции, %:", self.max_pos_pct)
        form.addRow("Long entry period:", self.long_entry)
        form.addRow("Short entry period:", self.short_entry)
        form.addRow("Long exit period:", self.long_exit)
        form.addRow("Short exit period:", self.short_exit)
        form.addRow("ATR period:", self.atr_period)
        form.addRow("ATR stop multiple:", self.atr_stop_multiple)
        form.addRow("Добавлять юнит каждые ATR:", self.add_unit_every_atr)
        form.addRow("Макс. юнитов на символ:", self.max_units_per_symbol)
        form.addRow("Flat lookback candles:", self.flat_lookback_candles)
        form.addRow("Min channel range %:", self.min_channel_range_pct)
        form.addRow("Min ATR %:", self.min_atr_pct)
        form.addRow("Min body/range ratio:", self.min_body_to_range_ratio)
        form.addRow("Min efficiency ratio:", self.min_efficiency_ratio)
        form.addRow("Max direction flip ratio:", self.max_direction_flip_ratio)
        form.addRow("Telegram enabled:", self.telegram_enabled)
        form.addRow("Telegram bot token:", self.telegram_bot_token)
        form.addRow("Telegram chat id:", self.telegram_chat_id)
        form.addRow("2-й юнит scale:", self.pyramid_second_unit_scale)
        form.addRow("3-й юнит scale:", self.pyramid_third_unit_scale)
        form.addRow("4-й юнит scale:", self.pyramid_fourth_unit_scale)
        form.addRow("Break-even buffer ATR:", self.pyramid_break_even_buffer_atr)
        form.addRow("Min progress ATR:", self.pyramid_min_progress_atr)
        form.addRow("Min candle body ratio:", self.pyramid_min_body_ratio)
        form.addRow("Min stop distance ATR:", self.pyramid_min_stop_distance_atr)

        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Запустить бота")
        self.start_btn.clicked.connect(self.start_bot)
        btn_row.addStretch(1)
        btn_row.addWidget(self.start_btn)
        layout.addLayout(btn_row)

    def _collect_config(self) -> BotConfig:
        return BotConfig(
            api_key=self.api_key.text().strip(),
            secret_key=self.secret_key.text().strip(),
            passphrase=self.passphrase.text().strip(),
            flag=self.flag.currentText().strip(),
            timeframe=self.timeframe.currentText().strip(),
            leverage=int(self.leverage.value()),
            scan_interval_sec=int(self.scan_interval.value()),
            position_check_interval_sec=int(self.position_check_interval.value()),
            balance_refresh_sec=int(self.balance_refresh_sec.value()),
            risk_per_trade_pct=float(self.risk_pct.value()),
            max_position_notional_pct=float(self.max_pos_pct.value()),
            long_entry_period=int(self.long_entry.value()),
            short_entry_period=int(self.short_entry.value()),
            long_exit_period=int(self.long_exit.value()),
            short_exit_period=int(self.short_exit.value()),
            atr_period=int(self.atr_period.value()),
            atr_stop_multiple=float(self.atr_stop_multiple.value()),
            add_unit_every_atr=float(self.add_unit_every_atr.value()),
            max_units_per_symbol=int(self.max_units_per_symbol.value()),
            snapshot_interval_sec=int(self.snapshot_interval_sec.value()),
            gui_refresh_ms=int(self.gui_refresh_ms.value()),
            flat_lookback_candles=int(self.flat_lookback_candles.value()),
            min_channel_range_pct=float(self.min_channel_range_pct.value()),
            min_atr_pct=float(self.min_atr_pct.value()),
            min_body_to_range_ratio=float(self.min_body_to_range_ratio.value()),
            min_efficiency_ratio=float(self.min_efficiency_ratio.value()),
            max_direction_flip_ratio=float(self.max_direction_flip_ratio.value()),
            telegram_enabled=self.telegram_enabled.currentText() == "true",
            telegram_bot_token=self.telegram_bot_token.text().strip(),
            telegram_chat_id=self.telegram_chat_id.text().strip(),
            pyramid_second_unit_scale=float(self.pyramid_second_unit_scale.value()),
            pyramid_third_unit_scale=float(self.pyramid_third_unit_scale.value()),
            pyramid_fourth_unit_scale=float(self.pyramid_fourth_unit_scale.value()),
            pyramid_break_even_buffer_atr=float(self.pyramid_break_even_buffer_atr.value()),
            pyramid_min_progress_atr=float(self.pyramid_min_progress_atr.value()),
            pyramid_min_body_ratio=float(self.pyramid_min_body_ratio.value()),
            pyramid_min_stop_distance_atr=float(self.pyramid_min_stop_distance_atr.value()),
        )

    def start_bot(self) -> None:
        cfg = self._collect_config()
        if not cfg.api_key or not cfg.secret_key or not cfg.passphrase:
            QMessageBox.warning(self, "Ошибка", "Укажи API Key, Secret Key и Passphrase")
            return
        self.main_window = MainWindow(cfg)
        self.main_window.show()
        self.close()


class MainWindow(QMainWindow):
    def __init__(self, cfg: Optional[BotConfig] = None):
        super().__init__()
        self.cfg = cfg
        self.engine: Optional[TurtleEngine] = None
        self.worker: Optional[WorkerThread] = None
        self.latest_snapshot: Optional[dict] = None
        self.last_snapshot_received_at: Optional[datetime] = None

        if self.cfg is None:
            load_dotenv()
            self.cfg = BotConfig(
                api_key=os.getenv("OKX_API_KEY", "").strip(),
                secret_key=os.getenv("OKX_SECRET_KEY", "").strip(),
                passphrase=os.getenv("OKX_PASSPHRASE", "").strip(),
                flag=os.getenv("OKX_FLAG", "1").strip() or "1",
                timeframe=os.getenv("BOT_TIMEFRAME", "15m").strip() or "15m",
                leverage=int(os.getenv("BOT_LEVERAGE", "1") or 1),
                scan_interval_sec=int(os.getenv("BOT_SCAN_INTERVAL_SEC", "5") or 5),
                position_check_interval_sec=int(os.getenv("BOT_POSITION_CHECK_INTERVAL_SEC", "2") or 2),
                balance_refresh_sec=int(os.getenv("BOT_BALANCE_REFRESH_SEC", "3") or 3),
                risk_per_trade_pct=float(os.getenv("BOT_RISK_PER_TRADE_PCT", "1.0") or 1.0),
                max_position_notional_pct=float(os.getenv("BOT_MAX_POSITION_NOTIONAL_PCT", "2.0") or 2.0),
                long_entry_period=int(os.getenv("BOT_LONG_ENTRY_PERIOD", "55") or 55),
                short_entry_period=int(os.getenv("BOT_SHORT_ENTRY_PERIOD", "20") or 20),
                long_exit_period=int(os.getenv("BOT_LONG_EXIT_PERIOD", "20") or 20),
                short_exit_period=int(os.getenv("BOT_SHORT_EXIT_PERIOD", "10") or 10),
                atr_period=int(os.getenv("BOT_ATR_PERIOD", "20") or 20),
                atr_stop_multiple=float(os.getenv("BOT_ATR_STOP_MULTIPLE", "2.0") or 2.0),
                add_unit_every_atr=float(os.getenv("BOT_ADD_UNIT_EVERY_ATR", "0.5") or 0.5),
                max_units_per_symbol=int(os.getenv("BOT_MAX_UNITS_PER_SYMBOL", "4") or 4),
                snapshot_interval_sec=int(os.getenv("BOT_SNAPSHOT_INTERVAL_SEC", "2") or 2),
                gui_refresh_ms=int(os.getenv("BOT_GUI_REFRESH_MS", "1000") or 1000),
                flat_lookback_candles=int(os.getenv("BOT_FLAT_LOOKBACK_CANDLES", "36") or 36),
                min_channel_range_pct=float(os.getenv("BOT_MIN_CHANNEL_RANGE_PCT", "1.0") or 1.0),
                min_atr_pct=float(os.getenv("BOT_MIN_ATR_PCT", "0.18") or 0.18),
                min_body_to_range_ratio=float(os.getenv("BOT_MIN_BODY_TO_RANGE_RATIO", "0.28") or 0.28),
                min_efficiency_ratio=float(os.getenv("BOT_MIN_EFFICIENCY_RATIO", "0.18") or 0.18),
                max_direction_flip_ratio=float(os.getenv("BOT_MAX_DIRECTION_FLIP_RATIO", "0.65") or 0.65),
                telegram_enabled=(os.getenv("TELEGRAM_ENABLED", "false").strip().lower() == "true"),
                telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
                telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
                pyramid_second_unit_scale=float(os.getenv("BOT_PYRAMID_SECOND_UNIT_SCALE", "0.75") or 0.75),
                pyramid_third_unit_scale=float(os.getenv("BOT_PYRAMID_THIRD_UNIT_SCALE", "0.50") or 0.50),
                pyramid_fourth_unit_scale=float(os.getenv("BOT_PYRAMID_FOURTH_UNIT_SCALE", "0.25") or 0.25),
                pyramid_break_even_buffer_atr=float(os.getenv("BOT_PYRAMID_BREAK_EVEN_BUFFER_ATR", "0.05") or 0.05),
                pyramid_min_progress_atr=float(os.getenv("BOT_PYRAMID_MIN_PROGRESS_ATR", "0.60") or 0.60),
                pyramid_min_body_ratio=float(os.getenv("BOT_PYRAMID_MIN_BODY_RATIO", "0.35") or 0.35),
                pyramid_min_stop_distance_atr=float(os.getenv("BOT_PYRAMID_MIN_STOP_DISTANCE_ATR", "0.80") or 0.80),
            )

        self._dark_theme = detect_is_dark_theme()
        self.setStyleSheet(build_app_stylesheet(self._dark_theme))
        self.setWindowTitle(f"OKX Turtle Traders Bot {APP_VERSION}")
        if WINDOW_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(WINDOW_ICON_PATH)))

        self.resize(1500, 900)
        self._build_ui()
        self.apply_system_theme()

        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.refresh_from_latest_snapshot)
        self.gui_timer.start(max(100, self.cfg.gui_refresh_ms))

    def apply_system_theme(self):
        is_dark = detect_is_dark_theme()
        if is_dark != self._dark_theme:
            self._dark_theme = is_dark
            self.setStyleSheet(build_app_stylesheet(self._dark_theme))
            self.balance_chart.update()

    def event(self, e):
        if e.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self.apply_system_theme()
        return super().event(e)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        top = QHBoxLayout()

        ctrl_box = QGroupBox("Управление")
        ctrl_layout = QGridLayout(ctrl_box)

        self.status_label = QLabel("Бот остановлен")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.timeframe_label = QLabel(TIMEFRAME_LABELS.get(self.cfg.timeframe, self.cfg.timeframe))
        self.last_update_label = QLabel("--:--:--")
        self.last_scan_started_label = QLabel("--:--:--")
        self.last_scan_finished_label = QLabel("--:--:--")
        self.last_positions_check_label = QLabel("--:--:--")
        self.used_margin_label = QLabel("0.00")
        self.available_balance_label = QLabel("0.00")
        self.unrealized_pnl_label = QLabel("0.00")
        self.snapshot_time_label = QLabel("--:--:--")

        self.start_button = QPushButton("Старт")
        self.stop_button = QPushButton("Стоп")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_bot)
        self.stop_button.clicked.connect(self.stop_bot)

        ctrl_layout.addWidget(QLabel("Статус:"), 0, 0)
        ctrl_layout.addWidget(self.status_label, 0, 1)
        ctrl_layout.addWidget(QLabel("Таймфрейм:"), 1, 0)
        ctrl_layout.addWidget(self.timeframe_label, 1, 1)
        ctrl_layout.addWidget(QLabel("Последнее обновление:"), 2, 0)
        ctrl_layout.addWidget(self.last_update_label, 2, 1)
        ctrl_layout.addWidget(QLabel("Последний цикл scan:"), 3, 0)
        ctrl_layout.addWidget(self.last_scan_started_label, 3, 1)
        ctrl_layout.addWidget(QLabel("Последний finish scan:"), 4, 0)
        ctrl_layout.addWidget(self.last_scan_finished_label, 4, 1)
        ctrl_layout.addWidget(QLabel("Проверка позиций:"), 5, 0)
        ctrl_layout.addWidget(self.last_positions_check_label, 5, 1)
        ctrl_layout.addWidget(QLabel("Использовано:"), 6, 0)
        ctrl_layout.addWidget(self.used_margin_label, 6, 1)
        ctrl_layout.addWidget(QLabel("Доступно:"), 7, 0)
        ctrl_layout.addWidget(self.available_balance_label, 7, 1)
        ctrl_layout.addWidget(QLabel("Unrealized PnL:"), 8, 0)
        ctrl_layout.addWidget(self.unrealized_pnl_label, 8, 1)
        ctrl_layout.addWidget(QLabel("Последний snapshot:"), 9, 0)
        ctrl_layout.addWidget(self.snapshot_time_label, 9, 1)
        ctrl_layout.addWidget(self.start_button, 10, 0)
        ctrl_layout.addWidget(self.stop_button, 10, 1)

        analytics_box = QGroupBox("Аналитика")
        analytics_layout = QVBoxLayout(analytics_box)
        self.analytics_text = QTextEdit()
        self.analytics_text.setReadOnly(True)
        self.balance_chart = BalanceChartWidget()
        analytics_layout.addWidget(self.analytics_text)
        analytics_layout.addWidget(self.balance_chart)

        top.addWidget(ctrl_box, 1)
        top.addWidget(analytics_box, 2)

        root.addLayout(top)

        tabs = QTabWidget()

        self.positions_model = PositionTableModel()
        self.positions_table = QTableView()
        self.positions_table.setModel(self.positions_model)
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.positions_table.verticalHeader().setVisible(False)
        self.positions_table.setAlternatingRowColors(True)

        self.closed_model = ClosedTradesTableModel()
        self.closed_table = QTableView()
        self.closed_table.setModel(self.closed_model)
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.closed_table.verticalHeader().setVisible(False)
        self.closed_table.setAlternatingRowColors(True)

        pos_tab = QWidget()
        pos_layout = QVBoxLayout(pos_tab)
        pos_layout.addWidget(self.positions_table)

        closed_tab = QWidget()
        closed_layout = QVBoxLayout(closed_tab)
        closed_layout.addWidget(self.closed_table)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.addWidget(self.log_box)

        tabs.addTab(pos_tab, "Открытые позиции")
        tabs.addTab(closed_tab, "Закрытые сделки")
        tabs.addTab(log_tab, "Лог")

        root.addWidget(tabs)
        self.setCentralWidget(central)

    def append_log(self, text: str) -> None:
        self.log_box.append(text)

    def start_bot(self) -> None:
        if self.engine is not None:
            return
        try:
            self.engine = TurtleEngine(self.cfg)
            self.engine.snapshot.connect(self.on_snapshot)
            self.engine.log_line.connect(self.append_log)
            self.engine.status.connect(self.on_status)
            self.engine.error.connect(self.on_error)

            self.worker = WorkerThread(self.engine)
            self.worker.start()

            self.status_label.setText("Бот запущен")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] Бот запущен пользователем")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", str(e))
            logging.exception("Start failed")

    def stop_bot(self) -> None:
        if self.engine is None:
            return
        try:
            self.engine.stop()
            if self.worker is not None:
                self.worker.quit()
                self.worker.wait(3000)
        except Exception:
            logging.exception("Stop failed")
        finally:
            self.engine = None
            self.worker = None
            self.status_label.setText("Бот остановлен")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] Бот остановлен пользователем")

    def on_status(self, text: str) -> None:
        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def on_error(self, text: str) -> None:
        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: {text}")

    def on_snapshot(self, payload: dict) -> None:
        self.latest_snapshot = payload
        self.last_snapshot_received_at = datetime.now()

    def refresh_from_latest_snapshot(self) -> None:
        self.apply_system_theme()
        payload = self.latest_snapshot
        if not payload:
            return

        self.last_update_label.setText(format_clock(self.last_snapshot_received_at))
        self.last_scan_started_label.setText(payload.get("last_scan_started_at", "--:--:--"))
        self.last_scan_finished_label.setText(payload.get("last_scan_finished_at", "--:--:--"))
        self.last_positions_check_label.setText(payload.get("last_positions_check_at", "--:--:--"))
        self.snapshot_time_label.setText(format_clock(self.last_snapshot_received_at))
        self.used_margin_label.setText(f"{float(payload.get('used_margin', 0.0)):.4f}")
        self.available_balance_label.setText(f"{float(payload.get('available_balance', 0.0)):.4f}")
        self.unrealized_pnl_label.setText(f"{float(payload.get('unrealized_pnl', 0.0)):.4f}")

        positions = [PositionState(**row) for row in payload.get("open_positions", [])]
        closed = [ClosedTrade(**row) for row in payload.get("closed_trades", [])]

        self.positions_model.update_rows(positions[::-1])
        self.closed_model.update_rows(closed[::-1])

        chart_points = []
        for row in payload.get("balance_history", [])[-300:]:
            ts = row.get("ts", "")
            bal = float(row.get("balance", 0.0) or 0.0)
            chart_points.append((ts, bal))
        self.balance_chart.set_points(chart_points)

        self.update_analytics(positions, closed, chart_points)

    def update_analytics(self, positions: List[PositionState], closed: List[ClosedTrade], chart_points: List[tuple]) -> None:
        total_open = len(positions)
        total_closed = len(closed)
        total_realized = sum(x.pnl for x in closed)
        wins = sum(1 for x in closed if x.pnl > 0)
        losses = sum(1 for x in closed if x.pnl < 0)
        win_rate = (wins / total_closed * 100.0) if total_closed else 0.0
        avg_pnl = (total_realized / total_closed) if total_closed else 0.0
        total_unrealized = sum(x.unrealized_pnl for x in positions)

        lines = [
            f"Открытых позиций: {total_open}",
            f"Закрытых сделок: {total_closed}",
            f"Прибыльных: {wins}",
            f"Убыточных: {losses}",
            f"Win rate: {win_rate:.2f}%",
            f"Реализованный PnL: {total_realized:.4f}",
            f"Средний PnL на сделку: {avg_pnl:.4f}",
            f"Нереализованный PnL: {total_unrealized:.4f}",
        ]

        improvements = []
        if win_rate >= 50:
            improvements.append("✅ Win rate держится выше 50%")
        else:
            improvements.append("❌ Win rate ниже 50%, стоит усиливать фильтрацию входов")

        if total_realized >= 0:
            improvements.append("✅ Суммарный realized PnL положительный")
        else:
            improvements.append("❌ Суммарный realized PnL отрицательный")

        if positions:
            avg_units = sum(p.units for p in positions) / len(positions)
            if avg_units > 1.2:
                improvements.append("✅ Пирамидинг активно используется")
            else:
                improvements.append("❌ Пирамидинг почти не срабатывает")

        text = "\n".join(lines + ["", "Оценка:", *improvements])
        self.analytics_text.setPlainText(text)

    def closeEvent(self, event):
        self.stop_bot()
        super().closeEvent(event)