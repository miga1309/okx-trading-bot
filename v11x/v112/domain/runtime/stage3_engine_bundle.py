from __future__ import annotations

from dataclasses import dataclass

from analysis.export_engine import AnalysisExportEngine
from app.runtime_bridge import get_active_context
from domain.scanner.scanner_engine import ScannerEngine
from domain.trading.trading_engine import TradingEngine
from infrastructure.logging.logger_factory import get_engine_logger


@dataclass
class Stage3EngineBundle:
    bot: object
    scanner: ScannerEngine
    trading: TradingEngine
    analysis: AnalysisExportEngine

    @classmethod
    def attach(cls, bot: object) -> 'Stage3EngineBundle':
        existing = getattr(bot, 'stage3_engine_bundle', None)
        if existing is not None:
            return existing

        registry = getattr(bot, 'position_registry', None)
        scanner = ScannerEngine(bot=bot)
        trading = TradingEngine(bot=bot, registry=registry, scanner_engine=scanner)
        context = get_active_context()
        analysis_store = getattr(context, 'analysis_store', None) if context is not None else None
        analysis = AnalysisExportEngine(bot=bot, analysis_store=analysis_store)

        bundle = cls(bot=bot, scanner=scanner, trading=trading, analysis=analysis)
        bot.stage3_engine_bundle = bundle
        bot.scanner_engine = scanner
        bot.trading_engine = trading
        bot.analysis_export_engine = analysis

        logger = get_engine_logger('app')
        logger.info('stage3_engine_bundle_attached scanner=%s trading=%s analysis=%s', scanner is not None, trading is not None, analysis is not None, extra={'engine': 'app'})

        if context is not None:
            try:
                services = getattr(context, 'services', None)
                if services is not None:
                    services.register_instance('scanner_engine', scanner)
                    services.register_instance('trading_engine', trading)
                    services.register_instance('analysis_export_engine', analysis)
                    services.register_instance('stage3_engine_bundle', bundle)
                runtime_services = getattr(context, 'runtime_services', None)
                if isinstance(runtime_services, dict):
                    runtime_services.update({
                        'scanner_engine': scanner,
                        'trading_engine': trading,
                        'analysis_export_engine': analysis,
                        'stage3_engine_bundle': bundle,
                    })
            except Exception:
                logger.exception('failed_to_register_stage3_engine_bundle', extra={'engine': 'app'})
        return bundle
