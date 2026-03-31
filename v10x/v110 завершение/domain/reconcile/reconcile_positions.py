from __future__ import annotations

import logging

from sync_position_manager import restore_sync_position_state


class ReconcilePositions:
    def __init__(self, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.log = logging.getLogger("engine.reconcile")

    def sync_from_exchange(self) -> None:
        self.log.info("reconcile_sync_positions_from_exchange", extra={"engine": "reconcile"})
        return self.bot.sync_positions_from_exchange()

    def restore_sync_position_state(self, state, *, inst_id: str, pos_side: str, avg_px: float, last_px: float, qty: float, atr: float) -> list[str]:
        journal_file = getattr(self.bot, "position_journal_file", None)
        if journal_file is None:
            try:
                import sys
                module = sys.modules.get(self.bot.__class__.__module__)
                journal_file = getattr(module, "POSITION_JOURNAL_FILE", None)
            except Exception:
                journal_file = None
        cfg = getattr(self.bot, "cfg", None)
        return restore_sync_position_state(state, cfg, inst_id, pos_side, avg_px, last_px, qty, atr, journal_file=journal_file)
