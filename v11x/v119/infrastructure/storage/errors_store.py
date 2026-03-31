from __future__ import annotations

from pathlib import Path


class ErrorsStore:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = Path(logs_dir)

    def list_error_logs(self) -> list[Path]:
        return sorted(self.logs_dir.glob("*_errors.log"))
