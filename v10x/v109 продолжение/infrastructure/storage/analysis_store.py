from __future__ import annotations

from pathlib import Path


class AnalysisStore:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def list_exports(self) -> list[Path]:
        return sorted(self.export_dir.glob("*.zip"))
