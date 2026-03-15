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


def build_main_window_ui(window, deps):
    APP_VERSION = deps["APP_VERSION"]
    AnimatedGridWidget = deps["AnimatedGridWidget"]
    NeonPanel = deps["NeonPanel"]
    MarketPulseTile = deps["MarketPulseTile"]
    GlowBandWidget = deps["GlowBandWidget"]
    LaunchConfigWidget = deps["LaunchConfigWidget"]
    NeonRadarWidget = deps["NeonRadarWidget"]
    NeonGlyphWidget = deps["NeonGlyphWidget"]
    BalanceChartWidget = deps["BalanceChartWidget"]

    root = AnimatedGridWidget()
    window.bg_terminal = root
    window.setCentralWidget(root)

    layout = QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    # Header
    header = QFrame()
    header.setObjectName("CyberHeader")
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(12, 6, 12, 6)
    header_layout.setSpacing(3)

    window.lbl_terminal_title = QLabel(
        f"OKX TURTLE BOT {APP_VERSION}  —  CYBERPUNK QUANT TRADING TERMINAL"
    )
    window.lbl_terminal_title.setObjectName("CyberHeaderTitle")
    header_layout.addWidget(window.lbl_terminal_title)

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
    for chip in (
        window.lbl_header_mode,
        window.lbl_header_status_chip,
        window.lbl_header_tf_chip,
        window.lbl_header_pos_chip,
        window.lbl_header_uptime_chip,
    ):
        chip_row.addWidget(chip)
    chip_row.addStretch(1)
    header_layout.addLayout(chip_row)

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
    header_layout.addLayout(sys_row)
    layout.addWidget(header, stretch=0)

    # Main columns
    main_row = QHBoxLayout()
    main_row.setSpacing(8)

    left_col = QVBoxLayout()
    left_col.setSpacing(8)
    center_col = QVBoxLayout()
    center_col.setSpacing(8)
    right_col = QVBoxLayout()
    right_col.setSpacing(8)

    # Command deck
    window.start_window = LaunchConfigWidget(window)
    window.start_window.start_requested.connect(window.set_pending_config)
    launch_box = NeonPanel("Command Deck")
    launch_layout = QVBoxLayout(launch_box)
    launch_layout.setContentsMargins(8, 10, 8, 8)
    launch_layout.setSpacing(5)
    launch_layout.addWidget(window.start_window)

    button_grid = QGridLayout()
    button_grid.setHorizontalSpacing(6)
    button_grid.setVerticalSpacing(5)

    window.btn_start_bot = QPushButton("START BOT")
    window.btn_start_bot.setObjectName("toggleBotButton")
    window.btn_start_bot.setMinimumHeight(40)
    window.btn_start_bot.clicked.connect(window.toggle_engine)
    button_grid.addWidget(window.btn_start_bot, 0, 0, 1, 2)

    window.mode_switch_toggle = QPushButton()
    window.mode_switch_toggle.setCheckable(True)
    window.mode_switch_toggle.clicked.connect(window.on_trade_mode_changed)
    window.mode_switch_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    window.mode_switch_toggle.setMinimumHeight(30)
    button_grid.addWidget(window.mode_switch_toggle, 1, 0, 1, 2)

    window.btn_export_analysis = QPushButton("EXPORT / СДАТЬ АНАЛИЗЫ")
    window.btn_export_analysis.setMinimumHeight(32)
    window.btn_export_analysis.clicked.connect(window.export_analysis_bundle)
    button_grid.addWidget(window.btn_export_analysis, 2, 0)

    window.btn_reset_test = QPushButton("RESET ТЕСТА")
    window.btn_reset_test.setMinimumHeight(32)
    window.btn_reset_test.clicked.connect(window.reset_test_run)
    button_grid.addWidget(window.btn_reset_test, 2, 1)

    window.btn_clear_bans = QPushButton("ОЧИСТИТЬ БАН-ЛИСТ")
    window.btn_clear_bans.setMinimumHeight(32)
    window.btn_clear_bans.clicked.connect(window.clear_ban_lists)
    button_grid.addWidget(window.btn_clear_bans, 3, 0, 1, 2)

    window.toggle_button = window.btn_start_bot
    launch_layout.addLayout(button_grid)
    launch_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    left_col.addWidget(launch_box, stretch=0)

    # Balance hub
    balance_box = NeonPanel("Balance Hub")
    balance_layout = QVBoxLayout(balance_box)
    balance_layout.setContentsMargins(10, 14, 10, 10)
    balance_layout.setSpacing(6)

    window.lbl_status = QLabel("Статус: ожидание запуска")
    window.lbl_status.setProperty("chip", "true")
    window.lbl_status.hide()
    balance_layout.addWidget(window.lbl_status)

    window.lbl_balance_hero_title = QLabel("BALANCE OVERVIEW")
    window.lbl_balance_hero_title.setProperty("metricTitle", "true")
    balance_layout.addWidget(window.lbl_balance_hero_title)

    metric_grid = QGridLayout()
    metric_grid.setContentsMargins(0, 0, 0, 0)
    metric_grid.setHorizontalSpacing(8)
    metric_grid.setVerticalSpacing(8)

    window.lbl_balance_hero = QLabel("BALANCE\n0 USDT")
    window.lbl_balance_hero.setProperty("card", "true")
    window.lbl_balance_used = QLabel("USED\n0 USDT")
    window.lbl_balance_used.setProperty("card", "true")
    window.lbl_balance_available = QLabel("AVAILABLE\n0 USDT")
    window.lbl_balance_available.setProperty("card", "true")
    window.lbl_balance_equity = QLabel("BALANCE - USED = AVAILABLE\n0 - 0 = 0")
    window.lbl_balance_equity.setProperty("card", "true")
    window.lbl_balance_formula = window.lbl_balance_equity

    metric_grid.addWidget(window.lbl_balance_hero, 0, 0)
    metric_grid.addWidget(window.lbl_balance_used, 0, 1)
    metric_grid.addWidget(window.lbl_balance_available, 0, 2)
    metric_grid.addWidget(window.lbl_balance_equity, 1, 0, 1, 3)
    balance_layout.addLayout(metric_grid)

    window.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
    window.lbl_balance_summary.setProperty("card", "true")
    window.lbl_session_pnl = QLabel("Session PnL: 0.00 USDT")
    window.lbl_session_pnl.setProperty("card", "true")
    window.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
    window.lbl_balance_trend.setProperty("card", "true")
    window.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
    window.lbl_risk_panel.setProperty("card", "true")
    for widget in (
        window.lbl_balance_summary,
        window.lbl_session_pnl,
        window.lbl_balance_trend,
        window.lbl_risk_panel,
    ):
        balance_layout.addWidget(widget)
    left_col.addWidget(balance_box, stretch=3)

    # Risk radar
    risk_box = NeonPanel("Risk Radar")
    risk_layout = QGridLayout(risk_box)
    risk_layout.setContentsMargins(10, 12, 10, 10)
    risk_layout.setHorizontalSpacing(8)
    risk_layout.setVerticalSpacing(6)

    window.lbl_positions = QLabel("Открытых позиций: 0")
    window.lbl_positions.setProperty("card", "true")
    window.lbl_runtime = QLabel("Время работы: —")
    window.lbl_runtime.setProperty("card", "true")
    window.lbl_cycle_duration = QLabel("Цикл движка: —")
    window.lbl_cycle_duration.setProperty("card", "true")
    window.lbl_blocked_count = QLabel("Блокировок: 0")
    window.lbl_blocked_count.setProperty("card", "true")
    window.lbl_close_pending = QLabel("Close pending: 0")
    window.lbl_close_pending.setProperty("card", "true")
    window.lbl_exec_watch = QLabel("Execution watchlist: 0")
    window.lbl_exec_watch.setProperty("card", "true")

    risk_layout.addWidget(window.lbl_positions, 0, 0)
    risk_layout.addWidget(window.lbl_runtime, 0, 1)
    risk_layout.addWidget(window.lbl_cycle_duration, 1, 0)
    risk_layout.addWidget(window.lbl_blocked_count, 1, 1)
    risk_layout.addWidget(window.lbl_close_pending, 2, 0)
    risk_layout.addWidget(window.lbl_exec_watch, 2, 1)

    window.risk_radar_visual = NeonRadarWidget()
    risk_layout.addWidget(window.risk_radar_visual, 0, 2, 3, 1)
    risk_layout.setColumnStretch(0, 1)
    risk_layout.setColumnStretch(1, 1)
    risk_layout.setColumnStretch(2, 2)
    left_col.addWidget(risk_box, stretch=2)

    # Equity pulse
    chart_box = NeonPanel("Equity Pulse")
    chart_layout = QVBoxLayout(chart_box)
    chart_layout.setContentsMargins(10, 12, 10, 10)
    chart_layout.setSpacing(5)

    chart_top = QHBoxLayout()
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
    window.balance_chart_step_combo.setMinimumWidth(140)
    window.balance_chart_step_combo.currentIndexChanged.connect(window.on_balance_chart_step_changed)
    chart_top.addWidget(window.balance_chart_step_combo)

    window.lbl_balance_step = QLabel("Шаг: 1m")
    window.lbl_balance_step.setProperty("chip", "true")
    chart_top.addWidget(window.lbl_balance_step)

    window.lbl_balance_points = QLabel("Показано значений: 0/30")
    window.lbl_balance_points.setProperty("chip", "true")
    chart_top.addWidget(window.lbl_balance_points)

    chart_layout.addLayout(chart_top)

    window.balance_chart = BalanceChartWidget()
    window.balance_chart.set_dark_theme(True)
    window.balance_chart.setMinimumHeight(220)
    chart_layout.addWidget(window.balance_chart, 1)
    center_col.addWidget(chart_box, stretch=5)

    # Market radar
    radar_box = NeonPanel("Market Radar")
    radar_layout = QGridLayout(radar_box)
    radar_layout.setContentsMargins(10, 12, 10, 10)
    radar_layout.setHorizontalSpacing(8)
    radar_layout.setVerticalSpacing(8)
    window.market_tiles = []
    for i, symbol in enumerate(["BTC", "ETH", "SOL", "LINK", "ATOM", "MINA"]):
        tile = MarketPulseTile(symbol)
        window.market_tiles.append(tile)
        radar_layout.addWidget(tile, i // 3, i % 3)
    center_col.addWidget(radar_box, stretch=3)

    # Analytics matrix
    analytics_box = NeonPanel("Analytics Matrix")
    analytics_layout = QGridLayout(analytics_box)
    analytics_layout.setContentsMargins(10, 12, 10, 10)
    analytics_layout.setHorizontalSpacing(8)
    analytics_layout.setVerticalSpacing(6)

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
    right_col.addWidget(analytics_box, stretch=2)

    # Turtle signal center
    turtle_box = NeonPanel("Turtle Signal Center")
    turtle_layout = QVBoxLayout(turtle_box)
    turtle_layout.setContentsMargins(10, 12, 10, 10)
    turtle_layout.setSpacing(6)

    window.turtle_glyph = NeonGlyphWidget()
    window.turtle_glyph.setMinimumSize(92, 92)
    window.turtle_glyph.setMaximumHeight(104)
    turtle_layout.addWidget(window.turtle_glyph, alignment=Qt.AlignmentFlag.AlignHCenter)

    window.lbl_turtle_regime = QLabel("Turtle-индикатор: ожидание кандидата | Entry allowed: NO")
    window.lbl_turtle_regime.setProperty("card", "true")
    window.lbl_turtle_regime.setMinimumHeight(42)
    window.lbl_turtle_regime.setWordWrap(True)
    window.lbl_turtle_state_a = QLabel("DONCHIAN / REGIME: waiting for breakout")
    window.lbl_turtle_state_a.setProperty("card", "true")
    window.lbl_turtle_state_b = QLabel("TREND / ATR: channel width and ATR will appear here")
    window.lbl_turtle_state_b.setProperty("card", "true")
    window.lbl_turtle_state_c = QLabel("LIQUIDITY: waiting | ATR: — | MODE: AUTO")
    window.lbl_turtle_state_c.setProperty("card", "true")
    window.lbl_turtle_score = QLabel("ENTRY STATUS: NO | ENGINE SCORE 0/4")
    window.lbl_turtle_score.setProperty("card", "true")

    for widget in (
        window.lbl_turtle_regime,
        window.lbl_turtle_state_a,
        window.lbl_turtle_state_b,
        window.lbl_turtle_state_c,
        window.lbl_turtle_score,
    ):
        turtle_layout.addWidget(widget)
    right_col.addWidget(turtle_box, stretch=2)

    # Activity feed
    activity_box = NeonPanel("Activity Feed")
    activity_layout = QVBoxLayout(activity_box)
    activity_layout.setContentsMargins(10, 12, 10, 10)

    window.activity_feed = QTextEdit()
    window.activity_feed.setObjectName("ActivityFeed")
    window.activity_feed.setReadOnly(True)
    window.activity_feed.setMinimumHeight(150)
    window.activity_feed.setHtml(
        '<span style="color:#6ee7ff;">[BOOT] Activity Feed ready</span><br>'
        '<span style="color:#00ffa3;">[INFO] Awaiting engine events...</span>'
    )
    activity_layout.addWidget(window.activity_feed)
    right_col.addWidget(activity_box, stretch=2)

    main_row.addLayout(left_col, 3)
    main_row.addLayout(center_col, 5)
    main_row.addLayout(right_col, 3)
    layout.addLayout(main_row, stretch=8)

    # Bottom tabs
    window.tabs = QTabWidget()

    window.table = QTableView()
    window.table.setMinimumHeight(320)
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

    window.blocked_table = QTableWidget()
    window.blocked_table.setColumnCount(4)
    window.blocked_table.setHorizontalHeaderLabels(["Инструмент", "Тип", "Причина", "Осталось"])
    window.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    window.blocked_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    window.blocked_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.blocked_table.setAlternatingRowColors(True)
    window.tabs.addTab(window.blocked_table, "Watchlist / Bans")

    window.tabs.setDocumentMode(True)
    window.tabs.setMinimumHeight(320)
    layout.addWidget(window.tabs, stretch=7)

    window.glow_band = GlowBandWidget()
    window.glow_band.setFixedHeight(24)
    layout.addWidget(window.glow_band, stretch=0)

    window.filter_text = None
    window.filter_side = None
    window.filter_pnl = None

    window.gui_timer = QTimer(window)
    window.gui_timer.timeout.connect(window._on_gui_timer_tick)
    window.gui_timer.start(1000)
