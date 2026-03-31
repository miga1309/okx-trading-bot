# Auto-extracted from app/legacy_runtime.py during one-iteration runtime split
from app.runtime_support import *

@dataclass








class TurtleEngine(QObject):
    snapshot = pyqtSignal(dict)
    log_line = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    entry_candidate = pyqtSignal(dict)

    def __init__(self, cfg: BotConfig):
        super().__init__()
        self.cfg = cfg
        self.gateway = OkxGateway(cfg, hidden_checker=is_hidden_instrument)
        self.gateway.engine_ref = self
        self.market_data_cache = MarketDataCache(self.gateway, cfg, log_callback=self.log_line.emit, hidden_checker=is_hidden_instrument)
        self.gateway.attach_cache(self.market_data_cache)
        self.ws_manager = OkxWsManager(cfg, log_callback=self.log_line.emit)
        self.gateway.attach_ws_manager(self.ws_manager)
        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)
        self.signal_audit_logger = SignalAuditLogger(SIGNAL_AUDIT_FILE)
        self.position_journal_logger = EngineStatsLogger(POSITION_JOURNAL_FILE)
        self.position_snapshot_logger = EngineStatsLogger(POSITION_SNAPSHOTS_FILE)
        self.system_health_logger = EngineStatsLogger(SYSTEM_HEALTH_FILE)
        self.connectivity_logger = EngineStatsLogger(CONNECTIVITY_LOG_FILE)
        self.pyramid_diagnostics_logger = EngineStatsLogger(PYRAMID_DIAGNOSTICS_FILE)
        self.reentry_diagnostics_logger = EngineStatsLogger(REENTRY_DIAGNOSTICS_FILE)
        self.breakout_quality_logger = EngineStatsLogger(BREAKOUT_QUALITY_FILE)
        self.stop_engine_logger = EngineStatsLogger(STOP_ENGINE_FILE)
        self.running = False
        self._stop_requested = False
        self._shutdown_finalized = False
        self.lock = threading.Lock()
        self.position_state: Dict[str, PositionState] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.balance_history: List[dict] = []
        self.balance_lock = threading.Lock()
        self.latest_balance_snapshot: dict = {}
        self.balance_poller_running = False
        self.balance_poller_thread: Optional[threading.Thread] = None
        self._load_state()
        self.last_scan_started_at: Optional[float] = None
        self.last_scan_finished_at: Optional[float] = None
        self.last_positions_check_at: Optional[float] = None
        self.last_entry_scan_at: Optional[float] = None
        self.last_snapshot_emitted_at: Optional[float] = None
        self.last_position_snapshot_minute: Optional[str] = None
        self.last_system_health_minute: Optional[str] = None
        self.last_connectivity_summary_minute: Optional[str] = None
        self.exchange_health_check_interval_sec: float = 20.0
        self.exchange_last_health_check_ts: float = 0.0
        self.exchange_connectivity_state: str = "IDLE"
        self.exchange_connectivity_since_ts: float = time.time()
        self.exchange_connectivity_components: Dict[str, dict] = {}
        self.exchange_connectivity_last_error: str = ""
        self.exchange_recovery_pending: bool = False
        self.exchange_active_incident: Optional[dict] = None
        self.blocked_instruments: Dict[str, str] = {}
        self.temp_blocked_until: Dict[str, float] = {}
        self.close_retry_after: Dict[str, float] = {}
        self.recent_stopouts: Dict[str, dict] = {}
        self.illiquid_instruments: Dict[str, float] = {}
        self.illiquid_rejections: Dict[str, dict] = {}
        self.execution_risk_events: Dict[str, dict] = {}
        self.stop_engine = StopEngine(self)
        self.runtime_engine_bundle = RuntimeEngineBundle.attach(self)
        self.stage3_engine_bundle = Stage3EngineBundle.attach(self)
        self.instrument_health = InstrumentHealthTracker()
        self.market_scanner = MarketScannerRuntime(self.gateway, cfg, log_callback=self.log_line.emit, hard_blocked=set(getattr(cfg, "blacklist", []) or []), validation_log_path=SCANNER_VALIDATION_LOG_FILE, state_path=SCANNER_VALIDATION_STATE_FILE)
        self.telegram = TelegramNotifier(
            enabled=False if TELEGRAM_HARD_DISABLED else cfg.telegram_enabled,
            bot_token=cfg.telegram_bot_token,
            chat_id=cfg.telegram_chat_id,
            queue_dir=str(TELEGRAM_QUEUE_DIR),
        )
        if HIDDEN_INSTRUMENTS:
            self.log_line.emit(f"[PATCH] Hard block active: {', '.join(sorted(HIDDEN_INSTRUMENTS))}")
        self._manual_entry_event = threading.Event()
        self._manual_entry_allowed = False
        self.scan_cycle_seq = 0
        self.recent_rotation_exits: Dict[str, float] = {}
        self.last_scan_candidates: List[dict] = []
        self.last_near_pass_candidates: List[dict] = []
        self.last_signal_funnel: Dict[str, int] = {}
        self.last_scan_cycle_id: int = 0
        self.last_trade_ready_metrics: Dict[str, object] = {}
        self.last_trade_ready_log_at: float = 0.0
        self.pending_entries: Dict[str, PendingEntry] = {}
        self.used_breakouts: Dict[str, float] = {}
        self.reentry_guards: Dict[tuple[str, str, str], dict] = {}
        self.loss_streak_by_symbol_side: Dict[tuple[str, str], int] = defaultdict(int)
        self.symbol_quarantine_until: Dict[str, float] = {}
        self.position_cycle_active: bool = False
        self.position_cycle_last_minute_key: str = ""
        self.position_cycle_started_at: float = 0.0
        self.position_cycle_finished_at: float = 0.0
        self.position_cycle_last_duration_sec: float = 0.0
        self.position_cycle_total: int = 0
        self.position_cycle_done: int = 0
        self.position_cycle_last_error: str = ""
        self.position_cycle_scanner_paused: bool = False
        self.position_cycle_last_completed_utc: str = "—"

    @pyqtSlot(str, int)
    def handle_manual_add_units(self, inst_id: str, extra_units: int = 1) -> None:
        try:
            lifecycle = getattr(self, "position_lifecycle", None)
            manual_actions = getattr(lifecycle, "manual_actions", None) if lifecycle is not None else None
            if manual_actions is None:
                raise RuntimeError("manual actions engine unavailable")
            result = manual_actions.execute_manual_add_units(str(inst_id or "").strip(), int(extra_units or 1))
            if not bool((result or {}).get("ok", False)):
                self.error.emit(f"Ручной добор отклонён: {result}")
                return
            units = int((result or {}).get("units", 0) or 0)
            add_qty = float((result or {}).get("add_qty", 0.0) or 0.0)
            fill_price = float((result or {}).get("fill_price", 0.0) or 0.0)
            self.log_line.emit(f"Ручной добор выполнен {inst_id}: qty+={add_qty:.6f}, fill={fill_price:.6f}, units={units}")
            state = self.position_state.get(str(inst_id or '').strip())
            if state is not None:
                state.popup_snapshot_dirty = True
        except Exception as exc:
            logging.exception("Manual add units failed: %s", exc)
            self.error.emit(f"Ручной добор не выполнен: {exc}")

    def request_stop(self) -> None:
        self._stop_requested = True
        self.running = False
        self.log_line.emit("Получена команда остановки")

    def finalize_stop(self) -> None:
        if self._shutdown_finalized:
            return
        self._shutdown_finalized = True
        self.running = False
        try:
            self.market_data_cache.stop()
        except Exception:
            pass
        try:
            self.ws_manager.stop()
        except Exception:
            pass
        try:
            self.stop_balance_poller()
        except Exception:
            pass
        try:
            self._save_state()
        except Exception:
            logging.exception("Failed to save state during finalize_stop")
        self.stats_logger.log(
            "bot_stopped",
            open_positions=len(self.position_state),
            closed_trades=len(self.closed_trades),
        )
        self.position_journal_logger.log("session_stop", open_positions=len(self.position_state), closed_trades=len(self.closed_trades))
        self.status.emit("Бот остановлен")

    def _interruptible_sleep(self, seconds: float) -> None:
        deadline = time.time() + max(0.0, float(seconds or 0.0))
        while self.running and not self._stop_requested and time.time() < deadline:
            self._maybe_run_exchange_health_check(force=False)
            time.sleep(min(0.2, max(0.0, deadline - time.time())))

    def _exchange_probe_inst_id(self) -> str:
        swap_ids = list(getattr(self.gateway, "swap_ids", []) or [])
        return str(swap_ids[0] if swap_ids else "BTC-USDT-SWAP")

    def _probe_exchange_component(self, name: str, fn):
        started = time.time()
        try:
            payload = fn()
            latency_ms = round((time.time() - started) * 1000.0, 1)
            size_hint = 0
            if isinstance(payload, dict):
                data = payload.get("data")
                if isinstance(data, list):
                    size_hint = len(data)
            elif isinstance(payload, list):
                size_hint = len(payload)
            return {"name": name, "ok": True, "latency_ms": latency_ms, "error_type": "", "error": "", "size_hint": size_hint}
        except Exception as exc:
            latency_ms = round((time.time() - started) * 1000.0, 1)
            return {"name": name, "ok": False, "latency_ms": latency_ms, "error_type": exc.__class__.__name__, "error": str(exc), "size_hint": 0}

    def _maybe_run_exchange_health_check(self, force: bool = False) -> dict:
        now_ts = time.time()
        if not force and (now_ts - float(getattr(self, "exchange_last_health_check_ts", 0.0) or 0.0)) < float(getattr(self, "exchange_health_check_interval_sec", 5.0) or 5.0):
            return dict(getattr(self, "exchange_connectivity_components", {}) or {})
        probe_inst = self._exchange_probe_inst_id()
        components = {
            "public": self._probe_exchange_component("public", lambda: self.gateway.public_api.get_instruments(instType="SWAP")),
            "private": self._probe_exchange_component("private", lambda: self.gateway.account_api.get_account_balance()),
            "trade": self._probe_exchange_component("trade", lambda: self.gateway.trade_api.get_order_list(instType="SWAP", instId=probe_inst)),
            "market_data": self._probe_exchange_component("market_data", lambda: self.gateway.market_api.get_ticker(instId=probe_inst)),
        }
        ws_manager = getattr(self, "ws_manager", None)
        if ws_manager is not None and bool(getattr(self.cfg, "ws_enabled", True)):
            ws_health = dict(ws_manager.health_snapshot() or {})
            for ws_name in ("public", "private"):
                item = dict(ws_health.get(ws_name) or {})
                components[f"ws_{ws_name}"] = {
                    "name": f"ws_{ws_name}",
                    "ok": bool(item.get("ok", False)),
                    "latency_ms": 0.0,
                    "error_type": "" if bool(item.get("ok", False)) else "WsDegraded",
                    "error": str(item.get("error") or "") if not bool(item.get("ok", False)) else "",
                    "size_hint": int(item.get("messages", 0) or 0),
                }
        self.exchange_last_health_check_ts = now_ts
        self.exchange_connectivity_components = components
        state, detail = classify_connectivity_state(components)
        self.exchange_connectivity_last_error = str(detail.get("last_error", "") or "")
        self._update_exchange_connectivity_state(state, components, detail)
        return dict(components)

    def _update_exchange_connectivity_state(self, detected_state: str, components: dict, detail: dict) -> None:
        now_ts = time.time()
        prev_state = str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE")
        target_state = str(detected_state or "IDLE")
        if prev_state in {"DEGRADED", "DISCONNECTED"} and target_state == "CONNECTED":
            target_state = "RECOVERING"
            self.exchange_recovery_pending = True
        if prev_state == target_state:
            current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
            if current_minute != self.last_connectivity_summary_minute:
                summary_payload = summarize_connectivity_rows([], components=components, current_state=target_state)
                self.connectivity_logger.log("CONNECTIVITY_HEARTBEAT_SUMMARY", current_state=target_state, components=summary_payload.get("components", {}), components_down=summary_payload.get("components_down", []), last_error=self.exchange_connectivity_last_error, open_positions=len(self.position_state))
                self.last_connectivity_summary_minute = current_minute
            return
        prev_since = float(getattr(self, "exchange_connectivity_since_ts", now_ts) or now_ts)
        prev_duration = max(0.0, now_ts - prev_since)
        down = [name for name, item in (components or {}).items() if not bool(item.get("ok", False))]
        self.exchange_connectivity_state = target_state
        self.exchange_connectivity_since_ts = now_ts
        self.connectivity_logger.log("CONNECTIVITY_STATE_CHANGED", from_state=prev_state, to_state=target_state, duration_prev_state_sec=round(prev_duration, 3), components_down=down, components={k: {"ok": bool(v.get("ok", False)), "latency_ms": float(v.get("latency_ms", 0.0) or 0.0), "error_type": str(v.get("error_type", "") or "") } for k, v in (components or {}).items()}, last_error=self.exchange_connectivity_last_error)
        if target_state in {"DEGRADED", "DISCONNECTED"}:
            if not self.exchange_active_incident:
                self.exchange_active_incident = {"started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "start_state": target_state, "peak_state": target_state}
                self.connectivity_logger.log("CONNECTIVITY_INCIDENT_STARTED", started_at=self.exchange_active_incident["started_at"], start_state=target_state, components_down=down, last_error=self.exchange_connectivity_last_error)
            else:
                self.exchange_active_incident["peak_state"] = "DISCONNECTED" if target_state == "DISCONNECTED" else self.exchange_active_incident.get("peak_state", target_state)
        elif self.exchange_active_incident and target_state in {"RECOVERING", "CONNECTED"}:
            incident = dict(self.exchange_active_incident)
            ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                started_dt = datetime.strptime(str(incident.get("started_at", "")), "%Y-%m-%d %H:%M:%S")
                duration_sec = max(0.0, (datetime.now() - started_dt).total_seconds())
            except Exception:
                duration_sec = prev_duration
            self.connectivity_logger.log("CONNECTIVITY_INCIDENT_CLOSED", started_at=incident.get("started_at", ""), ended_at=ended_at, duration_sec=round(duration_sec, 3), start_state=incident.get("start_state", ""), peak_state=incident.get("peak_state", ""), recovered_to=target_state, components_down=down)
            self.exchange_active_incident = None

    def _complete_recovery_if_needed(self) -> None:
        if str(getattr(self, "exchange_connectivity_state", "")) != "RECOVERING" or not bool(getattr(self, "exchange_recovery_pending", False)):
            return
        self.sync_positions_from_exchange()
        for state in list(self.position_state.values()):
            try:
                self._run_stop_health_check(state, current_price=float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0))
            except Exception as exc:
                self.connectivity_logger.log("CONNECTIVITY_RECOVERY_STOP_CHECK_ERROR", inst_id=getattr(state, "inst_id", ""), side=getattr(state, "side", ""), error=str(exc))
        self.exchange_recovery_pending = False
        self.exchange_connectivity_state = "CONNECTED"
        self.exchange_connectivity_since_ts = time.time()
        self.connectivity_logger.log("CONNECTIVITY_RECOVERY_COMPLETED", open_positions=len(self.position_state))

    def _entries_blocked_by_connectivity(self) -> bool:
        return str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE") in {"DEGRADED", "DISCONNECTED", "RECOVERING"}

    def _extract_order_id(self, response: Optional[dict]) -> str:
        data = list((response or {}).get("data", []) or [])
        row = data[0] if data else {}
        return str(row.get("ordId") or row.get("algoId") or "")

    def _make_pending_entry(self, inst_id: str, side: str, system_name: str, qty: float, planned_entry_price: float, atr: float, stop_price: float, execution_mode: str = "market") -> PendingEntry:
        pending_id = _stable_trade_id(inst_id, f"{side}_pending", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        pending = PendingEntry(
            pending_entry_id=pending_id,
            inst_id=inst_id,
            side=side,
            strategy_tag=system_name,
            planned_qty=float(qty or 0.0),
            planned_entry_price=float(planned_entry_price or 0.0),
            execution_mode=str(execution_mode or "market"),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            expected_atr=float(atr or 0.0),
            expected_stop_price=float(stop_price or 0.0),
        )
        self.pending_entries[pending_id] = pending
        self.stats_logger.log("ENTRY_PENDING_CREATED", pending_entry_id=pending_id, inst_id=inst_id, side=side, system_name=system_name, planned_qty=qty, planned_entry_price=planned_entry_price, atr=atr, expected_stop_price=stop_price, execution_mode=execution_mode)
        return pending

    def _execution_hard_block_reason(self, inst_id: str) -> str:
        inst = str(inst_id or "").upper().strip()
        if not inst:
            return "invalid_instrument"
        if inst in set(str(x).upper() for x in (getattr(self.cfg, "blacklist", []) or [])):
            return "blacklist"
        if inst in set(str(x).upper() for x in (getattr(self, "blocked_instruments", set()) or set())):
            return "blocked_instruments"
        if is_hidden_instrument(inst):
            return "hidden_instrument"
        scanner = getattr(self, "market_scanner", None)
        if scanner is not None:
            try:
                allowed, reason, _status = scanner.allows_entry(inst)
            except Exception:
                allowed, reason = True, ""
            if not allowed:
                return str(reason or "scanner_blocked")
        return ""

    def _normalize_bootstrap_stop(self, inst_id: str, side: str, trigger_px: float, current_price: float = 0.0) -> float:
        try:
            return float(self.gateway.normalize_protective_stop(inst_id, side, trigger_px, current_price=current_price) or 0.0)
        except Exception:
            return float(trigger_px or 0.0)

    def _entry_lookback_period(self, system_name: str, side: str) -> int:
        if str(system_name or "") == "Turtle 55":
            return int(getattr(self.cfg, "long_entry_period", 55) or 55)
        if str(system_name or "") == "Turtle 20":
            return int(getattr(self.cfg, "short_entry_period", 20) or 20)
        return int(getattr(self.cfg, "long_entry_period", 55) if str(side or "") == "long" else getattr(self.cfg, "short_entry_period", 20) or 20)

    def _compute_bootstrap_stop(self, inst_id: str, side: str, system_name: str, fallback_price: float, atr: float) -> float:
        lookback = max(2, self._entry_lookback_period(system_name, side))
        buffer_pct = float(getattr(self.cfg, "bootstrap_stop_buffer_pct", 0.07) or 0.07)
        fallback = float(fallback_price or 0.0) - float(getattr(self.cfg, "atr_stop_multiple", 2.0) or 2.0) * float(atr or 0.0) if str(side or "") == "long" else float(fallback_price or 0.0) + float(getattr(self.cfg, "atr_stop_multiple", 2.0) or 2.0) * float(atr or 0.0)
        try:
            candles = list(self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback + 4) or [])
            if len(candles) < lookback:
                return float(fallback)
            window = candles[-lookback:]
            highs = [float(row[2]) for row in window]
            lows = [float(row[3]) for row in window]
            hh = max(highs)
            ll = min(lows)
            rng = max(hh - ll, 0.0)
            if rng <= 0.0:
                return float(fallback)
            buffer_abs = rng * buffer_pct
            if str(side or "") == "long":
                return float(ll - buffer_abs)
            return float(hh + buffer_abs)
        except Exception as exc:
            self._log_execution_event("bootstrap_stop_calc_failed", inst_id=inst_id, side=side, system_name=system_name, error=str(exc), fallback=fallback)
            return float(fallback)

    def _build_attached_bootstrap_stop(self, inst_id: str, trigger_px: float, current_price: float = 0.0) -> dict:
        return {
            "trigger_px": float(trigger_px or 0.0),
            "trigger_type": "mark",
            "current_price": float(current_price or 0.0),
            # OKX accepts attachAlgoClOrdId as optional.
            # In v111 using a custom attached algo client id caused order rejections
            # with sCode 51000 / "Parameter algoClOrdId error" on entry.
            # We therefore let the exchange assign the attached stop identifier here
            # and recover/link it later via stop snapshots.
            "use_custom_algo_id": False,
        }

    def _reconcile_live_fill(self, inst_id: str, side: str, fallback_price: float, fallback_qty: float) -> tuple[float, float]:
        try:
            positions = self.gateway.get_positions()
        except Exception as exc:
            self.log_line.emit(f"{inst_id}: не удалось синхронизировать live fill -> {exc}")
            return float(fallback_price or 0.0), float(fallback_qty or 0.0)
        detected_qty = float(fallback_qty or 0.0)
        detected_price = float(fallback_price or 0.0)
        for pos in positions:
            pos_inst = str(pos.get("instId") or "").strip()
            pos_side = self._detect_side_from_pos(pos)
            if pos_inst != inst_id or pos_side != side:
                continue
            try:
                qty = abs(float(pos.get("pos") or 0.0))
            except Exception:
                qty = 0.0
            try:
                avg_px = float(pos.get("avgPx") or 0.0)
            except Exception:
                avg_px = 0.0
            if qty > 0:
                detected_qty = qty
            if avg_px > 0:
                detected_price = avg_px
            break
        return detected_price, detected_qty

    def _mark_position_health(self, state: PositionState, status: str, reason: str = "") -> None:
        new_status = str(status or "HEALTHY")
        if str(getattr(state, "position_health_state", "HEALTHY")) != new_status:
            self.stats_logger.log("POSITION_HEALTH_CHANGED", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, health_state=new_status, reason=reason)
        state.position_health_state = new_status
        if reason:
            state.pyramiding_block_reason = reason

    def _update_stop_tracking(self, state: PositionState, is_active: bool, reason: str = "", verified: bool = True) -> None:
        return self.stop_engine._update_stop_tracking(state, is_active, reason=reason, verified=verified)

    def _fmt_price(self, value: float) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return str(value)

    def _notify(self, text: str) -> None:
        if TELEGRAM_HARD_DISABLED:
            return
        try:
            self.telegram.send(text)
        except Exception as exc:
            logging.warning("Telegram notify failed: %s", exc)

    def _emit_snapshot_safe(self) -> None:
        try:
            self.emit_snapshot()
        except Exception as exc:
            logging.warning("Failed to emit immediate snapshot: %s", exc)

    def _append_balance_point_from_account(self, account: dict, point_time: Optional[datetime] = None) -> None:
        data = account.get("data", []) or []
        root = data[0] if data else {}
        details = root.get("details", []) or []
        detail = details[0] if details else {}

        balance_total = self._extract_total_usdt(account)
        balance_available = self._extract_available_usdt(account)
        frozen_value = float(detail.get("frozenBal") or 0.0)
        balance_used = frozen_value if frozen_value > 0 else max(balance_total - balance_available, 0.0)

        dt = point_time or datetime.now()
        point = {
            "time": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "balance_total": float(balance_total),
            "balance_available": float(balance_available),
            "balance_used": float(balance_used),
        }

        with self.balance_lock:
            self.latest_balance_snapshot = dict(point)
            if self.balance_history and str(self.balance_history[-1].get("time", "")) == point["time"]:
                self.balance_history[-1] = point
            else:
                self.balance_history.append(point)
                self.balance_history = self.balance_history[-20000:]

    def _balance_poller_loop(self) -> None:
        interval = max(1, int(getattr(self.cfg, "balance_refresh_sec", 5) or 5))
        while self.running and self.balance_poller_running:
            try:
                account = self.gateway.get_account_balance()
                self._append_balance_point_from_account(account)
            except Exception as exc:
                logging.warning("Balance poller failed: %s", exc)
                self.log_line.emit(f"Не удалось опросить баланс: {exc}")
            slept = 0.0
            while self.running and self.balance_poller_running and slept < interval:
                time.sleep(0.2)
                slept += 0.2

    def start_balance_poller(self) -> None:
        if self.balance_poller_running:
            return
        self.balance_poller_running = True
        self.balance_poller_thread = threading.Thread(target=self._balance_poller_loop, name="BalancePoller", daemon=True)
        self.balance_poller_thread.start()
        self.log_line.emit(f"Независимый опрос баланса запущен (каждые {max(1, int(getattr(self.cfg, 'balance_refresh_sec', 5) or 5))}с)")

    def stop_balance_poller(self) -> None:
        self.balance_poller_running = False
        thread = self.balance_poller_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self.balance_poller_thread = None

    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            _migrate_previous_runtime_state_if_needed()
        if not STATE_FILE.exists():
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []
            self.latest_balance_snapshot = {}
            self.latest_balance_snapshot = {}
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                backup_path = _backup_runtime_state_file('top_level_invalid')
                raise ValueError(f'runtime state root must be dict, got {type(data).__name__}; backup={backup_path}')

            load_issues: List[str] = []
            if "positions" in data:
                restored_positions, position_issues = _restore_position_state_map(data.get("positions", {}))
                restored_closed_trades, closed_trade_issues = _restore_closed_trades(data.get("closed_trades", []))
                self.position_state = restored_positions
                self.closed_trades = restored_closed_trades
                self.balance_history = list(data.get("balance_history", []))[-20000:]
                self.latest_balance_snapshot = dict(self.balance_history[-1]) if self.balance_history else {}
                load_issues.extend(position_issues)
                load_issues.extend(closed_trade_issues)
            else:
                # backward compatibility with old file that stored only positions dict
                restored_positions, position_issues = _restore_position_state_map(data)
                self.position_state = restored_positions
                self.closed_trades = []
                self.balance_history = []
                self.latest_balance_snapshot = {}
                load_issues.extend(position_issues)

            if load_issues:
                backup_path = _backup_runtime_state_file('legacy_state_filtered')
                preview = '; '.join(load_issues[:5])
                logging.warning('State loaded with filtered legacy entries: issues=%s backup=%s preview=%s', len(load_issues), backup_path, preview)
        except Exception as exc:
            backup_path = _backup_runtime_state_file('state_load_failed')
            logging.warning("Failed to load state: %s (backup=%s)", exc, backup_path)
            self.position_state = {}
            self.closed_trades = []
            self.balance_history = []
            self.latest_balance_snapshot = {}

    def _save_state(self) -> None:
        with self.balance_lock:
            balance_history_copy = list(self.balance_history[-20000:])

        visible_open_positions = []
        for inst_id, state in self.position_state.items():
            if is_hidden_instrument(inst_id):
                continue
            last_px = _safe_float(getattr(state, 'last_px', 0.0))
            avg_px = _safe_float(getattr(state, 'avg_px', 0.0))
            atr = _safe_float(getattr(state, 'atr', 0.0))
            pnl_pct = ((last_px - avg_px) / avg_px * 100.0) if avg_px > 0 and getattr(state, 'side', '') == 'long' else 0.0
            if avg_px > 0 and getattr(state, 'side', '') == 'short':
                pnl_pct = ((avg_px - last_px) / avg_px * 100.0)
            position_age_sec = 0
            for _entry_text in (str(getattr(state, 'entry_time', '') or ''), str(getattr(state, 'signal_time', '') or '')):
                try:
                    if _entry_text:
                        entry_ts = datetime.strptime(_entry_text, '%Y-%m-%d %H:%M:%S').timestamp()
                        position_age_sec = max(0, int(time.time() - entry_ts))
                        break
                except Exception:
                    continue
            if _safe_float(getattr(state, 'next_pyramid_price', 0.0), 0.0) <= 0.0 and atr > 0 and avg_px > 0:
                units_for_restore = max(1, _safe_int(getattr(state, 'units', 1), 1))
                state.next_pyramid_price = avg_px + self.cfg.add_unit_every_atr * atr * units_for_restore if getattr(state, 'side', '') == 'long' else avg_px - self.cfg.add_unit_every_atr * atr * units_for_restore
            stop_state = str(getattr(state, 'stop_state', '') or '')
            exchange_stop_status = str(getattr(state, 'exchange_stop_status', '') or '')
            position_health_state = str(getattr(state, 'position_health_state', '') or '')
            close_pending = bool(getattr(state, 'close_pending', False))
            system_name = str(getattr(state, 'system_name', '') or '')
            peak_pnl_pct = _safe_float(getattr(state, 'peak_pnl_pct', 0.0))
            sync_status = derive_sync_status(
                stop_state=stop_state,
                exchange_stop_status=exchange_stop_status,
                position_health_state=position_health_state,
                close_pending=close_pending,
            )
            turtle_exit_period = turtle_exit_period_from_system(system_name)
            hybrid_stop_mode = determine_hybrid_stop_mode(
                system_name=system_name,
                units=_safe_int(getattr(state, 'units', 0), 0),
                pnl_pct=_safe_float(pnl_pct),
                peak_pnl_pct=peak_pnl_pct,
            )
            trend_hold_state = classify_trend_hold_state(
                hybrid_stop_mode=hybrid_stop_mode,
                units=_safe_int(getattr(state, 'units', 0), 0),
                pnl_pct=_safe_float(pnl_pct),
                peak_pnl_pct=peak_pnl_pct,
            )
            visible_open_positions.append({
                'trade_id': str(getattr(state, 'trade_id', '') or ''),
                'inst_id': str(getattr(state, 'inst_id', inst_id) or inst_id),
                'side': str(getattr(state, 'side', '') or ''),
                'last_px': last_px,
                'avg_px': avg_px,
                'stop_price': _safe_float(getattr(state, 'stop_price', 0.0)),
                'next_pyramid_price': _safe_float(getattr(state, 'next_pyramid_price', 0.0)),
                'units': _safe_int(getattr(state, 'units', 0)),
                'qty': _safe_float(getattr(state, 'qty', 0.0)),
                'unrealized_pnl': _safe_float(getattr(state, 'unrealized_pnl', 0.0)),
                'pnl_pct': _safe_float(pnl_pct),
                'peak_pnl_pct': peak_pnl_pct,
                'mae_pct': _safe_float(getattr(state, 'mae_pct', 0.0)),
                'atr': atr,
                'position_age_sec': position_age_sec,
                'system_name': system_name,
                'entry_time': str(getattr(state, 'entry_time', '') or ''),
                'entry_context_file': str(getattr(state, 'entry_context_file', '') or ''),
                'entry_period': _safe_int(getattr(state, 'entry_period', 0), 0),
                'turtle_exit_period': turtle_exit_period,
                'hybrid_stop_mode': hybrid_stop_mode,
                'trend_hold_state': trend_hold_state,
                'reconciler_interval_sec': reconciler_dynamic_sync_interval(len(self.position_state)),
                'exchange_stop_status': exchange_stop_status,
                'stop_state': stop_state,
                'position_health_state': position_health_state,
                'close_pending': close_pending,
                'sync_status': sync_status,
            })
        visible_closed_trades = [x for x in self.closed_trades if not is_hidden_instrument(getattr(x, 'inst_id', ''))]

        current_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
        if current_minute != self.last_position_snapshot_minute:
            for row in visible_open_positions:
                self.position_snapshot_logger.log(
                    'POSITION_SNAPSHOT',
                    trade_id=row.get('trade_id', ''),
                    inst_id=row.get('inst_id', ''),
                    side=row.get('side', ''),
                    price=_safe_float(row.get('last_px', 0.0)),
                    avg_entry_price=_safe_float(row.get('avg_px', 0.0)),
                    stop_price=_safe_float(row.get('stop_price', 0.0)),
                    next_unit_level=_safe_float(row.get('next_pyramid_price', 0.0)),
                    units=_safe_int(row.get('units', 0)),
                    qty_total=_safe_float(row.get('qty', 0.0)),
                    pnl_usd=_safe_float(row.get('unrealized_pnl', 0.0)),
                    pnl_pct=_safe_float(row.get('pnl_pct', 0.0)),
                    mfe_pct=_safe_float(row.get('peak_pnl_pct', 0.0)),
                    mae_pct=_safe_float(row.get('mae_pct', 0.0)),
                    atr=_safe_float(row.get('atr', 0.0)),
                    position_age_sec=_safe_int(row.get('position_age_sec', 0)),
                    note='Минутный snapshot позиции',
                )
            self.last_position_snapshot_minute = current_minute
        if current_minute != self.last_system_health_minute:
            cache_stats = self.market_data_cache.snapshot_stats() if getattr(self, 'market_data_cache', None) else {}
            self.system_health_logger.log(
                'SYSTEM_HEALTH',
                open_positions=len(visible_open_positions),
                closed_trades=len(visible_closed_trades),
                loop_duration_sec=_safe_float(getattr(self, 'last_cycle_duration_sec', 0.0)),
                symbols_scanned=_safe_int(getattr(self, 'last_scan_universe_total', len(getattr(self.gateway, 'swap_ids', []) or []))),
                signals_found=_safe_int((getattr(self, 'last_signal_funnel', {}) or {}).get('candidates', 0)),
                signals_blocked=_safe_int((getattr(self, 'last_signal_funnel', {}) or {}).get('rejected', 0)),
                cache_errors=_safe_int((cache_stats or {}).get('error_count', 0)),
                cache_fetch_count=_safe_int((cache_stats or {}).get('fetch_count', 0)),
                available_after_bans=_safe_int(len([inst for inst in getattr(self.gateway, 'swap_ids', []) if inst not in self.blocked_instruments and not is_hidden_instrument(inst)])),
                connectivity_state=str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE"),
                connectivity_components_down=[name for name, item in (getattr(self, "exchange_connectivity_components", {}) or {}).items() if not bool(item.get("ok", False))],
            )
            self.last_system_health_minute = current_minute

        payload = {
            "positions": {k: asdict(v) for k, v in self.position_state.items()},
            "closed_trades": [asdict(x) for x in self.closed_trades[-500:]],
            "balance_history": balance_history_copy,
        }
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._stop_requested = False
        self._shutdown_finalized = False
        self.stats_logger.log(
            "bot_started",
            version=APP_VERSION,
            account=("main" if self.cfg.flag == "0" else "demo"),
            timeframe=self.cfg.timeframe,
            scan_interval_sec=self.cfg.scan_interval_sec,
            position_check_interval_sec=self.cfg.position_check_interval_sec,
            snapshot_interval_sec=self.cfg.snapshot_interval_sec,
            risk_per_trade_pct=self.cfg.risk_per_trade_pct,
            max_position_notional_pct=self.cfg.max_position_notional_pct,
            max_units_per_symbol=self.cfg.max_units_per_symbol,
            pyramid_scales=[
                1.0,
                self.cfg.pyramid_second_unit_scale,
                self.cfg.pyramid_third_unit_scale,
                self.cfg.pyramid_fourth_unit_scale,
            ],
            breakout_mode="classic_turtle",
            structure_filter_enabled=False,
            max_open_positions_total=self.cfg.max_open_positions_total,
            max_open_positions_per_side=self.cfg.max_open_positions_per_side,
            liquidity_filter_enabled=bool(getattr(self.cfg, "liquidity_filter_enabled", True)),
            blacklist=list(self.cfg.blacklist),
        )
        self.position_journal_logger.log("session_start", version=APP_VERSION, timeframe=self.cfg.timeframe, account=("main" if self.cfg.flag == "0" else "demo"))
        self.market_data_cache.start()
        try:
            if bool(getattr(self.cfg, "ws_enabled", True)):
                self.ws_manager.start(self.gateway.swap_ids)
        except Exception as exc:
            logging.exception("Failed to start OKX WS manager")
            self.log_line.emit(f"[WS] старт не удался: {exc}")
        self.start_balance_poller()
        self.status.emit("Бот запущен")
        tf_profile = self._timeframe_filter_profile()
        self.log_line.emit(f"Торговый движок запущен (шаг: {self.cfg.timeframe}, режим: {self.cfg.trade_mode})")
        self.log_line.emit(
            "Профиль фильтров: {label} | ATR>={atr:.3f}% | RANGE>={rng:.3f}% | CH/ATR>={car:.2f} | TREND>={trend:.2f} ATR | BUF={buf:.3f} ATR".format(
                label=tf_profile.get("label", self.cfg.timeframe),
                atr=float(tf_profile.get("min_atr_pct", 0.0)),
                rng=float(tf_profile.get("min_channel_range_pct", 0.0)),
                car=float(tf_profile.get("flat_min_channel_atr_ratio", 0.0)),
                trend=float(tf_profile.get("trend_slope_atr_min", 0.0)),
                buf=float(tf_profile.get("breakout_buffer_atr", 0.0)),
            )
        )
        self._notify("✅ OKX Turtle Bot запущен")
        self.run_loop()

    def stop(self) -> None:
        self.request_stop()
        self.finalize_stop()
        self._notify("⛔ OKX Turtle Bot остановлен")

    def _current_utc_minute_key(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    def _position_cycle_progress_text(self) -> str:
        total = int(getattr(self, "position_cycle_total", 0) or 0)
        done = int(getattr(self, "position_cycle_done", 0) or 0)
        if total <= 0:
            return "0/0"
        return f"{min(done, total)}/{total}"

    def _update_popup_snapshot(self, state: PositionState, candles: Optional[List[List[float]]] = None, reason: str = "") -> None:
        context_file = str(getattr(state, 'entry_context_file', '') or '').strip()
        if not context_file:
            return
        try:
            payload = self._load_json_file(context_file)
            if not payload:
                return
            if candles is None:
                limit = max(80, int(max(getattr(state, 'entry_period', 20) or 20, getattr(state, 'exit_period', 10) or 10)) + 24)
                candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, limit) or []
            if candles:
                payload['candles'] = list(candles)
                latest_closed_ts = int(candles[-2][0]) if len(candles) >= 2 else int(candles[-1][0])
                if latest_closed_ts > 0:
                    payload['last_closed_candle_ts'] = latest_closed_ts
            payload['saved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload['version'] = APP_VERSION
            payload['timeframe'] = self.cfg.timeframe
            payload['inst_id'] = state.inst_id
            payload['side'] = state.side
            payload['entry_price'] = float(getattr(state, 'avg_px', 0.0) or payload.get('entry_price') or 0.0)
            payload['stop_price'] = float(getattr(state, 'stop_price', 0.0) or payload.get('stop_price') or 0.0)
            payload['next_pyramid_price'] = float(getattr(state, 'next_pyramid_price', 0.0) or 0.0)
            payload['atr'] = float(getattr(state, 'atr', 0.0) or payload.get('atr') or 0.0)
            payload['units'] = int(getattr(state, 'units', 0) or 0)
            payload['qty'] = float(getattr(state, 'qty', 0.0) or 0.0)
            payload['system_name'] = str(getattr(state, 'system_name', '') or payload.get('system_name') or '')
            payload['popup_snapshot_reason'] = str(reason or '')
            markers = []
            entry_price = float(payload.get('entry_price') or getattr(state, 'avg_px', 0.0) or 0.0)
            if candles and entry_price > 0.0:
                entry_time_text = str(getattr(state, 'entry_time', '') or payload.get('saved_at') or '')
                entry_ts_ms = 0
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        entry_ts_ms = int(datetime.strptime(entry_time_text, fmt).timestamp() * 1000)
                        break
                    except Exception:
                        continue
                candle_times = [int(c[0]) for c in candles if c]
                if candle_times:
                    marker_index = 0
                    if entry_ts_ms > 0:
                        marker_index = min(range(len(candle_times)), key=lambda i: abs(candle_times[i] - entry_ts_ms))
                    markers.append({'kind': 'entry', 'label': 'E', 'index': int(marker_index), 'price': entry_price, 'time': entry_time_text})
                    trade_id = str(getattr(state, 'trade_id', '') or '')
                    if trade_id and POSITION_JOURNAL_FILE.exists():
                        journal_rows = _read_jsonl_rows(POSITION_JOURNAL_FILE)
                        add_rows = [r for r in journal_rows if str(r.get('trade_id') or '').strip() == trade_id and str(r.get('event') or '').upper() in {'ADD_UNIT', 'PYRAMID_ADD', 'UNIT_ADD'}]
                        for idx, add_row in enumerate(add_rows, start=2):
                            event_ts = str(add_row.get('ts') or '').strip()
                            ts_match = 0
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                                try:
                                    ts_match = int(datetime.strptime(event_ts, fmt).timestamp() * 1000)
                                    break
                                except Exception:
                                    continue
                            add_idx = len(candle_times) - 1
                            if ts_match > 0:
                                add_idx = min(range(len(candle_times)), key=lambda i: abs(candle_times[i] - ts_match))
                            markers.append({'kind': f'add{idx}', 'label': f'A{idx}', 'index': int(add_idx), 'price': float(add_row.get('price') or add_row.get('avg_px') or add_row.get('last_price') or 0.0), 'time': event_ts})
            payload['markers'] = markers
            Path(context_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            logging.warning("Failed to refresh popup snapshot for %s: %s", getattr(state, 'inst_id', ''), exc)

    def _manage_single_position(self, state: PositionState) -> None:
        retry_after = self.close_retry_after.get(state.inst_id, 0.0)
        if retry_after and retry_after > time.time():
            return
        candles = []
        latest_closed_ts = 0
        try:
            candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 8) or []
            if len(candles) >= 2:
                latest_closed_ts = int(candles[-2][0])
            elif candles:
                latest_closed_ts = int(candles[-1][0])
        except Exception as exc:
            logging.warning("Candle refresh failed for %s: %s", state.inst_id, exc)
        last_popup_ts = int(getattr(state, 'popup_snapshot_last_candle_ts', 0) or 0)
        new_closed_candle = latest_closed_ts > 0 and latest_closed_ts > last_popup_ts
        if new_closed_candle:
            self._update_popup_snapshot(state, candles=candles, reason='closed_candle_pre_manage')
            state.popup_snapshot_last_candle_ts = latest_closed_ts
        try:
            self.update_and_maybe_exit_or_pyramid(state)
        except Exception as exc:
            self.log_line.emit(f"{state.inst_id}: ошибка управления позицией: {exc}")
            logging.warning("Manage failed for %s: %s", state.inst_id, exc)
            return
        if new_closed_candle or bool(getattr(state, 'popup_snapshot_dirty', False)):
            self._update_popup_snapshot(state, candles=candles or None, reason='post_manage_refresh')
            state.popup_snapshot_dirty = False

    def manage_open_positions(self) -> None:
        self.stats_logger.log("positions_check_started", tracked_positions=len(self.position_state))
        items = list(self.position_state.items())
        self.position_cycle_total = len(items)
        self.position_cycle_done = 0
        for inst_id, state in items:
            if not self.running or self._stop_requested:
                break
            self.position_cycle_done += 1
            self._manage_single_position(state)

    def _run_position_management_cycle(self, minute_key: str) -> None:
        if self.position_cycle_active:
            return
        cycle_started_at = time.time()
        self.position_cycle_active = True
        self.position_cycle_scanner_paused = True
        self.position_cycle_started_at = cycle_started_at
        self.position_cycle_last_error = ""
        self.position_cycle_last_minute_key = str(minute_key or self._current_utc_minute_key())
        self.position_cycle_done = 0
        self.position_cycle_total = len(self.position_state)
        try:
            self.last_scan_started_at = cycle_started_at
            self.last_positions_check_at = cycle_started_at
            self.sync_positions_from_exchange()
            self.position_cycle_total = len(self.position_state)
            self.manage_open_positions()
        except Exception as exc:
            self.position_cycle_last_error = str(exc)
            raise
        finally:
            self.position_cycle_active = False
            self.position_cycle_scanner_paused = False
            self.position_cycle_finished_at = time.time()
            self.position_cycle_last_duration_sec = max(0.0, self.position_cycle_finished_at - cycle_started_at)
            self.position_cycle_last_completed_utc = datetime.utcnow().strftime("%H:%M:%S UTC")

    def run_loop(self) -> None:
        self.last_entry_scan_at = 0.0
        while self.running and not self._stop_requested:
            cycle_started_at = time.time()
            try:
                self._maybe_run_exchange_health_check(force=True)
                self._complete_recovery_if_needed()
                minute_key = self._current_utc_minute_key()
                if minute_key != str(getattr(self, 'position_cycle_last_minute_key', '') or ''):
                    log_heartbeat("engine", "position_cycle_started", open_positions=len(self.position_state), timeframe=self.cfg.timeframe, utc_minute=minute_key)
                    self.stats_logger.log("position_cycle_started", open_positions=len(self.position_state), timeframe=self.cfg.timeframe, utc_minute=minute_key)
                    self._run_position_management_cycle(minute_key)
                    self.emit_snapshot()
                    self.last_scan_finished_at = time.time()
                    log_heartbeat("engine", "position_cycle_finished", duration_sec=round(self.position_cycle_last_duration_sec, 3), open_positions=len(self.position_state), utc_minute=minute_key)
                    self.stats_logger.log("position_cycle_finished", duration_sec=round(self.position_cycle_last_duration_sec, 3), open_positions=len(self.position_state), closed_trades=len(self.closed_trades), utc_minute=minute_key)
                now_ts = time.time()
                if not self.position_cycle_active and (now_ts - float(getattr(self, 'last_entry_scan_at', 0.0) or 0.0)) >= max(1.0, float(getattr(self.cfg, 'scan_interval_sec', 15) or 15)):
                    self.scan_markets()
                    self.last_entry_scan_at = now_ts
                    self.emit_snapshot()
            except Exception as exc:
                msg = f"Ошибка в цикле стратегии: {exc}"
                logging.exception(msg)
                self.stats_logger.log("cycle_error", error=str(exc))
                log_heartbeat("engine", "cycle_error", error=str(exc))
                self.error.emit(msg)
                self.log_line.emit(msg)
                self._notify(f"⚠️ Ошибка в цикле стратегии\n\n{msg}")
            self.last_cycle_duration_sec = time.time() - cycle_started_at
            self._interruptible_sleep(1.0)
        self.finalize_stop()

    def sync_positions_from_exchange(self) -> None:
        exchange_positions = self.gateway.get_positions()
        seen = set()
        changed = False
        for pos in exchange_positions:
            inst_id = pos.get("instId")
            pos_side = self._detect_side_from_pos(pos)
            if not inst_id or pos_side not in {"long", "short"}:
                continue
            if is_hidden_instrument(inst_id):
                continue
            seen.add(inst_id)
            qty = abs(float(pos.get("pos") or 0.0))
            if qty <= 0:
                continue
            avg_px = float(pos.get("avgPx") or 0.0)
            last_px = float(pos.get("markPx") or pos.get("last") or avg_px)
            upl = float(pos.get("upl") or 0.0)
            margin = float(pos.get("margin") or 0.0)
            current = self.position_state.get(inst_id)
            if current:
                current.qty = qty
                current.avg_px = avg_px
                current.last_px = last_px
                current.unrealized_pnl = upl
                current.margin = margin
                if float(getattr(current, "initial_stop_price", 0.0) or 0.0) <= 0.0 and float(getattr(current, "stop_price", 0.0) or 0.0) > 0.0:
                    current.initial_stop_price = float(current.stop_price)
                if float(getattr(current, "peak_price", 0.0) or 0.0) <= 0.0:
                    current.peak_price = max(last_px, avg_px)
                if float(getattr(current, "trough_price", 0.0) or 0.0) <= 0.0:
                    current.trough_price = min(last_px, avg_px)
                atr = float(getattr(current, "atr", 0.0) or 0.0)
                if atr <= 0:
                    atr = self.compute_atr(inst_id)
                exchange_entry_dt = parse_exchange_ts_ms(pos.get("cTime") or pos.get("uTime") or pos.get("pTime"))
                if exchange_entry_dt is not None:
                    current_entry_time = str(getattr(current, "entry_time", "") or "").strip()
                    if not current_entry_time:
                        current.entry_time = exchange_entry_dt.strftime("%Y-%m-%d %H:%M:%S")
                        changed = True
                if self._reset_missing_exchange_tracking(current):
                    changed = True
                restored_fields = restore_sync_position_state(current, self.cfg, inst_id, pos_side, avg_px, last_px, qty, atr, journal_file=POSITION_JOURNAL_FILE)
                if restored_fields:
                    changed = True
                    if not bool(getattr(current, "_sync_bootstrap_logged", False)):
                        self.position_journal_logger.log(
                            "SYNC_BOOTSTRAP",
                            trade_id=str(getattr(current, "trade_id", "") or ""),
                            inst_id=inst_id,
                            side=pos_side,
                            system_name=str(getattr(current, "system_name", "") or ""),
                            units=int(getattr(current, "units", 1) or 1),
                            stop_restored=bool("stop_price" in restored_fields or "stop_state" in restored_fields),
                            pyramid_restored=bool("next_pyramid_price" in restored_fields),
                            restored_fields=",".join(restored_fields),
                            note="Sync position bootstrap refresh",
                        )
                        setattr(current, "_sync_bootstrap_logged", True)
            else:
                changed = True
                atr = self.compute_atr(inst_id)
                stop_price = avg_px - self.cfg.atr_stop_multiple * atr if pos_side == "long" else avg_px + self.cfg.atr_stop_multiple * atr
                next_pyramid = avg_px + self.cfg.add_unit_every_atr * atr if pos_side == "long" else avg_px - self.cfg.add_unit_every_atr * atr
                exchange_entry_dt = parse_exchange_ts_ms(pos.get("cTime") or pos.get("uTime") or pos.get("pTime"))
                sync_entry_time = (exchange_entry_dt.strftime("%Y-%m-%d %H:%M:%S") if exchange_entry_dt is not None else datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                self.position_state[inst_id] = PositionState(
                    inst_id=inst_id,
                    side=pos_side,
                    qty=qty,
                    avg_px=avg_px,
                    last_px=last_px,
                    unrealized_pnl=upl,
                    margin=margin,
                    atr=atr,
                    stop_price=stop_price,
                    next_pyramid_price=next_pyramid,
                    entry_time=sync_entry_time,
                    signal_time=sync_entry_time,
                    system_name="sync",
                    entry_period=self.cfg.long_entry_period if pos_side == "long" else self.cfg.short_entry_period,
                    exit_period=self.cfg.long_exit_period if pos_side == "long" else self.cfg.short_exit_period,
                    initial_stop_price=stop_price,
                    peak_price=max(last_px, avg_px),
                    trough_price=min(last_px, avg_px),
                    peak_unrealized_pnl=max(upl, 0.0),
                    peak_pnl_pct=0.0,
                    trade_id=_stable_trade_id(inst_id, pos_side, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                restored_fields = restore_sync_position_state(self.position_state[inst_id], self.cfg, inst_id, pos_side, avg_px, last_px, qty, atr, journal_file=POSITION_JOURNAL_FILE)
                setattr(self.position_state[inst_id], "_sync_bootstrap_logged", True)
                self.position_journal_logger.log(
                    "SYNC_BOOTSTRAP",
                    trade_id=str(getattr(self.position_state[inst_id], "trade_id", "") or ""),
                    inst_id=inst_id,
                    side=pos_side,
                    system_name=str(getattr(self.position_state[inst_id], "system_name", "") or ""),
                    units=int(getattr(self.position_state[inst_id], "units", 1) or 1),
                    stop_restored=True,
                    pyramid_restored=True,
                    restored_fields=",".join(restored_fields),
                    note="Sync position bootstrap created",
                )
        removed = []
        for inst_id in list(self.position_state):
            if inst_id not in seen:
                prev_state = self.position_state.get(inst_id)
                if prev_state is None:
                    continue
                missing_count, missing_reason, missing_price = self._mark_position_missing_on_exchange(prev_state)
                close_pending = bool(getattr(prev_state, "close_pending", False))
                protective_pending = bool(getattr(prev_state, "local_protective_exit_pending", False))
                stop_state = str(getattr(prev_state, "stop_state", "") or "").upper()
                health_state = str(getattr(prev_state, "position_health_state", "") or "").upper()
                absence_synced = bool(getattr(prev_state, "position_absence_synced", False))
                should_finalize = absence_synced or close_pending or protective_pending or missing_count >= 2 or stop_state in {"ERROR", "MISSING"} or health_state in {"STOP_UNVERIFIED", "ERROR"}
                if should_finalize:
                    removed.append(inst_id)
                    self._finalize_closed_trade(prev_state, missing_price, missing_reason)
                changed = True
        self._save_state()
        self.stats_logger.log(
            "positions_synced",
            exchange_positions=len(exchange_positions),
            tracked_positions=len(self.position_state),
            removed_positions=removed,
        )

    def _detect_side_from_pos(self, pos: dict) -> Optional[str]:
        pos_value = float(pos.get("pos") or 0.0)
        if pos_value > 0:
            return "long"
        if pos_value < 0:
            return "short"
        side = (pos.get("posSide") or "").lower()
        if side in {"long", "short"}:
            return side
        return None

    def _timeframe_seconds(self) -> int:
        tf = str(self.cfg.timeframe or "").strip().lower()
        mapping = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "12h": 43200,
            "1d": 86400,
        }
        return mapping.get(tf, 900)

    def _minimal_turtle_entry_mode(self) -> bool:
        return bool(getattr(self.cfg, "minimal_turtle_entry_mode", True))

    def _stopout_cooldown_seconds(self) -> int:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            bars = max(6, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 900:
            bars = max(5, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 3600:
            bars = max(4, int(self.cfg.cooldown_after_stop_bars) - 1)
        else:
            bars = max(3, int(self.cfg.cooldown_after_stop_bars) - 2)

        raw = tf_sec * bars
        raw = max(int(self.cfg.cooldown_min_seconds), raw)
        raw = min(int(self.cfg.cooldown_max_seconds), raw)
        return raw

    def _tf_entry_profile(self) -> dict:
        tf = str(self.cfg.timeframe or "5m").strip().lower()
        base = {
            "strict_min": 1.00,
            "strict_max": 1.00,
            "lookback_bonus": 1.00,
            "label": str(self.cfg.timeframe),
            "liquidity": {
                "max_spread_pct": float(self.cfg.liquidity_max_spread_pct),
                "min_top_book_usdt": float(self.cfg.liquidity_min_top_of_book_usdt),
                "min_side_notional_usdt": float(self.cfg.liquidity_min_side_notional_usdt),
                "min_24h_quote_volume": float(self.cfg.liquidity_min_24h_quote_volume),
                "max_last_mid_deviation_ratio": 0.0045,
                "soft_side_ratio": 0.45,
            },
        }

        profiles = {
            "1m": {
                "label": "1m",
                "strict_min": 0.72,
                "strict_max": 1.10,
                "lookback_bonus": 1.06,
                "liquidity": {
                    "max_spread_pct": 0.60,
                    "min_top_book_usdt": 90.0,
                    "min_side_notional_usdt": 220.0,
                    "min_24h_quote_volume": 180000.0,
                    "max_last_mid_deviation_ratio": 0.0080,
                    "soft_side_ratio": 0.32,
                },
            },
            "5m": {
                "label": "5m",
                "strict_min": 0.88,
                "strict_max": 1.04,
                "lookback_bonus": 1.10,
                "liquidity": {
                    "max_spread_pct": 0.22,
                    "min_top_book_usdt": 500.0,
                    "min_side_notional_usdt": 1200.0,
                    "min_24h_quote_volume": 1500000.0,
                    "max_last_mid_deviation_ratio": 0.0048,
                    "soft_side_ratio": 0.55,
                },
            },
            "15m": {
                "label": "15m",
                "strict_min": 1.00,
                "strict_max": 1.00,
                "lookback_bonus": 1.00,
                "liquidity": {
                    "max_spread_pct": 0.20,
                    "min_top_book_usdt": 1200.0,
                    "min_side_notional_usdt": 2500.0,
                    "min_24h_quote_volume": 2500000.0,
                    "max_last_mid_deviation_ratio": 0.0045,
                    "soft_side_ratio": 0.45,
                },
            },
            "30m": {
                "label": "30m",
                "strict_min": 1.08,
                "strict_max": 0.96,
                "lookback_bonus": 0.96,
                "liquidity": {
                    "max_spread_pct": 0.17,
                    "min_top_book_usdt": 1800.0,
                    "min_side_notional_usdt": 3800.0,
                    "min_24h_quote_volume": 4200000.0,
                    "max_last_mid_deviation_ratio": 0.0039,
                    "soft_side_ratio": 0.47,
                },
            },
            "1h": {
                "label": "1H",
                "strict_min": 1.18,
                "strict_max": 0.92,
                "lookback_bonus": 0.92,
                "liquidity": {
                    "max_spread_pct": 0.14,
                    "min_top_book_usdt": 2500.0,
                    "min_side_notional_usdt": 5500.0,
                    "min_24h_quote_volume": 6500000.0,
                    "max_last_mid_deviation_ratio": 0.0035,
                    "soft_side_ratio": 0.48,
                },
            },
            "4h": {
                "label": "4H",
                "strict_min": 1.30,
                "strict_max": 0.88,
                "lookback_bonus": 0.88,
                "liquidity": {
                    "max_spread_pct": 0.12,
                    "min_top_book_usdt": 3200.0,
                    "min_side_notional_usdt": 7000.0,
                    "min_24h_quote_volume": 9000000.0,
                    "max_last_mid_deviation_ratio": 0.0030,
                    "soft_side_ratio": 0.50,
                },
            },
        }
        return {**base, **profiles.get(tf, profiles["5m"])}

    def _timeframe_filter_profile(self) -> dict:
        tf = str(self.cfg.timeframe or "5m").strip().lower()
        profiles = {
            "1m": {
                "label": "1m",
                "min_channel_range_pct": 0.10,
                "min_atr_pct": 0.028,
                "flat_min_channel_atr_ratio": 0.90,
                "min_efficiency_ratio": 0.045,
                "max_direction_flip_ratio": 0.96,
                "flat_max_wick_to_range_ratio": 0.94,
                "trend_slope_atr_min": 0.045,
                "breakout_buffer_atr": 0.055,
                "breakout_min_body_atr": 0.12,
                "min_body_to_range_ratio": 0.16,
                "breakout_close_near_extreme_ratio": 0.16,
                "breakout_max_prebreak_distance_atr": 0.70,
                "breakout_max_distance_atr": 0.80,
                "preferred_breakout_distance_atr_min": 0.02,
                "preferred_breakout_distance_atr_max": 0.35,
                "quality_atr_good_min": 0.05,
                "quality_atr_good_max": 0.20,
                "quality_atr_ok_max": 0.35,
                "quality_channel_good_min": 1.10,
                "quality_channel_good_max": 4.20,
                "quality_channel_ok_max": 6.50,
                "quality_slope_bonus_from": 0.10,
            },
            "5m": {
                "label": "5m",
                "min_channel_range_pct": 0.22,
                "min_atr_pct": 0.055,
                "flat_min_channel_atr_ratio": 1.10,
                "min_efficiency_ratio": 0.075,
                "max_direction_flip_ratio": 0.88,
                "flat_max_wick_to_range_ratio": 0.90,
                "trend_slope_atr_min": 0.08,
                "breakout_buffer_atr": 0.08,
                "breakout_min_body_atr": 0.16,
                "min_body_to_range_ratio": 0.20,
                "breakout_close_near_extreme_ratio": 0.22,
                "breakout_max_prebreak_distance_atr": 0.55,
                "breakout_max_distance_atr": 0.62,
                "preferred_breakout_distance_atr_min": 0.04,
                "preferred_breakout_distance_atr_max": 0.30,
                "quality_atr_good_min": 0.10,
                "quality_atr_good_max": 0.32,
                "quality_atr_ok_max": 0.55,
                "quality_channel_good_min": 1.40,
                "quality_channel_good_max": 4.50,
                "quality_channel_ok_max": 7.00,
                "quality_slope_bonus_from": 0.16,
            },
            "15m": {
                "label": "15m",
                "min_channel_range_pct": 0.35,
                "min_atr_pct": 0.075,
                "flat_min_channel_atr_ratio": 1.25,
                "min_efficiency_ratio": 0.10,
                "max_direction_flip_ratio": 0.84,
                "flat_max_wick_to_range_ratio": 0.88,
                "trend_slope_atr_min": 0.10,
                "breakout_buffer_atr": 0.10,
                "breakout_min_body_atr": 0.20,
                "min_body_to_range_ratio": 0.22,
                "breakout_close_near_extreme_ratio": 0.25,
                "breakout_max_prebreak_distance_atr": 0.45,
                "breakout_max_distance_atr": 0.50,
                "preferred_breakout_distance_atr_min": 0.05,
                "preferred_breakout_distance_atr_max": 0.30,
                "quality_atr_good_min": 0.16,
                "quality_atr_good_max": 0.45,
                "quality_atr_ok_max": 0.80,
                "quality_channel_good_min": 1.60,
                "quality_channel_good_max": 4.50,
                "quality_channel_ok_max": 7.50,
                "quality_slope_bonus_from": 0.18,
            },
            "30m": {
                "label": "30m",
                "min_channel_range_pct": 0.50,
                "min_atr_pct": 0.090,
                "flat_min_channel_atr_ratio": 1.35,
                "min_efficiency_ratio": 0.11,
                "max_direction_flip_ratio": 0.82,
                "flat_max_wick_to_range_ratio": 0.86,
                "trend_slope_atr_min": 0.115,
                "breakout_buffer_atr": 0.12,
                "breakout_min_body_atr": 0.22,
                "min_body_to_range_ratio": 0.24,
                "breakout_close_near_extreme_ratio": 0.28,
                "breakout_max_prebreak_distance_atr": 0.42,
                "breakout_max_distance_atr": 0.46,
                "preferred_breakout_distance_atr_min": 0.06,
                "preferred_breakout_distance_atr_max": 0.28,
                "quality_atr_good_min": 0.20,
                "quality_atr_good_max": 0.60,
                "quality_atr_ok_max": 1.00,
                "quality_channel_good_min": 1.80,
                "quality_channel_good_max": 5.00,
                "quality_channel_ok_max": 8.00,
                "quality_slope_bonus_from": 0.20,
            },
            "1h": {
                "label": "1H",
                "min_channel_range_pct": 0.80,
                "min_atr_pct": 0.120,
                "flat_min_channel_atr_ratio": 1.55,
                "min_efficiency_ratio": 0.12,
                "max_direction_flip_ratio": 0.80,
                "flat_max_wick_to_range_ratio": 0.84,
                "trend_slope_atr_min": 0.13,
                "breakout_buffer_atr": 0.14,
                "breakout_min_body_atr": 0.24,
                "min_body_to_range_ratio": 0.26,
                "breakout_close_near_extreme_ratio": 0.30,
                "breakout_max_prebreak_distance_atr": 0.38,
                "breakout_max_distance_atr": 0.42,
                "preferred_breakout_distance_atr_min": 0.08,
                "preferred_breakout_distance_atr_max": 0.26,
                "quality_atr_good_min": 0.24,
                "quality_atr_good_max": 0.80,
                "quality_atr_ok_max": 1.20,
                "quality_channel_good_min": 2.00,
                "quality_channel_good_max": 5.50,
                "quality_channel_ok_max": 8.50,
                "quality_slope_bonus_from": 0.24,
            },
            "4h": {
                "label": "4H",
                "min_channel_range_pct": 1.30,
                "min_atr_pct": 0.180,
                "flat_min_channel_atr_ratio": 1.80,
                "min_efficiency_ratio": 0.14,
                "max_direction_flip_ratio": 0.78,
                "flat_max_wick_to_range_ratio": 0.82,
                "trend_slope_atr_min": 0.16,
                "breakout_buffer_atr": 0.18,
                "breakout_min_body_atr": 0.28,
                "min_body_to_range_ratio": 0.28,
                "breakout_close_near_extreme_ratio": 0.33,
                "breakout_max_prebreak_distance_atr": 0.34,
                "breakout_max_distance_atr": 0.38,
                "preferred_breakout_distance_atr_min": 0.10,
                "preferred_breakout_distance_atr_max": 0.24,
                "quality_atr_good_min": 0.30,
                "quality_atr_good_max": 1.20,
                "quality_atr_ok_max": 1.80,
                "quality_channel_good_min": 2.20,
                "quality_channel_good_max": 6.00,
                "quality_channel_ok_max": 9.00,
                "quality_slope_bonus_from": 0.28,
            },
        }
        profile = profiles.get(tf, profiles["5m"]).copy()
        profile["timeframe"] = str(self.cfg.timeframe)
        return profile


    def _clear_expired_runtime_blocks(self) -> None:
        now_ts = time.time()
        for mapping in (self.temp_blocked_until, self.illiquid_instruments, self.recent_rotation_exits):
            for inst_id, until_ts in list(mapping.items()):
                try:
                    if float(until_ts or 0.0) <= now_ts:
                        mapping.pop(inst_id, None)
                except Exception:
                    mapping.pop(inst_id, None)

    def _is_temporarily_blocked(self, inst_id: str) -> tuple[bool, str]:
        until_ts = float(self.temp_blocked_until.get(inst_id, 0.0) or 0.0)
        if until_ts <= 0:
            return False, ""
        now_ts = time.time()
        if until_ts <= now_ts:
            self.temp_blocked_until.pop(inst_id, None)
            return False, ""
        ttl = max(1, int(until_ts - now_ts))
        return True, f"temporary_quarantine_{ttl}s"

    def _register_execution_risk(self, inst_id: str, reason: str, stage: str = "runtime", severity: float = 1.0, quarantine: bool = False) -> None:
        now_ts = time.time()
        item = dict(self.execution_risk_events.get(inst_id, {}))
        repeats = int(item.get("count", 0)) + 1
        score = float(item.get("score", 0.0) or 0.0) + float(severity or 0.0)
        status, health_score = self.instrument_health.register_event(inst_id, stage=stage, reason=reason, severity=float(severity or 0.0), force_quarantine=bool(quarantine), now_ts=now_ts)
        item.update({
            "count": repeats,
            "score": round(score, 3),
            "last_reason": str(reason or ""),
            "last_stage": str(stage or "runtime"),
            "last_ts": now_ts,
            "status": status,
            "health_score": health_score,
        })
        self.execution_risk_events[inst_id] = item
        state = self.position_state.get(inst_id)
        if state is not None:
            state.execution_risk_score = score
        should_quarantine = quarantine or status == "QUARANTINE" or repeats >= max(1, int(getattr(self.cfg, "execution_issue_repeats_for_quarantine", 2) or 2))
        if should_quarantine:
            hours = max(1, int(getattr(self.cfg, "execution_quarantine_hours", 6) or 6))
            until_ts = now_ts + hours * 3600
            self.temp_blocked_until[inst_id] = max(float(self.temp_blocked_until.get(inst_id, 0.0) or 0.0), until_ts)
            self.stats_logger.log(
                "execution_risk_quarantine",
                inst_id=inst_id,
                stage=stage,
                reason=reason,
                risk_score=round(score, 3),
                repeats=repeats,
                quarantine_hours=hours,
                health_status=status,
                health_score=health_score,
            )

    def _exchange_position_is_open(self, inst_id: str) -> bool:
        try:
            for pos in self.gateway.get_positions():
                if str(pos.get("instId") or "") != str(inst_id):
                    continue
                try:
                    if abs(float(pos.get("pos") or 0.0)) > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            return True
        return False

    def _block_illiquid_instrument(self, inst_id: str, reason: str) -> None:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            hours = 1
        elif tf_sec <= 900:
            hours = max(1, int(self.cfg.illiquid_block_hours))
        elif tf_sec <= 3600:
            hours = max(1, int(self.cfg.illiquid_block_hours) // 2 or 1)
        else:
            hours = 1

        until_ts = time.time() + hours * 3600
        self.illiquid_instruments[inst_id] = until_ts

        if inst_id not in self.temp_blocked_until or self.temp_blocked_until.get(inst_id, 0.0) < until_ts:
            self.temp_blocked_until[inst_id] = until_ts

        logging.info("%s: инструмент временно заблокирован как неликвидный на %sч (%s)", inst_id, hours, reason)

    def _register_illiquid_rejection(self, inst_id: str, reason: str) -> tuple[bool, str]:
        now_ts = time.time()
        data = self.illiquid_rejections.get(inst_id, {"count": 0, "last_reason": "", "last_ts": 0.0})

        gap_limit = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        if now_ts - float(data.get("last_ts", 0.0)) > gap_limit * 3:
            data["count"] = 0

        data["count"] = int(data.get("count", 0)) + 1
        data["last_reason"] = reason
        data["last_ts"] = now_ts
        self.illiquid_rejections[inst_id] = data

        repeats_for_ban = max(2, int(self.cfg.illiquid_repeats_for_ban))
        tf_sec = self._timeframe_seconds()

        effective_repeats = repeats_for_ban
        if tf_sec >= 3600:
            effective_repeats += 1

        if data["count"] >= effective_repeats:
            return True, f"{reason}; повторов={data['count']}"

        soft_cd = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        self.temp_blocked_until[inst_id] = max(self.temp_blocked_until.get(inst_id, 0.0), now_ts + soft_cd)
        return False, f"{reason}; мягкий пропуск {data['count']}/{effective_repeats}"

    def _liquidity_thresholds(self) -> dict:
        profile = self._tf_entry_profile()
        liq = dict(profile.get("liquidity") or {})
        return {
            "profile_label": str(profile.get("label") or self.cfg.timeframe),
            "max_spread_pct": float(liq.get("max_spread_pct") or self.cfg.liquidity_max_spread_pct),
            "min_top_book_usdt": float(liq.get("min_top_book_usdt") or self.cfg.liquidity_min_top_of_book_usdt),
            "min_side_notional_usdt": float(liq.get("min_side_notional_usdt") or self.cfg.liquidity_min_side_notional_usdt),
            "min_24h_quote_volume": float(liq.get("min_24h_quote_volume") or self.cfg.liquidity_min_24h_quote_volume),
            "max_last_mid_deviation_ratio": float(liq.get("max_last_mid_deviation_ratio") or 0.0045),
            "soft_side_ratio": float(liq.get("soft_side_ratio") or 0.45),
        }

    def _check_liquidity(self, inst_id: str, price: float) -> tuple[bool, str, dict]:
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception as exc:
            return False, f"нет ticker/ликвидности: {exc}", {}

        thresholds = self._liquidity_thresholds()

        bid_px = float(ticker.get("bidPx") or 0.0)
        ask_px = float(ticker.get("askPx") or 0.0)
        bid_sz = float(ticker.get("bidSz") or 0.0)
        ask_sz = float(ticker.get("askSz") or 0.0)
        vol_24h = float(ticker.get("volCcy24h") or ticker.get("vol24h") or 0.0)

        if bid_px <= 0 or ask_px <= 0:
            return False, "пустой bid/ask", {"profile_label": thresholds["profile_label"]}

        mid = (bid_px + ask_px) / 2.0
        spread_pct = ((ask_px - bid_px) / max(mid, 1e-12)) * 100.0

        best_bid_notional = bid_px * bid_sz
        best_ask_notional = ask_px * ask_sz
        best_side_notional = min(best_bid_notional, best_ask_notional)

        metrics = {
            "profile_label": thresholds["profile_label"],
            "entry_liquidity_guard_mode": "active_layered",
            "liquidity_filter_enabled": bool(getattr(self.cfg, "liquidity_filter_enabled", True)),
            "spread_pct": spread_pct,
            "best_bid_notional": best_bid_notional,
            "best_ask_notional": best_ask_notional,
            "best_side_notional": best_side_notional,
            "vol_24h": vol_24h,
            "last_mid_deviation_ratio": abs(price - mid) / max(mid, 1e-12),
            "threshold_max_spread_pct": thresholds["max_spread_pct"],
            "threshold_min_top_book_usdt": thresholds["min_top_book_usdt"],
            "threshold_min_side_notional_usdt": thresholds["min_side_notional_usdt"],
            "threshold_min_24h_quote_volume": thresholds["min_24h_quote_volume"],
            "threshold_max_last_mid_deviation_ratio": thresholds["max_last_mid_deviation_ratio"],
            "threshold_soft_side_ratio": thresholds["soft_side_ratio"],
        }

        if not bool(getattr(self.cfg, "liquidity_filter_enabled", True)):
            return True, "liquidity_filter_disabled_for_test", metrics

        if spread_pct > thresholds["max_spread_pct"]:
            return False, (
                f"широкий спред {spread_pct:.3f}% > {thresholds['max_spread_pct']:.3f}% "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if best_bid_notional < thresholds["min_top_book_usdt"] or best_ask_notional < thresholds["min_top_book_usdt"]:
            return False, (
                f"слабый top-of-book {best_side_notional:.0f} USDT < {thresholds['min_top_book_usdt']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if best_side_notional < thresholds["min_side_notional_usdt"] * thresholds["soft_side_ratio"]:
            return False, (
                f"слишком тонкий стакан {best_side_notional:.0f} USDT < "
                f"{thresholds['min_side_notional_usdt'] * thresholds['soft_side_ratio']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if vol_24h > 0 and vol_24h < thresholds["min_24h_quote_volume"]:
            return False, (
                f"низкий 24h объём {vol_24h:.0f} < {thresholds['min_24h_quote_volume']:.0f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics
        if metrics["last_mid_deviation_ratio"] > thresholds["max_last_mid_deviation_ratio"]:
            return False, (
                f"последняя цена далеко от mid {metrics['last_mid_deviation_ratio']:.4f} > "
                f"{thresholds['max_last_mid_deviation_ratio']:.4f} "
                f"(профиль {thresholds['profile_label']})"
            ), metrics

        sparse_metrics = {}
        try:
            candle_limit = max(int(getattr(self.cfg, "long_entry_period", 55) or 55) + 5, 60)
            sparse_candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, candle_limit) or []
            sparse_metrics = analyze_sparse_candles(
                sparse_candles,
                atr=max(self.compute_atr(inst_id), 0.0),
                short_period=int(getattr(self.cfg, "short_entry_period", 20) or 20),
                long_period=int(getattr(self.cfg, "long_entry_period", 55) or 55),
                short_threshold=max(1, int((getattr(self.cfg, "short_entry_period", 20) or 20) / 2)),
                long_threshold=max(1, int((getattr(self.cfg, "long_entry_period", 55) or 55) / 2)),
            )
            metrics.update({
                "sparse_20": int(sparse_metrics.get("weak_20", 0) or 0),
                "sparse_55": int(sparse_metrics.get("weak_55", 0) or 0),
                "sparse_ratio_20": float(sparse_metrics.get("ratio_20", 0.0) or 0.0),
                "sparse_ratio_55": float(sparse_metrics.get("ratio_55", 0.0) or 0.0),
                "sparse_median_volume": float(sparse_metrics.get("median_volume", 0.0) or 0.0),
            })
            if bool(sparse_metrics.get("reject", False)):
                return False, str(sparse_metrics.get("reason") or "sparse candles"), metrics
        except Exception:
            pass

        history_metrics = {
            "liquidity_history_points": 0,
            "liquidity_history_median_side_usdt": best_side_notional,
            "liquidity_history_peak_side_usdt": best_side_notional,
            "liquidity_history_last_side_usdt": best_side_notional,
            "liquidity_history_max_spread_pct": spread_pct,
            "liquidity_history_stable_points": 1 if best_side_notional >= thresholds["min_side_notional_usdt"] else 0,
        }
        metrics.update(history_metrics)

        if bool(getattr(self.cfg, "liquidity_trap_detector_enabled", True)):
            history_rows = []
            try:
                history_rows = self.market_data_cache.get_ticker_history(
                    inst_id,
                    max_points=max(3, int(getattr(self.cfg, "liquidity_history_lookback_points", 8) or 8)),
                    max_age=float(getattr(self.cfg, "liquidity_history_max_age_sec", 40.0) or 40.0),
                )
            except Exception:
                history_rows = []
            if history_rows:
                side_series = [float(row.get("best_side_notional") or 0.0) for row in history_rows]
                spread_series = [float(row.get("spread_pct") or 0.0) for row in history_rows]
                peak_side = max(side_series) if side_series else best_side_notional
                median_side = float(statistics.median(side_series)) if side_series else best_side_notional
                latest_side = side_series[-1] if side_series else best_side_notional
                max_spread_hist = max(spread_series) if spread_series else spread_pct
                stable_points = sum(1 for value in side_series if value >= thresholds["min_side_notional_usdt"])
                metrics.update({
                    "liquidity_history_points": len(history_rows),
                    "liquidity_history_median_side_usdt": median_side,
                    "liquidity_history_peak_side_usdt": peak_side,
                    "liquidity_history_last_side_usdt": latest_side,
                    "liquidity_history_max_spread_pct": max_spread_hist,
                    "liquidity_history_stable_points": stable_points,
                })
                min_points = max(3, int(getattr(self.cfg, "liquidity_history_min_stable_points", 4) or 4))
                collapse_ratio = float(getattr(self.cfg, "liquidity_history_collapse_ratio", 0.35) or 0.35)
                median_ratio = float(getattr(self.cfg, "liquidity_history_median_ratio", 0.60) or 0.60)
                spread_blowout_mult = float(getattr(self.cfg, "liquidity_history_spread_blowout_mult", 1.8) or 1.8)
                trap_detected = (
                    len(history_rows) >= min_points
                    and peak_side >= thresholds["min_side_notional_usdt"]
                    and latest_side <= peak_side * collapse_ratio
                    and median_side <= thresholds["min_side_notional_usdt"] * median_ratio
                    and max_spread_hist >= thresholds["max_spread_pct"] * spread_blowout_mult
                )
                if trap_detected:
                    return False, (
                        f"мираж ликвидности: пик {peak_side:.0f} USDT, медиана {median_side:.0f}, "
                        f"последний стакан {latest_side:.0f}, max spread {max_spread_hist:.3f}% "
                        f"(профиль {thresholds['profile_label']})"
                    ), metrics

                unstable_ratio = (latest_side / max(median_side, 1e-12)) if median_side > 0 else 0.0
                if len(history_rows) >= min_points and stable_points < min_points and latest_side < thresholds["min_side_notional_usdt"] * 0.85 and unstable_ratio < 0.70:
                    return False, (
                        f"нестабильный стакан: stable_points={stable_points}/{len(history_rows)}, "
                        f"последний стакан {latest_side:.0f} USDT, медиана {median_side:.0f} "
                        f"(профиль {thresholds['profile_label']})"
                    ), metrics

        return True, "ok", metrics

    def _register_stopout(self, state: PositionState, exit_price: float, reason: str) -> None:
        lower_reason = str(reason or "").lower()
        protective_markers = ("atr стоп", "канальный выход", "protective", "первичный стоп", "initial_stop", "desync", "авар")
        if not any(marker in lower_reason for marker in protective_markers):
            return
        cooldown_sec = self._stopout_cooldown_seconds()
        self.recent_stopouts[state.inst_id] = {
            "side": state.side,
            "exit_price": float(exit_price),
            "stop_price": float(state.stop_price),
            "atr": float(max(state.atr, 1e-12)),
            "until": time.time() + cooldown_sec,
            "reason": reason,
        }


    def _bars_to_seconds(self, bars: int) -> int:
        return max(1, int(self._timeframe_seconds() * max(1, int(bars or 1))))

    def _make_breakout_id(self, inst_id: str, side: str, system_name: str, entry_period: int, candle_ts: object, level: float) -> str:
        level_key = f"{float(level or 0.0):.8f}"
        return f"{inst_id}|{side}|{system_name}|{int(entry_period or 0)}|{candle_ts}|{level_key}"

    def _cleanup_runtime_guards(self) -> None:
        now_ts = time.time()
        self.used_breakouts = {k: v for k, v in self.used_breakouts.items() if float(v or 0.0) > now_ts}
        self.symbol_quarantine_until = {k: v for k, v in self.symbol_quarantine_until.items() if float(v or 0.0) > now_ts}
        self.reentry_guards = {k: v for k, v in self.reentry_guards.items() if float((v or {}).get("until", 0.0) or 0.0) > now_ts}

    def _check_entry_runtime_guards(self, inst_id: str, side: str, system_name: str, entry_price: float, atr: float, breakout_id: str) -> tuple[bool, str]:
        self._cleanup_runtime_guards()
        now_ts = time.time()
        quarantine_until = float(self.symbol_quarantine_until.get(inst_id, 0.0) or 0.0)
        if quarantine_until > now_ts:
            remain = max(1, int(quarantine_until - now_ts))
            return False, f"symbol quarantine active {remain}s"
        if breakout_id and breakout_id in self.used_breakouts:
            remain = max(1, int(float(self.used_breakouts.get(breakout_id, 0.0)) - now_ts))
            return False, f"same breakout already traded ({remain}s left)"
        guard = dict(self.reentry_guards.get((inst_id, side, system_name), {}) or {})
        until_ts = float(guard.get("until", 0.0) or 0.0)
        if until_ts > now_ts:
            remain = max(1, int(until_ts - now_ts))
            last_entry_price = float(guard.get("entry_price", 0.0) or 0.0)
            if last_entry_price > 0 and atr > 0:
                dist_atr = abs(float(entry_price or 0.0) - last_entry_price) / max(float(atr or 0.0), 1e-12)
                if dist_atr < float(getattr(self.cfg, "same_price_reentry_atr", 0.20) or 0.20):
                    return False, f"same-price reentry blocked {remain}s ({dist_atr:.2f} ATR)"
            return False, f"reentry cooldown active {remain}s"
        return True, "ok"

    def _register_entry_runtime_guard(self, inst_id: str, side: str, system_name: str, entry_price: float, atr: float, breakout_id: str, exit_reason: str = "") -> None:
        bars = int(getattr(self.cfg, "protective_reentry_cooldown_bars", 5) if "protective" in str(exit_reason or "").lower() else getattr(self.cfg, "reentry_cooldown_bars", 3))
        until_ts = time.time() + self._bars_to_seconds(bars)
        key = (inst_id, side, system_name)
        self.reentry_guards[key] = {
            "until": until_ts,
            "entry_price": float(entry_price or 0.0),
            "atr": float(atr or 0.0),
            "breakout_id": str(breakout_id or ""),
            "exit_reason": str(exit_reason or ""),
        }
        if breakout_id:
            self.used_breakouts[str(breakout_id)] = until_ts

    def _register_loss_streak(self, inst_id: str, side: str, pnl: float) -> None:
        key = (inst_id, side)
        if float(pnl or 0.0) < 0.0:
            self.loss_streak_by_symbol_side[key] = int(self.loss_streak_by_symbol_side.get(key, 0) or 0) + 1
            if int(self.loss_streak_by_symbol_side.get(key, 0) or 0) >= int(getattr(self.cfg, "loss_streak_limit", 3) or 3):
                self.symbol_quarantine_until[inst_id] = time.time() + int(getattr(self.cfg, "quarantine_minutes", 60) or 60) * 60
        else:
            self.loss_streak_by_symbol_side[key] = 0

    def _confirm_exchange_stop_active(self, state: PositionState, timeout_sec: float = 0.0) -> bool:
        return self.stop_engine._confirm_exchange_stop_active(state, timeout_sec=timeout_sec)

    def _early_invalid_exit_reason(self, state: PositionState, candles: List[List[float]], current_price: float) -> str:
        closed_bars = self._closed_bars_since_entry(state, candles)
        if closed_bars > int(getattr(self.cfg, "early_invalid_bars", 2) or 2):
            return ""
        breakout_level = float(getattr(state, "breakout_level", 0.0) or 0.0)
        atr = max(float(getattr(state, "atr", 0.0) or 0.0), 1e-12)
        if breakout_level > 0.0:
            if state.side == "long" and float(current_price or 0.0) <= breakout_level:
                return "Early invalidation: цена вернулась внутрь канала"
            if state.side == "short" and float(current_price or 0.0) >= breakout_level:
                return "Early invalidation: цена вернулась внутрь канала"
        move_against_atr = ((float(state.avg_px or 0.0) - float(current_price or 0.0)) / atr) if state.side == "long" else ((float(current_price or 0.0) - float(state.avg_px or 0.0)) / atr)
        if move_against_atr >= float(getattr(self.cfg, "early_invalid_move_atr", 1.5) or 1.5):
            return f"Early invalidation: движение против позиции {move_against_atr:.2f} ATR"
        return ""

    def _skip_profitable_turtle20_reentry(self, inst_id: str) -> tuple[bool, str]:
        """
        v081: не разделяем Turtle 20 и Turtle 55 искусственным profitable-skip.
        Оба канала следуют одной Turtle-логике.
        """
        return False, ""

    def _log_breakout_quality(self, inst_id: str, side: str, price: float, atr: float, system_name: str) -> None:
        try:
            candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(80, self.cfg.long_entry_period + 10)) or []
            if len(candles) < 2 or atr <= 0:
                self.breakout_quality_logger.log("breakout_quality", inst_id=inst_id, side=side, system_name=system_name, entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"), atr=atr, note="not_enough_data")
                return
            last = candles[-1]
            prev = candles[-2]
            entry_period = int(self.cfg.long_entry_period if str(system_name) == "Turtle 55" else self.cfg.short_entry_period if str(system_name) == "Turtle 20" else (self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period))
            if len(candles) < entry_period + 1:
                self.breakout_quality_logger.log("breakout_quality", inst_id=inst_id, side=side, system_name=system_name, entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"), atr=atr, note="not_enough_channel_data")
                return
            window = candles[-(entry_period + 1):-1]
            highs = [float(c[2]) for c in window]
            lows = [float(c[3]) for c in window]
            upper = max(highs) if highs else 0.0
            lower = min(lows) if lows else 0.0
            level = upper if side == "long" else lower
            last_open = float(last[1]); last_high = float(last[2]); last_low = float(last[3]); last_close = float(last[4])
            candle_range = max(last_high - last_low, 1e-12)
            body = abs(last_close - last_open)
            beyond = ((last_close - level) / max(atr, 1e-12)) if side == "long" else ((level - last_close) / max(atr, 1e-12))
            dist = ((price - level) / max(atr, 1e-12)) if side == "long" else ((level - price) / max(atr, 1e-12))
            self.breakout_quality_logger.log(
                "breakout_quality",
                inst_id=inst_id, side=side, system_name=system_name, timeframe=self.cfg.timeframe,
                entry_mode=("minimal" if self._minimal_turtle_entry_mode() else "full"),
                entry_price=round(float(price), 8), atr=round(float(atr), 8), breakout_level=round(level, 8),
                donchian_high=round(upper, 8), donchian_low=round(lower, 8),
                breakout_buffer_atr_actual=round(abs(price - level) / max(atr, 1e-12), 6),
                close_beyond_channel_atr=round(beyond, 6), channel_width_atr=round((upper - lower) / max(atr, 1e-12), 6),
                body_atr=round(body / max(atr, 1e-12), 6), body_to_range_ratio=round(body / candle_range, 6),
                distance_from_breakout_level_atr=round(dist, 6), fresh_breakout_true_false=bool(is_fresh_breakout(float(prev[4]), upper, lower, side)),
            )
        except Exception:
            pass

    def _recent_stopout_blocks_entry(self, inst_id: str, side: str, price: float) -> tuple[bool, str]:
        data = self.recent_stopouts.get(inst_id)
        if not data:
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=False, cooldown_blocked=False, recovery_blocked=False, final_decision_allow_true_false=True, final_reason="ok")
            return False, "ok"

        now_ts = time.time()
        until_ts = float(data.get("until", 0.0))
        if until_ts <= now_ts:
            self.recent_stopouts.pop(inst_id, None)
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, cooldown_expired=True, cooldown_blocked=False, recovery_blocked=False, final_decision_allow_true_false=True, final_reason="ok")
            return False, "ok"

        prev_side = str(data.get("side") or "")
        exit_price = float(data.get("exit_price") or 0.0)
        atr = float(max(data.get("atr") or 0.0, 1e-12))
        remain = max(1, int(until_ts - now_ts))
        distance = abs(price - exit_price)
        recovery_actual = distance / max(atr, 1e-12)

        if prev_side == side and distance < atr * self.cfg.reentry_recovery_atr:
            reason = (
                f"cooldown после ATR-стопа ещё активен {remain}s; "
                f"цена отошла только на {distance / atr:.2f} ATR"
            )
            self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, seconds_since_last_close=0, last_exit_reason=str(data.get("reason") or "stopout"), last_trade_pnl=float(data.get("pnl") or 0.0), cooldown_required_seconds=remain, cooldown_blocked=True, recovery_atr_required=float(self.cfg.reentry_recovery_atr), recovery_atr_actual=round(recovery_actual, 6), recovery_blocked=True, recent_trade_penalty=round(float(self._recent_trade_penalty(inst_id)), 6), final_decision_allow_true_false=False, final_reason=reason)
            return True, reason

        self._log_reentry_diagnostic(inst_id, side, price=price, recent_stopout_present=True, seconds_since_last_close=0, last_exit_reason=str(data.get("reason") or "stopout"), last_trade_pnl=float(data.get("pnl") or 0.0), cooldown_required_seconds=remain, cooldown_blocked=False, recovery_atr_required=float(self.cfg.reentry_recovery_atr), recovery_atr_actual=round(recovery_actual, 6), recovery_blocked=False, recent_trade_penalty=round(float(self._recent_trade_penalty(inst_id)), 6), final_decision_allow_true_false=True, final_reason="ok")
        return False, "ok"

    def _audit_signal(self, cycle_id: int, inst_id: str, stage: str, **payload) -> None:
        if not bool(getattr(self.cfg, "signal_audit_enabled", True)):
            return
        try:
            payload = dict(payload or {})
            if payload.get("reason") and not payload.get("reject_code"):
                payload["reject_code"] = _classify_reason_code(payload.get("reason"))
            self.signal_audit_logger.log("signal_audit", cycle_id=cycle_id, inst_id=inst_id, stage=stage, timeframe=self.cfg.timeframe, **payload)
        except Exception as exc:
            logging.warning("Signal audit failed for %s: %s", inst_id, exc)

    def _ema_values(self, closes: List[float], period: int) -> List[float]:
        vals = [float(v) for v in (closes or [])]
        if not vals:
            return []
        period = max(1, int(period or 1))
        k = 2.0 / (period + 1.0)
        ema = vals[0]
        result = [ema]
        for value in vals[1:]:
            ema = value * k + ema * (1.0 - k)
            result.append(ema)
        return result

    def _trend_filter(self, candles: List[List[float]], side: str, atr: float, price: float) -> tuple[bool, str, dict]:
        closes = [float(c[4]) for c in (candles or []) if len(c) >= 5]
        if len(closes) < 55:
            return False, "недостаточно свечей для фильтра тренда", {}
        ema20 = self._ema_values(closes, 20)
        ema50 = self._ema_values(closes, 50)
        if len(ema50) < 6 or len(ema20) < 3:
            return False, "EMA тренда недоступна", {}
        slope = ema50[-1] - ema50[-5]
        slope_atr = slope / max(atr, 1e-12)
        spacing = (ema20[-1] - ema50[-1]) / max(price, 1e-12) * 100.0
        metrics = {
            "trend_slope_atr": round(slope_atr, 6),
            "trend_spacing_pct": round(spacing, 6),
            "ema20": round(float(ema20[-1]), 8),
            "ema50": round(float(ema50[-1]), 8),
        }
        slope_min = float(self._timeframe_filter_profile().get("trend_slope_atr_min", 0.10) or 0.10)
        metrics["trend_slope_threshold_atr"] = round(slope_min, 6)
        if side == "long":
            if ema20[-1] <= ema50[-1]:
                return False, "trend filter: EMA20 <= EMA50 для long", metrics
            if slope_atr <= slope_min:
                return False, f"trend filter: слабый наклон EMA50 {slope_atr:.2f} ATR < {slope_min:.2f} ATR для long", metrics
        else:
            if ema20[-1] >= ema50[-1]:
                return False, "trend filter: EMA20 >= EMA50 для short", metrics
            if slope_atr >= -slope_min:
                return False, f"trend filter: слабый наклон EMA50 {slope_atr:.2f} ATR > {-slope_min:.2f} ATR для short", metrics
        return True, "ok", metrics

    def _volatility_gate(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str, dict]:
        filter_profile = self._timeframe_filter_profile()
        atr_pct = (atr / max(price, 1e-12)) * 100.0
        window = candles[-min(len(candles), max(20, int(self.cfg.flat_lookback_candles))):]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        channel = (max(highs) - min(lows)) if highs and lows else 0.0
        channel_atr_ratio = channel / max(atr, 1e-12)
        min_atr_pct = float(filter_profile.get("min_atr_pct", getattr(self.cfg, "min_atr_pct", 0.0)) or 0.0)
        min_channel_atr_ratio = float(filter_profile.get("flat_min_channel_atr_ratio", getattr(self.cfg, "flat_min_channel_atr_ratio", 2.0)) or 2.0)
        metrics = {
            "atr_pct": round(atr_pct, 6),
            "channel_atr_ratio": round(channel_atr_ratio, 6),
            "threshold_min_atr_pct": round(min_atr_pct, 6),
            "threshold_min_channel_atr_ratio": round(min_channel_atr_ratio, 6),
            "filter_profile": str(filter_profile.get("label") or self.cfg.timeframe),
        }
        if atr_pct < min_atr_pct:
            return False, f"volatility filter: ATR {atr_pct:.3f}% < {min_atr_pct:.3f}% ({filter_profile.get('label')})", metrics
        if channel_atr_ratio < min_channel_atr_ratio:
            return False, f"volatility filter: channel/ATR {channel_atr_ratio:.2f} < {min_channel_atr_ratio:.2f} ({filter_profile.get('label')})", metrics
        return True, "ok", metrics

    def _recent_trade_penalty(self, inst_id: str) -> float:
        penalty = 0.0
        matched = 0
        for trade in reversed(self.closed_trades[-24:]):
            if str(getattr(trade, "inst_id", "")) != str(inst_id):
                continue
            matched += 1
            try:
                closed_at = datetime.strptime(str(getattr(trade, "time", "")), "%Y-%m-%d %H:%M:%S")
                minutes_ago = max(0.0, (datetime.now() - closed_at).total_seconds() / 60.0)
            except Exception:
                minutes_ago = 99999.0
            if minutes_ago <= 60:
                penalty += 1.6
            elif minutes_ago <= 180:
                penalty += 0.9
            elif minutes_ago <= 720:
                penalty += 0.45
            if matched >= 3:
                break
        return penalty

    def _make_signal_funnel(self) -> dict:
        return {
            "cycle_id": int(self.scan_cycle_seq),
            "instruments_scanned": 0,
            "prefilter_skipped": 0,
            "warmup_rejected": 0,
            "flat_filter_rejected": 0,
            "structure_rejected": 0,
            "trend_rejected": 0,
            "liquidity_rejected": 0,
            "breakout_rejected": 0,
            "other_rejected": 0,
            "candidates": 0,
            "ranked_candidates": 0,
            "orders_sent": 0,
            "entry_failed": 0,
            "manual_skipped": 0,
            "opened": 0,
        }

    def _classify_rejection_bucket(self, reason: str) -> str:
        text = str(reason or "").lower()
        if "warmup" in text or "недостаточно свечей" in text or "atr недоступ" in text:
            return "warmup_rejected"
        if "flat filter" in text or "узкий диапазон" in text or "канал слишком мал" in text or "слабая структура диапазона" in text:
            return "flat_filter_rejected"
        if "structure filter" in text or "ложных выносов" in text or "плотная база" in text or "прилипла к центру" in text:
            return "structure_rejected"
        if "trend filter" in text or "ema20" in text or "ema50" in text:
            return "trend_rejected"
        if "liquidity" in text or "спред" in text or "стакан" in text or "top-of-book" in text or "объём" in text:
            return "liquidity_rejected"
        if "пробой" in text or "donchian" in text or "breakout" in text or "свеча" in text:
            return "breakout_rejected"
        return "other_rejected"

    def _register_near_pass_candidate(self, inst_id: str, side: str, system_name: str, score: float, reason: str, **payload) -> None:
        item = {
            "inst_id": inst_id,
            "side": side,
            "system_name": system_name,
            "near_pass_score": round(float(score or 0.0), 4),
            "reason": str(reason or ""),
        }
        item.update(payload)
        self.last_near_pass_candidates.append(item)

    def _bump_signal_funnel(self, bucket: str, amount: int = 1) -> None:
        if isinstance(getattr(self, "last_signal_funnel", None), dict) and bucket in self.last_signal_funnel:
            self.last_signal_funnel[bucket] = int(self.last_signal_funnel.get(bucket, 0) or 0) + int(amount or 0)

    def _emit_near_pass_diagnostics(self, cycle_id: int) -> None:
        top_n = max(1, int(getattr(self.cfg, "diagnostic_near_pass_top_n", 10) or 10))
        ranked = sorted(self.last_near_pass_candidates, key=lambda row: (-float(row.get("near_pass_score", 0.0)), str(row.get("inst_id", ""))))[:top_n]
        self.last_near_pass_candidates = ranked
        if not ranked:
            return
        self.log_line.emit("TOP NEAR-PASS CANDIDATES:")
        for idx, row in enumerate(ranked, start=1):
            message = (
                f"{idx:02d}. {row.get('inst_id')} {row.get('side')} {row.get('system_name')} | "
                f"score={float(row.get('near_pass_score', 0.0)):.3f} | {row.get('reason')}"
            )
            self.log_line.emit(message)
            self._audit_signal(cycle_id, str(row.get("inst_id") or "*"), "near_pass_candidate", rank=idx, side=row.get("side"), system_name=row.get("system_name"), near_pass_score=row.get("near_pass_score"), reason=row.get("reason"), breakout_distance_atr=row.get("breakout_distance_atr"), entry_period=row.get("entry_period"))

    def _collect_trade_ready_metrics(self) -> dict:
        self._clear_expired_runtime_blocks()
        universe = [inst_id for inst_id in list(getattr(self.gateway, "swap_ids", []) or []) if not is_hidden_instrument(inst_id)]
        universe_set = set(universe)
        blacklist = set(getattr(self.cfg, "blacklist", []) or []) & universe_set
        blocked = set(getattr(self, "blocked_instruments", {}).keys()) & universe_set
        temp_blocked = set()
        now_ts = time.time()
        for inst_id, until_ts in list(getattr(self, "temp_blocked_until", {}).items()):
            try:
                if float(until_ts or 0.0) > now_ts and inst_id in universe_set:
                    temp_blocked.add(inst_id)
            except Exception:
                continue
        illiquid = set()
        for inst_id, until_ts in list(getattr(self, "illiquid_instruments", {}).items()):
            try:
                if float(until_ts or 0.0) > now_ts and inst_id in universe_set:
                    illiquid.add(inst_id)
            except Exception:
                continue
        stopout = set()
        for inst_id, data in list(getattr(self, "recent_stopouts", {}).items()):
            try:
                if float((data or {}).get("until", 0.0) or 0.0) > now_ts and inst_id in universe_set:
                    stopout.add(inst_id)
            except Exception:
                continue
        open_positions = set(getattr(self, "position_state", {}).keys()) & universe_set
        hard_blocked = blacklist | blocked | temp_blocked | illiquid | stopout
        available_after_bans = [inst_id for inst_id in universe if inst_id not in hard_blocked]

        scanner_summary = {
            "scanner_total": len(universe),
            "scanner_scanned": 0,
            "scanner_ready": 0,
            "scanner_allowed": 0,
            "scanner_blocked": 0,
            "scanner_dead": 0,
            "scanner_saw": 0,
            "scanner_ripping": 0,
            "scanner_pending": len(universe),
            "scanner_failed": 0,
            "scanner_status_text": "IDLE",
            "scanner_safe": 0,
            "scanner_caution": 0,
            "scanner_risky": 0,
            "scanner_blacklist": 0,
            "scanner_exec_watch": 0,
            "scanner_admitted": 0,
        }
        scanner_admitted_symbols = set(available_after_bans)
        if getattr(self.cfg, "scanner_enabled", True) and hasattr(self, "market_scanner"):
            self.market_scanner.initialize_universe(list(universe))
            scanner_summary = dict(self.market_scanner.summary())
            scanner_admitted_symbols = {
                inst_id for inst_id in available_after_bans
                if self.market_scanner.allows_entry(inst_id)[0]
            }
        execution_watch = set()
        if getattr(self.cfg, "scanner_enabled", True) and hasattr(self, "market_scanner"):
            execution_watch = {
                inst_id for inst_id in universe
                if self.market_scanner.get_status(inst_id).execution_risk_class in {"RISKY", "BLACKLIST_CANDIDATE"}
            }
        else:
            execution_watch = set(getattr(self, "execution_risk_events", {}).keys()) & universe_set

        eligible = list(scanner_admitted_symbols)
        if not bool(getattr(self.cfg, "trade_ready_include_open_positions", False)):
            eligible = [inst_id for inst_id in eligible if inst_id not in open_positions]
        metrics = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scan_universe_total": len(universe),
            "blacklist_count": len(blacklist),
            "blocked_count": len(blocked),
            "temp_blocked_count": len(temp_blocked),
            "illiquid_count": len(illiquid),
            "stopout_cooldown_count": len(stopout),
            "hard_blocked_unique_count": len(hard_blocked),
            "execution_watchlist_count": len(execution_watch),
            "open_positions_count": len(open_positions),
            "available_after_bans_count": len(available_after_bans),
            "trade_ready_count": len(eligible),
            **scanner_summary,
        }
        return metrics

    def _maybe_log_trade_ready_metrics(self, force: bool = False) -> None:
        metrics = self._collect_trade_ready_metrics()
        self.last_trade_ready_metrics = dict(metrics)
        interval = max(60, int(getattr(self.cfg, "trade_ready_log_interval_sec", 900) or 900))
        now_ts = time.time()
        if force or (now_ts - float(getattr(self, "last_trade_ready_log_at", 0.0) or 0.0) >= interval):
            self.last_trade_ready_log_at = now_ts
            self.stats_logger.log("filter_diagnostics", **metrics, signal_funnel=dict(getattr(self, "last_signal_funnel", {}) or {}))

    def scan_markets(self) -> None:
        if bool(getattr(self, "position_cycle_active", False)) or bool(getattr(self, "position_cycle_scanner_paused", False)):
            self.last_signal_funnel = dict(getattr(self, "last_signal_funnel", {}) or {})
            return
        self._clear_expired_runtime_blocks()
        self.scan_cycle_seq += 1
        cycle_id = int(self.scan_cycle_seq)
        candidates = []
        rejected = 0
        skipped_prefilter = 0
        self.last_scan_cycle_id = cycle_id
        self.last_scan_candidates = []
        self.last_near_pass_candidates = []
        funnel = self._make_signal_funnel()
        self.last_signal_funnel = funnel

        self._audit_signal(cycle_id, "*", "cycle_started", open_positions=len(self.position_state), total_limit=int(getattr(self.cfg, "max_open_positions_total", 0) or 0))
        connectivity_state = str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE")
        if self._entries_blocked_by_connectivity():
            reason = f"connectivity_guard:{connectivity_state.lower()}"
            self.stats_logger.log("entry_scan_blocked", cycle_id=cycle_id, reason=reason, connectivity_state=connectivity_state)
            self._audit_signal(cycle_id, "*", "cycle_blocked", reason=reason, connectivity_state=connectivity_state)
            self.last_signal_funnel = dict(funnel)
            return
        if getattr(self.cfg, "scanner_enabled", True):
            scanner_interval = max(1, int(getattr(self.cfg, "scanner_refresh_interval_sec", 15) or 15))
            now_ts = time.time()
            last_scanner_ts = float(getattr(self, "last_scanner_refresh_ts", 0.0) or 0.0)
            if (now_ts - last_scanner_ts) >= scanner_interval:
                self.market_scanner.initialize_universe(list(getattr(self.gateway, "swap_ids", []) or []))
                processed = self.market_scanner.run_chunk(getattr(self.cfg, "scanner_chunk_size", 2))
                self.last_scanner_refresh_ts = now_ts
                if processed > 0:
                    self.log_line.emit(f"[SCANNER] refreshed {processed} instrument(s)")
        self._maybe_log_trade_ready_metrics(force=False)

        for inst_id in self.gateway.swap_ids:
            if not self.running:
                break
            blocked_now, blocked_reason = self._is_temporarily_blocked(inst_id)
            if inst_id in self.cfg.blacklist or inst_id in self.blocked_instruments or is_hidden_instrument(inst_id):
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason="blacklist_or_blocked")
                continue
            if blocked_now:
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason=blocked_reason)
                continue
            if inst_id in self.position_state:
                skipped_prefilter += 1
                funnel["prefilter_skipped"] += 1
                self._audit_signal(cycle_id, inst_id, "prefilter_skipped", reason="already_open")
                continue
            if getattr(self.cfg, "scanner_enabled", True):
                scanner_forced_refresh = False
                scanner_status_age_sec = float(getattr(self.market_scanner, "status_age_sec", lambda _x: 1e12)(inst_id))
                if bool(getattr(self.cfg, "scanner_entry_force_refresh", True)) and (scanner_status_age_sec > float(getattr(self.cfg, "scanner_status_ttl_sec", 90) or 90) or not self.market_scanner.is_ready(inst_id)):
                    scanner_status = self.market_scanner.refresh_for_entry(inst_id, force=True)
                    scanner_forced_refresh = True
                    scanner_status_age_sec = float(getattr(self.market_scanner, "status_age_sec", lambda _x: 1e12)(inst_id))
                scanner_allow, scanner_reason, scanner_status = self.market_scanner.allows_entry(inst_id)
                if not scanner_allow:
                    skipped_prefilter += 1
                    funnel["prefilter_skipped"] += 1
                    self._audit_signal(
                        cycle_id,
                        inst_id,
                        "prefilter_skipped",
                        reason=scanner_reason,
                        scanner_structure=getattr(scanner_status, "market_structure_class", "PENDING"),
                        scanner_final=getattr(scanner_status, "final_risk_class", "PENDING"),
                        scanner_exec=getattr(scanner_status, "execution_risk_class", "PENDING"),
                        scanner_primary_reason=getattr(scanner_status, "primary_reason", ""),
                        scanner_filter_type=getattr(scanner_status, "filter_type", ""),
                        scanner_status_age_sec=round(scanner_status_age_sec, 3),
                        scanner_forced_refresh=scanner_forced_refresh,
                        scanner_block_remaining_sec=round(float(getattr(self.market_scanner, "get_block_remaining_sec", lambda _x: 0.0)(inst_id)), 3),
                        market_data_connectivity_state=str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE"),
                    )
                    continue
            try:
                funnel["instruments_scanned"] += 1
                inst_candidates = self.evaluate_entry(inst_id, cycle_id=cycle_id)
                if inst_candidates:
                    candidates.extend(inst_candidates)
                else:
                    rejected += 1
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка анализа входа: {exc}")
                logging.warning("Entry eval failed for %s: %s", inst_id, exc)
                self._audit_signal(cycle_id, inst_id, "analysis_error", error=str(exc))

        if not candidates:
            self.last_signal_funnel = dict(funnel)
            self._emit_near_pass_diagnostics(cycle_id)
            self.stats_logger.log("signal_funnel", **self.last_signal_funnel)
            self._maybe_log_trade_ready_metrics(force=False)
            self.stats_logger.log("entry_candidates_ranked", cycle_id=cycle_id, total=0, opened=0, timeframe=self.cfg.timeframe, rejected=rejected, skipped_prefilter=skipped_prefilter)
            self._audit_signal(cycle_id, "*", "cycle_finished", candidates=0, opened=0, rejected=rejected, skipped_prefilter=skipped_prefilter, signal_funnel=self.last_signal_funnel)
            return

        def sort_key(item: dict):
            system_rank = 0 if int(item.get("entry_period", 0)) >= int(self.cfg.long_entry_period) else 1
            return (
                system_rank,
                -float(item.get("quality_score", 0.0)),
                -float(item.get("freshness_score", 0.0)),
                float(item.get("breakout_distance_atr", 0.0)),
                -float(item.get("liquidity_score", 0.0)),
                float(item.get("recent_trade_penalty", 0.0)),
                str(item.get("inst_id", "")),
            )

        candidates.sort(key=sort_key)
        self.last_scan_candidates = [dict(item) for item in candidates[:12]]
        funnel["candidates"] = len(candidates)
        top_n = max(1, int(getattr(self.cfg, "signal_audit_top_n", 12) or 12))
        funnel["ranked_candidates"] = min(len(candidates), top_n)
        for rank, candidate in enumerate(candidates[:top_n], start=1):
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "ranked_candidate",
                rank=rank,
                side=candidate.get("side"),
                system_name=candidate.get("system_name"),
                entry_period=candidate.get("entry_period"),
                breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4),
                liquidity_score=round(float(candidate.get("liquidity_score", 0.0)), 4),
                freshness_score=round(float(candidate.get("freshness_score", 0.0)), 4),
                recent_trade_penalty=round(float(candidate.get("recent_trade_penalty", 0.0)), 4),
                reason=candidate.get("reason"),
                quality_score=round(float(candidate.get("quality_score", 0.0)), 4),
            )

        opened = 0
        total_slots = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)

        for rank, candidate in enumerate(candidates, start=1):
            if not self.running:
                break
            if candidate["inst_id"] in self.position_state:
                self._audit_signal(cycle_id, candidate["inst_id"], "rank_skipped", rank=rank, reason="already_open_after_previous_fill")
                continue
            if total_slots > 0 and len(self.position_state) >= total_slots:
                rotation_ok = self._try_rotate_for_candidate(candidate, cycle_id=cycle_id, rank=rank)
                if not rotation_ok:
                    reason = f"достигнут общий лимит открытых позиций: {len(self.position_state)}/{total_slots}"
                    self.log_line.emit(f"{candidate['inst_id']}: вход пропущен — {reason}")
                    self.stats_logger.log("entry_rejected", cycle_id=cycle_id, inst_id=candidate["inst_id"], side=candidate["side"], price=candidate["price"], atr=candidate["atr"], system_name=candidate["system_name"], timeframe=self.cfg.timeframe, entry_period=candidate["entry_period"], exit_period=candidate["exit_period"], reason=reason)
                    self._audit_signal(cycle_id, candidate["inst_id"], "entry_skipped", rank=rank, reason=reason, side=candidate["side"], system_name=candidate["system_name"])
                    continue

            signal_payload = {
                "inst_id": candidate["inst_id"],
                "side": candidate["side"],
                "price": candidate["price"],
                "atr": candidate["atr"],
                "system_name": candidate["system_name"],
                "timeframe": self.cfg.timeframe,
                "entry_period": candidate["entry_period"],
                "exit_period": candidate["exit_period"],
                "reason": candidate["reason"],
                "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
            }
            self.stats_logger.log(
                "entry_signal",
                cycle_id=cycle_id,
                rank=rank,
                inst_id=candidate["inst_id"],
                side=candidate["side"],
                price=candidate["price"],
                atr=candidate["atr"],
                system_name=candidate["system_name"],
                timeframe=self.cfg.timeframe,
                entry_period=candidate["entry_period"],
                exit_period=candidate["exit_period"],
                reason=candidate["reason"],
                trade_mode=getattr(self.cfg, "trade_mode", "auto"),
                breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4),
                liquidity_score=round(float(candidate.get("liquidity_score", 0.0)), 4),
                freshness_score=round(float(candidate.get("freshness_score", 0.0)), 4),
                recent_trade_penalty=round(float(candidate.get("recent_trade_penalty", 0.0)), 4),
            )

            if getattr(self.cfg, "trade_mode", "auto") == "manual":
                if not self.request_manual_entry_approval(signal_payload):
                    self.stats_logger.log(
                        "entry_skipped_manual",
                        cycle_id=cycle_id,
                        rank=rank,
                        inst_id=candidate["inst_id"],
                        side=candidate["side"],
                        price=candidate["price"],
                        atr=candidate["atr"],
                        system_name=candidate["system_name"],
                        timeframe=self.cfg.timeframe,
                        reason=candidate["reason"],
                    )
                    self._audit_signal(cycle_id, candidate["inst_id"], "entry_skipped_manual", rank=rank, side=candidate["side"], system_name=candidate["system_name"])
                    continue

            try:
                opened_now = self.enter_position(candidate["inst_id"], candidate["side"], candidate["price"], candidate["atr"], candidate["system_name"], candidate)
            except Exception as exc:
                opened_now = False
                self._log_execution_event("entry_exception", inst_id=candidate.get("inst_id"), side=candidate.get("side"), system_name=candidate.get("system_name"), error=str(exc), traceback=traceback.format_exc())
                logging.exception("Entry execution failed for %s", candidate.get("inst_id"))
            if not opened_now:
                funnel["entry_failed"] += 1
                self._audit_signal(cycle_id, candidate["inst_id"], "entry_failed", rank=rank, side=candidate["side"], system_name=candidate["system_name"])
                continue
            opened += 1
            funnel["orders_sent"] += 1
            funnel["opened"] += 1
            self._audit_signal(cycle_id, candidate["inst_id"], "entry_sent", rank=rank, side=candidate["side"], system_name=candidate["system_name"], breakout_distance_atr=round(float(candidate.get("breakout_distance_atr", 0.0)), 4))

        self.last_signal_funnel = dict(funnel)
        self._emit_near_pass_diagnostics(cycle_id)
        self.stats_logger.log("signal_funnel", **self.last_signal_funnel)
        self._maybe_log_trade_ready_metrics(force=False)
        self.stats_logger.log("entry_candidates_ranked", cycle_id=cycle_id, total=len(candidates), opened=opened, timeframe=self.cfg.timeframe, rejected=rejected, skipped_prefilter=skipped_prefilter)
        self._audit_signal(cycle_id, "*", "cycle_finished", candidates=len(candidates), opened=opened, rejected=rejected, skipped_prefilter=skipped_prefilter, signal_funnel=self.last_signal_funnel)


    def _rotation_cooldown_seconds(self) -> int:
        tf_sec = max(60, self._timeframe_seconds())
        return max(tf_sec, min(tf_sec * 3, 3600))

    def _is_rotation_recently_exited(self, inst_id: str) -> bool:
        until_ts = float(self.recent_rotation_exits.get(inst_id, 0.0) or 0.0)
        if until_ts <= 0:
            return False
        if until_ts <= time.time():
            self.recent_rotation_exits.pop(inst_id, None)
            return False
        return True

    def _position_pnl_pct(self, state: PositionState, last_px: Optional[float] = None) -> float:
        try:
            margin = float(getattr(state, "margin", 0.0) or 0.0)
        except Exception:
            margin = 0.0
        if margin > 0:
            try:
                return (float(getattr(state, "unrealized_pnl", 0.0) or 0.0) / margin) * 100.0
            except Exception:
                return 0.0
        try:
            avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        except Exception:
            avg_px = 0.0
        try:
            current_px = float(last_px if last_px is not None else getattr(state, "last_px", avg_px) or avg_px)
        except Exception:
            current_px = avg_px
        if avg_px <= 0:
            return 0.0
        if str(getattr(state, "side", "")).lower() == "long":
            return ((current_px - avg_px) / avg_px) * 100.0
        return ((avg_px - current_px) / avg_px) * 100.0

    def _rotation_candidate_reason(self, candidate: dict) -> str:
        return (
            f"{candidate.get('system_name', 'signal')} {candidate.get('side', '')} "
            f"{candidate.get('inst_id', '')} rank-new-entry"
        ).strip()

    def _pick_rotation_victim(self, incoming_candidate: dict) -> tuple[Optional[PositionState], str]:
        if not bool(getattr(self.cfg, "rotation_enabled", True)):
            return None, "rotation_disabled"
        total_slots = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)
        if total_slots <= 0 or len(self.position_state) < total_slots:
            return None, "slots_available"
        incoming_inst = str(incoming_candidate.get("inst_id") or "")
        threshold = max(1, int(getattr(self.cfg, "rotation_max_units_threshold", 3) or 3))
        require_negative = bool(getattr(self.cfg, "rotation_require_negative_pnl", True))
        pool = []
        for state in self.position_state.values():
            if str(state.inst_id) == incoming_inst:
                continue
            if int(getattr(state, "units", 1) or 1) > threshold:
                continue
            pnl_pct = self._position_pnl_pct(state)
            min_negative_pnl_pct = float(getattr(self.cfg, "rotation_min_negative_pnl_pct", 0.0) or 0.0)
            if require_negative and pnl_pct >= -abs(min_negative_pnl_pct):
                continue
            pool.append((state, pnl_pct))
        if not pool:
            if require_negative:
                return None, "нет убыточной позиции для ротации с допустимым числом юнитов"
            return None, "нет позиции для ротации с допустимым числом юнитов"
        pool.sort(key=lambda item: (int(getattr(item[0], "units", 1) or 1), float(item[1]), float(getattr(item[0], "unrealized_pnl", 0.0) or 0.0), str(item[0].inst_id)))
        victim, pnl_pct = pool[0]
        return victim, f"выбран {victim.inst_id}: units={victim.units}, pnl_pct={pnl_pct:.2f}%"

    def _try_rotate_for_candidate(self, candidate: dict, cycle_id: int, rank: int) -> bool:
        victim, pick_reason = self._pick_rotation_victim(candidate)
        if victim is None:
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "rotation_unavailable",
                rank=rank,
                reason=pick_reason,
                incoming_system=candidate.get("system_name"),
                incoming_side=candidate.get("side"),
            )
            return False
        try:
            ticker = self.gateway.get_ticker_data(victim.inst_id)
            close_price = float(ticker.get("markPx") or ticker.get("last") or victim.last_px or victim.avg_px)
        except Exception:
            close_price = float(victim.last_px or victim.avg_px or 0.0)
        if close_price <= 0:
            self._audit_signal(cycle_id, candidate["inst_id"], "rotation_failed", rank=rank, reason=f"{pick_reason}; цена закрытия недоступна")
            return False
        fresh_pnl_pct = self._position_pnl_pct(victim, last_px=close_price)
        min_negative_pnl_pct = float(getattr(self.cfg, "rotation_min_negative_pnl_pct", 0.0) or 0.0)
        if bool(getattr(self.cfg, "rotation_require_negative_pnl", True)) and fresh_pnl_pct >= -abs(min_negative_pnl_pct):
            reason = f"{pick_reason}; перед закрытием PnL восстановился до {fresh_pnl_pct:.2f}%"
            self.stats_logger.log(
                "rotation_aborted_recovered",
                cycle_id=cycle_id,
                rank=rank,
                victim_inst_id=victim.inst_id,
                incoming_inst_id=candidate["inst_id"],
                victim_pnl_pct=round(float(fresh_pnl_pct), 4),
                reason=reason,
            )
            self._audit_signal(
                cycle_id,
                candidate["inst_id"],
                "rotation_aborted_recovered",
                rank=rank,
                reason=reason,
                victim_inst_id=victim.inst_id,
                victim_pnl_pct=round(float(fresh_pnl_pct), 4),
            )
            return False
        rotation_reason = f"Ротация под новый сигнал {candidate['inst_id']}"
        self.stats_logger.log(
            "rotation_started",
            cycle_id=cycle_id,
            rank=rank,
            victim_inst_id=victim.inst_id,
            victim_side=victim.side,
            victim_units=victim.units,
            victim_unrealized_pnl=float(getattr(victim, "unrealized_pnl", 0.0) or 0.0),
            incoming_inst_id=candidate["inst_id"],
            incoming_side=candidate["side"],
            incoming_system_name=candidate["system_name"],
            pick_reason=pick_reason,
        )
        self._audit_signal(
            cycle_id,
            candidate["inst_id"],
            "rotation_started",
            rank=rank,
            incoming_side=candidate["side"],
            incoming_system=candidate["system_name"],
            victim_inst_id=victim.inst_id,
            victim_units=victim.units,
            pick_reason=pick_reason,
        )
        self.close_position(victim, close_price, rotation_reason)
        if victim.inst_id in self.position_state:
            self.stats_logger.log(
                "rotation_failed",
                cycle_id=cycle_id,
                rank=rank,
                victim_inst_id=victim.inst_id,
                incoming_inst_id=candidate["inst_id"],
                reason="victim_position_still_open_after_close_attempt",
            )
            self._audit_signal(cycle_id, candidate["inst_id"], "rotation_failed", rank=rank, reason="позиция для ротации не закрылась", victim_inst_id=victim.inst_id)
            return False
        self.recent_rotation_exits[victim.inst_id] = time.time() + self._rotation_cooldown_seconds()
        self.log_line.emit(
            f"Ротация: закрыта {victim.inst_id} ({victim.units} юн.) ради нового сигнала {candidate['inst_id']}"
        )
        self.stats_logger.log(
            "rotation_completed",
            cycle_id=cycle_id,
            rank=rank,
            victim_inst_id=victim.inst_id,
            incoming_inst_id=candidate["inst_id"],
            incoming_side=candidate["side"],
            incoming_system_name=candidate["system_name"],
        )
        self._audit_signal(
            cycle_id,
            candidate["inst_id"],
            "rotation_completed",
            rank=rank,
            victim_inst_id=victim.inst_id,
            incoming_side=candidate["side"],
            incoming_system=candidate["system_name"],
        )
        return True

    def _entry_side_limits_ok(self, side: str) -> tuple[bool, str]:
        total_open = len(self.position_state)
        same_side_open = sum(1 for p in self.position_state.values() if str(getattr(p, "side", "")) == str(side))

        max_total = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)
        max_same_side = int(getattr(self.cfg, "max_open_positions_per_side", 0) or 0)

        if max_total > 0 and total_open >= max_total:
            return False, f"достигнут лимит открытых позиций: {total_open}/{max_total}"

        if max_same_side > 0 and same_side_open >= max_same_side:
            return False, f"достигнут лимит позиций по стороне {side}: {same_side_open}/{max_same_side}"

        return True, ""

    def _log_pyramid_diagnostic(self, state: PositionState, event: str, **payload) -> None:
        try:
            base = {
                "trade_id": getattr(state, "trade_id", ""),
                "inst_id": state.inst_id,
                "side": state.side,
                "units": int(getattr(state, "units", 0) or 0),
                "qty": float(getattr(state, "qty", 0.0) or 0.0),
                "avg_px": float(getattr(state, "avg_px", 0.0) or 0.0),
                "stop_price": float(getattr(state, "stop_price", 0.0) or 0.0),
                "next_pyramid_price": float(getattr(state, "next_pyramid_price", 0.0) or 0.0),
                "atr": float(getattr(state, "atr", 0.0) or 0.0),
                "has_locked_break_even": bool(self._has_locked_break_even(state)) if getattr(state, "atr", 0.0) > 0 else False,
            }
            base.update(payload or {})
            self.pyramid_diagnostics_logger.log(event, **base)
        except Exception:
            pass

    def _log_reentry_diagnostic(self, inst_id: str, side: str, **payload) -> None:
        try:
            base = {"inst_id": inst_id, "side": side, "timeframe": self.cfg.timeframe}
            base.update(payload or {})
            self.reentry_diagnostics_logger.log("reentry_check", **base)
        except Exception:
            pass


    def evaluate_entry(self, inst_id: str, cycle_id: Optional[int] = None) -> list[dict]:
        profile = self._tf_entry_profile()
        max_entry_period = max(self.cfg.long_entry_period, self.cfg.short_entry_period)
        max_exit_period = max(self.cfg.long_exit_period, self.cfg.short_exit_period)

        warmup_extra = max(6, int(getattr(self.cfg, "atr_warmup_extra_candles", 10) or 10))
        min_history = max(max_entry_period, self.cfg.atr_period + warmup_extra, max_exit_period, self.cfg.flat_lookback_candles + 4, 55)
        lookback = int(max(max_entry_period, self.cfg.atr_period, max_exit_period, self.cfg.flat_lookback_candles, 55) * profile["lookback_bonus"]) + warmup_extra
        lookback = max(lookback, min_history)

        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback)
        if len(candles) < min_history:
            reason = f"ATR warmup: недостаточно свечей {len(candles)}/{min_history}"
            if cycle_id is not None:
                self._bump_signal_funnel("warmup_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason=reason)
            return []

        last = candles[-1]
        prev_candle = candles[-2] if len(candles) >= 2 else last
        price = float(last[4])
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            reason = "ATR warmup: цена или ATR недоступны после прогрева"
            if cycle_id is not None:
                self._bump_signal_funnel("warmup_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason=reason)
            return []

        if self._is_rotation_recently_exited(inst_id):
            if cycle_id is not None:
                self._audit_signal(cycle_id, inst_id, "rejected", reason="инструмент недавно закрыт ротацией, повторный вход временно заблокирован")
            return []

        minimal_turtle_mode = self._minimal_turtle_entry_mode()
        structure_penalty = 0.0
        structure_penalty_reason = ""
        structure_metrics = {"false_breakouts": 0, "dense_base": False, "center_glue": False, "penalty": 0.0}
        vol_metrics = {
            "atr_pct": round((atr / max(price, 1e-12)) * 100.0, 6),
            "channel_atr_ratio": 0.0,
            "threshold_min_atr_pct": 0.0,
            "threshold_min_channel_atr_ratio": 0.0,
        }
        liquidity_metrics = {"profile_label": self._liquidity_thresholds().get("profile_label", str(self.cfg.timeframe)), "liquidity_filter_enabled": not minimal_turtle_mode}
        if not minimal_turtle_mode:
            flat_market, flat_reason = self.is_flat_market(candles, price, atr)
            if flat_market:
                channel_window = candles[-min(len(candles), max(20, int(self.cfg.flat_lookback_candles))):]
                highs = [float(c[2]) for c in channel_window]
                lows = [float(c[3]) for c in channel_window]
                channel_atr_ratio = ((max(highs) - min(lows)) / max(atr, 1e-12)) if highs and lows else 0.0
                near_score = max(0.0, min(1.0, channel_atr_ratio / max(float(self.cfg.flat_min_channel_atr_ratio), 1e-12)))
                self._register_near_pass_candidate(inst_id, "both", "flat_filter", near_score, flat_reason, breakout_distance_atr=round(channel_atr_ratio, 4), entry_period=max_entry_period)
                if cycle_id is not None:
                    self._bump_signal_funnel("flat_filter_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"flat filter: {flat_reason}", price=price, atr=atr)
                return []

            structure_risk, structure_reason, structure_metrics = self._detect_structure_risk(candles, atr)
            structure_penalty = float((structure_metrics or {}).get("penalty", 0.0) or 0.0)
            structure_penalty_reason = str((structure_metrics or {}).get("penalty_reason", "") or "")
            if structure_risk:
                self._register_near_pass_candidate(inst_id, "both", "structure_filter", 0.55, structure_reason, entry_period=max_entry_period)
                if cycle_id is not None:
                    self._bump_signal_funnel("structure_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"structure filter: {structure_reason}", price=price, atr=atr, **structure_metrics)
                return []

            vol_ok, vol_reason, vol_metrics = self._volatility_gate(candles, price, atr)
            if not vol_ok:
                if cycle_id is not None:
                    self._bump_signal_funnel(self._classify_rejection_bucket(vol_reason))
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=vol_reason, price=price, atr=atr, **vol_metrics)
                return []

            liquid_ok, liquid_reason, liquidity_metrics = self._check_liquidity(inst_id, price)
            if not liquid_ok:
                if cycle_id is not None and bool(getattr(self.cfg, "signal_audit_log_all_rejections", True)):
                    self._bump_signal_funnel("liquidity_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", reason=f"liquidity: {liquid_reason}", price=price, atr=atr, **{k: round(v, 6) if isinstance(v, float) else v for k, v in liquidity_metrics.items()})
                if inst_id in set(getattr(self.cfg, "execution_risk_watchlist", []) or []) or "top-of-book" in liquid_reason or "тонкий стакан" in liquid_reason or "пустой" in liquid_reason:
                    self._register_execution_risk(inst_id, liquid_reason, stage="entry_liquidity", severity=0.75, quarantine=False)
                logging.info("%s: пропуск входа, illiquidity-filter без бана (%s)", inst_id, liquid_reason)
                return []
        else:
            logging.debug("%s: minimal turtle mode active — non-Turtle entry filters are bypassed", inst_id)

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        last_high = float(last[2])
        last_low = float(last[3])
        prev_high = float(prev_candle[2])
        prev_low = float(prev_candle[3])

        systems = [
            {
                "name": "Turtle 20",
                "entry_period": int(self.cfg.short_entry_period),
                "exit_period": int(self.cfg.short_exit_period),
            },
            {
                "name": "Turtle 55",
                "entry_period": int(self.cfg.long_entry_period),
                "exit_period": int(self.cfg.long_exit_period),
            },
        ]

        signals = []
        for system in systems:
            entry_period = int(system["entry_period"])
            if entry_period <= 0:
                continue
            prev_window = candles[-entry_period - 1:-1]
            if len(prev_window) < entry_period:
                continue
            long_level = max(float(c[2]) for c in prev_window)
            short_level = min(float(c[3]) for c in prev_window)
            if last_high >= long_level and prev_high < long_level:
                signals.append({
                    "side": "long",
                    "level": long_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                    "freshness_score": max(0.0, (last_high - max(prev_high, long_level - atr * 0.01)) / max(atr, 1e-12)),
                })
            if last_low <= short_level and prev_low > short_level:
                signals.append({
                    "side": "short",
                    "level": short_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                    "freshness_score": max(0.0, (min(prev_low, short_level + atr * 0.01) - last_low) / max(atr, 1e-12)),
                })

        if not signals:
            if cycle_id is not None:
                self._bump_signal_funnel("breakout_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", reason="нет свежего пробоя Donchian на последней закрытой свече", price=price, atr=atr, last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8))
            return []

        signals.sort(key=lambda s: (-s["entry_period"], 0 if s["side"] == "long" else 1))

        candidates = []
        ticker = None
        active_liquidity = self._liquidity_thresholds()
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception:
            ticker = None
        bid_px = float((ticker or {}).get("bidPx") or 0.0)
        ask_px = float((ticker or {}).get("askPx") or 0.0)
        vol_24h = float((ticker or {}).get("volCcy24h") or (ticker or {}).get("vol24h") or 0.0)
        spread_pct = 0.0
        if bid_px > 0 and ask_px > 0:
            mid = (bid_px + ask_px) / 2.0
            if mid > 0:
                spread_pct = ((ask_px - bid_px) / mid) * 100.0
        liquidity_score = max(0.0, vol_24h / max(float(active_liquidity.get("min_24h_quote_volume") or 1.0), 1.0))
        if spread_pct > 0:
            liquidity_score += max(0.0, float(active_liquidity.get("max_spread_pct") or self.cfg.liquidity_max_spread_pct) / spread_pct)

        recent_trade_penalty = self._recent_trade_penalty(inst_id)
        self._log_reentry_diagnostic(inst_id, "scan", price=price, recent_trade_penalty=round(float(recent_trade_penalty), 6), recent_stopout_present=bool(self.recent_stopouts.get(inst_id)), final_decision_allow_true_false=True, final_reason="scan")

        for signal in signals:
            side = signal["side"]
            level = float(signal["level"])
            system_name = str(signal["system_name"])

            if side == "long" and cooldown_blocked_long:
                if cycle_id is not None:
                    self._bump_signal_funnel("other_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=cooldown_reason_long)
                logging.info("%s: %s long-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_long)
                continue
            if side == "short" and cooldown_blocked_short:
                if cycle_id is not None:
                    self._bump_signal_funnel("other_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=cooldown_reason_short)
                logging.info("%s: %s short-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_short)
                continue

            if minimal_turtle_mode:
                trend_ok, trend_reason, trend_metrics = True, "minimal_turtle_mode", {
                    "trend_slope_atr": 0.0,
                    "trend_spacing_pct": 0.0,
                    "ema20": 0.0,
                    "ema50": 0.0,
                    "trend_slope_threshold_atr": 0.0,
                }
            else:
                trend_ok, trend_reason, trend_metrics = self._trend_filter(candles, side, atr, price)
            if not trend_ok:
                slope_abs = abs(float(trend_metrics.get("trend_slope_atr", 0.0) or 0.0))
                near_score = max(0.0, min(1.0, slope_abs / 0.10))
                self._register_near_pass_candidate(inst_id, side, system_name, near_score, trend_reason, entry_period=signal["entry_period"])
                if cycle_id is not None:
                    self._bump_signal_funnel("trend_rejected")
                    self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=trend_reason, **trend_metrics)
                continue

            if int(signal["entry_period"]) == int(self.cfg.short_entry_period):
                skip_t20, skip_reason = self._skip_profitable_turtle20_reentry(inst_id)
                if skip_t20:
                    if cycle_id is not None:
                        self._bump_signal_funnel("other_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=skip_reason)
                    logging.info("%s: %s", inst_id, skip_reason)
                    continue

            ok, reason = self._confirm_breakout(candles, atr, side, level)
            if ok:
                breakout_distance = max(0.0, (price - level) / max(atr, 1e-12)) if side == "long" else max(0.0, (level - price) / max(atr, 1e-12))
                last_open = float(last[1])
                breakout_body_atr = abs(float(price) - float(last_open)) / max(atr, 1e-12)
                max_breakout_distance = min(float(getattr(self.cfg, "breakout_max_distance_atr", 0.50) or 0.50), float(getattr(self.cfg, "max_entry_distance_atr_hard", 1.50) or 1.50))
                if breakout_body_atr > float(getattr(self.cfg, "max_breakout_body_atr", 3.50) or 3.50):
                    late_reason = f"oversized breakout candle {breakout_body_atr:.2f} ATR > {float(getattr(self.cfg, 'max_breakout_body_atr', 3.50) or 3.50):.2f} ATR"
                    if cycle_id is not None:
                        self._bump_signal_funnel("breakout_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=late_reason, breakout_distance_atr=round(breakout_distance, 4), breakout_body_atr=round(breakout_body_atr, 4))
                    continue
                same_dir_seq = 0
                recent_slice = candles[-4:]
                for candle in reversed(recent_slice):
                    try:
                        c_open = float(candle[1]); c_close = float(candle[4])
                    except Exception:
                        continue
                    if side == "long" and c_close > c_open:
                        same_dir_seq += 1
                    elif side == "short" and c_close < c_open:
                        same_dir_seq += 1
                    else:
                        break
                if same_dir_seq >= 3:
                    late_reason = f"momentum chase blocked after {same_dir_seq} same-side candles"
                    if cycle_id is not None:
                        self._bump_signal_funnel("breakout_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=late_reason, breakout_distance_atr=round(breakout_distance, 4), breakout_body_atr=round(breakout_body_atr, 4))
                    continue
                breakout_id = self._make_breakout_id(inst_id, side, system_name, int(signal["entry_period"]), last[0], level)
                entry_allowed, entry_block_reason = self._check_entry_runtime_guards(inst_id, side, system_name, price, atr, breakout_id)
                if not entry_allowed:
                    self._log_reentry_diagnostic(inst_id, side, price=price, breakout_id=breakout_id, cooldown_blocked=True, final_decision_allow_true_false=False, final_reason=entry_block_reason)
                    if cycle_id is not None:
                        self._bump_signal_funnel("other_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=entry_block_reason, breakout_distance_atr=round(breakout_distance, 4))
                    continue
                if (not minimal_turtle_mode) and breakout_distance > max_breakout_distance:
                    late_reason = f"late breakout distance {breakout_distance:.2f} ATR > {max_breakout_distance:.2f} ATR"
                    self._register_near_pass_candidate(inst_id, side, system_name, 0.30, late_reason, breakout_distance_atr=round(breakout_distance, 4), entry_period=signal["entry_period"])
                    if cycle_id is not None:
                        self._bump_signal_funnel("breakout_rejected")
                        self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=late_reason, breakout_distance_atr=round(breakout_distance, 4))
                    logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, late_reason)
                    continue
                buffer_mult = 0.0 if minimal_turtle_mode else float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0)
                tf_sec_local = self._timeframe_seconds()
                if not minimal_turtle_mode:
                    if tf_sec_local <= 60:
                        buffer_mult *= 0.60
                    elif tf_sec_local <= 300:
                        buffer_mult *= 0.82
                entry_trigger_price = level + atr * buffer_mult if side == "long" else level - atr * buffer_mult
                quality_score = 0.0
                filter_profile = self._timeframe_filter_profile()
                preferred_min = float(filter_profile.get("preferred_breakout_distance_atr_min", getattr(self.cfg, "preferred_breakout_distance_atr_min", 0.05)) or 0.05)
                preferred_max = float(filter_profile.get("preferred_breakout_distance_atr_max", getattr(self.cfg, "preferred_breakout_distance_atr_max", 0.30)) or 0.30)
                if preferred_min <= breakout_distance <= preferred_max:
                    quality_score += 3.0
                elif breakout_distance < preferred_min:
                    quality_score += 1.2
                elif breakout_distance <= max_breakout_distance:
                    quality_score += 1.0
                atr_pct = float(vol_metrics.get("atr_pct", 0.0))
                if float(filter_profile.get("quality_atr_good_min", 0.18)) <= atr_pct <= float(filter_profile.get("quality_atr_good_max", 0.45)):
                    quality_score += 2.0
                elif float(filter_profile.get("quality_atr_good_max", 0.45)) < atr_pct <= float(filter_profile.get("quality_atr_ok_max", 0.80)):
                    quality_score += 1.0
                channel_ratio = float(vol_metrics.get("channel_atr_ratio", 0.0))
                if float(filter_profile.get("quality_channel_good_min", 1.6)) <= channel_ratio <= float(filter_profile.get("quality_channel_good_max", 4.5)):
                    quality_score += 2.0
                elif float(filter_profile.get("quality_channel_good_max", 4.5)) < channel_ratio <= float(filter_profile.get("quality_channel_ok_max", 7.5)):
                    quality_score += 0.8
                slope_atr = abs(float(trend_metrics.get("trend_slope_atr", 0.0) or 0.0))
                if slope_atr >= float(filter_profile.get("quality_slope_bonus_from", 0.18)):
                    quality_score += 1.0
                quality_score += min(2.0, float(signal.get("freshness_score", 0.0)))
                quality_score += min(1.0, liquidity_score / 8.0)
                quality_score -= recent_trade_penalty
                quality_score -= structure_penalty
                candidate = {
                    "inst_id": inst_id,
                    "side": side,
                    "price": price,
                    "entry_trigger_price": entry_trigger_price,
                    "atr": atr,
                    "system_name": system_name,
                    "entry_period": signal["entry_period"],
                    "exit_period": signal["exit_period"],
                    "reason": reason if not structure_penalty_reason else f"{reason}; structure penalty: {structure_penalty_reason}",
                    "breakout_distance_atr": breakout_distance,
                    "liquidity_score": liquidity_score,
                    "freshness_score": float(signal.get("freshness_score", 0.0)),
                    "recent_trade_penalty": recent_trade_penalty,
                    "liquidity_profile": str(active_liquidity.get("profile_label") or self.cfg.timeframe),
                    "trend_slope_atr": float(trend_metrics.get("trend_slope_atr", 0.0)),
                    "atr_pct": atr_pct,
                    "quality_score": round(quality_score, 6),
                    "structure_penalty": round(structure_penalty, 6),
                    "false_breakouts": int((structure_metrics or {}).get("false_breakouts", 0) or 0),
                    "dense_base": bool((structure_metrics or {}).get("dense_base", False)),
                    "center_glue": bool((structure_metrics or {}).get("center_glue", False)),
                    "breakout_id": breakout_id,
                    "breakout_level": level,
                    "breakout_candle_ts": str(last[0]),
                    "breakout_body_atr": breakout_body_atr,
                }
                candidates.append(candidate)
                if cycle_id is not None:
                    self._bump_signal_funnel("candidates")
                self._audit_signal(cycle_id, inst_id, "candidate", side=side, system_name=system_name, entry_period=signal["entry_period"], breakout_distance_atr=round(breakout_distance, 4), liquidity_score=round(liquidity_score, 4), freshness_score=round(float(signal.get("freshness_score", 0.0)), 4), recent_trade_penalty=round(recent_trade_penalty, 4), liquidity_profile=str(active_liquidity.get("profile_label") or self.cfg.timeframe), reason=candidate.get("reason"), breakout_buffer_atr=float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0), entry_trigger_price=round(entry_trigger_price, 8), donchian_high=round(long_level, 8), donchian_low=round(short_level, 8), breakout_level=round(level, 8), last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8), distance_to_high=round((long_level - price) / max(atr, 1e-12), 6), distance_to_low=round((price - short_level) / max(atr, 1e-12), 6), quality_score=round(float(candidate.get("quality_score", 0.0)), 4), structure_penalty=round(float(candidate.get("structure_penalty", 0.0)), 4), false_breakouts=int(candidate.get("false_breakouts", 0) or 0), dense_base=bool(candidate.get("dense_base", False)), center_glue=bool(candidate.get("center_glue", False)), breakout_id=candidate.get("breakout_id"), breakout_body_atr=round(float(candidate.get("breakout_body_atr", 0.0)),4), **trend_metrics, **vol_metrics)
                continue

            breakout_distance = max(0.0, (price - level) / max(atr, 1e-12)) if side == "long" else max(0.0, (level - price) / max(atr, 1e-12))
            near_score = max(0.0, 1.0 - min(1.0, abs(float(getattr(self.cfg, "breakout_buffer_atr", 0.0) or 0.0) - breakout_distance)))
            self._register_near_pass_candidate(inst_id, side, system_name, near_score, reason, breakout_distance_atr=round(breakout_distance, 4), entry_period=signal["entry_period"])
            self.stats_logger.log(
                "entry_rejected",
                cycle_id=cycle_id,
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                entry_period=signal["entry_period"],
                exit_period=signal["exit_period"],
                reason=reason,
            )
            if cycle_id is not None:
                self._bump_signal_funnel("breakout_rejected")
                self._audit_signal(cycle_id, inst_id, "rejected", side=side, system_name=system_name, reason=reason, donchian_high=round(long_level, 8), donchian_low=round(short_level, 8), breakout_level=round(level, 8), last_high=round(last_high, 8), last_low=round(last_low, 8), last_close=round(price, 8), prev_high=round(prev_high, 8), prev_low=round(prev_low, 8), distance_to_high=round((long_level - price) / max(atr, 1e-12), 6), distance_to_low=round((price - short_level) / max(atr, 1e-12), 6))
            logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, reason)

        return candidates

    def _set_manual_entry_decision(self, allowed: bool) -> None:
        self._manual_entry_allowed = bool(allowed)
        self._manual_entry_event.set()

    def request_manual_entry_approval(self, payload: dict) -> bool:
        self._manual_entry_allowed = False
        self._manual_entry_event.clear()
        try:
            self.entry_candidate.emit(payload)
        except Exception as exc:
            logging.warning("Failed to emit manual entry candidate: %s", exc)
            return False

        wait_sec = 120
        self.log_line.emit(
            f"{payload.get('inst_id')}: найден сигнал {payload.get('system_name')} {payload.get('side')} — ожидание решения в ручном режиме"
        )
        approved = self._manual_entry_event.wait(wait_sec)
        if not approved:
            self.log_line.emit(f"{payload.get('inst_id')}: сигнал пропущен — не получено решение за {wait_sec}с")
            return False
        if not self._manual_entry_allowed:
            self.log_line.emit(f"{payload.get('inst_id')}: сигнал пропущен пользователем")
            return False
        self.log_line.emit(f"{payload.get('inst_id')}: сигнал подтверждён пользователем")
        return True

    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        profile = self._tf_entry_profile()
        filter_profile = self._timeframe_filter_profile()
        strict_min = profile["strict_min"]
        strict_max = profile["strict_max"]

        lookback = min(len(candles), max(10, int(self.cfg.flat_lookback_candles * profile["lookback_bonus"])))
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

        candle_ranges = [max(float(c[2]) - float(c[3]), 1e-12) for c in window]
        body_ratios = [abs(float(c[4]) - float(c[1])) / rng for c, rng in zip(window, candle_ranges)]
        wick_ratios = [1.0 - br for br in body_ratios]
        avg_wick_ratio = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0.0

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

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.72

        # Блокируем только действительно мёртвый рынок.
        min_channel_range_pct = float(filter_profile.get("min_channel_range_pct", self.cfg.min_channel_range_pct) or self.cfg.min_channel_range_pct)
        min_atr_pct = float(filter_profile.get("min_atr_pct", self.cfg.min_atr_pct) or self.cfg.min_atr_pct)
        min_channel_atr_ratio = float(filter_profile.get("flat_min_channel_atr_ratio", self.cfg.flat_min_channel_atr_ratio) or self.cfg.flat_min_channel_atr_ratio)
        max_flip_ratio = float(filter_profile.get("max_direction_flip_ratio", self.cfg.max_direction_flip_ratio) or self.cfg.max_direction_flip_ratio)
        max_wick_ratio = float(filter_profile.get("flat_max_wick_to_range_ratio", self.cfg.flat_max_wick_to_range_ratio) or self.cfg.flat_max_wick_to_range_ratio)
        min_efficiency_ratio = float(filter_profile.get("min_efficiency_ratio", self.cfg.min_efficiency_ratio) or self.cfg.min_efficiency_ratio)

        if channel_range_pct < min_channel_range_pct * 0.60 * strict_min:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}% < {min_channel_range_pct * 0.60 * strict_min:.3f}%"
        if atr_pct < min_atr_pct * 0.68 * strict_min:
            return True, f"крайне низкий ATR {atr_pct:.3f}% < {min_atr_pct * 0.68 * strict_min:.3f}%"
        if channel_atr_ratio < min_channel_atr_ratio * 0.76 * strict_min:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f} < {min_channel_atr_ratio * 0.76 * strict_min:.2f}"

        hard_flags = []
        soft_flags = []

        # Оставляем только реально токсичные признаки шума.
        if flip_ratio > max_flip_ratio * strict_max:
            hard_flags.append(f"пила {flip_ratio:.0%}")

        if avg_wick_ratio > max_wick_ratio * strict_max:
            soft_flags.append(f"много теней {avg_wick_ratio:.2f}")
        if efficiency_ratio < min_efficiency_ratio * strict_min:
            soft_flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if volume_dry:
            soft_flags.append("затухающий объём")

        if len(hard_flags) >= 1 and len(soft_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if len(hard_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if channel_atr_ratio < min_channel_atr_ratio * 0.88 * strict_min and efficiency_ratio < min_efficiency_ratio * 0.85 * strict_min:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"

    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str, dict]:
        if len(candles) < 12:
            return False, "ok", {"false_breakouts": 0, "dense_base": False, "center_glue": False, "penalty": 0.0}

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)
        false_breaks = 0
        if swing_span <= atr * (1.8 * strict_min):
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

        base_touches_high = 0
        base_touches_low = 0
        top = max(highs)
        bottom = min(lows)
        threshold = atr * (0.30 * strict_min)

        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1

        dense_base = base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * (2.4 * strict_min)
        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * (0.34 * strict_min))
        center_glue = close_cluster >= max(8, int(len(closes) * 0.74))

        penalty = 0.0
        penalty_reasons = []
        hard_reject_from = max(4, int(getattr(self.cfg, "structure_false_breakouts_hard_reject_from", 6) or 6))
        penalty_from = max(1, int(getattr(self.cfg, "structure_false_breakouts_penalty_from", 3) or 3))
        if false_breaks >= hard_reject_from:
            return True, f"серия ложных выносов ({false_breaks})", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": 3.0}
        if false_breaks >= penalty_from:
            penalty += min(3.0, (false_breaks - penalty_from + 1) * 0.75)
            penalty_reasons.append(f"ложные выносы {false_breaks}")
        if dense_base:
            if bool(getattr(self.cfg, "structure_dense_base_as_penalty", True)):
                penalty += 2.0
                penalty_reasons.append("плотная база")
            else:
                return True, "слишком плотная база", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": penalty}
        if center_glue:
            if bool(getattr(self.cfg, "structure_center_glue_as_penalty", True)):
                penalty += 1.5
                penalty_reasons.append("центр диапазона")
            else:
                return True, "цена прилипла к центру диапазона", {"false_breakouts": false_breaks, "dense_base": dense_base, "center_glue": center_glue, "penalty": penalty}

        metrics = {
            "false_breakouts": false_breaks,
            "dense_base": dense_base,
            "center_glue": center_glue,
            "penalty": round(penalty, 4),
            "penalty_reason": "; ".join(penalty_reasons) if penalty_reasons else "",
        }
        return False, "ok", metrics

    def _confirm_breakout(self, candles: list, atr: float, side: str, level: float) -> tuple[bool, str]:
        """
        v081:
        В minimal Turtle mode держимся ближе к классике:
        свежий пробой Donchian на последней закрытой свече,
        закрытие должно быть за каналом, но без обязательного +ATR-буфера.
        """
        if not candles or len(candles) < 2:
            return False, "нет свечей"
        if atr <= 0:
            return False, "ATR недоступен"
        if side not in {"long", "short"}:
            return False, "неизвестная сторона"

        last = candles[-1]
        prev = candles[-2]
        last_open = float(last[1])
        last_high = float(last[2])
        last_low = float(last[3])
        last_close = float(last[4])
        prev_high = float(prev[2])
        prev_low = float(prev[3])
        body = abs(last_close - last_open)
        candle_range = max(last_high - last_low, 1e-12)

        if self._minimal_turtle_entry_mode():
            entry_period = int(self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period)
            if len(candles) < entry_period + 1:
                return False, "недостаточно свечей для Donchian-канала"

            window = candles[-(entry_period + 1):-1]
            highs = [float(c[2]) for c in window]
            lows = [float(c[3]) for c in window]
            if not highs or not lows:
                return False, "канал Donchian недоступен"

            upper = max(highs)
            lower = min(lows)
            channel_width_atr = (upper - lower) / max(atr, 1e-12)
            min_channel_width_atr = 0.50
            if channel_width_atr < min_channel_width_atr:
                return False, f"канал слишком узкий: {channel_width_atr:.2f} ATR < {min_channel_width_atr:.2f} ATR"

            prev_close = float(prev[4])
            if side == "long":
                if not is_fresh_breakout(prev_close, level, lower, "long"):
                    return False, "пробой не свежий: предыдущая свеча уже закрылась выше канала"
                if last_high < level:
                    return False, "нет пробоя уровня Donchian"
                if last_close <= level:
                    return False, "закрытие не удержалось выше канала"
                return True, "classic_turtle_breakout_long"

            if not is_fresh_breakout(prev_close, upper, level, "short"):
                return False, "пробой не свежий: предыдущая свеча уже закрылась ниже канала"
            if last_low > level:
                return False, "нет пробоя уровня Donchian"
            if last_close >= level:
                return False, "закрытие не удержалось ниже канала"
            return True, "classic_turtle_breakout_short"

        filter_profile = self._timeframe_filter_profile()
        breakout_buffer_mult = float(filter_profile.get("breakout_buffer_atr", getattr(self.cfg, "breakout_buffer_atr", 0.0)) or 0.0)
        breakout_buffer = max(atr * breakout_buffer_mult, abs(level) * 0.00004)
        min_body = atr * float(filter_profile.get("breakout_min_body_atr", getattr(self.cfg, "breakout_min_body_atr", 0.0)) or 0.0)
        min_body_ratio = float(filter_profile.get("min_body_to_range_ratio", getattr(self.cfg, "min_body_to_range_ratio", 0.0)) or 0.0)
        near_extreme = float(filter_profile.get("breakout_close_near_extreme_ratio", getattr(self.cfg, "breakout_close_near_extreme_ratio", 0.0)) or 0.0)
        max_prebreak_dist = float(filter_profile.get("breakout_max_prebreak_distance_atr", getattr(self.cfg, "breakout_max_prebreak_distance_atr", 999.0)) or 999.0)
        max_breakout_dist = float(filter_profile.get("breakout_max_distance_atr", getattr(self.cfg, "breakout_max_distance_atr", 999.0)) or 999.0)

        if side == "long":
            if prev_high >= level:
                return False, "пробой не свежий: предыдущая свеча уже была на уровне/выше канала"
            if (level - prev_high) / max(atr, 1e-12) > max_prebreak_dist:
                return False, "пробой слишком далёк от канала до сигнальной свечи"
            if last_high < level + breakout_buffer:
                return False, f"нет пробоя с буфером {breakout_buffer_mult:.2f} ATR"
            if min_body > 0 and body < min_body:
                return False, f"слишком маленькое тело свечи {body / max(atr, 1e-12):.2f} ATR"
            if min_body_ratio > 0 and (body / candle_range) < min_body_ratio:
                return False, f"тело свечи слишком мало к диапазону {body / candle_range:.2f} < {min_body_ratio:.2f}"
            if ((last_close - level) / max(atr, 1e-12)) > max_breakout_dist:
                return False, f"late breakout distance {(last_close - level) / max(atr, 1e-12):.2f} ATR > {max_breakout_dist:.2f} ATR"
            if near_extreme > 0 and (last_high - last_close) / candle_range > (1.0 - near_extreme):
                return False, "закрытие слишком далеко от верхнего экстремума"
            if last_close < level + breakout_buffer * 0.35:
                return False, "свеча не удержала пробой выше канала к закрытию"
            return True, "classic_turtle_buffered_breakout_long"

        if prev_low <= level:
            return False, "пробой не свежий: предыдущая свеча уже была на уровне/ниже канала"
        if (prev_low - level) / max(atr, 1e-12) > max_prebreak_dist:
            return False, "пробой слишком далёк от канала до сигнальной свечи"
        if last_low > level - breakout_buffer:
            return False, f"нет пробоя с буфером {breakout_buffer_mult:.2f} ATR"
        if min_body > 0 and body < min_body:
            return False, f"слишком маленькое тело свечи {body / max(atr, 1e-12):.2f} ATR"
        if min_body_ratio > 0 and (body / candle_range) < min_body_ratio:
            return False, f"тело свечи слишком мало к диапазону {body / candle_range:.2f} < {min_body_ratio:.2f}"
        if ((level - last_close) / max(atr, 1e-12)) > max_breakout_dist:
            return False, f"late breakout distance {(level - last_close) / max(atr, 1e-12):.2f} ATR > {max_breakout_dist:.2f} ATR"
        if near_extreme > 0 and (last_close - last_low) / candle_range > (1.0 - near_extreme):
            return False, "закрытие слишком далеко от нижнего экстремума"
        if last_close > level - breakout_buffer * 0.35:
            return False, "свеча не удержала пробой ниже канала к закрытию"
        return True, "classic_turtle_buffered_breakout_short"

    def _compute_turtle_regime(self) -> dict:
        probe_inst = "BTC-USDT-SWAP" if "BTC-USDT-SWAP" in self.gateway.swap_ids else (self.gateway.swap_ids[0] if self.gateway.swap_ids else "")
        if not probe_inst:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        try:
            candles = self.gateway.get_candles(
                probe_inst,
                self.cfg.timeframe,
                max(self.cfg.atr_period, self.cfg.long_entry_period, 32) + 8
            )
        except Exception:
            candles = []

        if len(candles) < max(self.cfg.atr_period + 2, 20):
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        price = float(candles[-1][4] or 0.0)
        if atr <= 0 or price <= 0:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        window = candles[-min(len(candles), max(20, self.cfg.flat_lookback_candles)):]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        channel = max(highs) - min(lows)
        channel_atr_ratio = channel / max(atr, 1e-12)
        atr_pct = (atr / price) * 100.0

        net_move = abs(closes[-1] - closes[0]) if len(closes) > 1 else 0.0
        travel = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / travel) if travel > 0 else 0.0

        center = (max(highs) + min(lows)) / 2.0
        breakout_pressure = abs(closes[-1] - center) / max(channel, 1e-12)

        score = 0
        if channel_atr_ratio >= 3.0:
            score += 1
        if efficiency_ratio >= 0.28:
            score += 1
        if atr_pct >= max(0.10, self.cfg.min_atr_pct * 0.75):
            score += 1
        if breakout_pressure >= 0.33:
            score += 1

        if score >= 3:
            label = "Трендовый"
        elif score == 2:
            label = "Нейтральный"
        else:
            label = "Флэт"

        return {
            "label": label,
            "score": score,
            "channel_atr_ratio": round(channel_atr_ratio, 2),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "atr_pct": round(atr_pct, 3),
            "instrument": probe_inst,
        }

    def calculate_atr_from_candles(self, candles: List[List[float]], period: int) -> float:
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            high = candles[i][2]
            low = candles[i][3]
            prev_close = candles[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        recent = trs[-period:]
        return sum(recent) / len(recent)

    def compute_atr(self, inst_id: str) -> float:
        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, self.cfg.atr_period + 5)
        return self.calculate_atr_from_candles(candles, self.cfg.atr_period)

    def _extract_available_usdt(self, account: dict) -> float:
        data = account.get("data", [])
        if not data:
            return 0.0
        root = data[0]
        details = root.get("details", []) or []
        for item in details:
            if str(item.get("ccy", "")).upper() == "USDT":
                for key in ("availBal", "availEq", "cashBal", "eq"):
                    try:
                        value = float(item.get(key) or 0.0)
                    except (TypeError, ValueError):
                        value = 0.0
                    if value > 0:
                        return value
        for key in ("availEq", "adjEq", "totalEq"):
            try:
                value = float(root.get(key) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value
        return 0.0

    def _extract_total_usdt(self, account: dict) -> float:
        data = account.get("data", [])
        if not data:
            return 0.0
        root = data[0]
        try:
            total = float(root.get("totalEq") or 0.0)
        except (TypeError, ValueError):
            total = 0.0
        if total > 0:
            return total
        return self._extract_available_usdt(account)

    def _extract_order_error(self, resp: dict) -> tuple[str, str]:
        data = resp.get("data", []) or []
        if not data:
            return str(resp.get("code") or ""), str(resp.get("msg") or "")
        first = data[0] or {}
        return str(first.get("sCode") or resp.get("code") or ""), str(first.get("sMsg") or resp.get("msg") or "")

    def _handle_order_rejection(self, inst_id: str, resp: dict, context: str = "ордер") -> None:
        code, message = self._extract_order_error(resp)
        safe_message = (message or "").strip()

        if code in OkxGateway.COMPLIANCE_RESTRICTION_CODES:
            self.blocked_instruments[inst_id] = message or "Local compliance restriction"
            if inst_id not in self.cfg.blacklist:
                self.cfg.blacklist.append(inst_id)
            self.log_line.emit(f"{inst_id}: исключён из сканирования из-за ограничений биржи ({code}: {safe_message})")
            logging.warning("Instrument %s blocked by exchange compliance: %s", inst_id, message)
            self._notify(
                f"🚫 Инструмент исключён биржей\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}"
            )
            return

        if code in OkxGateway.POSITION_LIMIT_ERROR_CODES:
            cooldown_sec = 6 * 60 * 60
            self.temp_blocked_until[inst_id] = time.time() + cooldown_sec
            self.blocked_instruments[inst_id] = safe_message or "Exchange open position limit reached"
            self.log_line.emit(f"{inst_id}: временно исключён из сканирования на 6 часов из-за лимита позиции биржи ({code}: {safe_message})")
            logging.warning("Instrument %s blocked by exchange position limit: %s", inst_id, message)
            self._notify(
                f"⚠️ Инструмент временно исключён\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}\n"
                f"Пауза: 6 часов"
            )
            return

        if code in OkxGateway.LOT_SIZE_ERROR_CODES:
            self.log_line.emit(f"{inst_id}: отклонение {context} из-за шага лота ({code}: {safe_message}). Инструмент пропущен до следующего цикла.")
            logging.warning("Lot size rejection for %s: %s", inst_id, message)
            self._notify(
                f"⚠️ Отклонение ордера по шагу лота\n\n"
                f"Инструмент: {inst_id}\n"
                f"Контекст: {context}\n"
                f"Код: {code}\n"
                f"Причина: {safe_message}"
            )
            return

        self.stats_logger.log("order_rejected", inst_id=inst_id, context=context, code=code, reason=safe_message or str(resp))
        self.log_line.emit(f"{inst_id}: биржа отклонила {context}: {resp}")
        self._notify(
            f"⚠️ Биржа отклонила {context}\n\n"
            f"Инструмент: {inst_id}\n"
            f"Код: {code}\n"
            f"Причина: {safe_message or str(resp)}"
        )

    def _log_execution_event(self, stage: str, **payload) -> None:
        record = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stage": str(stage or "")}
        record.update(payload)
        try:
            with EXECUTION_LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logging.warning("Failed to write execution log: %s", exc)

    def _entry_abort(self, inst_id: str, side: str, system_name: str, reason: str, **extra) -> bool:
        payload = {"inst_id": inst_id, "side": side, "system_name": system_name, "reason": str(reason or "unknown")}
        payload.update(extra)
        self._log_execution_event("entry_aborted", **payload)
        self.stats_logger.log("entry_aborted", **payload)
        try:
            self.log_line.emit(f"{inst_id}: вход отменён — {reason}")
        except Exception:
            pass
        return False

    def enter_position(self, inst_id: str, side: str, price: float, atr: float, system_name: str, candidate: Optional[dict] = None) -> bool:
        candidate = dict(candidate or {})
        self._log_execution_event("entry_attempt", inst_id=inst_id, side=side, system_name=system_name, candidate_price=price, candidate_atr=atr)
        account = self.gateway.get_account_balance(force=True)
        data = account.get("data", [])
        if not data:
            return self._entry_abort(inst_id, side, system_name, "account_data_empty", price=price, atr=atr)
        total_eq = self._extract_total_usdt(account)
        available_eq = self._extract_available_usdt(account)
        if total_eq <= 0 or available_eq <= 0:
            return self._entry_abort(inst_id, side, system_name, "account_equity_invalid", total_eq=total_eq, available_eq=available_eq, price=price, atr=atr)

        exposure_ok, exposure_reason = self._entry_side_limits_ok(side)
        if not exposure_ok:
            self.stats_logger.log(
                "entry_rejected",
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                reason=exposure_reason,
            )
            self.log_line.emit(f"{inst_id}: вход пропущен — {exposure_reason}")
            self._log_execution_event("entry_rejected", inst_id=inst_id, side=side, system_name=system_name, reason=exposure_reason, price=price, atr=atr)
            return False
        try:
            info = self.gateway.instrument_info(inst_id)
        except Exception as exc:
            return self._entry_abort(inst_id, side, system_name, "instrument_info_error", error=str(exc), price=price, atr=atr)
        ct_val = float(info.get("ctVal") or 1.0)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)

        try:
            live_ticker = self.gateway.get_ticker_data(inst_id) or {}
        except Exception as exc:
            return self._entry_abort(inst_id, side, system_name, "ticker_fetch_error", error=str(exc), price=price, atr=atr)
        live_price = float(live_ticker.get("last") or 0.0)
        if live_price > 0:
            price = live_price
        if price <= 0:
            return self._entry_abort(inst_id, side, system_name, "price_invalid", ticker=live_ticker, atr=atr)
        if atr <= 0:
            try:
                atr = float(candidate.get("atr") or 0.0)
            except Exception:
                atr = 0.0
        if atr <= 0:
            try:
                candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(int(getattr(self.cfg, "atr_period", 20) or 20) + 5, 30)) or []
                if len(candles) >= 2:
                    trs = []
                    prev_close = float(candles[0][4])
                    for row in candles[1:]:
                        hi = float(row[2]); lo = float(row[3]); cl = float(row[4])
                        tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
                        trs.append(tr)
                        prev_close = cl
                    period = max(2, int(getattr(self.cfg, "atr_period", 20) or 20))
                    if len(trs) >= period:
                        atr = float(statistics.fmean(trs[-period:]))
            except Exception as exc:
                self._log_execution_event("entry_atr_recalc_failed", inst_id=inst_id, side=side, system_name=system_name, error=str(exc))
        if atr <= 0:
            return self._entry_abort(inst_id, side, system_name, "atr_invalid", price=price, atr=atr)

        risk_amount = total_eq * (self.cfg.risk_per_trade_pct / 100.0)
        risk_per_contract = atr * ct_val * self.cfg.atr_stop_multiple
        if risk_per_contract <= 0 or ct_val <= 0:
            return self._entry_abort(inst_id, side, system_name, "risk_model_invalid", price=price, atr=atr, ct_val=ct_val, risk_per_contract=risk_per_contract)

        qty_by_risk = risk_amount / risk_per_contract
        max_notional = available_eq * (self.cfg.max_position_notional_pct / 100.0)
        qty_by_notional = max_notional / (price * ct_val)
        qty = min(qty_by_risk, qty_by_notional)
        if max_mkt_sz > 0:
            qty = min(qty, max_mkt_sz)
        qty = self.floor_to_step(qty, lot_sz)
        if qty < min_sz:
            return self._entry_abort(inst_id, side, system_name, "qty_below_min", price=price, atr=atr, qty=qty, min_sz=min_sz, lot_sz=lot_sz)

        order_side = "buy" if side == "long" else "sell"
        hard_block_reason = self._execution_hard_block_reason(inst_id)
        if hard_block_reason:
            return self._entry_abort(inst_id, side, system_name, hard_block_reason, price=price, atr=atr)
        bootstrap_stop_price = self._normalize_bootstrap_stop(inst_id, side, self._compute_bootstrap_stop(inst_id, side, system_name, price, atr), current_price=price)
        pending = self._make_pending_entry(inst_id, side, system_name, qty, price, atr, bootstrap_stop_price, execution_mode="market")
        attached_bootstrap_stop = self._build_attached_bootstrap_stop(inst_id, bootstrap_stop_price, current_price=price)
        self._log_execution_event("order_submit", inst_id=inst_id, side=side, system_name=system_name, qty=qty, price=price, atr=atr, stop_price=bootstrap_stop_price, pending_entry_id=pending.pending_entry_id, stop_mode="BOOTSTRAP", validation_result="normalized_pre_submit")
        try:
            resp = self.gateway.place_market_order(inst_id, order_side, qty, attached_stop=attached_bootstrap_stop)
        except Exception as exc:
            self.pending_entries.pop(pending.pending_entry_id, None)
            return self._entry_abort(inst_id, side, system_name, "order_submit_exception", error=str(exc), qty=qty, price=price, atr=atr)
        pending.entry_order_id = self._extract_order_id(resp)
        if resp.get("code") != "0":
            pending.status = "REJECTED"
            self._handle_order_rejection(inst_id, resp, "ордер")
            self.pending_entries.pop(pending.pending_entry_id, None)
            self._log_execution_event("order_rejected", inst_id=inst_id, side=side, system_name=system_name, qty=qty, price=price, atr=atr, response=resp)
            return False

        actual_entry_price, actual_qty = self._reconcile_live_fill(inst_id, side, price, qty)
        pending.status = "FILLED" if actual_qty > 0 else "PARTIALLY_FILLED"
        pending.avg_fill_price_current = actual_entry_price
        pending.filled_qty_current = actual_qty
        qty = actual_qty if actual_qty > 0 else qty
        price = actual_entry_price if actual_entry_price > 0 else price
        if price <= 0 or qty <= 0:
            self.pending_entries.pop(pending.pending_entry_id, None)
            return self._entry_abort(inst_id, side, system_name, "fill_invalid", price=price, qty=qty, atr=atr, response=resp)
        bootstrap_stop_price = self._normalize_bootstrap_stop(inst_id, side, self._compute_bootstrap_stop(inst_id, side, system_name, price, atr), current_price=price)
        atr_stop_price = price - self.cfg.atr_stop_multiple * atr if side == "long" else price + self.cfg.atr_stop_multiple * atr
        stop_price = bootstrap_stop_price
        next_pyramid = price + self.cfg.add_unit_every_atr * atr if side == "long" else price - self.cfg.add_unit_every_atr * atr
        entry_slippage_pct = (((price - pending.planned_entry_price) / max(pending.planned_entry_price, 1e-12)) * 100.0) if side == "long" else (((pending.planned_entry_price - price) / max(pending.planned_entry_price, 1e-12)) * 100.0)
        self.stats_logger.log("ENTRY_RECONCILED", pending_entry_id=pending.pending_entry_id, inst_id=inst_id, side=side, planned_entry_price=pending.planned_entry_price, actual_entry_price=price, planned_qty=pending.planned_qty, actual_qty=qty, entry_slippage_pct=entry_slippage_pct, execution_mode="market")
        self._log_execution_event("order_filled", inst_id=inst_id, side=side, system_name=system_name, pending_entry_id=pending.pending_entry_id, qty=qty, price=price, atr=atr, entry_slippage_pct=entry_slippage_pct)
        if system_name == "Turtle 55":
            entry_period = self.cfg.long_entry_period
            exit_period = self.cfg.long_exit_period
        elif system_name == "Turtle 20":
            entry_period = self.cfg.short_entry_period
            exit_period = self.cfg.short_exit_period
        else:
            entry_period = self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period
            exit_period = self.cfg.long_exit_period if side == "long" else self.cfg.short_exit_period

        trade_id = _stable_trade_id(inst_id, side, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        position_notional_usdt = price * qty * ct_val
        entry_context_payload = self._build_entry_context_payload(
            inst_id, side, price, atr, stop_price, next_pyramid, system_name, qty,
            trade_id=trade_id,
            risk_amount_usdt=risk_amount,
            risk_per_contract=risk_per_contract,
            planned_risk_pct=float(self.cfg.risk_per_trade_pct),
            position_notional_usdt=position_notional_usdt,
            qty_by_risk=qty_by_risk,
            qty_by_notional=qty_by_notional,
        )
        entry_context_file = self._save_entry_context(entry_context_payload)

        state = PositionState(
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=price,
            last_px=price,
            unrealized_pnl=0.0,
            margin=0.0,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            base_unit_qty=qty,
            signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            units=1,
            system_name=system_name,
            entry_period=entry_period,
            exit_period=exit_period,
            entry_context_file=entry_context_file,
            initial_stop_price=stop_price,
            bootstrap_stop_price=bootstrap_stop_price,
            peak_price=price,
            trough_price=price,
            peak_unrealized_pnl=0.0,
            peak_pnl_pct=0.0,
            trade_id=trade_id,
            planned_risk_pct=float(self.cfg.risk_per_trade_pct),
            risk_amount_usdt=risk_amount,
            risk_per_contract=risk_per_contract,
            position_notional_usdt=position_notional_usdt,
            planned_entry_px=float(getattr(pending, "planned_entry_price", price) or price),
            actual_entry_px=price,
            entry_slippage_pct=float(entry_slippage_pct),
            entry_execution_mode="market",
            stop_state="UNVERIFIED",
            position_health_state="STOP_UNVERIFIED",
            initial_stop_verified=False,
            initial_stop_set_ts=time.time(),
            initial_stop_verify_due_ts=time.time() + float(getattr(self.cfg, "initial_stop_verify_delay_sec", 12.0) or 12.0),
            exchange_stop_trigger_type="mark",
            exchange_stop_last_update_method="entry_attach",
            active_stop_mode="BOOTSTRAP",
            desired_stop_mode="BOOTSTRAP",
            stop_mode_since_ts=time.time(),
            stop_transition_reason="entry_bootstrap_attached",
        )
        self.position_state[inst_id] = state
        state.popup_snapshot_dirty = True
        state.exchange_stop_status = "attach_pending"
        state.exchange_stop_last_update_method = "entry_attach"
        state.exchange_stop_qty = float(qty or 0.0)
        state.exchange_stop_full_position = True
        self._log_stop_engine("STOP_INIT_ATTACHED_REQUESTED", state, requested_stop=stop_price, reason="entry_bootstrap_stop", attached_payload=attached_bootstrap_stop)
        self._update_stop_tracking(state, True, reason="initial_exchange_stop_attached", verified=False)
        self.pending_entries.pop(pending.pending_entry_id, None)
        self.position_journal_logger.log("OPEN", trade_id=trade_id, inst_id=inst_id, side=side, price=price, stop_price=stop_price, qty=qty, units=1, atr=atr, system_name=system_name, planned_risk_pct=float(self.cfg.risk_per_trade_pct), risk_amount_usdt=risk_amount, risk_per_contract=risk_per_contract, position_notional_usdt=position_notional_usdt, note="Первичный вход + bootstrap-stop")
        self._log_breakout_quality(inst_id, side, price, atr, system_name)
        self._save_state()
        self.stats_logger.log("position_opened", trade_id=trade_id, inst_id=inst_id, side=side, qty=qty, price=price, atr=atr, stop_price=stop_price, system_name=system_name, timeframe=self.cfg.timeframe, balance_total=total_eq, balance_available=available_eq, planned_risk_pct=float(self.cfg.risk_per_trade_pct), risk_amount_usdt=risk_amount, risk_per_contract=risk_per_contract, position_notional_usdt=position_notional_usdt)
        self.trade_logger.log("OPEN", inst_id, side, qty, price, atr, stop_price, system_name, "Первичный вход + bootstrap-stop")
        self.log_line.emit(f"Открыта {side} позиция {inst_id}, qty={qty}, ATR={atr:.6f}, bootstrap-stop={stop_price:.6f}")
        self._notify(
            f"{'📈' if side == 'long' else '📉'} Открыта {side.upper()} позиция\n\n"
            f"Инструмент: {inst_id}\n"
            f"Цена входа: {self._fmt_price(price)}\n"
            f"Qty: {qty}\n"
            f"ATR: {self._fmt_price(atr)}\n"
            f"Bootstrap-stop: {self._fmt_price(stop_price)}\n"
            f"Юнитов: 1\n"
            f"Система: {system_name}"
        )
        self._emit_snapshot_safe()
        return True

    def _build_entry_context_payload(self, inst_id: str, side: str, price: float, atr: float, stop_price: float, next_pyramid: float, system_name: str, qty: float, trade_id: str = "", risk_amount_usdt: float = 0.0, risk_per_contract: float = 0.0, planned_risk_pct: float = 0.0, position_notional_usdt: float = 0.0, qty_by_risk: float = 0.0, qty_by_notional: float = 0.0) -> dict:
        candles_payload = []
        try:
            candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(80, self.cfg.long_entry_period + 10)) or []
            candles_payload = candles[-80:]
        except Exception as exc:
            logging.warning("Failed to capture candles for entry context %s: %s", inst_id, exc)

        entry_period = self.cfg.long_entry_period if system_name == "Turtle 55" else self.cfg.short_entry_period
        exit_period = self.cfg.long_exit_period if system_name == "Turtle 55" else self.cfg.short_exit_period

        channel_high = None
        channel_low = None
        try:
            if len(candles_payload) >= max(2, entry_period + 1):
                ref_window = candles_payload[-entry_period - 1:-1]
                channel_high = max(float(c[2]) for c in ref_window)
                channel_low = min(float(c[3]) for c in ref_window)
        except Exception:
            channel_high = None
            channel_low = None

        body_atr_at_entry = 0.0
        body_to_range_ratio_at_entry = 0.0
        close_near_extreme_ratio_at_entry = 0.0
        breakout_distance_atr = 0.0
        atr_pct_at_entry = (atr / max(price, 1e-12)) * 100.0 if price > 0 else 0.0
        if candles_payload:
            try:
                last = candles_payload[-1]
                lo = float(last[3]); hi = float(last[2]); op = float(last[1]); cl = float(last[4])
                rng = max(hi - lo, 1e-12)
                body = abs(cl - op)
                body_atr_at_entry = body / max(atr, 1e-12)
                body_to_range_ratio_at_entry = body / rng
                close_near_extreme_ratio_at_entry = ((hi - cl) / rng) if side == "long" else ((cl - lo) / rng)
                if side == "long" and channel_high is not None:
                    breakout_distance_atr = max(0.0, (price - float(channel_high)) / max(atr, 1e-12))
                elif side == "short" and channel_low is not None:
                    breakout_distance_atr = max(0.0, (float(channel_low) - price) / max(atr, 1e-12))
            except Exception:
                pass

        return {
            "version": APP_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trade_id": trade_id or _stable_trade_id(inst_id, side, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "inst_id": inst_id,
            "side": side,
            "timeframe": self.cfg.timeframe,
            "system_name": system_name,
            "entry_price": price,
            "entry_price_fact": price,
            "initial_stop_price": stop_price,
            "atr": atr,
            "stop_price": stop_price,
            "next_pyramid_price": next_pyramid,
            "qty": qty,
            "risk_amount_usdt": risk_amount_usdt,
            "risk_per_contract": risk_per_contract,
            "planned_risk_pct": planned_risk_pct,
            "position_notional_usdt": position_notional_usdt,
            "qty_by_risk": qty_by_risk,
            "qty_by_notional": qty_by_notional,
            "entry_period": entry_period,
            "exit_period": exit_period,
            "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
            "add_unit_every_atr": getattr(self.cfg, "add_unit_every_atr", 0.5),
            "channel_high": channel_high,
            "channel_low": channel_low,
            "breakout_distance_atr": breakout_distance_atr,
            "channel_atr_ratio": ((float(channel_high) - float(channel_low)) / max(atr, 1e-12)) if channel_high is not None and channel_low is not None else 0.0,
            "atr_pct_at_entry": atr_pct_at_entry,
            "body_atr_at_entry": body_atr_at_entry,
            "body_to_range_ratio_at_entry": body_to_range_ratio_at_entry,
            "close_near_extreme_ratio_at_entry": close_near_extreme_ratio_at_entry,
            "breakout_level": float(channel_high if side == "long" and channel_high is not None else channel_low if side == "short" and channel_low is not None else 0.0),
            "breakout_id": "",
            "candles": candles_payload,
        }

    def _save_entry_context(self, payload: dict) -> str:
        try:
            safe_inst = str(payload.get("inst_id", "UNKNOWN")).replace("/", "_").replace(":", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = ENTRY_CONTEXT_DIR / f"{ts}_{safe_inst}_{payload.get('side', 'na')}.json"
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(file_path)
        except Exception as exc:
            logging.warning("Failed to save entry context for %s: %s", payload.get("inst_id"), exc)
            return ""

    def _position_initial_risk(self, state: PositionState) -> float:
        initial_stop = float(getattr(state, "initial_stop_price", 0.0) or 0.0)
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        if avg_px <= 0:
            return 0.0
        if initial_stop > 0:
            return max(abs(avg_px - initial_stop), 1e-12)
        atr = float(getattr(state, "atr", 0.0) or 0.0)
        mult = float(getattr(self.cfg, "atr_stop_multiple", 2.0) or 2.0)
        return max(atr * mult, 1e-12)

    def _position_r_multiple(self, state: PositionState, price: float) -> float:
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        if avg_px <= 0:
            return 0.0
        risk = self._position_initial_risk(state)
        move = (float(price) - avg_px) if str(getattr(state, "side", "")).lower() == "long" else (avg_px - float(price))
        return move / max(risk, 1e-12)

    def _update_position_extremes(self, state: PositionState, current_price: float) -> None:
        current_price = float(current_price or 0.0)
        if current_price <= 0:
            return
        if float(getattr(state, "peak_price", 0.0) or 0.0) <= 0.0:
            state.peak_price = max(current_price, float(getattr(state, "avg_px", current_price) or current_price))
        if float(getattr(state, "trough_price", 0.0) or 0.0) <= 0.0:
            state.trough_price = min(current_price, float(getattr(state, "avg_px", current_price) or current_price))

        if str(getattr(state, "side", "")).lower() == "long":
            state.peak_price = max(float(state.peak_price or current_price), current_price)
            state.trough_price = min(float(state.trough_price or current_price), current_price)
        else:
            state.peak_price = max(float(state.peak_price or current_price), current_price)
            state.trough_price = min(float(state.trough_price or current_price), current_price)

        current_upl = float(getattr(state, "unrealized_pnl", 0.0) or 0.0)
        if current_upl > float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0):
            state.peak_unrealized_pnl = current_upl
        current_pct = self._position_pnl_pct(state, last_px=current_price)
        if current_pct > float(getattr(state, "peak_pnl_pct", 0.0) or 0.0):
            state.peak_pnl_pct = current_pct

    def _trend_pullback_exit_reason(self, state: PositionState, current_price: float) -> str:
        if not bool(getattr(self.cfg, "trend_stop_use_peak_pullback_exit", True)):
            return ""
        activation_r = float(getattr(self.cfg, "trend_stop_activation_r", 0.80) or 0.80)
        max_pullback_r = float(getattr(self.cfg, "trend_stop_max_pullback_from_peak_r", 0.90) or 0.90)
        current_r = self._position_r_multiple(state, current_price)
        peak_anchor = float(getattr(state, "peak_price", 0.0) or 0.0) if state.side == "long" else float(getattr(state, "trough_price", 0.0) or 0.0)
        if peak_anchor <= 0:
            return ""
        peak_r = self._position_r_multiple(state, peak_anchor)
        if peak_r < activation_r:
            return ""
        if (peak_r - current_r) < max_pullback_r:
            return ""
        lock_floor_r = max(float(getattr(self.cfg, "trend_stop_min_locked_r", 0.35) or 0.35), peak_r - max_pullback_r)
        if current_r > lock_floor_r:
            return ""
        return f"Защита тренда: откат от пика {peak_r:.2f}R → {current_r:.2f}R"


    def _log_stop_engine(self, event: str, state: Optional[PositionState] = None, **payload) -> None:
        return self.stop_engine._log_stop_engine(event, state, **payload)

    def _extract_algo_id(self, resp: dict) -> str:
        return self.stop_engine._extract_algo_id(resp)

    def _exchange_stop_move_threshold(self, state: PositionState, target_stop: float) -> float:
        return self.stop_engine._exchange_stop_move_threshold(state, target_stop)

    def _clear_exchange_stop_state(self, state: PositionState, status: str = "") -> None:
        return self.stop_engine._clear_exchange_stop_state(state, status=status)

    def _market_allows_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0) -> bool:
        return self.stop_engine._market_allows_exchange_stop(state, target_stop, current_price=current_price)

    def _mark_local_protective_exit(self, state: PositionState, reason: str, current_price: float = 0.0, requested_stop: float = 0.0, response: Optional[dict] = None) -> None:
        return self.stop_engine._mark_local_protective_exit(state, reason, current_price=current_price, requested_stop=requested_stop, response=response)

    def _stop_registry_key(self, state: PositionState) -> tuple[str, str]:
        return self.stop_engine._stop_registry_key(state)

    def _row_stop_qty(self, row: Optional[dict]) -> float:
        return self.stop_engine._row_stop_qty(row)

    def _row_close_fraction(self, row: Optional[dict]) -> float:
        return self.stop_engine._row_close_fraction(row)

    def _exchange_stop_covers_full_position(self, state: PositionState, row: Optional[dict]) -> bool:
        return self.stop_engine._exchange_stop_covers_full_position(state, row)

    def _exchange_stop_row_is_valid(self, state: PositionState, row: Optional[dict], target_stop: float = 0.0, require_full_cover: bool = True) -> bool:
        return self.stop_engine._exchange_stop_row_is_valid(state, row, target_stop=target_stop, require_full_cover=require_full_cover)

    def _mark_exchange_stop_desync(self, state: PositionState, reason: str = "") -> None:
        return self.stop_engine._mark_exchange_stop_desync(state, reason=reason)

    def _clear_exchange_stop_desync(self, state: PositionState) -> None:
        return self.stop_engine._clear_exchange_stop_desync(state)

    def _with_stop_recovery_lock(self, state: PositionState, reason: str = "") -> bool:
        return self.stop_engine._with_stop_recovery_lock(state, reason=reason)

    def _release_stop_recovery_lock(self, state: PositionState, success: bool = False) -> None:
        return self.stop_engine._release_stop_recovery_lock(state, success=success)

    def _safe_short_stop_target(self, state: PositionState, target_stop: float, current_price: float = 0.0) -> float:
        return self.stop_engine._safe_short_stop_target(state, target_stop, current_price=current_price)

    def _force_replace_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0, reason: str = "") -> bool:
        return self.stop_engine._force_replace_exchange_stop(state, target_stop, current_price=current_price, reason=reason)

    def _find_existing_exchange_stop_row(self, state: PositionState, target_stop: float = 0.0) -> Optional[dict]:
        return self.stop_engine._find_existing_exchange_stop_row(state, target_stop=target_stop)

    def _attach_existing_exchange_stop(self, state: PositionState, row: Optional[dict], status: str = "active") -> bool:
        return self.stop_engine._attach_existing_exchange_stop(state, row, status=status)

    def _sync_stop_from_exchange_snapshot(self, state: PositionState, target_stop: float = 0.0, status: str = "active") -> bool:
        return self.stop_engine._sync_stop_from_exchange_snapshot(state, target_stop=target_stop, status=status)

    def _cancel_exchange_stop(self, state: PositionState, reason: str = "") -> bool:
        return self.stop_engine._cancel_exchange_stop(state, reason=reason)

    def _place_exchange_stop(self, state: PositionState, target_stop: float, reason: str = "") -> bool:
        return self.stop_engine._place_exchange_stop(state, target_stop, reason=reason)

    def _replace_exchange_stop_if_needed(self, state: PositionState, prev_stop_price: float, new_stop_price: float, current_price: float = 0.0, reason: str = "turtle_trailing_update") -> bool:
        return self.stop_engine._replace_exchange_stop_if_needed(state, prev_stop_price, new_stop_price, current_price=current_price, reason=reason)

    def _confirm_exchange_stop_absent(self, state: PositionState, attempts: int = 6, delay_sec: float = 0.25) -> bool:
        return self.stop_engine._confirm_exchange_stop_absent(state, attempts=attempts, delay_sec=delay_sec)

    def _confirm_exchange_stop_present(self, state: PositionState, target_stop: float, attempts: int = 6, delay_sec: float = 0.25) -> bool:
        return self.stop_engine._confirm_exchange_stop_present(state, target_stop, attempts=attempts, delay_sec=delay_sec)

    def _verify_initial_stop_if_needed(self, state: PositionState, current_price: float = 0.0) -> bool:
        return self.stop_engine._verify_initial_stop_if_needed(state, current_price=current_price)

    def _run_stop_health_check(self, state: PositionState, current_price: float = 0.0) -> bool:
        return self.stop_engine._run_stop_health_check(state, current_price=current_price)

    def _amend_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0, reason: str = "") -> bool:
        return self.stop_engine._amend_exchange_stop(state, target_stop, current_price=current_price, reason=reason)

    def _desired_stop_mode(self, state: PositionState) -> str:
        return self.stop_engine._desired_stop_mode(state)

    def _atr_stop_target(self, state: PositionState, current_price: float, candles: Optional[List[List[float]]] = None) -> float:
        return self.stop_engine._atr_stop_target(state, current_price, candles=candles)

    def _turtle_stop_target(self, state: PositionState, candles: List[List[float]]) -> float:
        return self.stop_engine._turtle_stop_target(state, candles)

    def _can_switch_to_turtle(self, state: PositionState, turtle_stop: float) -> bool:
        return self.stop_engine._can_switch_to_turtle(state, turtle_stop)

    def _stop_reconcile_required(self, state: PositionState, current_price: float = 0.0, candles: Optional[List[List[float]]] = None) -> bool:
        return self.stop_engine._stop_reconcile_required(state, current_price=current_price, candles=candles)

    def _run_stop_recovery(self, state: PositionState, current_price: float, candles: List[List[float]], reason: str = "runtime_reconcile") -> bool:
        return self.stop_engine._run_stop_recovery(state, current_price, candles, reason=reason)

    def _apply_stop_policy(self, state: PositionState, current_price: float, candles: List[List[float]], reason: str = "manage") -> None:
        return self.stop_engine._apply_stop_policy(state, current_price, candles, reason=reason)

    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:
        return self.stop_engine.update_and_maybe_exit_or_pyramid(state)

    def _entry_bar_closed(self, state: PositionState, candles: List[List[float]]) -> bool:
        if not candles:
            return False
        try:
            entry_ts = datetime.strptime(str(getattr(state, "entry_time", "")), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return False
        tf_sec = max(1, self._timeframe_seconds())
        last_closed_open_ts = int(float(candles[-1][0])) / 1000.0
        first_full_bar_open_ts = ((int(entry_ts) // tf_sec) + 1) * tf_sec
        return last_closed_open_ts >= first_full_bar_open_ts

    def _closed_bars_since_entry(self, state: PositionState, candles: List[List[float]]) -> int:
        if not candles:
            return 0
        try:
            entry_ts = datetime.strptime(str(getattr(state, "entry_time", "")), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return 0
        tf_sec = max(1, self._timeframe_seconds())
        first_full_bar_open_ts = ((int(entry_ts) // tf_sec) + 1) * tf_sec
        count = 0
        for candle in candles:
            try:
                open_ts = int(float(candle[0])) / 1000.0
            except Exception:
                continue
            if open_ts >= first_full_bar_open_ts:
                count += 1
        return count

    def _breakeven_ready(self, state: PositionState, atr: float, current_price: float, candles: List[List[float]]) -> bool:
        if not bool(getattr(self.cfg, "breakeven_enabled", True)):
            return False
        hold_bars = max(0, int(getattr(self.cfg, "breakeven_min_hold_bars", 1) or 1))
        if hold_bars > 0 and self._closed_bars_since_entry(state, candles) < hold_bars:
            return False
        min_profit_atr = float(getattr(self.cfg, "breakeven_min_profit_atr", 0.8) or 0.8)
        move_atr = ((float(current_price) - float(state.avg_px)) / max(atr, 1e-12)) if state.side == "long" else ((float(state.avg_px) - float(current_price)) / max(atr, 1e-12))
        if move_atr >= min_profit_atr:
            return True
        current_r = self._position_r_multiple(state, current_price)
        return current_r >= float(getattr(self.cfg, "breakeven_min_locked_r", 0.5) or 0.5)

    def trailing_stop(self, state: PositionState, atr: float, last_close: float, candles: Optional[List[List[float]]] = None) -> float:
        if atr <= 0:
            return state.stop_price

        current_stop = float(getattr(state, "stop_price", 0.0) or 0.0)
        initial_stop = float(getattr(state, "initial_stop_price", 0.0) or 0.0)
        if current_stop <= 0.0:
            current_stop = initial_stop
        entry_bar_closed = self._entry_bar_closed(state, candles or [])
        if bool(getattr(self.cfg, "disable_trailing_on_entry_bar", True)) and not entry_bar_closed:
            return current_stop or initial_stop

        peak_anchor = float(getattr(state, "peak_price", 0.0) or 0.0) if state.side == "long" else float(getattr(state, "trough_price", 0.0) or 0.0)
        if peak_anchor <= 0:
            peak_anchor = float(last_close or state.last_px or state.avg_px or 0.0)

        stop_multiple = float(self.cfg.atr_stop_multiple)
        if state.side == "long":
            candidate = peak_anchor - stop_multiple * atr
            if initial_stop > 0.0:
                candidate = max(candidate, initial_stop)
            return max(current_stop, candidate)

        candidate = peak_anchor + stop_multiple * atr
        if initial_stop > 0.0:
            candidate = min(candidate, initial_stop)
        return min(current_stop, candidate) if current_stop else candidate

    def _pyramid_unit_scale(self, current_units: int) -> float:
        if current_units <= 1:
            return self.cfg.pyramid_second_unit_scale
        if current_units == 2:
            return self.cfg.pyramid_third_unit_scale
        return self.cfg.pyramid_fourth_unit_scale

    def _has_locked_break_even(self, state: PositionState) -> bool:
        buffer = max(state.atr * self.cfg.pyramid_break_even_buffer_atr, state.avg_px * 0.0002)
        if state.side == "long":
            return state.stop_price >= state.avg_px + buffer
        return state.stop_price <= state.avg_px - buffer


    def _trend_confirms_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> tuple[bool, str]:
        if not candles:
            return False, "нет свечей для подтверждения"
        if state.atr <= 0:
            return False, "ATR недоступен"

        progress = abs(last_close - state.avg_px)
        if progress < state.atr * self.cfg.pyramid_min_progress_atr:
            return False, f"недостаточный прогресс {progress / state.atr:.2f} ATR"

        distance_to_stop = abs(last_close - state.stop_price)
        if distance_to_stop < state.atr * self.cfg.pyramid_min_stop_distance_atr:
            return False, f"слишком близко к стопу {distance_to_stop / state.atr:.2f} ATR"

        # Ближе к классической Turtle:
        # не требуем body-ratio, flat-check и микроструктурных подтверждений.
        return True, ""


    def _lock_profit_after_pyramid(self, state: PositionState, fill_price: float) -> None:
        return

    def try_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]], candle_ts: int = 0) -> None:
        self._log_pyramid_diagnostic(state, "pyramid_strategy_check", reason_blocked="", last_price=last_close, note=f"candle_ts={candle_ts}")
        if str(getattr(state, "stop_state", "")) != "ACTIVE":
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="stop_not_active", last_price=last_close, note=str(getattr(state, "pyramiding_block_reason", "") or getattr(state, "stop_state", "UNVERIFIED")))
            return
        if str(getattr(state, "position_health_state", "HEALTHY")) != "HEALTHY":
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="position_health_not_ready", last_price=last_close, note=str(getattr(state, "position_health_state", "")))
            return
        if self.cfg.max_units_per_symbol > 0 and state.units >= self.cfg.max_units_per_symbol:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="max_units_reached", last_price=last_close)
            return
        if state.atr <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="position_not_eligible", last_price=last_close, note="atr_unavailable")
            return

        should_add = (state.side == "long" and last_close >= state.next_pyramid_price) or (
            state.side == "short" and last_close <= state.next_pyramid_price
        )
        distance_to_next = ((last_close - state.next_pyramid_price) / max(state.atr, 1e-12)) if state.side == "long" else ((state.next_pyramid_price - last_close) / max(state.atr, 1e-12))
        if not should_add:
            return

        allowed, reason = self._trend_confirms_pyramid(state, last_close, candles)
        if not allowed:
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason=reason, reason_code=_classify_reason_code(reason), last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            block_code = "trend_not_confirmed"
            if "прогресс" in reason:
                block_code = "progress_below_threshold"
            elif "стоп" in reason:
                block_code = "stop_distance_too_small"
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked=block_code, last_price=last_close, distance_to_next_add_atr=round(distance_to_next, 6), unrealized_r=round(self._position_r_multiple(state, last_close), 6), mfe_r=round(self._position_r_multiple(state, getattr(state, "peak_price", last_close) if state.side == "long" else getattr(state, "trough_price", last_close)), 6), note=reason)
            self.log_line.emit(f"{state.inst_id}: добор пропущен — {reason}")
            return

        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)
        scale = float(self._pyramid_unit_scale(state.units) or 1.0)
        add_qty = max(float(getattr(state, "base_unit_qty", 0.0) or 0.0) * scale, 0.0)
        if max_mkt_sz > 0:
            add_qty = min(add_qty, max_mkt_sz)
        add_qty = self.floor_to_step(add_qty, lot_sz)
        if add_qty < min_sz or add_qty <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="position_not_eligible", last_price=last_close, note="qty_below_min", proposed_qty=add_qty)
            return

        order_side = "buy" if state.side == "long" else "sell"
        pending = self._make_pending_entry(state.inst_id, state.side, state.system_name, add_qty, last_close, state.atr, state.stop_price, execution_mode="market")
        resp = self.gateway.place_market_order(state.inst_id, order_side, add_qty)
        pending.entry_order_id = self._extract_order_id(resp)
        if resp.get("code") != "0":
            pending.status = "REJECTED"
            self.pending_entries.pop(pending.pending_entry_id, None)
            self._handle_order_rejection(state.inst_id, resp, "добор")
            self.stats_logger.log("pyramid_skipped", inst_id=state.inst_id, side=state.side, units=state.units, reason="order_rejected", reason_code=str(resp.get("code") or "order_rejected"), last_price=last_close, next_pyramid_price=state.next_pyramid_price)
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="order_rejected", last_price=last_close, note=str(resp), proposed_qty=add_qty)
            return

        fill_price, live_qty = self._reconcile_live_fill(state.inst_id, state.side, last_close, state.qty + add_qty)
        pending.status = "FILLED"
        pending.avg_fill_price_current = fill_price
        pending.filled_qty_current = live_qty
        old_qty = float(state.qty)
        new_qty = float(live_qty if live_qty > 0 else (old_qty + add_qty))
        if new_qty <= 0:
            self._log_pyramid_diagnostic(state, "pyramid_blocked", reason_blocked="unknown", last_price=last_close, note="new_qty_non_positive")
            return

        if live_qty > 0 and fill_price > 0:
            state.avg_px = fill_price
            state.last_px = fill_price
        else:
            state.avg_px = ((state.avg_px * old_qty) + (fill_price * add_qty)) / new_qty
            state.last_px = fill_price
        prev_stop_cover_qty = float(getattr(state, "exchange_stop_qty", 0.0) or 0.0)
        state.qty = new_qty
        state.units += 1
        if prev_stop_cover_qty > 0.0:
            state.exchange_stop_qty = prev_stop_cover_qty
            state.exchange_stop_full_position = False
            state.exchange_stop_status = "partial_coverage_fault"
        state.position_notional_usdt = float(getattr(state, "position_notional_usdt", 0.0) or 0.0) + fill_price * add_qty * ct_val
        state.actual_entry_px = float(state.avg_px or fill_price)
        self.pending_entries.pop(pending.pending_entry_id, None)
        state.next_pyramid_price = fill_price + self.cfg.add_unit_every_atr * state.atr if state.side == "long" else fill_price - self.cfg.add_unit_every_atr * state.atr
        self._update_position_extremes(state, fill_price)
        self._lock_profit_after_pyramid(state, fill_price)

        self.position_journal_logger.log("ADD_UNIT", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=fill_price, stop_price=state.stop_price, qty=state.qty, add_qty=add_qty, units=state.units, atr=state.atr, next_pyramid_price=state.next_pyramid_price, note="Добор по Turtle")
        self.stats_logger.log("pyramid_added", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, qty=state.qty, add_qty=add_qty, price=fill_price, stop_price=state.stop_price, units=state.units, next_pyramid_price=state.next_pyramid_price)
        self.trade_logger.log("ADD", state.inst_id, state.side, add_qty, fill_price, state.atr, state.stop_price, state.system_name, f"Добор до {state.units} юнитов")
        self._log_pyramid_diagnostic(state, "pyramid_added", reason_blocked="", last_price=fill_price, add_qty=add_qty, distance_to_next_add_atr=round(distance_to_next, 6), unrealized_r=round(self._position_r_multiple(state, fill_price), 6), mfe_r=round(self._position_r_multiple(state, getattr(state, "peak_price", fill_price) if state.side == "long" else getattr(state, "trough_price", fill_price)), 6), note=f"candle_ts={candle_ts}")
        prev_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
        self._apply_stop_policy(state, last_close, candles, reason="pyramid_closed_candle")
        if float(getattr(state, "exchange_stop_price", 0.0) or 0.0) > 0.0 and abs(float(getattr(state, "exchange_stop_price", 0.0) or 0.0) - prev_exchange_stop) > 1e-12:
            time.sleep(1.0)
        self.log_line.emit(f"{state.inst_id}: добавлен юнит #{state.units}, qty+={add_qty}, новый stop={state.stop_price:.6f}")
        self._save_state()
        self._emit_snapshot_safe()



    def _closed_trade_already_registered(self, state: PositionState) -> bool:
        trade_id = str(getattr(state, "trade_id", "") or "").strip()
        inst_id = str(getattr(state, "inst_id", "") or "").strip()
        side = str(getattr(state, "side", "") or "").strip()
        for trade in reversed(self.closed_trades[-500:]):
            if trade_id and str(getattr(trade, "trade_id", "") or "").strip() == trade_id:
                return True
            if not trade_id and inst_id and side and str(getattr(trade, "inst_id", "") or "").strip() == inst_id and str(getattr(trade, "side", "") or "").strip() == side:
                return True
        return False

    def _reset_missing_exchange_tracking(self, state: Optional[PositionState]) -> bool:
        if state is None:
            return False
        changed = False
        if int(getattr(state, "missing_on_exchange_count", 0) or 0) != 0:
            state.missing_on_exchange_count = 0
            changed = True
        if str(getattr(state, "missing_on_exchange_since", "") or ""):
            state.missing_on_exchange_since = ""
            changed = True
        if float(getattr(state, "missing_on_exchange_last_seen_price", 0.0) or 0.0) != 0.0:
            state.missing_on_exchange_last_seen_price = 0.0
            changed = True
        return changed

    def _mark_position_missing_on_exchange(self, state: PositionState) -> tuple[int, str, float]:
        count = int(getattr(state, "missing_on_exchange_count", 0) or 0) + 1
        state.missing_on_exchange_count = count
        if not str(getattr(state, "missing_on_exchange_since", "") or ""):
            state.missing_on_exchange_since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fallback_price = float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        if fallback_price > 0.0:
            state.missing_on_exchange_last_seen_price = fallback_price
        reason = "SYNC confirmed close after exchange absence"
        stop_state = str(getattr(state, "stop_state", "") or "").upper()
        health_state = str(getattr(state, "position_health_state", "") or "").upper()
        local_reason = str(getattr(state, "local_protective_exit_reason", "") or "").strip()
        absence_synced = bool(getattr(state, "position_absence_synced", False))
        if local_reason:
            reason = f"SYNC confirmed close after protective exit: {local_reason}"
        elif bool(getattr(state, "close_pending", False)):
            reason = "SYNC confirmed close after pending request"
        elif absence_synced:
            reason = f"SYNC confirmed close after exchange-confirmed absence: {stop_state or health_state or 'position_absent_on_exchange'}"
        elif stop_state in {"ERROR", "MISSING"} or health_state in {"STOP_UNVERIFIED", "ERROR"}:
            reason = f"SYNC confirmed close after stop fault: {stop_state or health_state or 'unknown'}"
        self.position_journal_logger.log(
            "CLOSE_MISSING_ON_EXCHANGE",
            trade_id=str(getattr(state, "trade_id", "") or ""),
            inst_id=state.inst_id,
            side=state.side,
            price=fallback_price,
            stop_price=float(getattr(state, "stop_price", 0.0) or 0.0),
            qty=float(getattr(state, "qty", 0.0) or 0.0),
            units=int(getattr(state, "units", 0) or 0),
            reason=reason,
            note=f"missing_count={count}",
        )
        self.stats_logger.log(
            "close_pending_exchange",
            trade_id=str(getattr(state, "trade_id", "") or ""),
            inst_id=state.inst_id,
            side=state.side,
            qty=float(getattr(state, "qty", 0.0) or 0.0),
            price=fallback_price,
            reason=reason,
            missing_count=count,
            close_pending=bool(getattr(state, "close_pending", False)),
            local_protective_exit_pending=bool(getattr(state, "local_protective_exit_pending", False)),
            stop_state=str(getattr(state, "stop_state", "") or ""),
            position_health_state=str(getattr(state, "position_health_state", "") or ""),
        )
        self.log_line.emit(f"{state.inst_id}: позиция отсутствует на бирже, подтверждаю закрытие через sync ({count})")
        return count, reason, fallback_price

    def _finalize_closed_trade(self, state: PositionState, price: float, reason: str, candles: Optional[List[List[float]]] = None) -> None:
        if state is None:
            return
        if self._closed_trade_already_registered(state):
            if state.inst_id in self.position_state:
                del self.position_state[state.inst_id]
            self.close_retry_after.pop(state.inst_id, None)
            self._save_state()
            self._emit_snapshot_safe()
            return
        state.close_pending = False
        state.close_requested_at = ""
        state.last_close_error = ""
        self._reset_missing_exchange_tracking(state)
        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)

        pnl = ((price - state.avg_px) * state.qty * ct_val) if state.side == "long" else ((state.avg_px - price) * state.qty * ct_val)

        estimated_notional = max(state.avg_px * state.qty * ct_val, 0.0)
        estimated_margin = estimated_notional / max(float(self.cfg.leverage or 1), 1.0)
        if estimated_margin > 0:
            pnl_pct = (pnl / estimated_margin) * 100.0
        else:
            pnl_pct = 0.0

        self.stats_logger.log("position_closed", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason, reason_code=_classify_reason_code(reason))
        self.trade_logger.log("CLOSE", state.inst_id, state.side, state.qty, price, state.atr, state.stop_price, state.system_name, reason)
        self.position_journal_logger.log("CLOSE", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=price, stop_price=state.stop_price, qty=state.qty, units=state.units, unrealized_pnl=state.unrealized_pnl, peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0), reason=reason, note="Выход из позиции")
        duration_sec = 0
        try:
            duration_sec = max(0, int((datetime.now() - datetime.strptime(state.entry_time, "%Y-%m-%d %H:%M:%S")).total_seconds()))
        except Exception:
            duration_sec = 0
        trade_context_payload = self._build_trade_lifecycle_payload(state, price, reason, pnl, pnl_pct, duration_sec, candles=candles)
        trade_context_file = self._save_trade_context(trade_context_payload)
        self.closed_trades.append(ClosedTrade(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inst_id=state.inst_id,
            side=state.side,
            qty=state.qty,
            entry_px=state.avg_px,
            exit_px=price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            units=state.units,
            system_name=state.system_name,
            reason=reason,
            duration_sec=duration_sec,
            trade_context_file=trade_context_file,
            trade_id=str(getattr(state, "trade_id", "") or trade_context_payload.get("trade_id") or ""),
            stop_confirmed=bool(str(getattr(state, "stop_state", "") or "").upper() in {"ACTIVE", "CONFIRMED"}),
            stop_state=str(getattr(state, "stop_state", "") or ""),
            position_health_state=str(getattr(state, "position_health_state", "") or ""),
            block_reason=str(getattr(state, "pyramiding_block_reason", "") or ""),
            entry_distance_atr=float(getattr(state, "breakout_distance_atr", 0.0) or trade_context_payload.get("breakout_distance_atr") or 0.0),
        ))
        self.closed_trades = self.closed_trades[-500:]
        self.log_line.emit(f"Позиция {state.inst_id} закрыта. Причина: {reason}")
        self._clear_exchange_stop_state(state, status="closed")
        self._register_stopout(state, price, reason)
        self._register_entry_runtime_guard(state.inst_id, state.side, state.system_name, float(getattr(state, "avg_px", 0.0) or 0.0), float(getattr(state, "atr", 0.0) or 0.0), str(getattr(state, "breakout_id", "") or ""), reason)
        self._register_loss_streak(state.inst_id, state.side, pnl)
        self.position_journal_logger.log("CLOSED_TRADE_REGISTERED", trade_id=str(getattr(state, "trade_id", "") or ""), inst_id=state.inst_id, side=state.side, price=price, stop_price=state.stop_price, qty=state.qty, units=state.units, reason=reason, note=f"closed_trades_total={len(self.closed_trades)}")
        self.stats_logger.log("closed_trade_registered", trade_id=str(getattr(state, "trade_id", "") or ""), inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, pnl=pnl, pnl_pct=pnl_pct, reason=reason, closed_trades_total=len(self.closed_trades))

        emoji = "✅" if pnl >= 0 else "❌"
        try:
            self._cancel_exchange_stop(state, reason=f"post_close:{reason}")
        except Exception as exc:
            logging.warning("Post-close stop cancel failed for %s: %s", state.inst_id, exc)

        self._notify(
            f"{emoji} Позиция закрыта\n\n"
            f"Инструмент: {state.inst_id}\n"
            f"Сторона: {state.side.upper()}\n"
            f"Цена входа: {self._fmt_price(state.avg_px)}\n"
            f"Цена выхода: {self._fmt_price(price)}\n"
            f"PnL: {pnl:.4f}\n"
            f"PnL %: {pnl_pct:.2f}%\n"
            f"Юнитов: {state.units}\n"
            f"Причина: {reason}"
        )

        if state.inst_id in self.position_state:
            del self.position_state[state.inst_id]
            self.close_retry_after.pop(state.inst_id, None)
            self._save_state()
        self._emit_snapshot_safe()

    def close_position(self, state: PositionState, price: float, reason: str, candles: Optional[List[List[float]]] = None) -> None:
        state.close_attempts = int(getattr(state, "close_attempts", 0) or 0) + 1
        state.close_requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.last_close_error = ""
        resp = self.gateway.close_position(state.inst_id, reason, auto_cancel=True)
        if resp.get("code") != "0":
            code, message = self._extract_order_error(resp)
            safe_message = (message or resp.get("msg") or str(resp)).strip()

            if code in OkxGateway.CLOSE_REQUIRES_PENDING_CANCEL_CODES:
                cancel_resp = self.gateway.cancel_pending_close_orders(state.inst_id)
                self.log_line.emit(f"{state.inst_id}: перед закрытием отменяю pending close-orders ({code}: {safe_message})")
                self.stats_logger.log(
                    "close_pending_orders_cancel",
                    inst_id=state.inst_id,
                    side=state.side,
                    reason=reason,
                    exchange_code=code,
                    exchange_message=safe_message,
                    cancel_result=cancel_resp.get("msg", ""),
                    cancel_code=cancel_resp.get("code", ""),
                )
                retry_resp = self.gateway.close_position(state.inst_id, f"{reason} | retry_after_cancel", auto_cancel=True)
                if retry_resp.get("code") == "0":
                    resp = retry_resp
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    retry_code, retry_message = self._extract_order_error(retry_resp)
                    retry_safe_message = (retry_message or retry_resp.get("msg") or str(retry_resp)).strip()
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    state.last_close_error = retry_safe_message
                    self.log_line.emit(f"{state.inst_id}: повторное закрытие после отмены заявок не удалось: {retry_resp}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\n\n"
                        f"Инструмент: {state.inst_id}\n"
                        f"Причина: {safe_message}\n"
                        f"Повторная попытка: {retry_safe_message}"
                    )
                    return
            elif code in OkxGateway.CLOSE_MARKET_LIMIT_ERROR_CODES:
                fallback = self.gateway.close_position_by_reduce_only(state.inst_id, state.side, state.qty)
                if fallback.get("code") == "0":
                    self.log_line.emit(f"{state.inst_id}: позиция закрыта reduce-only ордерами из-за лимита market close")
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    state.last_close_error = str(fallback)
                    self.log_line.emit(f"{state.inst_id}: ошибка закрытия reduce-only: {fallback}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\n\n"
                        f"Инструмент: {state.inst_id}\n"
                        f"Причина: {safe_message}\n"
                        f"Fallback: {fallback}"
                    )
                    return
            else:
                if code == "51023":
                    self.close_retry_after.pop(state.inst_id, None)
                    self.log_line.emit(f"{state.inst_id}: позиция уже отсутствует на бирже, локальное состояние синхронизировано")
                    self.stats_logger.log(
                        "close_position_already_absent",
                        trade_id=getattr(state, "trade_id", ""),
                        inst_id=state.inst_id,
                        side=state.side,
                        reason=reason,
                        exchange_code=code,
                        exchange_message=safe_message,
                    )
                    resp = {"code": "0", "msg": "position_already_absent"}
                else:
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    state.last_close_error = safe_message
                    self.log_line.emit(f"{state.inst_id}: ошибка закрытия: {resp}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\n\n"
                        f"Инструмент: {state.inst_id}\n"
                        f"Причина: {safe_message}"
                    )
                    return

        self._finalize_closed_trade(state, price, reason, candles=candles)

    def _load_json_file(self, path_value: str) -> dict:
        try:
            path = Path(str(path_value or '').strip())
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Failed to load json context %s: %s", path_value, exc)
        return {}

    def _build_trade_lifecycle_payload(self, state: PositionState, exit_price: float, reason: str, pnl: float, pnl_pct: float, duration_sec: int, candles: Optional[List[List[float]]] = None) -> dict:
        entry_payload = self._load_json_file(getattr(state, 'entry_context_file', ''))
        entry_candles = list(entry_payload.get('candles') or [])

        tf_sec = max(60, self._timeframe_seconds())
        bars_in_trade = max(1, int(max(duration_sec, tf_sec) / tf_sec) + 6)
        desired_limit = min(320, max(96, bars_in_trade + 24, (state.entry_period or 0) + 24))

        trade_candles = list(candles or [])
        if len(trade_candles) < desired_limit:
            try:
                fetched = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, desired_limit) or []
                if fetched:
                    trade_candles = fetched
            except Exception as exc:
                logging.warning("Failed to fetch lifecycle candles for %s: %s", state.inst_id, exc)

        merged = []
        by_ts = {}
        for candle in entry_candles + trade_candles:
            try:
                ts = int(candle[0])
                by_ts[ts] = [int(candle[0]), float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4]), float(candle[5]) if len(candle) > 5 else 0.0]
            except Exception:
                continue
        for ts in sorted(by_ts):
            merged.append(by_ts[ts])

        entry_time_text = str(state.entry_time or entry_payload.get('saved_at') or '')
        exit_time_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            entry_dt = datetime.strptime(entry_time_text, "%Y-%m-%d %H:%M:%S")
            entry_ts_ms = int(entry_dt.timestamp() * 1000)
        except Exception:
            entry_ts_ms = int(merged[0][0]) if merged else 0

        try:
            exit_dt = datetime.strptime(exit_time_text, "%Y-%m-%d %H:%M:%S")
            exit_ts_ms = int(exit_dt.timestamp() * 1000)
        except Exception:
            exit_ts_ms = int(merged[-1][0]) if merged else 0

        if merged:
            before = [c for c in merged if int(c[0]) <= entry_ts_ms]
            after = [c for c in merged if int(c[0]) >= entry_ts_ms]
            merged = (before[-40:] if before else merged[:40]) + [c for c in after if c not in (before[-40:] if before else [])]
            merged = merged[-260:]

        def nearest_index(target_ts: int) -> int:
            if not merged:
                return -1
            best_idx = 0
            best_dist = abs(int(merged[0][0]) - target_ts)
            for idx, candle in enumerate(merged):
                dist = abs(int(candle[0]) - target_ts)
                if dist < best_dist:
                    best_idx = idx
                    best_dist = dist
            return best_idx

        markers = []
        entry_idx = nearest_index(entry_ts_ms)
        if entry_idx >= 0:
            markers.append({
                'kind': 'entry',
                'label': 'E',
                'index': entry_idx,
                'price': float(state.avg_px or entry_payload.get('entry_price') or 0.0),
                'time': entry_time_text,
            })

        add_step = float(entry_payload.get('add_unit_every_atr', self.cfg.add_unit_every_atr) or self.cfg.add_unit_every_atr)
        base_entry = float(entry_payload.get('entry_price') or state.avg_px or 0.0)
        entry_atr = float(entry_payload.get('atr') or state.atr or 0.0)
        if state.units > 1 and entry_atr > 0 and add_step > 0:
            for unit_no in range(2, int(state.units) + 1):
                add_price = base_entry + entry_atr * add_step * (unit_no - 1) if state.side == 'long' else base_entry - entry_atr * add_step * (unit_no - 1)
                found_idx = -1
                for idx in range(max(0, entry_idx), len(merged)):
                    hi = float(merged[idx][2])
                    lo = float(merged[idx][3])
                    if lo <= add_price <= hi:
                        found_idx = idx
                        break
                if found_idx >= 0:
                    markers.append({
                        'kind': f'add_{unit_no}',
                        'label': f'A{unit_no}',
                        'index': found_idx,
                        'price': add_price,
                        'time': datetime.fromtimestamp(int(merged[found_idx][0]) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    })

        exit_idx = nearest_index(exit_ts_ms)
        if exit_idx >= 0:
            markers.append({
                'kind': 'exit',
                'label': 'X',
                'index': exit_idx,
                'price': float(exit_price),
                'time': exit_time_text,
            })

        channel_exit_level = 0.0
        try:
            if merged and int(state.exit_period or 0) > 0:
                exit_window = merged[max(0, exit_idx - int(state.exit_period) + 1):exit_idx + 1] if exit_idx >= 0 else merged[-int(state.exit_period):]
                if exit_window:
                    channel_exit_level = min(float(c[3]) for c in exit_window) if state.side == 'long' else max(float(c[2]) for c in exit_window)
        except Exception:
            channel_exit_level = 0.0

        return {
            'version': APP_VERSION,
            'saved_at': exit_time_text,
            'trade_id': str(getattr(state, 'trade_id', '') or entry_payload.get('trade_id') or _stable_trade_id(state.inst_id, state.side, entry_time_text)),
            'inst_id': state.inst_id,
            'side': state.side,
            'timeframe': self.cfg.timeframe,
            'system_name': state.system_name,
            'entry_price': float(base_entry or state.avg_px or 0.0),
            'exit_price': float(exit_price),
            'entry_atr': float(entry_atr or state.atr or 0.0),
            'start_stop_price': float(entry_payload.get('stop_price') or 0.0),
            'final_stop_price': float(state.stop_price or 0.0),
            'channel_exit_level': float(channel_exit_level or 0.0),
            'initial_stop_price': float(getattr(state, 'initial_stop_price', 0.0) or entry_payload.get('stop_price') or 0.0),
            'peak_price': float(getattr(state, 'peak_price', 0.0) or 0.0),
            'trough_price': float(getattr(state, 'trough_price', 0.0) or 0.0),
            'peak_unrealized_pnl': float(getattr(state, 'peak_unrealized_pnl', 0.0) or 0.0),
            'qty': float(state.qty or 0.0),
            'units': int(state.units or 1),
            'pnl': float(pnl),
            'pnl_pct': float(pnl_pct),
            'reason': reason,
            'duration_sec': int(duration_sec or 0),
            'entry_time': entry_time_text,
            'exit_time': exit_time_text,
            'entry_context_file': str(getattr(state, 'entry_context_file', '') or ''),
            'planned_risk_pct': float(getattr(state, 'planned_risk_pct', 0.0) or entry_payload.get('planned_risk_pct') or 0.0),
            'risk_amount_usdt': float(getattr(state, 'risk_amount_usdt', 0.0) or entry_payload.get('risk_amount_usdt') or 0.0),
            'risk_per_contract': float(getattr(state, 'risk_per_contract', 0.0) or entry_payload.get('risk_per_contract') or 0.0),
            'position_notional_usdt': float(getattr(state, 'position_notional_usdt', 0.0) or entry_payload.get('position_notional_usdt') or 0.0),
            'trailing_activated_at': str(getattr(state, 'trailing_activated_at', '') or ''),
            'breakeven_activated_at': str(getattr(state, 'breakeven_activated_at', '') or ''),
            'breakout_distance_atr': float(entry_payload.get('breakout_distance_atr') or 0.0),
            'channel_atr_ratio': float(entry_payload.get('channel_atr_ratio') or 0.0),
            'atr_pct_at_entry': float(entry_payload.get('atr_pct_at_entry') or 0.0),
            'body_atr_at_entry': float(entry_payload.get('body_atr_at_entry') or 0.0),
            'body_to_range_ratio_at_entry': float(entry_payload.get('body_to_range_ratio_at_entry') or 0.0),
            'close_near_extreme_ratio_at_entry': float(entry_payload.get('close_near_extreme_ratio_at_entry') or 0.0),
            'stop_confirmed': bool(str(getattr(state, 'stop_state', '') or '').upper() in {'ACTIVE', 'CONFIRMED'}),
            'stop_state': str(getattr(state, 'stop_state', '') or ''),
            'exchange_stop_status': str(getattr(state, 'exchange_stop_status', '') or ''),
            'position_health_state': str(getattr(state, 'position_health_state', '') or ''),
            'state_tag': str(getattr(state, 'state_tag', 'ACTIVE') or 'ACTIVE'),
            'pyramiding_block_reason': str(getattr(state, 'pyramiding_block_reason', '') or ''),
            'breakout_id': str(getattr(state, 'breakout_id', '') or entry_payload.get('breakout_id') or ''),
            'breakout_level': float(getattr(state, 'breakout_level', 0.0) or entry_payload.get('breakout_level') or 0.0),
            'breakout_body_atr': float(getattr(state, 'breakout_body_atr', 0.0) or entry_payload.get('body_atr_at_entry') or 0.0),
            'breakout_distance_atr_state': float(getattr(state, 'breakout_distance_atr', 0.0) or 0.0),
            'candles': merged,
            'markers': markers,
        }

    def _save_trade_context(self, payload: dict) -> str:
        try:
            safe_inst = str(payload.get('inst_id', 'UNKNOWN')).replace('/', '_').replace(':', '_')
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = TRADE_CONTEXT_DIR / f"{ts}_{safe_inst}_{payload.get('side', 'na')}_trade.json"
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return str(file_path)
        except Exception as exc:
            logging.warning("Failed to save trade context for %s: %s", payload.get('inst_id'), exc)
            return ""

    def emit_snapshot(self) -> None:
        with self.balance_lock:
            latest_balance = dict(self.latest_balance_snapshot)
            balance_history_copy = list(self.balance_history[-20000:])

        if latest_balance:
            balance_total = float(latest_balance.get("balance_total", 0.0) or 0.0)
            balance_available = float(latest_balance.get("balance_available", 0.0) or 0.0)
            balance_used = float(latest_balance.get("balance_used", 0.0) or 0.0)
        else:
            bal = self.gateway.get_account_balance()
            self._append_balance_point_from_account(bal)
            with self.balance_lock:
                latest_balance = dict(self.latest_balance_snapshot)
                balance_history_copy = list(self.balance_history[-20000:])
            balance_total = float(latest_balance.get("balance_total", 0.0) or 0.0)
            balance_available = float(latest_balance.get("balance_available", 0.0) or 0.0)
            balance_used = float(latest_balance.get("balance_used", 0.0) or 0.0)


        open_positions = []
        for state in self.position_state.values():
            row = asdict(state)
            avg_px = float(state.avg_px or 0.0)
            last_px = float(state.last_px or 0.0)
            atr = float(state.atr or 0.0)
            margin = float(state.margin or 0.0)
            upl = float(state.unrealized_pnl or 0.0)

            if margin > 0:
                pnl_pct = (upl / margin) * 100.0
            else:
                pnl_pct = 0.0

            if last_px > 0:
                stop_distance_pct = ((last_px - state.stop_price) / last_px * 100.0) if state.side == "long" else ((state.stop_price - last_px) / last_px * 100.0)
                pyramid_distance_pct = ((state.next_pyramid_price - last_px) / last_px * 100.0) if state.side == "long" else ((last_px - state.next_pyramid_price) / last_px * 100.0)
                atr_pct = (atr / last_px * 100.0) if atr > 0 else 0.0
            else:
                stop_distance_pct = 0.0
                pyramid_distance_pct = 0.0
                atr_pct = 0.0

            row["pnl_pct"] = pnl_pct
            row["atr_pct"] = atr_pct
            row["stop_distance_pct"] = stop_distance_pct
            row["pyramid_distance_pct"] = pyramid_distance_pct
            row["trend_strength_atr"] = (abs(last_px - avg_px) / atr) if atr > 0 else 0.0
            row["added_units"] = max(0, int(state.units) - 1)
            open_positions.append(row)

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

        now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Изменение баланса за день и за 7 дней
        day_change_pct = 0.0
        week_change_pct = 0.0

        history_with_dt = []
        for item in balance_history_copy:
            try:
                dt = datetime.strptime(str(item.get("time", "")), "%Y-%m-%d %H:%M:%S")
                val = float(item.get("balance_total", 0.0))
                history_with_dt.append((dt, val))
            except Exception:
                continue

        if history_with_dt:
            history_with_dt.sort(key=lambda x: x[0])
            current_balance_for_change = history_with_dt[-1][1]

            day_cutoff = datetime.now() - timedelta(days=1)
            week_cutoff = datetime.now() - timedelta(days=7)

            day_candidates = [v for dt, v in history_with_dt if dt <= day_cutoff]
            week_candidates = [v for dt, v in history_with_dt if dt <= week_cutoff]

            if day_candidates and abs(day_candidates[-1]) > 1e-12:
                day_change_pct = ((current_balance_for_change - day_candidates[-1]) / day_candidates[-1]) * 100.0

            if week_candidates and abs(week_candidates[-1]) > 1e-12:
                week_change_pct = ((current_balance_for_change - week_candidates[-1]) / week_candidates[-1]) * 100.0

        # Использовано риска
        used_risk_pct = sum(
            max(0.0, float(pos.get("stop_distance_pct", 0.0)))
            for pos in visible_open_positions
        )
        max_risk_budget_pct = max(
            0.0,
            len(visible_open_positions) * float(self.cfg.risk_per_trade_pct or 0.0)
        )

        # Сделки сегодня / средняя длительность
        today_str = datetime.now().strftime("%Y-%m-%d")
        trades_today = 0
        durations_today = []
        for trade in visible_closed_trades:
            try:
                if str(trade.time).startswith(today_str):
                    trades_today += 1
                    durations_today.append(int(trade.duration_sec or 0))
            except Exception:
                continue
        avg_duration_sec = int(sum(durations_today) / len(durations_today)) if durations_today else 0

        turtle_regime = self._compute_turtle_regime()
        trade_ready_metrics = self._collect_trade_ready_metrics()
        if bool(getattr(self, "position_cycle_active", False)) or bool(getattr(self, "position_cycle_scanner_paused", False)):
            trade_ready_metrics["scanner_status_text"] = "PAUSED: POSITIONS"
        self.last_trade_ready_metrics = dict(trade_ready_metrics)

        payload = {
            "timestamp": format_time_string(now_full),
            "engine": {
                "last_cycle_started": format_clock(self.last_scan_started_at),
                "last_cycle_finished": format_clock(self.last_scan_finished_at),
                "last_snapshot_emitted": format_time_string(now_full),
                "last_cycle_duration_sec": round(max(0.0, (self.last_scan_finished_at or time.time()) - (self.last_scan_started_at or time.time())), 3) if self.last_scan_started_at else 0.0,
                "scan_interval_sec": self.cfg.scan_interval_sec,
                "position_check_interval_sec": self.cfg.position_check_interval_sec,
                "snapshot_interval_sec": self.cfg.snapshot_interval_sec,
                "position_cycle_active": bool(getattr(self, 'position_cycle_active', False)),
                "position_cycle_progress": self._position_cycle_progress_text(),
                "position_cycle_done": int(getattr(self, 'position_cycle_done', 0) or 0),
                "position_cycle_total": int(getattr(self, 'position_cycle_total', 0) or 0),
                "position_cycle_last_duration_sec": round(float(getattr(self, 'position_cycle_last_duration_sec', 0.0) or 0.0), 3),
                "position_cycle_last_completed_utc": str(getattr(self, 'position_cycle_last_completed_utc', '—') or '—'),
                "position_cycle_last_error": str(getattr(self, 'position_cycle_last_error', '') or ''),
            },
            "balance_total": balance_total,
            "balance_available": balance_available,
            "balance_used": balance_used,
            "open_positions": [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))],
            "closed_trades": [asdict(x) for x in reversed([x for x in visible_closed_trades[-500:] if not is_hidden_instrument(x.inst_id)])],
            "analytics": {
                "trade_ready_count": int(trade_ready_metrics.get("trade_ready_count", 0) or 0),
                "available_after_bans_count": int(trade_ready_metrics.get("available_after_bans_count", 0) or 0),
                "scan_universe_total": int(trade_ready_metrics.get("scan_universe_total", 0) or 0),
                "blocked_total": int(trade_ready_metrics.get("hard_blocked_unique_count", 0) or 0),
                "scanner_total": int(trade_ready_metrics.get("scanner_total", 0) or 0),
                "scanner_scanned": int(trade_ready_metrics.get("scanner_scanned", trade_ready_metrics.get("scanner_ready", 0)) or 0),
                "scanner_ready": int(trade_ready_metrics.get("scanner_ready", 0) or 0),
                "scanner_allowed": int(trade_ready_metrics.get("scanner_allowed", trade_ready_metrics.get("scanner_admitted", 0)) or 0),
                "scanner_blocked": int(trade_ready_metrics.get("scanner_blocked", trade_ready_metrics.get("scanner_risky", 0)) or 0),
                "scanner_dead": int(trade_ready_metrics.get("scanner_dead", 0) or 0),
                "scanner_saw": int(trade_ready_metrics.get("scanner_saw", 0) or 0),
                "scanner_ripping": int(trade_ready_metrics.get("scanner_ripping", 0) or 0),
                "scanner_pending": int(trade_ready_metrics.get("scanner_pending", 0) or 0),
                "scanner_failed": int(trade_ready_metrics.get("scanner_failed", 0) or 0),
                "scanner_status_text": str(trade_ready_metrics.get("scanner_status_text", "IDLE") or "IDLE"),
                "scanner_safe": int(trade_ready_metrics.get("scanner_safe", 0) or 0),
                "scanner_caution": int(trade_ready_metrics.get("scanner_caution", 0) or 0),
                "scanner_risky": int(trade_ready_metrics.get("scanner_risky", 0) or 0),
                "scanner_blacklist": int(trade_ready_metrics.get("scanner_blacklist", 0) or 0),
                "scanner_exec_watch": int(trade_ready_metrics.get("scanner_exec_watch", 0) or 0),
                "good_positions_open": len(visible_open_positions),
                "good_trades_closed": len(visible_closed_trades),
                "good_trades_total": len(visible_open_positions) + len(visible_closed_trades),
                "open_pnl": open_pnl,
                "avg_open_pnl_pct": avg_pnl_pct,
                "best_open_pnl_pct": best_open,
                "worst_open_pnl_pct": worst_open,
                "long_count": longs,
                "short_count": shorts,
                "closed_count": len(visible_closed_trades),
                "realized_pnl": realized_pnl,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
                "day_change_pct": day_change_pct,
                "week_change_pct": week_change_pct,
                "used_risk_pct": used_risk_pct,
                "max_risk_budget_pct": max_risk_budget_pct,
                "trades_today": trades_today,
                "avg_duration_sec": avg_duration_sec,
                "turtle_regime_label": turtle_regime.get("label", "—"),
                "turtle_regime_score": turtle_regime.get("score", 0),
                "turtle_regime_channel_atr": turtle_regime.get("channel_atr_ratio", 0.0),
                "turtle_regime_efficiency": turtle_regime.get("efficiency_ratio", 0.0),
                "turtle_regime_atr_pct": turtle_regime.get("atr_pct", 0.0),
                "turtle_regime_instrument": turtle_regime.get("instrument", "—"),
                "position_cycle_active": bool(getattr(self, 'position_cycle_active', False)),
                "position_cycle_progress": self._position_cycle_progress_text(),
                "position_cycle_last_duration_sec": round(float(getattr(self, 'position_cycle_last_duration_sec', 0.0) or 0.0), 3),
                "position_cycle_last_completed_utc": str(getattr(self, 'position_cycle_last_completed_utc', '—') or '—'),
            },
            "balance_history": balance_history_copy,
            "settings": {
                "account": "Основной" if self.cfg.flag == "0" else "Демо",
                "timeframe": self.cfg.timeframe,
                "trade_mode": getattr(self.cfg, "trade_mode", "auto"),
                "risk_per_trade_pct": self.cfg.risk_per_trade_pct,
            },
            "market_data_cache": self.market_data_cache.snapshot_stats(),
            "signal_funnel": dict(self.last_signal_funnel or {}),
            "trade_ready_metrics": trade_ready_metrics,
            "connectivity": {
                "state": str(getattr(self, "exchange_connectivity_state", "IDLE") or "IDLE"),
                "since": datetime.fromtimestamp(float(getattr(self, "exchange_connectivity_since_ts", time.time()) or time.time())).strftime("%Y-%m-%d %H:%M:%S"),
                "components": dict(getattr(self, "exchange_connectivity_components", {}) or {}),
                "last_error": str(getattr(self, "exchange_connectivity_last_error", "") or ""),
            },
        }
        self.last_snapshot_emitted_at = time.time()
        self.stats_logger.log(
            "snapshot",
            balance_total=balance_total,
            balance_available=balance_available,
            balance_used=balance_used,
            open_positions=len(visible_open_positions),
            closed_trades=len(visible_closed_trades),
            open_pnl=open_pnl,
            realized_pnl=realized_pnl,
            winrate=winrate,
            timeframe=self.cfg.timeframe,
            market_data_fetch_count=self.market_data_cache.fetch_count,
            market_data_errors=self.market_data_cache.error_count,
            trade_ready_count=int(trade_ready_metrics.get("trade_ready_count", 0) or 0),
            available_after_bans_count=int(trade_ready_metrics.get("available_after_bans_count", 0) or 0),
            scan_universe_total=int(trade_ready_metrics.get("scan_universe_total", 0) or 0),
        )
        self.snapshot.emit(payload)

    @staticmethod
    def floor_to_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        try:
            value_dec = Decimal(str(value))
            step_dec = Decimal(str(step))
            units = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
            return float(units * step_dec)
        except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
            return 0.0
