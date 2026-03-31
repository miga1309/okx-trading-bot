from __future__ import annotations

import csv
import json
import logging
import math
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
}

VERDICT_UNCHECKED = "Не проверено"
VERDICT_TAG_GOOD = "хороший"
VERDICT_TAG_SAW = "пила"
VERDICT_TAG_DEAD = "мертвый"
VERDICT_TAG_RIPPING = "рваный"
VERDICT_TAG_BAD = "плохой"
VERDICT_TAG_SPIKE = "всплеск"
REVIEW_TAGS = [VERDICT_TAG_GOOD, VERDICT_TAG_SAW, VERDICT_TAG_DEAD, VERDICT_TAG_SPIKE, VERDICT_TAG_RIPPING, VERDICT_TAG_BAD]
VERDICT_CONFIRMED = "Теги выбраны"
VERDICT_REJECTED = "Теги выбраны"


def normalize_review_tags(value) -> list[str]:
    tags: list[str] = []
    if isinstance(value, str):
        raw_parts = [part.strip().lower() for part in value.replace(';', ',').split(',')]
        tags = [part for part in raw_parts if part]
    elif isinstance(value, (list, tuple, set)):
        tags = [str(part).strip().lower() for part in value if str(part).strip()]
    normalized: list[str] = []
    seen = set()
    legacy_map = {
        'подтверждено': VERDICT_TAG_GOOD,
        'не подтверждено': VERDICT_TAG_BAD,
    }
    for tag in tags:
        tag = legacy_map.get(tag, tag)
        if tag in REVIEW_TAGS and tag not in seen:
            seen.add(tag)
            normalized.append(tag)
    return normalized


def tags_to_display(value) -> str:
    tags = normalize_review_tags(value)
    return ', '.join(tags) if tags else VERDICT_UNCHECKED


@dataclass
class ScannerStatus:
    inst_id: str
    updated_at: float
    market_structure_class: str = "PENDING"  # DEAD / SAW / RIPPING / PASS / PENDING
    candle_viability_class: str = "PENDING"
    structure_risk_class: str = "PENDING"
    execution_risk_class: str = "PENDING"
    final_risk_class: str = "PENDING"  # ALLOW / BLOCK / FAILED / PENDING
    primary_reason: str = "PENDING"
    reason_codes: str = ""
    execution_risk_score: float = 0.0
    final_market_score: float = 0.0
    execution_confirmed: bool = False
    admitted: bool = False
    pending: bool = True
    failed: bool = False
    error: str = ""
    filter_type: str = "ALLOW"
    summary_text: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


class MarketScannerRuntime:
    def __init__(
        self,
        gateway: Any,
        cfg: Any,
        log_callback=None,
        hard_blocked: Optional[set[str]] = None,
        validation_log_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
    ):
        self.gateway = gateway
        self.cfg = cfg
        self.log = log_callback or (lambda _msg: None)
        self.hard_blocked = {str(x).upper() for x in (hard_blocked or set())}
        self.status_by_symbol: Dict[str, ScannerStatus] = {}
        self._queue: deque[str] = deque()
        self._universe: List[str] = []
        self._last_reset_ts: float = 0.0
        self.validation_log_path = Path(validation_log_path) if validation_log_path else None
        self.state_path = Path(state_path) if state_path else None
        self._review_records: Dict[str, dict] = {}
        self._entry_block_until: Dict[str, float] = {}
        self._load_state()

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
        return not status.pending and not status.failed and status.updated_at > 0.0 and not self.is_status_stale(inst_id)

    def is_status_stale(self, inst_id: str, ttl_sec: Optional[float] = None) -> bool:
        status = self.get_status(inst_id)
        ttl = float(ttl_sec if ttl_sec is not None else getattr(self.cfg, "scanner_status_ttl_sec", 90) or 90)
        if ttl <= 0:
            return False
        updated_at = float(getattr(status, "updated_at", 0.0) or 0.0)
        if updated_at <= 0.0:
            return True
        return (time.time() - updated_at) > ttl

    def status_age_sec(self, inst_id: str) -> float:
        status = self.get_status(inst_id)
        updated_at = float(getattr(status, "updated_at", 0.0) or 0.0)
        if updated_at <= 0.0:
            return 1e12
        return max(0.0, time.time() - updated_at)

    def get_block_remaining_sec(self, inst_id: str) -> float:
        inst_id = str(inst_id).upper()
        until_ts = float(self._entry_block_until.get(inst_id, 0.0) or 0.0)
        return max(0.0, until_ts - time.time())

    def _set_entry_cooldown(self, inst_id: str, seconds: float) -> None:
        inst_id = str(inst_id).upper()
        seconds = max(0.0, float(seconds or 0.0))
        if seconds <= 0.0:
            return
        until_ts = time.time() + seconds
        prev = float(self._entry_block_until.get(inst_id, 0.0) or 0.0)
        if until_ts > prev:
            self._entry_block_until[inst_id] = until_ts

    def refresh_for_entry(self, inst_id: str, force: bool = False) -> ScannerStatus:
        inst_id = str(inst_id).upper()
        if force or self.is_status_stale(inst_id) or not self.is_ready(inst_id):
            return self.refresh_symbol(inst_id)
        return self.get_status(inst_id)

    def allows_entry(self, inst_id: str) -> tuple[bool, str, ScannerStatus]:
        status = self.get_status(inst_id)
        inst_id = str(inst_id).upper()
        if inst_id in self.hard_blocked:
            return False, "blacklist", status
        block_remaining = self.get_block_remaining_sec(inst_id)
        if block_remaining > 0.0:
            return False, f"scanner_cooldown_{int(block_remaining)}s", status
        if status.pending or status.updated_at <= 0.0:
            return False, "scanner_pending", status
        if status.failed:
            return False, "scanner_failed", status
        if self.is_status_stale(inst_id):
            return False, "scanner_stale", status
        if status.admitted:
            return True, "scanner_pass", status
        reason = status.filter_type or status.primary_reason or "scanner_reject"
        return False, f"scanner_{str(reason).lower()}", status

    def refresh_symbol(self, inst_id: str) -> ScannerStatus:
        inst_id = str(inst_id).upper()
        status = self.status_by_symbol.setdefault(inst_id, ScannerStatus(inst_id=inst_id, updated_at=0.0))
        status.pending = True
        status.failed = False
        status.error = ""
        try:
            tf_long = str(getattr(self.cfg, "scanner_long_tf", "15m") or "15m")
            tf_fast = str(getattr(self.cfg, "scanner_fast_tf", "5m") or "5m")
            long_limit = max(40, int(getattr(self.cfg, "scanner_long_candles", 120) or 120))
            fast_limit = max(40, int(getattr(self.cfg, "scanner_fast_candles", 96) or 96))
            long_candles = list(self.gateway.get_candles(inst_id, tf_long, long_limit) or [])
            fast_candles = list(self.gateway.get_candles(inst_id, tf_fast, fast_limit) or [])
            deep_checks_enabled = bool(getattr(self.cfg, "scanner_deep_checks_enabled", False))
            trades = self._collect_trades(inst_id) if deep_checks_enabled else []
            book_rows = self._collect_liquidity(inst_id) if deep_checks_enabled else []
            analysis = self._analyze_symbol(inst_id, long_candles, fast_candles, trades, book_rows)
            filter_type = str(analysis.get("filter_type") or "ALLOW")
            admitted = filter_type == "ALLOW" and inst_id not in self.hard_blocked
            status.market_structure_class = "PASS" if admitted else filter_type
            status.candle_viability_class = "PASS" if admitted else filter_type
            status.structure_risk_class = filter_type
            status.execution_risk_class = filter_type
            status.final_risk_class = "ALLOW" if admitted else "BLOCK"
            status.primary_reason = str(analysis.get("summary_text") or filter_type)
            status.reason_codes = str(analysis.get("reason_codes") or "")
            status.execution_risk_score = float(analysis.get("execution_risk_score") or 0.0)
            status.final_market_score = float(analysis.get("final_market_score") or 0.0)
            status.execution_confirmed = bool(analysis.get("execution_confirmed") or False)
            status.admitted = admitted
            status.pending = False
            status.failed = False
            status.error = ""
            status.updated_at = time.time()
            status.filter_type = filter_type
            status.summary_text = str(analysis.get("summary_text") or "")
            status.metrics = dict(analysis.get("metrics") or {})
            status.raw = dict(analysis)
            if not admitted:
                self._upsert_review_record(status)
                if str(filter_type or '').upper() in {'DEAD', 'RIPPING'}:
                    self._set_entry_cooldown(inst_id, float(getattr(self.cfg, "scanner_bad_market_cooldown_sec", 1800) or 1800))
            self._save_state()
            return status
        except Exception as exc:
            message = str(exc)
            transient_markers = ("ReadError", "timed out", "Timeout", "WinError 10035", "temporarily", "socket")
            if any(marker.lower() in message.lower() for marker in transient_markers):
                logging.error("Scanner refresh temporary failure for %s: %s", inst_id, message)
            else:
                logging.exception("Scanner refresh failed for %s", inst_id)
            status.pending = False
            status.failed = True
            status.error = str(exc)
            status.updated_at = time.time()
            status.filter_type = "FAILED"
            status.final_risk_class = "FAILED"
            status.raw = {}
            self._set_entry_cooldown(inst_id, float(getattr(self.cfg, "scanner_failed_refresh_cooldown_sec", 120) or 120))
            return status

    def summary(self) -> Dict[str, int | str]:
        total = len(self._universe)
        scanned = pending = failed = allowed = blocked = dead = saw = ripping = 0
        for inst_id in self._universe:
            status = self.get_status(inst_id)
            if status.pending or status.updated_at <= 0.0:
                pending += 1
                continue
            scanned += 1
            if status.failed:
                failed += 1
                continue
            if status.admitted:
                allowed += 1
            else:
                blocked += 1
                if status.filter_type == "DEAD":
                    dead += 1
                elif status.filter_type == "SAW":
                    saw += 1
                elif status.filter_type == "RIPPING":
                    ripping += 1
        status_text = "idle"
        if pending > 0:
            status_text = "scanning"
        elif scanned > 0:
            status_text = "ready"
        return {
            "scanner_total": total,
            "scanner_scanned": scanned,
            "scanner_ready": scanned,
            "scanner_pending": pending,
            "scanner_failed": failed,
            "scanner_allowed": allowed,
            "scanner_blocked": blocked,
            "scanner_dead": dead,
            "scanner_saw": saw,
            "scanner_ripping": ripping,
            "scanner_status_text": status_text.upper(),
            # legacy compatibility
            "scanner_safe": allowed,
            "scanner_caution": 0,
            "scanner_risky": blocked,
            "scanner_blacklist": dead + ripping,
            "scanner_exec_watch": ripping,
            "scanner_admitted": allowed,
        }

    def review_rows(self, filter_type: str) -> List[dict]:
        ft = str(filter_type or "").upper()
        rows = [dict(v) for v in self._review_records.values() if str(v.get("filter_type") or "").upper() == ft]
        def _sort_key(row: dict):
            verdict = tags_to_display(row.get("review_tags") or row.get("user_verdict") or VERDICT_UNCHECKED)
            pr = 0 if verdict == VERDICT_UNCHECKED else 1 if row.get("recheck_needed") else 3
            return (pr, -int(row.get("hit_count") or 0), -(float(row.get("last_seen_ts") or 0.0)))
        rows.sort(key=_sort_key)
        return rows

    def update_validation(self, inst_id: str, filter_type: str, verdict: str, comment: str = "", tags=None) -> None:
        key = self._record_key(inst_id, filter_type)
        record = self._review_records.get(key)
        if not record:
            status = self.get_status(inst_id)
            self._upsert_review_record(status)
            record = self._review_records.get(key)
        if not record:
            return
        normalized_tags = normalize_review_tags(tags if tags is not None else verdict)
        record["review_tags"] = normalized_tags
        record["user_verdict"] = tags_to_display(normalized_tags)
        record["comment"] = str(comment or "")
        record["verdict_time"] = time.time()
        record["recheck_needed"] = False
        self._append_validation_log(record)
        self._save_state()

    def build_popup_payload(self, inst_id: str, filter_type: str) -> dict:
        status = self.get_status(inst_id)
        tf_popup = str(getattr(self.cfg, "scanner_popup_tf", "15m") or "15m")
        candles = []
        try:
            candles = list(self.gateway.get_candles(inst_id, tf_popup, int(getattr(self.cfg, "scanner_popup_candles", 80) or 80)) or [])
        except Exception:
            candles = list(((status.raw or {}).get("popup_candles") or []))
        metrics = dict(status.metrics or {})
        summary = [
            f"Фильтр: {status.filter_type}",
            f"Причина: {status.summary_text or status.primary_reason}",
        ]
        for key in sorted(metrics.keys()):
            try:
                val = metrics[key]
                summary.append(f"{key}: {val:.4f}" if isinstance(val, (int, float)) else f"{key}: {val}")
            except Exception:
                summary.append(f"{key}: {metrics[key]}")
        review = self._review_records.get(self._record_key(inst_id, filter_type), {})
        return {
            "inst_id": inst_id,
            "timeframe": tf_popup,
            "side": "long",
            "entry_period": 20,
            "candles": candles,
            "scanner_filter_type": status.filter_type,
            "scanner_reason": status.summary_text or status.primary_reason,
            "scanner_metrics": metrics,
            "scanner_notes": "\n".join(summary),
            "scanner_user_verdict": review.get("user_verdict", VERDICT_UNCHECKED),
            "scanner_review_tags": list(review.get("review_tags") or []),
            "scanner_user_comment": review.get("comment", ""),
            "chart_mode": "scanner",
        }

    def export_validation_rows(self) -> List[dict]:
        rows = []
        for record in self._review_records.values():
            item = dict(record)
            item["metrics_json"] = json.dumps(item.get("metrics") or {}, ensure_ascii=False)
            rows.append(item)
        rows.sort(key=lambda x: (str(x.get("filter_type") or ""), str(x.get("pair") or "")))
        return rows

    def _analyze_symbol(self, inst_id: str, long_candles: List[List[float]], fast_candles: List[List[float]], trades: List[dict], book_rows: List[dict]) -> Dict[str, Any]:
        dead = self._compute_dead_metrics(long_candles, fast_candles, trades, book_rows)
        saw = self._compute_saw_metrics(long_candles, fast_candles)
        ripping = self._compute_ripping_metrics(fast_candles, trades, book_rows)
        dead_votes = sum(1 for x in (dead["candle_dead"], dead["trade_dead"], dead["book_dead"]) if x)
        ripping_votes = sum(1 for x in (ripping["candle_ripping"], ripping["flow_ripping"], ripping["book_ripping"]) if x)
        saw_flag = saw["saw_core"] and saw["saw_confirm"]
        dead_flag = bool(dead["candle_dead"] and (dead["trade_dead"] or dead["book_dead"]))
        ripping_flag = bool(ripping["candle_ripping"] and (ripping["book_ripping"] or ripping["flow_ripping"]))
        if dead_flag:
            filter_type = "DEAD"
            summary = dead["summary_text"]
            metrics = dead["metrics"]
            reason_codes = "dead_votes"
            final_score = float(dead_votes)
        elif saw_flag:
            filter_type = "SAW"
            summary = saw["summary_text"]
            metrics = saw["metrics"]
            reason_codes = "saw_core"
            final_score = 2.0
        elif ripping_flag:
            filter_type = "RIPPING"
            summary = ripping["summary_text"]
            metrics = ripping["metrics"]
            reason_codes = "ripping_votes"
            final_score = float(ripping_votes)
        else:
            filter_type = "ALLOW"
            summary = "scanner_allow"
            metrics = {}
            reason_codes = "allow"
            final_score = 0.0
        return {
            "inst_id": inst_id,
            "filter_type": filter_type,
            "summary_text": summary,
            "reason_codes": reason_codes,
            "final_market_score": final_score,
            "execution_risk_score": float(ripping.get("risk_score") or 0.0),
            "execution_confirmed": bool(filter_type == "ALLOW"),
            "metrics": metrics,
            "dead": dead,
            "saw": saw,
            "ripping": ripping,
            "popup_candles": fast_candles[-80:] if fast_candles else long_candles[-80:],
        }

    def _compute_dead_metrics(self, long_candles, fast_candles, trades, book_rows):
        candles = list(long_candles or fast_candles or [])
        ranges = [max(0.0, float(c[2]) - float(c[3])) for c in candles if len(c) >= 5]
        closes = [float(c[4]) for c in candles if len(c) >= 5]
        median_range = self._median(ranges)
        atr_ratio = (statistics.fmean(ranges[-20:]) / closes[-1]) if ranges and closes and closes[-1] else 0.0
        active_ratio = self._active_ratio(ranges, median_range)
        spike_ratio = (max(ranges) / median_range) if ranges and median_range > 0 else 0.0
        follow_through = self._follow_through(candles)
        trade_count = len(trades)
        trade_count_per_min = trade_count / max(1.0, float(getattr(self.cfg, 'scanner_trade_window_minutes', 15) or 15))
        trade_gaps = self._trade_gaps_seconds(trades)
        intertrade_gap_p95 = self._percentile(trade_gaps, 95)
        zero_trade_ratio = self._zero_trade_ratio(trades)
        spreads = [float(r.get('spread_bps') or 0.0) for r in book_rows if r.get('spread_bps') is not None]
        depths = [float(r.get('depth_sum') or 0.0) for r in book_rows if r.get('depth_sum') is not None]
        spread_bps = statistics.fmean(spreads) if spreads else 0.0
        top_depth = statistics.fmean(depths) if depths else 0.0
        candle_dead = atr_ratio <= float(getattr(self.cfg, 'scanner_dead_atr_ratio_max', 0.0015) or 0.0015) and active_ratio <= float(getattr(self.cfg, 'scanner_dead_active_ratio_max', 0.20) or 0.20)
        trade_dead = zero_trade_ratio >= float(getattr(self.cfg, 'scanner_dead_zero_trade_ratio_min', 0.70) or 0.70) or intertrade_gap_p95 >= float(getattr(self.cfg, 'scanner_dead_gap_p95_min_sec', 1800.0) or 1800.0)
        book_dead = spread_bps >= float(getattr(self.cfg, 'scanner_dead_spread_bps_min', 50.0) or 50.0) or top_depth <= float(getattr(self.cfg, 'scanner_dead_depth_usdt_max', 500.0) or 500.0)
        summary = f"dead_core={int(candle_dead)} trade={int(trade_dead)} book={int(book_dead)}"
        return {
            'candle_dead': candle_dead,
            'trade_dead': trade_dead,
            'book_dead': book_dead,
            'summary_text': summary,
            'metrics': {
                'atr_ratio': atr_ratio,
                'active_ratio': active_ratio,
                'spike_ratio': spike_ratio,
                'follow_through': follow_through,
                'trade_count_per_min': trade_count_per_min,
                'zero_trade_ratio': zero_trade_ratio,
                'intertrade_gap_p95': intertrade_gap_p95,
                'spread_bps': spread_bps,
                'top_depth_usdt': top_depth,
            },
        }

    def _compute_saw_metrics(self, long_candles, fast_candles):
        candles = list(long_candles or fast_candles or [])
        if len(candles) < 25:
            return {'saw_core': False, 'saw_confirm': False, 'summary_text': 'not_enough_candles', 'metrics': {}}
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]
        flip_rate = self._flip_rate(closes)
        er = self._efficiency_ratio(closes, int(getattr(self.cfg, 'scanner_saw_er_window', 20) or 20))
        adx = self._approx_adx(highs, lows, closes, int(getattr(self.cfg, 'scanner_saw_adx_period', 14) or 14))
        false_breakout_rate = self._false_breakout_rate(candles)
        center_reversion_ratio = self._center_reversion_ratio(candles)
        return_autocorr = self._lag1_autocorr(self._returns(closes))
        saw_core = adx < float(getattr(self.cfg, 'scanner_saw_adx_max', 20.0) or 20.0) and flip_rate > float(getattr(self.cfg, 'scanner_saw_flip_rate_min', 0.5) or 0.5) and er < float(getattr(self.cfg, 'scanner_saw_efficiency_max', 0.3) or 0.3) and false_breakout_rate > float(getattr(self.cfg, 'scanner_saw_false_breakout_min', 0.5) or 0.5)
        saw_confirm = center_reversion_ratio > float(getattr(self.cfg, 'scanner_saw_center_reversion_min', 0.55) or 0.55) or return_autocorr < float(getattr(self.cfg, 'scanner_saw_autocorr_max', -0.05) or -0.05)
        return {
            'saw_core': saw_core,
            'saw_confirm': saw_confirm,
            'summary_text': f"saw_core={int(saw_core)} confirm={int(saw_confirm)}",
            'metrics': {
                'adx': adx,
                'flip_rate': flip_rate,
                'efficiency_ratio': er,
                'false_breakout_rate': false_breakout_rate,
                'center_reversion_ratio': center_reversion_ratio,
                'return_autocorr_lag1': return_autocorr,
            },
        }

    def _compute_ripping_metrics(self, fast_candles, trades, book_rows):
        candles = list(fast_candles or [])
        ranges = [max(0.0, float(c[2]) - float(c[3])) for c in candles if len(c) >= 5]
        closes = [float(c[4]) for c in candles if len(c) >= 5]
        median_range = self._median(ranges)
        mean_range = statistics.fmean(ranges) if ranges else 0.0
        atr_ratio = (statistics.fmean(ranges[-20:]) / closes[-1]) if ranges and closes and closes[-1] else 0.0
        range_cv = (statistics.pstdev(ranges) / mean_range) if len(ranges) > 1 and mean_range > 0 else 0.0
        jump_ratio = (max(ranges) / median_range) if ranges and median_range > 0 else 0.0
        return_kurtosis = self._kurtosis(self._returns(closes))
        candle_ripping = range_cv >= float(getattr(self.cfg, 'scanner_ripping_range_cv_min', 1.5) or 1.5) or jump_ratio >= float(getattr(self.cfg, 'scanner_ripping_jump_ratio_min', 15.0) or 15.0) or return_kurtosis >= 20.0
        trade_gaps = self._trade_gaps_seconds(trades)
        intertrade_gap_p95 = self._percentile(trade_gaps, 95)
        sizes = [float(t.get('size') or 0.0) for t in trades if float(t.get('size') or 0.0) > 0]
        trade_size_cv = (statistics.pstdev(sizes) / statistics.fmean(sizes)) if len(sizes) > 1 and statistics.fmean(sizes) > 0 else 0.0
        burst_trade_ratio = self._burst_trade_ratio(trades)
        flow_ripping = trade_size_cv >= float(getattr(self.cfg, 'scanner_ripping_trade_size_cv_min', 3.0) or 3.0) or burst_trade_ratio >= float(getattr(self.cfg, 'scanner_ripping_burst_trade_ratio_min', 0.65) or 0.65)
        spreads = [float(r.get('spread_bps') or 0.0) for r in book_rows if r.get('spread_bps') is not None]
        depths = [float(r.get('depth_sum') or 0.0) for r in book_rows if r.get('depth_sum') is not None]
        spread_bps = statistics.fmean(spreads) if spreads else 0.0
        spread_ready = len(spreads) > 1 and any(x > 0 for x in spreads)
        depth_ready = len(depths) > 1 and any(x > 0 for x in depths)
        spread_cv = (statistics.pstdev(spreads) / spread_bps) if spread_ready and spread_bps > 0 else 0.0
        depth_mean = statistics.fmean(depths) if depths else 0.0
        depth_cv = (statistics.pstdev(depths) / depth_mean) if depth_ready and depth_mean > 0 else 0.0
        top_depth = depth_mean if depths else 0.0
        book_ripping = (spread_ready and spread_cv >= float(getattr(self.cfg, 'scanner_ripping_spread_cv_min', 0.10) or 0.10)) or (depth_ready and depth_cv >= float(getattr(self.cfg, 'scanner_ripping_depth_cv_min', 0.20) or 0.20)) or top_depth <= float(getattr(self.cfg, 'scanner_ripping_depth_usdt_max', 2000.0) or 2000.0)
        risk_score = float(candle_ripping) + float(flow_ripping) + float(book_ripping)
        return {
            'candle_ripping': candle_ripping,
            'flow_ripping': flow_ripping,
            'book_ripping': book_ripping,
            'risk_score': risk_score,
            'summary_text': f"ripping_votes candle={int(candle_ripping)} flow={int(flow_ripping)} book={int(book_ripping)}",
            'metrics': {
                'atr_ratio': atr_ratio,
                'range_cv': range_cv,
                'jump_ratio': jump_ratio,
                'return_kurtosis': return_kurtosis,
                'intertrade_gap_p95': intertrade_gap_p95,
                'trade_size_cv': trade_size_cv,
                'burst_trade_ratio': burst_trade_ratio,
                'spread_bps': spread_bps,
                'spread_cv': spread_cv,
                'top_depth_usdt': top_depth,
                'depth_cv': depth_cv,
                'book_data_ready': 1.0 if (spread_ready or depth_ready) else 0.0,
            },
        }

    def _collect_trades(self, inst_id: str) -> List[dict]:
        rows: List[dict] = []
        api = getattr(self.gateway, 'market_api', None)
        if api is None:
            return rows
        limit = max(20, int(getattr(self.cfg, 'scanner_trade_limit', 100) or 100))
        resp = None
        for method_name in ('get_history_trades', 'get_trades'):
            method = getattr(api, method_name, None)
            if callable(method):
                try:
                    resp = method(instId=inst_id, limit=str(limit))
                    break
                except Exception:
                    continue
        data = list((resp or {}).get('data', []) or [])
        for item in data:
            try:
                rows.append({
                    'ts': int(item.get('ts') or item.get('tradeTime') or 0),
                    'price': float(item.get('px') or item.get('price') or 0.0),
                    'size': float(item.get('sz') or item.get('size') or 0.0),
                    'side': str(item.get('side') or ''),
                })
            except Exception:
                continue
        rows.sort(key=lambda x: x['ts'])
        return rows

    def _collect_liquidity(self, inst_id: str) -> List[Dict[str, Any]]:
        snapshots = max(1, int(getattr(self.cfg, 'scanner_orderbook_snapshots', 4) or 4))
        pause_sec = max(0.0, float(getattr(self.cfg, 'scanner_orderbook_pause_sec', 0.2) or 0.0))
        depth_size = max(1, int(getattr(self.cfg, 'scanner_orderbook_depth', 5) or 5))
        rows: List[Dict[str, Any]] = []
        api = getattr(self.gateway, 'market_api', None)
        for snap_no in range(1, snapshots + 1):
            try:
                resp = api.get_orderbook(instId=inst_id, sz=str(depth_size)) if api is not None else {}
                book_rows = list(resp.get('data', []) or [])
                book = book_rows[0] if book_rows else {}
                bids = list(book.get('bids', []) or [])
                asks = list(book.get('asks', []) or [])
                if bids and asks:
                    best_bid = float(bids[0][0]); best_ask = float(asks[0][0])
                    mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
                    spread_bps = ((best_ask - best_bid) / mid) * 10000.0 if mid else 0.0
                    bid_notional = sum(float(x[0]) * float(x[1]) for x in bids[:depth_size])
                    ask_notional = sum(float(x[0]) * float(x[1]) for x in asks[:depth_size])
                    rows.append({
                        'symbol': inst_id,
                        'snapshot_no': snap_no,
                        'ts': book.get('ts'),
                        'spread_bps': spread_bps,
                        'depth_sum': bid_notional + ask_notional,
                        'top5_bid_size_sum': bid_notional,
                        'top5_ask_size_sum': ask_notional,
                    })
                else:
                    rows.append({'symbol': inst_id, 'snapshot_no': snap_no, 'ts': None, 'spread_bps': None, 'depth_sum': 0.0})
            except Exception:
                rows.append({'symbol': inst_id, 'snapshot_no': snap_no, 'ts': None, 'spread_bps': None, 'depth_sum': 0.0})
            if snap_no < snapshots and pause_sec > 0:
                time.sleep(pause_sec)
        return rows

    def _upsert_review_record(self, status: ScannerStatus) -> None:
        if status.filter_type not in {'DEAD', 'SAW', 'RIPPING'}:
            return
        key = self._record_key(status.inst_id, status.filter_type)
        now_ts = time.time()
        record = self._review_records.get(key)
        metrics = dict(status.metrics or {})
        if record is None:
            record = {
                'key': key,
                'pair': status.inst_id,
                'filter_type': status.filter_type,
                'first_seen_ts': now_ts,
                'last_seen_ts': now_ts,
                'first_seen': self._fmt_ts(now_ts),
                'last_seen': self._fmt_ts(now_ts),
                'hit_count': 1,
                'reason': status.summary_text or status.primary_reason,
                'user_verdict': VERDICT_UNCHECKED,
                'review_tags': [],
                'comment': '',
                'verdict_time': 0.0,
                'recheck_needed': False,
                'active': True,
                'metrics': metrics,
            }
            self._review_records[key] = record
        else:
            record['last_seen_ts'] = now_ts
            record['last_seen'] = self._fmt_ts(now_ts)
            record['hit_count'] = int(record.get('hit_count') or 0) + 1
            record['reason'] = status.summary_text or status.primary_reason
            record['metrics'] = metrics
            record['active'] = True
            if now_ts - float(record.get('verdict_time') or 0.0) > float(getattr(self.cfg, 'scanner_recheck_after_sec', 86400) or 86400):
                if str(record.get('user_verdict') or VERDICT_UNCHECKED) != VERDICT_UNCHECKED:
                    record['recheck_needed'] = True


    def upsert_good_positions(self, positions: List[dict]) -> None:
        active_pairs = set()
        now_ts = time.time()
        for row in positions or []:
            inst_id = str(row.get('inst_id') or '').upper().strip()
            if not inst_id:
                continue
            active_pairs.add(inst_id)
            key = self._record_key(inst_id, 'GOOD')
            metrics = {
                'pnl_pct': float(row.get('pnl_pct', 0.0) or 0.0),
                'unrealized_pnl': float(row.get('unrealized_pnl', 0.0) or 0.0),
                'units': float(row.get('units', row.get('unit_count', 0.0)) or 0.0),
                'entry_price': float(row.get('entry_price', row.get('avg_price', 0.0)) or 0.0),
            }
            record = self._review_records.get(key)
            if record is None:
                record = {
                    'key': key, 'pair': inst_id, 'filter_type': 'GOOD', 'first_seen_ts': now_ts, 'last_seen_ts': now_ts,
                    'first_seen': self._fmt_ts(now_ts), 'last_seen': self._fmt_ts(now_ts), 'hit_count': 1,
                    'reason': 'Открытая позиция программы', 'user_verdict': VERDICT_UNCHECKED, 'review_tags': [], 'comment': '', 'verdict_time': 0.0,
                    'recheck_needed': False, 'active': True, 'metrics': metrics, 'side': str(row.get('side') or '').lower(),
                    'timeframe': str(getattr(self.cfg, 'timeframe', '5m') or '5m'), 'popup_candles': [],
                }
                self._review_records[key] = record
            else:
                record['last_seen_ts'] = now_ts
                record['last_seen'] = self._fmt_ts(now_ts)
                record['hit_count'] = int(record.get('hit_count') or 0) + 1
                record['reason'] = 'Открытая позиция программы'
                record['metrics'] = metrics
                record['side'] = str(row.get('side') or record.get('side') or '').lower()
                record['timeframe'] = str(getattr(self.cfg, 'timeframe', record.get('timeframe', '5m')) or '5m')
                record['active'] = True
                if now_ts - float(record.get('verdict_time') or 0.0) > float(getattr(self.cfg, 'scanner_recheck_after_sec', 86400) or 86400):
                    if tags_to_display(record.get('review_tags') or record.get('user_verdict')) != VERDICT_UNCHECKED:
                        record['recheck_needed'] = True
        for key, record in list(self._review_records.items()):
            if str(record.get('filter_type') or '').upper() == 'GOOD' and str(record.get('pair') or '').upper() not in active_pairs:
                record['active'] = False
        self._save_state()

    def _review_side_from_metrics(self, metrics: Dict[str, Any]) -> str:
        side = str(metrics.get('side') or '').lower().strip()
        return side if side in {'long','short'} else 'long'

    def _append_validation_log(self, record: dict) -> None:
        if self.validation_log_path is None:
            return
        self.validation_log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.validation_log_path.exists()
        with self.validation_log_path.open('a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp','pair','filter_type','user_verdict','review_tags','comment','hit_count','reason','side','timeframe','metrics_json'])
            if write_header:
                writer.writeheader()
            writer.writerow({
                'timestamp': self._fmt_ts(time.time()),
                'pair': record.get('pair',''),
                'filter_type': record.get('filter_type',''),
                'user_verdict': record.get('user_verdict', VERDICT_UNCHECKED),
                'review_tags': json.dumps(record.get('review_tags') or [], ensure_ascii=False),
                'comment': record.get('comment',''),
                'hit_count': record.get('hit_count',0),
                'reason': record.get('reason',''),
                'side': record.get('side', ''),
                'timeframe': record.get('timeframe', str(getattr(self.cfg, 'timeframe', '5m') or '5m')),
                'metrics_json': json.dumps(record.get('metrics') or {}, ensure_ascii=False),
            })

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'review_records': list(self._review_records.values())}
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def _load_state(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding='utf-8'))
            for item in list(payload.get('review_records') or []):
                key = str(item.get('key') or self._record_key(item.get('pair'), item.get('filter_type')))
                self._review_records[key] = item
        except Exception:
            logging.exception('Failed to load scanner state')

    def _record_key(self, inst_id: object, filter_type: object) -> str:
        return f"{str(inst_id or '').upper()}::{str(filter_type or '').upper()}"

    def _fmt_ts(self, ts: float) -> str:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))

    def _median(self, seq: List[float]) -> float:
        clean = [float(x) for x in seq if x is not None]
        return statistics.median(clean) if clean else 0.0

    def _active_ratio(self, ranges: List[float], median_range: float) -> float:
        if not ranges:
            return 0.0
        threshold = max(median_range * 0.5, 1e-12)
        return sum(1 for r in ranges if r > threshold) / len(ranges)

    def _follow_through(self, candles: List[List[float]]) -> float:
        if len(candles) < 6:
            return 0.0
        ranges = [max(0.0, float(c[2]) - float(c[3])) for c in candles]
        median_range = self._median(ranges)
        if median_range <= 0:
            return 0.0
        best_idx = max(range(len(ranges)), key=lambda i: ranges[i])
        if best_idx >= len(candles) - 3:
            return 0.0
        start_close = float(candles[best_idx][4])
        future_close = float(candles[min(len(candles)-1, best_idx+3)][4])
        return abs(future_close - start_close) / median_range

    def _trade_gaps_seconds(self, trades: List[dict]) -> List[float]:
        if len(trades) < 2:
            return [9999.0] if trades else [99999.0]
        gaps = []
        prev = int(trades[0].get('ts') or 0)
        for item in trades[1:]:
            cur = int(item.get('ts') or 0)
            if cur > prev > 0:
                gaps.append((cur - prev) / 1000.0)
            prev = cur
        return gaps or [9999.0]

    def _percentile(self, seq: List[float], pct: float) -> float:
        clean = sorted(float(x) for x in seq if x is not None)
        if not clean:
            return 0.0
        idx = min(len(clean)-1, max(0, int(math.ceil((pct/100.0) * len(clean))) - 1))
        return clean[idx]

    def _zero_trade_ratio(self, trades: List[dict]) -> float:
        gaps = self._trade_gaps_seconds(trades)
        if not gaps:
            return 1.0
        large = sum(1 for g in gaps if g >= 30.0)
        return large / len(gaps)

    def _flip_rate(self, closes: List[float]) -> float:
        if len(closes) < 3:
            return 0.0
        signs = []
        for prev, cur in zip(closes[:-1], closes[1:]):
            diff = cur - prev
            signs.append(1 if diff > 0 else -1 if diff < 0 else 0)
        flips = 0
        valid = 0
        for a, b in zip(signs[:-1], signs[1:]):
            if a == 0 or b == 0:
                continue
            valid += 1
            if a != b:
                flips += 1
        return flips / valid if valid else 0.0

    def _efficiency_ratio(self, closes: List[float], window: int) -> float:
        if len(closes) < window + 1:
            return 1.0
        sample = closes[-(window+1):]
        net = abs(sample[-1] - sample[0])
        total = sum(abs(b - a) for a, b in zip(sample[:-1], sample[1:]))
        return net / total if total > 0 else 1.0

    def _approx_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        if len(closes) < period + 2:
            return 0.0
        trs = []
        plus_dm = []
        minus_dm = []
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            plus = high_diff if high_diff > low_diff and high_diff > 0 else 0.0
            minus = low_diff if low_diff > high_diff and low_diff > 0 else 0.0
            tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
            trs.append(tr)
            plus_dm.append(plus)
            minus_dm.append(minus)
        if len(trs) < period:
            return 0.0
        atr = statistics.fmean(trs[-period:]) or 1e-12
        plus_di = (statistics.fmean(plus_dm[-period:]) / atr) * 100.0
        minus_di = (statistics.fmean(minus_dm[-period:]) / atr) * 100.0
        denom = plus_di + minus_di
        dx = abs(plus_di - minus_di) / denom * 100.0 if denom > 0 else 0.0
        return dx

    def _false_breakout_rate(self, candles: List[List[float]], lookback: int = 20) -> float:
        if len(candles) < lookback + 3:
            return 0.0
        count = fail = 0
        for idx in range(lookback, len(candles) - 1):
            window = candles[idx-lookback:idx]
            upper = max(float(c[2]) for c in window)
            lower = min(float(c[3]) for c in window)
            close_now = float(candles[idx][4])
            close_next = float(candles[idx+1][4])
            if close_now > upper:
                count += 1
                if close_next <= upper:
                    fail += 1
            elif close_now < lower:
                count += 1
                if close_next >= lower:
                    fail += 1
        return fail / count if count else 0.0

    def _center_reversion_ratio(self, candles: List[List[float]], window: int = 20) -> float:
        if len(candles) < window:
            return 0.0
        hits = total = 0
        for idx in range(window, len(candles)):
            sample = candles[idx-window:idx]
            upper = max(float(c[2]) for c in sample)
            lower = min(float(c[3]) for c in sample)
            if upper <= lower:
                continue
            mid_low = lower + (upper-lower)*0.25
            mid_high = upper - (upper-lower)*0.25
            close_val = float(candles[idx][4])
            total += 1
            if mid_low <= close_val <= mid_high:
                hits += 1
        return hits / total if total else 0.0

    def _returns(self, closes: List[float]) -> List[float]:
        out = []
        for a, b in zip(closes[:-1], closes[1:]):
            if a:
                out.append((b - a) / a)
        return out

    def _lag1_autocorr(self, returns: List[float]) -> float:
        if len(returns) < 3:
            return 0.0
        x = returns[:-1]
        y = returns[1:]
        mx = statistics.fmean(x); my = statistics.fmean(y)
        num = sum((a-mx)*(b-my) for a,b in zip(x,y))
        denx = sum((a-mx)**2 for a in x)
        deny = sum((b-my)**2 for b in y)
        den = math.sqrt(denx*deny)
        return num/den if den > 0 else 0.0

    def _kurtosis(self, values: List[float]) -> float:
        if len(values) < 4:
            return 0.0
        mean = statistics.fmean(values)
        var = statistics.pvariance(values)
        if var <= 0:
            return 0.0
        m4 = statistics.fmean([(v-mean)**4 for v in values])
        return m4 / (var**2)

    def _burst_trade_ratio(self, trades: List[dict]) -> float:
        gaps = self._trade_gaps_seconds(trades)
        if not gaps:
            return 0.0
        bursts = sum(1 for g in gaps if g <= 2.0)
        return bursts / len(gaps)
