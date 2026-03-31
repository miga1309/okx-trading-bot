from __future__ import annotations

from interface.gui.legacy_window_bindings import LegacyWindowBindings


class MainWindowFactory:
    def __init__(self, context) -> None:
        self.context = context
        self.bindings = LegacyWindowBindings(context)

    def create(self):
        from interface.gui.legacy_gui_runtime import MainWindow

        window = MainWindow()
        return self.bindings.attach(window)
