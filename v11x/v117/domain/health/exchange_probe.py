from __future__ import annotations

from domain.health.exchange_health import classify_connectivity_state


def probe_from_components(components: dict) -> tuple[str, dict]:
    return classify_connectivity_state(components)
