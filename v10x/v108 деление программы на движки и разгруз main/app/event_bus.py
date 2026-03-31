from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable[[dict], None]) -> None:
        self._subscribers[str(event_name)].append(callback)

    def publish(self, event_name: str, payload: dict | None = None) -> None:
        event_payload = dict(payload or {})
        for callback in list(self._subscribers.get(str(event_name), [])):
            callback(event_payload)
