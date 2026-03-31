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
VERDICT_TAG_SPIKE = "всплеск"
VERDICT_TAG_BAD = "плохой"
REVIEW_TAGS = [VERDICT_TAG_GOOD, VERDICT_TAG_SAW, VERDICT_TAG_DEAD, VERDICT_TAG_SPIKE, VERDICT_TAG_BAD]


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
        'рваный': VERDICT_TAG_SPIKE,
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
    market_structure_class: str = "PENDING"  # DEAD / SAW / SPIKE_DEAD / PASS / PENDING
    candle_viability_class: str = "PENDING"
    structure_risk_class: str = "PENDING"
    execution_risk_class: str = "SAFE"
    final_risk_class: str = "PENDING"  # PASS / BLOCK / FAILED / PENDING
    primary_reason: str = "PENDING"
    reason_codes: str = ""
    execution_risk_score: float = 0.0
    final_market_score: float = 0.0
    execution_confirmed: bool = True
    admitted: bool = False
    pending: bool = True
    failed: bool = False
    error: str = ""
    filter_type: str = "PENDING"
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
        normalized: list[str] = []
        for item in symbols:
            inst_id = str(item).upper().strip()
            if not inst_id:
                continue
            if inst_id.split('-', 1)[0].startswith('TEST'):
                continue
            normalized.append(inst_id)
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
        interval = max(300, int(getattr(self.cfg, 'scanner_rescan_interval_sec', 3600) or 3600))
        now_ts = time.time()
        if self._queue:
            return
        if (now_ts - self._last_reset_ts) < interval and self.status_by_symbol:
            return
        self._queue = deque(self._universe)
        self._last_reset_ts = now_ts
        self.log('[SCANNER] hourly rescan scheduled')

    def queue_size(self) -> int:
        return len(self._queue)

    def has_pending_queue(self) -> bool:
        return bool(self._queue)

    def desired_chunk_interval_sec(self) -> float:
        universe = max(1, len(self._universe) or len(self.status_by_symbol) or 1)
        target_cycle = float(getattr(self.cfg, 'scanner_target_cycle_sec', 540) or 540)
        target_cycle = max(180.0, target_cycle)
        chunk_size = max(1, int(getattr(self.cfg, 'scanner_chunk_size', 3) or 3))
        slots = max(1.0, math.ceil(universe / float(chunk_size)))
        return max(5.0, target_cycle / slots)

    def run_chunk(self, chunk_size: Optional[int] = None) -> int:
        self.maybe_schedule_full_rescan()
        if not self._queue:
            return 0
        quota = max(1, int(chunk_size or getattr(self.cfg, 'scanner_chunk_size', 1) or 1))
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
        ttl = float(ttl_sec if ttl_sec is not None else getattr(self.cfg, 'scanner_status_ttl_sec', 3900) or 3900)
        if ttl <= 0:
            return False
        updated_at = float(getattr(status, 'updated_at', 0.0) or 0.0)
        if updated_at <= 0.0:
            return True
        return (time.time() - updated_at) > ttl

    def status_age_sec(self, inst_id: str) -> float:
        status = self.get_status(inst_id)
        updated_at = float(getattr(status, 'updated_at', 0.0) or 0.0)
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
        status = self.get_status(inst_id)
        if force or self.is_status_stale(inst_id) or not self.is_ready(inst_id):
            return self.refresh_symbol(inst_id)
        return status

    def allows_entry(self, inst_id: str) -> tuple[bool, str, ScannerStatus]:
        status = self.get_status(inst_id)
        inst_id = str(inst_id).upper()
        if inst_id in self.hard_blocked:
            return False, 'blacklist', status
        block_remaining = self.get_block_remaining_sec(inst_id)
        if block_remaining > 0.0:
            return False, f'scanner_cooldown_{int(block_remaining)}s', status
        if status.pending or status.updated_at <= 0.0:
            return False, 'scanner_pending', status
        if status.failed:
            return False, 'scanner_failed', status
        if self.is_status_stale(inst_id):
            return False, 'scanner_stale', status
        if status.admitted:
            return True, 'scanner_pass', status
        reason = status.filter_type or status.primary_reason or 'scanner_reject'
        return False, f"scanner_{str(reason).lower()}", status

    def refresh_symbol(self, inst_id: str) -> ScannerStatus:
        inst_id = str(inst_id).upper()
        status = self.status_by_symbol.setdefault(inst_id, ScannerStatus(inst_id=inst_id, updated_at=0.0))
        status.pending = True
        status.failed = False
        status.error = ''
        try:
            timeframe = str(getattr(self.cfg, 'timeframe', '15m') or '15m')
            candle_limit = max(24, int(getattr(self.cfg, 'scanner_window_candles', 24) or 24))
            candles = list(self.gateway.get_candles(inst_id, timeframe, candle_limit) or [])
            analysis = self._analyze_symbol(inst_id, candles)
            filter_type = str(analysis.get('filter_type') or 'PENDING').upper()
            admitted = filter_type == 'PASS' and inst_id not in self.hard_blocked
            status.market_structure_class = filter_type
            status.candle_viability_class = filter_type
            status.structure_risk_class = 'LOW' if admitted else 'HIGH'
            status.execution_risk_class = 'SAFE'
            status.final_risk_class = 'PASS' if admitted else 'BLOCK'
            status.primary_reason = str(analysis.get('primary_reason') or filter_type.lower())
            status.reason_codes = str(analysis.get('reason_codes') or status.primary_reason)
            status.execution_risk_score = 0.0
            status.final_market_score = float(analysis.get('final_market_score') or 0.0)
            status.execution_confirmed = True
            status.admitted = admitted
            status.pending = False
            status.failed = False
            status.filter_type = filter_type
            status.summary_text = str(analysis.get('summary_text') or status.primary_reason)
            status.metrics = dict(analysis.get('metrics') or {})
            status.raw = {
                'candles': list(analysis.get('popup_candles') or candles[-80:]),
                'timeframe': timeframe,
            }
            status.updated_at = time.time()
            cooldown = float(getattr(self.cfg, 'scanner_bad_market_cooldown_sec', 1800) or 1800)
            if filter_type in {'DEAD', 'SPIKE_DEAD', 'SAW'}:
                self._set_entry_cooldown(inst_id, cooldown)
            self._upsert_review_record(status)
            self._save_state()
            self.log(f"[SCANNER] {inst_id}: {filter_type} | {status.summary_text}")
            return status
        except Exception as exc:
            status.pending = False
            status.failed = True
            status.admitted = False
            status.error = str(exc)
            status.filter_type = 'FAILED'
            status.primary_reason = 'scanner_failed'
            status.summary_text = status.error
            status.final_risk_class = 'FAILED'
            status.updated_at = time.time()
            self._set_entry_cooldown(inst_id, float(getattr(self.cfg, 'scanner_failed_refresh_cooldown_sec', 120) or 120))
            logging.exception('Market scanner refresh failed for %s', inst_id)
            return status

    def summary(self) -> Dict[str, Any]:
        total = len(self._universe)
        scanned = 0
        pending = 0
        failed = 0
        allowed = 0
        blocked = 0
        dead = 0
        saw = 0
        spike_dead = 0
        for status in self.status_by_symbol.values():
            if status.pending or status.updated_at <= 0.0:
                pending += 1
                continue
            if status.failed:
                failed += 1
                continue
            scanned += 1
            if status.admitted:
                allowed += 1
            else:
                blocked += 1
            if status.filter_type == 'DEAD':
                dead += 1
            elif status.filter_type == 'SAW':
                saw += 1
            elif status.filter_type == 'SPIKE_DEAD':
                spike_dead += 1
        status_text = 'READY' if not self._queue else f'RUNNING {len(self._queue)} LEFT'
        return {
            'scanner_total': total,
            'scanner_scanned': scanned,
            'scanner_ready': scanned,
            'scanner_pending': pending,
            'scanner_failed': failed,
            'scanner_allowed': allowed,
            'scanner_blocked': blocked,
            'scanner_dead': dead,
            'scanner_saw': saw,
            'scanner_spike_dead': spike_dead,
            'scanner_status_text': status_text.upper(),
            'scanner_safe': allowed,
            'scanner_caution': 0,
            'scanner_risky': blocked,
            'scanner_blacklist': dead + saw + spike_dead,
            'scanner_admitted': allowed,
        }

    def review_rows(self, filter_type: str) -> List[dict]:
        ft = str(filter_type or '').upper()
        rows = [dict(v) for v in self._review_records.values() if str(v.get('filter_type') or '').upper() == ft]
        def _sort_key(row: dict):
            verdict = tags_to_display(row.get('review_tags') or row.get('user_verdict') or VERDICT_UNCHECKED)
            pr = 0 if verdict == VERDICT_UNCHECKED else 1 if row.get('recheck_needed') else 3
            return (pr, -int(row.get('hit_count') or 0), -(float(row.get('last_seen_ts') or 0.0)))
        rows.sort(key=_sort_key)
        return rows

    def update_validation(self, inst_id: str, filter_type: str, verdict: str, comment: str = '', tags=None) -> None:
        inst_id = str(inst_id or '').upper().strip()
        filter_type = str(filter_type or '').upper().strip()
        key = self._record_key(inst_id, filter_type)
        record = self._review_records.get(key)
        if not record:
            status = self.get_status(inst_id)
            self._upsert_review_record(status)
            record = self._review_records.get(key)
        if not record:
            return
        normalized_tags = normalize_review_tags(tags if tags is not None else verdict)
        record['review_tags'] = normalized_tags
        record['user_verdict'] = tags_to_display(normalized_tags)
        record['comment'] = str(comment or '')
        record['verdict_time'] = time.time()
        record['recheck_needed'] = False
        record['last_seen_ts'] = max(float(record.get('last_seen_ts') or 0.0), float(record.get('verdict_time') or 0.0))
        record['last_seen'] = self._fmt_ts(float(record.get('last_seen_ts') or time.time()))
        self._append_validation_log(record)
        self._save_state()

    def build_popup_payload(self, inst_id: str, filter_type: str) -> dict:
        status = self.get_status(inst_id)
        filter_type = str(filter_type or status.filter_type or '').upper()
        timeframe = str((status.raw or {}).get('timeframe') or getattr(self.cfg, 'timeframe', '15m') or '15m')
        popup_limit = max(24, int(getattr(self.cfg, 'scanner_popup_candles', 80) or 80))
        candles = []
        try:
            candles = list(self.gateway.get_candles(inst_id, timeframe, popup_limit) or [])
        except Exception:
            candles = list(((status.raw or {}).get('candles') or []))
        metrics = dict(status.metrics or {})
        summary = [
            f'Фильтр: {status.filter_type}',
            f'Причина: {status.summary_text or status.primary_reason}',
        ]
        for key in sorted(metrics.keys()):
            try:
                val = metrics[key]
                summary.append(f'{key}: {val:.6f}' if isinstance(val, (int, float)) else f'{key}: {val}')
            except Exception:
                summary.append(f'{key}: {metrics[key]}')
        review = self._review_records.get(self._record_key(inst_id, filter_type), {})
        return {
            'inst_id': inst_id,
            'timeframe': timeframe,
            'side': 'long',
            'entry_period': 20,
            'candles': candles,
            'scanner_filter_type': filter_type or status.filter_type,
            'scanner_reason': status.summary_text or status.primary_reason,
            'scanner_metrics': metrics,
            'scanner_notes': '\n'.join(summary),
            'scanner_user_verdict': review.get('user_verdict', VERDICT_UNCHECKED),
            'scanner_review_tags': list(review.get('review_tags') or []),
            'scanner_user_comment': review.get('comment', ''),
            'chart_mode': 'scanner',
        }

    def export_validation_rows(self) -> List[dict]:
        rows = []
        for record in self._review_records.values():
            item = dict(record)
            item['metrics_json'] = json.dumps(item.get('metrics') or {}, ensure_ascii=False)
            rows.append(item)
        rows.sort(key=lambda x: (str(x.get('filter_type') or ''), str(x.get('pair') or '')))
        return rows

    def _analyze_symbol(self, inst_id: str, candles: List[List[float]]) -> Dict[str, Any]:
        window = [list(c) for c in candles if isinstance(c, (list, tuple)) and len(c) >= 5]
        window = window[-max(24, int(getattr(self.cfg, 'scanner_window_candles', 24) or 24)):]
        if len(window) < 24:
            raise RuntimeError(f'not enough candles: {len(window)}/24')
        metrics = self._compute_metrics(window)
        filter_type = 'PASS'
        summary = 'scanner_pass'
        reason_codes = 'pass'
        final_score = 0.0
        if self._is_spike_dead(metrics):
            filter_type = 'SPIKE_DEAD'
            summary = 'dead_background_with_spikes'
            reason_codes = 'spike_dead'
            final_score = 3.0
        elif self._is_dead(metrics):
            filter_type = 'DEAD'
            summary = 'dead_market_low_range_low_volatility'
            reason_codes = 'dead'
            final_score = 2.0
        elif self._is_saw(metrics):
            filter_type = 'SAW'
            summary = 'choppy_market_high_chop_low_er'
            reason_codes = 'saw'
            final_score = 1.0
        elif not self._passes_pass_vitality(metrics):
            filter_type = 'DEAD'
            summary = 'flat_market_failed_pass_vitality'
            reason_codes = 'dead_flat_pass_gate'
            final_score = 2.0
        metrics['window_candles'] = float(len(window))
        return {
            'inst_id': inst_id,
            'filter_type': filter_type,
            'primary_reason': reason_codes,
            'summary_text': summary,
            'reason_codes': reason_codes,
            'final_market_score': final_score,
            'metrics': metrics,
            'popup_candles': window[-80:],
        }

    def _compute_metrics(self, candles: List[List[float]]) -> Dict[str, float]:
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        opens = [float(c[1]) for c in candles]
        closes = [float(c[4]) for c in candles]
        ranges = [max(0.0, hi - lo) for hi, lo in zip(highs, lows)]
        tr_values = []
        prev_close = closes[0]
        for hi, lo, close in zip(highs, lows, closes):
            tr_values.append(max(hi - lo, abs(hi - prev_close), abs(lo - prev_close)))
            prev_close = close
        close_last = closes[-1] if closes[-1] else 1e-12
        window_range = max(highs) - min(lows)
        window_range_pct = window_range / close_last if close_last > 0 else 0.0
        range_pcts = [(r / c) if c else 0.0 for r, c in zip(ranges, closes)]
        body_ratios = []
        dead_count = 0
        micro_body_count = 0
        narrow_range_count = 0
        dir_signs: list[int] = []
        dead_bar_range_pct_max = float(getattr(self.cfg, 'scanner_dead_bar_range_pct_max', 0.0035) or 0.0035)
        dead_body_ratio_max = float(getattr(self.cfg, 'scanner_dead_body_ratio_max', 0.25) or 0.25)
        micro_body_ratio_max = float(getattr(self.cfg, 'scanner_micro_body_ratio_max', 0.18) or 0.18)
        narrow_range_pct_max = float(getattr(self.cfg, 'scanner_narrow_range_pct_max', 0.0055) or 0.0055)
        flat_close_change_pct_max = float(getattr(self.cfg, 'scanner_flat_close_change_pct_max', 0.0015) or 0.0015)
        flat_mid_change_pct_max = float(getattr(self.cfg, 'scanner_flat_mid_change_pct_max', 0.0018) or 0.0018)
        mids = []
        for op, hi, lo, cl, rng in zip(opens, highs, lows, closes, ranges):
            body = abs(cl - op)
            body_ratio = body / rng if rng > 0 else 0.0
            body_ratios.append(body_ratio)
            range_pct = (rng / cl) if cl else 0.0
            mids.append((hi + lo) / 2.0 if (hi > 0 or lo > 0) else cl)
            if range_pct < dead_bar_range_pct_max and body_ratio < dead_body_ratio_max:
                dead_count += 1
            if body_ratio < micro_body_ratio_max:
                micro_body_count += 1
            if range_pct < narrow_range_pct_max:
                narrow_range_count += 1
        flat_close_count = 0
        flat_close_run = 0
        max_flat_close_run = 0
        for prev, cur in zip(closes[:-1], closes[1:]):
            diff = cur - prev
            base = abs(prev) if prev else 1e-12
            is_flat_close = abs(diff) / base <= flat_close_change_pct_max
            if is_flat_close:
                flat_close_count += 1
                flat_close_run += 1
                if flat_close_run > max_flat_close_run:
                    max_flat_close_run = flat_close_run
            else:
                flat_close_run = 0
            dir_signs.append(1 if diff > 0 else -1 if diff < 0 else 0)
        flat_mid_count = 0
        flat_mid_run = 0
        max_flat_mid_run = 0
        for prev_mid, cur_mid in zip(mids[:-1], mids[1:]):
            base = abs(prev_mid) if prev_mid else 1e-12
            is_flat_mid = abs(cur_mid - prev_mid) / base <= flat_mid_change_pct_max
            if is_flat_mid:
                flat_mid_count += 1
                flat_mid_run += 1
                if flat_mid_run > max_flat_mid_run:
                    max_flat_mid_run = flat_mid_run
            else:
                flat_mid_run = 0
        flips = 0
        valid_pairs = 0
        for a, b in zip(dir_signs[:-1], dir_signs[1:]):
            if a == 0 or b == 0:
                continue
            valid_pairs += 1
            if a != b:
                flips += 1
        flip_share = (flips / valid_pairs) if valid_pairs else 0.0
        median_range = self._median(ranges)
        spike_multiplier = float(getattr(self.cfg, 'scanner_spike_multiplier', 2.5) or 2.5)
        spike_count = sum(1 for rng in ranges if median_range > 0 and rng > spike_multiplier * median_range)
        spike_share = spike_count / len(ranges) if ranges else 0.0
        er = self._efficiency_ratio(closes)
        chop = self._choppiness(tr_values, window_range, len(candles))
        parkinson = self._parkinson_volatility(highs, lows)
        avg_range_pct = self._safe_fmean(range_pcts, 0.0)
        avg_body_ratio = self._safe_fmean(body_ratios, 0.0)
        return {
            'window_range_pct': window_range_pct,
            'avg_range_pct': avg_range_pct,
            'avg_body_ratio': avg_body_ratio,
            'ER_24': er,
            'CHOP_24': chop,
            'Parkinson_24': parkinson,
            'dead_share': dead_count / len(candles),
            'micro_body_share': micro_body_count / len(candles),
            'narrow_range_share': narrow_range_count / len(candles),
            'flat_close_share': (flat_close_count / max(1, len(closes) - 1)),
            'flat_mid_share': (flat_mid_count / max(1, len(mids) - 1)),
            'max_flat_close_run_share': (max_flat_close_run / max(1, len(closes) - 1)),
            'max_flat_mid_run_share': (max_flat_mid_run / max(1, len(mids) - 1)),
            'spike_share': spike_share,
            'flip_share': flip_share,
            'median_range': median_range,
            'spike_count': float(spike_count),
        }

    def _is_dead(self, metrics: Dict[str, float]) -> bool:
        strict_dead = (
            float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_dead_window_range_pct_max', 0.040) or 0.040)
            and float(metrics.get('avg_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_dead_avg_range_pct_max', 0.006) or 0.006)
            and float(metrics.get('Parkinson_24', 0.0)) < float(getattr(self.cfg, 'scanner_dead_parkinson_max', 0.006) or 0.006)
            and float(metrics.get('dead_share', 0.0)) >= float(getattr(self.cfg, 'scanner_dead_share_min', 0.50) or 0.50)
            and float(metrics.get('ER_24', 0.0)) < float(getattr(self.cfg, 'scanner_dead_er_max', 0.35) or 0.35)
        )
        flat_dead = (
            float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_flat_dead_window_range_pct_max', 0.070) or 0.070)
            and float(metrics.get('avg_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_flat_dead_avg_range_pct_max', 0.010) or 0.010)
            and float(metrics.get('ER_24', 0.0)) < float(getattr(self.cfg, 'scanner_flat_dead_er_max', 0.55) or 0.55)
            and float(metrics.get('flat_close_share', 0.0)) >= float(getattr(self.cfg, 'scanner_flat_close_share_min', 0.72) or 0.72)
            and float(metrics.get('flat_mid_share', 0.0)) >= float(getattr(self.cfg, 'scanner_flat_mid_share_min', 0.72) or 0.72)
            and float(metrics.get('narrow_range_share', 0.0)) >= float(getattr(self.cfg, 'scanner_narrow_range_share_min', 0.72) or 0.72)
            and float(metrics.get('micro_body_share', 0.0)) >= float(getattr(self.cfg, 'scanner_micro_body_share_min', 0.72) or 0.72)
        )
        hard_flat_dead = (
            float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_hard_flat_dead_window_range_pct_max', 0.025) or 0.025)
            and float(metrics.get('avg_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_hard_flat_dead_avg_range_pct_max', 0.0045) or 0.0045)
            and float(metrics.get('flat_close_share', 0.0)) >= float(getattr(self.cfg, 'scanner_hard_flat_close_share_min', 0.82) or 0.82)
            and float(metrics.get('narrow_range_share', 0.0)) >= float(getattr(self.cfg, 'scanner_hard_narrow_range_share_min', 0.80) or 0.80)
            and (
                float(metrics.get('micro_body_share', 0.0)) >= float(getattr(self.cfg, 'scanner_hard_micro_body_share_min', 0.78) or 0.78)
                or float(metrics.get('max_flat_close_run_share', 0.0)) >= float(getattr(self.cfg, 'scanner_hard_flat_run_share_min', 0.45) or 0.45)
            )
        )
        return strict_dead or flat_dead or hard_flat_dead

    def _is_spike_dead(self, metrics: Dict[str, float]) -> bool:
        dead_background = (
            float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_spike_dead_window_range_pct_max', 0.075) or 0.075)
            and float(metrics.get('avg_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_spike_dead_avg_range_pct_max', 0.011) or 0.011)
            and (
                float(metrics.get('dead_share', 0.0)) >= float(getattr(self.cfg, 'scanner_spike_dead_share_min', 0.34) or 0.34)
                or (
                    float(metrics.get('flat_close_share', 0.0)) >= float(getattr(self.cfg, 'scanner_spike_flat_close_share_min', 0.52) or 0.52)
                    and float(metrics.get('narrow_range_share', 0.0)) >= float(getattr(self.cfg, 'scanner_spike_narrow_range_share_min', 0.50) or 0.50)
                )
            )
        )
        return (
            dead_background
            and float(metrics.get('spike_share', 0.0)) >= float(getattr(self.cfg, 'scanner_spike_share_min', 0.08) or 0.08)
            and float(metrics.get('spike_count', 0.0)) >= float(getattr(self.cfg, 'scanner_spike_count_min', 1.0) or 1.0)
        )

    def _is_saw(self, metrics: Dict[str, float]) -> bool:
        return (
            float(metrics.get('CHOP_24', 0.0)) >= float(getattr(self.cfg, 'scanner_saw_chop_min', 61.8) or 61.8)
            and float(metrics.get('ER_24', 0.0)) <= float(getattr(self.cfg, 'scanner_saw_er_max', 0.28) or 0.28)
            and float(metrics.get('flip_share', 0.0)) >= float(getattr(self.cfg, 'scanner_saw_flip_share_min', 0.55) or 0.55)
            and float(metrics.get('window_range_pct', 0.0)) >= float(getattr(self.cfg, 'scanner_saw_window_range_pct_min', 0.030) or 0.030)
        )

    def _passes_pass_vitality(self, metrics: Dict[str, float]) -> bool:
        hard_fail = (
            float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_pass_gate_window_range_pct_min', 0.022) or 0.022)
            and float(metrics.get('avg_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_pass_gate_avg_range_pct_min', 0.0045) or 0.0045)
            and float(metrics.get('flat_close_share', 0.0)) >= float(getattr(self.cfg, 'scanner_pass_gate_flat_close_share_min', 0.78) or 0.78)
            and float(metrics.get('narrow_range_share', 0.0)) >= float(getattr(self.cfg, 'scanner_pass_gate_narrow_range_share_min', 0.72) or 0.72)
        )
        shelf_fail = (
            float(metrics.get('max_flat_close_run_share', 0.0)) >= float(getattr(self.cfg, 'scanner_pass_gate_flat_run_share_min', 0.40) or 0.40)
            and float(metrics.get('micro_body_share', 0.0)) >= float(getattr(self.cfg, 'scanner_pass_gate_micro_body_share_min', 0.72) or 0.72)
            and float(metrics.get('window_range_pct', 0.0)) < float(getattr(self.cfg, 'scanner_pass_gate_flat_run_window_range_pct_max', 0.035) or 0.035)
        )
        return not (hard_fail or shelf_fail)

    def _upsert_review_record(self, status: ScannerStatus) -> None:
        if status.filter_type not in {'DEAD', 'SAW', 'SPIKE_DEAD', 'PASS'}:
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
                'timeframe': str((status.raw or {}).get('timeframe') or getattr(self.cfg, 'timeframe', '5m') or '5m'),
            }
            self._review_records[key] = record
        else:
            record['last_seen_ts'] = now_ts
            record['last_seen'] = self._fmt_ts(now_ts)
            record['hit_count'] = int(record.get('hit_count') or 0) + 1
            record['reason'] = status.summary_text or status.primary_reason
            record['metrics'] = metrics
            record['active'] = True
            record['timeframe'] = str((status.raw or {}).get('timeframe') or getattr(self.cfg, 'timeframe', '5m') or '5m')
            if now_ts - float(record.get('verdict_time') or 0.0) > float(getattr(self.cfg, 'scanner_recheck_after_sec', 86400) or 86400):
                if str(record.get('user_verdict') or VERDICT_UNCHECKED) != VERDICT_UNCHECKED:
                    record['recheck_needed'] = True

    def upsert_good_positions(self, positions: List[dict]) -> None:
        # Legacy hook kept only for compatibility with GUI refresh flow.
        return None

    def _append_validation_log(self, record: dict) -> None:
        if self.validation_log_path is None:
            return
        self.validation_log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.validation_log_path.exists()
        with self.validation_log_path.open('a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp','pair','filter_type','user_verdict','review_tags','comment','hit_count','reason','timeframe','metrics_json'])
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
                filter_type = str(item.get('filter_type') or '').upper()
                if filter_type == 'GOOD':
                    filter_type = 'PASS'
                    item['filter_type'] = 'PASS'
                if filter_type == 'RIPPING':
                    filter_type = 'SPIKE_DEAD'
                    item['filter_type'] = 'SPIKE_DEAD'
                key = str(item.get('key') or self._record_key(item.get('pair'), item.get('filter_type')))
                item['key'] = self._record_key(item.get('pair'), item.get('filter_type'))
                self._review_records[key] = item
        except Exception:
            logging.exception('Failed to load scanner state')

    def _record_key(self, inst_id: object, filter_type: object) -> str:
        return f"{str(inst_id or '').upper()}::{str(filter_type or '').upper()}"

    def _fmt_ts(self, ts: float) -> str:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))

    def _safe_fmean(self, seq: List[float], default: float = 0.0) -> float:
        clean: list[float] = []
        for x in seq:
            try:
                value = float(x)
            except Exception:
                continue
            if math.isnan(value) or math.isinf(value):
                continue
            clean.append(value)
        return statistics.fmean(clean) if clean else float(default)

    def _median(self, seq: List[float]) -> float:
        clean = [float(x) for x in seq if x is not None]
        return statistics.median(clean) if clean else 0.0

    def _efficiency_ratio(self, closes: List[float]) -> float:
        if len(closes) < 2:
            return 1.0
        net = abs(closes[-1] - closes[0])
        total = sum(abs(b - a) for a, b in zip(closes[:-1], closes[1:]))
        return net / total if total > 0 else 1.0

    def _choppiness(self, tr_values: List[float], window_range: float, n: int) -> float:
        if n <= 1 or window_range <= 0:
            return 100.0
        tr_sum = sum(max(0.0, float(v)) for v in tr_values)
        if tr_sum <= 0:
            return 100.0
        ratio = tr_sum / max(window_range, 1e-12)
        return 100.0 * (math.log10(max(ratio, 1e-12)) / math.log10(max(n, 2)))

    def _parkinson_volatility(self, highs: List[float], lows: List[float]) -> float:
        values = []
        for hi, lo in zip(highs, lows):
            if hi > 0 and lo > 0 and hi >= lo:
                values.append((math.log(hi / lo) ** 2) / (4.0 * math.log(2.0)))
        return math.sqrt(self._safe_fmean(values, 0.0)) if values else 0.0
