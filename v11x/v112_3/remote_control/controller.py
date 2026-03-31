from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox

from analysis.export_engine import AnalysisExportEngine

from .bridge import RemoteBridge


class RemoteControlController:
    ALLOWED_COMMANDS = {"status", "start_bot", "stop_bot", "reset_test", "analysis", "update_component", "update_full"}

    def __init__(self, *, window: object, context: object, poll_interval_ms: int = 1500) -> None:
        self.window = window
        self.context = context
        self.log = logging.getLogger("remote_control")
        runtime_dir = getattr(getattr(context, "settings", None), "runtime_dir", Path("runtime"))
        self.bridge = RemoteBridge(Path(runtime_dir) / "remote_bridge")
        self._busy_lock = threading.Lock()
        self._is_busy = False
        self._current_operation = ""
        self._last_result = ""
        self._timer = QTimer(window)
        self._timer.timeout.connect(self.poll_once)
        self._timer.start(max(500, int(poll_interval_ms or 1500)))
        self.write_state(extra={"status": "idle", "last_result": "ready"})

    def write_state(self, *, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "app_version": str(getattr(getattr(self.context, "settings", None), "app_version", "unknown")),
            "busy": bool(self._is_busy),
            "current_operation": str(self._current_operation or ""),
            "last_result": str(self._last_result or ""),
            "bot_running": bool(self._bot_running()),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        status_file = Path(getattr(getattr(self.context, "settings", None), "runtime_dir", Path("runtime"))) / "telegram_status.json"
        if status_file.exists():
            try:
                payload["telegram_status"] = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                payload["telegram_status"] = {}
        if extra:
            payload.update(dict(extra))
        try:
            self.bridge.write_state(payload)
        except Exception:
            self.log.exception("remote_state_write_failed")

    def poll_once(self) -> None:
        self.write_state()
        if self._is_busy:
            return
        for cmd_path in self.bridge.list_pending_commands():
            processing = self.bridge.move_to_processing(cmd_path)
            if processing is None:
                continue
            try:
                payload = json.loads(processing.read_text(encoding="utf-8"))
            except Exception as exc:
                self.log.exception("remote_command_read_failed")
                try:
                    processing.unlink(missing_ok=True)
                except Exception:
                    pass
                self.bridge.write_result("invalid", {"status": "error", "message": f"invalid command payload: {exc}"})
                return
            self._execute_command(payload)
            try:
                processing.unlink(missing_ok=True)
            except Exception:
                pass
            return

    def _execute_command(self, payload: dict[str, Any]) -> None:
        command_id = str(payload.get("command_id") or "unknown")
        command = str(payload.get("command") or "").strip().lower()
        args = dict(payload.get("args") or {})
        if command not in self.ALLOWED_COMMANDS:
            self.bridge.write_result(command_id, {"status": "error", "message": f"unsupported command: {command}"})
            return
        with self._busy_guard(command):
            try:
                result = self._dispatch(command, args)
            except Exception as exc:
                self._last_result = f"{command}: error: {exc}"
                self.log.exception("remote_command_failed command=%s", command)
                self.write_state(extra={"status": "error", "last_result": self._last_result})
                self.bridge.write_result(command_id, {"status": "error", "message": str(exc)})
                return
            self._last_result = str(result.get("message") or f"{command}: ok")
            self.write_state(extra={"status": result.get("status", "ok"), "last_result": self._last_result})
            self.bridge.write_result(command_id, result)

    from contextlib import contextmanager
    @contextmanager
    def _busy_guard(self, command: str):
        if not self._busy_lock.acquire(blocking=False):
            raise RuntimeError("remote controller busy")
        self._is_busy = True
        self._current_operation = command
        self.write_state(extra={"status": "busy", "current_operation": command})
        try:
            yield
        finally:
            self._is_busy = False
            self._current_operation = ""
            self._busy_lock.release()
            self.write_state(extra={"status": "idle"})

    def _dispatch(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        if command == "status":
            return {"status": "ok", "message": self._status_text()}
        if command == "start_bot":
            return self._start_bot()
        if command == "stop_bot":
            return self._stop_bot()
        if command == "reset_test":
            return self._reset_test()
        if command == "analysis":
            return self._run_analysis()
        if command == "update_component":
            component = str(args.get("component") or "").strip()
            return self._stub_update(f"component={component}" if component else "component=<missing>")
        if command == "update_full":
            return self._stub_update("full")
        raise RuntimeError(f"unsupported command: {command}")

    def _status_text(self) -> str:
        return (
            f"OKX Turtle Bot {getattr(getattr(self.context, 'settings', None), 'app_version', 'unknown')}\n"
            f"bot: {'RUNNING' if self._bot_running() else 'STOPPED'}\n"
            f"busy: {'YES' if self._is_busy else 'NO'}\n"
            f"updated: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _bot_running(self) -> bool:
        worker = getattr(self.window, "worker", None)
        try:
            return bool(worker and worker.isRunning())
        except Exception:
            return False

    def _start_bot(self) -> dict[str, Any]:
        if self._bot_running():
            return {"status": "ok", "message": "bot already running"}
        start_fn = getattr(self.window, "start_engine_from_controls", None)
        if not callable(start_fn):
            raise RuntimeError("start handler not available")
        start_fn()
        time.sleep(0.2)
        running = self._bot_running()
        return {"status": "ok" if running else "error", "message": "bot started" if running else "bot did not start"}

    def _stop_bot(self) -> dict[str, Any]:
        if not self._bot_running():
            return {"status": "ok", "message": "bot already stopped"}
        stop_fn = getattr(self.window, "stop_engine", None)
        if not callable(stop_fn):
            raise RuntimeError("stop handler not available")
        stop_fn()
        for _ in range(20):
            if not self._bot_running():
                break
            time.sleep(0.15)
        running = self._bot_running()
        return {"status": "ok" if not running else "error", "message": "bot stopped" if not running else "bot still running"}

    def _reset_test(self) -> dict[str, Any]:
        reset_fn = getattr(self.window, "reset_test_run", None)
        if not callable(reset_fn):
            raise RuntimeError("reset handler not available")
        original = QMessageBox.question
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes
            reset_fn()
        finally:
            QMessageBox.question = original
        return {"status": "ok", "message": "reset_test completed"}

    def _run_analysis(self) -> dict[str, Any]:
        services = getattr(self.context, "services", None)
        analysis_engine = services.optional("analysis_export_engine") if services is not None else None
        if analysis_engine is None:
            analysis_engine = AnalysisExportEngine(bot=self.window, analysis_store=services.optional("analysis_store") if services is not None else None)
        archive_path = analysis_engine.export(mode="full", snapshot=getattr(self.window, "latest_snapshot", {}) or {}, cfg=getattr(self.window, "current_cfg", None))
        archive_path = Path(archive_path)
        if not archive_path.exists() or archive_path.stat().st_size <= 0:
            raise RuntimeError("analysis archive was not created")
        return {"status": "ok", "message": f"analysis ready: {archive_path.name}", "file_path": str(archive_path)}

    def _stub_update(self, target: str) -> dict[str, Any]:
        runtime_dir = Path(getattr(getattr(self.context, "settings", None), "runtime_dir", Path("runtime")))
        backup_dir = runtime_dir / "remote_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        note = backup_dir / f"pre_update_{stamp}.txt"
        note.write_text(f"remote update placeholder created for {target}\n", encoding="utf-8")
        return {"status": "ok", "message": f"update stub prepared: {target}", "backup_note": str(note)}
