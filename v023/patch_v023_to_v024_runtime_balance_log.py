# patch_v023_to_v024_runtime_balance_log.py
# Патч для текущего main_v023.py
#
# Делает:
# 1) APP_VERSION -> v024
# 2) Добавляет счётчик времени работы программы
# 3) Убирает countdown бан-листа
# 4) Объединяет баланс/использовано/доступно в одну ячейку
# 5) Пишет в лог, с каким шагом запущен бот
# 6) Добавляет простую self-check проверку таймфрейма
#
# Использование:
#   python patch_v023_to_v024_runtime_balance_log.py

from pathlib import Path
import shutil
import sys

TARGET_FILE = Path("main_v023.py")
BACKUP_FILE = Path("main_v023.py.bak_v024_runtime_balance")


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

    text = replace_once(
        text,
        'APP_VERSION = "v023"',
        'APP_VERSION = "v024"',
        "app_version",
    )

    old_init = '''
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
        self._blocked_refresh_interval_sec = 10
        self._blocked_countdown_sec = 10
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
'''.strip("\n")

    new_init = '''
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
        self._bot_started_ts: Optional[float] = None
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
'''.strip("\n")
    text = replace_once(text, old_init, new_init, "mainwindow_init")

    old_metrics = '''
        self.lbl_status = QLabel("Статус: ожидание запуска")
        self.lbl_account = QLabel("Аккаунт: —")
        self.lbl_timeframe = QLabel("Таймфрейм: —")
        self.lbl_total = QLabel("Баланс: 0")
        self.lbl_available = QLabel("Доступно: 0")
        self.lbl_frozen = QLabel("Использовано: 0")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_last_update = QLabel("Последнее обновление: —")
        self.lbl_engine_cycle = QLabel("Последний цикл движка: —")
        self.lbl_snapshot_signal = QLabel("Последний snapshot: —")
        self.lbl_cycle_duration = QLabel("Цикл движка: —")
        self.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
        self.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
        self.lbl_trade_speed = QLabel("Сделок сегодня: 0 | Средняя длительность: —")
        labels = [
            self.lbl_status,
            self.lbl_account,
            self.lbl_timeframe,
            self.lbl_total,
            self.lbl_available,
            self.lbl_frozen,
            self.lbl_positions,
            self.lbl_last_update,
            self.lbl_engine_cycle,
            self.lbl_snapshot_signal,
            self.lbl_cycle_duration,
            self.lbl_balance_trend,
            self.lbl_risk_panel,
            self.lbl_trade_speed,
        ]
'''.strip("\n")

    new_metrics = '''
        self.lbl_status = QLabel("Статус: ожидание запуска")
        self.lbl_account = QLabel("Аккаунт: —")
        self.lbl_timeframe = QLabel("Таймфрейм: —")
        self.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_runtime = QLabel("Время работы: —")
        self.lbl_last_update = QLabel("Последнее обновление: —")
        self.lbl_engine_cycle = QLabel("Последний цикл движка: —")
        self.lbl_snapshot_signal = QLabel("Последний snapshot: —")
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
            self.lbl_last_update,
            self.lbl_engine_cycle,
            self.lbl_snapshot_signal,
            self.lbl_cycle_duration,
            self.lbl_balance_trend,
            self.lbl_risk_panel,
            self.lbl_trade_speed,
        ]
'''.strip("\n")
    text = replace_once(text, old_metrics, new_metrics, "metrics_labels")

    old_buttons = '''
        self.lbl_refresh_countdown = QLabel("Обновление таблиц через: —")
        self.lbl_refresh_countdown.setProperty("card", "true")
        self.lbl_refresh_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_refresh_countdown.setMinimumWidth(180)
        button_row.addWidget(self.lbl_refresh_countdown)

        self.lbl_blocked_count = QLabel("Бан-лист через: —")
        self.lbl_blocked_count.setProperty("card", "true")
        button_row.addWidget(self.lbl_blocked_count)
'''.strip("\n")

    new_buttons = '''
        self.lbl_refresh_countdown = QLabel("Обновление таблиц через: —")
        self.lbl_refresh_countdown.setProperty("card", "true")
        self.lbl_refresh_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_refresh_countdown.setMinimumWidth(180)
        button_row.addWidget(self.lbl_refresh_countdown)

        self.lbl_blocked_count = QLabel("Блокировок: 0")
        self.lbl_blocked_count.setProperty("card", "true")
        self.lbl_blocked_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(self.lbl_blocked_count)
'''.strip("\n")
    text = replace_once(text, old_buttons, new_buttons, "button_row_labels")

    old_launch = '''
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
        self._blocked_countdown_sec = self._blocked_refresh_interval_sec
        self.refresh_blocked_instruments_view()
        self._update_blocked_countdown_label()
        self.append_log("Бот запущен пользователем")
'''.strip("\n")

    new_launch = '''
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
        self._bot_started_ts = time.time()
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._sync_toggle_button_state()
        self._update_refresh_countdown_label()
        self.refresh_blocked_instruments_view()
        self.append_log(f"Бот запущен пользователем (шаг: {cfg.timeframe})")
        self.append_log(f"Проверка параметров запуска: GUI={self.start_window.timeframe_combo.currentData()} | Config={cfg.timeframe}")
'''.strip("\n")
    text = replace_once(text, old_launch, new_launch, "launch_engine")

    old_stop = '''
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
        self._blocked_countdown_sec = self._blocked_refresh_interval_sec
        self._sync_toggle_button_state()
        self._update_refresh_countdown_label()
        self._update_blocked_countdown_label()
        self.refresh_blocked_instruments_view()
'''.strip("\n")

    new_stop = '''
    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
            self.worker = None
        self._bot_running = False
        self._bot_started_ts = None
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._sync_toggle_button_state()
        self._update_refresh_countdown_label()
        self.refresh_blocked_instruments_view()
        if hasattr(self, "lbl_runtime"):
            self.lbl_runtime.setText("Время работы: —")
'''.strip("\n")
    text = replace_once(text, old_stop, new_stop, "stop_engine")

    old_refresh_helper = '''
    def _update_refresh_countdown_label(self) -> None:
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
'''.strip("\n")

    new_refresh_helper = '''
    def _update_refresh_countdown_label(self) -> None:
        if not hasattr(self, "lbl_refresh_countdown"):
            return
        if self.engine and self.worker and self.worker.isRunning():
            self.lbl_refresh_countdown.setText(f"Обновление таблиц через: {max(0, int(self._snapshot_countdown_sec))} сек")
        else:
            self.lbl_refresh_countdown.setText("Обновление таблиц через: —")

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
'''.strip("\n")
    text = replace_once(text, old_refresh_helper, new_refresh_helper, "helpers")

    old_tick = '''
    def _on_gui_timer_tick(self) -> None:
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
'''.strip("\n")

    new_tick = '''
    def _on_gui_timer_tick(self) -> None:
        if self.engine and self.worker and self.worker.isRunning():
            self._snapshot_countdown_sec -= 1

            if self._snapshot_countdown_sec <= 0:
                self.request_snapshot()
                self.refresh_blocked_instruments_view()
                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        else:
            self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec

        self._update_refresh_countdown_label()
        self._update_runtime_label()
'''.strip("\n")
    text = replace_once(text, old_tick, new_tick, "gui_timer_tick")

    old_start_engine_log = '''
        self.status.emit("Бот запущен")
        self.log_line.emit("Торговый движок запущен")
        self._notify("✅ OKX Turtle Bot запущен")
        self.run_loop()
'''.strip("\n")

    new_start_engine_log = '''
        self.status.emit("Бот запущен")
        self.log_line.emit(f"Торговый движок запущен (шаг: {self.cfg.timeframe})")
        self._notify("✅ OKX Turtle Bot запущен")
        self.run_loop()
'''.strip("\n")
    text = replace_once(text, old_start_engine_log, new_start_engine_log, "engine_start_log")

    old_snapshot_ui = '''
        self.lbl_account.setText(f"Аккаунт: {payload['settings']['account']}")
        self.lbl_timeframe.setText(f"Таймфрейм: {payload['settings']['timeframe']}")
        self.lbl_total.setText(f"Баланс: {payload['balance_total']:.0f}")
        self.lbl_available.setText(f"Доступно: {payload['balance_available']:.0f}")
        self.lbl_frozen.setText(f"Использовано: {payload.get('balance_used', 0.0):.0f}")
        self.lbl_positions.setText(f"Открытых позиций: {len(payload['open_positions'])}")
'''.strip("\n")

    new_snapshot_ui = '''
        self.lbl_account.setText(f"Аккаунт: {payload['settings']['account']}")
        self.lbl_timeframe.setText(f"Таймфрейм: {payload['settings']['timeframe']}")
        self.lbl_balance_summary.setText(
            f"Баланс: {payload['balance_total']:.0f} | "
            f"Использовано: {payload.get('balance_used', 0.0):.0f} | "
            f"Доступно: {payload['balance_available']:.0f}"
        )
        self.lbl_positions.setText(f"Открытых позиций: {len(payload['open_positions'])}")
'''.strip("\n")
    text = replace_once(text, old_snapshot_ui, new_snapshot_ui, "on_snapshot_balance_ui")

    old_clear_bans = '''
        if self.engine is None:
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
'''.strip("\n")

    new_clear_bans = '''
        if self.engine is None:
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
'''.strip("\n")
    text = replace_once(text, old_clear_bans, new_clear_bans, "clear_bans_label")

    # Небольшая коррекция аналитики: closed_count должно соответствовать видимым сделкам
    old_closed_count = '''                "closed_count": len(self.closed_trades),'''
    new_closed_count = '''                "closed_count": len(visible_closed_trades),'''
    text = replace_once(text, old_closed_count, new_closed_count, "analytics_closed_count")

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:  {BACKUP_FILE.resolve()}")
    print(f"Updated: {TARGET_FILE.resolve()}")
    print("Новая версия: v024")
    print()
    print("Что проверить:")
    print("1) В логе при запуске должны появиться строки:")
    print("   - Бот запущен пользователем (шаг: 5m/15m/...)")
    print("   - Проверка параметров запуска: GUI=... | Config=...")
    print("   - Торговый движок запущен (шаг: ...)")
    print("2) В статистике должна быть строка:")
    print("   - Время работы: 00:00:XX")
    print("3) Баланс должен показываться в одной ячейке:")
    print("   - Баланс | Использовано | Доступно")
    print("4) Countdown бан-листа должен исчезнуть, вместо него:")
    print("   - Блокировок: N")


if __name__ == "__main__":
    main()