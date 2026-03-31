from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    app_dir: Path
    app_version: str
    entry_module: str
    logs_dir: Path
    runtime_dir: Path
    runtime_state_file: Path
    analysis_exports_dir: Path
    dotenv_path: Path
    telegram_worker_exe: Path

    @classmethod
    def from_root(cls, *, app_dir: Path, app_version: str, entry_module: str) -> "AppSettings":
        logs_dir = app_dir / "logs"
        runtime_dir = app_dir / "runtime"
        logs_dir.mkdir(parents=True, exist_ok=True)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        analysis_exports_dir = logs_dir / "analysis_exports"
        analysis_exports_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            app_dir=app_dir,
            app_version=app_version,
            entry_module=entry_module,
            logs_dir=logs_dir,
            runtime_dir=runtime_dir,
            runtime_state_file=logs_dir / "runtime_state.json",
            analysis_exports_dir=analysis_exports_dir,
            dotenv_path=app_dir / ".env",
            telegram_worker_exe=app_dir / "telegram_worker.exe",
        )
