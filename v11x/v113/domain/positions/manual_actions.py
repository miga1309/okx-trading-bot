from __future__ import annotations

import logging
import time
from typing import Any


class ManualActions:
    def __init__(self, bot: object, registry) -> None:
        self.bot = bot
        self.registry = registry
        self.log = logging.getLogger("engine.positions")

    def can_manual_add_units(self, inst_id: str) -> bool:
        state = self.registry.get(inst_id)
        return state is not None and int(getattr(state, "units", 0) or 0) >= 4

    def preview_manual_add_units(self, inst_id: str, extra_units: int = 1) -> dict[str, Any]:
        state = self.registry.get(inst_id)
        if state is None:
            raise KeyError(f"Position not found for {inst_id}")
        extra_units = max(1, int(extra_units or 1))
        current_units = int(getattr(state, "units", 0) or 0)
        if current_units < 4:
            raise ValueError("Manual add is available only after 4 units")
        base_unit_qty = float(getattr(state, "base_unit_qty", 0.0) or 0.0)
        current_qty = float(getattr(state, "qty", 0.0) or 0.0)
        add_qty = base_unit_qty * extra_units if base_unit_qty > 0 else 0.0
        projected_qty = current_qty + add_qty
        projected_units = current_units + extra_units
        last_px = float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        est_fill_px = last_px if last_px > 0 else avg_px
        projected_avg_px = avg_px
        if projected_qty > 0 and est_fill_px > 0:
            projected_avg_px = ((avg_px * current_qty) + (est_fill_px * add_qty)) / projected_qty if current_qty > 0 else est_fill_px
        upl = float(getattr(state, "unrealized_pnl", 0.0) or 0.0)
        margin = float(getattr(state, "margin", 0.0) or 0.0)
        pnl_pct = (upl / margin * 100.0) if margin > 0 else 0.0
        stop_price = float(getattr(state, "stop_price", 0.0) or 0.0)
        ct_val = 1.0
        try:
            info = self.bot.gateway.instrument_info(str(getattr(state, "inst_id", inst_id) or inst_id)) or {}
            ct_val = float(info.get("ctVal") or 1.0)
        except Exception:
            ct_val = 1.0
        payload = {
            "inst_id": str(getattr(state, "inst_id", inst_id) or inst_id),
            "side": str(getattr(state, "side", "") or ""),
            "current_units": current_units,
            "extra_units": extra_units,
            "projected_units": projected_units,
            "base_unit_qty": base_unit_qty,
            "current_qty": current_qty,
            "add_qty": add_qty,
            "projected_qty": projected_qty,
            "avg_px": avg_px,
            "estimated_fill_px": est_fill_px,
            "projected_avg_px": projected_avg_px,
            "last_px": last_px,
            "unrealized_pnl": upl,
            "pnl_pct": pnl_pct,
            "next_pyramid_price": float(getattr(state, "next_pyramid_price", 0.0) or 0.0),
            "stop_price": stop_price,
            "current_notional_usdt": current_qty * est_fill_px * ct_val,
            "projected_notional_usdt": projected_qty * est_fill_px * ct_val,
            "active_stop_mode": str(getattr(state, "active_stop_mode", "") or ""),
        }
        self.log.info("manual_add_preview=%s", payload, extra={"engine": "positions"})
        return payload

    def execute_manual_add_units(self, inst_id: str, extra_units: int = 1) -> dict[str, Any]:
        state = self.registry.get(inst_id)
        if state is None:
            raise KeyError(f"Position not found for {inst_id}")
        extra_units = max(1, int(extra_units or 1))
        if int(getattr(state, "units", 0) or 0) < 4:
            raise ValueError("Manual add is available only after 4 units")
        base_unit_qty = float(getattr(state, "base_unit_qty", 0.0) or 0.0)
        add_qty = base_unit_qty * extra_units
        if add_qty <= 0:
            raise ValueError("base_unit_qty is invalid for manual add")
        order_side = "buy" if str(getattr(state, "side", "") or "") == "long" else "sell"
        last_px = float(getattr(state, "last_px", 0.0) or getattr(state, "avg_px", 0.0) or 0.0)
        resp = self.bot.gateway.place_market_order(str(getattr(state, "inst_id", inst_id) or inst_id), order_side, add_qty)
        if str((resp or {}).get("code", "")) != "0":
            self.log.warning("manual_add_rejected inst_id=%s response=%s", inst_id, resp, extra={"engine": "positions"})
            return {"ok": False, "response": resp}
        fill_price, live_qty = self.bot._reconcile_live_fill(state.inst_id, state.side, last_px, float(getattr(state, "qty", 0.0) or 0.0) + add_qty)
        old_qty = float(getattr(state, "qty", 0.0) or 0.0)
        new_qty = float(live_qty if live_qty > 0 else (old_qty + add_qty))
        if new_qty <= 0:
            return {"ok": False, "response": resp, "reason": "new_qty_non_positive"}
        avg_px = float(getattr(state, "avg_px", 0.0) or 0.0)
        fill_price = float(fill_price or last_px or avg_px or 0.0)
        if live_qty > 0 and fill_price > 0:
            state.avg_px = fill_price
            state.last_px = fill_price
        else:
            state.avg_px = ((avg_px * old_qty) + (fill_price * add_qty)) / new_qty if new_qty > 0 else avg_px
            state.last_px = fill_price
        prev_stop_cover_qty = float(getattr(state, "exchange_stop_qty", 0.0) or 0.0)
        state.qty = new_qty
        state.units = int(getattr(state, "units", 0) or 0) + extra_units
        if prev_stop_cover_qty > 0.0:
            state.exchange_stop_full_position = False
            state.exchange_stop_status = "partial_coverage_fault"
        state.actual_entry_px = float(getattr(state, "avg_px", fill_price) or fill_price)
        state.next_pyramid_price = fill_price + self.bot.cfg.add_unit_every_atr * state.atr if state.side == "long" else fill_price - self.bot.cfg.add_unit_every_atr * state.atr
        try:
            info = self.bot.gateway.instrument_info(state.inst_id) or {}
            ct_val = float(info.get("ctVal") or 1.0)
        except Exception:
            ct_val = 1.0
        state.position_notional_usdt = float(getattr(state, "position_notional_usdt", 0.0) or 0.0) + fill_price * add_qty * ct_val
        self.bot.position_journal_logger.log("MANUAL_ADD_UNIT", trade_id=str(getattr(state, "trade_id", "") or ""), inst_id=state.inst_id, side=state.side, price=fill_price, stop_price=state.stop_price, qty=state.qty, add_qty=add_qty, units=state.units, atr=state.atr, next_pyramid_price=state.next_pyramid_price, note="Ручной добор сверх 4 юнитов")
        self.bot.stats_logger.log("manual_add_unit", trade_id=str(getattr(state, "trade_id", "") or ""), inst_id=state.inst_id, side=state.side, qty=state.qty, add_qty=add_qty, price=fill_price, stop_price=state.stop_price, units=state.units)
        self.bot.trade_logger.log("ADD", state.inst_id, state.side, add_qty, fill_price, state.atr, state.stop_price, state.system_name, f"Ручной добор до {state.units} юнитов")
        self.bot._update_position_extremes(state, fill_price)
        candles = self.bot.gateway.get_candles(state.inst_id, self.bot.cfg.timeframe, max(state.exit_period, self.bot.cfg.atr_period) + 5) or []
        strategy_price = float(candles[-1][4]) if candles and len(candles[-1]) > 4 else fill_price
        self.bot._apply_stop_policy(state, strategy_price, candles, reason="manual_add_unit")
        time.sleep(0.5)
        self.bot._save_state()
        self.bot._emit_snapshot_safe()
        self.bot.log_line.emit(f"{state.inst_id}: вручную добавлен юнит, now units={state.units}, qty+={add_qty}, stop={state.stop_price:.6f}")
        self.log.info("manual_add_executed inst_id=%s add_qty=%s units=%s", state.inst_id, add_qty, state.units, extra={"engine": "positions"})
        return {"ok": True, "response": resp, "fill_price": fill_price, "add_qty": add_qty, "units": state.units}
