# patch_v022_fix_pnl_okx.py
# Патч для текущего main_v022.py
#
# Исправляет:
# 1) open PnL % -> upl / margin * 100
# 2) mark price вместо ticker last для обновления last_px
# 3) closed PnL с учетом ctVal
# 4) closed PnL % как pnl / estimated_margin * 100
#
# Использование:
#   python patch_v022_fix_pnl_okx.py

from pathlib import Path
import shutil
import sys

TARGET_FILE = Path("main_v022.py")
BACKUP_FILE = Path("main_v022.py.bak_fix_pnl_okx")


def fail(msg: str) -> None:
    print(f"ОШИБКА: {msg}")
    sys.exit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET_FILE.exists():
        fail(f"Файл не найден: {TARGET_FILE.resolve()}")

    text = TARGET_FILE.read_text(encoding="utf-8")

    old_update_block = '''
    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:
        candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 5)
        if not candles:
            return
        current_price = self.gateway.get_ticker_last(state.inst_id)
        state.last_px = current_price
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
'''.strip("\n")

    new_update_block = '''
    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:
        candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 5)
        if not candles:
            return
        ticker = self.gateway.get_ticker_data(state.inst_id)
        current_price = float(ticker.get("markPx") or ticker.get("last") or state.last_px or state.avg_px)
        state.last_px = current_price
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
'''.strip("\n")

    old_close_block = '''
    def close_position(self, state: PositionState, price: float, reason: str) -> None:
        resp = self.gateway.close_position(state.inst_id, reason)
        if resp.get("code") != "0":
            code, message = self._extract_order_error(resp)
            safe_message = (message or resp.get("msg") or str(resp)).strip()
            if code in OkxGateway.CLOSE_MARKET_LIMIT_ERROR_CODES:
                fallback = self.gateway.close_position_by_reduce_only(state.inst_id, state.side, state.qty)
                if fallback.get("code") == "0":
                    self.log_line.emit(f"{state.inst_id}: позиция закрыта reduce-only ордерами из-за лимита market close")
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    self.log_line.emit(f"{state.inst_id}: ошибка закрытия reduce-only: {fallback}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\\n\\n"
                        f"Инструмент: {state.inst_id}\\n"
                        f"Причина: {safe_message}\\n"
                        f"Fallback: {fallback}"
                    )
                    return
            else:
                self.close_retry_after[state.inst_id] = time.time() + 60
                self.log_line.emit(f"{state.inst_id}: ошибка закрытия: {resp}")
                self._notify(
                    f"⚠️ Ошибка закрытия позиции\\n\\n"
                    f"Инструмент: {state.inst_id}\\n"
                    f"Причина: {safe_message}"
                )
                return
        pnl = (price - state.avg_px) * state.qty if state.side == "long" else (state.avg_px - price) * state.qty
        pnl_pct = ((price - state.avg_px) / state.avg_px * 100.0) if state.side == "long" else ((state.avg_px - price) / state.avg_px * 100.0)
        self.stats_logger.log("position_closed", inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason)
'''.strip("\n")

    new_close_block = '''
    def close_position(self, state: PositionState, price: float, reason: str) -> None:
        resp = self.gateway.close_position(state.inst_id, reason)
        if resp.get("code") != "0":
            code, message = self._extract_order_error(resp)
            safe_message = (message or resp.get("msg") or str(resp)).strip()
            if code in OkxGateway.CLOSE_MARKET_LIMIT_ERROR_CODES:
                fallback = self.gateway.close_position_by_reduce_only(state.inst_id, state.side, state.qty)
                if fallback.get("code") == "0":
                    self.log_line.emit(f"{state.inst_id}: позиция закрыта reduce-only ордерами из-за лимита market close")
                    self.close_retry_after.pop(state.inst_id, None)
                else:
                    self.close_retry_after[state.inst_id] = time.time() + 60
                    self.log_line.emit(f"{state.inst_id}: ошибка закрытия reduce-only: {fallback}")
                    self._notify(
                        f"⚠️ Ошибка закрытия позиции\\n\\n"
                        f"Инструмент: {state.inst_id}\\n"
                        f"Причина: {safe_message}\\n"
                        f"Fallback: {fallback}"
                    )
                    return
            else:
                self.close_retry_after[state.inst_id] = time.time() + 60
                self.log_line.emit(f"{state.inst_id}: ошибка закрытия: {resp}")
                self._notify(
                    f"⚠️ Ошибка закрытия позиции\\n\\n"
                    f"Инструмент: {state.inst_id}\\n"
                    f"Причина: {safe_message}"
                )
                return

        info = self.gateway.instrument_info(state.inst_id)
        ct_val = float(info.get("ctVal") or 1.0)

        pnl = ((price - state.avg_px) * state.qty * ct_val) if state.side == "long" else ((state.avg_px - price) * state.qty * ct_val)

        estimated_notional = max(state.avg_px * state.qty * ct_val, 0.0)
        estimated_margin = estimated_notional / max(float(self.cfg.leverage or 1), 1.0)
        if estimated_margin > 0:
            pnl_pct = (pnl / estimated_margin) * 100.0
        else:
            pnl_pct = 0.0

        self.stats_logger.log("position_closed", inst_id=state.inst_id, side=state.side, qty=state.qty, entry_price=state.avg_px, exit_price=price, atr=state.atr, stop_price=state.stop_price, units=state.units, reason=reason)
'''.strip("\n")

    old_emit_snapshot_block = '''
        open_positions = []
        for state in self.position_state.values():
            row = asdict(state)
            avg_px = float(state.avg_px or 0.0)
            last_px = float(state.last_px or 0.0)
            atr = float(state.atr or 0.0)
            if avg_px > 0:
                pnl_pct = ((last_px - avg_px) / avg_px * 100.0) if state.side == "long" else ((avg_px - last_px) / avg_px * 100.0)
                stop_distance_pct = ((last_px - state.stop_price) / last_px * 100.0) if state.side == "long" else ((state.stop_price - last_px) / last_px * 100.0)
                pyramid_distance_pct = ((state.next_pyramid_price - last_px) / last_px * 100.0) if state.side == "long" else ((last_px - state.next_pyramid_price) / last_px * 100.0)
                atr_pct = (atr / last_px * 100.0) if last_px > 0 else 0.0
            else:
                pnl_pct = 0.0
                stop_distance_pct = 0.0
                pyramid_distance_pct = 0.0
                atr_pct = 0.0
            row["pnl_pct"] = pnl_pct
            row["atr_pct"] = atr_pct
            row["stop_distance_pct"] = stop_distance_pct
            row["pyramid_distance_pct"] = pyramid_distance_pct
            row["trend_strength_atr"] = (abs(last_px - avg_px) / atr) if atr > 0 else 0.0
            row["added_units"] = max(0, int(state.units) - 1)
            open_positions.append(row)
'''.strip("\n")

    new_emit_snapshot_block = '''
        open_positions = []
        for state in self.position_state.values():
            row = asdict(state)
            avg_px = float(state.avg_px or 0.0)
            last_px = float(state.last_px or 0.0)
            atr = float(state.atr or 0.0)
            margin = float(state.margin or 0.0)
            upl = float(state.unrealized_pnl or 0.0)

            if margin > 0:
                pnl_pct = (upl / margin) * 100.0
            else:
                pnl_pct = 0.0

            if last_px > 0:
                stop_distance_pct = ((last_px - state.stop_price) / last_px * 100.0) if state.side == "long" else ((state.stop_price - last_px) / last_px * 100.0)
                pyramid_distance_pct = ((state.next_pyramid_price - last_px) / last_px * 100.0) if state.side == "long" else ((last_px - state.next_pyramid_price) / last_px * 100.0)
                atr_pct = (atr / last_px * 100.0) if atr > 0 else 0.0
            else:
                stop_distance_pct = 0.0
                pyramid_distance_pct = 0.0
                atr_pct = 0.0

            row["pnl_pct"] = pnl_pct
            row["atr_pct"] = atr_pct
            row["stop_distance_pct"] = stop_distance_pct
            row["pyramid_distance_pct"] = pyramid_distance_pct
            row["trend_strength_atr"] = (abs(last_px - avg_px) / atr) if atr > 0 else 0.0
            row["added_units"] = max(0, int(state.units) - 1)
            open_positions.append(row)
'''.strip("\n")

    text = replace_once(text, old_update_block, new_update_block, "update_and_maybe_exit_or_pyramid")
    text = replace_once(text, old_close_block, new_close_block, "close_position_pnl")
    text = replace_once(text, old_emit_snapshot_block, new_emit_snapshot_block, "emit_snapshot_open_positions")

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:  {BACKUP_FILE.resolve()}")
    print(f"Updated: {TARGET_FILE.resolve()}")


if __name__ == "__main__":
    main()