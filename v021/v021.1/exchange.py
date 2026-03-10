from typing import Any, Dict, List, Optional

from okx.Account import AccountAPI
from okx.MarketData import MarketAPI
from okx.PublicData import PublicAPI
from okx.Trade import TradeAPI


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


class OKXGateway:
    def __init__(self, cfg):
        self.cfg = cfg

        flag = "1" if getattr(cfg, "demo_mode", False) else "0"

        self.trade_api = TradeAPI(
            api_key=cfg.api_key,
            api_secret_key=cfg.api_secret,
            passphrase=cfg.api_passphrase,
            use_server_time=False,
            flag=flag,
        )
        self.account_api = AccountAPI(
            api_key=cfg.api_key,
            api_secret_key=cfg.api_secret,
            passphrase=cfg.api_passphrase,
            use_server_time=False,
            flag=flag,
        )
        self.market_api = MarketAPI(
            api_key=cfg.api_key,
            api_secret_key=cfg.api_secret,
            passphrase=cfg.api_passphrase,
            use_server_time=False,
            flag=flag,
        )
        self.public_api = PublicAPI(
            api_key=cfg.api_key,
            api_secret_key=cfg.api_secret,
            passphrase=cfg.api_passphrase,
            use_server_time=False,
            flag=flag,
        )

        self._inst_cache: Dict[str, Dict[str, Any]] = {}

    # --------------------------- instruments -----------------------------

    def get_swap_instruments(self) -> List[str]:
        resp = self.public_api.get_instruments(instType="SWAP")
        data = resp.get("data", []) if isinstance(resp, dict) else []
        result: List[str] = []

        for row in data:
            inst_id = row.get("instId")
            if inst_id:
                result.append(inst_id)
                self._inst_cache[inst_id] = row

        return result

    def list_swap_instruments(self) -> List[str]:
        return self.get_swap_instruments()

    def get_instruments(self) -> List[str]:
        return self.get_swap_instruments()

    def list_instruments(self) -> List[str]:
        return self.get_swap_instruments()

    # ----------------------------- candles ------------------------------

    def get_candles(self, inst_id: str, timeframe: str, limit: int = 100):
        bar = timeframe
        resp = self.market_api.get_candlesticks(instId=inst_id, bar=bar, limit=str(limit))
        return resp.get("data", []) if isinstance(resp, dict) else []

    def fetch_candles(self, inst_id: str, timeframe: str, limit: int = 100):
        return self.get_candles(inst_id, timeframe, limit)

    def candles(self, inst_id: str, timeframe: str, limit: int = 100):
        return self.get_candles(inst_id, timeframe, limit)

    # ----------------------------- balance ------------------------------

    def get_available_balance(self) -> float:
        ccy = getattr(self.cfg, "quote_ccy", "USDT")
        resp = self.account_api.get_account_balance(ccy=ccy)
        data = resp.get("data", []) if isinstance(resp, dict) else []

        for acc in data:
            details = acc.get("details", [])
            for row in details:
                if row.get("ccy") == ccy:
                    return _safe_float(row.get("availBal"))

        return 0.0

    def fetch_available_balance(self) -> float:
        return self.get_available_balance()

    def get_balance(self) -> float:
        return self.get_available_balance()

    def fetch_balance(self) -> float:
        return self.get_available_balance()

    # ----------------------------- positions ----------------------------

    def get_positions(self):
        resp = self.account_api.get_positions(instType="SWAP")
        return resp.get("data", []) if isinstance(resp, dict) else []

    def fetch_positions(self):
        return self.get_positions()

    def list_positions(self):
        return self.get_positions()

    # ----------------------------- helpers ------------------------------

    def format_size(self, inst_id: str, qty: float) -> str:
        info = self._inst_cache.get(inst_id)
        if info is None:
            self.get_swap_instruments()
            info = self._inst_cache.get(inst_id, {})

        lot_sz = _safe_float(info.get("lotSz"), 0.0)
        min_sz = _safe_float(info.get("minSz"), 0.0)

        q = max(qty, min_sz if min_sz > 0 else qty)

        if lot_sz > 0:
            steps = int(q / lot_sz)
            q = steps * lot_sz
            if q < min_sz:
                q = min_sz

        if q >= 100:
            return f"{q:.0f}"
        if q >= 1:
            return f"{q:.4f}".rstrip("0").rstrip(".")
        return f"{q:.8f}".rstrip("0").rstrip(".")

    def _format_sz(self, inst_id: str, qty: float) -> str:
        return self.format_size(inst_id, qty)

    # ----------------------------- orders -------------------------------

    def place_market_order(
        self,
        inst_id: str,
        side: str,
        pos_side: Optional[str],
        sz: str,
        reduce_only: bool = False,
    ) -> dict:
        params = {
            "instId": inst_id,
            "tdMode": getattr(self.cfg, "td_mode", "cross"),
            "side": side,
            "ordType": "market",
            "sz": sz,
        }

        if reduce_only:
            params["reduceOnly"] = "true"

        # posSide добавляем только если явно включен режим hedge
        if getattr(self.cfg, "use_pos_side", False) and pos_side:
            params["posSide"] = pos_side

        return self.trade_api.place_order(**params)

    def create_market_order(
        self,
        inst_id: str,
        side: str,
        pos_side: Optional[str],
        sz: str,
        reduce_only: bool = False,
    ) -> dict:
        return self.place_market_order(inst_id, side, pos_side, sz, reduce_only)

    def market_order(
        self,
        inst_id: str,
        side: str,
        pos_side: Optional[str],
        sz: str,
        reduce_only: bool = False,
    ) -> dict:
        return self.place_market_order(inst_id, side, pos_side, sz, reduce_only)

    def close_position(self, inst_id: str, pos_side: Optional[str] = None) -> dict:
        params = {
            "instId": inst_id,
            "mgnMode": getattr(self.cfg, "td_mode", "cross"),
        }

        if getattr(self.cfg, "use_pos_side", False) and pos_side:
            params["posSide"] = pos_side

        return self.trade_api.close_positions(**params)

    def close_positions(self, inst_id: str, pos_side: Optional[str] = None) -> dict:
        return self.close_position(inst_id, pos_side)