from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def launch_watchdog(*, app_version: str) -> Optional[subprocess.Popen]:
    try:
        helper = Path(__file__).resolve().with_name("watchdog_helper.py")
        if not helper.exists():
            return None
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        cmd = [sys.executable, "-u", str(helper), "--pid", str(os.getpid()), "--version", str(app_version or "")]
        return subprocess.Popen(cmd, cwd=str(helper.parent.parent), creationflags=creationflags)
    except Exception:
        return None


def stop_watchdog(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
    except Exception:
        pass
