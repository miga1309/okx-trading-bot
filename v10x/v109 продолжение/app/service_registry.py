from __future__ import annotations


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, object] = {}

    def register_instance(self, name: str, service: object) -> None:
        self._services[str(name)] = service

    def get(self, name: str) -> object:
        return self._services[name]

    def optional(self, name: str, default=None):
        return self._services.get(name, default)
