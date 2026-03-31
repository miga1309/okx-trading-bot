
import json
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox

from integration.telegram.notifier import (
    APP_DIR,
    PROJECT_ROOT,
    resolve_log_file,
    resolve_pid_file,
    resolve_status_file,
    run_worker_forever,
)

WINDOW_TITLE = "Telegram Worker Control"
REFRESH_MS = 1500
LOG_TAIL_LINES = 18


class TelegramWorkerControlApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("820x560")
        self.root.minsize(760, 500)

        self.app_dir = Path(APP_DIR)
        self.project_root = Path(PROJECT_ROOT)
        self.pid_file = resolve_pid_file(None)
        self.status_file = resolve_status_file(None)
        self.log_file = resolve_log_file(None)
        self.remote_state_file = self.project_root / "runtime" / "remote_bridge" / "state" / "remote_state.json"
        self.python_exe = Path(sys.executable).resolve()
        self._after_id: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.worker_stop_event: Optional[threading.Event] = None

        self.status_vars = {
            "worker": tk.StringVar(value="unknown"),
            "pid": tk.StringVar(value="-"),
            "updated": tk.StringVar(value="-"),
            "bot": tk.StringVar(value="-"),
            "queue": tk.StringVar(value="-"),
            "bridge": tk.StringVar(value="-"),
            "log": tk.StringVar(value=str(self.log_file)),
            "launcher": tk.StringVar(value=self._launcher_desc()),
            "health": tk.StringVar(value="-"),
        }
        self.auto_refresh = tk.BooleanVar(value=True)
        self.log_tail_text = tk.StringVar(value="")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Telegram Worker", font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Checkbutton(header, text="Auto refresh", variable=self.auto_refresh, command=self._toggle_auto_refresh).pack(side="right")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(10, 10))
        ttk.Button(actions, text="Start", command=self.start_worker).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Stop", command=self.stop_worker).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Restart", command=self.restart_worker).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open Log", command=self.open_log).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open Runtime", command=self.open_runtime_dir).pack(side="left")

        info = ttk.LabelFrame(outer, text="Status", padding=10)
        info.pack(fill="x")
        rows = [
            ("Worker", "worker"),
            ("PID", "pid"),
            ("Updated", "updated"),
            ("Bot", "bot"),
            ("Health", "health"),
            ("Launcher", "launcher"),
            ("Log file", "log"),
            ("Queue", "queue"),
            ("Bridge", "bridge"),
        ]
        for idx, (label, key) in enumerate(rows):
            ttk.Label(info, text=f"{label}:", width=12).grid(row=idx, column=0, sticky="w", pady=2, padx=(0, 8))
            ttk.Label(info, textvariable=self.status_vars[key]).grid(row=idx, column=1, sticky="w", pady=2)
        info.columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(outer, text="Log tail", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log_widget = tk.Text(log_frame, wrap="word", height=18, font=("Consolas", 9))
        self.log_widget.pack(side="left", fill="both", expand=True)
        self.log_widget.configure(state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_widget.yview)
        scroll.pack(side="right", fill="y")
        self.log_widget.configure(yscrollcommand=scroll.set)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text=f"Project root: {self.project_root}").pack(side="left")

    def _launcher_desc(self) -> str:
        return "embedded worker in telegram_worker_gui.exe"

    def _worker_thread_alive(self) -> bool:
        return bool(self.worker_thread and self.worker_thread.is_alive())

    def _read_status_payload(self) -> dict:
        try:
            if self.status_file.exists():
                return json.loads(self.status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _read_remote_state_payload(self) -> dict:
        try:
            if self.remote_state_file.exists():
                return json.loads(self.remote_state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _read_pid(self) -> Optional[int]:
        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
            return int(raw) if raw else None
        except Exception:
            return None

    def _pid_alive(self, pid: Optional[int]) -> bool:
        if not pid or pid <= 0:
            return False
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=5,
                )
                text = (result.stdout or "") + "\n" + (result.stderr or "")
                return str(pid) in text and "No tasks are running" not in text
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _tail_log(self, path: Path, lines: int = LOG_TAIL_LINES) -> str:
        if not path.exists():
            return "Log file not found yet."
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Failed to read log: {exc}"
        chunks = text.splitlines()[-lines:]
        return "\n".join(chunks) if chunks else "Log file is empty."

    def _set_log_tail(self, text: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.insert("1.0", text)
        self.log_widget.configure(state="disabled")

    def refresh(self) -> None:
        status = self._read_status_payload()
        remote = self._read_remote_state_payload()
        pid = self._read_pid()
        alive = self._worker_thread_alive() or self._pid_alive(pid)
        updated_at = str((remote.get("updated_at") if isinstance(remote, dict) else None) or status.get("updated_at") or status.get("started_at") or "-")
        queue_dir = str(status.get("queue_dir") or self.project_root / "runtime" / "telegram_queue")
        bridge_dir = str((status.get("remote_bridge_dir") or (remote.get("bridge_dir") if isinstance(remote, dict) else None)) or self.project_root / "runtime" / "remote_bridge")
        remote_health = dict(remote.get("health") or {}) if isinstance(remote, dict) else {}
        health = status.get("health") or {}
        health_text = str(remote_health.get("connectivity_state") or remote_health.get("engine") or health.get("connectivity_state") or health.get("telegram_worker") or ("CONNECTED" if alive else "IDLE"))
        engine_state = str((remote.get("engine") if isinstance(remote, dict) else None) or remote_health.get("engine") or status.get("engine") or health.get("engine") or "").strip().upper()
        status_bot_flag = bool((remote.get("bot_running") if isinstance(remote, dict) else False) or status.get("bot_running", False))
        if status_bot_flag or engine_state == "RUNNING":
            bot_running = "RUNNING"
        elif engine_state in {"STARTING", "STOPPING", "RECOVERING"}:
            bot_running = engine_state
        else:
            bot_running = "STOPPED"

        self.status_vars["worker"].set("RUNNING" if alive else "STOPPED")
        self.status_vars["pid"].set(str(pid or "-"))
        self.status_vars["updated"].set(updated_at)
        self.status_vars["bot"].set(bot_running)
        self.status_vars["queue"].set(queue_dir)
        self.status_vars["bridge"].set(bridge_dir)
        self.status_vars["launcher"].set(self._launcher_desc())
        self.status_vars["health"].set(health_text)
        self.status_vars["log"].set(str(self.log_file))
        self._set_log_tail(self._tail_log(self.log_file))

        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.auto_refresh.get():
            self._after_id = self.root.after(REFRESH_MS, self.refresh)

    def _toggle_auto_refresh(self) -> None:
        self._schedule_refresh()

    def _spawn_worker(self) -> None:
        if self._worker_thread_alive():
            return
        self.worker_stop_event = threading.Event()

        def _runner() -> None:
            run_worker_forever(stop_event=self.worker_stop_event)

        self.worker_thread = threading.Thread(target=_runner, name="TelegramWorkerThread", daemon=True)
        self.worker_thread.start()

    def start_worker(self) -> None:
        pid = self._read_pid()
        if self._worker_thread_alive() or self._pid_alive(pid):
            messagebox.showinfo(WINDOW_TITLE, "Telegram worker is already running.")
            return
        try:
            self._spawn_worker()
            time.sleep(0.6)
            self.refresh()
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, f"Failed to start worker:\n{exc}")

    def _terminate_pid(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=10)
            return
        os.kill(pid, signal.SIGTERM)

    def stop_worker(self) -> None:
        pid = self._read_pid()
        if self._worker_thread_alive():
            try:
                if self.worker_stop_event is not None:
                    self.worker_stop_event.set()
                if self.worker_thread is not None:
                    self.worker_thread.join(timeout=8.0)
                self.refresh()
                return
            except Exception as exc:
                messagebox.showerror(WINDOW_TITLE, f"Failed to stop worker:\n{exc}")
                return
        if not self._pid_alive(pid):
            self.refresh()
            messagebox.showinfo(WINDOW_TITLE, "Telegram worker is not running.")
            return
        try:
            self._terminate_pid(int(pid))
            deadline = time.time() + 8.0
            while time.time() < deadline:
                if not self._pid_alive(pid):
                    break
                time.sleep(0.25)
            self.refresh()
        except Exception as exc:
                messagebox.showerror(WINDOW_TITLE, f"Failed to stop worker:\n{exc}")

    def restart_worker(self) -> None:
        pid = self._read_pid()
        if self._worker_thread_alive() or self._pid_alive(pid):
            try:
                self._terminate_pid(int(pid))
                time.sleep(0.8)
            except Exception as exc:
                messagebox.showerror(WINDOW_TITLE, f"Failed to stop worker before restart:\n{exc}")
                return
        self.start_worker()

    def open_log(self) -> None:
        try:
            target = self.log_file if self.log_file.exists() else self.project_root
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                webbrowser.open(target.as_uri())
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, f"Failed to open log:\n{exc}")

    def open_runtime_dir(self) -> None:
        runtime_dir = self.project_root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(runtime_dir))  # type: ignore[attr-defined]
            else:
                webbrowser.open(runtime_dir.as_uri())
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, f"Failed to open runtime dir:\n{exc}")

    def _on_close(self) -> None:
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        if self._worker_thread_alive() and self.worker_stop_event is not None:
            try:
                self.worker_stop_event.set()
                if self.worker_thread is not None:
                    self.worker_thread.join(timeout=3.0)
            except Exception:
                pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    TelegramWorkerControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
