# patch_v022_dual_turtle_systems.py
# Патч для main_v022.py
#
# Что делает:
# 1) Исправляет критический баг канала: текущая свеча исключается из расчёта уровня пробоя.
# 2) Включает обе Turtle-системы в обе стороны:
#    - Turtle 20/10 для long и short
#    - Turtle 55/20 для long и short
# 3) Делает entry_period / exit_period зависимыми от system_name, а не от направления.
#
# Использование:
#   python patch_v022_dual_turtle_systems.py
#
# Скрипт создаст:
#   - backup: main_v022.py.bak_dual_turtle
#   - обновлённый: main_v022.py

from pathlib import Path
import shutil
import sys


TARGET_FILE = Path("main_v022.py")
BACKUP_FILE = Path("main_v022.py.bak_dual_turtle")


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

    old_evaluate_entry = '''
    def evaluate_entry(self, inst_id: str) -> None:
        profile = self._tf_entry_profile()
        lookback = int(max(
            self.cfg.long_entry_period,
            self.cfg.short_entry_period,
            self.cfg.atr_period,
            self.cfg.long_exit_period,
            self.cfg.short_exit_period,
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
            should_ban, final_reason = self._register_illiquid_rejection(inst_id, liquid_reason)
            if should_ban:
                self._block_illiquid_instrument(inst_id, final_reason)
                logging.info("%s: пропуск входа, illiquidity-filter -> ban (%s)", inst_id, final_reason)
            else:
                logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, final_reason)
            return

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
        if is_flat:
            logging.info("%s: пропуск входа, flat-filter (%s)", inst_id, flat_reason)
            return

        structure_blocked, structure_reason = self._detect_structure_risk(candles, atr)
        if structure_blocked:
            logging.info("%s: пропуск входа, structure-filter (%s)", inst_id, structure_reason)
            return

        long_level = max(float(c[2]) for c in candles[-self.cfg.long_entry_period:])
        short_level = min(float(c[3]) for c in candles[-self.cfg.short_entry_period:])
        last_high = float(last[2])
        last_low = float(last[3])

        if last_high >= long_level:
            if cooldown_blocked_long:
                logging.info("%s: long-сигнал отклонён (%s)", inst_id, cooldown_reason_long)
                return
            ok, reason = self._confirm_breakout(candles, atr, "long", long_level)
            if ok:
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side="long",
                    price=price,
                    atr=atr,
                    system_name="Turtle 55",
                    timeframe=self.cfg.timeframe,
                )
                self.enter_position(inst_id, "long", price, atr, "Turtle 55")
            else:
                self.stats_logger.log(
                    "entry_rejected",
                    inst_id=inst_id,
                    side="long",
                    price=price,
                    atr=atr,
                    reason=reason,
                )
                logging.info("%s: long-сигнал отклонён (%s)", inst_id, reason)
            return

        if last_low <= short_level:
            if cooldown_blocked_short:
                logging.info("%s: short-сигнал отклонён (%s)", inst_id, cooldown_reason_short)
                return
            ok, reason = self._confirm_breakout(candles, atr, "short", short_level)
            if ok:
                self.stats_logger.log(
                    "entry_signal",
                    inst_id=inst_id,
                    side="short",
                    price=price,
                    atr=atr,
                    system_name="Turtle 20",
                    timeframe=self.cfg.timeframe,
                )
                self.enter_position(inst_id, "short", price, atr, "Turtle 20")
            else:
                self.stats_logger.log(
                    "entry_rejected",
                    inst_id=inst_id,
                    side="short",
                    price=price,
                    atr=atr,
                    reason=reason,
                )
                logging.info("%s: short-сигнал отклонён (%s)", inst_id, reason)
'''.strip("\n")

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
            should_ban, final_reason = self._register_illiquid_rejection(inst_id, liquid_reason)
            if should_ban:
                self._block_illiquid_instrument(inst_id, final_reason)
                logging.info("%s: пропуск входа, illiquidity-filter -> ban (%s)", inst_id, final_reason)
            else:
                logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, final_reason)
            return

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
        if is_flat:
            logging.info("%s: пропуск входа, flat-filter (%s)", inst_id, flat_reason)
            return

        structure_blocked, structure_reason = self._detect_structure_risk(candles, atr)
        if structure_blocked:
            logging.info("%s: пропуск входа, structure-filter (%s)", inst_id, structure_reason)
            return

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

        # Сначала более ранняя система 20, потом 55.
        # Внутри одинаковой системы сначала long, потом short — только для детерминизма.
        signals.sort(key=lambda s: (s["entry_period"], 0 if s["side"] == "long" else 1))

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
'''.strip("\n")

    old_enter_position_tail = '''
        state = PositionState(
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=price,
            last_px=price,
            unrealized_pnl=0.0,
            margin=0.0,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            base_unit_qty=qty,
            signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            units=1,
            system_name=system_name,
            entry_period=self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period,
            exit_period=self.cfg.long_exit_period if side == "long" else self.cfg.short_exit_period,
        )
'''.strip("\n")

    new_enter_position_tail = '''
        if system_name == "Turtle 55":
            entry_period = self.cfg.long_entry_period
            exit_period = self.cfg.long_exit_period
        elif system_name == "Turtle 20":
            entry_period = self.cfg.short_entry_period
            exit_period = self.cfg.short_exit_period
        else:
            entry_period = self.cfg.long_entry_period if side == "long" else self.cfg.short_entry_period
            exit_period = self.cfg.long_exit_period if side == "long" else self.cfg.short_exit_period

        state = PositionState(
            inst_id=inst_id,
            side=side,
            qty=qty,
            avg_px=price,
            last_px=price,
            unrealized_pnl=0.0,
            margin=0.0,
            atr=atr,
            stop_price=stop_price,
            next_pyramid_price=next_pyramid,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            base_unit_qty=qty,
            signal_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            units=1,
            system_name=system_name,
            entry_period=entry_period,
            exit_period=exit_period,
        )
'''.strip("\n")

    text = replace_once(text, old_evaluate_entry, new_evaluate_entry, "evaluate_entry")
    text = replace_once(text, old_enter_position_tail, new_enter_position_tail, "enter_position_state")

    if not BACKUP_FILE.exists():
        shutil.copy2(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Backup:   {BACKUP_FILE.resolve()}")
    print(f"Updated:  {TARGET_FILE.resolve()}")


if __name__ == "__main__":
    main()
