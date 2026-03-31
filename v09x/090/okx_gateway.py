from __future__ import annotations

import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Optional, Callable

import okx.Account as Account
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.Trade as Trade

from trade_models import BotConfig

class OkxGateway:
    COMPLIANCE_RESTRICTION_CODES = {"51155"}
    LOT_SIZE_ERROR_CODES = {"51121"}
    POSITION_LIMIT_ERROR_CODES = {"54031"}
    CLOSE_MARKET_LIMIT_ERROR_CODES = {"51108"}
    CLOSE_REQUIRES_PENDING_CANCEL_CODES = {"51115", "51117"}

    def __init__(self, cfg: BotConfig, hidden_checker: Optional[Callable[[object], bool]] = None):
        self.hidden_checker = hidden_checker or (lambda _inst_id: False)
        self.cfg = cfg
        self.account_api = Account.AccountAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.market_api = MarketData.MarketAPI(flag=cfg.flag)
        self.public_api = PublicData.PublicAPI(flag=cfg.flag)
        self.trade_api = Trade.TradeAPI(cfg.api_key, cfg.secret_key, cfg.passphrase, False, cfg.flag)
        self.instrument_cache: Dict[str, dict] = {}
        self.swap_ids: List[str] = []
        self.cache: Optional[MarketDataCache] = None
        self.engine_ref = None
        self.refresh_instruments()

    def refresh_instruments(self) -> None:
        resp = self.public_api.get_instruments(instType="SWAP")
        data = resp.get("data", [])
        self.instrument_cache = {x["instId"]: x for x in data if x.get("state") == "live"}
        self.swap_ids = sorted([
            inst_id for inst_id in self.instrument_cache
            if inst_id.endswith("-USDT-SWAP") and not self.hidden_checker(inst_id)
        ])
        logging.info("Loaded %s swap instruments", len(self.swap_ids))

    def get_account_balance(self) -> dict:
        return self.account_api.get_account_balance()

    def get_positions(self) -> List[dict]:
        resp = self.account_api.get_positions(instType="SWAP")
        return resp.get("data", [])

    def attach_cache(self, cache: Optional[MarketDataCache]) -> None:
        self.cache = cache

    def fetch_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        # OKX returns newest first; convert to oldest -> newest and close only closed candles (skip newest forming candle).
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

    def get_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        if self.cache is not None:
            cached = self.cache.get_candles(inst_id, bar, limit)
            if cached is not None:
                return cached
        candles = self.fetch_candles(inst_id, bar, limit)
        if candles and self.cache is not None:
            self.cache.put_candles(inst_id, bar, candles)
        return candles

    def fetch_ticker_data(self, inst_id: str) -> dict:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return data[0]

    def get_ticker_last(self, inst_id: str) -> float:
        data = self.get_ticker_data(inst_id)
        return float(data["last"])

    def get_ticker_data(self, inst_id: str) -> dict:
        if self.cache is not None:
            cached = self.cache.get_ticker(inst_id)
            if cached is not None:
                return cached
        data = self.fetch_ticker_data(inst_id)
        if self.cache is not None:
            self.cache.put_ticker(inst_id, data)
        return data

    def instrument_info(self, inst_id: str) -> dict:
        info = self.instrument_cache.get(inst_id)
        if not info:
            self.refresh_instruments()
            info = self.instrument_cache.get(inst_id)
        if not info:
            raise KeyError(f"Instrument not found: {inst_id}")
        return info

    def get_pending_orders(self, inst_id: str) -> List[dict]:
        try:
            resp = self.trade_api.get_order_list(instType="SWAP", instId=inst_id)
            return list(resp.get("data", []) or [])
        except Exception as exc:
            logging.warning("Failed to load pending orders for %s: %s", inst_id, exc)
            return []

    def cancel_pending_orders(self, inst_id: str) -> dict:
        pending = self.get_pending_orders(inst_id)
        payload = []
        for order in pending:
            ord_id = str(order.get("ordId") or "").strip()
            cl_ord_id = str(order.get("clOrdId") or "").strip()
            if not ord_id and not cl_ord_id:
                continue
            item = {"instId": inst_id}
            if ord_id:
                item["ordId"] = ord_id
            elif cl_ord_id:
                item["clOrdId"] = cl_ord_id
            payload.append(item)
        if not payload:
            return {"code": "0", "msg": "no_pending_orders", "count": 0, "data": []}
        resp = self.trade_api.cancel_multiple_orders(payload)
        resp["count"] = len(payload)
        return resp

    def get_pending_algo_orders(self, inst_id: str) -> List[dict]:
        rows: List[dict] = []
        seen: set[tuple[str, str]] = set()
        for ord_type in ("conditional", "oco", "trigger", "move_order_stop", "iceberg", "twap", "chase"):
            try:
                resp = self.trade_api.order_algos_list(ordType=ord_type, instType="SWAP", instId=inst_id)
                for row in list(resp.get("data", []) or []):
                    algo_id = str(row.get("algoId") or "").strip()
                    if not algo_id:
                        continue
                    key = (ord_type, algo_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
            except Exception:
                continue
        return rows

    def cancel_pending_algo_orders(self, inst_id: str) -> dict:
        pending = self.get_pending_algo_orders(inst_id)
        payload = []
        for row in pending:
            algo_id = str(row.get("algoId") or "").strip()
            if not algo_id:
                continue
            payload.append({
                "instId": inst_id,
                "algoId": algo_id,
            })
        if not payload:
            return {"code": "0", "msg": "no_pending_algo_orders", "count": 0, "data": []}
        resp = self.trade_api.cancel_algo_order(payload)
        resp["count"] = len(payload)
        return resp

    def cancel_pending_close_orders(self, inst_id: str) -> dict:
        normal = self.cancel_pending_orders(inst_id)
        algo = self.cancel_pending_algo_orders(inst_id)
        return {
            "code": "0" if normal.get("code") == "0" and algo.get("code") == "0" else "1",
            "msg": "pending_close_orders_cancelled" if normal.get("code") == "0" and algo.get("code") == "0" else "pending_close_orders_cancel_failed",
            "normal": normal,
            "algo": algo,
        }

    def place_exchange_stop(self, inst_id: str, position_side: str, qty: float, trigger_px: float) -> dict:
        info = self.instrument_info(inst_id)
        lot_sz = float(info.get("lotSz") or 1.0)
        size = self.format_size(qty, lot_sz)
        close_side = "sell" if position_side == "long" else "buy"
        trigger_text = (f"{float(trigger_px):.12f}").rstrip("0").rstrip(".")
        params = dict(
            instId=inst_id,
            tdMode=self.cfg.td_mode,
            side=close_side,
            posSide="net",
            ordType="conditional",
            sz=size,
            slTriggerPx=trigger_text,
            slOrdPx="-1",
        )
        api_method = getattr(self.trade_api, "place_algo_order", None)
        if api_method is None:
            return {"code": "1", "msg": "place_algo_order_not_available", "data": []}
        logging.info("Placing exchange stop %s %s payload=%s", inst_id, position_side, params)
        return api_method(**params)

    def cancel_algo_by_id(self, inst_id: str, algo_id: str) -> dict:
        algo_id = str(algo_id or "").strip()
        if not algo_id:
            return {"code": "0", "msg": "no_algo_id", "data": []}
        return self.trade_api.cancel_algo_order([{"instId": inst_id, "algoId": algo_id}])

    def get_algo_order(self, inst_id: str, algo_id: str) -> Optional[dict]:
        algo_id = str(algo_id or "").strip()
        if not algo_id:
            return None
        for row in self.get_pending_algo_orders(inst_id):
            if str(row.get("algoId") or "").strip() == algo_id:
                return row
        return None

    def close_position(self, inst_id: str, note: str = "", auto_cancel: bool = False) -> dict:
        logging.info("Closing position %s. %s", inst_id, note)
        use_auto_cancel = "true" if auto_cancel or bool(getattr(self.cfg, "auto_cancel_pending_close_orders", True)) else ""
        return self.trade_api.close_positions(instId=inst_id, mgnMode=self.cfg.td_mode, autoCxl=use_auto_cancel)

    def close_position_by_reduce_only(self, inst_id: str, side: str, qty: float) -> dict:
        info = self.instrument_info(inst_id)
        lot_sz = float(info.get("lotSz") or 1.0)
        min_sz = float(info.get("minSz") or lot_sz)
        max_mkt_sz = float(info.get("maxMktSz") or 0.0)
        close_side = "sell" if side == "long" else "buy"
        remaining = max(0.0, float(qty or 0.0))
        filled = 0.0
        responses = []

        for _ in range(32):
            if remaining < min_sz:
                break
            chunk = remaining
            if max_mkt_sz > 0:
                chunk = min(chunk, max_mkt_sz)
            chunk = float(self.format_size(chunk, lot_sz) or 0.0)
            if chunk < min_sz:
                chunk = min_sz if remaining >= min_sz else 0.0
                chunk = float(self.format_size(chunk, lot_sz) or 0.0)
            if chunk <= 0:
                break
            resp = self.place_market_order(inst_id, close_side, chunk, reduce_only=True)
            responses.append(resp)
            if resp.get("code") != "0":
                return {"code": "1", "msg": "reduce_only_close_failed", "data": responses}
            remaining = max(0.0, remaining - chunk)
            filled += chunk
            if remaining < min_sz:
                break

        return {"code": "0", "msg": "reduce_only_close_ok", "filled": filled, "remaining": remaining, "data": responses}

    def format_size(self, qty: float, lot_sz: float) -> str:
        try:
            qty_dec = Decimal(str(qty))
            step_dec = Decimal(str(lot_sz))
            if step_dec <= 0:
                return format(qty_dec.normalize(), "f")
            units = (qty_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
            normalized = (units * step_dec).normalize()
            return format(normalized, "f")
        except (InvalidOperation, ValueError, TypeError):
            return str(qty)

    def place_market_order(self, inst_id: str, side: str, qty: float, reduce_only: bool = False) -> dict:
        info = self.instrument_info(inst_id)
        params = dict(
            instId=inst_id,
            tdMode=self.cfg.td_mode,
            side=side,
            posSide="net",
            ordType="market",
            sz=self.format_size(qty, float(info.get("lotSz") or 1.0)),
        )
        if reduce_only:
            params["reduceOnly"] = "true"
        logging.info("Placing order %s %s qty=%s", inst_id, side, qty)
        return self.trade_api.place_order(**params)
