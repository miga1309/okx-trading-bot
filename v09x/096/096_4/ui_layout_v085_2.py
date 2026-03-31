
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

class StaticTerminalRoot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "idle"
        self.setObjectName("StaticTerminalRoot")
        self.setStyleSheet(
            "QWidget#StaticTerminalRoot {"
            "background: #050816;"
            "}"
        )

    def set_mode(self, mode: str):
        self._mode = str(mode or "idle").lower()
        self.update()


class StaticGlowBand(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StaticGlowBand")

    def set_series(self, series_a=None, series_b=None):
        # Compatibility shim: main window may still call glow_band.set_series(...)
        return None


def build_main_window_ui(window, deps):
    APP_VERSION = deps["APP_VERSION"]
    NeonPanel = deps["NeonPanel"]
    LaunchConfigWidget = deps["LaunchConfigWidget"]
    BalanceChartWidget = deps["BalanceChartWidget"]

    root = StaticTerminalRoot()
    window.bg_terminal = root
    window.setCentralWidget(root)

    layout = QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    header = QFrame()
    header.setObjectName("CyberHeader")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(10, 4, 10, 4)
    header_layout.setSpacing(8)

    header_left = QVBoxLayout()
    header_left.setContentsMargins(0, 0, 0, 0)
    header_left.setSpacing(2)

    window.lbl_terminal_title = QLabel(
        f"OKX TURTLE BOT {APP_VERSION}  —  TURTLE TRADING TERMINAL"
    )
    window.lbl_terminal_title.setObjectName("CyberHeaderTitle")
    header_left.addWidget(window.lbl_terminal_title)

    chip_row = QHBoxLayout()
    chip_row.setSpacing(5)
    window.lbl_header_mode = QLabel("ACCOUNT: DEMO")
    window.lbl_header_mode.setProperty("chip", "true")
    window.lbl_header_status_chip = QLabel("ENGINE: IDLE")
    window.lbl_header_status_chip.setProperty("chip", "true")
    window.lbl_header_tf_chip = QLabel("TF: —")
    window.lbl_header_tf_chip.setProperty("chip", "true")
    window.lbl_header_pos_chip = QLabel("POS: 0/16")
    window.lbl_header_pos_chip.setProperty("chip", "true")
    window.lbl_header_uptime_chip = QLabel("UPTIME: —")
    window.lbl_header_uptime_chip.setProperty("chip", "true")
    window.lbl_header_errors_chip = QLabel("ERRORS: 0")
    window.lbl_header_errors_chip.setProperty("chip", "true")
    for chip in (
        window.lbl_header_mode,
        window.lbl_header_status_chip,
        window.lbl_header_tf_chip,
        window.lbl_header_pos_chip,
        window.lbl_header_uptime_chip,
        window.lbl_header_errors_chip,
    ):
        chip_row.addWidget(chip)

    window.ui_mode_combo = QComboBox()
    window.ui_mode_combo.addItem("UI MODE: PERFORMANCE", "performance")
    window.ui_mode_combo.addItem("UI MODE: BALANCED", "balanced")
    window.ui_mode_combo.addItem("UI MODE: LOW", "low")
    window.ui_mode_combo.currentIndexChanged.connect(window.on_ui_mode_changed)
    window.ui_mode_combo.setMinimumHeight(28)
    window.ui_mode_combo.setMinimumWidth(210)
    window.ui_mode_combo.setMaximumWidth(250)
    chip_row.addWidget(window.ui_mode_combo, 0)

    chip_row.addStretch(1)
    header_left.addLayout(chip_row)

    sys_row = QHBoxLayout()
    sys_row.setSpacing(5)
    window.lbl_sys_api = QLabel()
    window.lbl_sys_engine = QLabel()
    window.lbl_sys_strategy = QLabel()
    window.lbl_sys_okx = QLabel()
    for chip in (
        window.lbl_sys_api,
        window.lbl_sys_engine,
        window.lbl_sys_strategy,
        window.lbl_sys_okx,
    ):
        chip.setProperty("syschip", "true")
        sys_row.addWidget(chip)
    sys_row.addStretch(1)
    header_left.addLayout(sys_row)

    header_layout.addLayout(header_left, 1)

    window.btn_reload_ui = QPushButton("RELOAD UI")
    window.btn_reload_ui.setObjectName("reloadUIButton")
    window.btn_reload_ui.setCursor(Qt.CursorShape.PointingHandCursor)
    window.btn_reload_ui.setMinimumHeight(30)
    window.btn_reload_ui.clicked.connect(window.reload_ui)
    header_layout.addWidget(window.btn_reload_ui, 0, Qt.AlignmentFlag.AlignVCenter)

    layout.addWidget(header, stretch=0)

    main_row = QHBoxLayout()
    main_row.setSpacing(8)

    left_col = QVBoxLayout()
    left_col.setSpacing(8)
    center_col = QVBoxLayout()
    center_col.setSpacing(8)
    right_col = QVBoxLayout()
    right_col.setSpacing(8)

    launch_box = NeonPanel("Command Deck")
    launch_layout = QVBoxLayout(launch_box)
    launch_layout.setContentsMargins(8, 4, 8, 8)
    launch_layout.setSpacing(3)
    window.start_window = LaunchConfigWidget(window)
    window.start_window.start_requested.connect(window.set_pending_config)
    launch_layout.addWidget(window.start_window)

    button_grid = QGridLayout()
    button_grid.setHorizontalSpacing(6)
    button_grid.setVerticalSpacing(4)

    window.btn_start_bot = QPushButton("START BOT")
    window.btn_start_bot.setObjectName("toggleBotButton")
    window.btn_start_bot.setMinimumHeight(36)
    window.btn_start_bot.clicked.connect(window.toggle_engine)
    button_grid.addWidget(window.btn_start_bot, 0, 0, 1, 2)

    window.mode_switch_toggle = QPushButton()
    window.mode_switch_toggle.setCheckable(True)
    window.mode_switch_toggle.clicked.connect(window.on_trade_mode_changed)
    window.mode_switch_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    window.mode_switch_toggle.setMinimumHeight(28)
    button_grid.addWidget(window.mode_switch_toggle, 1, 0, 1, 2)

    window.btn_export_analysis = QPushButton("СДАТЬ АНАЛИЗЫ")
    window.btn_export_analysis.setMinimumHeight(30)
    window.btn_export_analysis.clicked.connect(window.export_analysis_bundle)
    button_grid.addWidget(window.btn_export_analysis, 2, 0)

    window.btn_reset_test = QPushButton("RESET ТЕСТА")
    window.btn_reset_test.setMinimumHeight(30)
    window.btn_reset_test.clicked.connect(window.reset_test_run)
    button_grid.addWidget(window.btn_reset_test, 2, 1)

    window.btn_clear_bans = QPushButton("ОЧИСТИТЬ БАН-ЛИСТ")
    window.btn_clear_bans.setMinimumHeight(30)
    window.btn_clear_bans.clicked.connect(window.clear_ban_lists)
    button_grid.addWidget(window.btn_clear_bans, 3, 0, 1, 2)

    window.toggle_button = window.btn_start_bot
    launch_layout.addLayout(button_grid)
    launch_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    left_col.addWidget(launch_box, stretch=0)

    balance_box = NeonPanel("Balance Hub")
    balance_layout = QVBoxLayout(balance_box)
    balance_layout.setContentsMargins(8, 4, 8, 8)
    balance_layout.setSpacing(4)

    window.lbl_status = QLabel("Статус: ожидание запуска")
    window.lbl_status.setProperty("chip", "true")
    window.lbl_status.hide()
    balance_layout.addWidget(window.lbl_status)

    window.lbl_balance_hero_title = QLabel("BALANCE OVERVIEW")
    window.lbl_balance_hero_title.setProperty("metricTitle", "true")
    balance_layout.addWidget(window.lbl_balance_hero_title)

    metric_grid = QGridLayout()
    metric_grid.setContentsMargins(0, 0, 0, 0)
    metric_grid.setHorizontalSpacing(6)
    metric_grid.setVerticalSpacing(6)

    window.lbl_balance_hero = QLabel("BALANCE\n0 USDT")
    window.lbl_balance_hero.setProperty("card", "true")
    window.lbl_balance_used = QLabel("USED\n0 USDT")
    window.lbl_balance_used.setProperty("card", "true")
    window.lbl_balance_available = QLabel("AVAILABLE\n0 USDT")
    window.lbl_balance_available.setProperty("card", "true")
    window.lbl_balance_equity = QLabel("")
    window.lbl_balance_equity.hide()
    window.lbl_balance_formula = window.lbl_balance_equity

    metric_grid.addWidget(window.lbl_balance_hero, 0, 0)
    metric_grid.addWidget(window.lbl_balance_used, 0, 1)
    metric_grid.addWidget(window.lbl_balance_available, 0, 2)
    metric_grid.setColumnStretch(0, 1)
    metric_grid.setColumnStretch(1, 1)
    metric_grid.setColumnStretch(2, 1)
    balance_layout.addLayout(metric_grid)

    summary_grid = QGridLayout()
    summary_grid.setContentsMargins(0, 0, 0, 0)
    summary_grid.setHorizontalSpacing(6)
    summary_grid.setVerticalSpacing(6)

    window.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
    window.lbl_balance_summary.setProperty("card", "true")
    window.lbl_session_pnl = QLabel("Session PnL: 0.00 USDT")
    window.lbl_session_pnl.setProperty("card", "true")
    window.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
    window.lbl_balance_trend.setProperty("card", "true")
    window.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
    window.lbl_risk_panel.setProperty("card", "true")

    summary_grid.addWidget(window.lbl_balance_summary, 0, 0, 1, 2)
    summary_grid.addWidget(window.lbl_session_pnl, 1, 0)
    summary_grid.addWidget(window.lbl_risk_panel, 1, 1)
    summary_grid.addWidget(window.lbl_balance_trend, 2, 0, 1, 2)
    summary_grid.setColumnStretch(0, 1)
    summary_grid.setColumnStretch(1, 1)
    balance_layout.addLayout(summary_grid)
    left_col.addWidget(balance_box, stretch=1)

    chart_box = NeonPanel("Equity Pulse")
    chart_layout = QVBoxLayout(chart_box)
    chart_layout.setContentsMargins(6, 2, 6, 6)
    chart_layout.setSpacing(3)

    chart_top = QHBoxLayout()
    chart_top.setContentsMargins(0, 0, 0, 0)
    chart_top.setSpacing(4)
    window.lbl_balance_chart_title = QLabel("NEON EQUITY CURVE")
    window.lbl_balance_chart_title.setProperty("metricTitle", "true")
    chart_top.addWidget(window.lbl_balance_chart_title)
    chart_top.addStretch(1)

    window.balance_chart_step_combo = QComboBox()
    for text, data in [
        ("1 минута", "1m"),
        ("5 минут", "5m"),
        ("15 минут", "15m"),
        ("30 минут", "30m"),
        ("1 час", "1H"),
        ("1 день", "1D"),
    ]:
        window.balance_chart_step_combo.addItem(text, data)
    window.balance_chart_step_combo.setCurrentIndex(0)
    window.balance_chart_step_combo.setMinimumWidth(132)
    window.balance_chart_step_combo.currentIndexChanged.connect(window.on_balance_chart_step_changed)
    chart_top.addWidget(window.balance_chart_step_combo)

    window.lbl_balance_step = QLabel("Шаг: 1m")
    window.lbl_balance_step.hide()
    window.lbl_balance_points = QLabel("Показано значений: 0/30")
    window.lbl_balance_points.hide()

    chart_layout.addLayout(chart_top)

    window.balance_chart = BalanceChartWidget()
    window.balance_chart.set_dark_theme(True)
    window.balance_chart.setMinimumHeight(292)
    chart_layout.addWidget(window.balance_chart, 1)
    center_col.addWidget(chart_box, stretch=7)

    analytics_box = NeonPanel("Analytics Matrix")
    analytics_layout = QGridLayout(analytics_box)
    analytics_layout.setContentsMargins(8, 4, 8, 8)
    analytics_layout.setHorizontalSpacing(6)
    analytics_layout.setVerticalSpacing(4)

    window.lbl_account = QLabel("Аккаунт: —")
    window.lbl_account.setProperty("card", "true")
    window.lbl_account.hide()
    window.lbl_timeframe = QLabel("Таймфрейм: —")
    window.lbl_timeframe.setProperty("card", "true")
    window.lbl_timeframe.hide()
    window.lbl_open_pnl = QLabel("Open PnL: 0")
    window.lbl_open_pnl.setProperty("card", "true")
    window.lbl_realized = QLabel("Реализованный PnL: 0")
    window.lbl_realized.setProperty("card", "true")
    window.lbl_winrate = QLabel("Winrate: 0%")
    window.lbl_winrate.setProperty("card", "true")
    window.lbl_closed_stats = QLabel("Закрытых сделок: 0")
    window.lbl_closed_stats.setProperty("card", "true")
    window.lbl_avg_open = QLabel("Средний PnL %: 0")
    window.lbl_avg_open.setProperty("card", "true")
    window.lbl_best = QLabel("Лучший PnL %: 0")
    window.lbl_best.setProperty("card", "true")
    window.lbl_worst = QLabel("Худший PnL %: 0")
    window.lbl_worst.setProperty("card", "true")
    window.lbl_long_short = QLabel("Long/Short: 0 / 0")
    window.lbl_long_short.setProperty("card", "true")
    window.lbl_trade_speed = QLabel("Сделок сегодня: 0 | Средняя длительность: —")
    window.lbl_trade_speed.setProperty("card", "true")

    cards = [
        window.lbl_open_pnl,
        window.lbl_realized,
        window.lbl_winrate,
        window.lbl_closed_stats,
        window.lbl_avg_open,
        window.lbl_best,
        window.lbl_worst,
        window.lbl_long_short,
        window.lbl_trade_speed,
    ]
    positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0, 1, 2)]
    for card, pos in zip(cards, positions):
        if len(pos) == 2:
            analytics_layout.addWidget(card, pos[0], pos[1])
        else:
            analytics_layout.addWidget(card, pos[0], pos[1], pos[2], pos[3])
    right_col.addWidget(analytics_box, stretch=3)

    risk_box = NeonPanel("Risk Radar")
    risk_layout = QGridLayout(risk_box)
    risk_layout.setContentsMargins(8, 4, 8, 8)
    risk_layout.setHorizontalSpacing(6)
    risk_layout.setVerticalSpacing(6)

    window.lbl_positions = QLabel("POS: 0")
    window.lbl_runtime = QLabel("UPTIME: —")
    window.lbl_cycle_duration = QLabel("SCAN: —")
    window.lbl_blocked_count = QLabel("BLOCKS: 0")
    window.lbl_available_markets = QLabel("AVAIL: 0/0")
    window.lbl_ready_count = QLabel("READY: 0")
    window.lbl_close_pending = QLabel("CLOSE: 0")
    window.lbl_exec_watch = QLabel("WATCH: 0")
    risk_cards = [
        window.lbl_positions,
        window.lbl_runtime,
        window.lbl_cycle_duration,
        window.lbl_blocked_count,
        window.lbl_available_markets,
        window.lbl_ready_count,
        window.lbl_close_pending,
        window.lbl_exec_watch,
    ]
    for lbl in risk_cards:
        lbl.setProperty("card", "true")
        lbl.setMinimumHeight(38)
        lbl.setWordWrap(True)
    risk_positions = [(0,0),(0,1),(1,0),(1,1),(2,0),(2,1),(3,0),(3,1)]
    for card, pos in zip(risk_cards, risk_positions):
        risk_layout.addWidget(card, pos[0], pos[1])
    risk_box.hide()

    scanner_box = NeonPanel("Сканнер рынка")
    scanner_layout = QGridLayout(scanner_box)
    scanner_layout.setContentsMargins(8, 4, 8, 8)
    scanner_layout.setHorizontalSpacing(6)
    scanner_layout.setVerticalSpacing(6)

    window.lbl_scanner_total = QLabel("TOTAL: 0")
    window.lbl_scanner_scanned = QLabel("SCANNED: 0")
    window.lbl_scanner_allowed = QLabel("ALLOWED: 0")
    window.lbl_scanner_blocked = QLabel("BLOCKED: 0")
    window.lbl_scanner_dead = QLabel("МЁРТВЫЙ: 0")
    window.lbl_scanner_saw = QLabel("ПИЛА: 0")
    window.lbl_scanner_ripping = QLabel("РВАНЫЙ: 0")
    window.lbl_scanner_pending = QLabel("PENDING: 0")
    window.lbl_scanner_status = QLabel("STATUS: IDLE")
    scanner_cards = [
        window.lbl_scanner_total, window.lbl_scanner_scanned, window.lbl_scanner_allowed,
        window.lbl_scanner_blocked, window.lbl_scanner_dead, window.lbl_scanner_saw,
        window.lbl_scanner_ripping, window.lbl_scanner_pending, window.lbl_scanner_status,
    ]
    for lbl in scanner_cards:
        lbl.setProperty("card", "true")
        lbl.setMinimumHeight(38)
        lbl.setWordWrap(True)
    scanner_positions = [(0,0),(0,1),(1,0),(1,1),(2,0),(2,1),(3,0),(3,1),(4,0,1,2)]
    for card, pos in zip(scanner_cards, scanner_positions):
        if len(pos) == 2:
            scanner_layout.addWidget(card, pos[0], pos[1])
        else:
            scanner_layout.addWidget(card, pos[0], pos[1], pos[2], pos[3])
    right_col.addWidget(scanner_box, stretch=4)
    right_col.addStretch(1)

    main_row.addLayout(left_col, 4)
    main_row.addLayout(center_col, 7)
    main_row.addLayout(right_col, 4)
    layout.addLayout(main_row, stretch=7)

    # Hidden placeholders kept for compatibility with runtime update code.
    window.market_radar_box = None
    window.market_radar_content = None
    window.btn_market_radar_toggle = None
    window.market_tiles = []

    window.turtle_glyph = None
    window.lbl_turtle_regime = QLabel("")
    window.lbl_turtle_state_a = QLabel("")
    window.lbl_turtle_state_b = QLabel("")
    window.lbl_turtle_state_c = QLabel("")
    window.lbl_turtle_score = QLabel("")
    for lbl in (window.lbl_turtle_regime, window.lbl_turtle_state_a, window.lbl_turtle_state_b, window.lbl_turtle_state_c, window.lbl_turtle_score):
        lbl.hide()

    readable_cards = [
        window.lbl_balance_hero, window.lbl_balance_used, window.lbl_balance_available,
        window.lbl_balance_summary, window.lbl_session_pnl, window.lbl_balance_trend, window.lbl_risk_panel,
        window.lbl_cycle_duration, window.lbl_blocked_count,
        window.lbl_available_markets, window.lbl_ready_count, window.lbl_close_pending, window.lbl_exec_watch,
        window.lbl_scanner_total, window.lbl_scanner_scanned, window.lbl_scanner_allowed, window.lbl_scanner_blocked,
        window.lbl_scanner_dead, window.lbl_scanner_saw, window.lbl_scanner_ripping, window.lbl_scanner_pending, window.lbl_scanner_status,
        window.lbl_open_pnl, window.lbl_realized, window.lbl_winrate, window.lbl_closed_stats,
        window.lbl_avg_open, window.lbl_best, window.lbl_worst, window.lbl_long_short, window.lbl_trade_speed,
    ]
    for card in readable_cards:
        card.setWordWrap(True)
        card.setMinimumHeight(38)
    for card in (window.lbl_balance_hero, window.lbl_balance_used, window.lbl_balance_available):
        card.setMinimumHeight(44)

    window.tabs = QTabWidget()

    window.table = QTableView()
    window.table.setMinimumHeight(420)
    window.table.setModel(window.table_model)
    window.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    window.table.setAlternatingRowColors(True)
    window.table.doubleClicked.connect(window.show_open_position_context)
    window.tabs.addTab(window.table, "Trading Desk")

    window.closed_table = QTableView()
    window.closed_table.setModel(window.closed_table_model)
    window.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    window.closed_table.setAlternatingRowColors(True)
    window.closed_table.doubleClicked.connect(window.show_closed_trade_context)
    window.tabs.addTab(window.closed_table, "Closed Trades")

    window.log_text = QTextEdit()
    window.log_text.setReadOnly(True)
    window.tabs.addTab(window.log_text, "System Log")

    window.activity_feed = QTextEdit()
    window.activity_feed.setObjectName("ActivityFeed")
    window.activity_feed.setReadOnly(True)
    window.activity_feed.setHtml(
        '<span style="color:#6ee7ff;">[BOOT] Activity Feed ready</span><br>'
        '<span style="color:#00ffa3;">[INFO] Awaiting engine events...</span>'
    )
    window.tabs.addTab(window.activity_feed, "Activity Feed")

    window.market_scanner_tabs = QTabWidget()

    def _build_scanner_table():
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["Пара", "Первое", "Последнее", "Хиты", "Причина", "Вердикт", "Перепров.", "Комментарий"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        return table

    window.scanner_dead_table = _build_scanner_table()
    window.scanner_saw_table = _build_scanner_table()
    window.scanner_ripping_table = _build_scanner_table()
    window.scanner_good_table = _build_scanner_table()
    window.market_scanner_tabs.addTab(window.scanner_dead_table, "Мёртвый рынок")
    window.market_scanner_tabs.addTab(window.scanner_saw_table, "Пила")
    window.market_scanner_tabs.addTab(window.scanner_ripping_table, "Рваный рынок")
    window.market_scanner_tabs.addTab(window.scanner_good_table, "Хорошие сделки")
    window.tabs.addTab(window.market_scanner_tabs, "Сканнер рынка")

    window.blocked_table = QTableWidget()
    window.blocked_table.setColumnCount(4)
    window.blocked_table.setHorizontalHeaderLabels(["Инструмент", "Тип", "Причина", "Осталось"])
    window.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    window.blocked_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    window.blocked_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.blocked_table.setAlternatingRowColors(True)
    window.tabs.addTab(window.blocked_table, "Watchlist / Bans")

    window.tabs.setDocumentMode(True)
    window.tabs.setMinimumHeight(420)
    layout.addWidget(window.tabs, stretch=10)

    window.glow_band = StaticGlowBand()
    window.glow_band.setFixedHeight(10)
    window.glow_band.setStyleSheet(
        "background: #08111f; border: 1px solid #1c325a; border-radius: 6px;"
    )
    layout.addWidget(window.glow_band, stretch=0)

    window.lbl_ui_mode_hint = None
    window.filter_text = None
    window.filter_side = None
    window.filter_pnl = None

    window.gui_timer = QTimer(window)
    window.gui_timer.timeout.connect(window._on_gui_timer_tick)
    window.gui_timer.start(1000)
