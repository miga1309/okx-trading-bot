from pathlib import Path
import re

SOURCE_FILE = "main_v021_balanced_ui.py"
TARGET_FILE = "main_v021c.py"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок для замены: {label}")
    return text.replace(old, new, 1)


def must_sub(text: str, pattern: str, repl: str, label: str) -> str:
    new_text, n = re.subn(pattern, repl, text, flags=re.S)
    if n != 1:
        raise RuntimeError(f"Ожидалась 1 замена для {label}, получено: {n}")
    return new_text


def patch() -> None:
    src = Path(SOURCE_FILE)
    if not src.exists():
        raise FileNotFoundError(f"Не найден исходный файл: {SOURCE_FILE}")

    text = src.read_text(encoding="utf-8")

    # -------------------------------------------------
    # Версия
    # -------------------------------------------------
    text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "v021c"',
        text,
        count=1,
    )

    # -------------------------------------------------
    # BotConfig: немного усиливаем anti-flat и добавляем cooldown
    # -------------------------------------------------
    replacements = [
        ('    flat_lookback_candles: int = 28\n', '    flat_lookback_candles: int = 32\n', 'flat_lookback_candles'),
        ('    min_channel_range_pct: float = 0.75\n', '    min_channel_range_pct: float = 0.82\n', 'min_channel_range_pct'),
        ('    min_atr_pct: float = 0.12\n', '    min_atr_pct: float = 0.14\n', 'min_atr_pct'),
        ('    min_body_to_range_ratio: float = 0.22\n', '    min_body_to_range_ratio: float = 0.24\n', 'min_body_to_range_ratio'),
        ('    min_efficiency_ratio: float = 0.12\n', '    min_efficiency_ratio: float = 0.15\n', 'min_efficiency_ratio'),
        ('    max_direction_flip_ratio: float = 0.78\n', '    max_direction_flip_ratio: float = 0.72\n', 'max_direction_flip_ratio'),
        ('    flat_max_repeated_close_ratio: float = 0.72\n', '    flat_max_repeated_close_ratio: float = 0.68\n', 'flat_max_repeated_close_ratio'),
        ('    flat_max_inside_ratio: float = 0.82\n', '    flat_max_inside_ratio: float = 0.74\n', 'flat_max_inside_ratio'),
        ('    flat_max_wick_to_range_ratio: float = 0.78\n', '    flat_max_wick_to_range_ratio: float = 0.72\n', 'flat_max_wick_to_range_ratio'),
        ('    flat_min_channel_atr_ratio: float = 1.70\n', '    flat_min_channel_atr_ratio: float = 2.00\n', 'flat_min_channel_atr_ratio'),
        ('    flat_max_micro_pullback_ratio: float = 0.92\n', '    flat_max_micro_pullback_ratio: float = 0.84\n', 'flat_max_micro_pullback_ratio'),
    ]
    for old, new, label in replacements:
        text = must_replace(text, old, new, label)

    text = must_replace(
        text,
        '    flat_max_micro_pullback_ratio: float = 0.84\n',
        '    flat_max_micro_pullback_ratio: float = 0.84\n'
        '    cooldown_after_stop_bars: int = 6\n'
        '    cooldown_min_seconds: int = 900\n'
        '    cooldown_max_seconds: int = 21600\n'
        '    reentry_recovery_atr: float = 0.90\n',
        'add cooldown config',
    )

    # -------------------------------------------------
    # TurtleEngine.__init__: хранилище свежих стопов
    # -------------------------------------------------
    text = must_replace(
        text,
        '        self.temp_blocked_until: Dict[str, float] = {}\n'
        '        self.close_retry_after: Dict[str, float] = {}\n',
        '        self.temp_blocked_until: Dict[str, float] = {}\n'
        '        self.close_retry_after: Dict[str, float] = {}\n'
        '        self.recent_stopouts: Dict[str, dict] = {}\n',
        'recent_stopouts init',
    )

    # -------------------------------------------------
    # Вставляем helper-методы после _detect_side_from_pos
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def _detect_side_from_pos(self, pos: dict) -> Optional[str]:
        pos_value = float(pos.get("pos") or 0.0)
        if pos_value > 0:
            return "long"
        if pos_value < 0:
            return "short"
        side = (pos.get("posSide") or "").lower()
        if side in {"long", "short"}:
            return side
        return None

    def scan_markets(self) -> None:
''',
        '''    def _detect_side_from_pos(self, pos: dict) -> Optional[str]:
        pos_value = float(pos.get("pos") or 0.0)
        if pos_value > 0:
            return "long"
        if pos_value < 0:
            return "short"
        side = (pos.get("posSide") or "").lower()
        if side in {"long", "short"}:
            return side
        return None

    def _timeframe_seconds(self) -> int:
        tf = str(self.cfg.timeframe or "").strip().lower()
        mapping = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "12h": 43200,
            "1d": 86400,
        }
        return mapping.get(tf, 900)

    def _stopout_cooldown_seconds(self) -> int:
        raw = self._timeframe_seconds() * max(1, int(self.cfg.cooldown_after_stop_bars))
        raw = max(int(self.cfg.cooldown_min_seconds), raw)
        raw = min(int(self.cfg.cooldown_max_seconds), raw)
        return raw

    def _register_stopout(self, state: PositionState, exit_price: float, reason: str) -> None:
        lower_reason = str(reason or "").lower()
        if "atr стоп" not in lower_reason:
            return
        cooldown_sec = self._stopout_cooldown_seconds()
        self.recent_stopouts[state.inst_id] = {
            "side": state.side,
            "exit_price": float(exit_price),
            "stop_price": float(state.stop_price),
            "atr": float(max(state.atr, 1e-12)),
            "until": time.time() + cooldown_sec,
            "reason": reason,
        }

    def _recent_stopout_blocks_entry(self, inst_id: str, side: str, price: float) -> tuple[bool, str]:
        data = self.recent_stopouts.get(inst_id)
        if not data:
            return False, "ok"

        now_ts = time.time()
        if float(data.get("until", 0.0)) <= now_ts:
            self.recent_stopouts.pop(inst_id, None)
            return False, "ok"

        prev_side = str(data.get("side") or "")
        exit_price = float(data.get("exit_price") or 0.0)
        atr = float(max(data.get("atr") or 0.0, 1e-12))

        # Если пытаемся войти в ту же сторону слишком близко к свежему stop-out — блокируем.
        if prev_side == side:
            distance = abs(price - exit_price)
            if distance < atr * self.cfg.reentry_recovery_atr:
                remain = max(1, int(data["until"] - now_ts))
                return True, (
                    f"cooldown после ATR-стопа ещё активен {remain}s; "
                    f"цена отошла только на {distance / atr:.2f} ATR"
                )

        return False, "ok"

    def scan_markets(self) -> None:
''',
        'insert cooldown helpers',
    )

    # -------------------------------------------------
    # evaluate_entry: добавляем блокировку повторного входа после stop-out
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            return

        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
''',
        '''        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        if atr <= 0 or price <= 0:
            return

        cooldown_blocked_long, cooldown_reason_long = self._recent_stopout_blocks_entry(inst_id, "long", price)
        cooldown_blocked_short, cooldown_reason_short = self._recent_stopout_blocks_entry(inst_id, "short", price)

        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
''',
        'evaluate_entry insert cooldown precheck',
    )

    text = must_replace(
        text,
        '''        if last_high >= long_level:
            ok, reason = self._confirm_breakout(candles, atr, "long", long_level)
''',
        '''        if last_high >= long_level:
            if cooldown_blocked_long:
                logging.info("%s: long-сигнал отклонён (%s)", inst_id, cooldown_reason_long)
                return
            ok, reason = self._confirm_breakout(candles, atr, "long", long_level)
''',
        'long cooldown gate',
    )

    text = must_replace(
        text,
        '''        if last_low <= short_level:
            ok, reason = self._confirm_breakout(candles, atr, "short", short_level)
''',
        '''        if last_low <= short_level:
            if cooldown_blocked_short:
                logging.info("%s: short-сигнал отклонён (%s)", inst_id, cooldown_reason_short)
                return
            ok, reason = self._confirm_breakout(candles, atr, "short", short_level)
''',
        'short cooldown gate',
    )

    # -------------------------------------------------
    # Новый is_flat_market: жёстче против пилы и полумёртвых диапазонов
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def is_flat_market\(self, candles: List\[List\[float\]\], price: float, atr: float\) -> tuple\[bool, str\]:\n.*?        return False, "ok"\n',
        '''    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        lookback = min(len(candles), max(10, self.cfg.flat_lookback_candles))
        window = candles[-lookback:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        opens = [float(c[1]) for c in window]
        closes = [float(c[4]) for c in window]
        volumes = [float(c[5]) if len(c) > 5 else 0.0 for c in window]

        channel = max(highs) - min(lows)
        channel_range_pct = (channel / price) * 100.0 if price > 0 else 0.0
        atr_pct = (atr / price) * 100.0 if price > 0 else 0.0
        channel_atr_ratio = channel / max(atr, 1e-12)

        repeated_close_ratio = 0.0
        if len(closes) > 1:
            unchanged = sum(
                1 for i in range(1, len(closes))
                if abs(closes[i] - closes[i - 1]) <= max(price * 0.00005, atr * 0.03, 1e-12)
            )
            repeated_close_ratio = unchanged / (len(closes) - 1)

        candle_ranges = [max(float(c[2]) - float(c[3]), 1e-12) for c in window]
        body_ratios = [abs(float(c[4]) - float(c[1])) / rng for c, rng in zip(window, candle_ranges)]
        avg_body_ratio = sum(body_ratios) / len(body_ratios) if body_ratios else 0.0
        wick_ratios = [1.0 - br for br in body_ratios]
        avg_wick_ratio = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0.0

        inside_count = 0
        for i in range(1, len(window)):
            if window[i][2] <= window[i - 1][2] and window[i][3] >= window[i - 1][3]:
                inside_count += 1
        inside_ratio = inside_count / max(1, len(window) - 1)

        net_move = abs(closes[-1] - closes[0]) if len(closes) > 1 else 0.0
        travel = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / travel) if travel > 0 else 0.0

        directions = []
        for opn, cls in zip(opens, closes):
            delta = cls - opn
            if abs(delta) <= max(price * 0.00003, atr * 0.02, 1e-12):
                directions.append(0)
            else:
                directions.append(1 if delta > 0 else -1)

        flips = 0
        non_zero_dirs = [d for d in directions if d != 0]
        for i in range(1, len(non_zero_dirs)):
            if non_zero_dirs[i] != non_zero_dirs[i - 1]:
                flips += 1
        flip_ratio = flips / max(1, len(non_zero_dirs) - 1)

        micro_pullbacks = 0
        for i in range(2, len(closes)):
            prev_move = closes[i - 1] - closes[i - 2]
            curr_move = closes[i] - closes[i - 1]
            if abs(prev_move) > 0 and abs(curr_move) > 0 and (prev_move > 0 > curr_move or prev_move < 0 < curr_move):
                if abs(curr_move) <= abs(prev_move) * 1.15:
                    micro_pullbacks += 1
        micro_pullback_ratio = micro_pullbacks / max(1, len(closes) - 2)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.72

        # Совсем мёртвый рынок баним сразу
        if channel_range_pct < self.cfg.min_channel_range_pct * 0.60:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}%"
        if atr_pct < self.cfg.min_atr_pct * 0.60:
            return True, f"крайне низкий ATR {atr_pct:.3f}%"
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * 0.72:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f}"

        hard_flags = []
        soft_flags = []

        if repeated_close_ratio >= self.cfg.flat_max_repeated_close_ratio:
            hard_flags.append(f"повторяющиеся закрытия {repeated_close_ratio:.0%}")
        if inside_ratio >= self.cfg.flat_max_inside_ratio:
            hard_flags.append(f"inside-bars {inside_ratio:.0%}")
        if flip_ratio > self.cfg.max_direction_flip_ratio:
            hard_flags.append(f"пила {flip_ratio:.0%}")
        if micro_pullback_ratio > self.cfg.flat_max_micro_pullback_ratio:
            hard_flags.append(f"микроретесты {micro_pullback_ratio:.0%}")

        if avg_body_ratio < self.cfg.min_body_to_range_ratio:
            soft_flags.append(f"маленькие тела {avg_body_ratio:.2f}")
        if avg_wick_ratio > self.cfg.flat_max_wick_to_range_ratio:
            soft_flags.append(f"много теней {avg_wick_ratio:.2f}")
        if efficiency_ratio < self.cfg.min_efficiency_ratio:
            soft_flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if volume_dry:
            soft_flags.append("затухающий объём")

        # 2 жёстких признака или 1 жёсткий + 2 мягких уже считаем плохим рынком
        if len(hard_flags) >= 2:
            return True, "; ".join(hard_flags[:2])
        if len(hard_flags) >= 1 and len(soft_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        # Слабый диапазон + слабое направленное движение
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio and efficiency_ratio < self.cfg.min_efficiency_ratio * 1.05:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"
''',
        'replace is_flat_market',
    )

    # -------------------------------------------------
    # Чуть строже _detect_structure_risk и убираем дубль внутри функции
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def _detect_structure_risk\(self, candles: List\[List\[float\]\], atr: float\) -> tuple\[bool, str\]:\n.*?        return False, "ok"\n\n        window = candles\[-12:\].*?        return False, "ok"\n',
        '''    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str]:
        if len(candles) < 12:
            return False, "ok"

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)

        if swing_span <= atr * 1.9:
            false_breaks = 0
            for i in range(2, len(window)):
                prev_high = max(float(c[2]) for c in window[:i])
                prev_low = min(float(c[3]) for c in window[:i])
                h = float(window[i][2])
                l = float(window[i][3])
                c = float(window[i][4])
                if h > prev_high and c <= prev_high:
                    false_breaks += 1
                if l < prev_low and c >= prev_low:
                    false_breaks += 1
            if false_breaks >= 3:
                return True, f"серия ложных выносов ({false_breaks})"

        base_touches_high = 0
        base_touches_low = 0
        top = max(highs)
        bottom = min(lows)
        threshold = atr * 0.30
        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1

        if base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * 2.5:
            return True, "слишком плотная база"

        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * 0.34)
        if close_cluster >= max(8, int(len(closes) * 0.75)):
            return True, "цена прилипла к центру диапазона"

        return False, "ok"
''',
        'replace _detect_structure_risk',
    )

    # -------------------------------------------------
    # close_position: регистрируем ATR-stopout для cooldown
    # -------------------------------------------------
    text = must_replace(
        text,
        '''        self.log_line.emit(f"Позиция {state.inst_id} закрыта. Причина: {reason}")

        emoji = "✅" if pnl >= 0 else "❌"
''',
        '''        self.log_line.emit(f"Позиция {state.inst_id} закрыта. Причина: {reason}")
        self._register_stopout(state, price, reason)

        emoji = "✅" if pnl >= 0 else "❌"
''',
        'register stopout on close',
    )

    # -------------------------------------------------
    # Удаляем старые глобальные helper-функции в хвосте файла
    # -------------------------------------------------
    text = must_sub(
        text,
        r'\n+# ===============================\n# ANTI FLAT MARKET FILTER\n# ===============================.*?(?=\ndef main\(\) -> None:)',
        '\n',
        'remove old global anti-flat tail',
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()