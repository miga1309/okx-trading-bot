# patch_from_v025_1_to_v025_2.py
from pathlib import Path
import re

SRC = Path("main_v025_1.py")
DST = Path("main_v025_2.py")


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, repl: str, label: str, flags=re.MULTILINE | re.DOTALL) -> str:
    new_text, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        fail(f"Не удалось заменить блок regex: {label}")
    return new_text


def find_function_block(text: str, func_name: str) -> tuple[int, int]:
    """
    Находит блок функции вида:
        def func_name(...):
            ...
    и возвращает [start, end)
    """
    pattern = re.compile(rf"^    def {re.escape(func_name)}\s*\(", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        fail(f"Не найдена функция: {func_name}")

    start = m.start()

    next_def = re.compile(r"^    def \w+\s*\(", re.MULTILINE)
    m2 = next_def.search(text, m.end())
    if m2:
        end = m2.start()
    else:
        end = len(text)

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
    text = replace_once(text, '# Version: v025_1', '# Version: v025_2', "_header_version")
    text = replace_once(text, '# Based on: main_v025.py', '# Based on: main_v025_1.py', "_header_based_on")
    text = replace_once(text, 'APP_VERSION = "v025_1"', 'APP_VERSION = "v025_2"', "_app_version")

    # Если прошлый changelog совпадает - меняем красиво.
    old_changelog = (
        '# Changelog:\n'
        '# - Removed "Карта позиций" module from analytics panel\n'
        '# - Widened balance summary card ("Баланс / Использовано / Доступно")\n'
        '# - Widened Turtle regime indicator card in analytics panel\n'
        '# - Cleaned payload/render code related to position_map'
    )
    new_changelog = (
        '# Changelog:\n'
        '# - Moved strategy closer to classic Turtle logic\n'
        '# - Removed structure-filter from entry path\n'
        '# - Simplified breakout confirmation to classic channel breakout\n'
        '# - Increased working position size and strengthened pyramiding\n'
        '# - Added skip-rule for Turtle 20 after profitable trade'
    )
    if old_changelog in text:
        text = text.replace(old_changelog, new_changelog, 1)

    # ------------------------------------------------------------
    # 2) Конфиг ближе к Turtle
    # ------------------------------------------------------------
    config_replacements = [
        ('    max_position_notional_pct: float = 2.0', '    max_position_notional_pct: float = 5.0'),
        ('    pyramid_second_unit_scale: float = 0.75', '    pyramid_second_unit_scale: float = 1.00'),
        ('    pyramid_third_unit_scale: float = 0.50', '    pyramid_third_unit_scale: float = 1.00'),
        ('    pyramid_fourth_unit_scale: float = 0.25', '    pyramid_fourth_unit_scale: float = 1.00'),
        ('    pyramid_min_progress_atr: float = 0.60', '    pyramid_min_progress_atr: float = 0.50'),
        ('    pyramid_min_stop_distance_atr: float = 0.80', '    pyramid_min_stop_distance_atr: float = 0.55'),
        ('    breakout_buffer_atr: float = 0.10', '    breakout_buffer_atr: float = 0.00'),
        ('    breakout_min_body_atr: float = 0.42', '    breakout_min_body_atr: float = 0.00'),
        ('    breakout_close_near_extreme_ratio: float = 0.42', '    breakout_close_near_extreme_ratio: float = 0.00'),
        ('    breakout_min_range_expansion: float = 1.00', '    breakout_min_range_expansion: float = 0.00'),
        ('    breakout_max_prebreak_distance_atr: float = 4.2', '    breakout_max_prebreak_distance_atr: float = 999.0'),
        ('    breakout_retest_invalid_ratio: float = 0.72', '    breakout_retest_invalid_ratio: float = 1.00'),
        ('    breakout_volume_factor: float = 0.95', '    breakout_volume_factor: float = 0.00'),
    ]
    for old, new in config_replacements:
        if old in text:
            text = text.replace(old, new, 1)

    # ------------------------------------------------------------
    # 3) Вставка helper-функции
    # ------------------------------------------------------------
    helper_block = '''
    def _skip_profitable_turtle20_reentry(self, inst_id: str) -> tuple[bool, str]:
        """
        Ближе к классической Turtle:
        после прибыльной сделки по инструменту короткую систему Turtle 20 пропускаем.
        Turtle 55 остаётся активной.
        """
        for trade in reversed(self.closed_trades):
            if str(getattr(trade, "inst_id", "")) != str(inst_id):
                continue

            try:
                pnl_value = float(getattr(trade, "pnl", 0.0))
            except Exception:
                pnl_value = 0.0

            try:
                pnl_pct_value = float(getattr(trade, "pnl_pct", 0.0))
            except Exception:
                pnl_pct_value = 0.0

            if pnl_value > 0 or pnl_pct_value > 0:
                return True, f"последняя сделка по {inst_id} была прибыльной, Turtle 20 пропущен"
            return False, ""

        return False, ""
'''
    if "_skip_profitable_turtle20_reentry" not in text:
        text = insert_before_function(text, "_recent_stopout_blocks_entry", helper_block)

    # ------------------------------------------------------------
    # 4) Полная замена evaluate_entry
    # ------------------------------------------------------------
    new_evaluate_entry = '''
    def evaluate_entry(self, inst_id: str) -> None:
        profile = self._tf_entry_profile()
        max_entry_period = max(self.cfg.long_entry_period, self.cfg.short_entry_period)
        max_exit_period = max(self.cfg.long_exit_period, self.cfg.short_exit_period)

        lookback = int(max(
            max_entry_period,
            self.cfg.atr_period,
            max_exit_period,
            self.cfg.flat_lookback_candles,
        ) * profile["lookback_bonus"]) + 8

        candles = self.gateway.get_candles(inst_id, self.cfg.timeframe, lookback)
        if len(candles) < lookback:
            return

        last = candles[-1]
        price = float(last[4])
        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            return

        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            logging.info("%s: пропуск входа, illiquidity-filter без бана (%s)", inst_id, liquid_reason)
            return

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        last_high = float(last[2])
        last_low = float(last[3])

        systems = [
            {
                "name": "Turtle 20",
                "entry_period": int(self.cfg.short_entry_period),
                "exit_period": int(self.cfg.short_exit_period),
            },
            {
                "name": "Turtle 55",
                "entry_period": int(self.cfg.long_entry_period),
                "exit_period": int(self.cfg.long_exit_period),
            },
        ]

        signals = []

        for system in systems:
            entry_period = int(system["entry_period"])
            if entry_period <= 0:
                continue

            prev_window = candles[-entry_period - 1:-1]
            if len(prev_window) < entry_period:
                continue

            long_level = max(float(c[2]) for c in prev_window)
            short_level = min(float(c[3]) for c in prev_window)

            # Классический Turtle-подход:
            # вход по факту пробоя канала без structure-filter и scoring-confirmation.
            if last_high >= long_level:
                signals.append({
                    "side": "long",
                    "level": long_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                })

            if last_low <= short_level:
                signals.append({
                    "side": "short",
                    "level": short_level,
                    "system_name": system["name"],
                    "entry_period": entry_period,
                    "exit_period": int(system["exit_period"]),
                })

        if not signals:
            return

        # Приоритет у Turtle 55
        signals.sort(key=lambda s: (-s["entry_period"], 0 if s["side"] == "long" else 1))

        for signal in signals:
            side = signal["side"]
            level = float(signal["level"])
            system_name = str(signal["system_name"])

            if side == "long" and cooldown_blocked_long:
                logging.info("%s: %s long-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_long)
                continue

            if side == "short" and cooldown_blocked_short:
                logging.info("%s: %s short-сигнал отклонён (%s)", inst_id, system_name, cooldown_reason_short)
                continue

            # После прибыльной сделки Turtle 20 пропускаем, Turtle 55 оставляем.
            if int(signal["entry_period"]) == int(self.cfg.short_entry_period):
                skip_t20, skip_reason = self._skip_profitable_turtle20_reentry(inst_id)
                if skip_t20:
                    logging.info("%s: %s", inst_id, skip_reason)
                    continue

            ok, reason = self._confirm_breakout(candles, atr, side, level)
            if ok:
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side=side,
                    price=price,
                    atr=atr,
                    system_name=system_name,
                    timeframe=self.cfg.timeframe,
                    entry_period=signal["entry_period"],
                    exit_period=signal["exit_period"],
                    reason=reason,
                )
                self.enter_position(inst_id, side, price, atr, system_name)
                return

            self.stats_logger.log(
                "entry_rejected",
                inst_id=inst_id,
                side=side,
                price=price,
                atr=atr,
                system_name=system_name,
                timeframe=self.cfg.timeframe,
                entry_period=signal["entry_period"],
                exit_period=signal["exit_period"],
                reason=reason,
            )
            logging.info("%s: %s %s-сигнал отклонён (%s)", inst_id, system_name, side, reason)
'''
    text = replace_function(text, "evaluate_entry", new_evaluate_entry)

    # ------------------------------------------------------------
    # 5) Полная замена _confirm_breakout
    # ------------------------------------------------------------
    new_confirm_breakout = '''
    def _confirm_breakout(self, candles: list, atr: float, side: str, level: float) -> tuple[bool, str]:
        """
        v025_2:
        Совместимый stub.
        Подтверждение пробоя сведено к самому факту выхода за канал.
        """
        if not candles:
            return False, "нет свечей"
        if atr <= 0:
            return False, "ATR недоступен"
        if side not in {"long", "short"}:
            return False, "неизвестная сторона"
        return True, "classic_turtle_breakout"
'''
    text = replace_function(text, "_confirm_breakout", new_confirm_breakout)

    # ------------------------------------------------------------
    # 6) Ослабляем _trend_confirms_pyramid
    # ------------------------------------------------------------
    new_trend_confirms = '''
    def _trend_confirms_pyramid(self, state: PositionState, last_close: float, candles: List[List[float]]) -> tuple[bool, str]:
        if not candles:
            return False, "нет свечей для подтверждения"
        if state.atr <= 0:
            return False, "ATR недоступен"

        progress = abs(last_close - state.avg_px)
        if progress < state.atr * self.cfg.pyramid_min_progress_atr:
            return False, f"недостаточный прогресс {progress / state.atr:.2f} ATR"

        distance_to_stop = abs(last_close - state.stop_price)
        if distance_to_stop < state.atr * self.cfg.pyramid_min_stop_distance_atr:
            return False, f"слишком близко к стопу {distance_to_stop / state.atr:.2f} ATR"

        # Ближе к классической Turtle:
        # не требуем body-ratio, flat-check и микроструктурных подтверждений.
        return True, ""
'''
    text = replace_function(text, "_trend_confirms_pyramid", new_trend_confirms)

    # ------------------------------------------------------------
    # 7) Удаляем старые комментарии/остатки structure-filter в evaluate_entry, если остались
    # ------------------------------------------------------------
    text = re.sub(
        r'\n[ \t]*#.*structure-filter.*\n',
        '\n',
        text,
        flags=re.IGNORECASE
    )

    # ------------------------------------------------------------
    # 8) Обновляем лог старта, если найден нужный фрагмент
    # ------------------------------------------------------------
    old_start_fragment = '''            pyramid_scales=[
                1.0,
                self.cfg.pyramid_second_unit_scale,
                self.cfg.pyramid_third_unit_scale,
                self.cfg.pyramid_fourth_unit_scale,
            ],
            blacklist=list(self.cfg.blacklist),
'''
    new_start_fragment = '''            pyramid_scales=[
                1.0,
                self.cfg.pyramid_second_unit_scale,
                self.cfg.pyramid_third_unit_scale,
                self.cfg.pyramid_fourth_unit_scale,
            ],
            breakout_mode="classic_turtle",
            structure_filter_enabled=False,
            blacklist=list(self.cfg.blacklist),
'''
    if old_start_fragment in text:
        text = text.replace(old_start_fragment, new_start_fragment, 1)

    DST.write_text(text, encoding="utf-8")
    print(f"Готово: {DST}")


if __name__ == "__main__":
    main()
