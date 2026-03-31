from __future__ import annotations

from threading import RLock
from typing import Optional

_LOCK = RLock()
_ACTIVE_CONTEXT: object | None = None


def set_active_context(context: object | None) -> object | None:
    global _ACTIVE_CONTEXT
    with _LOCK:
        previous = _ACTIVE_CONTEXT
        _ACTIVE_CONTEXT = context
        return previous


def reset_active_context(previous: object | None) -> None:
    global _ACTIVE_CONTEXT
    with _LOCK:
        _ACTIVE_CONTEXT = previous


def get_active_context() -> Optional[object]:
    with _LOCK:
        return _ACTIVE_CONTEXT
