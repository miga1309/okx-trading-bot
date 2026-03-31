from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from infrastructure.logging.logger_factory import get_engine_logger


class AnalysisExportEngine:
    def __init__(self, *, bot: object | None = None, analysis_store: object | None = None) -> None:
        self.bot = bot
        self.analysis_store = analysis_store
        self.log = get_engine_logger("analysis")

    def export(self, *, mode: str = "full", snapshot: dict | None = None, cfg: object | None = None) -> Path:
        from analysis_exporter import build_analysis_export_bundle
        import main_v107 as legacy_runtime

        effective_snapshot = dict(snapshot or getattr(self.bot, 'latest_snapshot', {}) or {})
        effective_cfg = cfg if cfg is not None else getattr(self.bot, 'cfg', None)
        archive_path = Path(build_analysis_export_bundle(
            legacy_runtime.EXPORT_BUNDLE_CONTEXT,
            mode=str(mode or 'full'),
            snapshot=effective_snapshot,
            cfg=effective_cfg,
        ))
        if self.analysis_store is not None and hasattr(self.analysis_store, 'record_export'):
            try:
                self.analysis_store.record_export(archive_path)
            except Exception:
                self.log.exception('analysis_export_store_record_failed', extra={'engine': 'analysis'})
        self.log.info('analysis_export_created mode=%s archive=%s', mode, archive_path, extra={'engine': 'analysis'})
        return archive_path

    def list_exports(self) -> list[Path]:
        if self.analysis_store is None or not hasattr(self.analysis_store, 'list_exports'):
            return []
        exports = list(self.analysis_store.list_exports())
        self.log.info('analysis_export_list size=%s', len(exports), extra={'engine': 'analysis'})
        return exports

    def snapshot(self) -> dict[str, Any]:
        exports = self.list_exports()
        latest = str(exports[-1]) if exports else ''
        return {
            'count': len(exports),
            'latest_export': latest,
            'bot_bound': self.bot is not None,
        }
