# patch_v022_auto_refresh_10s_countdown.py
# Патч для текущего main_v022.py
#
# Что делает:
# 1) Убирает кнопку "Обновить таблицу"
# 2) Добавляет интерактивный счётчик "Обновление через: N сек"
# 3) Делает реальное обновление snapshot каждые 10 секунд через engine.emit_snapshot()
# 4) Бан-лист продолжает обновляться каждую секунду
#
# Использование:
#   python patch_v022_auto_refresh_10s_countdown.py

from pathlib import Path
import shutil
import sys

TARGET_FILE = Path("main_v022.py")
BACKUP_FILE = Path("main_v022.py.bak_auto_refresh_10s")


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

    old_init_block = '''
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
        self._bot_running = False
        self._last_banlist_render: str = ""
        self._is_dark_theme = False
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
'''.strip("\n")

    new_init_block = '''
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
        self._bot_running = False
        self._last_banlist_render: str = ""
        self._is_dark_theme = False
        self._snapshot_refresh_interval_sec = 10
        self._snapshot_countdown_sec = 10
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
'''.strip("\n")

    old_button_block = '''
        self.btn_refresh = QPushButton("Обновить таблицу")
        self.btn_refresh.clicked.connect(self.request_snapshot)
        self.btn_refresh.setEnabled(False)
        button_row.addWidget(self.btn_refresh)
'''.strip("\n")

    new_button_block = '''
        self.lbl_refresh_countdown = QLabel("Обновление через: —")
        self.lbl_refresh_countdown.setProperty("card", "true")
        self.lbl_refresh_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_refresh_countdown.setMinimumWidth(180)
        button_row.addWidget(self.lbl_refresh_countdown)
'''.strip("\n")

    old_timer_block = '''
        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.request_snapshot)
        self.gui_timer.timeout.connect(self.refresh_blocked_instruments_view)
        self.gui_timer.start(1000)
'''.strip("\n")

    new_timer_block = '''
        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self._on_gui_timer_tick)
        self.gui_timer.start(1000)
'''.strip("\n")

    old_launch_engine_block = '''
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
        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._sync_toggle_button_state()
        self.btn_refresh.setEnabled(True)
        self.refresh_blocked_instruments_view()
        self.append_log("Бот запущен пользователем")
'''.strip("\n")

    new_launch_engine_block = '''
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
        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._sync_toggle_button_state()
        self._update_refresh_countdown_label()
        self.refresh_blocked_instruments_view()
        self.append_log("Бот запущен пользователем")
'''.strip("\n")

    old_stop_engine_block = '''
    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
            self.worker = None
        self._bot_running = False
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
'''.strip("\n")

    new_stop_engine_block = '''
    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
            self.worker = None
        self._bot_running = False
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._sync_toggle_button_state()
        self._update_refresh_countdown_label()
        self.refresh_blocked_instruments_view()
'''.strip("\n")

    old_request_snapshot_block = '''
    def request_snapshot(self) -> None:
        if self.latest_snapshot:
            self.on_snapshot(self.latest_snapshot)
'''.strip("\n")

    new_request_snapshot_block = '''
    def request_snapshot(self) -> None:
        if self.engine and self.worker and self.worker.isRunning():
            try:
                self.engine.emit_snapshot()
                return
            except Exception as exc:
                self.append_log(f"Ошибка принудительного обновления таблицы: {exc}")
        if self.latest_snapshot:
            self.on_snapshot(self.latest_snapshot)
'''.strip("\n")

    insert_after_request_snapshot = '''
    def refresh_from_latest_snapshot(self) -> None:
        self.request_snapshot()
'''.strip("\n")

    replacement_request_snapshot_plus_helpers = '''
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
        if not hasattr(self, "lbl_refresh_countdown"):
            return
        if self.engine and self.worker and self.worker.isRunning():
            self.lbl_refresh_countdown.setText(f"Обновление через: {max(0, int(self._snapshot_countdown_sec))} сек")
        else:
            self.lbl_refresh_countdown.setText("Обновление через: —")

    def _on_gui_timer_tick(self) -> None:
        self.refresh_blocked_instruments_view()

        if self.engine and self.worker and self.worker.isRunning():
            self._snapshot_countdown_sec -= 1
            if self._snapshot_countdown_sec <= 0:
                self.request_snapshot()
                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        else:
            self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec

        self._update_refresh_countdown_label()

    def refresh_from_latest_snapshot(self) -> None:
        self.request_snapshot()
'''.strip("\n")

    text = replace_once(text, old_init_block, new_init_block, "init_block")
    text = replace_once(text, old_button_block, new_button_block, "button_refresh_block")
    text = replace_once(text, old_timer_block, new_timer_block, "gui_timer_block")
    text = replace_once(text, old_launch_engine_block, new_launch_engine_block, "launch_engine_block")
    text = replace_once(text, old_stop_engine_block, new_stop_engine_block, "stop_engine_block")
    text = replace_once(
        text,
        old_request_snapshot_block + "\n\n" + insert_after_request_snapshot,
        replacement_request_snapshot_plus_helpers,
        "request_snapshot_and_refresh_from_latest_snapshot",
    )

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:  {BACKUP_FILE.resolve()}")
    print(f"Updated: {TARGET_FILE.resolve()}")


if __name__ == "__main__":
    main()