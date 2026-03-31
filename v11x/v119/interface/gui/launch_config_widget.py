from app.runtime_support import *

class LaunchConfigWidget(QWidget):
    start_requested = pyqtSignal(BotConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_trade_mode = "auto"
        self._build_ui()

    def _write_telegram_status_file(self) -> None:
        try:
            cfg = self.parent().current_cfg if hasattr(self.parent(), "current_cfg") else None
            payload = {
                "app_version": APP_VERSION,
                "bot_running": False,
                "telegram_worker_running": False,
                "timeframe": str(getattr(cfg, "timeframe", "-") or "-"),
                "trade_mode": str(getattr(cfg, "trade_mode", getattr(self, "selected_trade_mode", "auto")) or "-"),
                "open_positions": 0,
                "error_count": int(RUNTIME_ERROR_TRACKER.count()),
                "balance": {"total": 0.0, "available": 0.0, "used": 0.0},
                "positions": [],
                "scanner": {},
                "health": {"engine": "STOPPED", "telegram_worker": "OFF", "connectivity_state": "IDLE", "components": {}},
                "latest_errors": [],
                "chart_image_path": "",
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
        return

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        self.account_combo = QComboBox()
        self.account_combo.addItem("Демо", "1")
        self.account_combo.addItem("Основной", "0")
        form.addRow("Аккаунт:", self.account_combo)

        self.timeframe_combo = QComboBox()
        for tf in ("1m", "5m", "15m", "30m", "1H", "4H"):
            self.timeframe_combo.addItem(tf, tf)
        idx = max(0, self.timeframe_combo.findData("5m"))
        self.timeframe_combo.setCurrentIndex(idx)
        form.addRow("Таймфрейм:", self.timeframe_combo)

        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(5)
        self.leverage_spin.hide()

        layout.addLayout(form)

    def set_trade_mode(self, mode: str) -> None:
        self.selected_trade_mode = "manual" if str(mode).lower() == "manual" else "auto"

    def build_config(self) -> BotConfig:
        load_dotenv()
        api_key = os.getenv("OKX_API_KEY", "").strip()
        secret_key = os.getenv("OKX_SECRET_KEY", "").strip()
        passphrase = os.getenv("OKX_PASSPHRASE", "").strip()
        if not api_key or not secret_key or not passphrase:
            raise ValueError("Не найдены OKX_API_KEY / OKX_SECRET_KEY / OKX_PASSPHRASE в .env")

        telegram_enabled_raw = os.getenv("TELEGRAM_ENABLED", "0").strip().lower()
        telegram_enabled = (telegram_enabled_raw in {"1", "true", "yes", "on"}) and not TELEGRAM_HARD_DISABLED
        telegram_bot_token = "" if TELEGRAM_HARD_DISABLED else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = "" if TELEGRAM_HARD_DISABLED else os.getenv("TELEGRAM_CHAT_ID", "").strip()

        cfg = BotConfig(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            flag=str(self.account_combo.currentData() or "1"),
            timeframe=str(self.timeframe_combo.currentData() or "5m"),
            leverage=5,
            trade_mode=self.selected_trade_mode,
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )
        self.start_requested.emit(cfg)
        return cfg
