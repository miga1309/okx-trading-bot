from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppContext:
    settings: object
    event_bus: object
    services: object
    log_bundle: object
    state_store: object
    errors_store: object
    analysis_store: object
    exchange_gateway: object
    session_control: object
