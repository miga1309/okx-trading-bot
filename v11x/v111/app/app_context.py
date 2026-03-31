from __future__ import annotations

from dataclasses import dataclass, field


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
    runtime_services: dict[str, object] = field(default_factory=dict)
