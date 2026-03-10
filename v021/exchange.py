import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Optional, Tuple

import okx.Account as Account
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.Trade as Trade

from app_core import (
    BotConfig,
    EngineStatsLogger,
    PositionState,
    TradeLogger,
    is_hidden_instrument,
    TRADE_CSV,
    ENGINE_STATS_FILE,
)

class OkxGateway:
    COMPLIANCE_RESTRICTION_CODES = {"51155"}
    LOT_SIZE_ERROR_CODES = {"51121"}
    MAX_MARKET_SIZE_ERROR_CODES = {"51202"}

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.account_api = Account.AccountAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.trade_api = Trade.TradeAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.market_api = MarketData.MarketAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.public_api = PublicData.PublicAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.instrument_cache: Dict[str, dict] = {}
        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)
        self.refresh_instruments()

    def refresh_instruments(self) -> None:
        resp = self.public_api.get_instruments(instType="SWAP")
        data = resp.get("data", [])
        instruments = {}
        for row in data:
            inst_id = row.get("instId", "")
            if not inst_id.endswith("-USDT-SWAP"):
                continue
            if is_hidden_instrument(inst_id):
                continue
            if inst_id in self.cfg.blacklist:
                continue
            instruments[inst_id] = row
        self.instrument_cache = instruments

    def get_swap_instruments(self) -> List[str]:
        if not self.instrument_cache:
            self.refresh_instruments()
        return sorted(self.instrument_cache.keys())

    def get_balance(self) -> float:
        resp = self.account_api.get_account_balance()
        data = resp.get("data", [])
        if not data:
            return 0.0
        details = data[0].get("details", [])
        for d in details:
            if d.get("ccy") == "USDT":
                return float(d.get("availBal") or d.get("cashBal") or 0.0)
        return 0.0

    def get_positions(self) -> List[dict]:
        resp = self.account_api.get_positions(instType="SWAP")
        return resp.get("data", [])

    def set_leverage(self, inst_id: str, lever: int, td_mode: str) -> None:
        try:
            self.account_api.set_leverage(instId=inst_id, lever=str(lever), mgnMode=td_mode)
        except Exception as e:
            logging.warning("set_leverage failed for %s: %s", inst_id, e)

    def get_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        resp = self.market_api.get_candlesticks(instId=inst_id, bar=bar, limit=str(limit + 1))
        raw = resp.get("data", [])
        if len(raw) < limit + 1:
            return []
        closed = raw[1 : limit + 1]
        closed.reverse()
        candles: List[List[float]] = []
        for row in closed:
            candles.append([
                int(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]) if len(row) > 5 else 0.0,
            ])
        return candles

    def get_ticker_last(self, inst_id: str) -> float:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return float(data[0]["last"])

    def instrument_info(self, inst_id: str) -> dict:
        info = self.instrument_cache.get(inst_id)
        if not info:
            self.refresh_instruments()
            info = self.instrument_cache.get(inst_id)
        if not info:
            raise KeyError(f"Instrument not found: {inst_id}")
        return info

    def close_position(self, inst_id: str, note: str = "") -> dict:
        logging.info("Closing position %s. %s", inst_id, note)
        return self.trade_api.close_positions(instId=inst_id, mgnMode=self.cfg.td_mode)

    def place_market_order(self, inst_id: str, side: str, pos_side: str, sz: str, reduce_only: bool = False) -> dict:
        return self.trade_api.place_order(
            instId=inst_id,
            tdMode=self.cfg.td_mode,
            side=side,
            posSide=pos_side,
            ordType="market",
            sz=sz,
            reduceOnly="true" if reduce_only else "false",
        )

    @staticmethod
    def _to_decimal(value: object, default: str = "0") -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    def round_qty_to_lot(self, inst_id: str, qty: float) -> float:
        info = self.instrument_info(inst_id)
        lot_sz = self._to_decimal(info.get("lotSz", "1"), "1")
        qty_dec = self._to_decimal(qty, "0")
        if lot_sz <= 0:
            return float(qty_dec)
        rounded = (qty_dec / lot_sz).quantize(Decimal("1"), rounding=ROUND_DOWN) * lot_sz
        return float(rounded)

    def min_order_qty(self, inst_id: str) -> float:
        info = self.instrument_info(inst_id)
        return float(self._to_decimal(info.get("minSz", "1"), "1"))

    def contract_value(self, inst_id: str) -> float:
        info = self.instrument_info(inst_id)
        return float(self._to_decimal(info.get("ctVal", "1"), "1"))

    def max_order_size_market(self, inst_id: str, td_mode: str) -> Optional[float]:
        try:
            resp = self.account_api.get_max_order_size(instId=inst_id, tdMode=td_mode)
            data = resp.get("data", [])
            if not data:
                return None
            row = data[0]
            for key in ("maxBuy", "maxSell", "maxMktSz", "maxMktBuySz", "maxMktSellSz"):
                val = row.get(key)
                if val not in (None, "", "0"):
                    return float(val)
        except Exception as e:
            logging.warning("get_max_order_size failed for %s: %s", inst_id, e)
        return None