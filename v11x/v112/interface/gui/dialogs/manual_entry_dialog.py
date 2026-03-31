from __future__ import annotations


class ManualEntryDialogProxy:
    def __init__(self, window) -> None:
        self.window = window

    def show(self, payload: dict) -> None:
        fn = getattr(self.window, 'show_manual_entry_dialog', None)
        if callable(fn):
            fn(payload)
