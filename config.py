from dataclasses import dataclass


APP_VERSION = "v0.20d"


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class GuiConfig:
    refresh_ms: int = 2000
    pnl_refresh_ms: int = 2000
    snapshot_interval_sec: int = 2
    theme_auto: bool = True
    dark_mode: bool = False


@dataclass
class RiskConfig:
    max_balance_risk_pct: float = 2.0
    max_open_positions: int = 10
    max_units_per_position: int = 4
    unit_size_pct: float = 25.0


@dataclass
class EngineConfig:
    market_poll_sec: int = 2
    position_check_sec: int = 2
    retry_delay_sec: int = 5
    enable_flat_filter: bool = True
    enable_pyramiding: bool = True


@dataclass
class ExchangeConfig:
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""
    demo_mode: bool = False


@dataclass
class AppConfig:
    telegram: TelegramConfig = TelegramConfig()
    gui: GuiConfig = GuiConfig()
    risk: RiskConfig = RiskConfig()
    engine: EngineConfig = EngineConfig()
    exchange: ExchangeConfig = ExchangeConfig()


def get_default_config() -> AppConfig:
    return AppConfig()