# === CHANGELOG HEADER ===
# Version: v124
# Date: 2026-03-31
# Changes: release 124 bootstrap; aligns runtime version propagation, watchdog startup, and WS-first application wiring for a full Telegram update release.
# === END CHANGELOG HEADER ===

from pathlib import Path

from app.application import BotApplication
from app.app_context import AppContext
from app.event_bus import EventBus
from app.service_registry import ServiceRegistry
from config.settings import AppSettings
from domain.session.session_control_engine import SessionControlEngine
from infrastructure.exchange.exchange_gateway import ExchangeGatewayFacade
from infrastructure.logging.logger_factory import configure_logging, get_system_logger
from infrastructure.storage.analysis_store import AnalysisStore
from infrastructure.storage.errors_store import ErrorsStore
from infrastructure.storage.state_store import StateStore
from interface.gui.main_window import MainWindowFactory


def build_application(*, app_version: str, entry_module: str) -> BotApplication:
    app_dir = Path(__file__).resolve().parent
    settings = AppSettings.from_root(app_dir=app_dir, app_version=app_version, entry_module=entry_module)
    log_bundle = configure_logging(settings.logs_dir, app_version=app_version)

    event_bus = EventBus()
    services = ServiceRegistry()
    state_store = StateStore(settings.runtime_state_file)
    errors_store = ErrorsStore(settings.logs_dir)
    analysis_store = AnalysisStore(settings.analysis_exports_dir)
    exchange_gateway = ExchangeGatewayFacade()
    session_control = SessionControlEngine(event_bus=event_bus, logger=get_system_logger(), state_store=state_store)

    context = AppContext(
        settings=settings,
        event_bus=event_bus,
        services=services,
        log_bundle=log_bundle,
        state_store=state_store,
        errors_store=errors_store,
        analysis_store=analysis_store,
        exchange_gateway=exchange_gateway,
        session_control=session_control,
    )

    services.register_instance('settings', settings)
    services.register_instance('event_bus', event_bus)
    services.register_instance('log_bundle', log_bundle)
    services.register_instance('state_store', state_store)
    services.register_instance('errors_store', errors_store)
    services.register_instance('analysis_store', analysis_store)
    services.register_instance('exchange_gateway', exchange_gateway)
    services.register_instance('session_control', session_control)

    main_window_factory = MainWindowFactory(context)
    app = BotApplication(context=context, main_window_factory=main_window_factory)
    services.register_instance('application', app)
    return app
