from __future__ import annotations

from pathlib import Path


class AnalysisExportDialogProxy:
    def __init__(self, window, export_engine=None) -> None:
        self.window = window
        self.export_engine = export_engine

    def export(self, mode: str = 'full') -> Path | None:
        if self.export_engine is not None:
            snapshot = dict(getattr(self.window, 'latest_snapshot', {}) or {})
            cfg = getattr(self.window, 'current_cfg', None)
            return self.export_engine.export(mode=mode, snapshot=snapshot, cfg=cfg)
        fn = getattr(self.window, 'export_analysis', None)
        if callable(fn):
            fn(mode)
        return None
