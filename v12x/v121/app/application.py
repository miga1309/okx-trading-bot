from __future__ import annotations

import os
import sys
from typing import Protocol

from app.runtime_bridge import reset_active_context, set_active_context


class MainWindowFactoryProtocol(Protocol):
    def create(self): ...


class BotApplication:
    def __init__(self, *, context, main_window_factory: MainWindowFactoryProtocol):
        self.context = context
        self.main_window_factory = main_window_factory

    def run(self) -> None:
        from PyQt6.QtWidgets import QApplication

        os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", self.context.settings.app_version)
        os.environ.setdefault("OKX_TURTLE_ENTRY_MODULE", self.context.settings.entry_module)
        token = set_active_context(self.context)
        from app import runtime_entry
        from app import runtime_support

        self.context.session_control.transition_to_starting()
        runtime_support.log_heartbeat("app", "startup", version=self.context.settings.app_version)
        app = QApplication(sys.argv)
        runtime_entry.install_exception_logging()
        window = self.main_window_factory.create()
        self.context.services.register_instance("main_window", window)
        self.context.session_control.transition_to_running()
        window.show()
        try:
            exit_code = app.exec()
        finally:
            reset_active_context(token)
        self.context.session_control.transition_to_stopped(exit_code=exit_code)
        runtime_support.log_heartbeat("app", "shutdown", exit_code=exit_code)
        sys.exit(exit_code)
