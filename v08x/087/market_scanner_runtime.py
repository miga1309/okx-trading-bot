from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from market_scanner_v012.analyzers import analyze_symbol

TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "1D": 86400,
}


@dataclass
class ScannerStatus:
    inst_id: str
    updated_at: float
    market_structure_class: str = "PENDING"
    candle_viability_class: str = "PENDING"
    structure_risk_class: str = "PENDING"
    execution_risk_class: str = "PENDING"
    final_risk_class: str = "PENDING"
    primary_reason: str = "PENDING"
    reason_codes: str = ""
    execution_risk_score: float = 0.0
    final_market_score: float = 0.0
    execution_confirmed: bool = False
    admitted: bool = False
    pending: bool = True
    failed: bool = False
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class MarketScannerRuntime:
    def __init__(
        self,
        gateway: Any,
        cfg: Any,
        log_callback=None,
        hard_blocked: Optional[set[str]] = None,
    ):
        self.gateway = gateway
        self.cfg = cfg
        self.log = log_callback or (lambda _msg: None)
        self.hard_blocked = {str(x).upper() for x in (hard_blocked or set())}
        self.status_by_symbol: Dict[str, ScannerStatus] = {}
        self._queue: deque[str] = deque()
        self._universe: List[str] = []
        self._last_reset_ts: float = 0.0

    def initialize_universe(self, symbols: List[str]) -> None:
        normalized = [str(x).upper() for x in symbols if str(x).strip()]
        if normalized == self._universe:
            return
        self._universe = normalized
        self._queue = deque(normalized)
        known = set(normalized)
        for inst_id in list(self.status_by_symbol.keys()):
            if inst_id not in known:
                self.status_by_symbol.pop(inst_id, None)
        for inst_id in normalized:
            self.status_by_symbol.setdefault(inst_id, ScannerStatus(inst_id=inst_id, updated_at=0.0))
        self._last_reset_ts = time.time()

    def maybe_schedule_full_rescan(self) -> None:
        interval = max(300, int(getattr(self.cfg, "scanner_rescan_interval_sec", 3600) or 3600))
        now_ts = time.time()
        if (now_ts - self._last_reset_ts) < interval:
            return
        self._queue = deque(self._universe)
        self._last_reset_ts = now_ts
        self.log("[SCANNER] hourly rescan scheduled")

    def run_chunk(self, chunk_size: Optional[int] = None) -> int:
        self.maybe_schedule_full_rescan()
        if not self._queue:
            return 0
        quota = max(1, int(chunk_size or getattr(self.cfg, "scanner_chunk_size", 4) or 4))
        processed = 0
        while self._queue and processed < quota:
            inst_id = self._queue.popleft()
            self.refresh_symbol(inst_id)
            processed += 1
        return processed

    def get_status(self, inst_id: str) -> ScannerStatus:
        inst_id = str(inst_id).upper()
        return self.status_by_symbol.setdefault(inst_id, ScannerStatus(inst_id=inst_id, updated_at=0.0))

    def is_ready(self, inst_id: str) -> bool:
        status = self.get_status(inst_id)
        return not status.pending and not status.failed and status.updated_at > 0.0

    def allows_entry(self, inst_id: str) -> tuple[bool, str, ScannerStatus]:
        status = self.get_status(inst_id)
        if str(inst_id).upper() in self.hard_blocked:
            return False, "blacklist", status
        if status.pending or status.updated_at <= 0.0:
            return False, "scanner_pending", status
        if status.failed:
            return False, "scanner_failed", status
        if status.admitted:
            return True, "scanner_pass", status
        reason = status.market_structure_class or status.final_risk_class or status.primary_reason or "scanner_reject"
        return False, f"scanner_{str(reason).lower()}", status

    def refresh_symbol(self, inst_id: str) -> ScannerStatus:
        inst_id = str(inst_id).upper()
        status = self.status_by_symbol.setdefault(inst_id, ScannerStatus(inst_id=inst_id, updated_at=0.0))
        status.pending = True
        status.failed = False
        status.error = ""
        try:
            candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, self._history_limit())
            rows = []
            for row in candles:
                if len(row) < 6:
                    continue
                ts, o, h, l, c, v = row[:6]
                rows.append({
                    "ts": int(ts),
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                    "quote_volume": float(c) * float(v),
                })
            df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "quote_volume"])
            liquidity_rows = self._collect_liquidity(inst_id)
            analysis = analyze_symbol(
                inst_id,
                self.cfg.timeframe,
                df,
                expected_count=self._expected_count(),
                liquidity_rows=liquidity_rows,
                profile=str(getattr(self.cfg, "scanner_profile", "balanced") or "balanced"),
            )
            summary = dict(analysis.summary or {})
            market_structure_class = str(summary.get("market_structure_class") or summary.get("candle_reject_type") or "UNKNOWN")
            final_risk_class = str(summary.get("final_risk_class") or "UNKNOWN")
            candle_viability_class = str(summary.get("candle_viability_class") or "UNKNOWN")
            execution_risk_class = str(summary.get("execution_risk_class") or "UNKNOWN")
            structure_risk_class = str(summary.get("structure_risk_class") or "UNKNOWN")
            admitted = (
                candle_viability_class == "PASS"
                and market_structure_class == "PASS"
                and final_risk_class in {"SAFE", "CAUTION"}
                and execution_risk_class in {"SAFE", "CAUTION"}
                and inst_id not in self.hard_blocked
            )
            status.market_structure_class = market_structure_class
            status.candle_viability_class = candle_viability_class
            status.structure_risk_class = structure_risk_class
            status.execution_risk_class = execution_risk_class
            status.final_risk_class = final_risk_class
            status.primary_reason = str(summary.get("primary_reason") or summary.get("reject_reason_primary") or market_structure_class)
            status.reason_codes = str(summary.get("reason_codes") or "")
            status.execution_risk_score = float(summary.get("execution_risk_score") or 0.0)
            status.final_market_score = float(summary.get("final_market_score") or 0.0)
            status.execution_confirmed = bool(summary.get("execution_confirmed") or summary.get("execution_multi_snapshot_confirmed"))
            status.admitted = admitted
            status.pending = False
            status.failed = False
            status.error = ""
            status.updated_at = time.time()
            status.raw = summary
            return status
        except Exception as exc:
            logging.exception("Scanner refresh failed for %s", inst_id)
            status.pending = False
            status.failed = True
            status.error = str(exc)
            status.updated_at = time.time()
            status.raw = {}
            return status

    def summary(self) -> Dict[str, int]:
        total = len(self._universe)
        ready = pending = failed = safe = caution = risky = blacklist = exec_watch = admitted = 0
        for inst_id in self._universe:
            status = self.get_status(inst_id)
            if status.pending or status.updated_at <= 0.0:
                pending += 1
                continue
            if status.failed:
                failed += 1
                continue
            ready += 1
            if status.final_risk_class == "SAFE":
                safe += 1
            elif status.final_risk_class == "CAUTION":
                caution += 1
            elif status.final_risk_class == "RISKY":
                risky += 1
            else:
                blacklist += 1
            if status.execution_risk_class in {"RISKY", "BLACKLIST_CANDIDATE"}:
                exec_watch += 1
            if status.admitted:
                admitted += 1
        return {
            "scanner_total": total,
            "scanner_ready": ready,
            "scanner_pending": pending,
            "scanner_failed": failed,
            "scanner_safe": safe,
            "scanner_caution": caution,
            "scanner_risky": risky,
            "scanner_blacklist": blacklist,
            "scanner_exec_watch": exec_watch,
            "scanner_admitted": admitted,
        }

    def _history_limit(self) -> int:
        seconds = max(60, TIMEFRAME_TO_SECONDS.get(str(self.cfg.timeframe), 900))
        days = max(1, int(getattr(self.cfg, "scanner_history_days", 1) or 1))
        limit = int((86400 * days) / seconds)
        return max(32, min(limit, 400))

    def _expected_count(self) -> int:
        return self._history_limit()

    def _collect_liquidity(self, inst_id: str) -> List[Dict[str, Any]]:
        snapshots = max(1, int(getattr(self.cfg, "scanner_liquidity_snapshots", 3) or 3))
        pause_sec = max(0.0, float(getattr(self.cfg, "scanner_liquidity_pause_sec", 0.25) or 0.0))
        depth_size = max(1, int(getattr(self.cfg, "scanner_orderbook_depth", 5) or 5))
        rows: List[Dict[str, Any]] = []
        for snap_no in range(1, snapshots + 1):
            try:
                resp = self.gateway.market_api.get_orderbook(instId=inst_id, sz=str(depth_size))
                book_rows = list(resp.get("data", []) or [])
                book = book_rows[0] if book_rows else {}
                bids = list(book.get("bids", []) or [])
                asks = list(book.get("asks", []) or [])
                if not bids or not asks:
                    rows.append({
                        "symbol": inst_id,
                        "snapshot_no": snap_no,
                        "ts": book.get("ts"),
                        "spread_pct": None,
                        "best_bid_size": None,
                        "best_ask_size": None,
                        "top5_bid_size_sum": 0.0,
                        "top5_ask_size_sum": 0.0,
                        "depth_sum": 0.0,
                        "depth_imbalance": None,
                        "mid_price": None,
                    })
                else:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else None
                    spread_pct = ((best_ask - best_bid) / mid) if mid else None
                    bid_sizes = [float(x[1]) for x in bids[:depth_size]]
                    ask_sizes = [float(x[1]) for x in asks[:depth_size]]
                    bid_sum = sum(bid_sizes)
                    ask_sum = sum(ask_sizes)
                    depth_sum = bid_sum + ask_sum
                    imbalance = ((bid_sum - ask_sum) / depth_sum) if depth_sum else None
                    rows.append({
                        "symbol": inst_id,
                        "snapshot_no": snap_no,
                        "ts": book.get("ts"),
                        "spread_pct": spread_pct,
                        "best_bid_size": float(bids[0][1]),
                        "best_ask_size": float(asks[0][1]),
                        "top5_bid_size_sum": bid_sum,
                        "top5_ask_size_sum": ask_sum,
                        "depth_sum": depth_sum,
                        "depth_imbalance": imbalance,
                        "mid_price": mid,
                    })
            except Exception:
                rows.append({
                    "symbol": inst_id,
                    "snapshot_no": snap_no,
                    "ts": None,
                    "spread_pct": None,
                    "best_bid_size": None,
                    "best_ask_size": None,
                    "top5_bid_size_sum": None,
                    "top5_ask_size_sum": None,
                    "depth_sum": None,
                    "depth_imbalance": None,
                    "mid_price": None,
                })
            if snap_no < snapshots and pause_sec > 0:
                time.sleep(pause_sec)
        return rows
