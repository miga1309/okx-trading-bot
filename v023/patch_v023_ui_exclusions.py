# patch_v023_ui_exclusions.py
# Патч для текущего main_v022.py
#
# Делает:
# 1) APP_VERSION -> v023
# 2) Убирает кнопку "Применить параметры"
# 3) toggle_engine() всегда берёт актуальные параметры прямо из StartWindow
# 4) Бан-лист обновляется раз в 10 секунд
# 5) Убирает "Фильтры таблицы"
# 6) Увеличивает график баланса по высоте
# 7) Исключает LINK-USDT-SWAP и BREV-USDT-SWAP из торговли, статистики и GUI
#
# Использование:
#   python patch_v023_ui_exclusions.py

from pathlib import Path
import shutil
import sys

TARGET_FILE = Path("main_v022.py")
BACKUP_FILE = Path("main_v022.py.bak_v023")


def fail(msg: str) -> None:
    print(f"ОШИБКА: {msg}")
    sys.exit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET_FILE.exists():
        fail(f"Файл не найден: {TARGET_FILE.resolve()}")

    text = TARGET_FILE.read_text(encoding="utf-8")

    replacements = [
        (
            'APP_VERSION = "v022"',
            'APP_VERSION = "v023"',
            "app_version",
        ),
        (
            'HIDDEN_INSTRUMENTS = {"BREV-USDT-SWAP"}',
            'HIDDEN_INSTRUMENTS = {"BREV-USDT-SWAP", "LINK-USDT-SWAP"}',
            "hidden_instruments",
        ),
        (
            'HIDDEN_PREFIXES = ("BREV-",)',
            'HIDDEN_PREFIXES = ("BREV-",)',
            "hidden_prefixes_nochange",
        ),
        (
            '    blacklist: List[str] = field(default_factory=lambda: ["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP"])',
            '    blacklist: List[str] = field(default_factory=lambda: ["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP", "LINK-USDT-SWAP"])',
            "botconfig_blacklist",
        ),
        (
            '        self.start_button = QPushButton("Применить параметры")\n        self.start_button.clicked.connect(self._emit_start)\n        layout.addWidget(self.start_button)',
            '        self.start_button = None',
            "remove_start_button",
        ),
        (
            '        self._snapshot_refresh_interval_sec = 10\n        self._snapshot_countdown_sec = 10',
            '        self._snapshot_refresh_interval_sec = 10\n        self._snapshot_countdown_sec = 10\n        self._blocked_refresh_interval_sec = 10\n        self._blocked_countdown_sec = 10',
            "mainwindow_init_counters",
        ),
        (
            '        self.start_window = StartWindow()\n        self.start_window.start_requested.connect(self.set_pending_config)\n        self.start_window.setMaximumHeight(165)\n        layout.addWidget(self.start_window, stretch=0)',
            '        self.start_window = StartWindow()\n        self.start_window.start_requested.connect(self.set_pending_config)\n        self.start_window.setMaximumHeight(145)\n        layout.addWidget(self.start_window, stretch=0)',
            "start_window_height",
        ),
        (
            '        self.balance_chart = BalanceChartWidget()\n        self.balance_chart.setMinimumHeight(110)\n        self.balance_chart.setMaximumHeight(150)\n        metrics_layout.addWidget(self.balance_chart, 6, 0, 1, 3)',
            '        self.balance_chart = BalanceChartWidget()\n        self.balance_chart.setMinimumHeight(180)\n        self.balance_chart.setMaximumHeight(240)\n        metrics_layout.addWidget(self.balance_chart, 6, 0, 1, 3)',
            "bigger_balance_chart",
        ),
        (
            '        filter_box = QGroupBox("Фильтры таблицы")\n        filter_layout = QHBoxLayout(filter_box)\n        self.filter_text = QLineEdit()\n        self.filter_text.setPlaceholderText("Поиск по инструменту...")\n        self.filter_text.textChanged.connect(self.apply_filters)\n        filter_layout.addWidget(self.filter_text)\n\n        self.filter_side = QComboBox()\n        self.filter_side.addItems(["Все", "Long", "Short"])\n        self.filter_side.currentIndexChanged.connect(self.apply_filters)\n        filter_layout.addWidget(self.filter_side)\n\n        self.filter_pnl = QComboBox()\n        self.filter_pnl.addItems(["Все", "Прибыльные", "Убыточные"])\n        self.filter_pnl.currentIndexChanged.connect(self.apply_filters)\n        filter_layout.addWidget(self.filter_pnl)\n        filter_box.setMaximumHeight(64)\n        layout.addWidget(filter_box, stretch=0)\n',
            '        self.filter_text = None\n        self.filter_side = None\n        self.filter_pnl = None\n',
            "remove_filter_box",
        ),
        (
            '        self.lbl_refresh_countdown = QLabel("Обновление через: —")',
            '        self.lbl_refresh_countdown = QLabel("Обновление таблиц через: —")',
            "rename_refresh_label",
        ),
        (
            '        self.lbl_blocked_count = QLabel("Блокировок: 0")',
            '        self.lbl_blocked_count = QLabel("Бан-лист через: —")',
            "blocked_label_text",
        ),
        (
            '        self.refresh_blocked_instruments_view()\n        self.append_log("Бот запущен пользователем")',
            '        self._blocked_countdown_sec = self._blocked_refresh_interval_sec\n        self.refresh_blocked_instruments_view()\n        self._update_blocked_countdown_label()\n        self.append_log("Бот запущен пользователем")',
            "launch_engine_blocked_counter",
        ),
        (
            '        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec\n        self._sync_toggle_button_state()\n        self._update_refresh_countdown_label()\n        self.refresh_blocked_instruments_view()',
            '        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec\n        self._blocked_countdown_sec = self._blocked_refresh_interval_sec\n        self._sync_toggle_button_state()\n        self._update_refresh_countdown_label()\n        self._update_blocked_countdown_label()\n        self.refresh_blocked_instruments_view()',
            "stop_engine_blocked_counter",
        ),
        (
            '    def toggle_engine(self) -> None:\n        if self.worker and self.worker.isRunning():\n            self.stop_engine()\n            return\n        if self.current_cfg is None:\n            self.start_window._emit_start()\n            if self.current_cfg is None:\n                return\n        self.launch_engine(self.current_cfg)\n',
            '''    def toggle_engine(self) -> None:
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
''',
            "toggle_engine",
        ),
        (
            '    def _update_refresh_countdown_label(self) -> None:\n        if not hasattr(self, "lbl_refresh_countdown"):\n            return\n        if self.engine and self.worker and self.worker.isRunning():\n            self.lbl_refresh_countdown.setText(f"Обновление через: {max(0, int(self._snapshot_countdown_sec))} сек")\n        else:\n            self.lbl_refresh_countdown.setText("Обновление через: —")\n',
            '''    def _update_refresh_countdown_label(self) -> None:
        if not hasattr(self, "lbl_refresh_countdown"):
            return
        if self.engine and self.worker and self.worker.isRunning():
            self.lbl_refresh_countdown.setText(f"Обновление таблиц через: {max(0, int(self._snapshot_countdown_sec))} сек")
        else:
            self.lbl_refresh_countdown.setText("Обновление таблиц через: —")

    def _update_blocked_countdown_label(self) -> None:
        if not hasattr(self, "lbl_blocked_count"):
            return
        if self.engine and self.worker and self.worker.isRunning():
            self.lbl_blocked_count.setText(f"Бан-лист через: {max(0, int(self._blocked_countdown_sec))} сек")
        else:
            self.lbl_blocked_count.setText("Бан-лист через: —")
''',
            "refresh_countdown_helpers",
        ),
        (
            '    def _on_gui_timer_tick(self) -> None:\n        self.refresh_blocked_instruments_view()\n\n        if self.engine and self.worker and self.worker.isRunning():\n            self._snapshot_countdown_sec -= 1\n            if self._snapshot_countdown_sec <= 0:\n                self.request_snapshot()\n                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec\n        else:\n            self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec\n\n        self._update_refresh_countdown_label()\n',
            '''    def _on_gui_timer_tick(self) -> None:
        if self.engine and self.worker and self.worker.isRunning():
            self._snapshot_countdown_sec -= 1
            self._blocked_countdown_sec -= 1

            if self._snapshot_countdown_sec <= 0:
                self.request_snapshot()
                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec

            if self._blocked_countdown_sec <= 0:
                self.refresh_blocked_instruments_view()
                self._blocked_countdown_sec = self._blocked_refresh_interval_sec
        else:
            self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
            self._blocked_countdown_sec = self._blocked_refresh_interval_sec

        self._update_refresh_countdown_label()
        self._update_blocked_countdown_label()
''',
            "gui_tick",
        ),
        (
            '    def apply_filters(self) -> None:\n        if not self.latest_snapshot:\n            self.table_model.update_rows([])\n            self.closed_table_model.update_rows([])\n            return\n        search = self.filter_text.text().strip().lower()\n        side_filter = self.filter_side.currentText()\n        pnl_filter = self.filter_pnl.currentText()\n\n        def match(row: dict) -> bool:\n            inst = str(row.get("inst_id", "")).lower()\n            if is_hidden_instrument(row.get("inst_id")):\n                return False\n            side = str(row.get("side", "")).lower()\n            pnl_pct = float(row.get("pnl_pct", 0.0))\n            if search and search not in inst:\n                return False\n            if side_filter == "Long" and side != "long":\n                return False\n            if side_filter == "Short" and side != "short":\n                return False\n            if pnl_filter == "Прибыльные" and pnl_pct < 0:\n                return False\n            if pnl_filter == "Убыточные" and pnl_pct >= 0:\n                return False\n            return True\n\n        open_rows = [row for row in self.latest_snapshot.get("open_positions", []) if match(row)]\n        open_rows.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)\n        self.table_model.update_rows(open_rows)\n\n        closed_rows = [row for row in self.latest_snapshot.get("closed_trades", []) if match(row)]\n        closed_rows.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)\n        self.closed_table_model.update_rows(closed_rows)\n',
            '''    def apply_filters(self) -> None:
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
''',
            "apply_filters_simplified",
        ),
        (
            '    def append_log(self, message: str) -> None:\n        upper_message = str(message).upper()\n        if "BREV-" in upper_message:\n            return\n',
            '    def append_log(self, message: str) -> None:\n        upper_message = str(message).upper()\n        if "BREV-" in upper_message or "LINK-USDT" in upper_message:\n            return\n',
            "append_log_hidden",
        ),
        (
            '        self.closed_table = QTableView()',
            '        self.closed_table = QTableView()',
            "dummy_closed_table",
        ),
    ]

    for old, new, label in replacements:
        if old == new:
            continue
        text = replace_once(text, old, new, label)

    extra_old = '''
class StartWindow(QWidget):
    start_requested = pyqtSignal(BotConfig)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — параметры запуска")
        self.setMinimumWidth(520)
        self._build_ui()
        self.apply_system_theme()
'''.strip("\n")

    extra_new = '''
class StartWindow(QWidget):
    start_requested = pyqtSignal(BotConfig)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — параметры запуска")
        self.setMinimumWidth(520)
        self._build_ui()
        self.apply_system_theme()
'''.strip("\n")
    text = replace_once(text, extra_old, extra_new, "startwindow_anchor")

    emit_old = '''
    def _emit_start(self) -> None:
        load_dotenv(APP_DIR / ".env")
        api_key = os.getenv("OKX_API_KEY", "")
        secret_key = os.getenv("OKX_SECRET_KEY", "")
        passphrase = os.getenv("OKX_PASSPHRASE", "")
        telegram_enabled = os.getenv("TELEGRAM_ENABLED", "0").strip() == "1"
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not all([api_key, secret_key, passphrase]):
            QMessageBox.critical(self, "Нет ключей", "Создай файл .env рядом с main.py и заполни OKX_API_KEY / OKX_SECRET_KEY / OKX_PASSPHRASE")
            return
        cfg = BotConfig(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            flag="0" if self.account_combo.currentIndex() == 0 else "1",
            timeframe=self.timeframe_combo.currentData(),
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
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )
        self.start_requested.emit(cfg)
'''.strip("\n")

    emit_new = '''
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
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            blacklist=["USDC-USDT-SWAP", "XSR-USDT-SWAP", "BREV-USDT-SWAP", "LINK-USDT-SWAP"],
        )

    def _emit_start(self) -> None:
        cfg = self.build_config()
        self.start_requested.emit(cfg)
'''.strip("\n")

    text = replace_once(text, emit_old, emit_new, "startwindow_build_config")

    sync_old = '''
        open_pnl = sum(float(x.get("unrealized_pnl", 0.0)) for x in open_positions)
        longs = sum(1 for x in open_positions if x.get("side") == "long")
        shorts = sum(1 for x in open_positions if x.get("side") == "short")
        avg_pnl_pct = sum(float(x.get("pnl_pct", 0.0)) for x in open_positions) / len(open_positions) if open_positions else 0.0
        best_open = max((float(x.get("pnl_pct", 0.0)) for x in open_positions), default=0.0)
        worst_open = min((float(x.get("pnl_pct", 0.0)) for x in open_positions), default=0.0)
        realized_pnl = sum(x.pnl for x in self.closed_trades)
        wins = sum(1 for x in self.closed_trades if x.pnl > 0)
        losses = sum(1 for x in self.closed_trades if x.pnl < 0)
        winrate = wins / len(self.closed_trades) * 100.0 if self.closed_trades else 0.0
'''.strip("\n")

    sync_new = '''
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
'''.strip("\n")

    text = replace_once(text, sync_old, sync_new, "emit_snapshot_stats_filter")

    payload_old = '''            "open_positions": open_positions,
            "closed_trades": [asdict(x) for x in reversed([x for x in self.closed_trades[-500:] if not is_hidden_instrument(x.inst_id)])],
'''
    payload_new = '''            "open_positions": [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))],
            "closed_trades": [asdict(x) for x in reversed([x for x in visible_closed_trades[-500:] if not is_hidden_instrument(x.inst_id)])],
'''
    text = replace_once(text, payload_old, payload_new, "payload_open_positions_hidden")

    snapshot_log_old = '''            open_positions=len(open_positions),
            closed_trades=len(self.closed_trades),
'''
    snapshot_log_new = '''            open_positions=len(visible_open_positions),
            closed_trades=len(visible_closed_trades),
'''
    text = replace_once(text, snapshot_log_old, snapshot_log_new, "snapshot_log_counts")

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:  {BACKUP_FILE.resolve()}")
    print(f"Updated: {TARGET_FILE.resolve()}")
    print("Новая версия: v023")


if __name__ == "__main__":
    main()