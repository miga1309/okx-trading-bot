from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Position:
    symbol: str
    side: str
    qty: float
    entry_price: float
    stop_price: float = 0.0
    pnl_pct: float = 0.0
    units: int = 1
    opened_at: datetime = field(default_factory=datetime.now)

    def opened_at_str(self) -> str:
        return self.opened_at.strftime("%H:%M:%S")


@dataclass
class ClosedTrade:
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: float
    pnl_pct: float
    opened_at: datetime
    closed_at: datetime

    def opened_at_str(self) -> str:
        return self.opened_at.strftime("%H:%M:%S")

    def closed_at_str(self) -> str:
        return self.closed_at.strftime("%H:%M:%S")


@dataclass
class Snapshot:
    created_at: datetime = field(default_factory=datetime.now)
    balance: float = 0.0
    used_margin: float = 0.0
    open_positions: int = 0
    closed_trades: int = 0
    total_pnl_pct: float = 0.0

    def created_at_str(self) -> str:
        return self.created_at.strftime("%H:%M:%S")


@dataclass
class BotState:
    is_running: bool = False
    last_update: Optional[datetime] = None
    last_engine_cycle: Optional[datetime] = None
    last_snapshot: Optional[datetime] = None
    open_positions: List[Position] = field(default_factory=list)
    closed_trades: List[ClosedTrade] = field(default_factory=list)

    def last_update_str(self) -> str:
        return self.last_update.strftime("%H:%M:%S") if self.last_update else "--:--:--"

    def last_engine_cycle_str(self) -> str:
        return self.last_engine_cycle.strftime("%H:%M:%S") if self.last_engine_cycle else "--:--:--"

    def last_snapshot_str(self) -> str:
        return self.last_snapshot.strftime("%H:%M:%S") if self.last_snapshot else "--:--:--"