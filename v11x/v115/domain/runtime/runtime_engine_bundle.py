from __future__ import annotations

import logging
from dataclasses import dataclass

from app.runtime_bridge import get_active_context
from domain.balance.balance_engine import BalanceEngine
from domain.execution.execution_engine import ExecutionEngine
from domain.health.health_monitor import HealthMonitor
from domain.positions.position_lifecycle_engine import PositionLifecycleEngine
from domain.positions.position_registry import PositionRegistry
from domain.reconcile.reconcile_engine import ReconcileEngine
from domain.stops.stop_engine import ModularStopEngine


@dataclass
class RuntimeEngineBundle:
    bot: object
    registry: PositionRegistry
    position_lifecycle: PositionLifecycleEngine
    execution: ExecutionEngine
    stops: ModularStopEngine
    balance: BalanceEngine
    reconcile: ReconcileEngine
    health: HealthMonitor

    @classmethod
    def attach(cls, bot: object) -> "RuntimeEngineBundle":
        existing = getattr(bot, "runtime_engine_bundle", None)
        if existing is not None:
            return existing

        registry = PositionRegistry(bot)
        position_lifecycle = PositionLifecycleEngine(bot=bot, registry=registry)
        execution = ExecutionEngine(bot=bot, registry=registry)
        legacy_stop_engine = getattr(bot, "stop_engine", None)
        stops = ModularStopEngine(bot=bot, registry=registry, legacy_stop_engine=legacy_stop_engine)
        balance = BalanceEngine(bot=bot)
        reconcile = ReconcileEngine(bot=bot, registry=registry, stop_engine=stops)
        health = HealthMonitor(bot=bot)

        bundle = cls(
            bot=bot,
            registry=registry,
            position_lifecycle=position_lifecycle,
            execution=execution,
            stops=stops,
            balance=balance,
            reconcile=reconcile,
            health=health,
        )
        bot.runtime_engine_bundle = bundle
        bot.position_registry = registry
        bot.position_lifecycle = position_lifecycle
        bot.execution_engine = execution
        bot.stop_runtime_engine = stops
        bot.balance_engine = balance
        bot.reconcile_engine = reconcile
        bot.health_monitor = health

        logger = logging.getLogger("engine.app")
        logger.info(
            "runtime_engine_bundle_attached positions=%s closed=%s",
            registry.open_count(),
            registry.closed_count(),
            extra={"engine": "app"},
        )

        context = get_active_context()
        if context is not None:
            try:
                services = getattr(context, "services", None)
                if services is not None:
                    services.register_instance("position_registry", registry)
                    services.register_instance("position_lifecycle", position_lifecycle)
                    services.register_instance("execution_engine", execution)
                    services.register_instance("stop_runtime_engine", stops)
                    services.register_instance("balance_engine", balance)
                    services.register_instance("reconcile_engine", reconcile)
                    services.register_instance("health_monitor", health)
                    services.register_instance("runtime_engine_bundle", bundle)
                exchange_gateway = getattr(context, "exchange_gateway", None)
                if exchange_gateway is not None and hasattr(exchange_gateway, "bind_runtime_gateway"):
                    exchange_gateway.bind_runtime_gateway(getattr(bot, "gateway", None))
                session_control = getattr(context, "session_control", None)
                if session_control is not None and hasattr(session_control, "publish_runtime_bind"):
                    session_control.publish_runtime_bind(bot=bot, bundle=bundle)
            except Exception:
                logger.exception("failed_to_register_runtime_engine_bundle", extra={"engine": "app"})
        return bundle
