from pathlib import Path
import re

SOURCE_FILE = "main_v021d.py"
TARGET_FILE = "main_v021d_banlist_gui.py"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок для замены: {label}")
    return text.replace(old, new, 1)


def patch() -> None:
    src = Path(SOURCE_FILE)
    if not src.exists():
        raise FileNotFoundError(f"Не найден исходный файл: {SOURCE_FILE}")

    text = src.read_text(encoding="utf-8")

    # -------------------------------------------------
    # Версия
    # -------------------------------------------------
    text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "v021d-banlist"',
        text,
        count=1,
    )

    # -------------------------------------------------
    # Импортировать time, если вдруг его нет
    # -------------------------------------------------
    if "\nimport time\n" not in text and "from time import" not in text:
        if "import sys\n" in text:
            text = text.replace("import sys\n", "import sys\nimport time\n", 1)
        else:
            text = "import time\n" + text

    # -------------------------------------------------
    # MainWindow state
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.latest_snapshot: Optional[dict] = None
        self.current_cfg: Optional[BotConfig] = None
        self._bot_running = False
        self._is_dark_theme = False
''',
        '''        self.latest_snapshot: Optional[dict] = None
        self.current_cfg: Optional[BotConfig] = None
        self._bot_running = False
        self._last_banlist_render: str = ""
        self._is_dark_theme = False
''',
        'mainwindow state',
    )

    # -------------------------------------------------
    # Кнопки + вкладки
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.toggle_button = QPushButton("Запустить бота")
        self.toggle_button.setObjectName("toggleBotButton")
        self.toggle_button.clicked.connect(self.toggle_engine)
        button_row.addWidget(self.toggle_button)

        self.btn_refresh = QPushButton("Обновить таблицу")
        self.btn_refresh.clicked.connect(self.request_snapshot)
        self.btn_refresh.setEnabled(False)
        button_row.addWidget(self.btn_refresh)
        button_row.addStretch(1)
        layout.addLayout(button_row, stretch=0)

        self.tabs = QTabWidget()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.tabs.addTab(self.table, "Открытые позиции")

        self.closed_table = QTableView()
        self.closed_table.setModel(self.closed_table_model)
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.closed_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.closed_table, "Закрытые сделки")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.tabs.addTab(self.log_text, "Лог работы")
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, stretch=14)

        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.request_snapshot)
        self.gui_timer.start(1000)
''',
        '''        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.toggle_button = QPushButton("Запустить бота")
        self.toggle_button.setObjectName("toggleBotButton")
        self.toggle_button.clicked.connect(self.toggle_engine)
        button_row.addWidget(self.toggle_button)

        self.btn_refresh = QPushButton("Обновить таблицу")
        self.btn_refresh.clicked.connect(self.request_snapshot)
        self.btn_refresh.setEnabled(False)
        button_row.addWidget(self.btn_refresh)

        self.lbl_blocked_count = QLabel("Блокировок: 0")
        self.lbl_blocked_count.setProperty("card", "true")
        button_row.addWidget(self.lbl_blocked_count)

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
        self.tabs.addTab(self.table, "Открытые позиции")

        self.closed_table = QTableView()
        self.closed_table.setModel(self.closed_table_model)
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.closed_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.closed_table, "Закрытые сделки")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.tabs.addTab(self.log_text, "Лог работы")

        self.blocked_text = QTextEdit()
        self.blocked_text.setReadOnly(True)
        self.tabs.addTab(self.blocked_text, "Бан-лист")

        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, stretch=14)

        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.request_snapshot)
        self.gui_timer.timeout.connect(self.refresh_blocked_instruments_view)
        self.gui_timer.start(1000)
''',
        'buttons and tabs',
    )

    # -------------------------------------------------
    # Вставляем методы перед set_pending_config
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def set_pending_config(self, cfg: BotConfig) -> None:
        self.current_cfg = cfg
        account = "Основной" if cfg.flag == "0" else "Демо"
        self.append_log(f"Параметры обновлены: {account}, {cfg.timeframe}")
''',
        '''    def _format_remaining(self, seconds_left: float) -> str:
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
        if not hasattr(self, "blocked_text"):
            return

        rows = self._collect_blocked_rows()

        if hasattr(self, "lbl_blocked_count"):
            self.lbl_blocked_count.setText(f"Блокировок: {len(rows)}")

        if not rows:
            rendered = "Активных блокировок нет."
        else:
            parts = []
            for idx, (inst_id, block_type, reason, ttl) in enumerate(rows, start=1):
                parts.append(
                    f"{idx}. {inst_id}\\n"
                    f"   Тип: {block_type}\\n"
                    f"   Причина: {reason}\\n"
                    f"   Осталось: {ttl}"
                )
            rendered = "\\n\\n".join(parts)

        if rendered != self._last_banlist_render:
            self._last_banlist_render = rendered
            self.blocked_text.setPlainText(rendered)

    def clear_ban_lists(self) -> None:
        if self.engine is None:
            self._last_banlist_render = ""
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
            if hasattr(self, "blocked_text"):
                self.blocked_text.setPlainText("Бан-лист очищен.")
            self.append_log("Бан-лист очищен (движок ещё не запущен)")
            return

        for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts"):
            data = getattr(self.engine, attr, None)
            if isinstance(data, dict):
                data.clear()

        self._last_banlist_render = ""
        self.refresh_blocked_instruments_view()
        self.append_log("Все заблокированные инструменты удалены из бан-листа")

    def set_pending_config(self, cfg: BotConfig) -> None:
        self.current_cfg = cfg
        account = "Основной" if cfg.flag == "0" else "Демо"
        self.append_log(f"Параметры обновлены: {account}, {cfg.timeframe}")
''',
        'insert ban methods',
    )

    # -------------------------------------------------
    # Обновлять бан-лист при запуске
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._sync_toggle_button_state()
        self.btn_refresh.setEnabled(True)
        self.append_log("Бот запущен пользователем")
''',
        '''        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._sync_toggle_button_state()
        self.btn_refresh.setEnabled(True)
        self.refresh_blocked_instruments_view()
        self.append_log("Бот запущен пользователем")
''',
        'launch refresh banlist',
    )

    # -------------------------------------------------
    # Обновлять бан-лист при остановке
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
        self._bot_running = False
        self._sync_toggle_button_state()
''',
        '''    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
        self._bot_running = False
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
''',
        'stop refresh banlist',
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()