from app.runtime_support import *
from domain.trading.legacy_turtle_engine import TurtleEngine

class GuiLogBuffer(QObject):
    flushed = pyqtSignal(list)

    def __init__(self, parent=None, interval_ms: int = 250, max_batch: int = 40):
        super().__init__(parent)
        self._queue = deque()
        self._lock = threading.Lock()
        self._max_batch = max(8, int(max_batch or 40))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(max(80, int(interval_ms or 250)))

    def push(self, line: str, color: str = '#8be9fd') -> None:
        with self._lock:
            self._queue.append((str(line), str(color)))

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def _flush(self) -> None:
        batch = []
        with self._lock:
            while self._queue and len(batch) < self._max_batch:
                batch.append(self._queue.popleft())
        if batch:
            self.flushed.emit(batch)


class TelegramTaskThread(QThread):
    completed = pyqtSignal(bool, str)

    def __init__(self, notifier: TelegramNotifier, message: str = '', image: object = None, caption: str = '', parent=None):
        super().__init__(parent)
        self.notifier = notifier
        self.message = str(message or '')
        self.image = image
        self.caption = str(caption or '')

    def run(self) -> None:
        try:
            if self.image is not None:
                with NamedTemporaryFile(prefix='okx_ui_', suffix='.png', delete=False) as tmp:
                    temp_path = tmp.name
                ok = False
                try:
                    ok = bool(self.image.save(temp_path, 'PNG'))
                except Exception:
                    ok = False
                if not ok:
                    raise RuntimeError('не удалось сохранить PNG во временный файл')
                try:
                    self.notifier.send_photo(temp_path, caption=self.caption)
                finally:
                    try:
                        Path(temp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                self.completed.emit(True, 'photo')
                return
            if self.message:
                self.notifier.send(self.message)
                self.completed.emit(True, 'message')
                return
            self.completed.emit(True, 'noop')
        except Exception as exc:
            self.completed.emit(False, str(exc))


class WorkerThread(QThread):
    engine_ready = pyqtSignal(object)
    startup_failed = pyqtSignal(str)

    def __init__(self, cfg: BotConfig):
        super().__init__()
        self.cfg = cfg
        self.engine = None

    def request_engine_stop(self) -> None:
        engine = self.engine
        if engine is not None:
            try:
                engine.request_stop()
            except Exception:
                pass
        try:
            self.requestInterruption()
        except Exception:
            pass

    def run(self) -> None:
        log_heartbeat("worker", "thread_started", timeframe=getattr(self.cfg, "timeframe", ""))
        try:
            engine = TurtleEngine(self.cfg)
            self.engine = engine
            log_heartbeat("worker", "engine_constructed", timeframe=getattr(self.cfg, "timeframe", ""))
            self.engine_ready.emit(engine)
            self.msleep(30)
            engine.start()
        except Exception as exc:
            logging.exception("WorkerThread crashed: %s", exc)
            log_heartbeat("worker", "thread_crash", error=str(exc))
            self.startup_failed.emit(str(exc))
        finally:
            if self.engine is not None:
                try:
                    self.engine.finalize_stop()
                except Exception as exc:
                    logging.exception("Engine finalization failed: %s", exc)
                    log_heartbeat("worker", "finalize_error", error=str(exc))
            self.engine = None
            log_heartbeat("worker", "thread_finished")
