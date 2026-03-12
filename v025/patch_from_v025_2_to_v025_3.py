# patch_from_v025_2_to_v025_3.py
from pathlib import Path
import re

SRC = Path("main_v025_2.py")
DST = Path("main_v025_3.py")


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def replace_if_exists(text: str, old: str, new: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    return text


def find_function_block(text: str, func_name: str) -> tuple[int, int]:
    pattern = re.compile(rf"^    def {re.escape(func_name)}\s*\(", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        fail(f"Не найдена функция: {func_name}")

    start = m.start()
    next_def = re.compile(r"^    def \w+\s*\(", re.MULTILINE)
    m2 = next_def.search(text, m.end())
    end = m2.start() if m2 else len(text)
    return start, end


def replace_function(text: str, func_name: str, new_block: str) -> str:
    start, end = find_function_block(text, func_name)
    return text[:start] + new_block.rstrip() + "\n\n" + text[end:]


def insert_before_function(text: str, func_name: str, block: str) -> str:
    start, _ = find_function_block(text, func_name)
    return text[:start] + block.rstrip() + "\n\n" + text[start:]


def main() -> None:
    if not SRC.exists():
        fail(f"Не найден исходный файл: {SRC}")

    text = SRC.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1) Версия / changelog
    # ------------------------------------------------------------
    text = replace_once(text, '# Version: v025_2', '# Version: v025_3', "_header_version")
    text = replace_once(text, '# Based on: main_v025_1.py', '# Based on: main_v025_2.py', "_header_based_on")
    text = replace_once(text, 'APP_VERSION = "v025_2"', 'APP_VERSION = "v025_3"', "_app_version")

    old_changelog = (
        '# Changelog:\n'
        '# - Moved strategy closer to classic Turtle logic\n'
        '# - Simplified breakout confirmation to classic channel breakout\n'
        '# - Increased working position size and strengthened pyramiding\n'
        '# - Added skip-rule for Turtle 20 after profitable trade'
    )
    new_changelog = (
        '# Changelog:\n'
        '# - Softened stop tightening after pyramid adds\n'
        '# - Removed ATR-stop ignore-in-profit behaviour\n'
        '# - Reduced pyramiding aggressiveness for noisy timeframes\n'
        '# - Added limits for total open positions and same-side exposure'
    )
    text = replace_if_exists(text, old_changelog, new_changelog)

    # ------------------------------------------------------------
    # 2) Конфиг: делаем сопровождение спокойнее
    # ------------------------------------------------------------
    config_replacements = [
        ('    max_position_notional_pct: float = 5.0', '    max_position_notional_pct: float = 3.5'),
        ('    pyramid_second_unit_scale: float = 1.00', '    pyramid_second_unit_scale: float = 0.75'),
        ('    pyramid_third_unit_scale: float = 1.00', '    pyramid_third_unit_scale: float = 0.50'),
        ('    pyramid_fourth_unit_scale: float = 1.00', '    pyramid_fourth_unit_scale: float = 0.25'),
        ('    pyramid_min_progress_atr: float = 0.50', '    pyramid_min_progress_atr: float = 0.45'),
        ('    pyramid_min_stop_distance_atr: float = 0.55', '    pyramid_min_stop_distance_atr: float = 0.35'),
    ]
    for old, new in config_replacements:
        text = replace_if_exists(text, old, new)

    # Новые лимиты на открытые позиции
    insertion_anchor = '    illiquid_repeats_for_ban: int = 3\n'
    extra_config = (
        '    illiquid_repeats_for_ban: int = 3\n'
        '    max_open_positions_total: int = 8\n'
        '    max_open_positions_per_side: int = 4\n'
    )
    if 'max_open_positions_total:' not in text:
        text = replace_once(text, insertion_anchor, extra_config, "_insert_open_position_limits")

    # ------------------------------------------------------------
    # 3) Helper для лимита позиций
    # ------------------------------------------------------------
    helper_block = '''
    def _entry_side_limits_ok(self, side: str) -> tuple[bool, str]:
        total_open = len(self.position_state)
        same_side_open = sum(1 for p in self.position_state.values() if str(getattr(p, "side", "")) == str(side))

        max_total = int(getattr(self.cfg, "max_open_positions_total", 0) or 0)
        max_same_side = int(getattr(self.cfg, "max_open_positions_per_side", 0) or 0)

        if max_total > 0 and total_open >= max_total:
            return False, f"достигнут лимит открытых позиций: {total_open}/{max_total}"

        if max_same_side > 0 and same_side_open >= max_same_side:
            return False, f"достигнут лимит позиций по стороне {side}: {same_side_open}/{max_same_side}"

        return True, ""
'''
    if "_entry_side_limits_ok" not in text:
        text = insert_before_function(text, "_recent_stopout_blocks_entry", helper_block)

    # ------------------------------------------------------------
    # 4) Вставляем проверку лимитов прямо в enter_position
    # ------------------------------------------------------------
    old_enter_snippet = '''        if total_eq <= 0 or available_eq <= 0:
            return
'''
    new_enter_snippet = '''        if total_eq <= 0 or available_eq <= 0:
            return

        exposure_ok, exposure_reason = self._entry_side_limits_ok(side)
        if not exposure_ok:
            self.stats_logger.log(
                "entry_rejected",
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                reason=exposure_reason,
            )
            self.log_line.emit(f"{inst_id}: вход пропущен — {exposure_reason}")
            return
'''
    text = replace_once(text, old_enter_snippet, new_enter_snippet, "_enter_position_exposure_guard")

    # ------------------------------------------------------------
    # 5) Смягчаем trailing stop после доборов
    # ------------------------------------------------------------
    new_trailing_stop = '''
    def trailing_stop(self, state: PositionState, atr: float, last_close: float) -> float:
        if atr <= 0:
            return state.stop_price

        # v025_3:
        # После доборов не перетягиваем стоп слишком агрессивно.
        stop_multiple = float(self.cfg.atr_stop_multiple)
        if state.units >= 4:
            stop_multiple = min(stop_multiple, 1.80)
        elif state.units >= 3:
            stop_multiple = min(stop_multiple, 1.90)
        elif state.units >= 2:
            stop_multiple = min(stop_multiple, 2.00)

        if state.side == "long":
            candidate = last_close - stop_multiple * atr
            return max(state.stop_price, candidate)

        candidate = last_close + stop_multiple * atr
        return min(state.stop_price, candidate)
'''
    text = replace_function(text, "trailing_stop", new_trailing_stop)

    # ------------------------------------------------------------
    # 6) Смягчаем lock-profit после добора
    # ------------------------------------------------------------
    new_lock_profit = '''
    def _lock_profit_after_pyramid(self, state: PositionState, fill_price: float) -> None:
        if state.atr <= 0 or state.units <= 1:
            return

        # v025_3:
        # Сохраняем идею защиты прибыли, но не душим тренд слишком близким стопом.
        if state.side == "long":
            if state.units == 2:
                floor = state.avg_px - state.atr * 0.15
            elif state.units == 3:
                floor = state.avg_px + state.atr * 0.05
            else:
                floor = state.avg_px + state.atr * 0.20

            tightened = fill_price - max(state.atr * 1.80, 1e-12)
            state.stop_price = max(state.stop_price, floor, tightened)
        else:
            if state.units == 2:
                floor = state.avg_px + state.atr * 0.15
            elif state.units == 3:
                floor = state.avg_px - state.atr * 0.05
            else:
                floor = state.avg_px - state.atr * 0.20

            tightened = fill_price + max(state.atr * 1.80, 1e-12)
            state.stop_price = min(state.stop_price, floor, tightened)
'''
    text = replace_function(text, "_lock_profit_after_pyramid", new_lock_profit)

    # ------------------------------------------------------------
    # 7) Убираем игнор ATR-стопа в плюсе
    # ------------------------------------------------------------
    new_update_and_exit = '''
    def update_and_maybe_exit_or_pyramid(self, state: PositionState) -> None:
        candles = self.gateway.get_candles(state.inst_id, self.cfg.timeframe, max(state.exit_period, self.cfg.atr_period) + 5)
        if not candles:
            return

        ticker = self.gateway.get_ticker_data(state.inst_id)
        current_price = float(ticker.get("markPx") or ticker.get("last") or state.last_px or state.avg_px)
        state.last_px = current_price

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr > 0:
            state.atr = atr

        state.stop_price = self.trailing_stop(state, state.atr, current_price)

        exit_window = candles[-state.exit_period:]
        exit_long_level = min(c[3] for c in exit_window)
        exit_short_level = max(c[2] for c in exit_window)

        stop_hit = (state.side == "long" and current_price <= state.stop_price) or (
            state.side == "short" and current_price >= state.stop_price
        )
        turtle_exit = (state.side == "long" and current_price <= exit_long_level) or (
            state.side == "short" and current_price >= exit_short_level
        )

        # v025_3:
        # ATR-стоп больше не игнорируем даже при символическом плюсе.
        if stop_hit:
            self.close_position(state, current_price, f"ATR стоп {self.cfg.atr_stop_multiple}N")
            return

        if turtle_exit:
            self.close_position(state, current_price, f"Канальный выход {state.exit_period} свечей")
            return

        self.try_pyramid(state, current_price, candles)
        self._save_state()
'''
    text = replace_function(text, "update_and_maybe_exit_or_pyramid", new_update_and_exit)

    # ------------------------------------------------------------
    # 8) Обновляем стартовый лог, если фрагмент есть
    # ------------------------------------------------------------
    old_start_fragment = '''            breakout_mode="classic_turtle",
            structure_filter_enabled=False,
            blacklist=list(self.cfg.blacklist),
'''
    new_start_fragment = '''            breakout_mode="classic_turtle",
            structure_filter_enabled=False,
            max_open_positions_total=self.cfg.max_open_positions_total,
            max_open_positions_per_side=self.cfg.max_open_positions_per_side,
            blacklist=list(self.cfg.blacklist),
'''
    text = replace_if_exists(text, old_start_fragment, new_start_fragment)

    DST.write_text(text, encoding="utf-8")
    print(f"Готово: {DST}")


if __name__ == "__main__":
    main()
