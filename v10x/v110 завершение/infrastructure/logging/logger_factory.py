from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import RLock


ENGINE_LOG_FILES = {
    "analysis": "analysis.log",
    "app": "app.log",
    "balance": "balance.log",
    "exchange": "exchange.log",
    "execution": "execution.log",
    "gui": "gui.log",
    "health": "health.log",
    "positions": "positions.log",
    "reconcile": "reconcile.log",
    "scanner": "scanner.log",
    "session": "session.log",
    "stops": "stops.log",
    "telegram": "telegram.log",
    "trading": "trading.log",
}

MODULE_ENGINE_MAP = {
    "analysis_exporter": "analysis",
    "bootstrap": "session",
    "exchange_health": "health",
    "main": "app",
    "main_v107": "app",
    "main_v108": "app",
    "market_data_cache": "exchange",
    "market_quality": "scanner",
    "market_scanner_runtime": "scanner",
    "scanner_engine": "scanner",
    "okx_gateway": "exchange",
    "okx_ws_manager": "exchange",
    "popups": "gui",
    "position_reconciler": "reconcile",
    "run_telegram_worker": "telegram",
    "stop_engine": "stops",
    "sync_position_manager": "reconcile",
    "telegram_notifier": "telegram",
    "trade_models": "positions",
    "trading_engine": "trading",
    "legacy_window_bindings": "gui",
}

FUNC_ENGINE_HINTS = {
    "reset_test_run": "session",
    "start_bot": "session",
    "stop_bot": "session",
    "try_pyramid": "trading",
    "close_position": "positions",
    "trailing_stop": "stops",
}


@dataclass(frozen=True)
class LogBundle:
    logs_dir: Path
    app_version: str


class _PerFileWriter:
    def __init__(self) -> None:
        self._locks: dict[Path, RLock] = {}

    def write(self, path: Path, line: str) -> None:
        lock = self._locks.setdefault(path, RLock())
        with lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


class EngineRoutingHandler(logging.Handler):
    def __init__(self, logs_dir: Path, *, errors_only: bool = False) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self.errors_only = errors_only
        self.writer = _PerFileWriter()

    def emit(self, record: logging.LogRecord) -> None:
        if self.errors_only and record.levelno < logging.ERROR:
            return
        engine = resolve_engine(record)
        if self.errors_only:
            target = self.logs_dir / f"{engine}_errors.log"
        else:
            target = self.logs_dir / ENGINE_LOG_FILES.get(engine, "app.log")
        try:
            line = self.format(record)
            self.writer.write(target, line)
            if record.levelno >= logging.CRITICAL:
                self.writer.write(self.logs_dir / "critical_errors.log", line)
        except Exception:
            pass


class SystemEventsHandler(logging.Handler):
    def __init__(self, logs_dir: Path) -> None:
        super().__init__(level=logging.INFO)
        self.logs_dir = logs_dir
        self.writer = _PerFileWriter()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name != "system_events":
            return
        try:
            self.writer.write(self.logs_dir / "system_events.log", self.format(record))
        except Exception:
            pass


def resolve_engine(record: logging.LogRecord) -> str:
    engine = getattr(record, "engine", None)
    if engine:
        return str(engine)
    logger_name = str(getattr(record, "name", "") or "")
    if logger_name.startswith("engine."):
        return logger_name.split(".", 1)[1]
    module_name = str(getattr(record, "module", "") or "")
    if module_name in MODULE_ENGINE_MAP:
        return MODULE_ENGINE_MAP[module_name]
    func_name = str(getattr(record, "funcName", "") or "")
    if func_name in FUNC_ENGINE_HINTS:
        return FUNC_ENGINE_HINTS[func_name]
    pathname = str(getattr(record, "pathname", "") or "")
    low = pathname.lower()
    if "scanner" in low:
        return "scanner"
    if "stop" in low:
        return "stops"
    if "reconcile" in low or "sync_position" in low:
        return "reconcile"
    if "popup" in low or "ui" in low:
        return "gui"
    if "telegram" in low:
        return "telegram"
    return "app"


def configure_logging(logs_dir: Path, *, app_version: str) -> LogBundle:
    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    routed_handler = EngineRoutingHandler(logs_dir, errors_only=False)
    routed_handler.setLevel(logging.INFO)
    routed_handler.setFormatter(formatter)

    error_handler = EngineRoutingHandler(logs_dir, errors_only=True)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    system_handler = SystemEventsHandler(logs_dir)
    system_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(routed_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(system_handler)

    logging.getLogger("system_events").info("logging_configured version=%s logs_dir=%s", app_version, logs_dir)
    return LogBundle(logs_dir=logs_dir, app_version=app_version)


def get_engine_logger(engine: str) -> logging.Logger:
    return logging.getLogger(f"engine.{engine}")


def get_system_logger() -> logging.Logger:
    return logging.getLogger("system_events")
