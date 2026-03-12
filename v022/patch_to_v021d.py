from pathlib import Path
import re

SOURCE_FILE = "main_v021c.py"
TARGET_FILE = "main_v021d.py"


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
        'APP_VERSION = "v021d"',
        text,
        count=1,
    )

    # -------------------------------------------------
    # BotConfig: новые параметры anti-illiquidity
    # -------------------------------------------------
    text = must_replace(
        text,
        '    reentry_recovery_atr: float = 0.90\n',
        '    reentry_recovery_atr: float = 0.90\n'
        '    liquidity_max_spread_pct: float = 0.18\n'
        '    liquidity_min_top_of_book_usdt: float = 1200.0\n'
        '    liquidity_min_side_notional_usdt: float = 2500.0\n'
        '    liquidity_min_24h_quote_volume: float = 2500000.0\n'
        '    illiquid_block_hours: int = 8\n',
        'add liquidity config',
    )

    # -------------------------------------------------
    # Gateway: метод получения сырого ticker
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def get_ticker_last(self, inst_id: str) -> float:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return float(data[0]["last"])

    def instrument_info(self, inst_id: str) -> dict:
''',
        '''    def get_ticker_last(self, inst_id: str) -> float:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return float(data[0]["last"])

    def get_ticker_data(self, inst_id: str) -> dict:
        resp = self.market_api.get_ticker(instId=inst_id)
        data = resp.get("data", [])
        if not data:
            raise RuntimeError(f"No ticker for {inst_id}")
        return data[0]

    def instrument_info(self, inst_id: str) -> dict:
''',
        'insert get_ticker_data',
    )

    # -------------------------------------------------
    # TurtleEngine.__init__: бан неликвидных
    # -------------------------------------------------
    text = must_replace(
        text,
        '        self.close_retry_after: Dict[str, float] = {}\n'
        '        self.recent_stopouts: Dict[str, dict] = {}\n',
        '        self.close_retry_after: Dict[str, float] = {}\n'
        '        self.recent_stopouts: Dict[str, dict] = {}\n'
        '        self.illiquid_instruments: Dict[str, float] = {}\n',
        'illiquid init',
    )

    # -------------------------------------------------
    # Helpers: timeframe-adaptive profile + liquidity filter
    # -------------------------------------------------
    text = must_replace(
        text,
        '''    def _stopout_cooldown_seconds(self) -> int:
        raw = self._timeframe_seconds() * max(1, int(self.cfg.cooldown_after_stop_bars))
        raw = max(int(self.cfg.cooldown_min_seconds), raw)
        raw = min(int(self.cfg.cooldown_max_seconds), raw)
        return raw

    def _register_stopout(self, state: PositionState, exit_price: float, reason: str) -> None:
''',
        '''    def _stopout_cooldown_seconds(self) -> int:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            bars = max(6, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 900:
            bars = max(5, int(self.cfg.cooldown_after_stop_bars))
        elif tf_sec <= 3600:
            bars = max(4, int(self.cfg.cooldown_after_stop_bars) - 1)
        else:
            bars = max(3, int(self.cfg.cooldown_after_stop_bars) - 2)

        raw = tf_sec * bars
        raw = max(int(self.cfg.cooldown_min_seconds), raw)
        raw = min(int(self.cfg.cooldown_max_seconds), raw)
        return raw

    def _tf_entry_profile(self) -> dict:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:  # 1m/3m/5m
            return {
                "strict_min": 1.18,
                "strict_max": 0.88,
                "liquidity_min": 1.35,
                "liquidity_max_spread": 0.80,
                "lookback_bonus": 1.15,
            }
        if tf_sec <= 900:  # 15m
            return {
                "strict_min": 1.00,
                "strict_max": 1.00,
                "liquidity_min": 1.00,
                "liquidity_max_spread": 1.00,
                "lookback_bonus": 1.00,
            }
        if tf_sec <= 3600:  # 30m/1h
            return {
                "strict_min": 0.90,
                "strict_max": 1.08,
                "liquidity_min": 0.80,
                "liquidity_max_spread": 1.20,
                "lookback_bonus": 0.92,
            }
        return {  # 2h+
            "strict_min": 0.82,
            "strict_max": 1.18,
            "liquidity_min": 0.65,
            "liquidity_max_spread": 1.35,
            "lookback_bonus": 0.85,
        }

    def _block_illiquid_instrument(self, inst_id: str, reason: str) -> None:
        hours = max(1, int(self.cfg.illiquid_block_hours))
        until_ts = time.time() + hours * 3600
        self.illiquid_instruments[inst_id] = until_ts
        self.temp_blocked_until[inst_id] = until_ts
        logging.info("%s: инструмент заблокирован как неликвидный на %sч (%s)", inst_id, hours, reason)

    def _check_liquidity(self, inst_id: str, price: float) -> tuple[bool, str]:
        try:
            ticker = self.gateway.get_ticker_data(inst_id)
        except Exception as exc:
            return False, f"нет ticker/ликвидности: {exc}"

        profile = self._tf_entry_profile()

        bid_px = float(ticker.get("bidPx") or 0.0)
        ask_px = float(ticker.get("askPx") or 0.0)
        bid_sz = float(ticker.get("bidSz") or 0.0)
        ask_sz = float(ticker.get("askSz") or 0.0)
        vol_24h = float(ticker.get("volCcy24h") or ticker.get("vol24h") or 0.0)

        if bid_px <= 0 or ask_px <= 0:
            return False, "пустой bid/ask"

        mid = (bid_px + ask_px) / 2.0
        spread_pct = ((ask_px - bid_px) / max(mid, 1e-12)) * 100.0

        max_spread_pct = self.cfg.liquidity_max_spread_pct * profile["liquidity_max_spread"]
        min_top_book = self.cfg.liquidity_min_top_of_book_usdt * profile["liquidity_min"]
        min_side_notional = self.cfg.liquidity_min_side_notional_usdt * profile["liquidity_min"]
        min_vol_24h = self.cfg.liquidity_min_24h_quote_volume * profile["liquidity_min"]

        best_bid_notional = bid_px * bid_sz
        best_ask_notional = ask_px * ask_sz

        if spread_pct > max_spread_pct:
            return False, f"широкий спред {spread_pct:.3f}%"
        if best_bid_notional < min_top_book or best_ask_notional < min_top_book:
            return False, f"слабый top-of-book {min(best_bid_notional, best_ask_notional):.0f} USDT"
        if min(best_bid_notional, best_ask_notional) < min_side_notional * 0.45:
            return False, f"слишком тонкий стакан {min(best_bid_notional, best_ask_notional):.0f} USDT"
        if vol_24h > 0 and vol_24h < min_vol_24h:
            return False, f"низкий 24h объём {vol_24h:.0f}"
        if abs(price - mid) / max(mid, 1e-12) > 0.0045:
            return False, "последняя цена далеко от mid"

        return True, "ok"

    def _register_stopout(self, state: PositionState, exit_price: float, reason: str) -> None:
''',
        'insert adaptive helpers',
    )

    # -------------------------------------------------
    # scan_markets: учитывать illiquid ban
    # -------------------------------------------------
    text = must_replace(
        text,
        '''            blocked_until = self.temp_blocked_until.get(inst_id, 0.0)
            if blocked_until and blocked_until > time.time():
                continue
''',
        '''            blocked_until = self.temp_blocked_until.get(inst_id, 0.0)
            if blocked_until and blocked_until > time.time():
                continue
            illiquid_until = self.illiquid_instruments.get(inst_id, 0.0)
            if illiquid_until and illiquid_until > time.time():
                continue
''',
        'scan_markets illiquid skip',
    )

    # -------------------------------------------------
    # evaluate_entry: liquidity gate + adaptive lookback
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def evaluate_entry\(self, inst_id: str\) -> None:\n.*?    def is_flat_market',
        '''    def evaluate_entry(self, inst_id: str) -> None:
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
            self._block_illiquid_instrument(inst_id, liquid_reason)
            logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, liquid_reason)
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

    def is_flat_market''',
        'replace evaluate_entry',
    )

    # -------------------------------------------------
    # is_flat_market: строже + адаптация под timeframe
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def is_flat_market\(self, candles: List\[List\[float\]\], price: float, atr: float\) -> tuple\[bool, str\]:\n.*?        return False, "ok"\n\n    def _detect_structure_risk',
        '''    def is_flat_market(self, candles: List[List[float]], price: float, atr: float) -> tuple[bool, str]:
        if not candles or price <= 0:
            return True, "нет данных для оценки волатильности"

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]
        strict_max = profile["strict_max"]

        lookback = min(len(candles), max(10, int(self.cfg.flat_lookback_candles * profile["lookback_bonus"])))
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
                if abs(curr_move) <= abs(prev_move) * 1.10:
                    micro_pullbacks += 1
        micro_pullback_ratio = micro_pullbacks / max(1, len(closes) - 2)

        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        last_volume = volumes[-1] if volumes else 0.0
        volume_dry = avg_volume > 0 and last_volume < avg_volume * 0.75

        # совсем мёртвый рынок
        if channel_range_pct < self.cfg.min_channel_range_pct * 0.68 * strict_min:
            return True, f"крайне узкий диапазон {channel_range_pct:.3f}%"
        if atr_pct < self.cfg.min_atr_pct * 0.70 * strict_min:
            return True, f"крайне низкий ATR {atr_pct:.3f}%"
        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * 0.82 * strict_min:
            return True, f"канал слишком мал к ATR {channel_atr_ratio:.2f}"

        hard_flags = []
        soft_flags = []

        if repeated_close_ratio >= self.cfg.flat_max_repeated_close_ratio * strict_max:
            hard_flags.append(f"повторяющиеся закрытия {repeated_close_ratio:.0%}")
        if inside_ratio >= self.cfg.flat_max_inside_ratio * strict_max:
            hard_flags.append(f"inside-bars {inside_ratio:.0%}")
        if flip_ratio > self.cfg.max_direction_flip_ratio * strict_max:
            hard_flags.append(f"пила {flip_ratio:.0%}")
        if micro_pullback_ratio > self.cfg.flat_max_micro_pullback_ratio * strict_max:
            hard_flags.append(f"микроретесты {micro_pullback_ratio:.0%}")

        if avg_body_ratio < self.cfg.min_body_to_range_ratio * strict_min:
            soft_flags.append(f"маленькие тела {avg_body_ratio:.2f}")
        if avg_wick_ratio > self.cfg.flat_max_wick_to_range_ratio * strict_max:
            soft_flags.append(f"много теней {avg_wick_ratio:.2f}")
        if efficiency_ratio < self.cfg.min_efficiency_ratio * strict_min:
            soft_flags.append(f"низкая эффективность {efficiency_ratio:.2f}")
        if volume_dry:
            soft_flags.append("затухающий объём")

        score = len(hard_flags) * 2 + len(soft_flags)

        if score >= 4:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if len(hard_flags) >= 1 and len(soft_flags) >= 2:
            return True, "; ".join((hard_flags + soft_flags)[:3])

        if channel_atr_ratio < self.cfg.flat_min_channel_atr_ratio * strict_min and efficiency_ratio < self.cfg.min_efficiency_ratio * 1.08 * strict_min:
            return True, f"слабая структура диапазона {channel_atr_ratio:.2f} / {efficiency_ratio:.2f}"

        return False, "ok"

    def _detect_structure_risk''',
        'replace is_flat_market',
    )

    # -------------------------------------------------
    # _detect_structure_risk: единая очищенная версия + adaptive thresholds
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def _detect_structure_risk\(self, candles: List\[List\[float\]\], atr: float\) -> tuple\[bool, str\]:\n.*?    def _confirm_breakout',
        '''    def _detect_structure_risk(self, candles: List[List[float]], atr: float) -> tuple[bool, str]:
        if len(candles) < 12:
            return False, "ok"

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]

        window = candles[-12:]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        swing_span = max(highs) - min(lows)

        if swing_span <= atr * (1.8 * strict_min):
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
        threshold = atr * (0.30 * strict_min)

        for h, l in zip(highs, lows):
            if abs(top - h) <= threshold:
                base_touches_high += 1
            if abs(l - bottom) <= threshold:
                base_touches_low += 1

        if base_touches_high >= 5 and base_touches_low >= 5 and swing_span < atr * (2.4 * strict_min):
            return True, "слишком плотная база"

        center = (top + bottom) / 2.0
        close_cluster = sum(1 for c in closes if abs(c - center) <= atr * (0.34 * strict_min))
        if close_cluster >= max(8, int(len(closes) * 0.74)):
            return True, "цена прилипла к центру диапазона"

        return False, "ok"

    def _confirm_breakout''',
        'replace structure risk',
    )

    # -------------------------------------------------
    # _confirm_breakout: adaptive thresholds by timeframe
    # -------------------------------------------------
    text = must_sub(
        text,
        r'    def _confirm_breakout\(self, candles: List\[List\[float\]\], atr: float, side: str, level: float\) -> tuple\[bool, str\]:\n.*?        return False, ", ".join\(reasons\[:3\]\) if reasons else f"недостаточно подтверждений \(\{score\}\)"\n',
        '''    def _confirm_breakout(self, candles: List[List[float]], atr: float, side: str, level: float) -> tuple[bool, str]:
        if len(candles) < 6:
            return False, "недостаточно свечей для подтверждения"

        profile = self._tf_entry_profile()
        strict_min = profile["strict_min"]
        strict_max = profile["strict_max"]

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

        need_body_atr = self.cfg.breakout_min_body_atr * strict_min
        need_range_expansion = self.cfg.breakout_min_range_expansion
        need_buffer_atr = self.cfg.breakout_buffer_atr * strict_min
        max_far_from_extreme = self.cfg.breakout_close_near_extreme_ratio * strict_max
        max_prebreak_distance = self.cfg.breakout_max_prebreak_distance_atr * strict_max
        max_retest_ratio = self.cfg.breakout_retest_invalid_ratio * strict_max
        min_volume_factor = self.cfg.breakout_volume_factor

        score = 0
        reasons = []

        if body >= atr * need_body_atr:
            score += 1
        else:
            reasons.append(f"слабое тело {body / max(atr, 1e-12):.2f} ATR")

        if last_range >= prev_range * need_range_expansion:
            score += 1
        else:
            reasons.append("без расширения диапазона")

        if avg_volume <= 0 or volume >= avg_volume * min_volume_factor:
            score += 1
        else:
            reasons.append("объём ниже среднего")

        if side == "long":
            if close >= level + atr * need_buffer_atr:
                score += 1
            else:
                reasons.append("закрытие слабо выше уровня")

            if (high - close) / last_range <= max_far_from_extreme:
                score += 1
            else:
                reasons.append("закрытие далеко от high")

            prebreak_distance = max(0.0, level - float(prev[4]))
            if prebreak_distance <= atr * max_prebreak_distance:
                score += 1
            else:
                reasons.append("вход сильно запоздал")

            retest_depth = max(0.0, level - low)
            if retest_depth / last_range <= max_retest_ratio:
                score += 1
            else:
                reasons.append("слишком глубокий ретест")

            if float(prev[2]) > level and float(prev[4]) < level - atr * 0.10 * strict_min:
                reasons.append("предыдущий слабый вынос вверх")
            else:
                score += 1
        else:
            if close <= level - atr * need_buffer_atr:
                score += 1
            else:
                reasons.append("закрытие слабо ниже уровня")

            if (close - low) / last_range <= max_far_from_extreme:
                score += 1
            else:
                reasons.append("закрытие далеко от low")

            prebreak_distance = max(0.0, float(prev[4]) - level)
            if prebreak_distance <= atr * max_prebreak_distance:
                score += 1
            else:
                reasons.append("вход сильно запоздал")

            retest_depth = max(0.0, high - level)
            if retest_depth / last_range <= max_retest_ratio:
                score += 1
            else:
                reasons.append("слишком глубокий ретест")

            if float(prev[3]) < level and float(prev[4]) > level + atr * 0.10 * strict_min:
                reasons.append("предыдущий слабый вынос вниз")
            else:
                score += 1

        required_score = 5 if self._timeframe_seconds() <= 900 else 4
        if score >= required_score:
            return True, "ok"

        return False, ", ".join(reasons[:3]) if reasons else f"недостаточно подтверждений ({score})"
''',
        'replace breakout confirm',
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()