from __future__ import annotations

import time
import logging
import math
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from common.trade_models import PositionState


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


class StopEngine:
    def __init__(self, bot):
        import logging
        self.bot = bot
        self.cfg = bot.cfg
        self.gateway = bot.gateway
        self.log_line = bot.log_line
        self.stop_engine_logger = bot.stop_engine_logger
        self.position_journal_logger = bot.position_journal_logger
        self.stats_logger = bot.stats_logger
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    def _mark_position_health(self, state: "PositionState", new_status: str, reason: str = "") -> None:
        self.bot._mark_position_health(state, new_status, reason=reason)

    def _register_execution_risk(self, *args, **kwargs) -> None:
        self.bot._register_execution_risk(*args, **kwargs)

    def _save_state(self) -> None:
        self.bot._save_state()

    def calculate_atr_from_candles(self, candles, period):
        return self.bot.calculate_atr_from_candles(candles, period)

    def trailing_stop(self, state, atr, current_price, candles=None):
        return self.bot.trailing_stop(state, atr, current_price, candles=candles)

    def try_pyramid(self, state, strategy_price, candles, candle_ts=0):
        return self.bot.try_pyramid(state, strategy_price, candles, candle_ts=candle_ts)

    def close_position(self, state, price, reason, candles=None):
        return self.bot.close_position(state, price, reason, candles=candles)

    def _update_position_extremes(self, state, current_price):
        return self.bot._update_position_extremes(state, current_price)

    def _log_stop_engine(self, event: str, state: Optional[PositionState] = None, **payload) -> None:
        base = {}
        if state is not None:
            base = {
                "trade_id": str(getattr(state, "trade_id", "") or ""),
                "inst_id": str(getattr(state, "inst_id", "") or ""),
                "side": str(getattr(state, "side", "") or ""),
                "qty": _safe_float(getattr(state, "qty", 0.0)),
                "strategy_stop_price": _safe_float(getattr(state, "stop_price", 0.0)),
                "exchange_stop_price": _safe_float(getattr(state, "exchange_stop_price", 0.0)),
                "exchange_stop_algo_id": str(getattr(state, "exchange_stop_algo_id", "") or ""),
                "exchange_stop_status": str(getattr(state, "exchange_stop_status", "") or ""),
                "atr": _safe_float(getattr(state, "atr", 0.0)),
            }
        base.update(payload)
        self.stop_engine_logger.log(event, **base)

    def _extract_algo_id(self, resp: dict) -> str:
        for row in list((resp or {}).get("data", []) or []):
            algo_id = str(row.get("algoId") or row.get("algoClOrdId") or "").strip()
            if algo_id:
                return algo_id
        return ""

    def _exchange_stop_move_threshold(self, state: PositionState, target_stop: float) -> float:
        atr_part = abs(float(getattr(state, "atr", 0.0) or 0.0)) * float(getattr(self.cfg, "exchange_stop_min_move_atr", 0.15) or 0.15)
        price_anchor = max(abs(float(target_stop or 0.0)), abs(float(getattr(state, "last_px", 0.0) or 0.0)), abs(float(getattr(state, "avg_px", 0.0) or 0.0)), 1e-12)
        pct_part = price_anchor * float(getattr(self.cfg, "exchange_stop_min_move_pct", 0.0002) or 0.0002)
        return max(atr_part, pct_part, 1e-12)

    def _price_tick_size(self, state: PositionState) -> float:
        try:
            info = dict(getattr(self.gateway, "instrument_cache", {}).get(str(getattr(state, "inst_id", "") or ""), {}) or {})
            tick = _safe_float(info.get("tickSz", 0.0), 0.0)
            return tick if tick > 0.0 else 0.0
        except Exception:
            return 0.0

    def _normalize_stop_price(self, state: PositionState, price: float) -> float:
        price = float(price or 0.0)
        if price <= 0.0:
            return 0.0
        tick = self._price_tick_size(state)
        if tick > 0.0:
            if str(getattr(state, "side", "") or "").lower() == "short":
                steps = math.ceil((price / tick) - 1e-12)
            else:
                steps = math.floor((price / tick) + 1e-12)
            return round(steps * tick, 12)
        return round(price, 8)

    def _stop_prices_equal(self, state: PositionState, a: float, b: float) -> bool:
        na = self._normalize_stop_price(state, a)
        nb = self._normalize_stop_price(state, b)
        if na <= 0.0 or nb <= 0.0:
            return False
        tick = self._price_tick_size(state)
        tol = max(tick * 0.5 if tick > 0.0 else 0.0, 1e-10)
        return abs(na - nb) <= tol

    def _stop_action_cooldown_sec(self) -> float:
        return max(0.5, float(getattr(self.cfg, "exchange_stop_action_cooldown_sec", 2.5) or 2.5))

    def _stop_snapshot_ttl_sec(self) -> float:
        return max(0.1, float(getattr(self.cfg, "exchange_stop_snapshot_ttl_sec", 1.0) or 1.0))

    def _invalidate_stop_snapshot_cache(self, state: PositionState) -> None:
        state.stop_snapshot_cache_ts = 0.0
        state.stop_snapshot_cache_rows = []

    def _get_pending_algo_rows(self, state: PositionState, force_rest: bool = False) -> list[dict]:
        now_ts = time.time()
        cache_ts = float(getattr(state, "stop_snapshot_cache_ts", 0.0) or 0.0)
        cache_rows = list(getattr(state, "stop_snapshot_cache_rows", []) or [])
        if not force_rest and cache_rows and (now_ts - cache_ts) <= self._stop_snapshot_ttl_sec():
            return cache_rows
        try:
            rows = list(self.gateway.get_pending_algo_orders(state.inst_id, prefer_ws=not force_rest, ttl_sec=self._stop_snapshot_ttl_sec()) or [])
        except TypeError:
            try:
                rows = list(self.gateway.get_pending_algo_orders(state.inst_id, prefer_ws=not force_rest) or [])
            except Exception:
                rows = []
        except Exception:
            rows = []
        state.stop_snapshot_cache_ts = now_ts
        state.stop_snapshot_cache_rows = list(rows)
        return rows

    def _begin_stop_action(self, state: PositionState, action: str, target_stop: float) -> None:
        state.stop_action_in_flight = True
        state.stop_action_kind = str(action or "")
        state.stop_action_target_px = self._normalize_stop_price(state, target_stop)
        state.stop_action_started_ts = time.time()
        if target_stop > 0.0:
            state.last_requested_stop_px = self._normalize_stop_price(state, target_stop)
        state.stop_last_action_ts = state.stop_action_started_ts
        self._invalidate_stop_snapshot_cache(state)

    def _finish_stop_action(self, state: PositionState, success: bool, confirmed_stop: float = 0.0) -> None:
        state.stop_action_in_flight = False
        state.stop_action_kind = ""
        state.stop_action_started_ts = 0.0
        state.stop_action_target_px = 0.0
        state.stop_last_action_ts = time.time()
        if success and confirmed_stop > 0.0:
            norm = self._normalize_stop_price(state, confirmed_stop)
            state.last_requested_stop_px = norm
            state.last_confirmed_stop_px = norm
            state.exchange_stop_price = norm
        self._invalidate_stop_snapshot_cache(state)

    def _stop_action_locked(self, state: PositionState, target_stop: float, action: str) -> bool:
        now_ts = time.time()
        cooldown = self._stop_action_cooldown_sec()
        norm_target = self._normalize_stop_price(state, target_stop)
        needs_full_cover_refresh = not bool(getattr(state, "exchange_stop_full_position", False))
        if bool(getattr(state, "stop_action_in_flight", False)):
            started_ts = float(getattr(state, "stop_action_started_ts", 0.0) or 0.0)
            inflight_target = float(getattr(state, "stop_action_target_px", 0.0) or 0.0)
            if (now_ts - started_ts) <= cooldown and self._stop_prices_equal(state, inflight_target, norm_target):
                if needs_full_cover_refresh:
                    self._log_stop_engine("STOP_LOCK_BYPASSED_FULL_COVER", state, action=action, requested_stop=norm_target, inflight_action=str(getattr(state, "stop_action_kind", "") or ""))
                else:
                    self._log_stop_engine("STOP_AMEND_LOCKED", state, action=action, requested_stop=norm_target, inflight_action=str(getattr(state, "stop_action_kind", "") or ""))
                    return True
        last_requested = float(getattr(state, "last_requested_stop_px", 0.0) or 0.0)
        last_action_ts = float(getattr(state, "stop_last_action_ts", 0.0) or 0.0)
        if last_requested > 0.0 and (now_ts - last_action_ts) <= cooldown and self._stop_prices_equal(state, last_requested, norm_target):
            if needs_full_cover_refresh:
                self._log_stop_engine("STOP_LOCK_BYPASSED_FULL_COVER", state, action=action, requested_stop=norm_target, cooldown=cooldown)
            else:
                self._log_stop_engine("STOP_AMEND_LOCKED", state, action=action, requested_stop=norm_target, cooldown=cooldown)
                return True
        return False

    def _should_skip_stop_update(self, state: PositionState, target_stop: float, reason: str = "") -> bool:
        norm_target = self._normalize_stop_price(state, target_stop)
        current_exchange = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
        last_confirmed = float(getattr(state, "last_confirmed_stop_px", 0.0) or 0.0)
        if not bool(getattr(state, "exchange_stop_full_position", False)):
            self._log_stop_engine("STOP_NOOP_BYPASSED_FULL_COVER", state, reason=reason or "full_cover_refresh_required", requested_stop=norm_target, current_exchange_stop=current_exchange, exchange_stop_qty=float(getattr(state, "exchange_stop_qty", 0.0) or 0.0), position_qty=float(getattr(state, "qty", 0.0) or 0.0))
            return False
        if current_exchange > 0.0 and self._stop_prices_equal(state, current_exchange, norm_target):
            self._log_stop_engine("STOP_NOOP_AMEND_SKIPPED", state, reason=reason or "exchange_stop_already_aligned", requested_stop=norm_target, current_exchange_stop=current_exchange)
            return True
        if last_confirmed > 0.0 and self._stop_prices_equal(state, last_confirmed, norm_target):
            self._log_stop_engine("STOP_NOOP_AMEND_SKIPPED", state, reason=reason or "confirmed_stop_already_aligned", requested_stop=norm_target, current_exchange_stop=last_confirmed)
            return True
        return False

    def _clear_exchange_stop_state(self, state: PositionState, status: str = "") -> None:
        state.exchange_stop_algo_id = ""
        state.exchange_stop_price = 0.0
        state.exchange_stop_qty = 0.0
        state.exchange_stop_full_position = False
        state.exchange_stop_last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.exchange_stop_status = status
        state.exchange_stop_last_sync_ts = time.time()
        state.exchange_stop_last_error_code = ""
        state.exchange_stop_last_error_msg = ""
        state.exchange_stop_last_update_method = ""
        state.last_confirmed_stop_px = 0.0
        self._invalidate_stop_snapshot_cache(state)

    def _market_allows_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0) -> bool:
        try:
            return bool(self.gateway.is_protective_stop_valid(state.inst_id, str(getattr(state, "side", "") or ""), float(target_stop or 0.0), current_price=current_price))
        except Exception:
            px = float(current_price or getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
            if px <= 0.0:
                return True
            if state.side == "long":
                return float(target_stop or 0.0) < px
            return float(target_stop or 0.0) > px

    def _mark_local_protective_exit(self, state: PositionState, reason: str, current_price: float = 0.0, requested_stop: float = 0.0, response: Optional[dict] = None) -> None:
        code = ""
        msg = ""
        if isinstance(response, dict):
            code = str(response.get("code", "") or "")
            msg = str(response.get("msg", "") or "")
            data = list(response.get("data", []) or [])
            if data and not msg:
                msg = str(data[0].get("sMsg") or data[0].get("msg") or "")
            if data and not code:
                code = str(data[0].get("sCode") or data[0].get("code") or "")
        state.exchange_stop_last_error_code = code
        state.exchange_stop_last_error_msg = msg
        self._request_emergency_close(state, reason=reason, current_price=current_price)
        self._log_stop_engine("LOCAL_PROTECTIVE_EXIT", state, reason=reason, requested_stop=requested_stop, current_price=current_price, response=response or {})

    def _stop_registry_key(self, state: PositionState) -> tuple[str, str]:
        return (str(getattr(state, "inst_id", "") or "").strip(), str(getattr(state, "side", "") or "").strip().lower())

    def _row_stop_qty(self, row: Optional[dict]) -> float:
        if not row:
            return 0.0
        return _safe_float((row or {}).get("sz", (row or {}).get("actualSz", 0.0)), 0.0)

    def _row_close_fraction(self, row: Optional[dict]) -> float:
        if not row:
            return 0.0
        return _safe_float((row or {}).get("closeFraction", 0.0), 0.0)

    def _exchange_stop_covers_full_position(self, state: PositionState, row: Optional[dict]) -> bool:
        if not row:
            return False
        close_fraction = self._row_close_fraction(row)
        if close_fraction >= 0.999999:
            return True
        stop_qty = self._row_stop_qty(row)
        pos_qty = abs(float(getattr(state, "qty", 0.0) or 0.0))
        if stop_qty > 0.0 and pos_qty > 0.0:
            tol = max(1e-9, pos_qty * 0.01)
            return abs(stop_qty - pos_qty) <= tol
        algo_id = str((row or {}).get("algoId") or (row or {}).get("algoClOrdId") or "").strip()
        local_algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
        local_qty = abs(float(getattr(state, "exchange_stop_qty", 0.0) or 0.0))
        if algo_id and local_algo_id and algo_id == local_algo_id and local_qty > 0.0 and pos_qty > 0.0:
            tol = max(1e-9, pos_qty * 0.01)
            return abs(local_qty - pos_qty) <= tol
        # Entry-attached bootstrap stop can cover the whole position only while the position
        # still has its initial single-unit size. After any add, lack of explicit coverage data
        # must be treated as partial/stale protection and rebuilt to full size.
        if algo_id and int(getattr(state, "units", 1) or 1) <= 1:
            method = str(getattr(state, "exchange_stop_last_update_method", "") or "")
            if method == "entry_attach" and pos_qty > 0.0:
                return True
        return False

    def _exchange_stop_row_is_valid(self, state: PositionState, row: Optional[dict], target_stop: float = 0.0, require_full_cover: bool = True) -> bool:
        if not row:
            return False
        desired_side = "sell" if str(getattr(state, "side", "") or "").lower() == "long" else "buy"
        side = str((row or {}).get("side") or "").strip().lower()
        if side and side != desired_side:
            return False
        algo_id = str((row or {}).get("algoId") or "").strip()
        if not algo_id:
            return False
        trigger = _safe_float((row or {}).get("slTriggerPx", (row or {}).get("triggerPx", 0.0)), 0.0)
        if target_stop > 0.0 and trigger > 0.0:
            threshold = self._exchange_stop_move_threshold(state, target_stop)
            if abs(trigger - target_stop) > max(threshold, 1e-12):
                return False
        if require_full_cover and not self._exchange_stop_covers_full_position(state, row):
            return False
        return True


    def _algo_row_state(self, row: Optional[dict]) -> str:
        if not row:
            return ""
        for key in ("state", "algoStatus", "status", "ordState"):
            value = str((row or {}).get(key) or "").strip().lower()
            if value:
                return value
        return ""

    def _algo_row_is_live(self, row: Optional[dict]) -> bool:
        if not row:
            return False
        state = self._algo_row_state(row)
        if not state:
            return True
        dead_states = {
            "canceled", "cancelled", "filled", "partially_filled", "partially-filled",
            "failed", "order_failed", "effective", "stopped", "triggered", "completed",
            "closed", "inactive", "pause", "paused"
        }
        return state not in dead_states

    def _request_emergency_close(self, state: PositionState, reason: str, current_price: float = 0.0) -> None:
        state.local_protective_exit_pending = True
        state.local_protective_exit_reason = str(reason or "exchange_stop_unavailable")
        state.exchange_stop_status = "emergency_close_required"
        self._update_stop_tracking(state, False, reason=reason or "exchange_stop_unavailable", hard=False)
        self._register_execution_risk(state.inst_id, f"emergency-close:{reason}", stage="stop_emergency", severity=3.0, quarantine=False)
        self._log_stop_engine("STOP_EMERGENCY_CLOSE_REQUESTED", state, reason=reason, current_price=current_price)

    def _mark_exchange_stop_desync(self, state: PositionState, reason: str = "") -> None:
        state.exchange_stop_desync = True
        state.exchange_stop_desync_reason = str(reason or "exchange_stop_desync")
        self._log_stop_engine("STOP_DESYNC", state, reason=state.exchange_stop_desync_reason)

    def _clear_exchange_stop_desync(self, state: PositionState) -> None:
        state.exchange_stop_desync = False
        state.exchange_stop_desync_reason = ""

    def _with_stop_recovery_lock(self, state: PositionState, reason: str = "") -> bool:
        now_ts = time.time()
        if bool(getattr(state, "stop_recovery_in_progress", False)):
            started_ts = float(getattr(state, "stop_recovery_started_ts", 0.0) or 0.0)
            if started_ts > 0.0 and (now_ts - started_ts) < 20.0:
                self._log_stop_engine("STOP_RECOVERY_SKIPPED", state, reason=reason or "recovery_already_running")
                return False
        state.stop_recovery_in_progress = True
        state.stop_recovery_started_ts = now_ts
        return True

    def _release_stop_recovery_lock(self, state: PositionState, success: bool = False) -> None:
        state.stop_recovery_in_progress = False
        state.stop_recovery_started_ts = 0.0
        if success:
            state.stop_recovery_failures = 0
        else:
            state.stop_recovery_failures = int(getattr(state, "stop_recovery_failures", 0) or 0) + 1

    def _safe_exchange_stop_target(self, state: PositionState, target_stop: float, current_price: float = 0.0) -> float:
        target_stop = float(target_stop or 0.0)
        if target_stop <= 0.0:
            return target_stop
        try:
            normalized = float(self.gateway.normalize_protective_stop(state.inst_id, str(getattr(state, "side", "") or ""), target_stop, current_price=current_price) or 0.0)
            if normalized > 0.0:
                return self._normalize_stop_price(state, normalized)
        except Exception:
            pass
        px = float(current_price or getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        if px <= 0.0:
            return self._normalize_stop_price(state, target_stop)
        min_step = max(abs(float(getattr(state, "atr", 0.0) or 0.0)) * 0.02, px * 0.0005, 1e-8)
        if str(getattr(state, "side", "") or "").lower() == "short":
            target_stop = max(target_stop, px + min_step)
        else:
            target_stop = min(target_stop, max(px - min_step, 1e-8))
        return self._normalize_stop_price(state, target_stop)

    def _safe_short_stop_target(self, state: PositionState, target_stop: float, current_price: float = 0.0) -> float:
        return self._safe_exchange_stop_target(state, target_stop, current_price=current_price)

    def _force_replace_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0, reason: str = "") -> bool:
        target_stop = self._safe_exchange_stop_target(state, float(target_stop or 0.0), current_price=current_price)
        if target_stop <= 0.0:
            return False
        if not self._with_stop_recovery_lock(state, reason=reason or "force_replace"):
            return False
        try:
            self._log_stop_engine("STOP_FORCE_REPLACE", state, requested_stop=target_stop, current_price=current_price, reason=reason)
            cancelled = self._cancel_exchange_stop(state, reason=f"force_replace:{reason}" if reason else "force_replace")
            if not cancelled:
                self._mark_exchange_stop_desync(state, f"force_replace_cancel_failed:{reason}")
                return False
            if not self._confirm_exchange_stop_absent(state, attempts=8, delay_sec=0.35):
                self._clear_exchange_stop_state(state, status="force_replace_missing_confirm_failed")
                self._mark_exchange_stop_desync(state, f"force_replace_absent_confirm_failed:{reason}")
                return False
            placed = self._place_exchange_stop(state, target_stop, reason=reason or "force_replace")
            if not placed:
                self._mark_exchange_stop_desync(state, f"force_replace_place_failed:{reason}")
                return False
            if not self._confirm_exchange_stop_present(state, target_stop, attempts=8, delay_sec=0.35):
                self._mark_exchange_stop_desync(state, f"force_replace_present_confirm_failed:{reason}")
                return False
            self._clear_exchange_stop_desync(state)
            self._release_stop_recovery_lock(state, success=True)
            return True
        finally:
            if bool(getattr(state, "stop_recovery_in_progress", False)):
                self._release_stop_recovery_lock(state, success=False)

    def _find_existing_exchange_stop_row(self, state: PositionState, target_stop: float = 0.0, force_rest: bool = False) -> Optional[dict]:
        rows = self._get_pending_algo_rows(state, force_rest=force_rest)
        if not rows:
            return None
        desired_side = "sell" if str(getattr(state, "side", "") or "").lower() == "long" else "buy"
        target_stop = float(target_stop or 0.0)
        threshold = self._exchange_stop_move_threshold(state, target_stop if target_stop > 0 else float(getattr(state, "stop_price", 0.0) or 0.0))
        matched_full = None
        matched_partial = None
        fallback_full = None
        fallback = None
        for row in rows:
            if not self._algo_row_is_live(row):
                continue
            side = str(row.get("side") or "").strip().lower()
            if side and side != desired_side:
                continue
            algo_id = str(row.get("algoId") or row.get("algoClOrdId") or "").strip()
            if not algo_id:
                continue
            trigger = _safe_float(row.get("slTriggerPx", row.get("triggerPx", 0.0)), 0.0)
            full_cover = self._exchange_stop_covers_full_position(state, row)
            if target_stop > 0 and trigger > 0 and abs(trigger - target_stop) <= max(threshold, 1e-12):
                if full_cover:
                    matched_full = row
                    break
                if matched_partial is None:
                    matched_partial = row
            elif full_cover and fallback_full is None:
                fallback_full = row
            if fallback is None:
                fallback = row
        return matched_full or matched_partial or fallback_full or fallback

    def _attach_existing_exchange_stop(self, state: PositionState, row: Optional[dict], status: str = "active") -> bool:
        if not row:
            return False
        algo_id = str(row.get("algoId") or row.get("algoClOrdId") or "").strip()
        if not algo_id:
            return False
        trigger = _safe_float(row.get("slTriggerPx", row.get("triggerPx", getattr(state, "exchange_stop_price", 0.0))), 0.0)
        state.exchange_stop_algo_id = algo_id
        row_qty = self._row_stop_qty(row)
        if row_qty > 0.0:
            state.exchange_stop_qty = row_qty
        elif str(getattr(state, "exchange_stop_algo_id", "") or "").strip() == algo_id and float(getattr(state, "exchange_stop_qty", 0.0) or 0.0) > 0.0:
            state.exchange_stop_qty = float(getattr(state, "exchange_stop_qty", 0.0) or 0.0)
        state.exchange_stop_full_position = self._exchange_stop_covers_full_position(state, row)
        if trigger > 0:
            norm_trigger = self._normalize_stop_price(state, trigger)
            state.exchange_stop_price = norm_trigger
            state.last_confirmed_stop_px = norm_trigger
            state.last_requested_stop_px = norm_trigger
        state.exchange_stop_last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.exchange_stop_status = status
        state.exchange_stop_last_sync_ts = time.time()
        state.exchange_stop_last_error_code = ""
        state.exchange_stop_last_error_msg = ""
        state.exchange_stop_last_update_method = str(getattr(state, "exchange_stop_last_update_method", "") or "attach")
        state.local_protective_exit_pending = False
        state.local_protective_exit_reason = ""
        self._clear_exchange_stop_desync(state)
        self._finish_stop_action(state, True, confirmed_stop=float(getattr(state, "exchange_stop_price", 0.0) or trigger or 0.0))
        self._update_stop_tracking(state, True, reason=status)
        return True

    def _sync_stop_from_exchange_snapshot(self, state: PositionState, target_stop: float = 0.0, status: str = "active") -> bool:
        row = self._find_existing_exchange_stop_row(state, target_stop=target_stop)
        return self._attach_existing_exchange_stop(state, row, status=status)

    def _stop_management_disabled(self, state: PositionState) -> bool:
        return bool(getattr(state, "position_absence_synced", False) or getattr(state, "stop_absence_sync_in_progress", False))

    def _ensure_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0, reason: str = "") -> bool:
        if self._stop_management_disabled(state):
            return False
        target_stop = self._safe_exchange_stop_target(state, float(target_stop or 0.0), current_price=current_price)
        if target_stop <= 0.0:
            return False
        if self._should_skip_stop_update(state, target_stop, reason=reason or "ensure_existing_exchange_stop"):
            return True
        if self._stop_action_locked(state, target_stop, "ensure"):
            return True
        if self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active"):
            current_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            threshold = self._exchange_stop_move_threshold(state, target_stop)
            if not bool(getattr(state, "exchange_stop_full_position", False)):
                self._log_stop_engine("STOP_PARTIAL_COVERAGE_FAULT", state, reason=reason or "ensure_existing_exchange_stop", requested_stop=target_stop, exchange_stop_qty=float(getattr(state, "exchange_stop_qty", 0.0) or 0.0), position_qty=float(getattr(state, "qty", 0.0) or 0.0))
                return self._force_replace_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "ensure_full_cover")
            if current_exchange_stop > 0.0 and abs(current_exchange_stop - target_stop) <= max(threshold, 1e-12):
                self._log_stop_engine("STOP_DEDUP_SKIPPED", state, reason=reason or "ensure_existing_exchange_stop", requested_stop=target_stop)
                return True
            algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
            if algo_id:
                return self._amend_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "ensure_existing_exchange_stop")
        return self._place_exchange_stop(state, target_stop, reason=reason or "ensure_exchange_stop")

    def _adopt_existing_exchange_stop(self, state: PositionState, target_stop: float = 0.0, status: str = "active", force_rest: bool = False) -> bool:
        row = self._find_existing_exchange_stop_row(state, target_stop=target_stop, force_rest=force_rest)
        if row is None and float(target_stop or 0.0) > 0.0:
            row = self._find_existing_exchange_stop_row(state, target_stop=0.0, force_rest=force_rest)
        if row is None:
            return False
        attached = self._attach_existing_exchange_stop(state, row, status=status)
        if attached:
            self._log_stop_engine("STOP_ADOPTED_EXISTING", state, requested_stop=float(target_stop or 0.0), status=status, force_rest=force_rest)
        return attached

    def _sync_absent_position_once(self, state: PositionState, current_price: float = 0.0, reason: str = "position_absent_on_exchange") -> bool:
        if bool(getattr(state, "position_absence_synced", False)):
            return False
        if self._stop_management_disabled(state):
            return False
        attempts = max(3, int(getattr(self.cfg, "position_absence_confirm_attempts", 4) or 4))
        delay_sec = max(0.25, float(getattr(self.cfg, "position_absence_confirm_delay_sec", 0.45) or 0.45))
        observed_absent = 0
        for attempt in range(1, attempts + 1):
            still_present = False
            try:
                positions = list(self.gateway.get_positions() or [])
            except Exception:
                positions = []
            for row in positions:
                inst = str(row.get("instId") or row.get("inst_id") or "").strip()
                if inst != str(getattr(state, "inst_id", "") or ""):
                    continue
                pos_side = str(row.get("posSide") or row.get("positionSide") or row.get("side") or "").strip().lower()
                if pos_side and pos_side not in {str(getattr(state, "side", "") or "").lower(), "net"}:
                    continue
                qty = abs(_safe_float(row.get("pos", row.get("qty", row.get("size", 0.0))), 0.0))
                if qty > 0.0:
                    still_present = True
                    break
            if still_present:
                state.position_absence_confirm_count = 0
                self._log_stop_engine("STOP_POSITION_ABSENCE_FALSE_ALARM", state, reason=reason, current_price=current_price, attempt=attempt)
                return False
            observed_absent += 1
            if attempt < attempts and delay_sec > 0.0:
                time.sleep(delay_sec)
        if observed_absent < attempts:
            return False
        state.stop_absence_sync_in_progress = True
        state.position_absence_synced = True
        self._clear_exchange_stop_state(state, status="position_absent_on_exchange")
        self._mark_position_health(state, "STOP_UNVERIFIED", reason=reason)
        self._update_stop_tracking(state, False, reason=reason, hard=True)
        self._log_stop_engine("STOP_POSITION_ABSENT_SYNC", state, reason=reason, current_price=current_price, confirmations=observed_absent)
        self.log_line.emit(f"[STOP] {state.inst_id}: позиция отсутствует на бирже, stop retry остановлен и запущена синхронизация")
        try:
            self.close_position(state, current_price or float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0), "Синхронизация: позиция отсутствует на бирже")
        except Exception as exc:
            logging.warning("Absent position sync failed for %s: %s", state.inst_id, exc)
        finally:
            state.stop_absence_sync_in_progress = False
        return False

    def _cancel_exchange_stop(self, state: PositionState, reason: str = "") -> bool:
        algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
        if not algo_id:
            existing_row = self._find_existing_exchange_stop_row(state, target_stop=float(getattr(state, "stop_price", 0.0) or 0.0))
            if existing_row is not None:
                self._attach_existing_exchange_stop(state, existing_row, status="active")
                algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
            else:
                self._clear_exchange_stop_state(state, status="cancel_skipped")
                return True
        try:
            resp = self.gateway.cancel_algo_by_id(state.inst_id, algo_id)
            ok = str(resp.get("code", "")) == "0"
        except Exception as exc:
            ok = False
            resp = {"code": "1", "msg": str(exc), "data": []}
        if ok:
            self._log_stop_engine("STOP_CANCELLED", state, reason=reason, cancelled_algo_id=algo_id)
            self._clear_exchange_stop_state(state, status="cancelled")
            return True
        data = list((resp or {}).get("data", []) or [])
        fail_msg = str((data[0].get("sMsg") if data else "") or resp.get("msg", "") or "")
        fail_code = str((data[0].get("sCode") if data else "") or resp.get("code", "") or "")
        lower_msg = fail_msg.lower()
        if fail_code == "51400" or "does not exist" in lower_msg or "filled" in lower_msg or "canceled" in lower_msg:
            self._log_stop_engine("STOP_CANCELLED", state, reason=reason or "already_missing", cancelled_algo_id=algo_id, response=resp)
            self._clear_exchange_stop_state(state, status="cancelled_or_missing")
            return True
        if "timed out" in lower_msg or "timeout" in lower_msg:
            state.exchange_stop_status = "cancel_pending_confirmation"
            state.exchange_stop_last_error_code = fail_code
            state.exchange_stop_last_error_msg = fail_msg
            state.exchange_stop_last_sync_ts = 0.0
            self._log_stop_engine("STOP_CANCEL_PENDING", state, reason=reason, response=resp)
            self._register_execution_risk(state.inst_id, f"cancel-timeout:{fail_msg or fail_code}", stage="stop_cancel", severity=2.0, quarantine=False)
            return False
        self._log_stop_engine("STOP_ERROR", state, operation="cancel_stop", reason=reason, response=resp)
        state.exchange_stop_status = "cancel_error"
        state.exchange_stop_last_error_code = fail_code
        state.exchange_stop_last_error_msg = fail_msg
        return False

    def _place_exchange_stop(self, state: PositionState, target_stop: float, reason: str = "") -> bool:
        if not bool(getattr(self.cfg, "exchange_protective_stop_enabled", True)):
            return False
        target_stop = self._safe_exchange_stop_target(state, float(target_stop or 0.0), current_price=float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0))
        current_price = float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        if self._should_skip_stop_update(state, target_stop, reason=reason or "dedup_existing_exchange_stop"):
            return True
        if self._stop_action_locked(state, target_stop, "place"):
            return True
        if target_stop <= 0.0 or float(getattr(state, "qty", 0.0) or 0.0) <= 0.0:
            self._log_stop_engine("STOP_ERROR", state, operation="place_stop", reason=reason, response="invalid_stop_or_qty", requested_stop=target_stop)
            return False
        if self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active"):
            current_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            threshold = self._exchange_stop_move_threshold(state, target_stop)
            if not bool(getattr(state, "exchange_stop_full_position", False)):
                self._log_stop_engine("STOP_PARTIAL_COVERAGE_FAULT", state, reason=reason or "dedup_existing_exchange_stop", requested_stop=target_stop, exchange_stop_qty=float(getattr(state, "exchange_stop_qty", 0.0) or 0.0), position_qty=float(getattr(state, "qty", 0.0) or 0.0))
                return self._force_replace_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "replace_partial_cover")
            if current_exchange_stop > 0.0 and abs(current_exchange_stop - target_stop) > max(threshold, 1e-12):
                if str(getattr(state, "exchange_stop_algo_id", "") or "").strip():
                    return self._amend_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "align_existing_stop")
            self._log_stop_engine("STOP_DEDUP_SKIPPED", state, reason=reason or "dedup_existing_exchange_stop", requested_stop=target_stop)
            return True
        if str(getattr(state, "exchange_stop_status", "") or "") == "cancel_pending_confirmation":
            confirmed = self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active_after_cancel_timeout")
            if confirmed:
                self._log_stop_engine("STOP_DEDUP_SKIPPED", state, reason="cancel_pending_but_existing_stop_alive", requested_stop=target_stop)
                return True
            self._log_stop_engine("STOP_MOVE_SKIPPED", state, reason="cancel_pending_confirmation", requested_stop=target_stop, current_price=current_price)
            return False
        if not self._market_allows_exchange_stop(state, target_stop, current_price=current_price):
            state.exchange_stop_status = "rejected_market_crossed"
            self._log_stop_engine("STOP_REJECTED", state, operation="place_stop", reason="market_already_crossed_stop", requested_stop=target_stop, current_price=current_price)
            self._mark_local_protective_exit(state, reason="market_already_crossed_stop", current_price=current_price, requested_stop=target_stop, response={"code": "LOCAL", "msg": "market_already_crossed_stop"})
            self.log_line.emit(f"[STOP] {state.inst_id}: цена уже пересекла стоп {target_stop:.6f}, включён локальный защитный выход")
            self._update_stop_tracking(state, False, reason="market_already_crossed_stop", hard=False)
            return False
        attempts = max(1, int(getattr(self.cfg, "exchange_stop_retry_attempts", 2) or 2))
        delay = max(0.0, float(getattr(self.cfg, "exchange_stop_retry_delay_sec", 0.35) or 0.35))
        last_resp = None
        had_existing_stop = bool(getattr(state, "exchange_stop_algo_id", "") or float(getattr(state, "exchange_stop_price", 0.0) or 0.0) > 0.0)
        state.exchange_stop_status = "place_pending"
        self._begin_stop_action(state, "place", target_stop)
        for attempt in range(1, attempts + 1):
            try:
                resp = self.gateway.place_exchange_stop(state.inst_id, state.side, state.qty, target_stop)
            except Exception as exc:
                resp = {"code": "1", "msg": str(exc), "data": []}
            last_resp = resp
            if str(resp.get("code", "")) == "0":
                algo_id = self._extract_algo_id(resp)
                state.exchange_stop_algo_id = algo_id
                state.exchange_stop_price = target_stop
                state.exchange_stop_qty = float(getattr(state, "qty", 0.0) or 0.0)
                state.exchange_stop_full_position = True
                state.exchange_stop_last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state.exchange_stop_status = "active"
                state.exchange_stop_last_sync_ts = time.time()
                state.exchange_stop_last_error_code = ""
                state.exchange_stop_last_error_msg = ""
                state.exchange_stop_last_update_method = "place"
                state.local_protective_exit_pending = False
                state.local_protective_exit_reason = ""
                if not bool(getattr(state, "initial_stop_set_ts", 0.0) or 0.0):
                    state.initial_stop_set_ts = time.time()
                if float(getattr(state, "initial_stop_verify_due_ts", 0.0) or 0.0) <= 0.0:
                    state.initial_stop_verify_due_ts = float(getattr(state, "initial_stop_set_ts", time.time()) or time.time()) + float(getattr(self.cfg, "initial_stop_verify_delay_sec", 12.0) or 12.0)
                self._log_stop_engine("STOP_REPLACED" if had_existing_stop else "STOP_PLACED", state, requested_stop=target_stop, reason=reason, response_code=resp.get("code", ""), attempt=attempt)
                self.log_line.emit(f"[STOP] {state.inst_id}: биржевой стоп установлен {target_stop:.6f} ({reason or 'n/a'})")
                self._finish_stop_action(state, True, confirmed_stop=target_stop)
                self._update_stop_tracking(state, True, reason=reason or "exchange_stop_active")
                return True
            data = list((resp or {}).get("data", []) or [])
            fail_code = str((data[0].get("sCode") if data else "") or resp.get("code", "") or "")
            fail_msg = str((data[0].get("sMsg") if data else "") or resp.get("msg", "") or "")
            lower_msg = fail_msg.lower()
            state.exchange_stop_last_error_code = fail_code
            state.exchange_stop_last_error_msg = fail_msg
            if fail_code == "51088" or "only place 1 tp/sl order" in lower_msg:
                adopted = self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active_conflict_existing", force_rest=True)
                if adopted:
                    current_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
                    threshold = self._exchange_stop_move_threshold(state, target_stop)
                    if current_exchange_stop > 0.0 and abs(current_exchange_stop - target_stop) > max(threshold, 1e-12):
                        self._finish_stop_action(state, False)
                        return self._amend_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "adopt_existing_after_51088")
                    self._finish_stop_action(state, True, confirmed_stop=current_exchange_stop or target_stop)
                    return True
            if fail_code == "51280" or "trigger price must be less than the last price" in lower_msg or "trigger price must be greater than the last price" in lower_msg:
                state.exchange_stop_status = "rejected_market_crossed"
                self._log_stop_engine("STOP_REJECTED", state, operation="place_stop", reason=reason, requested_stop=target_stop, current_price=current_price, response=resp)
                self._mark_local_protective_exit(state, reason="exchange_stop_rejected_market_crossed", current_price=current_price, requested_stop=target_stop, response=resp)
                self.log_line.emit(f"[STOP] {state.inst_id}: биржа отклонила стоп ({fail_code}) — цена уже за триггером, закрытие будет локально")
                self._update_stop_tracking(state, False, reason="exchange_stop_rejected_market_crossed", hard=False)
                return False
            if fail_code == "51023" or "position doesn't exist" in lower_msg:
                self._log_stop_engine("STOP_MISSING", state, operation="place_stop", reason=reason or "position_absent", requested_stop=target_stop, current_price=current_price, response=resp)
                return self._sync_absent_position_once(state, current_price=current_price, reason="position_absent_on_exchange")
            if attempt < attempts and delay > 0:
                time.sleep(delay)
        self._log_stop_engine("STOP_ERROR", state, operation="place_stop", reason=reason, requested_stop=target_stop, response=last_resp)
        state.exchange_stop_status = "place_error"
        self._register_execution_risk(state.inst_id, f"stop-place-error:{state.exchange_stop_last_error_msg or state.exchange_stop_last_error_code or 'unknown'}", stage="stop_place", severity=2.0, quarantine=False)
        self._update_stop_tracking(state, False, reason="exchange_stop_place_error", hard=False)
        self.log_line.emit(f"[STOP] {state.inst_id}: ошибка установки биржевого стопа -> {last_resp}")
        return False

    def _sync_exchange_stop_if_needed(self, state: PositionState, current_price: float = 0.0, reason: str = "sync_check") -> None:
        if not bool(getattr(self.cfg, "exchange_protective_stop_enabled", True)):
            return
        now_ts = time.time()
        interval = max(5, int(getattr(self.cfg, "exchange_stop_sync_interval_sec", 30) or 30))
        last_sync = float(getattr(state, "exchange_stop_last_sync_ts", 0.0) or 0.0)
        if now_ts - last_sync < interval:
            return
        state.exchange_stop_last_sync_ts = now_ts
        target_stop = float(getattr(state, "stop_price", 0.0) or 0.0)
        if self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active"):
            return
        if str(getattr(state, "exchange_stop_status", "") or "") == "cancel_pending_confirmation":
            self._clear_exchange_stop_state(state, status="missing_after_cancel_timeout")
            self._log_stop_engine("STOP_MISSING", state, reason=reason, action="confirmed_missing_after_cancel_timeout", current_price=current_price)
            return
        self._log_stop_engine("STOP_MISSING", state, reason=reason, action="place_missing_stop", current_price=current_price)
        self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason="missing_stop_recovery")

    def _replace_exchange_stop_if_needed(self, state: PositionState, prev_stop_price: float, new_stop_price: float, current_price: float = 0.0, reason: str = "turtle_trailing_update") -> bool:
        if not bool(getattr(self.cfg, "exchange_protective_stop_enabled", True)):
            return False
        new_stop = float(new_stop_price or 0.0)
        prev_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
        if new_stop <= 0.0:
            return False
        if state.side == "long":
            improved = (new_stop > max(prev_exchange_stop, 0.0)) if prev_exchange_stop > 0.0 else True
        else:
            improved = (new_stop < prev_exchange_stop) if prev_exchange_stop > 0.0 else True
        threshold = self._exchange_stop_move_threshold(state, new_stop)
        if prev_exchange_stop > 0.0 and abs(new_stop - prev_exchange_stop) < threshold:
            self._log_stop_engine("STOP_MOVE_SKIPPED", state, reason="below_move_threshold", old_exchange_stop=prev_exchange_stop, requested_stop=new_stop, threshold=threshold, current_price=current_price)
            return False
        if not improved:
            self._log_stop_engine("STOP_MOVE_SKIPPED", state, reason="not_improvement", old_exchange_stop=prev_exchange_stop, requested_stop=new_stop, current_price=current_price)
            return False
        changed = self._amend_exchange_stop(state, new_stop, current_price=current_price, reason=reason) if prev_exchange_stop > 0.0 else self._place_exchange_stop(state, new_stop, reason=reason)
        if changed:
            self._log_stop_engine("STOP_MOVED", state, old_strategy_stop=prev_stop_price, old_exchange_stop=prev_exchange_stop, new_stop=new_stop, current_price=current_price, reason=reason)
            return True
        return False

    def manage_open_positions(self) -> None:
        position_state = getattr(self.bot, "position_state", {}) or {}
        close_retry_after = getattr(self.bot, "close_retry_after", {}) or {}
        self.stats_logger.log("positions_check_started", tracked_positions=len(position_state))
        for inst_id, state in list(position_state.items()):
            retry_after = close_retry_after.get(inst_id, 0.0)
            if retry_after and retry_after > time.time():
                continue
            try:
                self.update_and_maybe_exit_or_pyramid(state)
            except Exception as exc:
                self.log_line.emit(f"{inst_id}: ошибка управления позицией: {exc}")
                logging.warning("Manage failed for %s: %s", inst_id, exc)


    def _compute_turtle_exit_levels(self, candles: List[List[float]], exit_period: int) -> tuple[float, float]:
        exit_window = candles[-max(1, int(exit_period)):]
        return min(c[3] for c in exit_window), max(c[2] for c in exit_window)

    def _confirm_exchange_stop_absent(self, state: PositionState, attempts: int = 6, delay_sec: float = 0.25) -> bool:
        for _ in range(max(1, attempts)):
            row = self._find_existing_exchange_stop_row(state)
            if row is None:
                return True
            if delay_sec > 0:
                time.sleep(delay_sec)
        return self._find_existing_exchange_stop_row(state) is None

    def _confirm_exchange_stop_present(self, state: PositionState, target_stop: float, attempts: int = 6, delay_sec: float = 0.25) -> bool:
        for _ in range(max(1, attempts)):
            if self._sync_stop_from_exchange_snapshot(state, target_stop=target_stop, status="active"):
                current = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
                if current > 0.0 and abs(current - float(target_stop or 0.0)) <= max(self._exchange_stop_move_threshold(state, target_stop), 1e-12) and bool(getattr(state, "exchange_stop_full_position", False)):
                    return True
            if delay_sec > 0:
                time.sleep(delay_sec)
        return False

    def _latest_closed_candle_ts(self, candles: List[List[float]]) -> int:
        if not candles:
            return 0
        try:
            return int(float(candles[-1][0]))
        except Exception:
            return 0

    def _is_stop_strategy_candle_due(self, state: PositionState, candles: List[List[float]]) -> bool:
        latest_ts = self._latest_closed_candle_ts(candles)
        if latest_ts <= 0:
            return False
        last_ts = int(getattr(state, "stop_strategy_last_candle_ts", 0) or 0)
        return latest_ts > last_ts

    def _is_pyramid_strategy_candle_due(self, state: PositionState, candles: List[List[float]]) -> bool:
        latest_ts = self._latest_closed_candle_ts(candles)
        if latest_ts <= 0:
            return False
        last_ts = int(getattr(state, "pyramid_strategy_last_candle_ts", 0) or 0)
        return latest_ts > last_ts

    def _verify_initial_stop_if_needed(self, state: PositionState, current_price: float = 0.0) -> bool:
        if self._stop_management_disabled(state):
            return False
        if bool(getattr(state, "initial_stop_verified", False)):
            return False
        due_ts = float(getattr(state, "initial_stop_verify_due_ts", 0.0) or 0.0)
        if due_ts <= 0.0 or time.time() < due_ts:
            return False
        target_stop = self._safe_short_stop_target(state, float(getattr(state, "initial_stop_price", 0.0) or getattr(state, "stop_price", 0.0) or 0.0), current_price=current_price)
        attempts = max(3, int(getattr(self.cfg, "initial_stop_verify_attempts", 8) or 8))
        delay_sec = max(0.25, float(getattr(self.cfg, "initial_stop_verify_delay_between_attempts_sec", 0.4) or 0.4))
        if self._confirm_exchange_stop_present(state, target_stop, attempts=attempts, delay_sec=delay_sec):
            state.initial_stop_verified = True
            state.stop_health_confirm_count = max(1, int(getattr(state, "stop_health_confirm_count", 0) or 0))
            self._update_stop_tracking(state, True, reason="initial_stop_confirmed", verified=True)
            self._log_stop_engine("STOP_INIT_CONFIRMED", state, requested_stop=target_stop, current_price=current_price)
            return False
        if self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active_confirmed", force_rest=True):
            current_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            threshold = self._exchange_stop_move_threshold(state, target_stop)
            if current_exchange_stop > 0.0 and abs(current_exchange_stop - target_stop) > max(threshold, 1e-12):
                self._amend_exchange_stop(state, target_stop, current_price=current_price, reason="initial_stop_verify_align")
            state.initial_stop_verified = True
            state.stop_health_confirm_count = max(1, int(getattr(state, "stop_health_confirm_count", 0) or 0))
            self._update_stop_tracking(state, True, reason="initial_stop_recovered", verified=True)
            self._log_stop_engine("STOP_INIT_RECOVERED", state, requested_stop=target_stop, current_price=current_price, recovery="snapshot_attach")
            return False
        failures = int(getattr(state, "initial_stop_verify_failures", 0) or 0) + 1
        state.initial_stop_verify_failures = failures
        placed = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason="initial_stop_verify_recover")
        if placed and self._confirm_exchange_stop_present(state, target_stop, attempts=attempts, delay_sec=delay_sec):
            state.initial_stop_verified = True
            state.initial_stop_verify_failures = 0
            state.stop_health_confirm_count = max(1, int(getattr(state, "stop_health_confirm_count", 0) or 0))
            self._clear_exchange_stop_desync(state)
            self._update_stop_tracking(state, True, reason="initial_stop_recovered", verified=True)
            self._log_stop_engine("STOP_INIT_RECOVERED", state, requested_stop=target_stop, current_price=current_price)
            return False
        abort_failures = max(3, int(getattr(self.cfg, "initial_stop_abort_failures", 4) or 4))
        state.initial_stop_verify_due_ts = time.time() + max(6.0, delay_sec * 6.0)
        self._update_stop_tracking(state, False, reason="initial_stop_pending_retry", hard=False)
        if failures >= abort_failures:
            self._log_stop_engine("STOP_INIT_ABORT", state, requested_stop=target_stop, current_price=current_price, failures=failures)
            self.close_position(state, current_price or float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0), "Аварийное закрытие: биржевой стоп не подтверждён")
            return True
        self._log_stop_engine("STOP_INIT_RETRY_SCHEDULED", state, requested_stop=target_stop, current_price=current_price, retry_due_ts=state.initial_stop_verify_due_ts, failures=failures)
        return False

    def _run_stop_health_check(self, state: PositionState, current_price: float = 0.0) -> bool:
        if self._stop_management_disabled(state):
            return False
        now_ts = time.time()
        last_check = float(getattr(state, "stop_health_last_check_ts", 0.0) or 0.0)
        if getattr(state, "entry_recovery_until_ts", 0.0) and time.time() < float(getattr(state, "entry_recovery_until_ts", 0.0) or 0.0):
            return False
        if now_ts - last_check < 90.0:
            return False
        state.stop_health_last_check_ts = now_ts
        self._log_stop_engine("STOP_HEALTH_CHECK", state, current_price=current_price)
        target_stop = float(getattr(state, "stop_price", 0.0) or 0.0)
        if self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active_confirmed", force_rest=True):
            current_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            threshold = self._exchange_stop_move_threshold(state, target_stop if target_stop > 0.0 else current_exchange_stop)
            state.stop_health_missing_count = 0
            state.stop_health_confirm_count = int(getattr(state, "stop_health_confirm_count", 0) or 0) + 1
            if target_stop > 0.0 and current_exchange_stop > 0.0 and abs(current_exchange_stop - target_stop) > max(threshold, 1e-12):
                amended = self._amend_exchange_stop(state, target_stop, current_price=current_price, reason="health_align")
                if amended and self._confirm_exchange_stop_present(state, target_stop, attempts=4, delay_sec=0.25):
                    self._log_stop_engine("STOP_HEALTH_RESTORED", state, current_price=current_price)
                    return True
            self._update_stop_tracking(state, True, reason="stop_health_confirmed", verified=True)
            self._log_stop_engine("STOP_HEALTH_CONFIRMED", state, current_price=current_price, confirmations=state.stop_health_confirm_count)
            return False
        missing_count = int(getattr(state, "stop_health_missing_count", 0) or 0) + 1
        state.stop_health_missing_count = missing_count
        state.stop_health_confirm_count = 0
        self._log_stop_engine("STOP_HEALTH_MISSING", state, current_price=current_price, missing_count=missing_count)
        restored = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason="health_restore")
        if restored and self._confirm_exchange_stop_present(state, target_stop, attempts=6, delay_sec=0.25):
            state.stop_recovery_failures = 0
            state.stop_health_missing_count = 0
            state.stop_health_confirm_count = 1
            self._update_stop_tracking(state, True, reason="stop_health_restored", verified=True)
            self._log_stop_engine("STOP_HEALTH_RESTORED", state, current_price=current_price)
            return True
        missing_threshold = max(2, int(getattr(self.cfg, "stop_health_missing_confirmations", 3) or 3))
        if missing_count < missing_threshold:
            state.stop_state = "PENDING_RECHECK"
            state.pyramiding_block_reason = "exchange_stop_health_recheck"
            self._mark_position_health(state, "STOP_UNVERIFIED", "exchange_stop_health_recheck")
            self._log_stop_engine("STOP_HEALTH_SOFT_MISSING", state, current_price=current_price, missing_count=missing_count, threshold=missing_threshold)
            return False
        self._mark_exchange_stop_desync(state, "stop_health_restore_failed")
        self._update_stop_tracking(state, False, reason="stop_health_restore_failed", hard=False)
        self._log_stop_engine("STOP_HEALTH_ERROR", state, current_price=current_price, missing_count=missing_count)
        return False

    def _amend_exchange_stop(self, state: PositionState, target_stop: float, current_price: float = 0.0, reason: str = "") -> bool:
        target_stop = self._safe_exchange_stop_target(state, float(target_stop or 0.0), current_price=current_price)
        algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
        if target_stop <= 0.0:
            return False
        if self._should_skip_stop_update(state, target_stop, reason=reason or "exchange_stop_already_aligned"):
            return True
        if self._stop_action_locked(state, target_stop, "amend"):
            return True
        if not algo_id:
            if self._adopt_existing_exchange_stop(state, target_stop=float(getattr(state, "stop_price", 0.0) or target_stop), status="active", force_rest=True):
                algo_id = str(getattr(state, "exchange_stop_algo_id", "") or "").strip()
        if not algo_id:
            return self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "amend_missing_algo")
        if not self._market_allows_exchange_stop(state, target_stop, current_price=current_price):
            self._log_stop_engine("STOP_REJECTED", state, operation="amend_stop", reason="market_already_crossed_stop", requested_stop=target_stop, current_price=current_price)
            self._mark_local_protective_exit(state, reason="market_already_crossed_stop", current_price=current_price, requested_stop=target_stop, response={"code": "LOCAL", "msg": "market_already_crossed_stop"})
            return False
        attempts = max(1, int(getattr(self.cfg, "exchange_stop_retry_attempts", 2) or 2))
        delay = max(0.0, float(getattr(self.cfg, "exchange_stop_retry_delay_sec", 0.35) or 0.35))
        last_resp = None
        self._begin_stop_action(state, "amend", target_stop)
        for attempt in range(1, attempts + 1):
            try:
                resp = self.gateway.amend_exchange_stop(state.inst_id, algo_id, target_stop, str(getattr(state, "exchange_stop_trigger_type", "mark") or "mark"), position_side=str(getattr(state, "side", "") or ""))
            except Exception as exc:
                resp = {"code": "1", "msg": str(exc), "data": []}
            last_resp = resp
            if str(resp.get("code", "")) == "0":
                state.exchange_stop_price = target_stop
                state.exchange_stop_qty = float(getattr(state, "qty", 0.0) or 0.0)
                state.exchange_stop_full_position = True
                state.exchange_stop_last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state.exchange_stop_status = "active"
                state.exchange_stop_last_sync_ts = time.time()
                state.exchange_stop_last_error_code = ""
                state.exchange_stop_last_error_msg = ""
                state.exchange_stop_last_update_method = "amend"
                self._finish_stop_action(state, True, confirmed_stop=target_stop)
                self._update_stop_tracking(state, True, reason=reason or "exchange_stop_amended")
                self._log_stop_engine("STOP_AMENDED", state, requested_stop=target_stop, current_price=current_price, reason=reason, attempt=attempt)
                self.log_line.emit(f"[STOP] {state.inst_id}: биржевой стоп изменён {target_stop:.6f} ({reason or 'n/a'})")
                return True
            data = list((resp or {}).get("data", []) or [])
            fail_code = str((data[0].get("sCode") if data else "") or resp.get("code", "") or "")
            fail_msg = str((data[0].get("sMsg") if data else "") or resp.get("msg", "") or "")
            lower_msg = fail_msg.lower()
            state.exchange_stop_last_error_code = fail_code
            state.exchange_stop_last_error_msg = fail_msg
            if fail_code == "51003" or "client order id or order id is required" in lower_msg:
                relinked = self._adopt_existing_exchange_stop(state, target_stop=target_stop, status="active_relinked", force_rest=True)
                self._finish_stop_action(state, False)
                if relinked:
                    self._log_stop_engine("STOP_AMEND_RELINKED", state, requested_stop=target_stop, current_price=current_price, reason=reason, response=resp)
                    if not bool(getattr(state, "exchange_stop_full_position", False)):
                        self._log_stop_engine("STOP_PARTIAL_COVERAGE_FAULT", state, reason=reason or "amend_relinked_partial", requested_stop=target_stop, exchange_stop_qty=float(getattr(state, "exchange_stop_qty", 0.0) or 0.0), position_qty=float(getattr(state, "qty", 0.0) or 0.0), response=resp)
                    replaced = self._force_replace_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "amend_relinked_force_replace")
                    if replaced:
                        self._clear_exchange_stop_desync(state)
                        return True
                    self._mark_exchange_stop_desync(state, f"amend_relinked_replace_failed:{reason or 'unknown'}")
                    return False
                self._clear_exchange_stop_state(state, status="missing_algo_id")
                self._log_stop_engine("STOP_AMEND_ABORTED", state, requested_stop=target_stop, current_price=current_price, reason=reason or "missing_algo_id", response=resp)
                return False
            if fail_code == "51023" or "position doesn't exist" in lower_msg:
                self._log_stop_engine("STOP_MISSING", state, operation="amend_stop", reason=reason or "position_absent", requested_stop=target_stop, current_price=current_price, response=resp)
                self._finish_stop_action(state, False)
                return self._sync_absent_position_once(state, current_price=current_price, reason="position_absent_on_exchange")
            if fail_code == "51400" or "does not exist" in lower_msg or "filled" in lower_msg or "canceled" in lower_msg:
                self._clear_exchange_stop_state(state, status="missing_before_amend")
                self._finish_stop_action(state, False)
                return self._place_exchange_stop(state, target_stop, reason=reason or "amend_missing_replace")
            if fail_code == "51302" and str(getattr(state, "side", "") or "").lower() == "short":
                target_stop = self._safe_short_stop_target(state, target_stop, current_price=current_price)
            if attempt < attempts and delay > 0:
                time.sleep(delay)
        self._log_stop_engine("STOP_ERROR", state, operation="amend_stop", reason=reason, requested_stop=target_stop, current_price=current_price, response=last_resp)
        state.exchange_stop_status = "amend_error"
        self._clear_exchange_stop_state(state, status="amend_fallback_replace")
        self._finish_stop_action(state, False)
        replaced = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=f"amend_fallback:{reason}")
        if replaced:
            self._log_stop_engine("STOP_AMEND_FALLBACK_REPLACED", state, requested_stop=target_stop, current_price=current_price, reason=reason)
            self._clear_exchange_stop_desync(state)
            return True
        self._mark_exchange_stop_desync(state, f"amend_failed:{reason}")
        return False

    def _desired_stop_mode(self, state: PositionState) -> str:
        active_mode = str(getattr(state, "active_stop_mode", "BOOTSTRAP") or "BOOTSTRAP").upper()
        confirmations_needed = max(1, int(getattr(self.cfg, "stop_health_confirmations_for_atr_switch", 2) or 2))
        if active_mode == "BOOTSTRAP":
            if not bool(getattr(state, "initial_stop_verified", False)):
                return "BOOTSTRAP"
            if int(getattr(state, "stop_health_confirm_count", 0) or 0) < confirmations_needed:
                return "BOOTSTRAP"
            return "ATR"
        if active_mode == "ATR":
            return "TURTLE" if int(getattr(state, "units", 1) or 1) >= 3 else "ATR"
        if active_mode == "TURTLE":
            return "TURTLE"
        return "TURTLE" if int(getattr(state, "units", 1) or 1) >= 3 else "ATR"

    def _bootstrap_stop_target(self, state: PositionState) -> float:
        return float(getattr(state, "bootstrap_stop_price", 0.0) or getattr(state, "initial_stop_price", 0.0) or getattr(state, "stop_price", 0.0) or 0.0)

    def _atr_stop_target(self, state: PositionState, current_price: float, candles: Optional[List[List[float]]] = None) -> float:
        return self.trailing_stop(state, state.atr, current_price, candles=candles)

    def _turtle_stop_target(self, state: PositionState, candles: List[List[float]]) -> float:
        exit_long_level, exit_short_level = self._compute_turtle_exit_levels(candles, state.exit_period)
        return exit_long_level if state.side == "long" else exit_short_level
    def _can_switch_to_turtle(self, state: PositionState, turtle_stop: float) -> bool:
        turtle_stop = float(turtle_stop or 0.0)
        if turtle_stop <= 0.0:
            return False
        current_stop = float(getattr(state, "exchange_stop_price", 0.0) or getattr(state, "stop_price", 0.0) or 0.0)
        if current_stop <= 0.0:
            return True
        if str(getattr(state, "side", "") or "").lower() == "long":
            return turtle_stop >= current_stop
        return turtle_stop <= current_stop

    def _select_protective_stop(self, state: PositionState, *values: float) -> float:
        candidates = [float(v or 0.0) for v in values if float(v or 0.0) > 0.0]
        if not candidates:
            return 0.0
        if str(getattr(state, "side", "") or "").lower() == "long":
            return max(candidates)
        return min(candidates)

    def _is_stop_regression(self, state: PositionState, candidate_stop: float, reference_stop: float) -> bool:
        candidate_stop = float(candidate_stop or 0.0)
        reference_stop = float(reference_stop or 0.0)
        if candidate_stop <= 0.0 or reference_stop <= 0.0:
            return False
        if str(getattr(state, "side", "") or "").lower() == "long":
            return candidate_stop < reference_stop
        return candidate_stop > reference_stop

    def _stop_reconcile_required(self, state: PositionState, current_price: float = 0.0, candles: Optional[List[List[float]]] = None) -> bool:
        desired_mode = self._desired_stop_mode(state)
        active_mode = str(getattr(state, "active_stop_mode", desired_mode) or desired_mode).upper()
        state.desired_stop_mode = desired_mode
        if bool(getattr(state, "exchange_stop_desync", False)):
            return True
        if desired_mode == "BOOTSTRAP":
            target_stop = self._bootstrap_stop_target(state)
            if active_mode != "BOOTSTRAP":
                return True
        elif desired_mode == "TURTLE" and active_mode == "ATR" and candles:
            turtle_stop = self._turtle_stop_target(state, candles)
            if not self._can_switch_to_turtle(state, turtle_stop):
                active_mode = "ATR"
            else:
                return True
        elif active_mode != desired_mode:
            return True
        if float(getattr(state, "qty", 0.0) or 0.0) > 0.0:
            if not str(getattr(state, "exchange_stop_algo_id", "") or "").strip():
                return True
            if not bool(getattr(state, "exchange_stop_full_position", False)):
                return True
            if float(getattr(state, "exchange_stop_price", 0.0) or 0.0) <= 0.0:
                return True
        return False
    def _run_stop_recovery(self, state: PositionState, current_price: float, candles: List[List[float]], reason: str = "runtime_reconcile") -> bool:
        if self._stop_management_disabled(state):
            return False
        desired_mode = self._desired_stop_mode(state)
        active_mode = str(getattr(state, "active_stop_mode", desired_mode) or desired_mode).upper()
        state.desired_stop_mode = desired_mode
        bootstrap_stop = self._bootstrap_stop_target(state)
        atr_stop = self._atr_stop_target(state, current_price, candles=candles)
        turtle_stop = self._turtle_stop_target(state, candles)
        if desired_mode == "BOOTSTRAP":
            target_mode = "BOOTSTRAP"
            target_stop = float(bootstrap_stop or 0.0)
        elif desired_mode == "TURTLE" and active_mode != "TURTLE" and not self._can_switch_to_turtle(state, turtle_stop):
            target_mode = "ATR"
            target_stop = float(atr_stop or 0.0)
        else:
            target_mode = desired_mode if desired_mode != "TURTLE" or active_mode == "TURTLE" or self._can_switch_to_turtle(state, turtle_stop) else "ATR"
            target_stop = float((turtle_stop if target_mode == "TURTLE" else atr_stop) or 0.0)
        if target_stop <= 0.0:
            return False
        protective_stop = self._select_protective_stop(state, getattr(state, "exchange_stop_price", 0.0), getattr(state, "stop_price", 0.0))
        if self._is_stop_regression(state, target_stop, protective_stop):
            self._log_stop_engine("STOP_REGRESSION_BLOCKED", state, desired_mode=desired_mode, active_mode=active_mode, target_mode=target_mode, requested_stop=target_stop, protected_stop=protective_stop, current_price=current_price, reason=reason)
            target_mode = active_mode or target_mode
            target_stop = protective_stop
        prev_attempts = int(getattr(state, "stop_recovery_attempts", 0) or 0)
        state.stop_recovery_attempts = prev_attempts + 1
        state.stop_recovery_last_reason = str(reason or "runtime_reconcile")
        state.stop_recovery_last_ts = time.time()
        self._log_stop_engine("STOP_RECOVERY_START", state, desired_mode=desired_mode, target_mode=target_mode, target_stop=target_stop, current_price=current_price, reason=reason, attempt=state.stop_recovery_attempts)
        ok = False
        existing_row = self._find_existing_exchange_stop_row(state, target_stop=target_stop)
        if self._exchange_stop_row_is_valid(state, existing_row, target_stop=target_stop, require_full_cover=True):
            self._attach_existing_exchange_stop(state, existing_row, status="recovered")
            state.stop_price = target_stop
            state.active_stop_mode = target_mode
            ok = True
        else:
            ok = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=reason or "runtime_reconcile")
            if ok and self._confirm_exchange_stop_present(state, target_stop, attempts=6, delay_sec=0.25):
                state.stop_price = target_stop
                state.active_stop_mode = target_mode
        if ok:
            state.stop_recovery_attempts = 0
            self._clear_exchange_stop_desync(state)
            self._log_stop_engine("STOP_RECOVERY_OK", state, desired_mode=desired_mode, target_mode=target_mode, target_stop=target_stop, current_price=current_price, reason=reason)
            return True
        failure_count = int(getattr(state, "stop_recovery_failures", 0) or 0) + 1
        state.stop_recovery_failures = failure_count
        self._mark_exchange_stop_desync(state, f"recovery_failed:{reason}:{target_mode.lower()}")
        self._log_stop_engine("STOP_RECOVERY_FAILED", state, desired_mode=desired_mode, target_mode=target_mode, target_stop=target_stop, current_price=current_price, reason=reason, failures=failure_count)
        if failure_count >= 3:
            self._log_stop_engine("STOP_RECOVERY_CRITICAL", state, desired_mode=desired_mode, target_mode=target_mode, target_stop=target_stop, current_price=current_price, reason=reason, failures=failure_count)
        return False
    def _apply_stop_policy(self, state: PositionState, current_price: float, candles: List[List[float]], reason: str = "manage") -> None:
        if self._stop_management_disabled(state):
            return
        desired_mode = self._desired_stop_mode(state)
        state.desired_stop_mode = desired_mode
        bootstrap_stop = float(self._bootstrap_stop_target(state) or 0.0)
        atr_stop = float(self._atr_stop_target(state, current_price, candles=candles) or 0.0)
        turtle_stop = float(self._turtle_stop_target(state, candles) or 0.0)
        active_mode = str(getattr(state, "active_stop_mode", "BOOTSTRAP") or "BOOTSTRAP").upper()

        if active_mode == "TURTLE":
            target_mode = "TURTLE"
            target_stop = turtle_stop
        elif active_mode == "BOOTSTRAP" and desired_mode == "BOOTSTRAP":
            target_mode = "BOOTSTRAP"
            target_stop = bootstrap_stop
        elif desired_mode == "BOOTSTRAP":
            target_mode = "BOOTSTRAP"
            target_stop = bootstrap_stop
        elif desired_mode == "TURTLE":
            if self._can_switch_to_turtle(state, turtle_stop):
                target_mode = "TURTLE"
                target_stop = turtle_stop
            else:
                target_mode = "ATR"
                target_stop = atr_stop
                self._log_stop_engine("STOP_MODE_BRIDGE", state, desired_mode=desired_mode, active_mode=active_mode, bridge_mode=target_mode, atr_stop=atr_stop, turtle_stop=turtle_stop, current_price=current_price, reason=reason)
        else:
            target_mode = "ATR"
            target_stop = atr_stop

        target_stop = float(target_stop or 0.0)
        if target_stop <= 0.0:
            return

        prev_stop = float(getattr(state, "stop_price", 0.0) or 0.0)
        prev_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
        protective_stop = self._select_protective_stop(state, prev_exchange_stop, prev_stop)
        if self._is_stop_regression(state, target_stop, protective_stop):
            self._log_stop_engine("STOP_REGRESSION_BLOCKED", state, desired_mode=desired_mode, active_mode=active_mode, target_mode=target_mode, requested_stop=target_stop, protected_stop=protective_stop, current_price=current_price, reason=reason)
            target_mode = active_mode or target_mode
            target_stop = protective_stop
        threshold = max(float(getattr(state, "atr", 0.0) or 0.0) * 0.10, abs(float(current_price or 0.0)) * 0.0001, 1e-12)
        needs_cover_replace = prev_exchange_stop > 0.0 and not bool(getattr(state, "exchange_stop_full_position", False))

        if active_mode != target_mode:
            old_mode = active_mode
            old_stop = prev_exchange_stop or prev_stop or 0.0
            moved = False
            existing_row = self._find_existing_exchange_stop_row(state, target_stop=target_stop)
            existing_valid = self._exchange_stop_row_is_valid(state, existing_row, target_stop=target_stop, require_full_cover=True)
            if existing_valid and not needs_cover_replace:
                moved = self._attach_existing_exchange_stop(state, existing_row, status="active")
            elif needs_cover_replace:
                moved = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=f"switch_to_{target_mode.lower()}_full_cover")
            elif prev_exchange_stop > 0.0:
                if abs(target_stop - prev_exchange_stop) >= threshold:
                    moved = self._replace_exchange_stop_if_needed(state, prev_stop, target_stop, current_price=current_price, reason=f"switch_to_{target_mode.lower()}")
                else:
                    moved = self._sync_stop_from_exchange_snapshot(state, target_stop=target_stop, status="active")
                    if not moved:
                        moved = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=f"switch_to_{target_mode.lower()}_refresh")
            else:
                moved = self._place_exchange_stop(state, target_stop, reason=f"switch_to_{target_mode.lower()}")
            if moved or self._confirm_exchange_stop_present(state, target_stop, attempts=4, delay_sec=0.25):
                state.stop_price = target_stop
                state.active_stop_mode = target_mode
                state.stop_mode_since_ts = time.time()
                state.stop_transition_reason = str(reason or f"switch_to_{target_mode.lower()}")
                state.stop_recovery_failures = 0
                self._clear_exchange_stop_desync(state)
                self._log_stop_engine("STOP_MODE_SWITCHED", state, old_mode=old_mode, new_mode=target_mode, desired_mode=desired_mode, old_stop=old_stop, new_stop=target_stop, reason=reason, moved=moved)
                self.position_journal_logger.log("STOP_MODE_SWITCH", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=current_price, prev_stop_price=old_stop, stop_price=target_stop, qty=state.qty, units=state.units, note=f"{old_mode} -> {target_mode}")
                if target_mode == "ATR" and not getattr(state, "trailing_activated_at", ""):
                    state.trailing_activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                self._mark_exchange_stop_desync(state, f"mode_switch_failed:{target_mode.lower()}")
                self._log_stop_engine("STOP_MODE_SWITCH_SKIPPED", state, old_mode=old_mode, new_mode=target_mode, desired_mode=desired_mode, old_stop=old_stop, requested_stop=target_stop, reason=reason)
            return

        if needs_cover_replace:
            moved = self._ensure_exchange_stop(state, target_stop, current_price=current_price, reason=f"{target_mode.lower()}_full_cover")
            if moved:
                state.stop_price = target_stop
                self._clear_exchange_stop_desync(state)
                return
            self._mark_exchange_stop_desync(state, f"full_cover_replace_failed:{target_mode.lower()}")
        elif abs(target_stop - prev_stop) >= threshold:
            moved = self._replace_exchange_stop_if_needed(state, prev_stop, target_stop, current_price=current_price, reason=f"{target_mode.lower()}_update")
            if moved:
                state.stop_price = target_stop
                self._clear_exchange_stop_desync(state)
                if target_mode == "ATR" and not getattr(state, "trailing_activated_at", ""):
                    state.trailing_activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.position_journal_logger.log("TRAIL_UPDATE", trade_id=getattr(state, "trade_id", ""), inst_id=state.inst_id, side=state.side, price=current_price, prev_stop_price=prev_stop, stop_price=state.stop_price, qty=state.qty, units=state.units, unrealized_pnl=state.unrealized_pnl, peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0), note=f"{target_mode} stop update")
                return
            self._mark_exchange_stop_desync(state, f"stop_update_failed:{target_mode.lower()}")

        if self._stop_reconcile_required(state, current_price=current_price, candles=candles):
            recovered = self._run_stop_recovery(state, current_price=current_price, candles=candles, reason=f"{reason}_no_change_reconcile")
            if recovered:
                state.stop_recovery_failures = 0
                return
        self._log_stop_engine("STOP_STRATEGY_NO_CHANGE", state, desired_mode=desired_mode, active_mode=active_mode, target_mode=target_mode, requested_stop=target_stop, current_price=current_price, reason=reason)


    def _update_stop_tracking(self, state: PositionState, is_active: bool, reason: str = "", verified: bool = True, hard: bool = False) -> None:
        state.stop_attach_attempts = int(getattr(state, "stop_attach_attempts", 0) or 0) + 1
        if is_active:
            state.stop_state = "ACTIVE" if verified else "PENDING_RECHECK"
            state.stop_health_missing_count = 0
            if verified:
                state.stop_verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state.initial_stop_verified = True
                state.pyramiding_block_reason = ""
                self._mark_position_health(state, "HEALTHY")
            else:
                state.initial_stop_verified = False
                state.pyramiding_block_reason = reason or "exchange_stop_pending_verification"
                self._mark_position_health(state, "STOP_UNVERIFIED", reason or "exchange_stop_pending_verification")
            return
        state.initial_stop_verified = False
        state.stop_health_confirm_count = 0
        if hard:
            state.stop_state = "ERROR"
            state.pyramiding_block_reason = reason or "exchange_stop_not_active"
            self._mark_position_health(state, "STOP_UNVERIFIED", reason or "exchange_stop_not_active")
            return
        state.stop_state = "MISSING"
        state.pyramiding_block_reason = reason or "exchange_stop_recheck_required"
        self._mark_position_health(state, "STOP_UNVERIFIED", reason or "exchange_stop_recheck_required")

    def _confirm_exchange_stop_active(self, state: PositionState, timeout_sec: float = 0.0) -> bool:
        timeout_sec = float(timeout_sec or getattr(self.cfg, "stop_confirm_timeout_sec", 3.0) or 3.0)
        deadline = time.time() + max(0.5, timeout_sec)
        while time.time() < deadline:
            existing_row = self._find_existing_exchange_stop_row(state, target_stop=float(getattr(state, "stop_price", 0.0) or 0.0))
            if existing_row is not None:
                self._attach_existing_exchange_stop(state, existing_row, status="active_confirmed")
                return True
            if str(getattr(state, "exchange_stop_status", "") or "") == "active" and float(getattr(state, "exchange_stop_price", 0.0) or 0.0) > 0.0:
                return True
            time.sleep(0.25)
        return False

    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:

        if self._stop_management_disabled(state):
            return

        candles = list(getattr(state, "_cycle_candles", None) or [])
        if not candles:
            candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 5)
        if not candles:
            return

        ticker = self.gateway.get_ticker_data(state.inst_id)
        current_price = float(ticker.get("markPx") or ticker.get("last") or state.last_px or state.avg_px)
        state.last_px = current_price

        if self._verify_initial_stop_if_needed(state, current_price=current_price):
            return
        if bool(getattr(state, "local_protective_exit_pending", False)):
            reason = str(getattr(state, "local_protective_exit_reason", "exchange_stop_unavailable") or "exchange_stop_unavailable")
            self._log_stop_engine("STOP_EMERGENCY_CLOSE_EXECUTE", state, current_price=current_price, reason=reason)
            self.close_position(state, current_price, f"Аварийное закрытие: {reason}", candles=candles)
            return
        health_recovered = self._run_stop_health_check(state, current_price=current_price)
        if health_recovered:
            time.sleep(0.15)

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr > 0:
            state.atr = atr

        strategy_price = float(candles[-1][4]) if candles and len(candles[-1]) > 4 else current_price
        if self._stop_reconcile_required(state, current_price=strategy_price, candles=candles):
            recovered = self._run_stop_recovery(state, current_price=strategy_price, candles=candles, reason="manage_cycle_reconcile")
            if recovered:
                time.sleep(0.15)

        prev_peak_upl = float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0)
        self._update_position_extremes(state, current_price)
        latest_closed_ts = self._latest_closed_candle_ts(candles)
        stop_strategy_candle_due = self._is_stop_strategy_candle_due(state, candles)
        pyramid_strategy_candle_due = self._is_pyramid_strategy_candle_due(state, candles)
        if stop_strategy_candle_due:
            prev_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            self._log_stop_engine("STOP_STRATEGY_RECALC", state, current_price=current_price, strategy_price=strategy_price, candle_ts=latest_closed_ts)
            self._apply_stop_policy(state, strategy_price, candles, reason="closed_candle")
            state.stop_strategy_last_candle_ts = latest_closed_ts
            new_exchange_stop = float(getattr(state, "exchange_stop_price", 0.0) or 0.0)
            if new_exchange_stop > 0.0 and abs(new_exchange_stop - prev_exchange_stop) > 1e-12:
                time.sleep(0.25)

        if float(getattr(state, "peak_unrealized_pnl", 0.0) or 0.0) > prev_peak_upl + max(25.0, abs(prev_peak_upl) * 0.08):
            self.position_journal_logger.log(
                "PEAK_PNL",
                trade_id=getattr(state, "trade_id", ""),
                inst_id=state.inst_id,
                side=state.side,
                price=current_price,
                stop_price=state.stop_price,
                qty=state.qty,
                units=state.units,
                unrealized_pnl=state.unrealized_pnl,
                peak_unrealized_pnl=getattr(state, "peak_unrealized_pnl", 0.0),
                note="Новый пик open PnL",
            )

        exit_long_level, exit_short_level = self._compute_turtle_exit_levels(candles, state.exit_period)
        turtle_exit = (state.side == "long" and current_price <= exit_long_level) or (
            state.side == "short" and current_price >= exit_short_level
        )

        if turtle_exit and str(getattr(state, "active_stop_mode", "ATR") or "ATR").upper() == "TURTLE":
            self.close_position(state, current_price, f"Канальный выход {state.exit_period} свечей", candles=candles)
            return

        if pyramid_strategy_candle_due:
            self.try_pyramid(state, strategy_price, candles, candle_ts=latest_closed_ts)
            state.pyramid_strategy_last_candle_ts = latest_closed_ts
        self._save_state()
