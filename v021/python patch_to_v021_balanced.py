from pathlib import Path
import re

SOURCE_FILE = "main_v021.py"
TARGET_FILE = "main_v021_balanced.py"


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

    # ---------------------------------------
    # Версия
    # ---------------------------------------
    text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "v021b"',
        text,
        count=1,
    )

    # ---------------------------------------
    # Смягчаем параметры BotConfig
    # ---------------------------------------
    replacements = [
        ('    flat_lookback_candles: int = 36\n', '    flat_lookback_candles: int = 28\n', 'flat_lookback_candles'),
        ('    min_channel_range_pct: float = 1.0\n', '    min_channel_range_pct: float = 0.75\n', 'min_channel_range_pct'),
        ('    min_atr_pct: float = 0.18\n', '    min_atr_pct: float = 0.12\n', 'min_atr_pct'),
        ('    min_body_to_range_ratio: float = 0.28\n', '    min_body_to_range_ratio: float = 0.22\n', 'min_body_to_range_ratio'),
        ('    min_efficiency_ratio: float = 0.18\n', '    min_efficiency_ratio: float = 0.12\n', 'min_efficiency_ratio'),
        ('    max_direction_flip_ratio: float = 0.65\n', '    max_direction_flip_ratio: float = 0.78\n', 'max_direction_flip_ratio'),
        ('    breakout_buffer_atr: float = 0.18\n', '    breakout_buffer_atr: float = 0.10\n', 'breakout_buffer_atr'),
        ('    breakout_min_body_atr: float = 0.65\n', '    breakout_min_body_atr: float = 0.42\n', 'breakout_min_body_atr'),
        ('    breakout_close_near_extreme_ratio: float = 0.32\n', '    breakout_close_near_extreme_ratio: float = 0.42\n', 'breakout_close_near_extreme_ratio'),
        ('    breakout_min_range_expansion: float = 1.15\n', '    breakout_min_range_expansion: float = 1.00\n', 'breakout_min_range_expansion'),
        ('    breakout_max_prebreak_distance_atr: float = 2.8\n', '    breakout_max_prebreak_distance_atr: float = 4.2\n', 'breakout_max_prebreak_distance_atr'),
        ('    breakout_retest_invalid_ratio: float = 0.55\n', '    breakout_retest_invalid_ratio: float = 0.72\n', 'breakout_retest_invalid_ratio'),
        ('    breakout_volume_factor: float = 1.20\n', '    breakout_volume_factor: float = 0.95\n', 'breakout_volume_factor'),
        ('    flat_max_repeated_close_ratio: float = 0.55\n', '    flat_max_repeated_close_ratio: float = 0.72\n', 'flat_max_repeated_close_ratio'),
        ('    flat_max_inside_ratio: float = 0.72\n', '    flat_max_inside_ratio: float = 0.82\n', 'flat_max_inside_ratio'),
        ('    flat_max_wick_to_range_ratio: float = 0.62\n', '    flat_max_wick_to_range_ratio: float = 0.78\n', 'flat_max_wick_to_range_ratio'),
        ('    flat_min_channel_atr_ratio: float = 2.4\n', '    flat_min_channel_atr_ratio: float = 1.70\n', 'flat_min_channel_atr_ratio'),
        ('    flat_max_micro_pullback_ratio: float = 0.82\n', '    flat_max_micro_pullback_ratio: float = 0.92\n', 'flat_max_micro_pullback_ratio'),
    ]

    for old, new, label in replacements:
        text = must_replace(text, old, new, label)

    # ---------------------------------------
    # Меняем is_flat_market на score-based вариант
    # ---------------------------------------
    text = must_sub(
        text,
        r'    def is_flat_market\(self, candles: List\[List\[float\]\], price: float, atr: float\) -> tuple\[bool, str\]:\n.*?        return False, "ok"\n',
        '''    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        lookback = min(len(candles), max(8, self.cfg.flat_lookback_candles))
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
                if abs(curr_move) <= abs(prev_move) * 1.1:
                    micro_pullbacks += 1
        micro_pullback_ratio = micro_pullbacks / max(1, len(closes) - 2)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.70

        # Жёсткий отсев только для реально мёртвого рынка
        if channel_range_pct < self.cfg.min_channel_range_pct * 0.55:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}%"
        if atr_pct < self.cfg.min_atr_pct * 0.55:
            return True, f"крайне низкий ATR {atr_pct:.3f}%"

        # Мягкая score-based логика
        flags = []

        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio:
            flags.append(f"малый канал/ATR {channel_atr_ratio:.2f}")
        if repeated_close_ratio >= self.cfg.flat_max_repeated_close_ratio:
            flags.append(f"повторяющиеся закрытия {repeated_close_ratio:.0%}")
        if avg_body_ratio < self.cfg.min_body_to_range_ratio:
            flags.append(f"маленькие тела {avg_body_ratio:.2f}")
        if avg_wick_ratio > self.cfg.flat_max_wick_to_range_ratio:
            flags.append(f"много теней {avg_wick_ratio:.2f}")
        if inside_ratio >= self.cfg.flat_max_inside_ratio:
            flags.append(f"inside-bars {inside_ratio:.0%}")
        if efficiency_ratio < self.cfg.min_efficiency_ratio:
            flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if flip_ratio > self.cfg.max_direction_flip_ratio:
            flags.append(f"пила {flip_ratio:.0%}")
        if micro_pullback_ratio > self.cfg.flat_max_micro_pullback_ratio:
            flags.append(f"микроретесты {micro_pullback_ratio:.0%}")
        if volume_dry and efficiency_ratio < max(0.10, self.cfg.min_efficiency_ratio):
            flags.append("затухающий объём")

        # бан только если слабых признаков несколько одновременно
        if len(flags) >= 3:
            return True, "; ".join(flags[:3])

        # отдельный компромиссный случай: маленький канал + совсем слабая эффективность
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * 0.9 and efficiency_ratio < self.cfg.min_efficiency_ratio * 0.9:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"
''',
        'replace is_flat_market',
    )

    # ---------------------------------------
    # Ослабляем structure risk
    # ---------------------------------------
    text = must_sub(
        text,
        r'    def _detect_structure_risk\(self, candles: List\[List\[float\]\], atr: float\) -> tuple\[bool, str\]:\n.*?        return False, "ok"\n',
        '''    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str]:
        if len(candles) < 12:
            return False, "ok"

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)

        # Баним только если ложных выносов реально серия
        if swing_span <= atr * 1.7:
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
        threshold = atr * 0.28
        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1

        if base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * 2.2:
            return True, "слишком плотная база"

        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * 0.30)
        if close_cluster >= max(8, int(len(closes) * 0.78)):
            return True, "цена прилипла к центру диапазона"

        return False, "ok"
''',
        'replace _detect_structure_risk',
    )

    # ---------------------------------------
    # Ослабляем breakout confirmation
    # ---------------------------------------
    text = must_sub(
        text,
        r'    def _confirm_breakout\(self, candles: List\[List\[float\]\], atr: float, side: str, level: float\) -> tuple\[bool, str\]:\n.*?        return True, "ok"\n',
        '''    def _confirm_breakout(self, candles: List[List[float]], atr: float, side: str, level: float) -> tuple[bool, str]:
        if len(candles) < 6:
            return False, "недостаточно свечей для подтверждения"

        last = candles[-1]
        prev = candles[-2]
        prev2 = candles[-3]

        opn = float(last[1])
        high = float(last[2])
        low = float(last[3])
        close = float(last[4])
        volume = float(last[5]) if len(last) > 5 else 0.0

        last_range = max(high - low, 1e-12)
        prev_range = max(float(prev[2]) - float(prev[3]), 1e-12)
        body = abs(close - opn)

        avg_volume = 0.0
        vol_window = candles[-6:-1]
        if vol_window:
            vols = [float(c[5]) if len(c) > 5 else 0.0 for c in vol_window]
            avg_volume = sum(vols) / len(vols) if vols else 0.0

        score = 0
        reasons = []

        if body >= atr * self.cfg.breakout_min_body_atr:
            score += 1
        else:
            reasons.append(f"слабое тело {body / max(atr, 1e-12):.2f} ATR")

        if last_range >= prev_range * self.cfg.breakout_min_range_expansion:
            score += 1
        else:
            reasons.append("без расширения диапазона")

        if avg_volume <= 0 or volume >= avg_volume * self.cfg.breakout_volume_factor:
            score += 1
        else:
            reasons.append("объём ниже среднего")

        if side == "long":
            if close >= level + atr * self.cfg.breakout_buffer_atr:
                score += 1
            else:
                reasons.append("закрытие слабо выше уровня")

            if (high - close) / last_range <= self.cfg.breakout_close_near_extreme_ratio:
                score += 1
            else:
                reasons.append("закрытие далеко от high")

            prebreak_distance = max(0.0, level - float(prev[4]))
            if prebreak_distance <= atr * self.cfg.breakout_max_prebreak_distance_atr:
                score += 1
            else:
                reasons.append("вход сильно запоздал")

            retest_depth = max(0.0, level - low)
            if retest_depth / last_range <= self.cfg.breakout_retest_invalid_ratio:
                score += 1
            else:
                reasons.append("слишком глубокий ретест")

            if float(prev[2]) > level and float(prev[4]) < level - atr * 0.12:
                reasons.append("предыдущий слабый вынос вверх")
            else:
                score += 1

        else:
            if close <= level - atr * self.cfg.breakout_buffer_atr:
                score += 1
            else:
                reasons.append("закрытие слабо ниже уровня")

            if (close - low) / last_range <= self.cfg.breakout_close_near_extreme_ratio:
                score += 1
            else:
                reasons.append("закрытие далеко от low")

            prebreak_distance = max(0.0, float(prev[4]) - level)
            if prebreak_distance <= atr * self.cfg.breakout_max_prebreak_distance_atr:
                score += 1
            else:
                reasons.append("вход сильно запоздал")

            retest_depth = max(0.0, high - level)
            if retest_depth / last_range <= self.cfg.breakout_retest_invalid_ratio:
                score += 1
            else:
                reasons.append("слишком глубокий ретест")

            if float(prev[3]) < level and float(prev[4]) > level + atr * 0.12:
                reasons.append("предыдущий слабый вынос вниз")
            else:
                score += 1

        # Требуем не идеальный пробой, а хороший набор признаков
        if score >= 5:
            return True, "ok"

        return False, ", ".join(reasons[:3]) if reasons else f"недостаточно подтверждений ({score})"
''',
        'replace _confirm_breakout',
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()