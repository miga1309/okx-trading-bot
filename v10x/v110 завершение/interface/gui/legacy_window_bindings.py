from __future__ import annotations

from app.runtime_bridge import get_active_context
from infrastructure.logging.logger_factory import get_engine_logger
from interface.gui.dialogs.analysis_export_dialog import AnalysisExportDialogProxy
from interface.gui.dialogs.manual_entry_dialog import ManualEntryDialogProxy
from interface.gui.presenters.balance_presenter import BalancePresenter
from interface.gui.presenters.health_presenter import HealthPresenter
from interface.gui.presenters.logs_presenter import LogsPresenter
from interface.gui.presenters.positions_presenter import PositionsPresenter
from interface.gui.presenters.scanner_presenter import ScannerPresenter


class LegacyWindowBindings:
    def __init__(self, context) -> None:
        self.context = context
        self.log = get_engine_logger('gui')

    def attach(self, window):
        window.app_context = self.context
        window.resolve_service = lambda name, default=None: self.context.services.optional(name, default)
        window.positions_presenter = PositionsPresenter()
        window.scanner_presenter = ScannerPresenter()
        window.balance_presenter = BalancePresenter()
        window.health_presenter = HealthPresenter()
        window.logs_presenter = LogsPresenter()
        window.manual_entry_dialog_proxy = ManualEntryDialogProxy(window)
        window.analysis_export_dialog_proxy = AnalysisExportDialogProxy(window, self.context.services.optional('analysis_export_engine'))
        window.collect_architecture_snapshot = lambda: self.collect_architecture_snapshot(window)
        self.log.info('legacy_window_bindings_attached window=%s', window.__class__.__name__, extra={'engine': 'gui'})
        return window

    def collect_architecture_snapshot(self, window) -> dict:
        snapshot = dict(getattr(window, 'latest_snapshot', {}) or {})
        context = get_active_context() or self.context
        services = getattr(context, 'services', None)
        scanner_engine = services.optional('scanner_engine') if services is not None else None
        trading_engine = services.optional('trading_engine') if services is not None else None
        analysis_engine = services.optional('analysis_export_engine') if services is not None else None
        return {
            'positions': window.positions_presenter.present(snapshot),
            'scanner': window.scanner_presenter.present(snapshot),
            'balance': window.balance_presenter.present(snapshot),
            'health': window.health_presenter.present(snapshot),
            'logs': window.logs_presenter.present(list((snapshot.get('logs') or [])) if isinstance(snapshot, dict) else []),
            'scanner_engine': scanner_engine.summary() if scanner_engine is not None and hasattr(scanner_engine, 'summary') else {},
            'trading_engine': trading_engine.snapshot() if trading_engine is not None and hasattr(trading_engine, 'snapshot') else {},
            'analysis_engine': analysis_engine.snapshot() if analysis_engine is not None and hasattr(analysis_engine, 'snapshot') else {},
        }
