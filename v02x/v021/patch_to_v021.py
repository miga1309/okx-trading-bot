from pathlib import Path
import re

SOURCE_FILE = "main_v0.20d_flatfix.py"
TARGET_FILE = "main_v021.py"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок для замены: {label}")
    return text.replace(old, new, 1)


def must_sub(text: str, pattern: str, repl: str, label: str) -> str:
    new_text, n = re.subn(pattern, repl, text, flags=re.S)
    if n != 1:
        raise RuntimeError(f"Ожидалась 1 замена для {label}, получено: {n}")
    return new_text


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
        'APP_VERSION = "v021"',
        text,
        count=1,
    )

    # -------------------------------------------------
    # BotConfig: новые параметры усиленного анти-флэта
    # -------------------------------------------------
    text = must_replace(
        text,
        '    pyramid_min_stop_distance_atr: float = 0.80\n',
        '    pyramid_min_stop_distance_atr: float = 0.80\n'
        '    breakout_buffer_atr: float = 0.18\n'
        '    breakout_min_body_atr: float = 0.65\n'
        '    breakout_close_near_extreme_ratio: float = 0.32\n'
        '    breakout_min_range_expansion: float = 1.15\n'
        '    breakout_max_prebreak_distance_atr: float = 2.8\n'
        '    breakout_retest_invalid_ratio: float = 0.55\n'
        '    breakout_volume_factor: float = 1.20\n'
        '    flat_max_repeated_close_ratio: float = 0.55\n'
        '    flat_max_inside_ratio: float = 0.72\n'
        '    flat_max_wick_to_range_ratio: float = 0.62\n'
        '    flat_min_channel_atr_ratio: float = 2.4\n'
        '    flat_max_micro_pullback_ratio: float = 0.82\n',
        'BotConfig extra fields',
    )

    # -------------------------------------------------
    # Полная замена build_app_stylesheet
    # ВАЖНО: в твоём файле блок заканчивается перед def setup_logging
    # -------------------------------------------------
    text = must_sub(
        text,
        r'def build_app_stylesheet\(is_dark: bool\) -> str:\n.*?\n(?=def setup_logging\(\) -> None:)',
        '''def build_app_stylesheet(is_dark: bool) -> str:
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
                padding: 4px 8px;
                min-height: 28px;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                padding: 4px 8px;
                min-height: 28px;
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
                padding: 8px 12px;
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
            padding: 4px 8px;
            min-height: 28px;
        }
        QLineEdit, QDoubleSpinBox, QSpinBox {
            padding: 4px 8px;
            min-height: 28px;
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
            padding: 8px 12px;
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
''',
        'replace build_app_stylesheet',
    )

    # -------------------------------------------------
    # StartWindow.apply_system_theme: убрать обращения к чужим виджетам
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))
        self.balance_chart.set_dark_theme(self._is_dark_theme)
        self.table.viewport().update()
        self.closed_table.viewport().update()
''',
        '''    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))
''',
        'StartWindow.apply_system_theme',
    )

    # -------------------------------------------------
    # StartWindow: скрыть риск
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setDecimals(2)
        self.risk_spin.setRange(0.1, 5.0)
        self.risk_spin.setValue(1.0)
        self.risk_spin.setSuffix(" %")
        form.addRow("Риск на сделку:", self.risk_spin)

        defaults_hint = QLabel(
            "Параметры стратегии зафиксированы под Turtle: S1 20/10, S2 55/20, ATR 20, стоп 2N."
        )
''',
        '''        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setDecimals(2)
        self.risk_spin.setRange(0.1, 5.0)
        self.risk_spin.setValue(1.0)
        self.risk_spin.setSuffix(" %")
        self.risk_spin.hide()

        defaults_hint = QLabel(
            "Параметры стратегии зафиксированы под Turtle v021: S1 20/10, S2 55/20, ATR 20, стоп 2N, усиленный anti-flat / anti-fake-breakout."
        )
''',
        'hide risk field in StartWindow',
    )

    text = must_replace(
        text,
        '        self.start_button = QPushButton("Запустить бота")\n',
        '        self.start_button = QPushButton("Применить параметры")\n',
        'StartWindow button label',
    )

    text = must_replace(
        text,
        '            risk_per_trade_pct=float(self.risk_spin.value()),\n',
        '            risk_per_trade_pct=1.0,\n',
        'fixed risk value',
    )

    # -------------------------------------------------
    # MainWindow: состояния
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.latest_snapshot: Optional[dict] = None
        self._is_dark_theme = False
        self._build_ui()
        self.apply_system_theme()
''',
        '''        self.latest_snapshot: Optional[dict] = None
        self.current_cfg: Optional[BotConfig] = None
        self._bot_running = False
        self._is_dark_theme = False
        self._build_ui()
        self.apply_system_theme()
        self._sync_toggle_button_state()
''',
        'MainWindow init state',
    )

    # -------------------------------------------------
    # MainWindow.apply_system_theme
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))
        if hasattr(self, "balance_chart") and self.balance_chart is not None:
            self.balance_chart.set_dark_theme(self._is_dark_theme)
        if hasattr(self, "table") and self.table is not None:
            self.table.viewport().update()
        if hasattr(self, "closed_table") and self.closed_table is not None:
            self.closed_table.viewport().update()
        if hasattr(self, "start_window") and self.start_window is not None:
            self.start_window.setStyleSheet("")
''',
        '''    def apply_system_theme(self) -> None:
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
''',
        'MainWindow.apply_system_theme',
    )

    # -------------------------------------------------
    # Start config instead of immediate launch
    # -------------------------------------------------
    text = must_replace(
        text,
        '        self.start_window.start_requested.connect(self.launch_engine)\n',
        '        self.start_window.start_requested.connect(self.set_pending_config)\n',
        'connect pending config',
    )

    # -------------------------------------------------
    # Убираем lbl_risk
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_risk = QLabel("Риск на сделку: —")
        self.lbl_last_update = QLabel("Последнее обновление: —")
''',
        '''        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_last_update = QLabel("Последнее обновление: —")
''',
        'remove lbl_risk label',
    )

    text = must_replace(
        text,
        '''            self.lbl_positions,
            self.lbl_risk,
            self.lbl_last_update,
''',
        '''            self.lbl_positions,
            self.lbl_last_update,
''',
        'remove lbl_risk from labels list',
    )

    # -------------------------------------------------
    # Кнопки и вкладки
    # -------------------------------------------------
    text = must_sub(
        text,
        r'        button_row = QHBoxLayout\(\)\n.*?        self\.gui_timer = QTimer\(self\)',
        '''        button_row = QHBoxLayout()
        self.toggle_button = QPushButton("Запустить бота")
        self.toggle_button.setObjectName("toggleBotButton")
        self.toggle_button.clicked.connect(self.toggle_engine)
        button_row.addWidget(self.toggle_button)

        self.btn_refresh = QPushButton("Обновить таблицу")
        self.btn_refresh.clicked.connect(self.request_snapshot)
        self.btn_refresh.setEnabled(False)
        button_row.addWidget(self.btn_refresh)
        button_row.addStretch(1)
        layout.addLayout(button_row)

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
        layout.addWidget(self.tabs, stretch=6)

        self.gui_timer = QTimer(self)''',
        'replace stop/log panels',
    )

    # -------------------------------------------------
    # Новые методы toggle/start
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def launch_engine(self, cfg: BotConfig) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Уже запущен", "Сначала останови текущего бота")
            return
        try:
            self.engine = TurtleEngine(cfg)
''',
        '''    def set_pending_config(self, cfg: BotConfig) -> None:
        self.current_cfg = cfg
        account = "Основной" if cfg.flag == "0" else "Демо"
        self.append_log(f"Параметры обновлены: {account}, {cfg.timeframe}")

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
        if self.current_cfg is None:
            self.start_window._emit_start()
            if self.current_cfg is None:
                return
        self.launch_engine(self.current_cfg)

    def launch_engine(self, cfg: BotConfig) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Уже запущен", "Сначала останови текущего бота")
            return
        self.current_cfg = cfg
        try:
            self.engine = TurtleEngine(cfg)
''',
        'insert toggle methods',
    )

    text = must_replace(
        text,
        '''        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self.btn_stop.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.append_log("Бот запущен пользователем")
''',
        '''        self.worker = WorkerThread(self.engine)
        self.worker.start()
        self._bot_running = True
        self._sync_toggle_button_state()
        self.btn_refresh.setEnabled(True)
        self.append_log("Бот запущен пользователем")
''',
        'launch engine state',
    )

    text = must_replace(
        text,
        '''    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
        self.btn_stop.setEnabled(False)
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
''',
        'stop engine state',
    )

    text = text.replace(
        '        self.lbl_risk.setText(f"Риск на сделку: {payload[\'settings\'][\'risk_per_trade_pct\']}%")\n',
        ''
    )

    text = must_replace(
        text,
        '''    def on_status(self, message: str) -> None:
        self.lbl_status.setText(f"Статус: {message}")
        if "запущен" in message.lower():
            self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 700;")
        elif "остановлен" in message.lower():
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 700;")
        else:
            self.lbl_status.setStyleSheet("")
        self.append_log(message)
''',
        '''    def on_status(self, message: str) -> None:
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
''',
        'on_status state sync',
    )

    # -------------------------------------------------
    # Усиленный anti-flat / anti-fake-breakout
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def evaluate_entry\(self, inst_id: str\) -> None:\n.*?    def calculate_atr_from_candles',
        '''    def evaluate_entry(self, inst_id: str) -> None:
        lookback = max(
            self.cfg.long_entry_period,
            self.cfg.short_entry_period,
            self.cfg.atr_period,
            self.cfg.long_exit_period,
            self.cfg.short_exit_period,
            self.cfg.flat_lookback_candles,
        ) + 8
        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback)
        if len(candles) < lookback:
            return

        last = candles[-1]
        price = float(last[4])
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            return

        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
        if is_flat:
            logging.info("%s: пропуск входа, flat-filter (%s)", inst_id, flat_reason)
            return

        structure_blocked, structure_reason = self._detect_structure_risk(candles, atr)
        if structure_blocked:
            logging.info("%s: пропуск входа, structure-filter (%s)", inst_id, structure_reason)
            return

        long_level = max(float(c[2]) for c in candles[-self.cfg.long_entry_period:])
        short_level = min(float(c[3]) for c in candles[-self.cfg.short_entry_period:])
        last_high = float(last[2])
        last_low = float(last[3])

        if last_high >= long_level:
            ok, reason = self._confirm_breakout(candles, atr, "long", long_level)
            if ok:
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side="long",
                    price=price,
                    atr=atr,
                    system_name="Turtle 55",
                    timeframe=self.cfg.timeframe,
                )
                self.enter_position(inst_id, "long", price, atr, "Turtle 55")
            else:
                self.stats_logger.log(
                    "entry_rejected",
                    inst_id=inst_id,
                    side="long",
                    price=price,
                    atr=atr,
                    reason=reason,
                )
                logging.info("%s: long-сигнал отклонён (%s)", inst_id, reason)
            return

        if last_low <= short_level:
            ok, reason = self._confirm_breakout(candles, atr, "short", short_level)
            if ok:
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side="short",
                    price=price,
                    atr=atr,
                    system_name="Turtle 20",
                    timeframe=self.cfg.timeframe,
                )
                self.enter_position(inst_id, "short", price, atr, "Turtle 20")
            else:
                self.stats_logger.log(
                    "entry_rejected",
                    inst_id=inst_id,
                    side="short",
                    price=price,
                    atr=atr,
                    reason=reason,
                )
                logging.info("%s: short-сигнал отклонён (%s)", inst_id, reason)

    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        lookback = min(len(candles), max(8, self.cfg.flat_lookback_candles))
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
                if abs(curr_move) <= abs(prev_move) * 1.1:
                    micro_pullbacks += 1
        micro_pullback_ratio = micro_pullbacks / max(1, len(closes) - 2)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.75

        if channel_range_pct < self.cfg.min_channel_range_pct:
            return True, f"узкий диапазон {channel_range_pct:.3f}%"
        if atr_pct < self.cfg.min_atr_pct:
            return True, f"низкий ATR {atr_pct:.3f}%"
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f}"
        if repeated_close_ratio >= self.cfg.flat_max_repeated_close_ratio:
            return True, f"повторяющиеся закрытия {repeated_close_ratio:.0%}"
        if avg_body_ratio < self.cfg.min_body_to_range_ratio:
            return True, f"маленькие тела свечей {avg_body_ratio:.2f}"
        if avg_wick_ratio > self.cfg.flat_max_wick_to_range_ratio:
            return True, f"слишком много теней {avg_wick_ratio:.2f}"
        if inside_ratio >= self.cfg.flat_max_inside_ratio:
            return True, f"слишком много inside-bars {inside_ratio:.0%}"
        if efficiency_ratio < self.cfg.min_efficiency_ratio:
            return True, f"низкая эффективность движения {efficiency_ratio:.2f}"
        if flip_ratio > self.cfg.max_direction_flip_ratio:
            return True, f"частая смена направления {flip_ratio:.0%}"
        if micro_pullback_ratio > self.cfg.flat_max_micro_pullback_ratio:
            return True, f"слишком много микроретестов {micro_pullback_ratio:.0%}"
        if volume_dry and efficiency_ratio < 0.45:
            return True, "затухающий объём в боковике"

        return False, "ok"

    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str]:
        if len(candles) < 12:
            return False, "ok"

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)
        if swing_span <= atr * 2.0:
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
            if false_breaks >= 2:
                return True, f"серия ложных выносов ({false_breaks})"

        base_touches_high = 0
        base_touches_low = 0
        top = max(highs)
        bottom = min(lows)
        threshold = atr * 0.35
        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1
        if base_touches_high >= 4 and base_touches_low >= 4 and swing_span < atr * 3.2:
            return True, "плотная база без выхода"

        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * 0.45)
        if close_cluster >= max(6, int(len(closes) * 0.65)):
            return True, "цена залипает у центра диапазона"

        return False, "ok"

    def _confirm_breakout(self, candles: List[List[float]], atr: float, side: str, level: float) -> tuple[bool, str]:
        if len(candles) < 6:
            return False, "недостаточно свечей для подтверждения"

        last = candles[-1]
        prev = candles[-2]
        prev2 = candles[-3]

        opn = float(last[1])
        high = float(last[2])
        low = float(last[3])
        close = float(last[4])
        volume = float(last[5]) if len(last) > 5 else 0.0

        last_range = max(high - low, 1e-12)
        prev_range = max(float(prev[2]) - float(prev[3]), 1e-12)
        body = abs(close - opn)

        avg_volume = 0.0
        vol_window = candles[-6:-1]
        if vol_window:
            vols = [float(c[5]) if len(c) > 5 else 0.0 for c in vol_window]
            avg_volume = sum(vols) / len(vols) if vols else 0.0

        if body < atr * self.cfg.breakout_min_body_atr:
            return False, f"слабое тело пробойной свечи {body / max(atr, 1e-12):.2f} ATR"

        if last_range < prev_range * self.cfg.breakout_min_range_expansion:
            return False, "нет расширения диапазона свечи"

        if avg_volume > 0 and volume < avg_volume * self.cfg.breakout_volume_factor:
            return False, "объём не подтверждает пробой"

        if side == "long":
            if close < level + atr * self.cfg.breakout_buffer_atr:
                return False, "закрытие не ушло выше уровня с запасом"
            if (high - close) / last_range > self.cfg.breakout_close_near_extreme_ratio:
                return False, "закрытие далеко от максимума свечи"
            prebreak_distance = max(0.0, level - float(prev[4]))
            if prebreak_distance > atr * self.cfg.breakout_max_prebreak_distance_atr:
                return False, "вход запоздал после уже ушедшего движения"
            if float(prev[2]) > level and float(prev[4]) < level - atr * 0.05:
                return False, "перед пробоем был слабый ложный вынос вверх"
            retest_depth = max(0.0, level - low)
            if retest_depth / last_range > self.cfg.breakout_retest_invalid_ratio:
                return False, "слишком глубокий ретест уровня внутри пробойной свечи"
            if float(prev[4]) > float(prev[1]) and float(prev2[4]) < float(prev2[1]) and close <= high - last_range * 0.25:
                return False, "покупатель не удержал импульс после разворота"
        else:
            if close > level - atr * self.cfg.breakout_buffer_atr:
                return False, "закрытие не ушло ниже уровня с запасом"
            if (close - low) / last_range > self.cfg.breakout_close_near_extreme_ratio:
                return False, "закрытие далеко от минимума свечи"
            prebreak_distance = max(0.0, float(prev[4]) - level)
            if prebreak_distance > atr * self.cfg.breakout_max_prebreak_distance_atr:
                return False, "вход запоздал после уже ушедшего движения"
            if float(prev[3]) < level and float(prev[4]) > level + atr * 0.05:
                return False, "перед пробоем был слабый ложный вынос вниз"
            retest_depth = max(0.0, high - level)
            if retest_depth / last_range > self.cfg.breakout_retest_invalid_ratio:
                return False, "слишком глубокий ретест уровня внутри пробойной свечи"
            if float(prev[4]) < float(prev[1]) and float(prev2[4]) > float(prev2[1]) and close >= low + last_range * 0.25:
                return False, "продавец не удержал импульс после разворота"

        return True, "ok"

    def calculate_atr_from_candles''',
        'replace evaluate_entry block',
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()