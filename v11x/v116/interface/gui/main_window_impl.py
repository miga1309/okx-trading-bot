from app.runtime_support import *
from domain.trading.legacy_turtle_engine import TurtleEngine
from interface.gui.table_models import PositionTableModel, ClosedTradesTableModel
from interface.gui.chart_widgets import BalanceChartWidget
from interface.gui.runtime_threads import GuiLogBuffer, TelegramTaskThread, WorkerThread
from interface.gui.launch_config_widget import LaunchConfigWidget
from interface.gui.neon_widgets import NeonRadarWidget, NeonGlyphWidget
from interface.gui.analysis_export_dialog_runtime import AnalysisExportDialog

class MainWindow(QMainWindow):

    start_requested = pyqtSignal(BotConfig)
    manual_add_units_requested = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — Cyberpunk Quant Trading Terminal Reload UI")
        self.resize(1620, 1120)
        self.setMinimumSize(1480, 1060)

        self.engine = None
        self.worker = None
        self.current_cfg = None
        self.latest_snapshot = None
        self.table_model = PositionTableModel()
        self.closed_table_model = ClosedTradesTableModel()
        self._bot_running = False
        self._bot_started_ts = None
        self._snapshot_refresh_interval_sec = 2
        self._snapshot_countdown_sec = 0
        self._manual_dialog_open = False
        self._pending_manual_signal = None
        self._engine_transitioning = False
        self._engine_transition_action = ""
        self._telegram_screenshot_timer = None
        self._telegram_screenshot_interval_ms = 15 * 60 * 1000
        self._telegram_screenshot_start_delay_ms = 30 * 1000
        self._telegram_screenshot_inflight = False
        self._close_after_stop_requested = False
        self.telegram_ui_notifier = None
        self._telegram_workers = []
        self._telegram_worker_process = None
        self._telegram_worker_check_timer = QTimer(self)
        self._telegram_worker_check_timer.timeout.connect(self._refresh_telegram_controls)
        self._telegram_worker_check_timer.start(2000)
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._emit_gui_heartbeat)
        self._heartbeat_timer.start(60 * 1000)
        self._error_indicator_timer = QTimer(self)
        self._error_indicator_timer.timeout.connect(self._refresh_error_indicator)
        self._error_indicator_timer.start(1500)
        log_heartbeat("gui", "window_initialized", version=APP_VERSION)
        self._log_buffer = GuiLogBuffer(self, interval_ms=250, max_batch=32)
        self._log_buffer.flushed.connect(self._flush_log_batch)
        self._last_heavy_snapshot_at = 0.0
        self._runtime_ui_profile = "balanced"
        self.selected_ui_mode = "balanced"
        self.market_radar_expanded = False
        self._ui_mode_profiles = {
            "performance": {"gui_ms": 950, "panel_ms": 40, "grid_ms": 22, "spark_ms": 28, "band_ms": 40, "radar_ms": 28, "glyph_ms": 32},
            "balanced": {"gui_ms": 1300, "panel_ms": 48, "grid_ms": 28, "spark_ms": 34, "band_ms": 46, "radar_ms": 32, "glyph_ms": 36},
            "low": {"gui_ms": 2600, "panel_ms": 90, "grid_ms": 66, "spark_ms": 80, "band_ms": 96, "radar_ms": 78, "glyph_ms": 84},
        }
        self._runtime_transition_profile = {"gui_ms": 2300, "panel_ms": 150, "grid_ms": 135, "spark_ms": 160, "band_ms": 190, "radar_ms": 150, "glyph_ms": 160}
        self._runtime_trading_profiles = {
            "performance": {"gui_ms": 1150, "panel_ms": 52, "grid_ms": 30, "spark_ms": 38, "band_ms": 52, "radar_ms": 38, "glyph_ms": 40},
            "balanced": {"gui_ms": 1550, "panel_ms": 62, "grid_ms": 38, "spark_ms": 46, "band_ms": 60, "radar_ms": 44, "glyph_ms": 48},
            "low": {"gui_ms": 3000, "panel_ms": 105, "grid_ms": 76, "spark_ms": 92, "band_ms": 110, "radar_ms": 92, "glyph_ms": 98},
        }

        self._build_ui()
        self._setup_scanner_review_tables()
        self._update_scanner_review_views()
        self._update_system_health_indicators()
        self.apply_system_theme()
        self._apply_ui_mode_to_controls(self.selected_ui_mode)
        self._update_terminal_mode()
        self._sync_market_radar_toggle()
        self._apply_runtime_ui_profile()
        self._refresh_error_indicator()
        self._refresh_telegram_controls()

    def _refresh_error_indicator(self) -> None:
        try:
            count = int(RUNTIME_ERROR_TRACKER.count())
        except Exception:
            count = 0
        self._safe_set_label_text("lbl_header_errors_chip", f"ERRORS: {count}")
        if hasattr(self, "lbl_header_errors_chip") and self.lbl_header_errors_chip is not None:
            if count > 0:
                self.lbl_header_errors_chip.setStyleSheet("background:#7f1d1d;color:#ffe4e6;border:1px solid #ef4444;border-radius:10px;padding:4px 8px;font-weight:800;")
            else:
                self.lbl_header_errors_chip.setStyleSheet("")

    def _capture_ui_state(self) -> dict:
        state = {}
        try:
            if hasattr(self, "tabs") and self.tabs is not None:
                state["tab_index"] = int(self.tabs.currentIndex())
        except Exception:
            pass
        try:
            if hasattr(self, "balance_chart_step_combo") and self.balance_chart_step_combo is not None:
                state["balance_chart_step"] = self.balance_chart_step_combo.currentData()
        except Exception:
            pass
        try:
            if hasattr(self, "start_window") and self.start_window is not None:
                state["account_flag"] = self.start_window.account_combo.currentData()
                state["timeframe"] = self.start_window.timeframe_combo.currentData()
                state["trade_mode"] = getattr(self.start_window, "selected_trade_mode", "auto")
                state["ui_mode"] = getattr(self, "selected_ui_mode", "balanced")
                state["market_radar_expanded"] = bool(getattr(self, "market_radar_expanded", False))
        except Exception:
            pass
        try:
            if hasattr(self, "activity_feed") and self.activity_feed is not None:
                state["activity_feed_html"] = self.activity_feed.toHtml()
        except Exception:
            pass
        try:
            if hasattr(self, "log_text") and self.log_text is not None:
                state["system_log_text"] = self.log_text.toPlainText()
        except Exception:
            pass
        return state

    def _restore_ui_state(self, state: dict | None) -> None:
        state = dict(state or {})
        try:
            tf = state.get("timeframe")
            if tf is not None and hasattr(self, "start_window") and self.start_window is not None:
                idx = self.start_window.timeframe_combo.findData(tf)
                if idx >= 0:
                    self.start_window.timeframe_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            flag = state.get("account_flag")
            if flag is not None and hasattr(self, "start_window") and self.start_window is not None:
                idx = self.start_window.account_combo.findData(flag)
                if idx >= 0:
                    self.start_window.account_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            mode = state.get("trade_mode")
            if mode is not None and hasattr(self, "start_window") and self.start_window is not None:
                self.start_window.set_trade_mode(str(mode))
            if hasattr(self, "mode_switch_toggle"):
                self.mode_switch_toggle.setChecked(str(state.get("trade_mode", "auto")).lower() == "manual")
                self._sync_trade_mode_toggle()
        except Exception:
            pass
        try:
            ui_mode = str(state.get("ui_mode", getattr(self, "selected_ui_mode", "balanced")) or "balanced")
            self._apply_ui_mode_to_controls(ui_mode)
            self.market_radar_expanded = bool(state.get("market_radar_expanded", getattr(self, "market_radar_expanded", False)))
            if hasattr(self, "_sync_market_radar_toggle"):
                self._sync_market_radar_toggle()
        except Exception:
            pass
        try:
            step = state.get("balance_chart_step")
            if step is not None and hasattr(self, "balance_chart_step_combo") and self.balance_chart_step_combo is not None:
                idx = self.balance_chart_step_combo.findData(step)
                if idx >= 0:
                    self.balance_chart_step_combo.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            if hasattr(self, "activity_feed") and self.activity_feed is not None and state.get("activity_feed_html"):
                self.activity_feed.setHtml(state["activity_feed_html"])
        except Exception:
            pass
        try:
            if hasattr(self, "log_text") and self.log_text is not None and state.get("system_log_text") is not None:
                self.log_text.setPlainText(state["system_log_text"])
        except Exception:
            pass
        try:
            if hasattr(self, "tabs") and self.tabs is not None:
                idx = int(state.get("tab_index", 0) or 0)
                idx = max(0, min(idx, self.tabs.count() - 1))
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass
        try:
            self._sync_engine_controls_after_ui_reload()
            self._update_system_health_indicators()
            self.apply_system_theme()
            if hasattr(self, "update_ui"):
                self.update_ui()
            self._sync_market_radar_toggle()
        except Exception:
            pass

    def toggle_market_radar(self) -> None:
        self.market_radar_expanded = not bool(getattr(self, "market_radar_expanded", False))
        self._sync_market_radar_toggle()

    def _sync_market_radar_toggle(self) -> None:
        expanded = bool(getattr(self, "market_radar_expanded", False))
        if hasattr(self, "market_radar_content") and self.market_radar_content is not None:
            self.market_radar_content.setVisible(expanded)
        if hasattr(self, "btn_market_radar_toggle") and self.btn_market_radar_toggle is not None:
            self.btn_market_radar_toggle.setText("MARKET RADAR ▲" if expanded else "MARKET RADAR ▼")
            self.btn_market_radar_toggle.setChecked(expanded)
        if hasattr(self, "market_radar_box") and self.market_radar_box is not None:
            self.market_radar_box.updateGeometry()

    def _append_log_line(self, message: str) -> None:
        try:
            self.append_log(message)
        except Exception:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                line = f"[{ts}] {message}"
                if hasattr(self, "log_text") and self.log_text is not None:
                    self.log_text.append(line)
                if hasattr(self, "activity_feed") and self.activity_feed is not None:
                    self.activity_feed.append(line)
            except Exception:
                pass

    def _sync_engine_controls_after_ui_reload(self) -> None:
        running = bool(self.worker and self.worker.isRunning()) or bool(self.engine and getattr(self.engine, "running", False)) or bool(self._bot_running)
        self._bot_running = running
        self._sync_toggle_button_state()
        try:
            if hasattr(self, "lbl_header_status_chip") and self.lbl_header_status_chip is not None:
                self.lbl_header_status_chip.setText("ENGINE: RUNNING" if running else "ENGINE: IDLE")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_status") and self.lbl_status is not None:
                self.lbl_status.setText("Статус: Бот запущен" if running else "Статус: Бот остановлен")
                self.lbl_status.setStyleSheet("color: #00ffa3; font-weight: 800;" if running else "color: #ff4d4f; font-weight: 800;")
        except Exception:
            pass
        try:
            if hasattr(self, "start_window") and self.start_window is not None:
                self.start_window.setEnabled(not running)
        except Exception:
            pass

    def _teardown_ui(self) -> None:
        try:
            if hasattr(self, "gui_timer") and self.gui_timer is not None:
                self.gui_timer.stop()
                self.gui_timer.deleteLater()
        except Exception:
            pass
        try:
            cw = self.centralWidget()
            if cw is not None:
                cw.setParent(None)
                cw.deleteLater()
        except Exception:
            pass

    def reload_ui(self) -> None:
        ui_state = self._capture_ui_state()
        try:
            module_name = getattr(self, "_ui_layout_module_name", "ui_layout_v085_2")
            if module_name in sys.modules:
                ui_module = importlib.reload(sys.modules[module_name])
            else:
                ui_module = importlib.import_module(module_name)
            self._teardown_ui()
            ui_module.build_main_window_ui(self, self._ui_dependencies())
            self._restore_ui_state(ui_state)
            self._append_log_line("[UI] Reload UI выполнен без остановки движка")
        except Exception as exc:
            try:
                self._append_log_line(f"[UI] Reload UI error: {exc}")
            except Exception:
                pass
            QMessageBox.warning(self, "Reload UI", f"Не удалось перезагрузить интерфейс: {exc}")

    def _set_health_chip(self, label_widget, name: str, state: str, detail: str = "") -> None:
        state_map = {
            "online": ("●", "#00ffa3"),
            "delay": ("●", "#ffb347"),
            "idle": ("●", "#7dd3fc"),
            "error": ("●", "#ff4d6d"),
        }
        dot, color = state_map.get(str(state).lower(), ("●", "#7dd3fc"))
        suffix = f"  {detail}" if detail else ""
        label_widget.setText(f"{dot} {name}{suffix}")
        label_widget.setProperty("syschip", "true")
        label_widget.setStyleSheet(f"color: {color}; font-weight: 900; background: rgba(6, 14, 28, 0.82); border: 1px solid #21456f; border-radius: 14px; padding: 5px 10px;")

    def _update_system_health_indicators(self) -> None:
        engine_state = "online" if self._bot_running else "idle"
        strategy_state = "online" if self._bot_running else "idle"
        okx_state = "online" if self.current_cfg is not None else "idle"
        api_state = "online" if self.current_cfg is not None else "idle"
        okx_detail = getattr(self.current_cfg, "timeframe", "—") if self.current_cfg else "—"
        api_detail = "REST"
        if self.latest_snapshot:
            engine_info = self.latest_snapshot.get("engine", {}) or {}
            cycle_dur = float(engine_info.get("last_cycle_duration_sec", 0.0) or 0.0)
            if cycle_dur >= 10.0:
                engine_state = "error"
            elif cycle_dur >= 5.0:
                engine_state = "delay"
            elif self._bot_running:
                engine_state = "online"
            md = self.latest_snapshot.get("market_data_cache", {}) or {}
            errors = int(md.get("error_count", 0) or 0)
            if errors > 0 and self._bot_running:
                api_state = "delay" if errors < 5 else "error"
            connectivity = self.latest_snapshot.get("connectivity", {}) or {}
            conn_state = str(connectivity.get("state", "IDLE") or "IDLE").upper()
            components = dict(connectivity.get("components", {}) or {})
            down = [name for name, item in components.items() if not bool((item or {}).get("ok", False))]
            conn_map = {"CONNECTED": "online", "RECOVERING": "delay", "DEGRADED": "delay", "DISCONNECTED": "error", "IDLE": "idle"}
            if conn_state in conn_map:
                okx_state = conn_map[conn_state]
                api_state = conn_map[conn_state] if conn_state != "CONNECTED" else api_state
                okx_detail = conn_state
                api_detail = ",".join(down[:2]) if down else conn_state
            elif self.latest_snapshot.get("settings"):
                okx_state = "online"
        for attr, args in {
            "lbl_sys_api": ("API", api_state, api_detail),
            "lbl_sys_engine": ("ENGINE", engine_state, "LIVE" if self._bot_running else "IDLE"),
            "lbl_sys_strategy": ("STRATEGY", strategy_state, (getattr(self.current_cfg, "trade_mode", "auto").upper() if self.current_cfg else "AUTO")),
            "lbl_sys_okx": ("OKX", okx_state, okx_detail),
        }.items():
            if hasattr(self, attr):
                self._set_health_chip(getattr(self, attr), *args)
        self._update_terminal_mode()

    def _update_terminal_mode(self) -> None:
        mode = "idle"
        if self._bot_running:
            mode = "trading"
        if self.latest_snapshot:
            engine_info = self.latest_snapshot.get("engine", {}) or {}
            cycle_dur = float(engine_info.get("last_cycle_duration_sec", 0.0) or 0.0)
            if cycle_dur >= 10.0:
                mode = "alert"
            elif cycle_dur >= 5.0 and mode != "alert":
                mode = "trading"
        if hasattr(self, "bg_terminal"):
            self.bg_terminal.set_mode(mode)

    def _runtime_gui_active_mode(self) -> str:
        if self._engine_transitioning:
            return 'runtime_transition'
        if self._bot_running:
            return 'runtime_trading'
        return self.selected_ui_mode

    def _apply_animation_profile(self, profile: dict) -> None:
        if hasattr(self, 'gui_timer') and isinstance(self.gui_timer, QTimer):
            self.gui_timer.setInterval(max(500, int(profile['gui_ms'])))
        if hasattr(self, 'bg_terminal'):
            self._set_animation_timer_interval(self.bg_terminal, profile['grid_ms'])
        if hasattr(self, 'glow_band'):
            self._set_animation_timer_interval(self.glow_band, profile['band_ms'])
        if hasattr(self, 'neon_radar'):
            self._set_animation_timer_interval(self.neon_radar, profile['radar_ms'])
        if hasattr(self, 'neon_glyph'):
            self._set_animation_timer_interval(self.neon_glyph, profile['glyph_ms'])
        for panel in self.findChildren(NeonPanel):
            self._set_animation_timer_interval(panel, profile['panel_ms'])
        for tile in getattr(self, 'market_tiles', []) or []:
            if hasattr(tile, 'spark'):
                self._set_animation_timer_interval(tile.spark, profile['spark_ms'])

    def _apply_runtime_ui_profile(self) -> None:
        mode = self._runtime_gui_active_mode()
        self._runtime_ui_profile = mode
        if mode == 'runtime_transition':
            self._apply_animation_profile(self._runtime_transition_profile)
            return
        if mode == 'runtime_trading':
            base_mode = self._normalize_ui_mode(getattr(self, 'selected_ui_mode', 'balanced'))
            profile = self._runtime_trading_profiles.get(base_mode, self._runtime_trading_profiles['balanced'])
            self._apply_animation_profile(profile)
            return
        self._apply_ui_mode_profile(mode)

    def apply_system_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._is_dark_theme = detect_is_dark_theme(app)
        self.setStyleSheet(build_app_stylesheet(self._is_dark_theme))
        if hasattr(self, "balance_chart"):
            self.balance_chart.set_dark_theme(self._is_dark_theme)

    def eventFilter(self, watched, event) -> bool:
        if watched is QApplication.instance() and event.type() in {QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange, QEvent.Type.ThemeChange}:
            QTimer.singleShot(0, self.apply_system_theme)
        return super().eventFilter(watched, event)

    def _ui_dependencies(self) -> dict:
        return {
            "APP_VERSION": APP_VERSION,
            "AnimatedGridWidget": AnimatedGridWidget,
            "NeonPanel": NeonPanel,
            "MarketPulseTile": MarketPulseTile,
            "GlowBandWidget": GlowBandWidget,
            "LaunchConfigWidget": LaunchConfigWidget,
            "NeonRadarWidget": NeonRadarWidget,
            "NeonGlyphWidget": NeonGlyphWidget,
            "BalanceChartWidget": BalanceChartWidget,
        }

    def _build_ui(self) -> None:
        self._ui_layout_module_name = "ui_layout_v085_2"
        if self._ui_layout_module_name in sys.modules:
            ui_module = importlib.reload(sys.modules[self._ui_layout_module_name])
        else:
            ui_module = importlib.import_module(self._ui_layout_module_name)
        ui_module.build_main_window_ui(self, self._ui_dependencies())

    def show_open_position_context(self, index) -> None:
        try:
            row_idx = int(index.row())
            if row_idx < 0 or row_idx >= len(self.table_model.rows):
                return
            row = self.table_model.rows[row_idx]
            context_file = str(row.get("entry_context_file") or "").strip()
            if not context_file or not Path(context_file).exists():
                engine = getattr(self, "engine", None)
                fallback_payload = build_sync_popup_payload(engine, row, POSITION_JOURNAL_FILE)
                dlg = EntryContextDialog(fallback_payload, "", self, live_state=row)
                dlg.exec()
                return

            payload = json.loads(Path(context_file).read_text(encoding="utf-8"))
            live_payload = dict(payload)

            engine = getattr(self, "engine", None)
            inst_id = str(row.get("inst_id") or payload.get("inst_id") or "").strip()
            timeframe = str(payload.get("timeframe") or (getattr(getattr(engine, "cfg", None), "timeframe", "") if engine else "") or "5m").strip()
            current_candles = list(payload.get("candles") or [])
            entry_period = int(payload.get("entry_period") or row.get("entry_period") or 20)
            desired_limit = 80 if entry_period >= 55 else 60

            try:
                if engine is not None and inst_id:
                    fetched = engine.gateway.get_candles(inst_id, timeframe, desired_limit)
                    if fetched:
                        live_payload["candles"] = fetched
                        live_payload["live_chart"] = True
                        live_payload["chart_mode"] = "live"
            except Exception:
                live_payload["candles"] = current_candles

            try:
                trade_id = str(row.get("trade_id") or payload.get("trade_id") or "").strip()
                if trade_id and POSITION_JOURNAL_FILE.exists():
                    markers = list(live_payload.get("markers") or [])
                    journal_rows = _read_jsonl_rows(POSITION_JOURNAL_FILE)
                    add_rows = [r for r in journal_rows if str(r.get("trade_id") or "").strip() == trade_id and str(r.get("event") or "").upper() in {"ADD_UNIT", "PYRAMID_ADD", "UNIT_ADD"}]
                    candles_for_markers = list(live_payload.get("candles") or [])
                    if candles_for_markers:
                        candle_times = [int(c[0]) for c in candles_for_markers if c]
                        for idx, add_row in enumerate(add_rows, start=2):
                            event_ts = str(add_row.get("ts") or "").strip()
                            ts_match = None
                            if event_ts:
                                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                                    try:
                                        ts_match = int(datetime.strptime(event_ts, fmt).timestamp() * 1000)
                                        break
                                    except Exception:
                                        continue
                            marker_index = max(0, len(candles_for_markers) - 1)
                            if ts_match is not None and candle_times:
                                nearest = min(range(len(candle_times)), key=lambda i: abs(candle_times[i] - ts_match))
                                marker_index = int(nearest)
                            markers.append({
                                "kind": f"add{idx}",
                                "label": f"A{idx}",
                                "index": marker_index,
                                "price": float(add_row.get("price") or add_row.get("avg_px") or add_row.get("last_price") or 0.0),
                                "time": event_ts,
                            })
                    live_payload["markers"] = markers
            except Exception:
                pass

            if "candles" not in live_payload or not live_payload.get("candles"):
                live_payload["candles"] = current_candles

            live_payload["inst_id"] = inst_id or payload.get("inst_id")
            live_payload["timeframe"] = timeframe
            dlg = EntryContextDialog(live_payload, context_file, self, live_state=row)
            dlg.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Контекст входа", f"Не удалось открыть контекст входа: {exc}")
    def _selected_open_position_row(self) -> dict | None:
        try:
            table = getattr(self, "table", None)
            if table is None:
                return None
            index = table.currentIndex()
            row_idx = int(index.row())
            if row_idx < 0 or row_idx >= len(self.table_model.rows):
                return None
            row = self.table_model.rows[row_idx]
            return dict(row or {})
        except Exception:
            return None

    def _manual_add_preview_from_snapshot(self, inst_id: str, extra_units: int = 1) -> dict:
        snapshot = dict(getattr(self, "latest_snapshot", {}) or {})
        positions = dict(snapshot.get("positions") or {})
        state = dict(positions.get(inst_id) or {})
        if not state:
            raise KeyError(f"Позиция {inst_id} не найдена в snapshot")
        extra_units = max(1, int(extra_units or 1))
        current_units = int(state.get("units", 0) or 0)
        if current_units < 4:
            raise ValueError("Ручной добор доступен только после 4 юнитов")
        base_unit_qty = float(state.get("base_unit_qty", 0.0) or 0.0)
        current_qty = float(state.get("qty", 0.0) or 0.0)
        add_qty = base_unit_qty * extra_units if base_unit_qty > 0 else 0.0
        projected_qty = current_qty + add_qty
        last_px = float(state.get("last_px", 0.0) or state.get("avg_px", 0.0) or 0.0)
        avg_px = float(state.get("avg_px", 0.0) or 0.0)
        projected_avg_px = avg_px
        if projected_qty > 0 and last_px > 0:
            projected_avg_px = ((avg_px * current_qty) + (last_px * add_qty)) / projected_qty if current_qty > 0 else last_px
        upl = float(state.get("unrealized_pnl", 0.0) or 0.0)
        margin = float(state.get("margin", 0.0) or 0.0)
        pnl_pct = (upl / margin * 100.0) if margin > 0 else float(state.get("pnl_pct", 0.0) or 0.0)
        return {
            "inst_id": inst_id,
            "side": str(state.get("side", "") or ""),
            "current_units": current_units,
            "extra_units": extra_units,
            "projected_units": current_units + extra_units,
            "base_unit_qty": base_unit_qty,
            "current_qty": current_qty,
            "add_qty": add_qty,
            "projected_qty": projected_qty,
            "avg_px": avg_px,
            "estimated_fill_px": last_px,
            "projected_avg_px": projected_avg_px,
            "last_px": last_px,
            "unrealized_pnl": upl,
            "pnl_pct": pnl_pct,
            "next_pyramid_price": float(state.get("next_pyramid_price", 0.0) or 0.0),
            "stop_price": float(state.get("stop_price", 0.0) or 0.0),
            "current_notional_usdt": float(state.get("position_notional_usdt", current_qty * last_px) or 0.0),
            "projected_notional_usdt": float(state.get("position_notional_usdt", current_qty * last_px) or 0.0) + (add_qty * last_px),
            "active_stop_mode": str(state.get("active_stop_mode", "") or state.get("desired_stop_mode", "") or ""),
        }

    def on_open_position_selection_changed(self, *_args) -> None:
        self._refresh_manual_add_unit_controls()

    def _refresh_manual_add_unit_controls(self) -> None:
        btn = getattr(self, "btn_manual_add_unit", None)
        if btn is None:
            return
        row = self._selected_open_position_row()
        units = int((row or {}).get("units", 0) or 0)
        visible = bool(row) and units >= 4
        btn.setVisible(visible)
        btn.setEnabled(visible)
        if visible:
            btn.setText(f"Повысить юнит ({units}→{units + 1})")
        else:
            btn.setText("Повысить юнит")

    def show_manual_add_unit_dialog(self) -> None:
        row = self._selected_open_position_row()
        if not row:
            QMessageBox.information(self, "Ручной добор", "Сначала выбери открытую позицию в Trading Desk.")
            return
        inst_id = str(row.get("inst_id") or "").strip()
        units = int(row.get("units", 0) or 0)
        if units < 4:
            QMessageBox.information(self, "Ручной добор", "Кнопка доступна только после достижения 4 юнитов.")
            self._refresh_manual_add_unit_controls()
            return
        try:
            preview = self._manual_add_preview_from_snapshot(inst_id, extra_units=1)
            from interface.gui.dialogs.manual_add_unit_dialog import ManualAddUnitDialog
            dialog = ManualAddUnitDialog(preview, self)
            if dialog.exec() != int(QDialog.DialogCode.Accepted):
                return
            self.manual_add_units_requested.emit(inst_id, 1)
            self.append_log(f"{inst_id}: отправлена команда ручного добора ещё 1 юнита")
        except Exception as exc:
            logging.exception("Manual add dialog failed: %s", exc)
            QMessageBox.warning(self, "Ручной добор", f"Не удалось выполнить ручной добор: {exc}")

    def show_closed_trade_context(self, index) -> None:
        try:
            row_idx = int(index.row())
            if row_idx < 0 or row_idx >= len(self.closed_table_model.rows):
                return
            row = self.closed_table_model.rows[row_idx]
            context_file = str(row.get("trade_context_file") or "").strip()
            if not context_file or not Path(context_file).exists():
                QMessageBox.information(self, "Контекст закрытой сделки", "Для этой сделки ещё не найден сохранённый график жизненного цикла.")
                return
            payload = json.loads(Path(context_file).read_text(encoding="utf-8"))
            dlg = TradeLifecycleDialog(payload, context_file, self)
            dlg.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Контекст закрытой сделки", f"Не удалось открыть график закрытой сделки: {exc}")

    def _format_remaining(self, seconds_left: float) -> str:
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
        if not hasattr(self, "blocked_table"):
            return

        rows = self._collect_blocked_rows()

        self._safe_set_label_text("lbl_blocked_count", f"BLOCKS: {len(rows)}")
        if self.engine is not None:
            try:
                metrics = self.engine._collect_trade_ready_metrics()
                scan_total = int(metrics.get('scan_universe_total', 0) or 0)
                available_count = int(metrics.get('available_after_bans_count', 0) or 0)
                ready_count = int(metrics.get('trade_ready_count', 0) or 0)
                self._safe_set_label_text("lbl_available_markets", f"AVAIL: {available_count}/{scan_total}")
                self._safe_set_label_text("lbl_ready_count", f"READY: {ready_count}")
            except Exception:
                pass

        if not self._qt_widget_alive(getattr(self, 'blocked_table', None)):
            return
        self.blocked_table.setRowCount(len(rows))

        for row_idx, (inst_id, block_type, reason, ttl) in enumerate(rows):
            values = [inst_id, block_type, reason, ttl]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.blocked_table.setItem(row_idx, col_idx, item)

        if not rows:
            self.blocked_table.setRowCount(1)
            self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 2, QTableWidgetItem("Активных блокировок нет"))
            self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))
        self._update_scanner_review_views()


    def _setup_scanner_review_tables(self) -> None:
        mapping = {
            "DEAD": getattr(self, "scanner_dead_table", None),
            "SAW": getattr(self, "scanner_saw_table", None),
            "RIPPING": getattr(self, "scanner_ripping_table", None),
            "GOOD": getattr(self, "scanner_good_table", None),
        }
        for filter_type, table in mapping.items():
            if not self._qt_widget_alive(table):
                continue
            table.cellDoubleClicked.connect(lambda row, _col, ft=filter_type: self.open_scanner_review_popup(ft, row))
            table.cellChanged.connect(lambda row, col, ft=filter_type: self._on_scanner_table_cell_changed(ft, row, col))

    def _scanner_table_for_filter(self, filter_type: str):
        ft = str(filter_type or "").upper()
        if ft == "DEAD":
            return getattr(self, "scanner_dead_table", None)
        if ft == "SAW":
            return getattr(self, "scanner_saw_table", None)
        if ft == "RIPPING":
            return getattr(self, "scanner_ripping_table", None)
        if ft == "GOOD":
            return getattr(self, "scanner_good_table", None)
        return None

    def _scanner_filter_label(self, filter_type: str) -> str:
        return {"DEAD": "Мёртвый рынок", "SAW": "Пила", "RIPPING": "Рваный рынок", "GOOD": "Хорошие сделки"}.get(str(filter_type or '').upper(), str(filter_type or ''))

    def _apply_scanner_verdict_item_style(self, item: Optional[QTableWidgetItem], verdict: str) -> None:
        if item is None:
            return
        verdict = str(verdict or '').lower()
        item.setForeground(QBrush(QColor('#e6ecff')))
        if 'хороший' in verdict:
            item.setBackground(QBrush(QColor('#1d7f4e')))
        elif any(tag in verdict for tag in ('плохой', 'мертвый', 'рваный', 'пила', 'всплеск')):
            item.setBackground(QBrush(QColor(
                '#7c2d12' if 'пила' in verdict else
                '#a52a36' if 'плохой' in verdict else
                '#394867' if 'мертвый' in verdict else
                '#6b21a8' if 'всплеск' in verdict else
                '#7b3f00'
            )))
            item.setForeground(QBrush(QColor('#ffffff')))
        else:
            item.setBackground(QBrush())

    def _build_good_trade_review_rows(self) -> List[dict]:
        snapshot = dict(getattr(self, "latest_snapshot", {}) or {})
        open_rows = list(snapshot.get("open_positions") or [])
        closed_rows = list(snapshot.get("closed_trades") or [])
        scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
        persisted_rows = []
        if scanner is not None:
            try:
                persisted_rows = list(scanner.review_rows("GOOD"))
            except Exception:
                persisted_rows = []
        persisted_map = {str(r.get("pair") or "").upper(): dict(r) for r in persisted_rows if str(r.get("pair") or "").strip()}
        rows: List[dict] = []
        seen_pairs = set()
        snapshot_ts = str(snapshot.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        def _push(item: dict, *, active: bool) -> None:
            inst_id = str(item.get("inst_id") or item.get("pair") or "").strip().upper()
            if not inst_id or inst_id in seen_pairs:
                return
            seen_pairs.add(inst_id)
            side = str(item.get("side") or "").lower()
            units_val = int(float(item.get("units", item.get("unit_count", 1)) or 1))
            first_seen = str(item.get("entry_time") or item.get("open_time") or item.get("time") or snapshot_ts)
            last_seen = str(snapshot_ts if active else item.get("time") or item.get("close_time") or first_seen)
            pnl = float(item.get("pnl", item.get("unrealized_pnl", 0.0)) or 0.0)
            pnl_pct = float(item.get("pnl_pct", 0.0) or 0.0)
            status = "OPEN" if active else "CLOSED"
            note = f"{status} | {side or 'n/a'} | units={units_val} | pnl={pnl:+.2f} | pnl%={pnl_pct:+.2f}"
            persisted = dict(persisted_map.get(inst_id) or {})
            rows.append({
                "pair": inst_id,
                "first_seen": str(persisted.get("first_seen") or first_seen),
                "last_seen": str(persisted.get("last_seen") or last_seen),
                "last_seen_ts": float(persisted.get("last_seen_ts") or (time.time() if active else 0.0)),
                "hit_count": int(persisted.get("hit_count") or 1),
                "reason": str(persisted.get("reason") or note),
                "user_verdict": str(persisted.get("user_verdict") or "Не проверено"),
                "recheck_needed": bool(persisted.get("recheck_needed", active)),
                "comment": str(persisted.get("comment") or ""),
                "active": active,
                "review_tags": list(persisted.get("review_tags") or []),
            })

        for row in open_rows:
            _push(dict(row), active=True)
        for row in closed_rows:
            _push(dict(row), active=False)

        for inst_id, persisted in persisted_map.items():
            if inst_id in seen_pairs:
                continue
            rows.append({
                "pair": inst_id,
                "first_seen": str(persisted.get("first_seen") or snapshot_ts),
                "last_seen": str(persisted.get("last_seen") or snapshot_ts),
                "last_seen_ts": float(persisted.get("last_seen_ts") or 0.0),
                "hit_count": int(persisted.get("hit_count") or 1),
                "reason": str(persisted.get("reason") or "Проверка хорошей сделки"),
                "user_verdict": str(persisted.get("user_verdict") or "Не проверено"),
                "recheck_needed": bool(persisted.get("recheck_needed", False)),
                "comment": str(persisted.get("comment") or ""),
                "active": bool(persisted.get("active", False)),
                "review_tags": list(persisted.get("review_tags") or []),
            })

        rows.sort(key=lambda r: (0 if r.get("active") else 1, -float(r.get("last_seen_ts") or 0.0)))
        return rows

    def _update_scanner_review_views(self) -> None:
        scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
        if scanner is None:
            return
        for filter_type in ("DEAD", "SAW", "RIPPING", "GOOD"):
            table = self._scanner_table_for_filter(filter_type)
            if table is None:
                continue
            rows = self._build_good_trade_review_rows() if filter_type == "GOOD" else list(scanner.review_rows(filter_type))
            blocked = table.blockSignals(True)
            table.setRowCount(len(rows) if rows else 1)
            if not rows:
                for c, v in enumerate(["—", "—", "—", "0", "Нет записей", "Не проверено", "", ""]):
                    item = QTableWidgetItem(v)
                    table.setItem(0, c, item)
                    if c == 5:
                        self._apply_scanner_verdict_item_style(item, v)
                table.blockSignals(blocked)
                continue
            for row_idx, row in enumerate(rows):
                values = [
                    row.get("pair", ""),
                    row.get("first_seen", ""),
                    row.get("last_seen", ""),
                    str(row.get("hit_count", 0)),
                    row.get("reason", ""),
                    row.get("user_verdict", "Не проверено"),
                    "Да" if row.get("recheck_needed") else "",
                    row.get("comment", ""),
                ]
                for col_idx, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if filter_type == "GOOD" or col_idx != 7:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    table.setItem(row_idx, col_idx, item)
                    if col_idx == 5:
                        self._apply_scanner_verdict_item_style(item, str(value))
            table.blockSignals(blocked)

    def _on_scanner_table_cell_changed(self, filter_type: str, row: int, col: int) -> None:
        if col != 7:
            return
        table = self._scanner_table_for_filter(filter_type)
        scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
        if not self._qt_widget_alive(table) or scanner is None:
            return
        pair_item = table.item(row, 0)
        comment_item = table.item(row, 7)
        verdict_item = table.item(row, 5)
        if pair_item is None:
            return
        pair = str(pair_item.text() or "").strip()
        if not pair or pair == "—":
            return
        verdict = str(verdict_item.text() or "Не проверено").strip() if verdict_item is not None else "Не проверено"
        comment = str(comment_item.text() or "").strip() if comment_item is not None else ""
        scanner.update_validation(pair, filter_type, verdict, comment)
        QTimer.singleShot(0, self._update_scanner_review_views)

    def open_scanner_review_popup(self, filter_type: str, row: int) -> None:
        table = self._scanner_table_for_filter(filter_type)
        scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
        if not self._qt_widget_alive(table) or scanner is None:
            return
        item = table.item(int(row), 0)
        if item is None:
            return
        inst_id = str(item.text() or "").strip()
        if not inst_id or inst_id == "—":
            return
        payload = scanner.build_popup_payload(inst_id, filter_type)
        dlg = ScannerReviewDialog(payload, self)
        result = dlg.exec()
        if result == int(QDialog.DialogCode.Accepted) and getattr(dlg, "was_saved", lambda: False)():
            scanner.update_validation(inst_id, filter_type, dlg.selected_verdict(), dlg.selected_comment(), tags=getattr(dlg, "selected_tags", lambda: [])())
            QTimer.singleShot(0, self._update_scanner_review_views)

    def _telegram_enabled_in_cfg(self, cfg: Optional[BotConfig]) -> bool:
        if cfg is None:
            enabled_raw = os.getenv("TELEGRAM_ENABLED", "0").strip().lower()
            enabled = enabled_raw in {"1", "true", "yes", "on"}
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
            return bool(enabled and token and chat_id)
        return bool(getattr(cfg, "telegram_enabled", False) and getattr(cfg, "telegram_bot_token", "") and getattr(cfg, "telegram_chat_id", ""))

    def _emit_gui_heartbeat(self) -> None:
        try:
            log_heartbeat("gui", "alive", bot_running=bool(self._bot_running), transitioning=bool(self._engine_transitioning), worker_running=bool(self.worker and self.worker.isRunning()))
        except Exception:
            logging.exception("Failed to emit GUI heartbeat")

    def _stop_telegram_screenshot_timer(self) -> None:
        self._telegram_screenshot_inflight = False
        if self._telegram_screenshot_timer is not None:
            self._telegram_screenshot_timer.stop()
            self._telegram_screenshot_timer.deleteLater()
            self._telegram_screenshot_timer = None

    def _configure_telegram_screenshots(self, cfg: Optional[BotConfig]) -> None:
        self._stop_telegram_screenshot_timer()
        self.telegram_ui_notifier = None
        self._telegram_screenshot_inflight = False
        if TELEGRAM_HARD_DISABLED:
            self.append_log("Telegram: полностью отключён в версии v083_2 из-за блокировки/нестабильности")
            return
        if cfg is None:
            self.append_log("Telegram: конфиг отсутствует, отправка отключена")
            return
        enabled_flag = bool(getattr(cfg, "telegram_enabled", False))
        token = str(getattr(cfg, "telegram_bot_token", "") or "").strip()
        chat_id = str(getattr(cfg, "telegram_chat_id", "") or "").strip()
        if not enabled_flag:
            self.append_log("Telegram: отключён в .env (TELEGRAM_ENABLED=0)")
            return
        if not token or not chat_id:
            missing = []
            if not token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not chat_id:
                missing.append("TELEGRAM_CHAT_ID")
            self.append_log(f"Telegram: отсутствуют параметры в .env: {', '.join(missing)}")
            return
        try:
            self.telegram_ui_notifier = TelegramNotifier(enabled=True, bot_token=token, chat_id=chat_id, queue_dir=str(TELEGRAM_QUEUE_DIR))
            self._telegram_screenshot_timer = QTimer(self)
            self._telegram_screenshot_timer.setSingleShot(True)
            self._telegram_screenshot_timer.timeout.connect(self.send_main_window_screenshot_to_telegram)
            self._telegram_screenshot_timer.start(self._telegram_screenshot_start_delay_ms)
            self.append_log("Telegram: автоскрин главного окна включён с безопасной задержкой старта")
        except Exception as exc:
            self.telegram_ui_notifier = None
            self._stop_telegram_screenshot_timer()
            self.append_log(f"Telegram: не удалось включить автоскрин окна: {exc}")

    def _start_telegram_task(self, *, message: str = '', image: object = None, caption: str = '', success_log: str = '', error_prefix: str = 'Telegram') -> None:
        if TELEGRAM_HARD_DISABLED:
            return
        notifier = self.telegram_ui_notifier
        if notifier is None or not getattr(notifier, 'enabled', False):
            return
        worker = TelegramTaskThread(notifier, message=message, image=image, caption=caption, parent=self)
        self._telegram_workers.append(worker)

        def _done(ok: bool, result: str, worker_ref=worker):
            try:
                self._telegram_workers.remove(worker_ref)
            except ValueError:
                pass
            worker_ref.deleteLater()
            if image is not None:
                self._telegram_screenshot_inflight = False
                if self._bot_running and not self._engine_transitioning and self._telegram_screenshot_timer is not None:
                    self._telegram_screenshot_timer.start(self._telegram_screenshot_interval_ms)
            if ok:
                if success_log:
                    self.append_log(success_log)
            else:
                self.append_log(f"{error_prefix}: {result}")

        worker.completed.connect(_done)
        worker.start()

    def send_main_window_screenshot_to_telegram(self) -> None:
        if TELEGRAM_HARD_DISABLED:
            return
        notifier = self.telegram_ui_notifier
        if notifier is None or not getattr(notifier, "enabled", False):
            return
        if not self.isVisible() or self._engine_transitioning or self._telegram_screenshot_inflight:
            if self._bot_running and self._telegram_screenshot_timer is not None and not self._engine_transitioning:
                self._telegram_screenshot_timer.start(self._telegram_screenshot_interval_ms)
            return
        try:
            self._telegram_screenshot_inflight = True
            self.repaint()
            QApplication.processEvents()
            pixmap = self.grab()
            image = pixmap.toImage()
            if pixmap.isNull():
                raise RuntimeError("пустой pixmap")
            caption = f"OKX Turtle Bot {APP_VERSION} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            self._start_telegram_task(image=image, caption=caption, success_log="Telegram: скрин главного окна отправлен", error_prefix="Telegram: ошибка отправки скрина окна")
        except Exception as exc:
            self._telegram_screenshot_inflight = False
            self.append_log(f"Telegram: ошибка подготовки скрина окна: {exc}")
            if self._bot_running and self._telegram_screenshot_timer is not None and not self._engine_transitioning:
                self._telegram_screenshot_timer.start(self._telegram_screenshot_interval_ms)

    def _telegram_env_ready(self) -> bool:
        cfg = self.current_cfg
        return self._telegram_enabled_in_cfg(cfg)

    def _is_telegram_worker_running(self) -> bool:
        proc = getattr(self, "_telegram_worker_process", None)
        if proc is not None and proc.poll() is None:
            return True
        pid_path = resolve_pid_file(str(TELEGRAM_WORKER_PID_FILE))
        if not pid_path.exists():
            return False
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            if pid <= 0:
                return False
        except Exception:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _telegram_worker_exe_exists(self) -> bool:
        try:
            return TELEGRAM_WORKER_EXE_FILE.exists() and TELEGRAM_WORKER_EXE_FILE.is_file()
        except Exception:
            return False

    def _telegram_worker_script_exists(self) -> bool:
        try:
            return TELEGRAM_WORKER_SCRIPT_FILE.exists() and TELEGRAM_WORKER_SCRIPT_FILE.is_file()
        except Exception:
            return False

    def _telegram_worker_launcher_exists(self) -> bool:
        return bool(self._telegram_worker_exe_exists() or self._telegram_worker_script_exists())

    def _telegram_recent_errors(self, limit: int = 5) -> list[dict]:
        rows: list[dict] = []
        try:
            if TRACEBACK_ERROR_FILE.exists():
                lines = [line.strip() for line in TRACEBACK_ERROR_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
                for line in lines[-max(1, int(limit or 5)):]:
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    rows.append({
                        "time": str(item.get("time") or ""),
                        "source": str(item.get("source") or ""),
                        "title": str(item.get("title") or ""),
                        "message": str(item.get("message") or ""),
                    })
        except Exception:
            return []
        return rows

    def _telegram_chart_cache_path(self) -> Path:
        return TELEGRAM_CHART_IMAGE_FILE

    def _refresh_telegram_chart_cache(self, force: bool = False) -> str:
        try:
            now_ts = time.time()
            last_ts = float(getattr(self, "_telegram_chart_cache_ts", 0.0) or 0.0)
            if not force and (now_ts - last_ts) < 20.0:
                chart_path = self._telegram_chart_cache_path()
                if chart_path.exists() and chart_path.is_file():
                    return str(chart_path)
            if not self.isVisible() or self.isMinimized() or self._engine_transitioning or self._telegram_screenshot_inflight:
                return ""
            self.repaint()
            QApplication.processEvents()
            pixmap = self.grab()
            if pixmap.isNull():
                return ""
            chart_path = self._telegram_chart_cache_path()
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap.save(str(chart_path), "JPG", quality=90)
            self._telegram_chart_cache_ts = now_ts
            return str(chart_path)
        except Exception:
            return ""

    def _write_telegram_status_file(self) -> None:
        try:
            cfg = self.current_cfg
            snapshot = dict(getattr(self, "latest_snapshot", {}) or {})
            analytics = dict(snapshot.get("analytics") or {})
            connectivity = dict(snapshot.get("connectivity") or {})
            components = dict(connectivity.get("components") or {})
            open_rows = list(snapshot.get("open_positions") or [])
            if not open_rows:
                model = getattr(self, "table_model", None)
                if model is not None and hasattr(model, "rows"):
                    open_rows = list(getattr(model, "rows", []) or [])
                elif model is not None and hasattr(model, "_rows"):
                    open_rows = list(getattr(model, "_rows", []) or [])
            balance_total = float(snapshot.get("balance_total", 0.0) or 0.0)
            balance_available = float(snapshot.get("balance_available", 0.0) or 0.0)
            balance_used = float(snapshot.get("balance_used", 0.0) or 0.0)
            if balance_total <= 0.0 and getattr(self, "engine", None) is not None:
                try:
                    latest_balance = dict(getattr(self.engine, "latest_balance_snapshot", {}) or {})
                    balance_total = float(latest_balance.get("balance_total", 0.0) or 0.0)
                    balance_available = float(latest_balance.get("balance_available", 0.0) or 0.0)
                    balance_used = float(latest_balance.get("balance_used", 0.0) or 0.0)
                except Exception:
                    pass
            if balance_total <= 0.0 and hasattr(self, "latest_balance_snapshot"):
                latest_balance = dict(getattr(self, "latest_balance_snapshot", {}) or {})
                balance_total = float(latest_balance.get("balance_total", balance_total) or balance_total)
                balance_available = float(latest_balance.get("balance_available", balance_available) or balance_available)
                balance_used = float(latest_balance.get("balance_used", balance_used) or balance_used)
            position_rows = []
            for row in open_rows[:20]:
                position_rows.append({
                    "inst_id": str(row.get("inst_id") or ""),
                    "side": str(row.get("side") or ""),
                    "units": int(float(row.get("units", 0) or 0)),
                    "entry": float(row.get("avg_px", row.get("entry_price", 0.0)) or 0.0),
                    "stop": float(row.get("stop_price", 0.0) or 0.0),
                    "pnl": float(row.get("unrealized_pnl", row.get("pnl", 0.0)) or 0.0),
                    "pnl_pct": float(row.get("pnl_pct", 0.0) or 0.0),
                })
            scanner_payload = {
                "total": int(analytics.get("scanner_total", 0) or 0),
                "scanned": int(analytics.get("scanner_scanned", analytics.get("scanner_ready", 0)) or 0),
                "allowed": int(analytics.get("scanner_allowed", analytics.get("scanner_admitted", 0)) or 0),
                "blocked": int(analytics.get("scanner_blocked", analytics.get("scanner_risky", 0)) or 0),
                "dead": int(analytics.get("scanner_dead", 0) or 0),
                "saw": int(analytics.get("scanner_saw", 0) or 0),
                "ripping": int(analytics.get("scanner_ripping", 0) or 0),
                "pending": int(analytics.get("scanner_pending", 0) or 0),
                "status": str(analytics.get("scanner_status_text", "IDLE") or "IDLE"),
                "ready": int(analytics.get("trade_ready_count", 0) or 0),
                "available_after_bans": int(analytics.get("available_after_bans_count", 0) or 0),
                "scan_universe_total": int(analytics.get("scan_universe_total", 0) or 0),
            }
            top_candidates = []
            try:
                top = self._top_engine_candidate()
                if top:
                    top_candidates.append({
                        "inst_id": str(top.get("inst_id") or ""),
                        "side": str(top.get("side") or ""),
                        "system_name": str(top.get("system_name") or ""),
                        "score": float(top.get("score", top.get("breakout_distance_atr", 0.0)) or 0.0),
                    })
            except Exception:
                pass
            health_payload = {
                "connectivity_state": str(connectivity.get("state", getattr(getattr(self, "engine", None), "exchange_connectivity_state", "IDLE")) or "IDLE"),
                "components": {str(name): ("OK" if bool((item or {}).get("ok", False)) else "DOWN") for name, item in components.items()},
                "engine": "RUNNING" if bool(getattr(self, "_bot_running", False)) else "STOPPED",
                "telegram_worker": "ON" if bool(self._is_telegram_worker_running()) else "OFF",
                "market_data_errors": int((snapshot.get("market_data_cache") or {}).get("error_count", 0) or 0),
                "cycle_duration_sec": float((snapshot.get("engine") or {}).get("last_cycle_duration_sec", 0.0) or 0.0),
            }
            chart_path = self._refresh_telegram_chart_cache(force=False)
            payload = {
                "app_version": APP_VERSION,
                "bot_running": bool(getattr(self, "_bot_running", False)),
                "telegram_worker_running": bool(self._is_telegram_worker_running()),
                "timeframe": str(getattr(cfg, "timeframe", "-") or "-"),
                "trade_mode": str(getattr(cfg, "trade_mode", "-") or "-"),
                "open_positions": int(len(position_rows)),
                "error_count": int(RUNTIME_ERROR_TRACKER.count()),
                "balance": {
                    "total": balance_total,
                    "available": balance_available,
                    "used": balance_used,
                },
                "positions": position_rows,
                "scanner": scanner_payload,
                "top_candidates": top_candidates,
                "health": health_payload,
                "latest_errors": self._telegram_recent_errors(limit=5),
                "chart_image_path": str(chart_path or ""),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            status_path = resolve_status_file(str(TELEGRAM_STATUS_FILE))
            status_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = status_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(status_path)
        except Exception:
            pass


    def _refresh_telegram_controls(self) -> None:
        env_ready = self._telegram_enabled_in_cfg(self.current_cfg)
        exe_ready = self._telegram_worker_launcher_exists()
        running = self._is_telegram_worker_running()
        if running:
            status = "TG: ON"
        elif not env_ready:
            status = "TG: ENV OFF"
        elif not exe_ready:
            status = "TG: LAUNCHER MISS"
        else:
            status = "TG: OFF"
        self._safe_set_label_text("lbl_header_tg_chip", status)
        chip = getattr(self, "lbl_header_tg_chip", None)
        if chip is not None:
            if running:
                chip.setStyleSheet("background:#123524;color:#dcfce7;border:1px solid #22c55e;border-radius:10px;padding:4px 8px;font-weight:800;")
            elif not env_ready:
                chip.setStyleSheet("")
            elif not exe_ready:
                chip.setStyleSheet("background:#3f1d1d;color:#fecaca;border:1px solid #ef4444;border-radius:10px;padding:4px 8px;font-weight:800;")
            else:
                chip.setStyleSheet("background:#3a2a08;color:#fef3c7;border:1px solid #f59e0b;border-radius:10px;padding:4px 8px;font-weight:800;")
        btn_start = getattr(self, "btn_tg_start", None)
        btn_stop = getattr(self, "btn_tg_stop", None)
        if btn_start is not None:
            btn_start.setEnabled(env_ready and exe_ready and not running)
        if btn_stop is not None:
            btn_stop.setEnabled(running)
        self._write_telegram_status_file()

    def start_telegram_worker(self) -> None:
        if TELEGRAM_HARD_DISABLED:
            self.append_log("Telegram: модуль жёстко отключён в этой сборке")
            self._refresh_telegram_controls()
            return
        cfg = self.current_cfg
        if not self._telegram_enabled_in_cfg(cfg):
            self.append_log("Telegram: в .env должны быть TELEGRAM_ENABLED=1, TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
            self._refresh_telegram_controls()
            return
        if not self._telegram_worker_exe_exists():
            self.append_log(f"Telegram: не найден launcher Telegram worker | exe={TELEGRAM_WORKER_EXE_FILE} | script={TELEGRAM_WORKER_SCRIPT_FILE}")
            self._refresh_telegram_controls()
            return
        if self._is_telegram_worker_running():
            self.append_log("Telegram: worker уже запущен")
            self._refresh_telegram_controls()
            return
        try:
            queue_dir = ensure_queue_layout(str(TELEGRAM_QUEUE_DIR))
            log_file = resolve_log_file(str(TELEGRAM_WORKER_LOG_FILE))
            pid_file = resolve_pid_file(str(TELEGRAM_WORKER_PID_FILE))
            log_file.parent.mkdir(parents=True, exist_ok=True)
            queue_dir.mkdir(parents=True, exist_ok=True)
            status_file = resolve_status_file(str(TELEGRAM_STATUS_FILE))
            offset_file = resolve_offset_file(str(TELEGRAM_OFFSET_FILE))
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            if self._telegram_worker_exe_exists():
                remote_bridge_dir = APP_DIR / "runtime" / "remote_bridge"
                cmd = [str(TELEGRAM_WORKER_EXE_FILE), "--project-root", str(APP_DIR), "--queue-dir", str(queue_dir), "--log-file", str(log_file), "--pid-file", str(pid_file), "--status-file", str(status_file), "--offset-file", str(offset_file), "--remote-bridge-dir", str(remote_bridge_dir)]
                launch_desc = f"exe={TELEGRAM_WORKER_EXE_FILE} | project_root={APP_DIR}"
            else:
                py_exec = sys.executable or "python"
                remote_bridge_dir = APP_DIR / "runtime" / "remote_bridge"
                cmd = [str(py_exec), str(TELEGRAM_WORKER_SCRIPT_FILE), "--project-root", str(APP_DIR), "--queue-dir", str(queue_dir), "--log-file", str(log_file), "--pid-file", str(pid_file), "--status-file", str(status_file), "--offset-file", str(offset_file), "--remote-bridge-dir", str(remote_bridge_dir)]
                launch_desc = f"python={py_exec} script={TELEGRAM_WORKER_SCRIPT_FILE} | project_root={APP_DIR}"
            proc = subprocess.Popen(cmd, cwd=str(APP_DIR), creationflags=creationflags)
            self._telegram_worker_process = proc
            self.append_log(f"Telegram: worker запущен | {launch_desc} | queue={queue_dir}")
            try:
                notifier = getattr(self, "telegram_ui_notifier", None)
                if notifier is not None:
                    notifier.send(f"🤖 Telegram worker запущен\n\nВерсия: {APP_VERSION}\nОчередь: {queue_dir.name}")
            except Exception as notify_exc:
                self.append_log(f"Telegram: не удалось отправить стартовое сообщение worker: {notify_exc}")
        except Exception as exc:
            self.append_log(f"Telegram: ошибка запуска worker.exe: {exc}")
        self._refresh_telegram_controls()

    def stop_telegram_worker(self) -> None:
        stopped = False
        proc = getattr(self, "_telegram_worker_process", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                stopped = True
            except Exception:
                try:
                    proc.kill()
                    stopped = True
                except Exception:
                    pass
        pid_path = resolve_pid_file(str(TELEGRAM_WORKER_PID_FILE))
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text(encoding="utf-8").strip())
                if pid > 0:
                    try:
                        os.kill(pid, 15 if os.name != "nt" else 9)
                    except Exception:
                        pass
                pid_path.unlink(missing_ok=True)
                stopped = True
            except Exception:
                pass
        self._telegram_worker_process = None
        self.append_log("Telegram: worker остановлен" if stopped else "Telegram: worker не был запущен")
        self._refresh_telegram_controls()

    def _clear_ui_runtime_data(self) -> None:
        self.latest_snapshot = None
        if hasattr(self, "table_model") and self.table_model is not None:
            self.table_model.update_rows([])
        if hasattr(self, "closed_table_model") and self.closed_table_model is not None:
            self.closed_table_model.update_rows([])
        if hasattr(self, "balance_chart") and self.balance_chart is not None:
            step = self.balance_chart_step_combo.currentData() if hasattr(self, "balance_chart_step_combo") and self.balance_chart_step_combo is not None else "1m"
            self.balance_chart.update_points([], step, markers=[])
        if hasattr(self, "log_text") and self._qt_widget_alive(getattr(self, "log_text", None)):
            self.log_text.clear()
        if hasattr(self, "activity_feed") and self._qt_widget_alive(getattr(self, "activity_feed", None)):
            self.activity_feed.clear()
        if hasattr(self, "_log_buffer") and self._log_buffer is not None:
            self._log_buffer.clear()
        self._safe_set_label_text("lbl_positions", "Открытых позиций: 0")
        self._safe_set_label_text("lbl_balance_summary", "Баланс: 0 | Использовано: 0 | Доступно: 0")
        self._safe_set_label_text("lbl_open_pnl", "Open PnL: 0")
        self._safe_set_label_text("lbl_realized", "Реализованный PnL: 0")
        self._safe_set_label_text("lbl_closed_stats", "Закрытых сделок: 0")
        self._safe_set_label_text("lbl_winrate", "Winrate: 0%")
        self._safe_set_label_text("lbl_balance_points", "Показано значений: 0/30")
        self._safe_set_runtime_label("Время работы: —")
        self._safe_set_label_text("lbl_cycle_duration", "Цикл позиций: 0/0 | last 0.00 сек | —")
        self._safe_set_label_text("lbl_header_pos_cycle_chip", "POS CYCLE: IDLE")
        self._safe_set_label_text("lbl_balance_hero", 'BALANCE\n0 USDT')
        self._safe_set_label_text("lbl_balance_used", 'USED\n0 USDT')
        self._safe_set_label_text("lbl_balance_available", 'AVAILABLE\n0 USDT')
        self._safe_set_label_text("lbl_balance_equity", '')
        self._safe_set_label_text("lbl_balance_formula", '')
        self._safe_set_label_text("lbl_available_markets", 'AVAIL: 0/0')
        self._safe_set_label_text("lbl_ready_count", 'READY: 0')
        self._safe_set_label_text("lbl_scanner_total", 'TOTAL: 0')
        self._safe_set_label_text("lbl_scanner_scanned", 'SCANNED: 0')
        self._safe_set_label_text("lbl_scanner_allowed", 'ALLOWED: 0')
        self._safe_set_label_text("lbl_scanner_blocked", 'BLOCKED: 0')
        self._safe_set_label_text("lbl_scanner_dead", 'DEAD: 0')
        self._safe_set_label_text("lbl_scanner_saw", 'SAW: 0')
        self._safe_set_label_text("lbl_scanner_ripping", 'RIPPING: 0')
        self._safe_set_label_text("lbl_scanner_pending", 'PENDING: 0')
        self._safe_set_label_text("lbl_scanner_status", 'STATUS: IDLE')
        self._safe_set_label_text("lbl_session_pnl", 'Session PnL: 0.00')
        self._safe_set_label_text("lbl_header_status_chip", 'ENGINE: IDLE')
        self._refresh_manual_add_unit_controls()

    def _reset_remote_positions(self) -> tuple[int, list[str]]:
        cfg = self.current_cfg
        if cfg is None and self.engine is not None:
            cfg = self.engine.cfg
        if cfg is None:
            return 0, []
        gateway = OkxGateway(cfg)
        positions = gateway.get_positions()
        closed = 0
        errors = []
        for pos in positions:
            inst_id = str(pos.get("instId") or "").strip()
            if not inst_id:
                continue
            try:
                qty = abs(float(pos.get("pos") or 0.0))
            except Exception:
                qty = 0.0
            if qty <= 0:
                continue
            gateway.cancel_pending_close_orders(inst_id)
            resp = gateway.close_position(inst_id, "reset_test", auto_cancel=True)
            if resp.get("code") == "0":
                closed += 1
            else:
                errors.append(f"{inst_id}: {resp}")
        return closed, errors

    def reset_test_run(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset теста",
            "Остановить бота, попытаться закрыть все SWAP-позиции и очистить локальные логи/состояние?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        was_running = bool(self.worker and self.worker.isRunning())
        if was_running:
            self.stop_engine()

        closed = 0
        close_errors = []
        try:
            closed, close_errors = self._reset_remote_positions()
        except Exception as exc:
            close_errors = [str(exc)]

        reset_info = reset_local_runtime_files()

        if self.engine is not None:
            self.engine.position_state.clear()
            self.engine.closed_trades.clear()
            with self.engine.balance_lock:
                self.engine.balance_history.clear()
                self.engine.latest_balance_snapshot = {}
            for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections", "close_retry_after", "execution_risk_events"):
                data = getattr(self.engine, attr, None)
                if isinstance(data, dict):
                    data.clear()
            self.engine._save_state()

        self._clear_ui_runtime_data()
        self._refresh_error_indicator()
        self.refresh_blocked_instruments_view()
        self._safe_set_label_text("lbl_available_markets", "AVAIL: 0/0")
        self._safe_set_label_text("lbl_ready_count", "READY: 0")

        summary = (
            f"Reset теста выполнен: закрыто позиций {closed}, "
            f"удалено entry-context {reset_info['entry_context_removed']}, "
            f"trade-context {reset_info['trade_context_removed']}"
        )
        self.append_log(summary)
        if close_errors:
            self.append_log("Ошибки закрытия при reset: " + " | ".join(close_errors[:8]))

    def export_analysis_bundle(self) -> None:
        try:
            dialog = AnalysisExportDialog(self)
            dialog.btn_open.clicked.connect(lambda: os.startfile(str(ANALYSIS_EXPORT_DIR)) if os.name == 'nt' else None)
            if dialog.exec() != int(QDialog.DialogCode.Accepted):
                return
            mode = str(dialog.selected_mode or 'full').lower()
            archive_path = build_analysis_export_bundle(EXPORT_BUNDLE_CONTEXT, mode=mode, snapshot=self.latest_snapshot, cfg=self.current_cfg)
            self._append_scanner_exports_to_archive(archive_path)
            self.append_log(f"Сдать анализы: режим={mode} | архив сохранён {archive_path}")
            QMessageBox.information(
                self,
                "Сдать анализы",
                "Диагностический архив готов.\n\n"
                f"Режим: {mode}\n"
                f"Путь: {archive_path}\n\n"
                "Его можно загружать в чат для разбора работы стратегии.",
            )
        except Exception as exc:
            self.append_log(f"Сдать анализы: ошибка экспорта: {exc}")
            QMessageBox.warning(self, "Сдать анализы", f"Не удалось собрать архив анализа: {exc}")

    def _append_scanner_exports_to_archive(self, archive_path: Path) -> None:
        try:
            scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
            with zipfile.ZipFile(archive_path, 'a', compression=zipfile.ZIP_DEFLATED) as zf:
                if scanner is not None:
                    rows = scanner.export_validation_rows()
                    if rows:
                        headers = ["pair", "filter_type", "first_seen", "last_seen", "hit_count", "reason", "user_verdict", "recheck_needed", "comment", "metrics_json"]
                        lines = [",".join(headers)]
                        for row in rows:
                            values = [
                                str(row.get("pair", "")), str(row.get("filter_type", "")), str(row.get("first_seen", "")), str(row.get("last_seen", "")),
                                str(row.get("hit_count", 0)), str(row.get("reason", "")).replace(',', ';'), str(row.get("user_verdict", "")), str(row.get("recheck_needed", False)),
                                str(row.get("comment", "")).replace(',', ';'), json.dumps(row.get("metrics") or {}, ensure_ascii=False).replace(',', ';')
                            ]
                            lines.append(",".join(values))
                        zf.writestr('scanner_validation_summary.csv', "\n".join(lines))
                        zf.writestr('scanner_validation_summary.json', json.dumps(rows, ensure_ascii=False, indent=2))
                for path_obj, arc_name in ((SCANNER_VALIDATION_LOG_FILE, 'scanner_validation_log.csv'), (SCANNER_VALIDATION_STATE_FILE, 'scanner_validation_state.json')):
                    if path_obj.exists():
                        zf.write(path_obj, arcname=arc_name)
        except Exception as exc:
            self.append_log(f"Scanner export append failed: {exc}")

    def clear_ban_lists(self) -> None:
        if self.engine is None:
            self._safe_set_label_text("lbl_blocked_count", "Блокировок: 0")
            self._safe_set_label_text("lbl_available_markets", "AVAIL: 0/0")
            self._safe_set_label_text("lbl_ready_count", "READY: 0")
            self._safe_set_label_text("lbl_scanner_total", "TOTAL: 0")
            self._safe_set_label_text("lbl_scanner_scanned", "SCANNED: 0")
            self._safe_set_label_text("lbl_scanner_allowed", "ALLOWED: 0")
            self._safe_set_label_text("lbl_scanner_blocked", "BLOCKED: 0")
            self._safe_set_label_text("lbl_scanner_dead", "DEAD: 0")
            self._safe_set_label_text("lbl_scanner_saw", "SAW: 0")
            self._safe_set_label_text("lbl_scanner_ripping", "RIPPING: 0")
            self._safe_set_label_text("lbl_scanner_pending", "PENDING: 0")
            self._safe_set_label_text("lbl_scanner_status", "STATUS: IDLE")
            blocked_table = getattr(self, "blocked_table", None)
            if self._qt_widget_alive(blocked_table):
                blocked_table.setRowCount(1)
                blocked_table.setItem(0, 0, QTableWidgetItem("—"))
                blocked_table.setItem(0, 1, QTableWidgetItem("—"))
                blocked_table.setItem(0, 2, QTableWidgetItem("Бан-лист очищен."))
                blocked_table.setItem(0, 3, QTableWidgetItem("—"))
            self.append_log("Бан-лист очищен (движок ещё не запущен)")
            return

        for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections", "execution_risk_events"):
            data = getattr(self.engine, attr, None)
            if isinstance(data, dict):
                data.clear()

        self.refresh_blocked_instruments_view()
        self.append_log("Все заблокированные инструменты удалены из бан-листа")

    def set_pending_config(self, cfg: BotConfig) -> None:
        self.current_cfg = cfg
        account = "Основной" if cfg.flag == "0" else "Демо"
        self._apply_trade_mode_to_controls(getattr(cfg, "trade_mode", "auto"))
        self.append_log(f"Параметры обновлены: {account}, {cfg.timeframe}, режим: {getattr(cfg, 'trade_mode', 'auto')}")

    def _apply_trade_mode_to_controls(self, mode: str) -> None:
        normalized = "manual" if str(mode).lower() == "manual" else "auto"
        if hasattr(self, "mode_switch_toggle"):
            blocked = self.mode_switch_toggle.blockSignals(True)
            self.mode_switch_toggle.setChecked(normalized == "manual")
            self.mode_switch_toggle.setText("Режим: Ручной" if normalized == "manual" else "Режим: Авто")
            bg = "#b42318" if normalized == "manual" else "#157347"
            self.mode_switch_toggle.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: white; border: none; border-radius: 17px; padding: 6px 14px; font-weight: 700; }}"
                f"QPushButton:hover {{ opacity: 0.92; }}"
            )
            self.mode_switch_toggle.blockSignals(blocked)
        if hasattr(self, "start_window") and self.start_window is not None:
            self.start_window.set_trade_mode(normalized)

    def on_trade_mode_changed(self, *_args) -> None:
        mode = "manual" if (hasattr(self, "mode_switch_toggle") and self.mode_switch_toggle.isChecked()) else "auto"
        self._apply_trade_mode_to_controls(mode)
        if self.current_cfg is not None:
            self.current_cfg.trade_mode = mode
        if self.engine is not None and hasattr(self.engine, "cfg"):
            self.engine.cfg.trade_mode = mode
        if isinstance(getattr(self, "latest_snapshot", None), dict):
            self.latest_snapshot.setdefault("settings", {})
            self.latest_snapshot["settings"]["trade_mode"] = mode
        self.append_log(f"Режим торговли переключён: {'ручной' if mode == 'manual' else 'автоматический'}")

    def _normalize_ui_mode(self, mode: str) -> str:
        mode_norm = str(mode or "balanced").strip().lower()
        return mode_norm if mode_norm in self._ui_mode_profiles else "balanced"

    def _set_animation_timer_interval(self, widget, interval_ms: int) -> None:
        timer = getattr(widget, "_timer", None)
        if isinstance(timer, QTimer):
            timer.setInterval(max(20, int(interval_ms)))

    def _apply_ui_mode_profile(self, mode: str) -> None:
        mode_norm = self._normalize_ui_mode(mode)
        profile = self._ui_mode_profiles.get(mode_norm, self._ui_mode_profiles["balanced"])
        self._apply_animation_profile(profile)

    def _apply_ui_mode_to_controls(self, mode: str, *, log_change: bool = False) -> None:
        mode_norm = self._normalize_ui_mode(mode)
        self.selected_ui_mode = mode_norm
        labels = {"performance": "PERFORMANCE", "balanced": "BALANCED", "low": "LOW"}
        if hasattr(self, "ui_mode_combo") and self.ui_mode_combo is not None:
            idx = self.ui_mode_combo.findData(mode_norm)
            if idx >= 0 and self.ui_mode_combo.currentIndex() != idx:
                blocked = self.ui_mode_combo.blockSignals(True)
                self.ui_mode_combo.setCurrentIndex(idx)
                self.ui_mode_combo.blockSignals(blocked)
        if hasattr(self, "lbl_ui_mode_hint") and self.lbl_ui_mode_hint is not None:
            self.lbl_ui_mode_hint.setText(f"UI MODE: {labels.get(mode_norm, mode_norm.upper())}")
        self._apply_runtime_ui_profile()
        self._refresh_error_indicator()
        if log_change:
            self.append_log(f"GUI режим переключён: {labels.get(mode_norm, mode_norm.upper())}")

    def on_ui_mode_changed(self, *_args) -> None:
        mode = getattr(self, "selected_ui_mode", "balanced")
        if hasattr(self, "ui_mode_combo") and self.ui_mode_combo is not None:
            mode = str(self.ui_mode_combo.currentData() or mode)
        self._apply_ui_mode_to_controls(mode, log_change=True)

    def _human_side(self, side: str) -> str:
        side_norm = str(side or "").strip().lower()
        if side_norm == "long":
            return "Long"
        if side_norm == "short":
            return "Short"
        return side or "—"


    def on_entry_candidate(self, payload: dict) -> None:
        if self._manual_dialog_open:
            inst_id = str((payload or {}).get("inst_id") or "—")
            if self.engine is not None:
                self.engine._set_manual_entry_decision(False)
            self.append_log(f"{inst_id}: сигнал пропущен — уже открыто окно подтверждения ручного режима")
            return

        self._manual_dialog_open = True
        self._pending_manual_signal = dict(payload or {})
        inst_id = str(payload.get("inst_id") or "—")
        side = self._human_side(str(payload.get("side") or "—"))
        system_name = str(payload.get("system_name") or "—")
        price = float(payload.get("price") or 0.0)
        atr = float(payload.get("atr") or 0.0)
        timeframe = str(payload.get("timeframe") or "—")
        reason = str(payload.get("reason") or "signal")

        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Ручной режим: найден сигнал")
        box.setText("Найден новый сигнал для открытия позиции.")
        box.setInformativeText(
            f"Инструмент: {inst_id}\n"
            f"Направление: {side}\n"
            f"Система: {system_name}\n"
            f"Таймфрейм: {timeframe}\n"
            f"Цена: {price:.6f}\n"
            f"ATR: {atr:.6f}\n"
            f"Причина: {reason}"
        )
        trade_btn = box.addButton("Торгуем", QMessageBox.ButtonRole.AcceptRole)
        skip_btn = box.addButton("Пропускаем", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip_btn)
        box.setEscapeButton(skip_btn)
        box.setWindowModality(Qt.WindowModality.ApplicationModal)
        box.exec()

        allow = box.clickedButton() is trade_btn
        if self.engine is not None:
            self.engine._set_manual_entry_decision(allow)

        self.append_log(f"{inst_id}: ручной режим — {'торгуем' if allow else 'пропускаем'}")
        self._pending_manual_signal = None
        self._manual_dialog_open = False
        self._stop_telegram_screenshot_timer()

    def start_engine_from_controls(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            cfg = self.start_window.build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка параметров", str(exc))
            return
        self.current_cfg = cfg
        self.launch_engine(cfg)

    def _sync_toggle_button_state(self) -> None:
        if not hasattr(self, "toggle_button"):
            return
        if self._engine_transitioning and self._engine_transition_action == "starting":
            self.toggle_button.setText("STARTING...")
            self.toggle_button.setProperty("running", True)
            self.toggle_button.setEnabled(False)
        elif self._engine_transitioning and self._engine_transition_action == "stopping":
            self.toggle_button.setText("STOPPING...")
            self.toggle_button.setProperty("running", True)
            self.toggle_button.setEnabled(False)
        elif self._bot_running:
            self.toggle_button.setText("STOP BOT")
            self.toggle_button.setProperty("running", True)
            self.toggle_button.setEnabled(True)
        else:
            self.toggle_button.setText("START BOT")
            self.toggle_button.setProperty("running", False)
            self.toggle_button.setEnabled(True)
        self.toggle_button.style().unpolish(self.toggle_button)
        self.toggle_button.style().polish(self.toggle_button)
        self.toggle_button.update()

    def _set_engine_transition(self, active: bool, action: str = "") -> None:
        self._engine_transitioning = bool(active)
        self._engine_transition_action = str(action or "")
        if hasattr(self, "lbl_status") and self.lbl_status is not None:
            if active and action == "starting":
                self.lbl_status.setText("Статус: запуск...")
            elif active and action == "stopping":
                self.lbl_status.setText("Статус: остановка...")
        if hasattr(self, "lbl_header_status_chip") and getattr(self, "lbl_header_status_chip", None) is not None:
            if active and action == "starting":
                self.lbl_header_status_chip.setText("ENGINE: STARTING")
            elif active and action == "stopping":
                self.lbl_header_status_chip.setText("ENGINE: STOPPING")
        self._sync_toggle_button_state()
        self._apply_runtime_ui_profile()
        self._refresh_error_indicator()

    def start_engine_from_controls(self) -> None:
        if self._engine_transitioning or (self.worker and self.worker.isRunning()):
            return
        try:
            cfg = self.start_window.build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка параметров", str(exc))
            return
        self.current_cfg = cfg
        self._set_engine_transition(True, "starting")
        QTimer.singleShot(0, lambda cfg=cfg: self.launch_engine(cfg))

    def toggle_engine(self) -> None:
        if self._engine_transitioning:
            return
        if self.worker and self.worker.isRunning():
            self.stop_engine()
            return

        try:
            cfg = self.start_window.build_config()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка параметров", str(exc))
            return

        self.current_cfg = cfg
        self._set_engine_transition(True, "starting")
        QTimer.singleShot(0, lambda cfg=cfg: self.launch_engine(cfg))

    def _on_worker_finished(self) -> None:
        self.engine = None
        self.worker = None
        self._bot_running = False
        self._bot_started_ts = None
        self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
        self._pending_manual_signal = None
        self._manual_dialog_open = False
        self._set_engine_transition(False, "")
        self._sync_toggle_button_state()
        self._stop_telegram_screenshot_timer()
        self._apply_runtime_ui_profile()
        self._refresh_error_indicator()
        self.refresh_blocked_instruments_view()
        self._safe_set_runtime_label("Время работы: —")
        self._safe_set_label_text("lbl_header_status_chip", "ENGINE: STOPPED")
        if self._close_after_stop_requested:
            self._close_after_stop_requested = False
            log_heartbeat("gui", "close_after_stop")
            QTimer.singleShot(0, self.close)

    def _on_worker_engine_ready(self, engine: TurtleEngine) -> None:
        try:
            self.engine = engine
            self.engine.snapshot.connect(self._safe_on_snapshot)
            self.engine.log_line.connect(self.append_log)
            self.engine.status.connect(self.on_status)
            self.engine.error.connect(self.on_error)
            self.engine.entry_candidate.connect(self.on_entry_candidate)
            try:
                self.manual_add_units_requested.connect(self.engine.handle_manual_add_units, Qt.ConnectionType.QueuedConnection)
            except Exception:
                pass
            cfg = self.current_cfg
            if cfg is None:
                return
            self._configure_telegram_screenshots(cfg)
            self._bot_running = True
            self._snapshot_refresh_interval_sec = max(1, int(getattr(cfg, "snapshot_interval_sec", 2) or 2))
            self._apply_trade_mode_to_controls(getattr(cfg, "trade_mode", "auto"))
            self._snapshot_countdown_sec = 0
            self._bot_started_ts = time.time()
            self._set_engine_transition(False, "")
            self._sync_toggle_button_state()
            self.refresh_blocked_instruments_view()
            self.append_log(f"Бот запущен пользователем (шаг: {cfg.timeframe})")
            self.append_log(f"Проверка параметров запуска: GUI={self.start_window.timeframe_combo.currentData()} | Config={cfg.timeframe}")
            self.append_log(f"Signal audit: {SIGNAL_AUDIT_FILE}")
            self._apply_runtime_ui_profile()
            self._refresh_error_indicator()
            self._refresh_telegram_controls()
            if self.telegram_ui_notifier is not None and getattr(self.telegram_ui_notifier, "enabled", False):
                account_label = "demo" if str(getattr(cfg, "flag", "1")) == "1" else "main"
                self._start_telegram_task(message=f"OKX Turtle Bot {APP_VERSION} запущен | account={account_label} | tf={cfg.timeframe} | mode={getattr(cfg, 'trade_mode', 'auto')}", success_log="Telegram: отправлено стартовое сообщение", error_prefix="Telegram: не удалось отправить стартовое сообщение")
        except RuntimeError:
            return

    def _on_worker_startup_failed(self, error_text: str) -> None:
        self.engine = None
        self._bot_running = False
        self._bot_started_ts = None
        self._set_engine_transition(False, "")
        self._sync_toggle_button_state()
        self._stop_telegram_screenshot_timer()
        self._apply_runtime_ui_profile()
        self._refresh_error_indicator()
        self._refresh_telegram_controls()
        QMessageBox.critical(self, "Ошибка запуска", error_text)

    def launch_engine(self, cfg: BotConfig) -> None:
        if self.worker and self.worker.isRunning():
            self._set_engine_transition(False, "")
            QMessageBox.information(self, "Уже запущен", "Сначала останови текущего бота")
            return
        self.current_cfg = cfg
        self.worker = WorkerThread(cfg)
        self.worker.engine_ready.connect(self._on_worker_engine_ready)
        self.worker.startup_failed.connect(self._on_worker_startup_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def stop_engine(self) -> None:
        if self._engine_transitioning and self._engine_transition_action == "stopping":
            return
        self._pending_manual_signal = None
        self._manual_dialog_open = False
        if self.worker and self.worker.isRunning():
            self._set_engine_transition(True, "stopping")
            if self.engine is not None:
                self.engine._set_manual_entry_decision(False)
            self._stop_telegram_screenshot_timer()
            self.append_log("Остановка запрошена")
            try:
                self.worker.request_engine_stop()
            except Exception as exc:
                self.append_log(f"Не удалось передать команду остановки worker: {exc}")
            return
        self.engine = None
        self._on_worker_finished()

    def closeEvent(self, event) -> None:
        self._stop_telegram_screenshot_timer()
        log_heartbeat("gui", "close_event", bot_running=bool(self._bot_running), worker_running=bool(self.worker and self.worker.isRunning()))
        if self.engine or (self.worker and self.worker.isRunning()):
            self._close_after_stop_requested = True
            self.append_log("Закрытие окна отложено: сначала останавливаю движок")
            self.stop_engine()
            event.ignore()
            return
        super().closeEvent(event)

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
        return

    def _qt_widget_alive(self, widget) -> bool:
        if widget is None:
            return False
        try:
            widget.objectName()
            return True
        except RuntimeError:
            return False
        except Exception:
            return True

    def _safe_set_widget_text(self, widget, text: str) -> None:
        if not self._qt_widget_alive(widget):
            return
        try:
            widget.setText(text)
        except RuntimeError:
            pass

    def _safe_set_widget_style(self, widget, style: str) -> None:
        if not self._qt_widget_alive(widget):
            return
        try:
            widget.setStyleSheet(style)
        except RuntimeError:
            pass

    def _safe_label_text(self, attr_name: str, default: str = "") -> str:
        widget = getattr(self, attr_name, None)
        if not self._qt_widget_alive(widget):
            return default
        try:
            return widget.text()
        except RuntimeError:
            setattr(self, attr_name, None)
            return default

    def _safe_set_attr_style(self, attr_name: str, style: str) -> None:
        widget = getattr(self, attr_name, None)
        if not self._qt_widget_alive(widget):
            setattr(self, attr_name, None)
            return
        try:
            widget.setStyleSheet(style)
        except RuntimeError:
            setattr(self, attr_name, None)

    def _safe_set_label_text(self, attr_name: str, text: str) -> None:
        label = getattr(self, attr_name, None)
        if not self._qt_widget_alive(label):
            setattr(self, attr_name, None)
            return
        try:
            label.setText(text)
        except RuntimeError:
            setattr(self, attr_name, None)

    def _safe_set_runtime_label(self, text: str) -> None:
        self._safe_set_label_text("lbl_runtime", text)

    def _safe_runtime_label_text(self) -> str:
        label = getattr(self, "lbl_runtime", None)
        if label is None:
            return "Время работы: —"
        try:
            return label.text()
        except RuntimeError:
            self.lbl_runtime = None
            return "Время работы: —"

    def _update_runtime_label(self) -> None:
        if not getattr(self, "lbl_runtime", None):
            return
        if self._bot_started_ts and self.engine and self.worker and self.worker.isRunning():
            elapsed = max(0, int(time.time() - self._bot_started_ts))
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)
            self._safe_set_runtime_label(f"Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self._safe_set_runtime_label("Время работы: —")

    def _on_gui_timer_tick(self) -> None:
        try:
            if self.engine and self.worker and self.worker.isRunning():
                self._snapshot_countdown_sec -= 1
                if self._snapshot_countdown_sec <= 0:
                    self.request_snapshot()
                    if not self._engine_transitioning and not self._telegram_screenshot_inflight:
                        self.refresh_blocked_instruments_view()
                    self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec
            else:
                self._snapshot_countdown_sec = self._snapshot_refresh_interval_sec

            self._update_runtime_label()
        except RuntimeError:
            return

    def _safe_on_snapshot(self, payload: dict) -> None:
        try:
            self.on_snapshot(payload)
        except RuntimeError:
            return

    def refresh_from_latest_snapshot(self) -> None:
        self.request_snapshot()

    def _top_engine_candidate(self) -> dict:
        candidates = []
        if self.engine is not None:
            try:
                candidates = list(getattr(self.engine, "last_scan_candidates", []) or [])
            except Exception:
                candidates = []
        return dict(candidates[0]) if candidates else {}

    def _market_tile_status(self, inst: str, candidate_map: dict, blocked: set, risky_exit: set) -> tuple[str, float, str]:
        if inst in candidate_map:
            item = candidate_map[inst]
            side = str(item.get("side") or "watch").lower()
            status = "LONG CANDIDATE" if side == "long" else "SHORT CANDIDATE"
            score = max(12.0, min(99.0, float(item.get("breakout_distance_atr", 0.0)) * 22.0 + float(item.get("liquidity_score", 0.0)) * 7.0 + float(item.get("freshness_score", 0.0)) * 18.0 - float(item.get("recent_trade_penalty", 0.0)) * 10.0))
            reason = f"{item.get('system_name', 'Turtle')} | {item.get('liquidity_profile', self.balance_chart_step_combo.currentData() if hasattr(self, 'balance_chart_step_combo') else 'scan')} | breakout armed"
            return status, score, reason
        if inst in risky_exit or inst in blocked:
            score = 36.0 if inst in risky_exit else 42.0
            reason = 'Liquidity / exit-risk watchlist' if inst in risky_exit else 'Temporarily blocked / restricted'
            return 'RISK', score, reason
        return 'WATCH', 14.0, 'Watching breakout / ATR / liquidity alignment'

    def on_snapshot(self, payload: dict) -> None:
        self.latest_snapshot = payload
        heavy_refresh_allowed = (time.time() - float(getattr(self, "_last_heavy_snapshot_at", 0.0) or 0.0)) >= (2.0 if self._bot_running else 0.0)
        if heavy_refresh_allowed:
            self._last_heavy_snapshot_at = time.time()
        settings = payload.get("settings", {})
        analytics = payload.get("analytics", {})
        engine_info = payload.get("engine", {})
        open_positions = payload.get("open_positions", [])
        scanner = getattr(self.engine, "market_scanner", None) if self.engine is not None else getattr(self, "market_scanner", None)
        if scanner is not None:
            try:
                scanner.upsert_good_positions(list(open_positions or []))
            except Exception:
                logging.exception("Failed to update GOOD position review rows")

        account_name = settings.get('account', '—')
        timeframe = settings.get('timeframe', '—')
        mode = settings.get('trade_mode', getattr(self.current_cfg, 'trade_mode', 'auto'))
        self._apply_trade_mode_to_controls(mode)

        self._safe_set_label_text("lbl_account", f"Аккаунт: {account_name}")
        self._safe_set_label_text("lbl_timeframe", f"Таймфрейм: {timeframe}")
        self._safe_set_label_text("lbl_header_mode", f"ACCOUNT: {account_name.upper()}")
        self._safe_set_label_text("lbl_header_tf_chip", f"TF: {timeframe}")
        pos_chip = f"POS: {len(open_positions)}/{getattr(self.current_cfg, 'max_open_positions_total', 16) if self.current_cfg else 16}"
        self._safe_set_label_text("lbl_header_pos_chip", pos_chip)

        bal_total = payload.get('balance_total', 0.0)
        bal_used = payload.get('balance_used', 0.0)
        bal_avail = payload.get('balance_available', 0.0)
        equity_total = float(analytics.get('equity_total', bal_total + analytics.get('open_pnl', 0.0)) or (bal_total + analytics.get('open_pnl', 0.0)))
        self._safe_set_label_text("lbl_balance_hero", f"BALANCE\n{bal_total:,.2f} USDT")
        self._safe_set_label_text("lbl_balance_used", f"USED\n{bal_used:,.2f} USDT")
        self._safe_set_label_text("lbl_balance_available", f"AVAILABLE\n{bal_avail:,.2f} USDT")
        self._safe_set_label_text("lbl_balance_equity", '')
        self._safe_set_label_text("lbl_balance_formula", '')
        self._safe_set_label_text("lbl_balance_summary", f"Баланс: {bal_total:.0f} | Использовано: {bal_used:.0f} | Доступно: {bal_avail:.0f}")
        self._safe_set_label_text("lbl_session_pnl", f"Session PnL: {analytics.get('realized_pnl', 0.0) + analytics.get('open_pnl', 0.0):+.2f} USDT")
        self._safe_set_label_text("lbl_positions", f"POS: {len(open_positions)}")
        ready_count = int(analytics.get('trade_ready_count', 0) or 0)
        available_after_bans = int(analytics.get('available_after_bans_count', 0) or 0)
        scan_total = int(analytics.get('scan_universe_total', 0) or 0)
        blocked_total = int(analytics.get('blocked_total', 0) or 0)
        if hasattr(self, 'lbl_blocked_count') and self.lbl_blocked_count is not None:
            self._safe_set_label_text("lbl_blocked_count", f"BLOCKS: {blocked_total}")
        if hasattr(self, 'lbl_available_markets') and self.lbl_available_markets is not None:
            self._safe_set_label_text("lbl_available_markets", f"AVAIL: {available_after_bans}/{scan_total}")
        if hasattr(self, 'lbl_ready_count') and self.lbl_ready_count is not None:
            self._safe_set_label_text("lbl_ready_count", f"READY: {ready_count}")

        cycle_duration = float(engine_info.get('last_cycle_duration_sec', 0.0) or 0.0)
        pos_cycle_active = bool(engine_info.get('position_cycle_active', False))
        pos_cycle_progress = str(engine_info.get('position_cycle_progress', '0/0') or '0/0')
        pos_cycle_last_duration = float(engine_info.get('position_cycle_last_duration_sec', analytics.get('position_cycle_last_duration_sec', 0.0)) or 0.0)
        pos_cycle_last_completed = str(engine_info.get('position_cycle_last_completed_utc', analytics.get('position_cycle_last_completed_utc', '—')) or '—')
        if pos_cycle_active:
            self._safe_set_label_text("lbl_cycle_duration", f"Цикл позиций: {pos_cycle_progress} | RUN | {pos_cycle_last_duration:.2f} сек")
            self._safe_set_label_text("lbl_header_pos_cycle_chip", f"POS CYCLE: RUN {pos_cycle_progress}")
        else:
            self._safe_set_label_text("lbl_cycle_duration", f"Цикл позиций: {pos_cycle_progress} | last {pos_cycle_last_duration:.2f} сек | {pos_cycle_last_completed}")
            self._safe_set_label_text("lbl_header_pos_cycle_chip", f"POS CYCLE: {pos_cycle_progress} | {pos_cycle_last_duration:.1f}s")
        if pos_cycle_active:
            self._safe_set_attr_style("lbl_header_pos_cycle_chip", "color: #ff9f43; font-weight: 900;")
        elif pos_cycle_last_duration > 10:
            self._safe_set_attr_style("lbl_header_pos_cycle_chip", "color: #ff4d4f; font-weight: 900;")
        else:
            self._safe_set_attr_style("lbl_header_pos_cycle_chip", "color: #00ffa3; font-weight: 900;")
        if cycle_duration > 10:
            self._safe_set_attr_style("lbl_cycle_duration", "color: #ff4d4f; font-weight: 800;")
        elif cycle_duration >= 5:
            self._safe_set_attr_style("lbl_cycle_duration", "color: #ff9f43; font-weight: 800;")
        else:
            self._safe_set_attr_style("lbl_cycle_duration", "color: #00ffa3; font-weight: 800;")

        self._safe_set_label_text("lbl_open_pnl", f"Open PnL: {analytics.get('open_pnl', 0.0):+.4f}")
        self._safe_set_label_text("lbl_avg_open", f"Средний PnL %: {analytics.get('avg_open_pnl_pct', 0.0):+.2f}%")
        self._safe_set_label_text("lbl_best", f"Лучший PnL %: {analytics.get('best_open_pnl_pct', 0.0):+.2f}%")
        self._safe_set_label_text("lbl_worst", f"Худший PnL %: {analytics.get('worst_open_pnl_pct', 0.0):+.2f}%")
        self._safe_set_label_text("lbl_long_short", f"Long/Short: {analytics.get('long_count', 0)} / {analytics.get('short_count', 0)}")
        self._safe_set_label_text("lbl_realized", f"Реализованный PnL: {analytics.get('realized_pnl', 0.0):+.4f}")
        self._safe_set_label_text("lbl_closed_stats", f"Закрытых сделок: {analytics.get('closed_count', 0)}")
        self._safe_set_label_text("lbl_winrate", f"Winrate: {analytics.get('winrate', 0.0):.2f}%")
        if hasattr(self, 'lbl_balance_trend') and self.lbl_balance_trend is not None:
            self._safe_set_label_text("lbl_balance_trend", f"Изменение баланса: Сегодня {analytics.get('day_change_pct', 0.0):+.2f}% | 7 дней {analytics.get('week_change_pct', 0.0):+.2f}%")
        self._safe_set_label_text("lbl_risk_panel", f"Использовано риска: {analytics.get('used_risk_pct', 0.0):.2f}% / {analytics.get('max_risk_budget_pct', 0.0):.2f}%")
        self._safe_set_label_text("lbl_trade_speed", f"Сделок сегодня: {analytics.get('trades_today', 0)} | Средняя длительность: {format_duration(analytics.get('avg_duration_sec', 0))}")

        regime_label = analytics.get('turtle_regime_label', '—')
        regime_score = int(analytics.get('turtle_regime_score', 0) or 0)
        regime_inst = analytics.get('turtle_regime_instrument', '—')
        regime_channel = float(analytics.get('turtle_regime_channel_atr', 0.0) or 0.0)
        regime_eff = float(analytics.get('turtle_regime_efficiency', 0.0) or 0.0)
        regime_atr_pct = float(analytics.get('turtle_regime_atr_pct', 0.0) or 0.0)
        signal_funnel = payload.get('signal_funnel', {}) or {}
        top_candidate = self._top_engine_candidate()
        if top_candidate:
            cand_inst = str(top_candidate.get('inst_id', '—')).replace('-USDT-SWAP', '')
            cand_system = str(top_candidate.get('system_name', 'Turtle'))
            cand_side = str(top_candidate.get('side', 'watch')).upper()
            cand_breakout = float(top_candidate.get('breakout_distance_atr', 0.0) or 0.0)
            cand_liq = float(top_candidate.get('liquidity_score', 0.0) or 0.0)
            cand_profile = str(top_candidate.get('liquidity_profile', timeframe) or timeframe)
            cand_fresh = float(top_candidate.get('freshness_score', 0.0) or 0.0)
            entry_allowed = 'YES' if regime_label != 'Флэт' else 'WAIT'
            engine_score = min(4, max(1, regime_score + (1 if cand_breakout > 0.18 else 0)))
            self._safe_set_label_text("lbl_turtle_regime", f"Кандидат: {cand_inst} | {cand_system} {cand_side} | Entry allowed: {entry_allowed}")
            self._safe_set_label_text("lbl_turtle_state_a", f"BREAKOUT: {cand_system} | dist {cand_breakout:.2f} ATR | regime {regime_label}")
            self._safe_set_label_text("lbl_turtle_state_b", f"TREND / ATR: ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%")
            self._safe_set_label_text("lbl_turtle_state_c", f"LIQUIDITY: profile {cand_profile} | score {cand_liq:.1f} | fresh {cand_fresh:.2f} | ready {ready_count}")
            self._safe_set_label_text("lbl_turtle_score", f"ENTRY STATUS: {entry_allowed} | ENGINE SCORE {engine_score}/4 | CAND {int(signal_funnel.get('candidates', 0) or 0)}")
        else:
            entry_allowed = "YES" if regime_label == "Трендовый" and regime_score >= 3 else "NO"
            liquidity_pass = "PASS" if regime_label == "Трендовый" else ("WAIT" if regime_label == "Нейтральный" else "FILTERED")
            self._safe_set_label_text("lbl_turtle_regime", f"Кандидат: {regime_inst} | Режим: {regime_label} | Entry allowed: {entry_allowed}")
            self._safe_set_label_text("lbl_turtle_state_a", f"BREAKOUT: waiting for Donchian trigger | regime {regime_label}")
            self._safe_set_label_text("lbl_turtle_state_b", f"TREND / ATR: ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%")
            self._safe_set_label_text("lbl_turtle_state_c", f"LIQUIDITY: {liquidity_pass} | MODE {mode.upper()} | ready {ready_count} | {regime_inst.replace('-USDT-SWAP', '')}")
            self._safe_set_label_text("lbl_turtle_score", f"ENTRY STATUS: {entry_allowed} | ENGINE SCORE {regime_score}/4 | CAND {int(signal_funnel.get('candidates', 0) or 0)}")
        if regime_label == "Трендовый":
            turtle_style = "color: #00ffa3; font-weight: 800;"
        elif regime_label == "Нейтральный":
            turtle_style = "color: #ff9f43; font-weight: 800;"
        elif regime_label == "Флэт":
            turtle_style = "color: #ff4d4f; font-weight: 800;"
        else:
            turtle_style = ""
        for lbl in (self.lbl_turtle_regime, self.lbl_turtle_state_a, self.lbl_turtle_state_b, self.lbl_turtle_state_c, self.lbl_turtle_score):
            self._safe_set_widget_style(lbl, turtle_style)

        balance_history = payload.get('balance_history', [])
        if heavy_refresh_allowed:
            self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), [])
        if hasattr(self, "lbl_balance_step") and self.lbl_balance_step is not None:
            self._safe_set_label_text("lbl_balance_step", f"Шаг: {self.balance_chart_step_combo.currentData()}")
        shown_points = len(self.balance_chart._bucket_points()) if hasattr(self.balance_chart, '_bucket_points') else 0
        if hasattr(self, "lbl_balance_points") and self.lbl_balance_points is not None:
            self._safe_set_label_text("lbl_balance_points", f"Показано значений: {shown_points}/30")

        pending_close = sum(1 for row in open_positions if row.get('close_pending'))
        self._safe_set_label_text("lbl_close_pending", f"Close pending: {pending_close}")
        md = payload.get('market_data_cache', {})
        exec_watch = int(analytics.get('scanner_exec_watch', 0) or 0)
        self._safe_set_label_text("lbl_exec_watch", f"Execution watchlist: {exec_watch}")
        self._safe_set_label_text("lbl_scanner_total", f"TOTAL: {int(analytics.get('scanner_total', 0) or 0)}")
        self._safe_set_label_text("lbl_scanner_scanned", f"SCANNED: {int(analytics.get('scanner_scanned', analytics.get('scanner_ready', 0)) or 0)}")
        self._safe_set_label_text("lbl_scanner_allowed", f"ALLOWED: {int(analytics.get('scanner_allowed', analytics.get('scanner_admitted', 0)) or 0)}")
        self._safe_set_label_text("lbl_scanner_blocked", f"BLOCKED: {int(analytics.get('scanner_blocked', analytics.get('scanner_risky', 0)) or 0)}")
        self._safe_set_label_text("lbl_scanner_dead", f"DEAD: {int(analytics.get('scanner_dead', 0) or 0)}")
        self._safe_set_label_text("lbl_scanner_saw", f"SAW: {int(analytics.get('scanner_saw', 0) or 0)}")
        self._safe_set_label_text("lbl_scanner_ripping", f"RIPPING: {int(analytics.get('scanner_ripping', 0) or 0)}")
        self._safe_set_label_text("lbl_scanner_pending", f"PENDING: {int(analytics.get('scanner_pending', 0) or 0)}")
        self._safe_set_label_text("lbl_scanner_status", f"STATUS: {str(analytics.get('scanner_status_text', 'IDLE') or 'IDLE')}")
        if heavy_refresh_allowed:
            self._update_scanner_review_views()

        header_status = 'RUNNING' if self._bot_running else 'IDLE'
        self._safe_set_label_text("lbl_header_status_chip", f"ENGINE: {header_status}")
        uptime_text = self._safe_label_text("lbl_runtime", "Время работы: —").replace('Время работы: ', '')
        self._safe_set_label_text("lbl_header_uptime_chip", f"UPTIME: {uptime_text}")
        self._update_system_health_indicators()

        # market radar
        radar_rows = []
        blocked = set()
        candidate_map = {}
        if self.engine is not None:
            blocked.update(getattr(self.engine, 'blocked_instruments', {}).keys())
            blocked.update(getattr(self.engine, 'illiquid_instruments', {}).keys())
            blocked.update(getattr(self.engine, 'execution_risk_events', {}).keys())
            try:
                candidate_map = {str(item.get('inst_id')): dict(item) for item in list(getattr(self.engine, 'last_scan_candidates', []) or [])[:8] if item.get('inst_id')}
            except Exception:
                candidate_map = {}
        for row in sorted(open_positions, key=lambda x: abs(float(x.get('trend_strength_atr', 0.0))), reverse=True)[:6]:
            inst = row.get('inst_id', '—')
            pnl_pct = float(row.get('pnl_pct', 0.0) or 0.0)
            trend = float(row.get('trend_strength_atr', 0.0) or 0.0)
            status = 'LONG' if str(row.get('side', '')).lower() == 'long' else 'SHORT'
            score = min(99.0, abs(trend) * 20.0 + abs(pnl_pct) * 3.0)
            reason = f"Open position | trend {trend:.2f} ATR | pnl {pnl_pct:+.2f}%"
            radar_rows.append((inst, pnl_pct, trend, status, score, reason))
        fallback_watch = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'LINK-USDT-SWAP', 'ATOM-USDT-SWAP', 'MINA-USDT-SWAP']
        risky_exit = {'LINK-USDT-SWAP', 'ATOM-USDT-SWAP', 'MINA-USDT-SWAP', 'BREV-USDT-SWAP'}
        ordered_watch = list(candidate_map.keys()) + list((getattr(self.current_cfg, 'execution_risk_watchlist', []) if self.current_cfg else []) or []) + fallback_watch
        for inst in ordered_watch:
            if len(radar_rows) >= 6:
                break
            if not inst or any(r[0] == inst for r in radar_rows):
                continue
            status, score, reason = self._market_tile_status(inst, candidate_map, blocked, risky_exit)
            radar_rows.append((inst, 0.0, 0.0, status, score, reason))
        for idx, (tile, (inst, pnl_pct, trend, status, score, reason)) in enumerate(zip(self.market_tiles, radar_rows)):
            base = float(pnl_pct or 0.0)
            if inst in candidate_map:
                item = candidate_map[inst]
                impulse = float(item.get('breakout_distance_atr', 0.0) or 0.0) * 0.22 + float(item.get('freshness_score', 0.0) or 0.0) * 0.12
                values = [base * 0.15 + math.sin((j / 17.0) * math.pi * 1.25) * (0.18 + impulse) + impulse * (j / 17.0) for j in range(18)]
            elif status in {'LONG', 'SHORT'}:
                values = [base * 0.25 + ((j - 8) * 0.03) + trend * (0.04 if j % 2 == 0 else -0.02) for j in range(18)]
            else:
                values = [math.sin((j / 17.0) * math.pi * 1.8 + idx * 0.45) * 0.10 + (0.02 if status == 'WATCH' else -0.01) for j in range(18)]
            tile.set_data(inst, pnl_pct, values, status=status, score=score, reason=reason)

        band_source = []
        for point in balance_history[-48:]:
            try:
                band_source.append(float(point.get('balance_total', 0.0)))
            except Exception:
                continue
        if not band_source:
            band_source = [0.0] * 48
        pnl_band = []
        for row in open_positions[-48:]:
            try:
                pnl_band.append(float(row.get('pnl_pct', 0.0)))
            except Exception:
                continue
        if not pnl_band:
            pnl_band = [0.0] * max(12, min(48, len(band_source)))
        self.glow_band.set_series(band_source, pnl_band)

        self._apply_status_style(self.lbl_open_pnl, analytics.get('open_pnl', 0.0))
        self._apply_status_style(self.lbl_avg_open, analytics.get('avg_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_best, analytics.get('best_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_worst, analytics.get('worst_open_pnl_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_realized, analytics.get('realized_pnl', 0.0))
        self._apply_status_style(self.lbl_winrate, analytics.get('winrate', 0.0), percent=True)
        if hasattr(self, 'lbl_balance_trend') and self.lbl_balance_trend is not None:
            self._apply_status_style(self.lbl_balance_trend, analytics.get('day_change_pct', 0.0), percent=True)
        self._apply_status_style(self.lbl_session_pnl, analytics.get('realized_pnl', 0.0) + analytics.get('open_pnl', 0.0))

        if not self._engine_transitioning:
            self.apply_filters()

    def on_balance_chart_step_changed(self, *_args) -> None:
        if not self.latest_snapshot:
            return
        balance_history = self.latest_snapshot.get("balance_history", [])
        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), [])
        if hasattr(self, "lbl_balance_step") and self.lbl_balance_step is not None:
            self._safe_set_label_text("lbl_balance_step", f"Шаг: {self.balance_chart_step_combo.currentData()}")
        if hasattr(self, "lbl_balance_points") and self.lbl_balance_points is not None:
            self.lbl_balance_points.setText(f"Показано значений: {len(self.balance_chart._bucket_points())}/30")

    def _apply_status_style(self, label: QLabel, value: float, percent: bool = False) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        if self._is_dark_theme:
            neutral = "#e5e7eb"
        else:
            neutral = "#202020"
        if numeric > 0:
            color = "#16a34a"
        elif numeric < 0:
            color = "#dc2626"
        else:
            color = neutral
        font_weight = "600" if percent or numeric != 0 else "500"
        card_style = label.property("card") == "true"
        extra = "background: transparent;"
        if card_style:
            extra = ""
        label.setStyleSheet(f"color: {color}; font-weight: {font_weight}; {extra}")

    def apply_filters(self) -> None:
        if not self.latest_snapshot:
            self.table_model.update_rows([])
            self.closed_table_model.update_rows([])
            self._refresh_manual_add_unit_controls()
            return

        open_rows = [
            row for row in self.latest_snapshot.get("open_positions", [])
            if not is_hidden_instrument(row.get("inst_id"))
        ]
        open_rows.sort(key=lambda x: float(x.get("unrealized_pnl", x.get("pnl", 0.0)) or 0.0), reverse=True)
        self.table_model.update_rows(open_rows)

        closed_rows = []
        for row in self.latest_snapshot.get("closed_trades", []):
            if is_hidden_instrument(row.get("inst_id")):
                continue
            normalized = dict(row)
            normalized["trade_context_file"] = str(row.get("trade_context_file", "") or "")
            closed_rows.append(normalized)
        closed_rows.sort(key=lambda x: float(x.get("pnl", 0.0) or 0.0), reverse=True)
        self.closed_table_model.update_rows(closed_rows)
        self._refresh_manual_add_unit_controls()

    def append_log(self, message: str) -> None:
        upper_message = str(message).upper()
        if False:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        color = '#8be9fd'
        if any(token in upper_message for token in ['LONG', 'OPEN', 'RUNNING', 'ЗАПУЩЕН', 'ПОДТВЕРЖДЁН']):
            color = '#00ffa3'
        elif any(token in upper_message for token in ['SHORT', 'STOP', 'ERROR', 'ОШИБКА', 'ОТКЛОНИЛА', 'ПРОПУЩЕН']):
            color = '#ff4d4f'
        elif any(token in upper_message for token in ['ADD', 'PYRAMID', 'ROTATION', 'RESET']):
            color = '#ff9f43'
        self._log_buffer.push(line, color)

    def _flush_log_batch(self, batch: list) -> None:
        if not batch:
            return
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.append('\n'.join(line for line, _ in batch))
        if hasattr(self, 'activity_feed') and self.activity_feed is not None:
            self.activity_feed.append('<br>'.join(f'<span style="color:{color};">{line}</span>' for line, color in batch))
            doc2 = self.activity_feed.document()
            if doc2.blockCount() > 120:
                cursor2 = self.activity_feed.textCursor()
                cursor2.movePosition(cursor2.MoveOperation.Start)
                for _ in range(min(24, doc2.blockCount() - 120)):
                    cursor2.select(cursor2.SelectionType.BlockUnderCursor)
                    cursor2.removeSelectedText()
                    cursor2.deleteChar()
                    cursor2.movePosition(cursor2.MoveOperation.Start)
        if hasattr(self, 'log_text') and self.log_text is not None:
            doc = self.log_text.document()
            max_blocks = 500
            if doc.blockCount() > max_blocks:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                for _ in range(min(40, doc.blockCount() - max_blocks)):
                    cursor.select(cursor.SelectionType.BlockUnderCursor)
                    cursor.removeSelectedText()
                    cursor.deleteChar()
                    cursor.movePosition(cursor.MoveOperation.Start)

    def on_status(self, message: str) -> None:
        self.lbl_status.setText(f"Статус: {message}")
        lower = message.lower()
        if "запущен" in lower:
            self._bot_running = True
            self.lbl_status.setStyleSheet("color: #00ffa3; font-weight: 800;")
            if hasattr(self, 'lbl_header_status_chip'): self.lbl_header_status_chip.setText('ENGINE: RUNNING')
        elif "остановлен" in lower:
            self._bot_running = False
            self.lbl_status.setStyleSheet("color: #ff4d4f; font-weight: 800;")
            if hasattr(self, 'lbl_header_status_chip'): self.lbl_header_status_chip.setText('ENGINE: STOPPED')
        else:
            self.lbl_status.setStyleSheet("")
        self._sync_toggle_button_state()
        self._update_system_health_indicators()
        self.append_log(message)

    def on_error(self, message: str) -> None:
        self.append_log(message)
