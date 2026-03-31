from app.runtime_support_parts.base import *
from app.runtime_support_parts.theme import ENTRY_CONTEXT_DIR, TRADE_CONTEXT_DIR

class RuntimeErrorTracker:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._count = None

    def _is_countable_payload(self, payload: dict) -> bool:
        try:
            severity = str((payload or {}).get("severity") or "ERROR").upper()
            category = str((payload or {}).get("category") or "runtime").lower()
            title = str((payload or {}).get("title") or "").lower()
            message = str((payload or {}).get("message") or "").lower()
        except Exception:
            return True
        if severity not in {"ERROR", "CRITICAL"}:
            return False
        benign_markers = (
            "winerror 10035",
            "operation could not be completed immediately",
            "scanner refresh temporary failure",
            "market_already_crossed_stop",
            "readerror",
        )
        blob = f"{title} {message}"
        if category in {"network", "warning", "transient"}:
            return False
        return not any(marker in blob for marker in benign_markers)

    def _ensure_count(self) -> int:
        if self._count is not None:
            return int(self._count)
        count = 0
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except Exception:
                            payload = {"severity": "ERROR", "category": "runtime", "title": line, "message": line}
                        if self._is_countable_payload(payload):
                            count += 1
        except Exception:
            count = 0
        self._count = count
        return count

    def count(self) -> int:
        with self._lock:
            return self._ensure_count()

    def reset(self) -> None:
        with self._lock:
            try:
                self.path.write_text("", encoding="utf-8")
            except Exception:
                pass
            self._count = 0

    def record(self, *, source: str, title: str, message: str = "", traceback_text: str = "", extra: Optional[dict] = None, severity: str = "ERROR", category: str = "runtime") -> int:
        payload = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": str(source or ""),
            "title": str(title or ""),
            "message": str(message or ""),
            "traceback": str(traceback_text or ""),
            "severity": str(severity or "ERROR"),
            "category": str(category or "runtime"),
            "extra": dict(extra or {}),
        }
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                return self._ensure_count()
            current = self._ensure_count()
            if self._is_countable_payload(payload):
                current += 1
            self._count = current
            return int(self._count)


RUNTIME_ERROR_TRACKER = RuntimeErrorTracker(TRACEBACK_ERROR_FILE)


def record_runtime_error(source: str, title: str, *, exc_info=None, message: str = "", traceback_text: str = "", extra: Optional[dict] = None, severity: str = "ERROR", category: str = "runtime") -> int:
    tb_text = str(traceback_text or "")
    if not tb_text and exc_info:
        try:
            tb_text = "".join(traceback.format_exception(*exc_info))
        except Exception:
            tb_text = ""
    msg = str(message or "")
    if not msg and exc_info and len(exc_info) >= 2 and exc_info[1] is not None:
        msg = str(exc_info[1])
    return RUNTIME_ERROR_TRACKER.record(source=source, title=title, message=msg, traceback_text=tb_text, extra=extra, severity=severity, category=category)


class TracebackErrorCountingHandler(logging.Handler):
    _warning_markers = ("failed", "error", "exception", "traceback", "timeout", "readerror", "critical")

    def emit(self, record):
        try:
            message = record.getMessage()
            traceback_text = ""
            if record.exc_info:
                traceback_text = self.formatException(record.exc_info)
            elif isinstance(record.msg, str) and "Traceback" in record.msg:
                traceback_text = message
            lowered = str(message or "").lower()
            benign_markers = (
                "winerror 10035",
                "scanner refresh temporary failure",
                "market_already_crossed_stop",
                "operation could not be completed immediately",
            )
            should_record = bool(traceback_text) or record.levelno >= logging.ERROR
            if not should_record and record.levelno >= logging.WARNING:
                should_record = any(marker in lowered for marker in self._warning_markers)
            if not should_record:
                return
            severity = str(record.levelname or "ERROR")
            category = "logging"
            if any(marker in lowered for marker in benign_markers):
                category = "network" if "winerror 10035" in lowered or "completed immediately" in lowered else "warning"
                severity = "WARNING"
            extra = {
                "logger": record.name,
                "level": record.levelname,
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }
            record_runtime_error(
                f"logging:{record.name}",
                title=message,
                message=message,
                traceback_text=traceback_text,
                extra=extra,
                severity=severity,
                category=category,
            )
        except Exception:
            pass

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(APP_LOG, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    try:
        root_logger = logging.getLogger()
        if not any(isinstance(h, TracebackErrorCountingHandler) for h in root_logger.handlers):
            root_logger.addHandler(TracebackErrorCountingHandler())
    except Exception:
        pass
    try:
        crash_stream = open(CRASH_LOG, "a", encoding="utf-8")
        faulthandler.enable(crash_stream, all_threads=True)
    except Exception as exc:
        logging.warning("Failed to enable faulthandler: %s", exc)


def log_heartbeat(component: str, status: str, **payload) -> None:
    row = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "component": str(component or ""),
        "status": str(status or ""),
    }
    row.update(payload)
    try:
        with HEARTBEAT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        logging.exception("Failed to write heartbeat")


def recreate_trade_csv() -> None:
    with TRADE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time",
            "event",
            "inst_id",
            "side",
            "qty",
            "price",
            "atr",
            "stop_price",
            "system_name",
            "note",
        ])


def clear_json_directory(directory: Path) -> int:
    removed = 0
    directory.mkdir(exist_ok=True)
    for item in directory.glob("*.json"):
        try:
            item.unlink()
            removed += 1
        except Exception:
            pass
    return removed


def reset_local_runtime_files() -> dict:
    removed_entry = clear_json_directory(ENTRY_CONTEXT_DIR)
    removed_trade = clear_json_directory(TRADE_CONTEXT_DIR)

    if STATE_FILE.exists():
        try:
            STATE_FILE.unlink()
        except Exception:
            pass

    recreate_trade_csv()

    for file_path in (ENGINE_STATS_FILE, SIGNAL_AUDIT_FILE, POSITION_JOURNAL_FILE, POSITION_SNAPSHOTS_FILE, SYSTEM_HEALTH_FILE, PYRAMID_DIAGNOSTICS_FILE, REENTRY_DIAGNOSTICS_FILE, BREAKOUT_QUALITY_FILE, STOP_ENGINE_FILE, TRACEBACK_ERROR_FILE, APP_LOG, CRASH_LOG, HEARTBEAT_FILE):
        try:
            file_path.write_text("", encoding="utf-8")
        except Exception:
            pass

    try:
        RUNTIME_ERROR_TRACKER.reset()
    except Exception:
        pass

    return {
        "entry_context_removed": removed_entry,
        "trade_context_removed": removed_trade,
    }
