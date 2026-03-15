# patch_from_v024_4_to_v025.py
from pathlib import Path

SRC = Path("main_v024_4.py")
DST = Path("main_v025.py")


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, new_block: str, label: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        fail(f"Не найден start_marker для {label}: {start_marker}")
    end = text.find(end_marker, start)
    if end == -1:
        fail(f"Не найден end_marker для {label}: {end_marker}")
    return text[:start] + new_block + text[end:]


def main() -> None:
    if not SRC.exists():
        fail(f"Не найден исходный файл: {SRC}")

    text = SRC.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1) Header / version
    # ------------------------------------------------------------
    text = replace_once(
        text,
        'APP_VERSION = "v024_4"',
        'APP_VERSION = "v025"',
        "_app_version",
    )

    text = replace_once(
        text,
        "# Version: v024_4",
        "# Version: v025",
        "_header_version",
    )
    text = replace_once(
        text,
        "# Based on: main_v024_3.py",
        "# Based on: main_v024_4.py",
        "_header_based_on",
    )
    text = replace_once(
        text,
        "# Changelog:\n"
        "# - Removed flat-filter from entry logic\n"
        "# - Reduced breakout required_score to 2\n"
        "# - Added Turtle market regime indicator to analytics panel\n"
        '# - Redesigned chart into OKX-like "PnL за сегодня" style',
        "# Changelog:\n"
        "# - Fixed pyramiding: removed mandatory break-even lock for first add\n"
        "# - Fixed pyramiding: removed excessive profit-after-add filter\n"
        "# - Fixed entry priority: Turtle 55 now has priority over Turtle 20\n"
        "# - Fixed pyramid grid: next add level now advances from previous trigger",
        "_header_changelog",
    )

    # ------------------------------------------------------------
    # 2) Turtle 55 priority over Turtle 20
    # ------------------------------------------------------------
    text = replace_once(
        text,
        '        signals.sort(key=lambda s: (s["entry_period"], 0 if s["side"] == "long" else 1))',
        '        # v025: при одновременном сигнале приоритет у Turtle 55\n'
        '        signals.sort(key=lambda s: (-s["entry_period"], 0 if s["side"] == "long" else 1))',
        "_signals_sort",
    )

    # ------------------------------------------------------------
    # 3) Replace full _trend_confirms_pyramid function
    # ------------------------------------------------------------
    new_trend_confirms = '''    def _trend_confirms_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> tuple[bool, str]:
        if not candles:
            return False, "нет свечей для подтверждения"
        if state.atr <= 0:
            return False, "ATR недоступен"

        # v025:
        # Первый добор не блокируем обязательным переводом стопа в безубыток.
        progress = abs(last_close - state.avg_px)
        if progress < state.atr * self.cfg.pyramid_min_progress_atr:
            return False, f"недостаточный прогресс {progress / state.atr:.2f} ATR"

        distance_to_stop = abs(last_close - state.stop_price)
        if distance_to_stop < state.atr * self.cfg.pyramid_min_stop_distance_atr:
            return False, f"слишком близко к стопу {distance_to_stop / state.atr:.2f} ATR"

        is_flat, flat_reason = self.is_flat_market(candles, last_close, state.atr)
        if is_flat:
            return False, f"рынок выровнялся ({flat_reason})"

        last_candle = candles[-1]
        candle_range = max(last_candle[2] - last_candle[3], 1e-12)
        body_ratio = abs(last_candle[4] - last_candle[1]) / candle_range
        if body_ratio < self.cfg.pyramid_min_body_ratio:
            return False, f"слабая импульсная свеча {body_ratio:.2f}"

        if state.side == "long":
            if last_candle[4] <= last_candle[1]:
                return False, "последняя свеча не бычья"
            if len(candles) >= 2 and last_candle[4] < candles[-2][4]:
                return False, "нет продолжения вверх"
        else:
            if last_candle[4] >= last_candle[1]:
                return False, "последняя свеча не медвежья"
            if len(candles) >= 2 and last_candle[4] > candles[-2][4]:
                return False, "нет продолжения вниз"

        return True, ""
'''

    text = replace_between(
        text,
        "    def _trend_confirms_pyramid(",
        "    def _lock_profit_after_pyramid(",
        new_trend_confirms,
        "_trend_confirms_pyramid",
    )

    # ------------------------------------------------------------
    # 4) Remove projected_profit_pct filter block
    # ------------------------------------------------------------
    old_profit_block = '''        projected_total_qty = state.qty + add_qty
        if projected_total_qty <= 0:
            return
        projected_avg_px = ((state.avg_px * state.qty) + (last_close * add_qty)) / projected_total_qty
        projected_profit_pct = (
            ((last_close - projected_avg_px) / projected_avg_px * 100.0)
            if state.side == "long"
            else ((projected_avg_px - last_close) / projected_avg_px * 100.0)
        )
        required_profit_pct = max(0.0, state.units * 5.0)
        if projected_profit_pct + 1e-9 < required_profit_pct:
            reason = (
                f"после добора прибыль {projected_profit_pct:.2f}% меньше требуемых {required_profit_pct:.2f}% "
                f"для {state.units} добавленных юнитов"
            )
            self.stats_logger.log(
                "pyramid_skipped",
                inst_id=state.inst_id,
                side=state.side,
                units=state.units,
                reason=reason,
                last_price=last_close,
                next_pyramid_price=state.next_pyramid_price,
                projected_profit_pct=projected_profit_pct,
                required_profit_pct=required_profit_pct,
                add_qty=add_qty,
                scale=scale,
            )
            self.log_line.emit(f"{state.inst_id}: добор пропущен — {reason}")
            return
'''

    new_profit_block = '''        projected_total_qty = state.qty + add_qty
        if projected_total_qty <= 0:
            return
        projected_avg_px = ((state.avg_px * state.qty) + (last_close * add_qty)) / projected_total_qty

        # v025:
        # Убрано жёсткое требование сохранять 5%/10%/15% прибыли после добора.
        # Оно фактически блокировало pyramiding на большинстве инструментов.
'''

    text = replace_once(text, old_profit_block, new_profit_block, "_profit_filter_block")

    # ------------------------------------------------------------
    # 5) Advance next_pyramid_price from previous trigger, not last_close
    # ------------------------------------------------------------
    old_next_pyramid_block = '''        old_qty = state.qty
        state.qty += add_qty
        state.avg_px = ((state.avg_px * old_qty) + (last_close * add_qty)) / state.qty
        state.units += 1
        state.next_pyramid_price = (
            last_close + self.cfg.add_unit_every_atr * state.atr
            if state.side == "long"
            else last_close - self.cfg.add_unit_every_atr * state.atr
        )
        self._lock_profit_after_pyramid(state, last_close)
        added_units = max(0, state.units - 1)
        total_profit_pct = (
            ((last_close - state.avg_px) / state.avg_px * 100.0)
            if state.side == "long"
            else ((state.avg_px - last_close) / state.avg_px * 100.0)
        )
'''

    new_next_pyramid_block = '''        old_qty = state.qty
        prev_trigger_price = float(state.next_pyramid_price)
        state.qty += add_qty
        state.avg_px = ((state.avg_px * old_qty) + (last_close * add_qty)) / state.qty
        state.units += 1
        state.next_pyramid_price = (
            prev_trigger_price + self.cfg.add_unit_every_atr * state.atr
            if state.side == "long"
            else prev_trigger_price - self.cfg.add_unit_every_atr * state.atr
        )
        self._lock_profit_after_pyramid(state, last_close)
        added_units = max(0, state.units - 1)
        total_profit_pct = (
            ((last_close - state.avg_px) / state.avg_px * 100.0)
            if state.side == "long"
            else ((state.avg_px - last_close) / state.avg_px * 100.0)
        )
'''

    text = replace_once(text, old_next_pyramid_block, new_next_pyramid_block, "_next_pyramid_block")

    # ------------------------------------------------------------
    # 6) Simplify pyramid log message
    # ------------------------------------------------------------
    old_log_msg = '''        self.log_line.emit(
            f"{state.inst_id}: добавлен unit #{state.units}, qty+={add_qty}, "
            f"scale={scale:.2f}, прибыль после добора={total_profit_pct:.2f}%, новый стоп={self._fmt_price(state.stop_price)}"
        )
'''

    new_log_msg = '''        self.log_line.emit(
            f"{state.inst_id}: добавлен unit #{state.units}, qty+={add_qty}, "
            f"scale={scale:.2f}, pnl={total_profit_pct:.2f}%, "
            f"следующий добор={self._fmt_price(state.next_pyramid_price)}, "
            f"новый стоп={self._fmt_price(state.stop_price)}"
        )
'''

    text = replace_once(text, old_log_msg, new_log_msg, "_pyramid_log_message")

    DST.write_text(text, encoding="utf-8")
    print(f"Готово: {DST}")


if __name__ == "__main__":
    main()
