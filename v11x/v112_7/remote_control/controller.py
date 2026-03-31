from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from analysis.export_engine import AnalysisExportEngine

from .bridge import RemoteBridge
from .updater import UpdateError, UpdateManager


class RemoteControlController:
    ALLOWED_COMMANDS = {"status", "start_bot", "stop_bot", "reset_test", "analysis", "update_component", "update_full"}

    def __init__(self, *, window: object, context: object, poll_interval_ms: int = 1500) -> None:
        self.window = window
        self.context = context
        self.log = logging.getLogger("remote_control")
        runtime_dir = getattr(getattr(context, "settings", None), "runtime_dir", Path("runtime"))
        self.runtime_dir = Path(runtime_dir)
        self.project_root = Path(__file__).resolve().parent.parent
        self.bridge = RemoteBridge(self.runtime_dir / "remote_bridge")
        self.updater = UpdateManager(self.project_root, self.runtime_dir, self.log)
        self._scheduled_restart = False
        self._scheduled_restart_script: Path | None = None
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
            return self._update_component(component)
        if command == "update_full":
            return self._update_full()
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
        engine = getattr(self.window, "engine", None)
        try:
            worker_running = bool(worker and worker.isRunning())
        except Exception:
            worker_running = False
        try:
            engine_running = bool(engine and getattr(engine, "running", False))
        except Exception:
            engine_running = False
        window_flag = bool(getattr(self.window, "_bot_running", False))
        transition_action = str(getattr(self.window, "_engine_transition_action", "") or "")
        transitioning = bool(getattr(self.window, "_engine_transitioning", False))
        if transitioning and transition_action == "starting":
            return True
        if transitioning and transition_action == "stopping":
            return True
        return bool(worker_running or engine_running or window_flag)

    def _wait_until(self, predicate, timeout_sec: float, step_sec: float = 0.1) -> bool:
        deadline = time.time() + max(0.5, float(timeout_sec or 0.5))
        while time.time() < deadline:
            try:
                QApplication.processEvents()
            except Exception:
                pass
            try:
                if bool(predicate()):
                    return True
            except Exception:
                pass
            time.sleep(max(0.02, float(step_sec or 0.1)))
        try:
            QApplication.processEvents()
        except Exception:
            pass
        try:
            return bool(predicate())
        except Exception:
            return False

    def _start_bot(self) -> dict[str, Any]:
        if self._bot_running():
            return {"status": "ok", "message": "bot already running"}
        start_fn = getattr(self.window, "start_engine_from_controls", None)
        if not callable(start_fn):
            raise RuntimeError("start handler not available")
        start_fn()
        started = self._wait_until(lambda: self._bot_running() and not bool(getattr(self.window, "_engine_transitioning", False)), timeout_sec=20.0, step_sec=0.2)
        return {"status": "ok" if started else "error", "message": "bot started" if started else "bot did not start in time"}

    def _stop_bot(self) -> dict[str, Any]:
        if not self._bot_running():
            return {"status": "ok", "message": "bot already stopped"}
        stop_fn = getattr(self.window, "stop_engine", None)
        if not callable(stop_fn):
            raise RuntimeError("stop handler not available")
        stop_fn()
        stopped = self._wait_until(lambda: (not self._bot_running()) and (not bool(getattr(self.window, "_engine_transitioning", False))), timeout_sec=30.0, step_sec=0.2)
        return {"status": "ok" if stopped else "error", "message": "bot stopped" if stopped else "bot stop still in progress"}

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

    def _apply_update(self, loaded, *, restart_app: bool) -> dict[str, Any]:
        was_running = self._bot_running()
        pre_backup = self.updater.create_backup(loaded, stage="pre_update")
        stopped_for_update = False
        rollback_restored: list[str] = []
        try:
            if was_running:
                stop_result = self._stop_bot()
                if stop_result.get("status") != "ok":
                    raise UpdateError(str(stop_result.get("message") or "failed to stop bot before update"))
                stopped_for_update = True
            changed_files = self.updater.apply_loaded(loaded)
            post_backup = self.updater.create_backup(loaded, stage="post_update")
        except Exception as exc:
            self.log.exception("remote_update_apply_failed")
            try:
                rollback_restored = self.updater.restore_backup(pre_backup)
            except Exception as rollback_exc:
                raise UpdateError(f"update failed and rollback failed: {rollback_exc}") from exc
            if was_running:
                retry = self._start_bot()
                retry_msg = retry.get("message") or retry.get("status")
            else:
                retry_msg = "bot remained stopped after rollback"
            raise UpdateError(
                f"update failed, rollback restored {len(rollback_restored)} files; restart result: {retry_msg}"
            ) from exc

        restarted_engine = False
        restart_script = None
        if restart_app:
            restart_script = self.updater.schedule_app_restart(main_py="main.py", delay_sec=2.0)
            self._scheduled_restart = True
            self._scheduled_restart_script = restart_script
            QTimer.singleShot(1200, self._restart_application)
        elif was_running or stopped_for_update:
            start_result = self._start_bot()
            if start_result.get("status") != "ok":
                try:
                    restored = self.updater.restore_backup(pre_backup)
                except Exception as exc:
                    raise UpdateError(f"update failed and rollback also failed: {exc}") from exc
                retry = self._start_bot() if was_running else {"status": "ok", "message": "bot remained stopped after rollback"}
                raise UpdateError(
                    f"update failed after apply, rollback restored {len(restored)} files; restart result: {retry.get('message') or retry.get('status')}"
                )
            restarted_engine = True

        message = f"update applied: {loaded.description} ({loaded.version}) | files={len(changed_files)}"
        if restarted_engine:
            message += " | bot restarted"
        if restart_script is not None:
            message += " | app restart scheduled"
        return {
            "status": "ok",
            "message": message,
            "version": loaded.version,
            "files_changed": changed_files,
            "pre_update_backup": str(pre_backup),
            "post_update_backup": str(post_backup),
            "restart_scheduled": bool(restart_script is not None),
            "restart_script": str(restart_script) if restart_script is not None else "",
        }

    def _update_component(self, component: str) -> dict[str, Any]:
        loaded = self.updater.load_component_manifest(component)
        return self._apply_update(loaded, restart_app=False)

    def _update_full(self) -> dict[str, Any]:
        loaded = self.updater.load_full_manifest()
        return self._apply_update(loaded, restart_app=bool(loaded.restart_app or True))

    def _restart_application(self) -> None:
        if not self._scheduled_restart:
            return
        self._scheduled_restart = False
        self._scheduled_restart_script: Path | None = None
        script = self._scheduled_restart_script
        self._scheduled_restart_script = None
        try:
            if script is None:
                script = self.updater.schedule_app_restart(main_py="main.py", delay_sec=2.0)
            self.updater.launch_restart_script(script)
        except Exception:
            self.log.exception("remote_full_update_restart_launch_failed")
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()
