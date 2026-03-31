from __future__ import annotations

import logging
import time
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Optional, Callable

from market_data_cache import MarketDataCache

import okx.Account as Account
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import okx.Trade as Trade

from trade_models import BotConfig

class OkxGateway:
    STABLECOIN_BASES = {"USDC", "USDT", "DAI", "FDUSD", "TUSD", "USDE", "USDP", "EURC", "PYUSD", "USDD", "RLUSD"}

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
        self._positions_cache: List[dict] = []
        self._positions_cache_ts: float = 0.0
        self._account_cache: Optional[dict] = None
        self._account_cache_ts: float = 0.0
        self._account_config_cache: Optional[dict] = None
        self._account_config_ts: float = 0.0
        self.position_mode: str = "net_mode"
        self.cache: Optional[MarketDataCache] = None
        self.engine_ref = None
        self.ws_manager = None
        self.refresh_instruments()
        self._refresh_position_mode_from_account_config(force=True)


    def get_account_config(self, force: bool = False) -> dict:
        ttl = 60.0
        if not force and self._account_config_cache is not None and (time.time() - self._account_config_ts) <= ttl:
            return dict(self._account_config_cache)
        getter = getattr(self.account_api, "get_account_config", None)
        if getter is None:
            return dict(self._account_config_cache or {})
        try:
            resp = getter()
            self._account_config_cache = dict(resp or {})
            self._account_config_ts = time.time()
            return dict(self._account_config_cache)
        except Exception as exc:
            logging.warning("Failed to load account config: %s", exc)
            return dict(self._account_config_cache or {})

    def _refresh_position_mode_from_account_config(self, force: bool = False) -> str:
        resp = self.get_account_config(force=force)
        data = list((resp or {}).get("data", []) or [])
        row = dict(data[0]) if data else {}
        pos_mode = str(row.get("posMode") or row.get("pos_mode") or "").strip()
        if pos_mode:
            self.position_mode = pos_mode
        return self.position_mode

    def _resolve_pos_side(self, position_side: str = "", order_side: str = "") -> str:
        mode = str(getattr(self, "position_mode", "net_mode") or "net_mode").lower()
        if mode in {"long_short_mode", "long_short"}:
            if str(position_side).lower() in {"long", "short"}:
                return str(position_side).lower()
            return "long" if str(order_side).lower() == "buy" else "short"
        return "net"

    def _make_client_id(self, prefix: str, inst_id: str) -> str:
        symbol = ''.join(ch for ch in str(inst_id).upper() if ch.isalnum())[-8:] or 'SWAP'
        return f"{prefix[:4]}{symbol}{int(time.time()*1000)%1000000000:09d}"[:32]


    def attach_ws_manager(self, ws_manager) -> None:
        self.ws_manager = ws_manager

    def refresh_instruments(self) -> None:
        resp = self.public_api.get_instruments(instType="SWAP")
        data = resp.get("data", [])
        self.instrument_cache = {x["instId"]: x for x in data if x.get("state") == "live"}
        self.swap_ids = sorted([
            inst_id for inst_id in self.instrument_cache
            if inst_id.endswith("-USDT-SWAP") and not self.hidden_checker(inst_id) and str(inst_id).split('-', 1)[0].upper() not in self.STABLECOIN_BASES
        ])
        logging.info("Loaded %s swap instruments", len(self.swap_ids))

    def get_account_balance(self, force: bool = False) -> dict:
        ttl = max(0.0, float(getattr(self.cfg, "account_snapshot_ttl_sec", 10.0) or 10.0))
        if not force and self._account_cache is not None and (ttl <= 0.0 or (time.time() - self._account_cache_ts) <= ttl):
            return dict(self._account_cache)
        if not force and self.ws_manager is not None:
            snapshot = self.ws_manager.get_account_snapshot(max_age_sec=ttl if ttl > 0 else 10.0)
            if snapshot is not None:
                self._account_cache = {"code": "0", "data": [dict(snapshot)]}
                self._account_cache_ts = time.time()
                return dict(self._account_cache)
        resp = self.account_api.get_account_balance()
        self._account_cache = dict(resp or {})
        self._account_cache_ts = time.time()
        return dict(self._account_cache)

    def get_positions(self, force: bool = False) -> List[dict]:
        ttl = max(0.0, float(getattr(self.cfg, "positions_snapshot_ttl_sec", 4.0) or 4.0))
        if not force and self._positions_cache and (ttl <= 0.0 or (time.time() - self._positions_cache_ts) <= ttl):
            return [dict(item) for item in self._positions_cache]
        if not force and self.ws_manager is not None:
            snapshot = self.ws_manager.get_positions_snapshot(max_age_sec=ttl if ttl > 0 else 6.0)
            if snapshot is not None:
                self._positions_cache = [dict(item) for item in snapshot]
                self._positions_cache_ts = time.time()
                return [dict(item) for item in self._positions_cache]
        resp = self.account_api.get_positions(instType="SWAP")
        data = list(resp.get("data", []) or [])
        self._positions_cache = [dict(item) for item in data]
        self._positions_cache_ts = time.time()
        return [dict(item) for item in self._positions_cache]

    def attach_cache(self, cache: Optional[MarketDataCache]) -> None:
        self.cache = cache

    def fetch_candles(self, inst_id: str, bar: str, limit: int) -> List[List[float]]:
        # Prefer fresh WS candles first, then fall back to REST closed candles.
        if self.ws_manager is not None:
            try:
                snap = self.ws_manager.get_candles_snapshot(inst_id, bar, max(2, int(limit)))
                if snap is not None and len(snap) >= limit:
                    return [list(row) for row in snap[-limit:]]
            except Exception:
                pass
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
        if self.ws_manager is not None:
            try:
                snap = self.ws_manager.get_candles_snapshot(inst_id, bar, max(2, int(limit)))
                if snap is not None and len(snap) >= limit:
                    if self.cache is not None:
                        self.cache.put_candles(inst_id, bar, snap)
                    return [list(row) for row in snap[-limit:]]
            except Exception:
                pass
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
        if self.ws_manager is not None:
            snap = self.ws_manager.get_ticker_snapshot(inst_id)
            if snap is not None:
                if self.cache is not None:
                    self.cache.put_ticker(inst_id, snap)
                return snap
        data = self.fetch_ticker_data(inst_id)
        if self.cache is not None:
            self.cache.put_ticker(inst_id, data)
        return data

    def get_orderbook_snapshot(self, inst_id: str, depth_size: Optional[int] = None) -> dict:
        depth_size = max(1, int(depth_size or getattr(self.cfg, "ws_book_depth_levels", getattr(self.cfg, "scanner_orderbook_depth", 5)) or 5))
        if self.ws_manager is not None:
            try:
                snap = self.ws_manager.get_book_snapshot(inst_id)
                if snap is not None:
                    return dict(snap)
            except Exception:
                pass
        try:
            resp = self.market_api.get_orderbook(instId=inst_id, sz=str(depth_size))
            rows = list(resp.get('data', []) or [])
            return dict(rows[0] or {}) if rows else {}
        except Exception:
            return {}

    def get_orderbook_metrics(self, inst_id: str, depth_size: Optional[int] = None) -> dict:
        depth_size = max(1, int(depth_size or getattr(self.cfg, "ws_book_depth_levels", getattr(self.cfg, "scanner_orderbook_depth", 5)) or 5))
        if self.ws_manager is not None:
            try:
                metrics = self.ws_manager.get_book_metrics(inst_id)
                if metrics is not None:
                    return dict(metrics)
            except Exception:
                pass
        snap = self.get_orderbook_snapshot(inst_id, depth_size=depth_size)
        bids = list(snap.get('bids', []) or [])
        asks = list(snap.get('asks', []) or [])
        if not bids or not asks:
            return {'instId': str(inst_id).upper(), 'source': 'rest', 'spread_bps': None, 'depth_sum': 0.0, 'bid_notional': 0.0, 'ask_notional': 0.0, 'liquidity_hole_ratio': 1.0}
        best_bid = float(bids[0][0]); best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
        spread_bps = ((best_ask - best_bid) / mid) * 10000.0 if mid else 0.0
        bid_notional = sum(float(px) * float(sz) for px, sz, *_ in bids[:depth_size])
        ask_notional = sum(float(px) * float(sz) for px, sz, *_ in asks[:depth_size])
        min_side = min(bid_notional, ask_notional)
        max_side = max(bid_notional, ask_notional, 1e-12)
        return {'instId': str(inst_id).upper(), 'source': 'rest', 'spread_bps': spread_bps, 'depth_sum': bid_notional + ask_notional, 'bid_notional': bid_notional, 'ask_notional': ask_notional, 'liquidity_hole_ratio': min_side / max_side, 'ts': snap.get('ts')}

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
        if self.ws_manager is not None:
            try:
                ws_rows = list(self.ws_manager.get_pending_algo_orders(inst_id) or [])
                if ws_rows:
                    return ws_rows
            except Exception:
                logging.exception("WS algo snapshot failed for %s", inst_id)
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
        close_side = "sell" if position_side == "long" else "buy"
        trigger_text = (f"{float(trigger_px):.12f}").rstrip("0").rstrip(".")
        params = dict(
            instId=inst_id,
            tdMode=self.cfg.td_mode,
            side=close_side,
            posSide=self._resolve_pos_side(position_side=position_side, order_side=close_side),
            ordType="conditional",
            reduceOnly="true",
            closeFraction="1",
            algoClOrdId=self._make_client_id("SL", inst_id),
            slTriggerPx=trigger_text,
            slTriggerPxType="mark",
            slOrdPx="-1",
        )
        api_method = getattr(self.trade_api, "place_algo_order", None)
        if api_method is None:
            return {"code": "1", "msg": "place_algo_order_not_available", "data": []}
        logging.info("Placing exchange stop %s %s payload=%s", inst_id, position_side, params)
        return api_method(**params)


    def amend_exchange_stop(self, inst_id: str, algo_id: str, new_trigger_px: float, trigger_px_type: str = "mark") -> dict:
        algo_id = str(algo_id or "").strip()
        if not algo_id:
            return {"code": "1", "msg": "missing_algo_id", "data": []}
        trigger_text = (f"{float(new_trigger_px):.12f}").rstrip("0").rstrip(".")
        params = [{
            "instId": inst_id,
            "algoId": algo_id,
            "newSlTriggerPx": trigger_text,
            "newSlOrdPx": "-1",
            "newSlTriggerPxType": str(trigger_px_type or "mark"),
        }]
        api_method = getattr(self.trade_api, "amend_algo_order", None)
        if api_method is None:
            return {"code": "1", "msg": "amend_algo_order_not_available", "data": []}
        logging.info("Amending exchange stop %s algo=%s payload=%s", inst_id, algo_id, params)
        try:
            return api_method(params)
        except TypeError:
            return api_method(instId=inst_id, algoId=algo_id, newSlTriggerPx=trigger_text, newSlOrdPx="-1", newSlTriggerPxType=str(trigger_px_type or "mark"))

    def cancel_algo_by_id(self, inst_id: str, algo_id: str) -> dict:
        algo_id = str(algo_id or "").strip()
        if not algo_id:
            return {"code": "0", "msg": "no_algo_id", "data": []}
        return self.trade_api.cancel_algo_order([{"instId": inst_id, "algoId": algo_id}])

    def get_algo_order(self, inst_id: str, algo_id: str) -> Optional[dict]:
        algo_id = str(algo_id or "").strip()
        if not algo_id:
            return None
        if self.ws_manager is not None:
            try:
                row = self.ws_manager.get_algo_order_snapshot(algo_id)
                if row:
                    return row
            except Exception:
                logging.exception("WS algo get failed for %s", inst_id)
        for row in self.get_pending_algo_orders(inst_id):
            if str(row.get("algoId") or row.get("algoClOrdId") or "").strip() == algo_id:
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
            posSide=self._resolve_pos_side(order_side=side),
            ordType="market",
            clOrdId=self._make_client_id("MKT", inst_id),
            sz=self.format_size(qty, float(info.get("lotSz") or 1.0)),
        )
        if reduce_only:
            params["reduceOnly"] = "true"
        logging.info("Placing order %s %s qty=%s", inst_id, side, qty)
        return self.trade_api.place_order(**params)
