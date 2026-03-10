import os
import sys
from datetime import datetime
from typing import Any, List

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_core import (
    APP_VERSION,
    TIMEFRAME_LABELS,
    WINDOW_ICON_PATH,
    BotConfig,
    ClosedTrade,
    PositionState,
    build_app_stylesheet,
    detect_is_dark_theme,
    format_clock,
)

from engine import TradingEngine
from exchange import OKXGateway


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.config = BotConfig(
            api_key=os.getenv("OKX_API_KEY", "").strip(),
            api_secret=os.getenv("OKX_API_SECRET", "").strip(),
            api_passphrase=os.getenv("OKX_API_PASSPHRASE", "").strip(),
            demo_mode=os.getenv("OKX_DEMO", "0").strip() in ("1", "true", "True"),
        )

        if not getattr(self.config, "timeframe", None):
            self.config.timeframe = "1m"
        if not hasattr(self.config, "engine_interval_sec"):
            self.config.engine_interval_sec = 2.0
        if not hasattr(self.config, "gui_interval_sec"):
            self.config.gui_interval_sec = 2.0
        if not hasattr(self.config, "max_positions"):
            self.config.max_positions = 10
        if not hasattr(self.config, "risk_per_trade"):
            self.config.risk_per_trade = 0.01
        if not hasattr(self.config, "max_position_fraction"):
            self.config.max_position_fraction = 0.02

        self.gateway = OKXGateway(self.config)
        self.engine = TradingEngine(self.config, self.gateway, self.append_log)

        self._build_ui()
        self._build_timers()
        self.apply_system_theme()
        self.refresh_from_latest_snapshot()

    # ------------------------------- UI -----------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION}")
        self.resize(1500, 900)

        if WINDOW_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(WINDOW_ICON_PATH)))

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        top_bar = self._build_top_bar()
        root.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(splitter, 1)

        upper = QWidget()
        upper_layout = QGridLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        self.stats_box = self._build_stats_box()
        self.settings_box = self._build_settings_box()
        self.positions_box = self._build_positions_box()
        self.closed_box = self._build_closed_box()

        upper_layout.addWidget(self.stats_box, 0, 0)
        upper_layout.addWidget(self.settings_box, 0, 1)
        upper_layout.addWidget(self.positions_box, 1, 0, 1, 2)

        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(8)
        lower_layout.addWidget(self.closed_box)
        lower_layout.addWidget(self._build_log_box())

        splitter.addWidget(upper)
        splitter.addWidget(lower)
        splitter.setSizes([540, 320])

        self._build_menu()

    def _build_top_bar(self) -> QWidget:
        box = QGroupBox("Управление")
        layout = QHBoxLayout(box)

        self.status_label = QLabel("Бот остановлен")
        self.status_label.setStyleSheet("font-weight: 700; color: #c62828;")

        self.start_btn = QPushButton("Запустить")
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.refresh_btn = QPushButton("Обновить")

        self.start_btn.clicked.connect(self.on_start_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        self.refresh_btn.clicked.connect(self.refresh_from_latest_snapshot)

        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.refresh_btn)

        return box

    def _build_stats_box(self) -> QWidget:
        box = QGroupBox("Статистика")
        form = QFormLayout(box)

        self.lbl_last_update = QLabel("-")
        self.lbl_last_cycle = QLabel("-")
        self.lbl_equity = QLabel("0")
        self.lbl_used = QLabel("0")
        self.lbl_open_count = QLabel("0")
        self.lbl_closed_count = QLabel("0")

        form.addRow("Последнее обновление:", self.lbl_last_update)
        form.addRow("Последний цикл движка:", self.lbl_last_cycle)
        form.addRow("Equity:", self.lbl_equity)
        form.addRow("Использовано:", self.lbl_used)
        form.addRow("Открытых позиций:", self.lbl_open_count)
        form.addRow("Закрытых сделок:", self.lbl_closed_count)

        return box

    def _build_settings_box(self) -> QWidget:
        box = QGroupBox("Настройки")
        form = QFormLayout(box)

        self.timeframe_combo = QComboBox()
        timeframe_values = list(TIMEFRAME_LABELS.keys()) if TIMEFRAME_LABELS else ["1m", "3m", "5m", "15m", "1H", "4H"]
        self.timeframe_combo.addItems(timeframe_values)
        if self.config.timeframe in timeframe_values:
            self.timeframe_combo.setCurrentText(self.config.timeframe)
        else:
            self.timeframe_combo.setCurrentText("1m")
            self.config.timeframe = "1m"
        self.timeframe_combo.currentTextChanged.connect(self.on_timeframe_changed)

        self.max_positions_edit = QLineEdit(str(getattr(self.config, "max_positions", 10)))
        self.risk_edit = QLineEdit(str(getattr(self.config, "risk_per_trade", 0.01)))
        self.max_pos_fraction_edit = QLineEdit(str(getattr(self.config, "max_position_fraction", 0.02)))
        self.demo_checkbox = QCheckBox("Demo mode")
        self.demo_checkbox.setChecked(bool(getattr(self.config, "demo_mode", False)))

        self.apply_settings_btn = QPushButton("Применить настройки")
        self.apply_settings_btn.clicked.connect(self.apply_settings_from_ui)

        form.addRow("Таймфрейм:", self.timeframe_combo)
        form.addRow("Макс. позиций:", self.max_positions_edit)
        form.addRow("Риск на сделку:", self.risk_edit)
        form.addRow("Лимит позиции:", self.max_pos_fraction_edit)
        form.addRow("", self.demo_checkbox)
        form.addRow("", self.apply_settings_btn)

        return box

    def _build_positions_box(self) -> QWidget:
        box = QGroupBox("Открытые позиции")
        layout = QVBoxLayout(box)

        self.positions_table = QTableWidget(0, 9)
        self.positions_table.setHorizontalHeaderLabels(
            [
                "Инструмент",
                "Сторона",
                "Qty",
                "Вход",
                "Стоп",
                "ATR",
                "Юнитов",
                "PnL",
                "PnL%",
            ]
        )
        self.positions_table.verticalHeader().setVisible(False)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.positions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.positions_table)
        return box

    def _build_closed_box(self) -> QWidget:
        box = QGroupBox("Закрытые сделки")
        layout = QVBoxLayout(box)

        self.closed_table = QTableWidget(0, 8)
        self.closed_table.setHorizontalHeaderLabels(
            [
                "Инструмент",
                "Сторона",
                "Qty",
                "Вход",
                "Выход",
                "PnL",
                "PnL%",
                "Причина",
            ]
        )
        self.closed_table.verticalHeader().setVisible(False)
        self.closed_table.setAlternatingRowColors(True)
        self.closed_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.closed_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.closed_table)
        return box

    def _build_log_box(self) -> QWidget:
        box = QGroupBox("Лог")
        layout = QVBoxLayout(box)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)

        layout.addWidget(self.log_edit)
        return box

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("Файл")

        action_exit = QAction("Выход", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _build_timers(self) -> None:
        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.refresh_from_latest_snapshot)
        self.gui_timer.start(int(_safe_float(getattr(self.config, "gui_interval_sec", 2.0), 2.0) * 1000))

    # ----------------------------- handlers -------------------------------

    def on_start_clicked(self) -> None:
        self.apply_settings_from_ui()

        try:
            self.engine.start()
            self.status_label.setText("Бот запущен")
            self.status_label.setStyleSheet("font-weight: 700; color: #2e7d32;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.append_log("Бот запущен пользователем")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", str(e))

    def on_stop_clicked(self) -> None:
        try:
            self.engine.stop()
            self.status_label.setText("Бот остановлен")
            self.status_label.setStyleSheet("font-weight: 700; color: #c62828;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.append_log("Бот остановлен пользователем")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка остановки", str(e))

    def on_timeframe_changed(self, value: str) -> None:
        self.config.timeframe = value
        self.append_log(f"Таймфрейм изменён: {value}")

    def apply_settings_from_ui(self) -> None:
        self.config.timeframe = self.timeframe_combo.currentText()
        self.config.max_positions = _safe_int(self.max_positions_edit.text(), 10)
        self.config.risk_per_trade = _safe_float(self.risk_edit.text(), 0.01)
        self.config.max_position_fraction = _safe_float(self.max_pos_fraction_edit.text(), 0.02)
        self.config.demo_mode = self.demo_checkbox.isChecked()

        self.append_log(
            f"Настройки применены: timeframe={self.config.timeframe}, "
            f"max_positions={self.config.max_positions}, "
            f"risk={self.config.risk_per_trade}, "
            f"max_position_fraction={self.config.max_position_fraction}"
        )

    # ----------------------------- refresh --------------------------------

    def refresh_from_latest_snapshot(self) -> None:
        try:
            snapshot = self.engine.get_snapshot()
        except Exception as e:
            self.append_log(f"Не удалось обновить snapshot: {e}")
            return

        self._fill_stats(snapshot)
        self._fill_positions(snapshot.get("positions", []))
        self._fill_closed_trades(snapshot.get("closed_trades", []))

    def _fill_stats(self, snapshot: dict) -> None:
        self.lbl_last_update.setText(self._format_ts(snapshot.get("last_snapshot_at")))
        self.lbl_last_cycle.setText(self._format_ts(snapshot.get("last_cycle_at")))
        self.lbl_equity.setText(f"{_safe_float(snapshot.get('equity_estimate')):.2f}")
        self.lbl_used.setText(f"{_safe_float(snapshot.get('used_margin_estimate')):.2f}")
        self.lbl_open_count.setText(str(len(snapshot.get("positions", []))))
        self.lbl_closed_count.setText(str(len(snapshot.get("closed_trades", []))))

        running = bool(snapshot.get("running"))
        if running:
            self.status_label.setText("Бот запущен")
            self.status_label.setStyleSheet("font-weight: 700; color: #2e7d32;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_label.setText("Бот остановлен")
            self.status_label.setStyleSheet("font-weight: 700; color: #c62828;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def _fill_positions(self, rows: List[dict]) -> None:
        parsed: List[PositionState] = []
        for row in rows:
            try:
                parsed.append(PositionState(**row))
            except Exception:
                continue

        self.positions_table.setRowCount(len(parsed))

        for r, pos in enumerate(parsed):
            values = [
                pos.inst_id,
                pos.side,
                self._fmt_num(pos.qty),
                self._fmt_num(pos.entry_price),
                self._fmt_num(pos.stop_price),
                self._fmt_num(pos.atr),
                str(getattr(pos, "units", 1)),
                self._fmt_num(pos.pnl),
                f"{_safe_float(pos.pnl_pct):.2f}%",
            ]

            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c in (1, 7, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.positions_table.setItem(r, c, item)

            pnl_pct = _safe_float(pos.pnl_pct)
            if pnl_pct > 0:
                for c in range(self.positions_table.columnCount()):
                    self.positions_table.item(r, c).setBackground(Qt.GlobalColor.green)
            elif pnl_pct < 0:
                for c in range(self.positions_table.columnCount()):
                    self.positions_table.item(r, c).setBackground(Qt.GlobalColor.red)

        self.positions_table.resizeColumnsToContents()

    def _fill_closed_trades(self, rows: List[dict]) -> None:
        parsed: List[ClosedTrade] = []
        for row in rows[-300:]:
            try:
                parsed.append(ClosedTrade(**row))
            except Exception:
                continue

        self.closed_table.setRowCount(len(parsed))

        for r, tr in enumerate(parsed):
            values = [
                tr.inst_id,
                tr.side,
                self._fmt_num(tr.qty),
                self._string_or_dash(getattr(tr, "entry_time", "")),
                self._string_or_dash(getattr(tr, "exit_time", "")),
                self._fmt_num(tr.pnl),
                f"{_safe_float(tr.pnl_pct):.2f}%",
                self._string_or_dash(getattr(tr, "reason", "")),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.closed_table.setItem(r, c, item)

        self.closed_table.resizeColumnsToContents()

    # ----------------------------- misc -----------------------------------

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{timestamp}] {message}")

    def apply_system_theme(self) -> None:
        is_dark = detect_is_dark_theme()
        self.setStyleSheet(build_app_stylesheet(is_dark))

    def closeEvent(self, event) -> None:
        try:
            if self.engine.is_running():
                self.engine.stop()
        finally:
            super().closeEvent(event)

    def _format_ts(self, value: Any) -> str:
        ts = _safe_float(value, 0.0)
        if ts <= 0:
            return "-"
        try:
            return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        except Exception:
            return "-"

    def _fmt_num(self, value: Any) -> str:
        x = _safe_float(value, 0.0)
        if abs(x) >= 1000:
            return f"{x:,.2f}".replace(",", " ")
        if abs(x) >= 1:
            return f"{x:.4f}".rstrip("0").rstrip(".")
        return f"{x:.6f}".rstrip("0").rstrip(".")

    def _string_or_dash(self, value: Any) -> str:
        text = str(value).strip()
        return text if text else "-"