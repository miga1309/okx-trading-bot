from __future__ import annotations


class MainWindowFactory:
    def __init__(self, context) -> None:
        self.context = context

    def create(self):
        import main_v107 as legacy_runtime

        return legacy_runtime.MainWindow()
