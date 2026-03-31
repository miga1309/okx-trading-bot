from __future__ import annotations

import threading
import time
from collections import deque
from typing import Dict, List, Optional, Callable

class MarketDataCache:
    def __init__(self, gateway, cfg, log_callback=None, hidden_checker: Optional[Callable[[object], bool]] = None):
        self.hidden_checker = hidden_checker or (lambda _inst_id: False)
        self.gateway = gateway
        self.cfg = cfg
        self.log_callback = log_callback
        self.lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.ticker_cache: Dict[str, dict] = {}
        self.ticker_ts: Dict[str, float] = {}
        self.candles_cache: Dict[tuple[str, str], List[List[float]]] = {}
        self.candles_ts: Dict[tuple[str, str], float] = {}
        self.ticker_history: Dict[str, deque] = {}
        self.error_count = 0
        self.last_error = ""
        self.last_cycle_at: Optional[float] = None
        self.last_log_at = 0.0
        self.fetch_count = 0

    def _log(self, message: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(message)
            except Exception:
                pass

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="MarketDataCache", daemon=True)
        self.thread.start()
        self._log("Асинхронный market-data worker запущен")

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.thread = None

    def _needed_candles_limit(self) -> int:
        base = max(
            int(getattr(self.cfg, "long_entry_period", 55) or 55),
            int(getattr(self.cfg, "short_entry_period", 20) or 20),
            int(getattr(self.cfg, "long_exit_period", 20) or 20),
            int(getattr(self.cfg, "short_exit_period", 10) or 10),
            int(getattr(self.cfg, "atr_period", 20) or 20),
            int(getattr(self.cfg, "flat_lookback_candles", 32) or 32),
            80,
        )
        return base + 8

    def _prioritized_instruments(self) -> List[str]:
        swap_ids = list(getattr(self.gateway, "swap_ids", []) or [])
        engine = getattr(self.gateway, "engine_ref", None)
        open_ids: List[str] = []
        blocked: set[str] = set()
        if engine is not None:
            try:
                open_ids = list(getattr(engine, "position_state", {}).keys())
                blocked = set(getattr(engine, "blocked_instruments", {}).keys())
            except Exception:
                open_ids = []
                blocked = set()
        seen = set()
        ordered: List[str] = []
        for inst_id in open_ids + swap_ids:
            if not inst_id or inst_id in seen or inst_id in blocked or self.hidden_checker(inst_id):
                continue
            if inst_id in getattr(self.cfg, "blacklist", []):
                continue
            seen.add(inst_id)
            ordered.append(inst_id)
        return ordered

    def _run(self) -> None:
        while self.running:
            ordered = self._prioritized_instruments()
            limit = self._needed_candles_limit()
            bar = self.cfg.timeframe
            now = time.time()
            ticker_ttl = max(1.0, float(getattr(self.cfg, "market_data_ticker_ttl_sec", getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)) or getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)))
            candle_ttl = max(1.0, float(getattr(self.cfg, "market_data_candle_ttl_sec", getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)) or getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)))
            fetched_this_cycle = 0

            for inst_id in ordered:
                if not self.running:
                    break
                try:
                    ticker_fresh = (now - self.ticker_ts.get(inst_id, 0.0)) < ticker_ttl
                    candles_key = (inst_id, bar)
                    candles_fresh = (now - self.candles_ts.get(candles_key, 0.0)) < candle_ttl
                    if not ticker_fresh:
                        ticker = self.gateway.fetch_ticker_data(inst_id)
                        self.put_ticker(inst_id, ticker)
                        fetched_this_cycle += 1
                    if not candles_fresh:
                        candles = self.gateway.fetch_candles(inst_id, bar, limit)
                        if candles:
                            self.put_candles(inst_id, bar, candles)
                            fetched_this_cycle += 1
                except Exception as exc:
                    self.error_count += 1
                    self.last_error = str(exc)
                time.sleep(max(0.02, float(getattr(self.cfg, "market_data_worker_sleep_sec", 0.12) or 0.12)))

            self.last_cycle_at = time.time()
            self.fetch_count += fetched_this_cycle
            log_every = max(10, int(getattr(self.cfg, "market_data_log_every_sec", 60) or 60))
            if self.last_cycle_at - self.last_log_at >= log_every:
                self.last_log_at = self.last_cycle_at
                self._log(
                    f"Market-data worker: instruments={len(ordered)}, fetched={fetched_this_cycle}, "
                    f"ticker_cache={len(self.ticker_cache)}, candle_cache={len(self.candles_cache)}, errors={self.error_count}"
                )
            if not ordered:
                time.sleep(0.25)

    def put_ticker(self, inst_id: str, ticker: dict) -> None:
        now_ts = time.time()
        snap = dict(ticker)
        bid_px = float(snap.get("bidPx") or 0.0)
        ask_px = float(snap.get("askPx") or 0.0)
        bid_sz = float(snap.get("bidSz") or 0.0)
        ask_sz = float(snap.get("askSz") or 0.0)
        mid = ((bid_px + ask_px) / 2.0) if bid_px > 0 and ask_px > 0 else 0.0
        spread_pct = (((ask_px - bid_px) / max(mid, 1e-12)) * 100.0) if mid > 0 else 0.0
        hist_item = {
            "ts": now_ts,
            "bid_px": bid_px,
            "ask_px": ask_px,
            "bid_sz": bid_sz,
            "ask_sz": ask_sz,
            "mid": mid,
            "spread_pct": spread_pct,
            "best_bid_notional": bid_px * bid_sz,
            "best_ask_notional": ask_px * ask_sz,
            "best_side_notional": min(bid_px * bid_sz, ask_px * ask_sz),
        }
        history_limit = max(6, int(getattr(self.cfg, "liquidity_history_lookback_points", 8) or 8) + 4)
        with self.lock:
            self.ticker_cache[inst_id] = snap
            self.ticker_ts[inst_id] = now_ts
            history = self.ticker_history.get(inst_id)
            if history is None or getattr(history, "maxlen", 0) != history_limit:
                history = deque(list(history or []), maxlen=history_limit)
                self.ticker_history[inst_id] = history
            history.append(hist_item)

    def get_ticker_history(self, inst_id: str, max_points: Optional[int] = None, max_age: Optional[float] = None) -> List[dict]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "liquidity_history_max_age_sec", 40.0) or 40.0)
        with self.lock:
            rows = list(self.ticker_history.get(inst_id, []))
        now_ts = time.time()
        if age_limit > 0:
            rows = [dict(row) for row in rows if (now_ts - float(row.get("ts", 0.0) or 0.0)) <= age_limit]
        else:
            rows = [dict(row) for row in rows]
        if max_points is not None and max_points > 0:
            rows = rows[-max_points:]
        return rows

    def put_candles(self, inst_id: str, bar: str, candles: List[List[float]]) -> None:
        with self.lock:
            self.candles_cache[(inst_id, bar)] = list(candles)
            self.candles_ts[(inst_id, bar)] = time.time()

    def get_ticker(self, inst_id: str, max_age: Optional[float] = None) -> Optional[dict]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "market_data_ticker_ttl_sec", getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)) or getattr(self.cfg, "market_data_cache_ttl_sec", 12.0))
        with self.lock:
            ticker = self.ticker_cache.get(inst_id)
            ts = self.ticker_ts.get(inst_id, 0.0)
            if ticker and (time.time() - ts) <= age_limit:
                return dict(ticker)
        return None

    def get_candles(self, inst_id: str, bar: str, limit: int, max_age: Optional[float] = None) -> Optional[List[List[float]]]:
        age_limit = max_age if max_age is not None else float(getattr(self.cfg, "market_data_candle_ttl_sec", getattr(self.cfg, "market_data_cache_ttl_sec", 12.0)) or getattr(self.cfg, "market_data_cache_ttl_sec", 12.0))
        key = (inst_id, bar)
        with self.lock:
            candles = self.candles_cache.get(key)
            ts = self.candles_ts.get(key, 0.0)
            if candles and len(candles) >= limit and (time.time() - ts) <= age_limit:
                return [list(row) for row in candles[-limit:]]
        return None

    def snapshot_stats(self) -> dict:
        return {
            "running": bool(self.running),
            "ticker_cache_size": len(self.ticker_cache),
            "ticker_history_size": len(self.ticker_history),
            "candles_cache_size": len(self.candles_cache),
            "fetch_count": int(self.fetch_count),
            "error_count": int(self.error_count),
            "last_error": self.last_error,
            "last_cycle_at": self.last_cycle_at,
        }
