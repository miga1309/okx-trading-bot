import json
import logging
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from app_core import (
    BotConfig,
    ClosedTrade,
    PositionState,
    STATE_FILE,
    TIMEFRAME_TO_SECONDS,
    format_clock,
    TradeLogger,
    EngineStatsLogger,
    TRADE_CSV,
    ENGINE_STATS_FILE,
)
from exchange import OkxGateway

class TurtleEngine(QObject):
    snapshot = pyqtSignal(dict)
    log_line = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cfg: BotConfig):
        super().__init__()
        self.cfg = cfg
        self.gateway = OkxGateway(cfg)
        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)
        self.running = False
        self.lock = threading.Lock()
        self.position_state: Dict[str, PositionState] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.balance_history: List[dict] = []
        self._load_state()
        self.last_scan_started_at: Optional[float] = None
        self.last_scan_finished_at: Optional[float] = None
        self.last_positions_check_at: Optional[float] = None

    def _log(self, text: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
        logging.info(text)
        self.log_line.emit(line)

    def _emit_status(self, text: str) -> None:
        self.status.emit(text)

    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.closed_trades = [ClosedTrade(**x) for x in data.get("closed_trades", [])]
            self.balance_history = data.get("balance_history", [])
        except Exception as e:
            logging.warning("Failed to load state: %s", e)

    def _save_state(self) -> None:
        data = {
            "closed_trades": [asdict(x) for x in self.closed_trades[-2000:]],
            "balance_history": self.balance_history[-5000:],
        }
        try:
            STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logging.warning("Failed to save state: %s", e)

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        self.running = True
        self._log("Торговый движок запущен")
        last_scan = 0.0
        last_positions_check = 0.0
        last_balance_refresh = 0.0
        last_snapshot = 0.0

        while self.running:
            now = time.time()
            try:
                if now - last_positions_check >= max(1, self.cfg.position_check_interval_sec):
                    self.last_positions_check_at = now
                    self.sync_positions()
                    self.check_open_positions()
                    last_positions_check = now

                if now - last_scan >= max(1, self.cfg.scan_interval_sec):
                    self.last_scan_started_at = now
                    self.scan_for_entries()
                    self.last_scan_finished_at = time.time()
                    last_scan = now

                if now - last_balance_refresh >= max(1, self.cfg.balance_refresh_sec):
                    self.record_balance_point()
                    last_balance_refresh = now

                if now - last_snapshot >= max(1, self.cfg.snapshot_interval_sec):
                    self.emit_snapshot()
                    last_snapshot = now

            except Exception as e:
                logging.exception("Engine loop error")
                self.error.emit(str(e))
                self._log(f"Ошибка движка: {e}")

            time.sleep(0.2)

        self._log("Торговый движок остановлен")

    def emit_snapshot(self) -> None:
        try:
            used_margin = sum(p.margin for p in self.position_state.values())
            pnl = sum(p.unrealized_pnl for p in self.position_state.values())
            balance = self.gateway.get_balance()
            payload = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "open_positions": [asdict(p) for p in self.position_state.values()],
                "closed_trades": [asdict(x) for x in self.closed_trades[-300:]],
                "balance_history": self.balance_history[-1000:],
                "used_margin": used_margin,
                "unrealized_pnl": pnl,
                "available_balance": balance,
                "engine_running": self.running,
                "last_scan_started_at": format_clock(datetime.fromtimestamp(self.last_scan_started_at)) if self.last_scan_started_at else "--:--:--",
                "last_scan_finished_at": format_clock(datetime.fromtimestamp(self.last_scan_finished_at)) if self.last_scan_finished_at else "--:--:--",
                "last_positions_check_at": format_clock(datetime.fromtimestamp(self.last_positions_check_at)) if self.last_positions_check_at else "--:--:--",
            }
            self.snapshot.emit(payload)
        except Exception as e:
            self._log(f"Не удалось обновить snapshot: {e}")

    def record_balance_point(self) -> None:
        try:
            balance = self.gateway.get_balance()
            self.balance_history.append({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "balance": balance,
            })
            self.balance_history = self.balance_history[-5000:]
            self._save_state()
        except Exception as e:
            self._log(f"Не удалось записать баланс: {e}")

    def sync_positions(self) -> None:
        remote_positions = self.gateway.get_positions()
        current: Dict[str, PositionState] = {}
        for row in remote_positions:
            inst_id = row.get("instId", "")
            if not inst_id.endswith("-USDT-SWAP"):
                continue
            if is_hidden_instrument(inst_id):
                continue
            if inst_id in self.cfg.blacklist:
                continue
            pos = float(row.get("pos", 0) or 0)
            if pos == 0:
                continue
            side = "long" if row.get("posSide") == "long" else "short"
            avg_px = float(row.get("avgPx") or 0)
            last_px = self.gateway.get_ticker_last(inst_id)
            upl = float(row.get("upl") or 0)
            margin = float(row.get("margin") or 0)

            prev = self.position_state.get(inst_id)
            atr = prev.atr if prev else 0.0
            stop_price = prev.stop_price if prev else 0.0
            next_pyramid_price = prev.next_pyramid_price if prev else 0.0
            entry_time = prev.entry_time if prev else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            base_unit_qty = prev.base_unit_qty if prev else 0.0
            units = prev.units if prev else 1
            system_name = prev.system_name if prev else ""
            entry_period = prev.entry_period if prev else 0
            exit_period = prev.exit_period if prev else 0
            signal_time = prev.signal_time if prev else ""

            current[inst_id] = PositionState(
                inst_id=inst_id,
                side=side,
                qty=abs(pos),
                avg_px=avg_px,
                last_px=last_px,
                unrealized_pnl=upl,
                margin=margin,
                atr=atr,
                stop_price=stop_price,
                next_pyramid_price=next_pyramid_price,
                entry_time=entry_time,
                base_unit_qty=base_unit_qty,
                units=units,
                system_name=system_name,
                entry_period=entry_period,
                exit_period=exit_period,
                signal_time=signal_time,
            )

        gone = set(self.position_state.keys()) - set(current.keys())
        for inst_id in gone:
            prev = self.position_state.get(inst_id)
            if prev:
                self._log(f"{inst_id}: позиция исчезла из биржи, удаляю из локального состояния")

        self.position_state = current

    def calc_atr(self, candles: List[List[float]], period: int) -> float:
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            _, _, high, low, close, _ = candles[i]
            prev_close = candles[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        if len(trs) < period:
            return 0.0
        return sum(trs[-period:]) / period

    def get_channel_high(self, candles: List[List[float]], period: int) -> float:
        if len(candles) < period:
            return 0.0
        return max(c[2] for c in candles[-period:])

    def get_channel_low(self, candles: List[List[float]], period: int) -> float:
        if len(candles) < period:
            return 0.0
        return min(c[3] for c in candles[-period:])

    def get_last_close(self, candles: List[List[float]]) -> float:
        if not candles:
            return 0.0
        return candles[-1][4]

    def count_direction_flips(self, candles: List[List[float]]) -> float:
        if len(candles) < 3:
            return 1.0
        dirs: List[int] = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1][4]
            close = candles[i][4]
            if close > prev_close:
                dirs.append(1)
            elif close < prev_close:
                dirs.append(-1)
            else:
                dirs.append(0)
        effective = [d for d in dirs if d != 0]
        if len(effective) < 2:
            return 1.0
        flips = 0
        for i in range(1, len(effective)):
            if effective[i] != effective[i - 1]:
                flips += 1
        return flips / max(1, len(effective) - 1)

    def calc_efficiency_ratio(self, candles: List[List[float]]) -> float:
        if len(candles) < 2:
            return 0.0
        start = candles[0][4]
        end = candles[-1][4]
        net = abs(end - start)
        path = 0.0
        for i in range(1, len(candles)):
            path += abs(candles[i][4] - candles[i - 1][4])
        if path <= 0:
            return 0.0
        return net / path

    def calc_body_to_range_ratio(self, candles: List[List[float]]) -> float:
        if not candles:
            return 0.0
        values = []
        for row in candles:
            open_px = row[1]
            high = row[2]
            low = row[3]
            close = row[4]
            rng = max(1e-12, high - low)
            body = abs(close - open_px)
            values.append(body / rng)
        return sum(values) / len(values)

    def channel_range_pct(self, candles: List[List[float]]) -> float:
        if not candles:
            return 0.0
        high = max(c[2] for c in candles)
        low = min(c[3] for c in candles)
        if low <= 0:
            return 0.0
        return (high - low) / low * 100.0

    def atr_pct(self, atr: float, last_close: float) -> float:
        if last_close <= 0:
            return 0.0
        return atr / last_close * 100.0

    def passes_flat_filter(self, inst_id: str, candles: List[List[float]], atr: float) -> Tuple[bool, dict]:
        metrics = {
            "channel_range_pct": 0.0,
            "atr_pct": 0.0,
            "body_to_range_ratio": 0.0,
            "efficiency_ratio": 0.0,
            "direction_flip_ratio": 1.0,
        }
        if len(candles) < max(5, self.cfg.flat_lookback_candles):
            return True, metrics

        lookback = candles[-self.cfg.flat_lookback_candles :]
        last_close = self.get_last_close(lookback)
        metrics["channel_range_pct"] = self.channel_range_pct(lookback)
        metrics["atr_pct"] = self.atr_pct(atr, last_close)
        metrics["body_to_range_ratio"] = self.calc_body_to_range_ratio(lookback)
        metrics["efficiency_ratio"] = self.calc_efficiency_ratio(lookback)
        metrics["direction_flip_ratio"] = self.count_direction_flips(lookback)

        passed = (
            metrics["channel_range_pct"] >= self.cfg.min_channel_range_pct
            and metrics["atr_pct"] >= self.cfg.min_atr_pct
            and metrics["body_to_range_ratio"] >= self.cfg.min_body_to_range_ratio
            and metrics["efficiency_ratio"] >= self.cfg.min_efficiency_ratio
            and metrics["direction_flip_ratio"] <= self.cfg.max_direction_flip_ratio
        )

        if not passed:
            self.stats_logger.log(
                "flat_filter_block",
                inst_id=inst_id,
                timeframe=self.cfg.timeframe,
                metrics=metrics,
                thresholds={
                    "min_channel_range_pct": self.cfg.min_channel_range_pct,
                    "min_atr_pct": self.cfg.min_atr_pct,
                    "min_body_to_range_ratio": self.cfg.min_body_to_range_ratio,
                    "min_efficiency_ratio": self.cfg.min_efficiency_ratio,
                    "max_direction_flip_ratio": self.cfg.max_direction_flip_ratio,
                },
            )

        return passed, metrics

    def get_open_position_count(self) -> int:
        return len(self.position_state)

    def calc_position_notional(self, balance: float) -> float:
        return balance * (self.cfg.max_position_notional_pct / 100.0)

    def calc_risk_amount(self, balance: float) -> float:
        return balance * (self.cfg.risk_per_trade_pct / 100.0)

    def estimate_unit_qty(self, inst_id: str, last_price: float, atr: float, balance: float) -> float:
        if atr <= 0 or last_price <= 0 or balance <= 0:
            return 0.0

        contract_value = self.gateway.contract_value(inst_id)
        risk_amount = self.calc_risk_amount(balance)
        stop_distance = atr * self.cfg.atr_stop_multiple

        if contract_value <= 0 or stop_distance <= 0:
            return 0.0

        qty_by_risk = risk_amount / (stop_distance * contract_value)

        max_notional = self.calc_position_notional(balance)
        qty_by_notional = max_notional / (last_price * contract_value)

        qty = min(qty_by_risk, qty_by_notional)
        qty = self.gateway.round_qty_to_lot(inst_id, qty)
        min_qty = self.gateway.min_order_qty(inst_id)
        if qty < min_qty:
            return 0.0

        max_market = self.gateway.max_order_size_market(inst_id, self.cfg.td_mode)
        if max_market is not None and qty > max_market:
            qty = self.gateway.round_qty_to_lot(inst_id, max_market)

        if qty < min_qty:
            return 0.0
        return qty

    def open_position(
        self,
        inst_id: str,
        side: str,
        qty: float,
        atr: float,
        system_name: str,
        entry_period: int,
        exit_period: int,
        signal_time: str = "",
    ) -> None:
        side_api = "buy" if side == "long" else "sell"
        pos_side = side
        last_px = self.gateway.get_ticker_last(inst_id)

        self.gateway.set_leverage(inst_id, self.cfg.leverage, self.cfg.td_mode)
        resp = self.gateway.place_market_order(inst_id, side_api, pos_side, str(qty))
        if resp.get("code") != "0":
            self._log(f"{inst_id}: биржа отклонила ордер: {resp}")
            self.stats_logger.log("entry_rejected", inst_id=inst_id, side=side, qty=qty, response=resp)
            return

        avg_px = last_px
        stop_price = avg_px - atr * self.cfg.atr_stop_multiple if side == "long" else avg_px + atr * self.cfg.atr_stop_multiple
        next_pyramid_price = avg_px + atr * self.cfg.add_unit_every_atr if side == "long" else avg_px - atr * self.cfg.add_unit_every_atr

        ps = PositionState(
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=avg_px,
            last_px=last_px,
            unrealized_pnl=0.0,
            margin=0.0,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid_price,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            base_unit_qty=qty,
            units=1,
            system_name=system_name,
            entry_period=entry_period,
            exit_period=exit_period,
            signal_time=signal_time,
        )
        self.position_state[inst_id] = ps
        self.trade_logger.log("open", inst_id, side, qty, avg_px, atr, stop_price, system_name, f"{system_name}; signal={signal_time}")
        self.stats_logger.log(
            "entry_opened",
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=avg_px,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid_price,
            system_name=system_name,
            entry_period=entry_period,
            exit_period=exit_period,
            signal_time=signal_time,
        )
        self._log(f"Открыта {side} позиция {inst_id}, qty={qty:.8f}, ATR={atr:.6f}, stop={stop_price:.6f}")

    def maybe_add_pyramid(self, ps: PositionState) -> None:
        if self.cfg.max_units_per_symbol and ps.units >= self.cfg.max_units_per_symbol:
            return
        if ps.atr <= 0 or ps.qty <= 0:
            return
        if ps.base_unit_qty <= 0:
            return

        progress_atr = abs(ps.last_px - ps.avg_px) / max(1e-12, ps.atr)
        if progress_atr < self.cfg.pyramid_min_progress_atr:
            return

        if ps.side == "long":
            if ps.last_px < ps.next_pyramid_price:
                return
        else:
            if ps.last_px > ps.next_pyramid_price:
                return

        candles = self.gateway.get_candles(ps.inst_id, self.cfg.timeframe, max(self.cfg.atr_period + 2, 8))
        if len(candles) < max(self.cfg.atr_period, 2):
            return

        last_candle = candles[-1]
        open_px = last_candle[1]
        high_px = last_candle[2]
        low_px = last_candle[3]
        close_px = last_candle[4]
        candle_range = max(1e-12, high_px - low_px)
        body_ratio = abs(close_px - open_px) / candle_range
        if body_ratio < self.cfg.pyramid_min_body_ratio:
            return

        if ps.side == "long":
            dynamic_stop = max(ps.stop_price, ps.avg_px + ps.atr * self.cfg.pyramid_break_even_buffer_atr)
            stop_distance = ps.last_px - dynamic_stop
        else:
            dynamic_stop = min(ps.stop_price, ps.avg_px - ps.atr * self.cfg.pyramid_break_even_buffer_atr)
            stop_distance = dynamic_stop - ps.last_px

        if stop_distance < ps.atr * self.cfg.pyramid_min_stop_distance_atr:
            return

        unit_index = ps.units + 1
        scale_map = {
            2: self.cfg.pyramid_second_unit_scale,
            3: self.cfg.pyramid_third_unit_scale,
            4: self.cfg.pyramid_fourth_unit_scale,
        }
        scale = scale_map.get(unit_index, self.cfg.pyramid_fourth_unit_scale if unit_index > 4 else 1.0)
        add_qty = ps.base_unit_qty * max(0.0, scale)

        add_qty = self.gateway.round_qty_to_lot(ps.inst_id, add_qty)
        min_qty = self.gateway.min_order_qty(ps.inst_id)
        if add_qty < min_qty:
            return

        max_market = self.gateway.max_order_size_market(ps.inst_id, self.cfg.td_mode)
        if max_market is not None and add_qty > max_market:
            add_qty = self.gateway.round_qty_to_lot(ps.inst_id, max_market)
            if add_qty < min_qty:
                self._log(f"{ps.inst_id}: добор пропущен, лимит market size < min qty")
                self.stats_logger.log(
                    "pyramid_skipped_max_market_too_small",
                    inst_id=ps.inst_id,
                    side=ps.side,
                    requested_qty=ps.base_unit_qty * max(0.0, scale),
                    clipped_qty=add_qty,
                    min_qty=min_qty,
                    units=ps.units,
                )
                return

        side_api = "buy" if ps.side == "long" else "sell"
        resp = self.gateway.place_market_order(ps.inst_id, side_api, ps.side, str(add_qty))
        if resp.get("code") != "0":
            data = resp.get("data", [])
            code = str(data[0].get("sCode")) if data else ""
            if code in self.gateway.MAX_MARKET_SIZE_ERROR_CODES:
                self._log(f"{ps.inst_id}: биржа отклонила добор: {resp}")
                self.stats_logger.log(
                    "pyramid_rejected_max_market",
                    inst_id=ps.inst_id,
                    side=ps.side,
                    qty=add_qty,
                    response=resp,
                    units=ps.units,
                )
                return

            self._log(f"{ps.inst_id}: не удалось добрать позицию: {resp}")
            self.stats_logger.log(
                "pyramid_rejected",
                inst_id=ps.inst_id,
                side=ps.side,
                qty=add_qty,
                response=resp,
                units=ps.units,
            )
            return

        new_qty_total = ps.qty + add_qty
        ps.avg_px = ((ps.avg_px * ps.qty) + (ps.last_px * add_qty)) / max(1e-12, new_qty_total)
        ps.qty = new_qty_total
        ps.units += 1
        ps.stop_price = dynamic_stop
        ps.next_pyramid_price = ps.last_px + ps.atr * self.cfg.add_unit_every_atr if ps.side == "long" else ps.last_px - ps.atr * self.cfg.add_unit_every_atr

        self.trade_logger.log("pyramid", ps.inst_id, ps.side, add_qty, ps.last_px, ps.atr, ps.stop_price, ps.system_name, f"units={ps.units}")
        self.stats_logger.log(
            "pyramid_filled",
            inst_id=ps.inst_id,
            side=ps.side,
            qty=add_qty,
            total_qty=ps.qty,
            avg_px=ps.avg_px,
            stop_price=ps.stop_price,
            next_pyramid_price=ps.next_pyramid_price,
            units=ps.units,
            body_ratio=body_ratio,
            dynamic_stop=dynamic_stop,
        )
        self._log(f"{ps.inst_id}: добор {ps.side}, qty={add_qty:.8f}, всего={ps.qty:.8f}, units={ps.units}")

    def close_position(self, ps: PositionState, reason: str, note: str = "") -> None:
        resp = self.gateway.close_position(ps.inst_id, note)
        if resp.get("code") != "0":
            self._log(f"{ps.inst_id}: не удалось закрыть позицию: {resp}")
            self.stats_logger.log(
                "close_rejected",
                inst_id=ps.inst_id,
                side=ps.side,
                qty=ps.qty,
                reason=reason,
                response=resp,
            )
            return

        exit_px = self.gateway.get_ticker_last(ps.inst_id)
        pnl = (exit_px - ps.avg_px) * ps.qty if ps.side == "long" else (ps.avg_px - exit_px) * ps.qty
        pnl_pct = ((exit_px - ps.avg_px) / ps.avg_px * 100.0) if ps.side == "long" else ((ps.avg_px - exit_px) / ps.avg_px * 100.0)
        entry_dt = None
        try:
            entry_dt = datetime.strptime(ps.entry_time, "%Y-%m-%d %H:%M:%S")
        except Exception:
            entry_dt = None
        duration_sec = int((datetime.now() - entry_dt).total_seconds()) if entry_dt else 0

        ct = ClosedTrade(
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inst_id=ps.inst_id,
            side=ps.side,
            qty=ps.qty,
            entry_px=ps.avg_px,
            exit_px=exit_px,
            pnl=pnl,
            pnl_pct=pnl_pct,
            units=ps.units,
            system_name=ps.system_name,
            reason=reason,
            duration_sec=duration_sec,
        )
        self.closed_trades.append(ct)
        self.closed_trades = self.closed_trades[-2000:]

        self.trade_logger.log("close", ps.inst_id, ps.side, ps.qty, exit_px, ps.atr, ps.stop_price, ps.system_name, f"{reason}; {note}")
        self.stats_logger.log(
            "position_closed",
            inst_id=ps.inst_id,
            side=ps.side,
            qty=ps.qty,
            entry_px=ps.avg_px,
            exit_px=exit_px,
            pnl=pnl,
            pnl_pct=pnl_pct,
            units=ps.units,
            system_name=ps.system_name,
            reason=reason,
            note=note,
            duration_sec=duration_sec,
        )
        self._log(f"Закрыта {ps.side} позиция {ps.inst_id}, PnL={pnl:.4f} ({pnl_pct:.2f}%), причина: {reason}")
        self.position_state.pop(ps.inst_id, None)
        self._save_state()

    def check_open_positions(self) -> None:
        for inst_id, ps in list(self.position_state.items()):
            try:
                candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, max(self.cfg.long_exit_period, self.cfg.short_exit_period, self.cfg.atr_period) + 5)
                if not candles:
                    continue

                last_px = self.gateway.get_ticker_last(inst_id)
                ps.last_px = last_px

                if ps.side == "long":
                    if last_px <= ps.stop_price:
                        self.close_position(ps, "stop", "price <= stop")
                        continue

                    exit_low = self.get_channel_low(candles[:-1], ps.exit_period) if len(candles) > ps.exit_period else 0.0
                    if exit_low > 0 and last_px < exit_low:
                        self.close_position(ps, "channel_exit", f"price < {ps.exit_period}-low")
                        continue
                else:
                    if last_px >= ps.stop_price:
                        self.close_position(ps, "stop", "price >= stop")
                        continue

                    exit_high = self.get_channel_high(candles[:-1], ps.exit_period) if len(candles) > ps.exit_period else 0.0
                    if exit_high > 0 and last_px > exit_high:
                        self.close_position(ps, "channel_exit", f"price > {ps.exit_period}-high")
                        continue

                self.maybe_add_pyramid(ps)

            except Exception as e:
                self._log(f"{inst_id}: ошибка сопровождения позиции: {e}")
                self.stats_logger.log("position_check_error", inst_id=inst_id, error=str(e))

    def scan_for_entries(self) -> None:
        instruments = self.gateway.get_swap_instruments()
        balance = self.gateway.get_balance()
        open_count = self.get_open_position_count()

        self.stats_logger.log(
            "scan_started",
            timeframe=self.cfg.timeframe,
            instruments_total=len(instruments),
            balance=balance,
            open_positions=open_count,
        )

        for inst_id in instruments:
            if not self.running:
                break
            if inst_id in self.position_state:
                continue

            try:
                candles = self.gateway.get_candles(
                    inst_id,
                    self.cfg.timeframe,
                    max(
                        self.cfg.long_entry_period,
                        self.cfg.short_entry_period,
                        self.cfg.long_exit_period,
                        self.cfg.short_exit_period,
                        self.cfg.atr_period,
                        self.cfg.flat_lookback_candles,
                    ) + 5,
                )
                if not candles:
                    continue

                atr = self.calc_atr(candles, self.cfg.atr_period)
                if atr <= 0:
                    continue

                passed_flat, metrics = self.passes_flat_filter(inst_id, candles, atr)
                if not passed_flat:
                    self._log(
                        f"{inst_id}: пропуск по фильтру флэта "
                        f"(range={metrics['channel_range_pct']:.2f}%, atr={metrics['atr_pct']:.3f}%, "
                        f"body={metrics['body_to_range_ratio']:.2f}, eff={metrics['efficiency_ratio']:.2f}, "
                        f"flip={metrics['direction_flip_ratio']:.2f})"
                    )
                    continue

                last_close = self.get_last_close(candles)
                qty = self.estimate_unit_qty(inst_id, last_close, atr, balance)
                if qty <= 0:
                    self.stats_logger.log(
                        "entry_qty_zero",
                        inst_id=inst_id,
                        last_close=last_close,
                        atr=atr,
                        balance=balance,
                    )
                    continue

                prev_candles = candles[:-1]
                if len(prev_candles) < max(self.cfg.long_entry_period, self.cfg.short_entry_period):
                    continue

                long_breakout = self.get_channel_high(prev_candles, self.cfg.long_entry_period)
                short_breakout = self.get_channel_low(prev_candles, self.cfg.short_entry_period)

                if long_breakout > 0 and last_close > long_breakout:
                    self.open_position(
                        inst_id=inst_id,
                        side="long",
                        qty=qty,
                        atr=atr,
                        system_name="Turtle 55/20",
                        entry_period=self.cfg.long_entry_period,
                        exit_period=self.cfg.long_exit_period,
                        signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    continue

                if short_breakout > 0 and last_close < short_breakout:
                    self.open_position(
                        inst_id=inst_id,
                        side="short",
                        qty=qty,
                        atr=atr,
                        system_name="Turtle 20/10",
                        entry_period=self.cfg.short_entry_period,
                        exit_period=self.cfg.short_exit_period,
                        signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    continue

            except Exception as e:
                self._log(f"{inst_id}: ошибка анализа инструмента: {e}")
                self.stats_logger.log("scan_error", inst_id=inst_id, error=str(e))

        self.stats_logger.log(
            "scan_finished",
            timeframe=self.cfg.timeframe,
            instruments_total=len(instruments),
            open_positions=len(self.position_state),
            closed_trades=len(self.closed_trades),
        )