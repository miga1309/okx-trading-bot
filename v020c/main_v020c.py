# ============================================================
# main.py
# OKX Turtle Bot v0.20c
# Монолитная версия
# Python 3.11+
# pip install pyqt6 ccxt
# ============================================================

import sys
import os
import csv
import json
import math
import time
import traceback
import threading

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import ccxt

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def dt_str(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%H:%M:%S")
    except Exception:
        return "--:--:--"


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


# ============================================================
# КОНФИГ
# ============================================================

@dataclass
class BotConfig:
    version: str = "v0.20c"

    # API
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""

    # Режим
    testnet: bool = False

    # Рынки
    symbols_text: str = "BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP"
    timeframe: str = "1m"
    ohlcv_limit: int = 120

    # Риск
    risk_per_trade: float = 0.02
    max_positions: int = 10
    max_units: int = 4
    pyramid_step_atr: float = 0.5

    # Turtle / индикаторы
    atr_period: int = 20
    entry_channel_period: int = 20
    exit_channel_period: int = 10
    entry_ema_period: int = 50

    # Фильтры входа
    min_adx: float = 18.0
    min_channel_width_atr: float = 1.2
    min_breakout_buffer_atr: float = 0.15
    min_atr_percent: float = 0.003
    flat_lookback: int = 25

    require_ema_slope: bool = True
    require_breakout_close: bool = True

    # Таймеры
    engine_interval_sec: int = 2
    gui_interval_ms: int = 2000
    pnl_update_ms: int = 2000
    snapshot_interval_sec: int = 5

    # Логи / статистика
    stats_file: str = "stats_v020c.csv"

    def symbols(self) -> List[str]:
        return [s.strip() for s in self.symbols_text.split(",") if s.strip()]


# ============================================================
# СТРУКТУРЫ ДАННЫХ
# ============================================================

@dataclass
class Position:
    symbol: str
    side: str                 # long / short
    qty: float
    entry_price: float
    stop_price: float
    atr: float

    units: int = 1
    entry_time_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    last_add_price: float = 0.0

    exit_price: float = 0.0
    exit_time_ms: int = 0
    realized_pnl: float = 0.0

    def direction(self) -> int:
        return 1 if self.side == "long" else -1

    def pnl_percent(self, current_price: float) -> float:
        if self.entry_price <= 0:
            return 0.0
        if self.side == "long":
            return ((current_price - self.entry_price) / self.entry_price) * 100.0
        return ((self.entry_price - current_price) / self.entry_price) * 100.0

    def pnl_usdt(self, current_price: float) -> float:
        if self.side == "long":
            return (current_price - self.entry_price) * self.qty
        return (self.entry_price - current_price) * self.qty


# ============================================================
# ЛОГГЕР СТАТИСТИКИ
# ============================================================

class StatsLogger:
    def __init__(self, path: str):
        self.path = path

        if not os.path.exists(self.path):
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "time",
                    "event",
                    "symbol",
                    "side",
                    "price",
                    "qty",
                    "units",
                    "pnl",
                    "comment",
                ])

    def write(
        self,
        event: str,
        symbol: str = "",
        side: str = "",
        price: float = 0.0,
        qty: float = 0.0,
        units: int = 0,
        pnl: float = 0.0,
        comment: str = "",
    ):
        try:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    event,
                    symbol,
                    side,
                    f"{price:.8f}",
                    f"{qty:.8f}",
                    units,
                    f"{pnl:.8f}",
                    comment,
                ])
        except Exception:
            pass


# ============================================================
# ИНДИКАТОРЫ
# ============================================================

def ema(values: List[float], period: int) -> List[Optional[float]]:
    if not values or len(values) < period:
        return []

    k = 2 / (period + 1)
    result: List[Optional[float]] = [None] * len(values)

    sma = sum(values[:period]) / period
    result[period - 1] = sma
    prev = sma

    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        result[i] = prev

    return result


def rma(values: List[float], period: int) -> List[Optional[float]]:
    if not values or len(values) < period:
        return []

    result: List[Optional[float]] = [None] * len(values)

    first_avg = sum(values[:period]) / period
    result[period - 1] = first_avg
    prev = first_avg

    for i in range(period, len(values)):
        prev = ((prev * (period - 1)) + values[i]) / period
        result[i] = prev

    return result


def calc_atr(candles: List[list], period: int = 20) -> List[Optional[float]]:
    if not candles or len(candles) < period + 1:
        return []

    highs = [safe_float(c[2]) for c in candles]
    lows = [safe_float(c[3]) for c in candles]
    closes = [safe_float(c[4]) for c in candles]

    tr = []
    for i in range(len(candles)):
        if i == 0:
            tr.append(highs[i] - lows[i])
        else:
            tr_val = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            tr.append(tr_val)

    return rma(tr, period)


def calc_adx(candles: List[list], period: int = 14) -> List[Optional[float]]:
    if not candles or len(candles) < period * 2:
        return []

    highs = [safe_float(c[2]) for c in candles]
    lows = [safe_float(c[3]) for c in candles]
    closes = [safe_float(c[4]) for c in candles]

    plus_dm = [0.0]
    minus_dm = [0.0]
    tr = [highs[0] - lows[0]]

    for i in range(1, len(candles)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    tr_rma = rma(tr, period)
    plus_rma = rma(plus_dm, period)
    minus_rma = rma(minus_dm, period)

    plus_di = [None] * len(candles)
    minus_di = [None] * len(candles)
    dx = [None] * len(candles)

    for i in range(len(candles)):
        if tr_rma[i] is None or tr_rma[i] == 0:
            continue

        pdi = 100 * (plus_rma[i] / tr_rma[i]) if plus_rma[i] is not None else None
        mdi = 100 * (minus_rma[i] / tr_rma[i]) if minus_rma[i] is not None else None

        plus_di[i] = pdi
        minus_di[i] = mdi

        if pdi is None or mdi is None or (pdi + mdi) == 0:
            continue

        dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi)

    dx_values = [0.0 if v is None else v for v in dx]
    adx = rma(dx_values, period)
    return adx


def highest_high(candles: List[list], start: int, end: int) -> float:
    return max(safe_float(c[2]) for c in candles[start:end])


def lowest_low(candles: List[list], start: int, end: int) -> float:
    return min(safe_float(c[3]) for c in candles[start:end])


def get_last_close(candles: List[list]) -> float:
    if not candles:
        return 0.0
    return safe_float(candles[-1][4])


def is_flat_market(candles: List[list], config: BotConfig) -> bool:
    if not candles or len(candles) < max(config.flat_lookback, config.atr_period) + 2:
        return True

    closes = [safe_float(c[4]) for c in candles]
    atr_list = calc_atr(candles, config.atr_period)
    adx_list = calc_adx(candles, 14)

    if not atr_list or not adx_list:
        return True

    close_now = closes[-1]
    atr_now = atr_list[-1]
    adx_now = adx_list[-1]

    if atr_now is None or adx_now is None or close_now <= 0:
        return True

    atr_percent = atr_now / close_now

    start = len(candles) - config.flat_lookback
    hh = highest_high(candles, start, len(candles))
    ll = lowest_low(candles, start, len(candles))
    width = hh - ll

    if adx_now < config.min_adx:
        return True

    if atr_percent < config.min_atr_percent:
        return True

    if atr_now <= 0:
        return True

    if width / atr_now < config.min_channel_width_atr:
        return True

    return False


# ============================================================
# ОБЕРТКА ДЛЯ OKX
# ============================================================

class OKXExchange:
    def __init__(self, config: BotConfig, log_callback):
        self.config = config
        self.log = log_callback

        urls = None
        if config.testnet:
            urls = {
                "api": {
                    "public": "https://www.okx.com",
                    "private": "https://www.okx.com",
                }
            }

        self.exchange = ccxt.okx(
            {
                "apiKey": config.api_key,
                "secret": config.api_secret,
                "password": config.api_passphrase,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                },
                **({"urls": urls} if urls else {}),
            }
        )

        self.markets_loaded = False
        self.market_cache = {}

    def load_markets(self):
        if not self.markets_loaded:
            self.market_cache = self.exchange.load_markets()
            self.markets_loaded = True
            self.log("Рынки OKX загружены")

    def fetch_balance_usdt(self) -> float:
        try:
            bal = self.exchange.fetch_balance()
            total = bal.get("USDT", {}).get("free", 0.0)
            used = bal.get("USDT", {}).get("used", 0.0)
            return safe_float(total) + safe_float(used)
        except Exception as e:
            self.log(f"Не удалось получить баланс: {e}")
            return 0.0

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[list]:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_ticker_last(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(symbol)
        return safe_float(ticker.get("last"))

    def market_info(self, symbol: str) -> dict:
        self.load_markets()
        return self.market_cache.get(symbol, {})

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        try:
            return float(self.exchange.amount_to_precision(symbol, amount))
        except Exception:
            return amount

    def price_to_precision(self, symbol: str, price: float) -> float:
        try:
            return float(self.exchange.price_to_precision(symbol, price))
        except Exception:
            return price

    def create_market_order(self, symbol: str, side: str, amount: float, reduce_only: bool = False):
        params = {}
        if reduce_only:
            params["reduceOnly"] = True
        return self.exchange.create_order(symbol, "market", side, amount, None, params)
# ============================================================
# ТОРГОВЫЙ ДВИЖОК
# ============================================================

class TradingEngine:
    def __init__(self, config: BotConfig, exchange: OKXExchange, log_callback, snapshot_callback):
        self.config = config
        self.exchange = exchange
        self.log = log_callback
        self.snapshot_callback = snapshot_callback

        self.stats = StatsLogger(config.stats_file)

        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []

        self.last_snapshot = {}
        self.last_cycle_time = "--:--:--"
        self.last_snapshot_time = "--:--:--"

        self.equity_curve: List[Tuple[str, float]] = []

        self._lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.log("Торговый движок запущен")

    def stop(self):
        self.running = False
        self.log("Торговый движок остановлен")

    def _loop(self):
        last_snapshot_ts = 0.0

        while self.running:
            cycle_started = time.time()

            try:
                self.run_cycle()

                if time.time() - last_snapshot_ts >= self.config.snapshot_interval_sec:
                    self.make_snapshot()
                    last_snapshot_ts = time.time()

            except Exception as e:
                self.log(f"Ошибка цикла движка: {e}")
                self.log(traceback.format_exc())

            self.last_cycle_time = now_str()

            elapsed = time.time() - cycle_started
            sleep_for = max(0.1, self.config.engine_interval_sec - elapsed)
            time.sleep(sleep_for)

    def run_cycle(self):
        symbols = self.config.symbols()
        if not symbols:
            return

        for symbol in symbols:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol,
                    self.config.timeframe,
                    self.config.ohlcv_limit,
                )

                if not candles or len(candles) < max(
                    self.config.entry_channel_period + 2,
                    self.config.exit_channel_period + 2,
                    self.config.entry_ema_period + 2,
                    self.config.atr_period + 2,
                    60,
                ):
                    continue

                last_price = get_last_close(candles)

                with self._lock:
                    pos = self.open_positions.get(symbol)

                if pos:
                    self.manage_position(symbol, candles, pos, last_price)
                else:
                    with self._lock:
                        positions_count = len(self.open_positions)

                    if positions_count < self.config.max_positions:
                        signal = self.check_entry_signal(symbol, candles)
                        if signal:
                            self.open_position(symbol, signal, candles, last_price)

            except Exception as e:
                self.log(f"{symbol}: ошибка обработки: {e}")

    # --------------------------------------------------------
    # ВХОД В ПОЗИЦИЮ
    # --------------------------------------------------------

    def check_entry_signal(self, symbol: str, candles: List[list]) -> Optional[str]:
        if is_flat_market(candles, self.config):
            return None

        closes = [safe_float(c[4]) for c in candles]
        atr_list = calc_atr(candles, self.config.atr_period)
        adx_list = calc_adx(candles, 14)
        ema_list = ema(closes, self.config.entry_ema_period)

        if not atr_list or not adx_list or not ema_list:
            return None

        i = len(candles) - 1
        prev_i = i - 1

        atr_now = atr_list[i]
        adx_now = adx_list[i]
        ema_now = ema_list[i]
        ema_prev = ema_list[prev_i]

        if atr_now is None or adx_now is None or ema_now is None or ema_prev is None:
            return None

        close_now = closes[i]

        channel_start = i - self.config.entry_channel_period
        if channel_start < 0:
            return None

        high_prev_channel = highest_high(candles, channel_start, i)
        low_prev_channel = lowest_low(candles, channel_start, i)

        channel_width = high_prev_channel - low_prev_channel
        atr_percent = atr_now / close_now if close_now else 0.0

        if adx_now < self.config.min_adx:
            return None

        if atr_percent < self.config.min_atr_percent:
            return None

        if atr_now <= 0:
            return None

        if channel_width / atr_now < self.config.min_channel_width_atr:
            return None

        ema_slope_ok_long = ema_now > ema_prev
        ema_slope_ok_short = ema_now < ema_prev

        candle_close = safe_float(candles[-1][4])

        long_breakout = close_now > high_prev_channel
        short_breakout = close_now < low_prev_channel

        if self.config.require_breakout_close:
            long_breakout = candle_close > high_prev_channel
            short_breakout = candle_close < low_prev_channel

        long_buffer_ok = (close_now - high_prev_channel) >= atr_now * self.config.min_breakout_buffer_atr
        short_buffer_ok = (low_prev_channel - close_now) >= atr_now * self.config.min_breakout_buffer_atr

        if long_breakout and close_now > ema_now:
            if (not self.config.require_ema_slope) or ema_slope_ok_long:
                if long_buffer_ok:
                    self.log(
                        f"{symbol}: сигнал LONG "
                        f"(close={close_now:.6f}, breakout={high_prev_channel:.6f}, ADX={adx_now:.2f})"
                    )
                    return "long"

        if short_breakout and close_now < ema_now:
            if (not self.config.require_ema_slope) or ema_slope_ok_short:
                if short_buffer_ok:
                    self.log(
                        f"{symbol}: сигнал SHORT "
                        f"(close={close_now:.6f}, breakout={low_prev_channel:.6f}, ADX={adx_now:.2f})"
                    )
                    return "short"

        return None

    def calc_position_size(self, symbol: str, price: float, atr_value: float) -> float:
        balance = self.exchange.fetch_balance_usdt()

        if balance <= 0 or atr_value <= 0 or price <= 0:
            return 0.0

        risk_amount = balance * self.config.risk_per_trade
        stop_distance = 2.0 * atr_value

        qty = risk_amount / stop_distance

        market = self.exchange.market_info(symbol)
        contract_size = safe_float(market.get("contractSize", 1.0), 1.0)

        if contract_size > 0:
            qty = qty / contract_size

        qty = self.exchange.amount_to_precision(symbol, qty)
        return max(0.0, qty)

    def open_position(self, symbol: str, side: str, candles: List[list], price: float):
        atr_list = calc_atr(candles, self.config.atr_period)
        if not atr_list or atr_list[-1] is None:
            return

        atr_now = atr_list[-1]
        qty = self.calc_position_size(symbol, price, atr_now)

        if qty <= 0:
            self.log(f"{symbol}: размер позиции получился 0")
            return

        order_side = "buy" if side == "long" else "sell"

        try:
            # ------------------------------------------------
            # РЕАЛЬНЫЙ ОРДЕР
            # Если хочешь сначала тест без ордеров,
            # закомментируй следующую строку
            # ------------------------------------------------
            self.exchange.create_market_order(symbol, order_side, qty)

            stop_price = price - 2.0 * atr_now if side == "long" else price + 2.0 * atr_now

            pos = Position(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=price,
                stop_price=stop_price,
                atr=atr_now,
                units=1,
                last_add_price=price,
            )

            with self._lock:
                self.open_positions[symbol] = pos

            self.log(
                f"Открыта {side} позиция {symbol}, "
                f"qty={qty:.6f}, ATR={atr_now:.6f}, stop={stop_price:.6f}"
            )

            self.stats.write(
                event="OPEN",
                symbol=symbol,
                side=side,
                price=price,
                qty=qty,
                units=1,
                comment="entry",
            )

        except Exception as e:
            self.log(f"{symbol}: биржа отклонила ордер: {e}")

    # --------------------------------------------------------
    # СОПРОВОЖДЕНИЕ ПОЗИЦИИ
    # --------------------------------------------------------

    def manage_position(self, symbol: str, candles: List[list], pos: Position, current_price: float):
        atr_list = calc_atr(candles, self.config.atr_period)
        if not atr_list or atr_list[-1] is None:
            return

        atr_now = atr_list[-1]
        i = len(candles) - 1

        exit_start = i - self.config.exit_channel_period
        if exit_start < 0:
            return

        exit_high = highest_high(candles, exit_start, i)
        exit_low = lowest_low(candles, exit_start, i)

        # trailing stop
        if pos.side == "long":
            new_stop = max(pos.stop_price, current_price - 2.0 * atr_now)
            pos.stop_price = new_stop
        else:
            new_stop = min(pos.stop_price, current_price + 2.0 * atr_now)
            pos.stop_price = new_stop

        should_exit = False
        exit_reason = ""

        if pos.side == "long":
            if current_price <= pos.stop_price:
                should_exit = True
                exit_reason = "stop"
            elif current_price < exit_low:
                should_exit = True
                exit_reason = "exit_channel"
        else:
            if current_price >= pos.stop_price:
                should_exit = True
                exit_reason = "stop"
            elif current_price > exit_high:
                should_exit = True
                exit_reason = "exit_channel"

        if should_exit:
            self.close_position(symbol, current_price, exit_reason)
            return

        # pyramiding
        if pos.units < self.config.max_units:
            if pos.side == "long":
                trigger_price = pos.last_add_price + atr_now * self.config.pyramid_step_atr
                if current_price >= trigger_price:
                    self.add_unit(symbol, pos, current_price, atr_now)
            else:
                trigger_price = pos.last_add_price - atr_now * self.config.pyramid_step_atr
                if current_price <= trigger_price:
                    self.add_unit(symbol, pos, current_price, atr_now)

    def add_unit(self, symbol: str, pos: Position, current_price: float, atr_now: float):
        add_qty = pos.qty / pos.units if pos.units > 0 else pos.qty
        order_side = "buy" if pos.side == "long" else "sell"

        try:
            # ------------------------------------------------
            # РЕАЛЬНЫЙ ДОБОР
            # ------------------------------------------------
            self.exchange.create_market_order(symbol, order_side, add_qty)

            total_cost_old = pos.entry_price * pos.qty
            total_cost_new = current_price * add_qty
            new_qty = pos.qty + add_qty

            if new_qty <= 0:
                return

            pos.entry_price = (total_cost_old + total_cost_new) / new_qty
            pos.qty = new_qty
            pos.units += 1
            pos.last_add_price = current_price

            if pos.side == "long":
                pos.stop_price = max(pos.stop_price, current_price - 2.0 * atr_now)
            else:
                pos.stop_price = min(pos.stop_price, current_price + 2.0 * atr_now)

            self.log(
                f"{symbol}: добор {pos.side}, "
                f"qty={add_qty:.6f}, units={pos.units}, new_avg={pos.entry_price:.6f}"
            )

            self.stats.write(
                event="ADD",
                symbol=symbol,
                side=pos.side,
                price=current_price,
                qty=add_qty,
                units=pos.units,
                comment="pyramid",
            )

        except Exception as e:
            self.log(f"{symbol}: биржа отклонила добор: {e}")

    def close_position(self, symbol: str, price: float, reason: str):
        with self._lock:
            pos = self.open_positions.get(symbol)
            if not pos:
                return

        order_side = "sell" if pos.side == "long" else "buy"

        try:
            # ------------------------------------------------
            # РЕАЛЬНОЕ ЗАКРЫТИЕ
            # ------------------------------------------------
            self.exchange.create_market_order(symbol, order_side, pos.qty, reduce_only=True)

            pnl = pos.pnl_usdt(price)

            pos.exit_price = price
            pos.exit_time_ms = int(time.time() * 1000)
            pos.realized_pnl = pnl

            with self._lock:
                self.open_positions.pop(symbol, None)
                self.closed_positions.insert(0, pos)

            self.log(
                f"Закрыта {pos.side} позиция {symbol}, "
                f"qty={pos.qty:.6f}, pnl={pnl:.2f}, reason={reason}"
            )

            self.stats.write(
                event="CLOSE",
                symbol=symbol,
                side=pos.side,
                price=price,
                qty=pos.qty,
                units=pos.units,
                pnl=pnl,
                comment=reason,
            )

        except Exception as e:
            self.log(f"{symbol}: ошибка закрытия позиции: {e}")

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def make_snapshot(self):
        with self._lock:
            open_copy = dict(self.open_positions)
            closed_copy = list(self.closed_positions)

        total_open_pnl = 0.0
        open_rows = []

        for symbol, pos in open_copy.items():
            try:
                last_price = self.exchange.fetch_ticker_last(symbol)
            except Exception:
                last_price = pos.entry_price

            pnl = pos.pnl_usdt(last_price)
            pnl_pct = pos.pnl_percent(last_price)
            total_open_pnl += pnl

            open_rows.append(
                {
                    "symbol": symbol,
                    "side": pos.side,
                    "qty": pos.qty,
                    "units": pos.units,
                    "entry_price": pos.entry_price,
                    "current_price": last_price,
                    "stop_price": pos.stop_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "entry_time": dt_str(pos.entry_time_ms),
                }
            )

        closed_rows = []
        total_realized = 0.0

        for pos in closed_copy[:200]:
            total_realized += pos.realized_pnl
            closed_rows.append(
                {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "qty": pos.qty,
                    "units": pos.units,
                    "entry_price": pos.entry_price,
                    "exit_price": pos.exit_price,
                    "pnl": pos.realized_pnl,
                    "entry_time": dt_str(pos.entry_time_ms),
                    "exit_time": dt_str(pos.exit_time_ms),
                }
            )

        balance = self.exchange.fetch_balance_usdt()

        snapshot = {
            "balance": balance,
            "used": 0.0,
            "open_positions": open_rows,
            "closed_positions": closed_rows,
            "open_pnl": total_open_pnl,
            "realized_pnl": total_realized,
            "last_cycle_time": self.last_cycle_time,
            "last_snapshot_time": now_str(),
            "bot_running": self.running,
        }

        self.last_snapshot = snapshot
        self.last_snapshot_time = snapshot["last_snapshot_time"]

        self.equity_curve.append(
            (snapshot["last_snapshot_time"], total_realized + total_open_pnl)
        )

        if len(self.equity_curve) > 200:
            self.equity_curve = self.equity_curve[-200:]

        self.snapshot_callback(snapshot)
# =========================
# POSITION MANAGER
# =========================

class Position:
    def __init__(self, symbol, side, entry_price, qty, atr, stop):
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.qty = qty
        self.atr = atr
        self.stop = stop
        self.units = 1
        self.open_time = datetime.now()
        self.pnl = 0.0
        self.pnl_percent = 0.0

    def update_pnl(self, price):
        if self.side == "long":
            self.pnl = (price - self.entry_price) * self.qty
            self.pnl_percent = (price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl = (self.entry_price - price) * self.qty
            self.pnl_percent = (self.entry_price - price) / self.entry_price * 100


class PositionManager:

    def __init__(self):
        self.positions = {}
        self.closed_positions = []

    def open_position(self, symbol, side, price, qty, atr, stop):
        pos = Position(symbol, side, price, qty, atr, stop)
        self.positions[symbol] = pos
        return pos

    def close_position(self, symbol, price):

        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)

        pos.update_pnl(price)

        pos.close_time = datetime.now()

        self.closed_positions.append(pos)

    def update_price(self, symbol, price):

        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        pos.update_pnl(price)

    def get_open_positions(self):
        return list(self.positions.values())

    def get_closed_positions(self):
        return self.closed_positions


# =========================
# TURTLE LOGIC
# =========================

class TurtleStrategy:

    def __init__(self, config):
        self.config = config

    def breakout_long(self, highs, price):

        if len(highs) < self.config.entry_period:
            return False

        highest = max(highs[-self.config.entry_period:])

        return price > highest

    def breakout_short(self, lows, price):

        if len(lows) < self.config.entry_period:
            return False

        lowest = min(lows[-self.config.entry_period:])

        return price < lowest

    def exit_long(self, lows, price):

        if len(lows) < self.config.exit_period:
            return False

        lowest = min(lows[-self.config.exit_period:])

        return price < lowest

    def exit_short(self, highs, price):

        if len(highs) < self.config.exit_period:
            return False

        highest = max(highs[-self.config.exit_period:])

        return price > highest


# =========================
# MARKET DATA
# =========================

class MarketData:

    def __init__(self, exchange):
        self.exchange = exchange
        self.cache = {}

    def get_ohlc(self, symbol):

        try:
            candles = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=200)

            highs = [c[2] for c in candles]
            lows = [c[3] for c in candles]
            closes = [c[4] for c in candles]

            return highs, lows, closes

        except Exception as e:
            print("market data error:", e)
            return [], [], []

    def get_price(self, symbol):

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"]

        except:
            return None


# =========================
# ATR CALCULATOR
# =========================

def calculate_atr(highs, lows, closes, period=20):

    if len(highs) < period + 1:
        return None

    trs = []

    for i in range(1, len(highs)):

        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )

        trs.append(tr)

    atr = sum(trs[-period:]) / period

    return atr
# =========================
# TRADING ENGINE
# =========================

class TradingEngine:
    def __init__(self, exchange, config, logger, position_manager, market_data, strategy):
        self.exchange = exchange
        self.config = config
        self.logger = logger
        self.position_manager = position_manager
        self.market_data = market_data
        self.strategy = strategy

        self.running = False
        self.thread = None

        self.last_prices = {}
        self.last_engine_cycle = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.logger.log("Торговый движок запущен")

    def stop(self):
        self.running = False
        self.logger.log("Торговый движок остановлен")

    def run(self):
        while self.running:
            try:
                self.engine_cycle()
                self.last_engine_cycle = datetime.now()
            except Exception as e:
                self.logger.log(f"Ошибка торгового движка: {e}")

            time.sleep(self.config.engine_interval_sec)

    def engine_cycle(self):
        symbols = self.config.symbols

        for symbol in symbols:
            try:
                self.process_symbol(symbol)
            except Exception as e:
                self.logger.log(f"{symbol}: ошибка обработки инструмента: {e}")

    def process_symbol(self, symbol):
        highs, lows, closes = self.market_data.get_ohlc(symbol)
        if not highs or not lows or not closes:
            return

        price = closes[-1]
        self.last_prices[symbol] = price

        atr = calculate_atr(highs, lows, closes, self.config.atr_period)
        if atr is None or atr <= 0:
            return

        # защита от флэта / "ровного" рынка
        if self.is_flat_market(highs, lows, closes, atr):
            self.logger.log(f"{symbol}: пропуск входа, обнаружен флэт/ровный рынок")
            self.handle_existing_position(symbol, price, highs, lows, atr)
            return

        # сначала ведем уже открытую позицию
        if symbol in self.position_manager.positions:
            self.handle_existing_position(symbol, price, highs, lows, atr)
            return

        # новые входы только если не превышен лимит позиций
        if len(self.position_manager.positions) >= self.config.max_open_positions:
            return

        self.try_open_position(symbol, price, highs, lows, atr)

    def handle_existing_position(self, symbol, price, highs, lows, atr):
        pos = self.position_manager.positions.get(symbol)
        if not pos:
            return

        self.position_manager.update_price(symbol, price)

        # выход по каналу Turtle
        if pos.side == "long" and self.strategy.exit_long(lows[:-1], price):
            self.close_position(symbol, price, "Выход long по каналу")
            return

        if pos.side == "short" and self.strategy.exit_short(highs[:-1], price):
            self.close_position(symbol, price, "Выход short по каналу")
            return

        # выход по стопу
        if pos.side == "long" and price <= pos.stop:
            self.close_position(symbol, price, "Сработал stop long")
            return

        if pos.side == "short" and price >= pos.stop:
            self.close_position(symbol, price, "Сработал stop short")
            return

        # добавление юнитов Turtle
        self.try_add_unit(symbol, price, atr)

    def try_open_position(self, symbol, price, highs, lows, atr):
        # используем предыдущие свечи без текущей для классического пробоя
        long_breakout = self.strategy.breakout_long(highs[:-1], price)
        short_breakout = self.strategy.breakout_short(lows[:-1], price)

        if long_breakout:
            qty = self.calculate_position_size(symbol, price, atr)
            if qty <= 0:
                return
            stop = price - self.config.stop_atr_mult * atr
            if self.place_order(symbol, "buy", qty):
                pos = self.position_manager.open_position(symbol, "long", price, qty, atr, stop)
                pos.last_add_price = price
                self.logger.log(
                    f"Открыта long позиция {symbol}, qty={qty}, ATR={atr:.6f}, stop={stop:.6f}"
                )

        elif short_breakout:
            qty = self.calculate_position_size(symbol, price, atr)
            if qty <= 0:
                return
            stop = price + self.config.stop_atr_mult * atr
            if self.place_order(symbol, "sell", qty):
                pos = self.position_manager.open_position(symbol, "short", price, qty, atr, stop)
                pos.last_add_price = price
                self.logger.log(
                    f"Открыта short позиция {symbol}, qty={qty}, ATR={atr:.6f}, stop={stop:.6f}"
                )

    def try_add_unit(self, symbol, price, atr):
        pos = self.position_manager.positions.get(symbol)
        if not pos:
            return

        if pos.units >= self.config.max_units:
            return

        add_step = self.config.add_unit_atr_step * atr
        last_add_price = getattr(pos, "last_add_price", pos.entry_price)

        need_add = False

        if pos.side == "long" and price >= last_add_price + add_step:
            need_add = True

        if pos.side == "short" and price <= last_add_price - add_step:
            need_add = True

        if not need_add:
            return

        qty = self.calculate_position_size(symbol, price, atr)
        if qty <= 0:
            return

        side = "buy" if pos.side == "long" else "sell"

        if self.place_order(symbol, side, qty):
            old_qty = pos.qty
            new_qty = old_qty + qty

            pos.entry_price = ((pos.entry_price * old_qty) + (price * qty)) / new_qty
            pos.qty = new_qty
            pos.units += 1
            pos.last_add_price = price

            # подтягиваем стоп по Turtle
            if pos.side == "long":
                new_stop = price - self.config.stop_atr_mult * atr
                pos.stop = max(pos.stop, new_stop)
            else:
                new_stop = price + self.config.stop_atr_mult * atr
                pos.stop = min(pos.stop, new_stop)

            self.logger.log(
                f"{symbol}: добавлен юнит #{pos.units}, qty={qty}, avg_entry={pos.entry_price:.6f}, stop={pos.stop:.6f}"
            )

    def close_position(self, symbol, price, reason="Закрытие позиции"):
        pos = self.position_manager.positions.get(symbol)
        if not pos:
            return

        side = "sell" if pos.side == "long" else "buy"

        if self.place_order(symbol, side, pos.qty, reduce_only=True):
            self.position_manager.close_position(symbol, price)
            closed = self.position_manager.closed_positions[-1]
            self.logger.log(
                f"{reason}: {symbol}, pnl={closed.pnl:.4f}, pnl%={closed.pnl_percent:.2f}%"
            )

    def place_order(self, symbol, side, qty, reduce_only=False):
        try:
            params = {}
            if reduce_only:
                params["reduceOnly"] = True

            order = self.exchange.create_market_order(symbol, side, qty, params=params)

            if order:
                return True

            self.logger.log(f"{symbol}: ордер не был исполнен")
            return False

        except Exception as e:
            self.logger.log(f"{symbol}: биржа отклонила ордер: {e}")
            return False

    def calculate_position_size(self, symbol, price, atr):
        try:
            balance = self.get_available_balance()
            if balance <= 0:
                return 0

            risk_amount = balance * (self.config.risk_per_trade_percent / 100.0)

            stop_distance = self.config.stop_atr_mult * atr
            if stop_distance <= 0:
                return 0

            raw_qty = risk_amount / stop_distance

            # доп. ограничение по доле капитала
            max_notional = balance * (self.config.max_position_balance_percent / 100.0)
            qty_by_balance = max_notional / price if price > 0 else 0

            qty = min(raw_qty, qty_by_balance)

            qty = self.normalize_quantity(symbol, qty)
            return max(qty, 0)

        except Exception as e:
            self.logger.log(f"{symbol}: ошибка расчета размера позиции: {e}")
            return 0

    def normalize_quantity(self, symbol, qty):
        try:
            market = self.exchange.market(symbol)

            lot_step = 1.0
            min_qty = 0.0

            if "limits" in market and market["limits"].get("amount") and market["limits"]["amount"].get("min"):
                min_qty = float(market["limits"]["amount"]["min"])

            if "precision" in market and market["precision"].get("amount") is not None:
                precision = market["precision"]["amount"]
                qty = float(self.exchange.amount_to_precision(symbol, qty))
            else:
                precision = None

            if min_qty and qty < min_qty:
                return 0

            # дополнительная защита от qty=0 после округления
            if qty <= 0:
                return 0

            return qty

        except Exception:
            try:
                qty = float(self.exchange.amount_to_precision(symbol, qty))
                if qty <= 0:
                    return 0
                return qty
            except Exception:
                return round(qty, 6)

    def get_available_balance(self):
        try:
            balance = self.exchange.fetch_balance()

            usdt = 0.0

            if "USDT" in balance:
                usdt_data = balance["USDT"]
                if isinstance(usdt_data, dict):
                    usdt = usdt_data.get("free", 0.0) or usdt_data.get("total", 0.0) or 0.0

            if not usdt and "free" in balance and isinstance(balance["free"], dict):
                usdt = balance["free"].get("USDT", 0.0)

            return float(usdt or 0.0)

        except Exception as e:
            self.logger.log(f"Ошибка получения баланса: {e}")
            return 0.0

    def is_flat_market(self, highs, lows, closes, atr):
        """
        Защита от 'ровного рынка':
        1. слишком узкий диапазон за последние N свечей
        2. слишком маленький средний сдвиг цены между свечами
        3. слишком маленький ATR относительно цены
        """
        n = min(self.config.flat_filter_bars, len(closes))
        if n < 10:
            return False

        recent_highs = highs[-n:]
        recent_lows = lows[-n:]
        recent_closes = closes[-n:]

        price = recent_closes[-1]
        if price <= 0:
            return False

        full_range = max(recent_highs) - min(recent_lows)
        range_pct = (full_range / price) * 100.0

        avg_step = 0.0
        if len(recent_closes) >= 2:
            moves = [abs(recent_closes[i] - recent_closes[i - 1]) for i in range(1, len(recent_closes))]
            avg_step = sum(moves) / len(moves)

        avg_step_pct = (avg_step / price) * 100.0 if price else 0.0
        atr_pct = (atr / price) * 100.0 if price else 0.0

        if range_pct < self.config.flat_range_threshold_pct:
            return True

        if avg_step_pct < self.config.flat_avg_step_threshold_pct:
            return True

        if atr_pct < self.config.flat_atr_threshold_pct:
            return True

        return False
# =========================
# MAIN WINDOW
# =========================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OKX Turtle Bot v0.20c")
        self.resize(1500, 900)

        self.logger = Logger()
        self.exchange = None

        self.config = BotConfig()
        self.position_manager = PositionManager()
        self.strategy = TurtleStrategy(self.config)
        self.market_data = None
        self.engine = None

        self.bot_running = False
        self.last_snapshot_time = None

        self.init_ui()
        self.init_timers()
        self.apply_table_styles()
        self.refresh_all_views()

    # =========================
    # UI INIT
    # =========================

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        top_layout = QHBoxLayout()
        root.addLayout(top_layout, 0)

        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()

        top_layout.addLayout(left_panel, 2)
        top_layout.addLayout(right_panel, 3)

        self.build_config_block(left_panel)
        self.build_control_block(left_panel)
        self.build_stats_block(left_panel)
        self.build_analytics_block(left_panel)

        self.build_open_positions_block(right_panel)
        self.build_closed_positions_block(right_panel)

        self.build_log_block(root)

    def build_config_block(self, parent_layout):
        group = QGroupBox("Настройки")
        layout = QGridLayout(group)

        row = 0

        layout.addWidget(QLabel("API Key"), row, 0)
        self.api_key_edit = QLineEdit()
        layout.addWidget(self.api_key_edit, row, 1)
        row += 1

        layout.addWidget(QLabel("API Secret"), row, 0)
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.api_secret_edit, row, 1)
        row += 1

        layout.addWidget(QLabel("Passphrase"), row, 0)
        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.passphrase_edit, row, 1)
        row += 1

        layout.addWidget(QLabel("Символы"), row, 0)
        self.symbols_edit = QLineEdit(",".join(self.config.symbols))
        layout.addWidget(self.symbols_edit, row, 1)
        row += 1

        layout.addWidget(QLabel("Период входа"), row, 0)
        self.entry_period_spin = QSpinBox()
        self.entry_period_spin.setRange(2, 500)
        self.entry_period_spin.setValue(self.config.entry_period)
        layout.addWidget(self.entry_period_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Период выхода"), row, 0)
        self.exit_period_spin = QSpinBox()
        self.exit_period_spin.setRange(2, 500)
        self.exit_period_spin.setValue(self.config.exit_period)
        layout.addWidget(self.exit_period_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("ATR период"), row, 0)
        self.atr_period_spin = QSpinBox()
        self.atr_period_spin.setRange(2, 200)
        self.atr_period_spin.setValue(self.config.atr_period)
        layout.addWidget(self.atr_period_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Риск на сделку %"), row, 0)
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 100.0)
        self.risk_spin.setDecimals(2)
        self.risk_spin.setValue(self.config.risk_per_trade_percent)
        layout.addWidget(self.risk_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Макс. доля позиции %"), row, 0)
        self.max_pos_balance_spin = QDoubleSpinBox()
        self.max_pos_balance_spin.setRange(0.1, 100.0)
        self.max_pos_balance_spin.setDecimals(2)
        self.max_pos_balance_spin.setValue(self.config.max_position_balance_percent)
        layout.addWidget(self.max_pos_balance_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Макс. позиций"), row, 0)
        self.max_positions_spin = QSpinBox()
        self.max_positions_spin.setRange(1, 100)
        self.max_positions_spin.setValue(self.config.max_open_positions)
        layout.addWidget(self.max_positions_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Макс. юнитов"), row, 0)
        self.max_units_spin = QSpinBox()
        self.max_units_spin.setRange(1, 10)
        self.max_units_spin.setValue(self.config.max_units)
        layout.addWidget(self.max_units_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Стоп ATR множитель"), row, 0)
        self.stop_mult_spin = QDoubleSpinBox()
        self.stop_mult_spin.setRange(0.1, 20.0)
        self.stop_mult_spin.setDecimals(2)
        self.stop_mult_spin.setValue(self.config.stop_atr_mult)
        layout.addWidget(self.stop_mult_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Шаг добавления юнита (ATR)"), row, 0)
        self.add_unit_spin = QDoubleSpinBox()
        self.add_unit_spin.setRange(0.1, 10.0)
        self.add_unit_spin.setDecimals(2)
        self.add_unit_spin.setValue(self.config.add_unit_atr_step)
        layout.addWidget(self.add_unit_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Фильтр флэта: свечей"), row, 0)
        self.flat_bars_spin = QSpinBox()
        self.flat_bars_spin.setRange(5, 500)
        self.flat_bars_spin.setValue(self.config.flat_filter_bars)
        layout.addWidget(self.flat_bars_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Флэт диапазон %"), row, 0)
        self.flat_range_spin = QDoubleSpinBox()
        self.flat_range_spin.setRange(0.001, 50.0)
        self.flat_range_spin.setDecimals(4)
        self.flat_range_spin.setValue(self.config.flat_range_threshold_pct)
        layout.addWidget(self.flat_range_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Флэт ср. шаг %"), row, 0)
        self.flat_step_spin = QDoubleSpinBox()
        self.flat_step_spin.setRange(0.0001, 10.0)
        self.flat_step_spin.setDecimals(4)
        self.flat_step_spin.setValue(self.config.flat_avg_step_threshold_pct)
        layout.addWidget(self.flat_step_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Флэт ATR %"), row, 0)
        self.flat_atr_spin = QDoubleSpinBox()
        self.flat_atr_spin.setRange(0.0001, 10.0)
        self.flat_atr_spin.setDecimals(4)
        self.flat_atr_spin.setValue(self.config.flat_atr_threshold_pct)
        layout.addWidget(self.flat_atr_spin, row, 1)

        parent_layout.addWidget(group)

    def build_control_block(self, parent_layout):
        group = QGroupBox("Управление")
        layout = QHBoxLayout(group)

        self.start_button = QPushButton("Запустить бота")
        self.stop_button = QPushButton("Остановить бота")
        self.save_button = QPushButton("Применить настройки")
        self.test_button = QPushButton("Тест подключения")

        self.start_button.clicked.connect(self.start_bot)
        self.stop_button.clicked.connect(self.stop_bot)
        self.save_button.clicked.connect(self.apply_config_from_ui)
        self.test_button.clicked.connect(self.test_connection)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.test_button)

        parent_layout.addWidget(group)

    def build_stats_block(self, parent_layout):
        group = QGroupBox("Статистика")
        layout = QGridLayout(group)

        row = 0

        layout.addWidget(QLabel("Статус:"), row, 0)
        self.status_value = QLabel("Бот остановлен")
        self.status_value.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Доступно USDT:"), row, 0)
        self.balance_value = QLabel("0.00")
        layout.addWidget(self.balance_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Использовано:"), row, 0)
        self.used_value = QLabel("0.00")
        layout.addWidget(self.used_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Открытых позиций:"), row, 0)
        self.open_positions_value = QLabel("0")
        layout.addWidget(self.open_positions_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Закрытых позиций:"), row, 0)
        self.closed_positions_value = QLabel("0")
        layout.addWidget(self.closed_positions_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Общий PnL:"), row, 0)
        self.total_pnl_value = QLabel("0.00")
        layout.addWidget(self.total_pnl_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Win rate:"), row, 0)
        self.winrate_value = QLabel("0.00%")
        layout.addWidget(self.winrate_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Последнее обновление:"), row, 0)
        self.last_update_value = QLabel("-")
        layout.addWidget(self.last_update_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Последний цикл движка:"), row, 0)
        self.last_engine_value = QLabel("-")
        layout.addWidget(self.last_engine_value, row, 1)
        row += 1

        layout.addWidget(QLabel("Последний snapshot:"), row, 0)
        self.last_snapshot_value = QLabel("-")
        layout.addWidget(self.last_snapshot_value, row, 1)

        parent_layout.addWidget(group)

    def build_analytics_block(self, parent_layout):
        group = QGroupBox("Аналитика")
        layout = QVBoxLayout(group)

        self.analytics_table = QTableWidget()
        self.analytics_table.setColumnCount(2)
        self.analytics_table.setHorizontalHeaderLabels(["Метрика", "Значение"])
        self.analytics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(self.analytics_table)
        parent_layout.addWidget(group)

    def build_open_positions_block(self, parent_layout):
        group = QGroupBox("Открытые позиции")
        layout = QVBoxLayout(group)

        self.open_table = QTableWidget()
        self.open_table.setColumnCount(9)
        self.open_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Время", "Вход", "Цена", "PnL", "PnL%", "Юнитов", "Stop"
        ])
        self.open_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.open_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.open_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        layout.addWidget(self.open_table)
        parent_layout.addWidget(group)

    def build_closed_positions_block(self, parent_layout):
        group = QGroupBox("Закрытые позиции")
        layout = QVBoxLayout(group)

        self.closed_table = QTableWidget()
        self.closed_table.setColumnCount(9)
        self.closed_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Открытие", "Закрытие", "Вход", "Выход", "PnL", "PnL%", "Юнитов"
        ])
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.closed_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.closed_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        layout.addWidget(self.closed_table)
        parent_layout.addWidget(group)

    def build_log_block(self, parent_layout):
        group = QGroupBox("Лог")
        layout = QVBoxLayout(group)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)

        layout.addWidget(self.log_text)
        parent_layout.addWidget(group, 1)

    def init_timers(self):
        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.refresh_all_views)
        self.gui_timer.start(self.config.gui_update_interval_ms)

        self.pnl_timer = QTimer(self)
        self.pnl_timer.timeout.connect(self.refresh_positions_only)
        self.pnl_timer.start(self.config.pnl_update_interval_ms)

    # =========================
    # CONFIG / EXCHANGE
    # =========================

    def apply_config_from_ui(self):
        self.config.api_key = self.api_key_edit.text().strip()
        self.config.api_secret = self.api_secret_edit.text().strip()
        self.config.passphrase = self.passphrase_edit.text().strip()

        symbols_raw = self.symbols_edit.text().strip()
        self.config.symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]

        self.config.entry_period = self.entry_period_spin.value()
        self.config.exit_period = self.exit_period_spin.value()
        self.config.atr_period = self.atr_period_spin.value()

        self.config.risk_per_trade_percent = self.risk_spin.value()
        self.config.max_position_balance_percent = self.max_pos_balance_spin.value()
        self.config.max_open_positions = self.max_positions_spin.value()
        self.config.max_units = self.max_units_spin.value()
        self.config.stop_atr_mult = self.stop_mult_spin.value()
        self.config.add_unit_atr_step = self.add_unit_spin.value()

        self.config.flat_filter_bars = self.flat_bars_spin.value()
        self.config.flat_range_threshold_pct = self.flat_range_spin.value()
        self.config.flat_avg_step_threshold_pct = self.flat_step_spin.value()
        self.config.flat_atr_threshold_pct = self.flat_atr_spin.value()

        self.logger.log("Настройки применены")

    def create_exchange(self):
        return ccxt.okx({
            "apiKey": self.config.api_key,
            "secret": self.config.api_secret,
            "password": self.config.passphrase,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap"
            }
        })

    def test_connection(self):
        try:
            self.apply_config_from_ui()

            exchange = self.create_exchange()
            balance = exchange.fetch_balance()

            usdt = 0.0
            if "free" in balance and isinstance(balance["free"], dict):
                usdt = balance["free"].get("USDT", 0.0)

            self.logger.log(f"Подключение к OKX успешно, доступно USDT: {usdt}")
        except Exception as e:
            self.logger.log(f"Ошибка подключения к OKX: {e}")

    # =========================
    # BOT CONTROL
    # =========================

    def start_bot(self):
        try:
            self.apply_config_from_ui()

            self.exchange = self.create_exchange()
            self.market_data = MarketData(self.exchange)
            self.strategy = TurtleStrategy(self.config)
            self.engine = TradingEngine(
                self.exchange,
                self.config,
                self.logger,
                self.position_manager,
                self.market_data,
                self.strategy
            )

            self.engine.start()
            self.bot_running = True

            self.status_value.setText("Бот запущен")
            self.status_value.setStyleSheet("color: green; font-weight: bold;")

            self.logger.log("Бот запущен пользователем")
            self.logger.log("Бот запущен")

        except Exception as e:
            self.logger.log(f"Не удалось запустить бота: {e}")

    def stop_bot(self):
        try:
            if self.engine:
                self.engine.stop()

            self.bot_running = False
            self.status_value.setText("Бот остановлен")
            self.status_value.setStyleSheet("color: red; font-weight: bold;")

            self.logger.log("Бот остановлен пользователем")
        except Exception as e:
            self.logger.log(f"Ошибка остановки бота: {e}")

    # =========================
    # REFRESH
    # =========================

    def refresh_all_views(self):
        self.refresh_log()
        self.refresh_stats()
        self.refresh_open_positions()
        self.refresh_closed_positions()
        self.refresh_analytics()

        self.last_update_value.setText(datetime.now().strftime("%H:%M:%S"))

    def refresh_positions_only(self):
        self.refresh_open_positions()
        self.refresh_closed_positions()

    def refresh_log(self):
        logs = self.logger.get_logs()
        self.log_text.setPlainText("\n".join(logs))
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def refresh_stats(self):
        open_positions = self.position_manager.get_open_positions()
        closed_positions = self.position_manager.get_closed_positions()

        self.open_positions_value.setText(str(len(open_positions)))
        self.closed_positions_value.setText(str(len(closed_positions)))

        total_pnl = sum(p.pnl for p in closed_positions) + sum(p.pnl for p in open_positions)
        self.total_pnl_value.setText(f"{total_pnl:.4f}")

        wins = len([p for p in closed_positions if p.pnl > 0])
        total_closed = len(closed_positions)
        winrate = (wins / total_closed * 100.0) if total_closed else 0.0
        self.winrate_value.setText(f"{winrate:.2f}%")

        used = 0.0
        for p in open_positions:
            used += p.entry_price * p.qty

        self.used_value.setText(f"{used:.2f}")

        if self.exchange:
            try:
                balance = self.exchange.fetch_balance()
                usdt = 0.0
                if "free" in balance and isinstance(balance["free"], dict):
                    usdt = balance["free"].get("USDT", 0.0)
                self.balance_value.setText(f"{float(usdt):.2f}")
            except Exception:
                pass

        if self.engine and self.engine.last_engine_cycle:
            self.last_engine_value.setText(self.engine.last_engine_cycle.strftime("%H:%M:%S"))

        if self.last_snapshot_time:
            self.last_snapshot_value.setText(self.last_snapshot_time.strftime("%H:%M:%S"))

    def refresh_open_positions(self):
        positions = self.position_manager.get_open_positions()
        self.open_table.setRowCount(len(positions))

        for row, pos in enumerate(positions):
            current_price = ""
            if self.engine and pos.symbol in self.engine.last_prices:
                current_price = f"{self.engine.last_prices[pos.symbol]:.6f}"

            values = [
                pos.symbol,
                pos.side,
                pos.open_time.strftime("%H:%M:%S"),
                f"{pos.entry_price:.6f}",
                current_price,
                f"{pos.pnl:.4f}",
                f"{pos.pnl_percent:.2f}%",
                str(pos.units),
                f"{pos.stop:.6f}",
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.open_table.setItem(row, col, item)

            self.paint_pnl_row(self.open_table, row, pos.pnl_percent)

    def refresh_closed_positions(self):
        positions = self.position_manager.get_closed_positions()
        self.closed_table.setRowCount(len(positions))

        for row, pos in enumerate(reversed(positions)):
            close_time = getattr(pos, "close_time", None)
            close_time_str = close_time.strftime("%H:%M:%S") if close_time else "-"

            values = [
                pos.symbol,
                pos.side,
                pos.open_time.strftime("%H:%M:%S"),
                close_time_str,
                f"{pos.entry_price:.6f}",
                f"{getattr(pos, 'close_price', 0.0):.6f}" if hasattr(pos, "close_price") else "-",
                f"{pos.pnl:.4f}",
                f"{pos.pnl_percent:.2f}%",
                str(pos.units),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.closed_table.setItem(row, col, item)

            self.paint_pnl_row(self.closed_table, row, pos.pnl_percent)

    def refresh_analytics(self):
        open_positions = self.position_manager.get_open_positions()
        closed_positions = self.position_manager.get_closed_positions()

        total_open_pnl = sum(p.pnl for p in open_positions)
        total_closed_pnl = sum(p.pnl for p in closed_positions)

        avg_open_pnl = (total_open_pnl / len(open_positions)) if open_positions else 0.0
        avg_closed_pnl = (total_closed_pnl / len(closed_positions)) if closed_positions else 0.0
        best_trade = max([p.pnl for p in closed_positions], default=0.0)
        worst_trade = min([p.pnl for p in closed_positions], default=0.0)

        data = [
            ("PnL открытых позиций", total_open_pnl),
            ("PnL закрытых позиций", total_closed_pnl),
            ("Средний PnL открытых", avg_open_pnl),
            ("Средний PnL закрытых", avg_closed_pnl),
            ("Лучшая сделка", best_trade),
            ("Худшая сделка", worst_trade),
        ]

        self.analytics_table.setRowCount(len(data))

        for row, (name, value) in enumerate(data):
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)

            value_item = QTableWidgetItem(f"{value:.4f}")
            value_item.setTextAlignment(Qt.AlignCenter)

            if value > 0:
                value_item.setForeground(QBrush(QColor("green")))
            elif value < 0:
                value_item.setForeground(QBrush(QColor("red")))

            self.analytics_table.setItem(row, 0, name_item)
            self.analytics_table.setItem(row, 1, value_item)

    # =========================
    # HELPERS
    # =========================

    def apply_table_styles(self):
        tables = [self.open_table, self.closed_table, self.analytics_table]
        for table in tables:
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)

    def paint_pnl_row(self, table, row, pnl_percent):
        if pnl_percent > 0:
            color = QColor(220, 255, 220)
        elif pnl_percent < 0:
            color = QColor(255, 220, 220)
        else:
            color = QColor(255, 255, 255)

        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setBackground(QBrush(color))

    def closeEvent(self, event):
        try:
            if self.engine:
                self.engine.stop()
        except Exception:
            pass
        event.accept()
class TradeEngine(threading.Thread):

    def __init__(self, config, exchange, logger, state):
        super().__init__(daemon=True)

        self.config = config
        self.exchange = exchange
        self.logger = logger
        self.state = state

        self.running = False

    def run(self):

        self.running = True
        self.logger.log("Торговый движок запущен")

        while self.running:

            try:

                self.process_cycle()

            except Exception as e:
                self.logger.log(f"Ошибка движка: {e}")

            time.sleep(self.config.engine_interval_sec)

    def stop(self):

        self.running = False
        self.logger.log("Торговый движок остановлен")

    def process_cycle(self):

        symbols = self.exchange.get_symbols()

        for symbol in symbols:

            try:
                self.process_symbol(symbol)
            except Exception as e:
                self.logger.log(f"{symbol}: ошибка обработки: {e}")

    def process_symbol(self, symbol):

        candles = self.exchange.get_candles(
            symbol,
            self.config.timeframe,
            self.config.breakout_period + 5
        )

        if candles is None or len(candles) < self.config.breakout_period:
            return

        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        closes = [c[4] for c in candles]

        last_price = closes[-1]

        atr = calculate_atr(candles, self.config.atr_period)

        if atr is None:
            return

        breakout_high = max(highs[-self.config.breakout_period:])
        breakout_low = min(lows[-self.config.breakout_period:])

        position = self.state.get_position(symbol)

        if position is None:

            self.try_open(symbol, last_price, atr, breakout_high, breakout_low)

        else:

            self.manage_position(symbol, position, last_price, atr)

    def try_open(self, symbol, price, atr, breakout_high, breakout_low):

        if self.state.total_positions() >= self.config.max_positions:
            return

        if price >= breakout_high:

            self.open_position(symbol, "long", price, atr)

        elif price <= breakout_low:

            self.open_position(symbol, "short", price, atr)

    def open_position(self, symbol, side, price, atr):

        balance = self.exchange.get_balance()

        risk = balance * self.config.risk_per_trade

        unit_size = risk / atr

        qty = unit_size

        order = self.exchange.place_order(
            symbol,
            side,
            qty
        )

        if not order:
            return

        stop = price - 2 * atr if side == "long" else price + 2 * atr

        position = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            qty=qty,
            units=1,
            atr=atr,
            stop=stop,
            entry_time=datetime.now()
        )

        self.state.add_position(position)

        self.logger.log(
            f"Открыта {side} позиция {symbol}, qty={qty:.4f}, ATR={atr:.6f}, stop={stop:.6f}"
        )

    def manage_position(self, symbol, position, price, atr):

        if position.side == "long":

            if price <= position.stop:
                self.close_position(symbol, position)

            elif price >= position.entry_price + atr and position.units < 4:
                self.add_unit(symbol, position, price, atr)

        else:

            if price >= position.stop:
                self.close_position(symbol, position)

            elif price <= position.entry_price - atr and position.units < 4:
                self.add_unit(symbol, position, price, atr)

    def add_unit(self, symbol, position, price, atr):

        qty = position.qty

        side = position.side

        order = self.exchange.place_order(symbol, side, qty)

        if not order:
            return

        position.units += 1
        position.qty += qty

        if side == "long":
            position.stop = max(position.stop, price - 2 * atr)
        else:
            position.stop = min(position.stop, price + 2 * atr)

        self.logger.log(
            f"{symbol}: добавлен юнит #{position.units}"
        )

    def close_position(self, symbol, position):

        side = "sell" if position.side == "long" else "buy"

        order = self.exchange.place_order(
            symbol,
            side,
            position.qty
        )

        if not order:
            return

        pnl = (position.entry_price - position.stop) * position.qty

        self.state.close_position(symbol)

        self.logger.log(
            f"{symbol}: позиция закрыта"
        )
class BotState:

    def __init__(self):
        self.lock = threading.Lock()

        self.positions = {}
        self.closed_positions = []

        self.logs = []

        self.start_time = None
        self.running = False

        self.last_cycle_time = None
        self.last_snapshot_time = None
        self.last_gui_update_time = None

        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0

        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0

        self.snapshot = {}

    def set_running(self, value: bool):
        with self.lock:
            self.running = value
            if value and self.start_time is None:
                self.start_time = datetime.now()

    def add_log(self, message: str):
        with self.lock:
            self.logs.append({
                "time": datetime.now(),
                "message": message
            })

            if len(self.logs) > 2000:
                self.logs = self.logs[-1000:]

    def get_logs(self, limit=300):
        with self.lock:
            return list(self.logs[-limit:])

    def set_last_cycle_time(self):
        with self.lock:
            self.last_cycle_time = datetime.now()

    def set_last_snapshot_time(self):
        with self.lock:
            self.last_snapshot_time = datetime.now()

    def set_last_gui_update_time(self):
        with self.lock:
            self.last_gui_update_time = datetime.now()

    def get_position(self, symbol):
        with self.lock:
            return self.positions.get(symbol)

    def get_positions(self):
        with self.lock:
            return dict(self.positions)

    def add_position(self, position):
        with self.lock:
            self.positions[position.symbol] = position

    def update_position(self, position):
        with self.lock:
            self.positions[position.symbol] = position

    def total_positions(self):
        with self.lock:
            return len(self.positions)

    def close_position(self, symbol, exit_price=None, reason="close"):

        with self.lock:
            position = self.positions.pop(symbol, None)

            if position is None:
                return None

            if exit_price is None:
                exit_price = position.stop

            pnl = self.calculate_position_pnl(position, exit_price)

            closed_trade = {
                "symbol": position.symbol,
                "side": position.side,
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "qty": position.qty,
                "units": position.units,
                "atr": position.atr,
                "stop": position.stop,
                "entry_time": position.entry_time,
                "exit_time": datetime.now(),
                "pnl": pnl,
                "pnl_percent": self.calculate_position_pnl_percent(position, exit_price),
                "reason": reason
            }

            self.closed_positions.append(closed_trade)
            self.realized_pnl += pnl
            self.total_trades += 1

            if pnl > 0:
                self.win_trades += 1
            else:
                self.loss_trades += 1

            if len(self.closed_positions) > 5000:
                self.closed_positions = self.closed_positions[-2000:]

            return closed_trade

    def get_closed_positions(self, limit=300):
        with self.lock:
            return list(self.closed_positions[-limit:])

    def calculate_position_pnl(self, position, current_price):
        if position.side == "long":
            return (current_price - position.entry_price) * position.qty
        return (position.entry_price - current_price) * position.qty

    def calculate_position_pnl_percent(self, position, current_price):
        if position.entry_price == 0:
            return 0.0

        if position.side == "long":
            return ((current_price - position.entry_price) / position.entry_price) * 100.0
        return ((position.entry_price - current_price) / position.entry_price) * 100.0

    def recalc_unrealized_pnl(self, ticker_prices: dict):
        total = 0.0

        with self.lock:
            for symbol, position in self.positions.items():
                price = ticker_prices.get(symbol)
                if price is None:
                    continue
                total += self.calculate_position_pnl(position, price)

            self.unrealized_pnl = total
            return total

    def get_statistics(self):
        with self.lock:
            win_rate = 0.0
            if self.total_trades > 0:
                win_rate = (self.win_trades / self.total_trades) * 100.0

            return {
                "running": self.running,
                "start_time": self.start_time,
                "open_positions": len(self.positions),
                "closed_positions": len(self.closed_positions),
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": self.unrealized_pnl,
                "total_pnl": self.realized_pnl + self.unrealized_pnl,
                "total_trades": self.total_trades,
                "win_trades": self.win_trades,
                "loss_trades": self.loss_trades,
                "win_rate": win_rate,
                "last_cycle_time": self.last_cycle_time,
                "last_snapshot_time": self.last_snapshot_time,
                "last_gui_update_time": self.last_gui_update_time
            }

    def build_snapshot(self, balance=None, equity=None, available=None):
        with self.lock:
            self.snapshot = {
                "time": datetime.now(),
                "running": self.running,
                "balance": balance,
                "equity": equity,
                "available": available,
                "positions_count": len(self.positions),
                "closed_count": len(self.closed_positions),
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": self.unrealized_pnl,
                "total_pnl": self.realized_pnl + self.unrealized_pnl,
                "total_trades": self.total_trades,
                "win_trades": self.win_trades,
                "loss_trades": self.loss_trades
            }
            return dict(self.snapshot)

    def get_snapshot(self):
        with self.lock:
            return dict(self.snapshot)

    def reset(self):
        with self.lock:
            self.positions = {}
            self.closed_positions = []
            self.logs = []

            self.start_time = None
            self.running = False

            self.last_cycle_time = None
            self.last_snapshot_time = None
            self.last_gui_update_time = None

            self.realized_pnl = 0.0
            self.unrealized_pnl = 0.0

            self.total_trades = 0
            self.win_trades = 0
            self.loss_trades = 0

            self.snapshot = {}
class MainWindow(QMainWindow):

    def __init__(self, config, exchange, state, logger):

        super().__init__()

        self.config = config
        self.exchange = exchange
        self.state = state
        self.logger = logger

        self.engine = None

        self.setWindowTitle("OKX Turtle Trading Bot")
        self.resize(1400, 900)

        self.init_ui()

        self.gui_timer = QTimer()
        self.gui_timer.timeout.connect(self.update_gui)
        self.gui_timer.start(self.config.gui_interval_sec * 1000)

    def init_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout()
        central.setLayout(layout)

        layout.addLayout(self.build_top_panel())

        splitter = QSplitter(Qt.Vertical)

        splitter.addWidget(self.build_positions_table())
        splitter.addWidget(self.build_closed_table())
        splitter.addWidget(self.build_log_panel())

        layout.addWidget(splitter)

    def build_top_panel(self):

        layout = QHBoxLayout()

        self.start_button = QPushButton("Запустить бота")
        self.stop_button = QPushButton("Остановить бота")

        self.start_button.clicked.connect(self.start_bot)
        self.stop_button.clicked.connect(self.stop_bot)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        layout.addSpacing(20)

        self.stats_label = QLabel()
        self.stats_label.setMinimumWidth(600)

        layout.addWidget(self.stats_label)

        layout.addStretch()

        return layout

    def build_positions_table(self):

        self.positions_table = QTableWidget()

        self.positions_table.setColumnCount(8)

        self.positions_table.setHorizontalHeaderLabels([
            "Символ",
            "Side",
            "Цена входа",
            "Цена",
            "PnL %",
            "Qty",
            "Юнитов",
            "Время"
        ])

        self.positions_table.horizontalHeader().setStretchLastSection(True)

        return self.positions_table

    def build_closed_table(self):

        self.closed_table = QTableWidget()

        self.closed_table.setColumnCount(9)

        self.closed_table.setHorizontalHeaderLabels([
            "Символ",
            "Side",
            "Entry",
            "Exit",
            "PnL",
            "PnL %",
            "Qty",
            "Units",
            "Время"
        ])

        self.closed_table.horizontalHeader().setStretchLastSection(True)

        return self.closed_table

    def build_log_panel(self):

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        return self.log_text

    def start_bot(self):

        if self.engine and self.engine.running:
            return

        self.engine = TradeEngine(
            self.config,
            self.exchange,
            self.logger,
            self.state
        )

        self.engine.start()

        self.state.set_running(True)

        self.logger.log("Бот запущен пользователем")

    def stop_bot(self):

        if not self.engine:
            return

        self.engine.stop()

        self.state.set_running(False)

        self.logger.log("Бот остановлен пользователем")

    def update_gui(self):

        self.update_stats()
        self.update_positions()
        self.update_closed()
        self.update_logs()

        self.state.set_last_gui_update_time()

    def update_stats(self):

        stats = self.state.get_statistics()

        text = (
            f"Статус: {'Запущен' if stats['running'] else 'Остановлен'} | "
            f"Открытых: {stats['open_positions']} | "
            f"Сделок: {stats['total_trades']} | "
            f"Winrate: {stats['win_rate']:.2f}% | "
            f"Realized PnL: {stats['realized_pnl']:.4f} | "
            f"Unrealized: {stats['unrealized_pnl']:.4f}"
        )

        self.stats_label.setText(text)

    def update_positions(self):

        positions = self.state.get_positions()

        self.positions_table.setRowCount(len(positions))

        for row, (symbol, pos) in enumerate(positions.items()):

            price = self.exchange.get_last_price(symbol)

            pnl_percent = self.state.calculate_position_pnl_percent(pos, price)

            values = [
                symbol,
                pos.side,
                f"{pos.entry_price:.6f}",
                f"{price:.6f}",
                f"{pnl_percent:.2f}",
                f"{pos.qty:.4f}",
                str(pos.units),
                pos.entry_time.strftime("%H:%M:%S")
            ]

            for col, v in enumerate(values):

                item = QTableWidgetItem(v)

                if col == 4:

                    if pnl_percent > 0:
                        item.setBackground(QColor(0, 80, 0))

                    elif pnl_percent < 0:
                        item.setBackground(QColor(80, 0, 0))

                self.positions_table.setItem(row, col, item)

    def update_closed(self):

        closed = self.state.get_closed_positions()

        self.closed_table.setRowCount(len(closed))

        for row, trade in enumerate(closed):

            values = [
                trade["symbol"],
                trade["side"],
                f"{trade['entry_price']:.6f}",
                f"{trade['exit_price']:.6f}",
                f"{trade['pnl']:.4f}",
                f"{trade['pnl_percent']:.2f}",
                f"{trade['qty']:.4f}",
                str(trade["units"]),
                trade["exit_time"].strftime("%H:%M:%S")
            ]

            for col, v in enumerate(values):

                item = QTableWidgetItem(v)

                if col == 5:

                    if trade["pnl_percent"] > 0:
                        item.setBackground(QColor(0, 80, 0))

                    elif trade["pnl_percent"] < 0:
                        item.setBackground(QColor(80, 0, 0))

                self.closed_table.setItem(row, col, item)

    def update_logs(self):

        logs = self.state.get_logs()

        text = ""

        for log in logs:
            text += f"[{log['time'].strftime('%H:%M:%S')}] {log['message']}\n"

        self.log_text.setText(text)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
class OkxExchange:

    BASE_URL = "https://www.okx.com"

    def __init__(self, config, logger):

        self.config = config
        self.logger = logger

        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.passphrase = config.api_passphrase

        self.session = requests.Session()

        self.symbols = []
        self.symbol_info = {}

        self.last_prices = {}

        self.load_instruments()

    # -------------------------
    # AUTH
    # -------------------------

    def _timestamp(self):
        return datetime.utcnow().isoformat("T", "milliseconds") + "Z"

    def _sign(self, timestamp, method, path, body=""):

        message = f"{timestamp}{method}{path}{body}"

        mac = hmac.new(
            bytes(self.api_secret, encoding="utf8"),
            bytes(message, encoding="utf-8"),
            digestmod=hashlib.sha256
        )

        d = mac.digest()

        return base64.b64encode(d).decode()

    def _headers(self, method, path, body=""):

        timestamp = self._timestamp()

        sign = self._sign(timestamp, method, path, body)

        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

    # -------------------------
    # HTTP
    # -------------------------

    def _get(self, path, auth=False):

        url = self.BASE_URL + path

        headers = None
        if auth:
            headers = self._headers("GET", path)

        r = self.session.get(url, headers=headers, timeout=10)

        return r.json()

    def _post(self, path, data):

        body = json.dumps(data)

        headers = self._headers("POST", path, body)

        url = self.BASE_URL + path

        r = self.session.post(url, headers=headers, data=body, timeout=10)

        return r.json()

    # -------------------------
    # INSTRUMENTS
    # -------------------------

    def load_instruments(self):

        self.logger.log("Загрузка инструментов OKX...")

        data = self._get("/api/v5/public/instruments?instType=SWAP")

        symbols = []

        for inst in data["data"]:

            symbol = inst["instId"]

            symbols.append(symbol)

            self.symbol_info[symbol] = {
                "lot_size": float(inst["lotSz"]),
                "tick_size": float(inst["tickSz"]),
                "min_size": float(inst["minSz"])
            }

        self.symbols = symbols

        self.logger.log(f"Загружено инструментов: {len(symbols)}")

    def get_symbols(self):
        return self.symbols

    # -------------------------
    # MARKET DATA
    # -------------------------

    def get_last_price(self, symbol):

        try:

            data = self._get(f"/api/v5/market/ticker?instId={symbol}")

            price = float(data["data"][0]["last"])

            self.last_prices[symbol] = price

            return price

        except Exception as e:

            self.logger.log(f"{symbol}: ошибка получения цены {e}")

            return self.last_prices.get(symbol)

    def get_candles(self, symbol, timeframe, limit):

        try:

            data = self._get(
                f"/api/v5/market/candles?instId={symbol}&bar={timeframe}&limit={limit}"
            )

            candles = []

            for c in reversed(data["data"]):

                candles.append([
                    int(c[0]),
                    float(c[1]),
                    float(c[2]),
                    float(c[3]),
                    float(c[4]),
                    float(c[5])
                ])

            return candles

        except Exception as e:

            self.logger.log(f"{symbol}: ошибка получения свечей {e}")

            return None

    # -------------------------
    # ACCOUNT
    # -------------------------

    def get_balance(self):

        try:

            data = self._get(
                "/api/v5/account/balance",
                auth=True
            )

            for c in data["data"][0]["details"]:

                if c["ccy"] == "USDT":

                    return float(c["availBal"])

            return 0.0

        except Exception as e:

            self.logger.log(f"Ошибка получения баланса: {e}")

            return 0.0

    # -------------------------
    # ORDER HELPERS
    # -------------------------

    def normalize_size(self, symbol, size):

        info = self.symbol_info.get(symbol)

        if not info:
            return size

        lot = info["lot_size"]

        size = max(size, info["min_size"])

        size = round(size / lot) * lot

        return float(size)

    # -------------------------
    # ORDERS
    # -------------------------

    def place_order(self, symbol, side, size):

        size = self.normalize_size(symbol, size)

        data = {
            "instId": symbol,
            "tdMode": "cross",
            "side": side,
            "ordType": "market",
            "sz": str(size)
        }

        try:

            result = self._post(
                "/api/v5/trade/order",
                data
            )

            if result["code"] != "0":

                msg = result.get("msg", "")

                if result["data"]:

                    msg = result["data"][0].get("sMsg", msg)

                if "51155" in str(result):

                    self.logger.log(
                        f"{symbol}: запрещено торговать (compliance restriction)"
                    )

                    if symbol in self.symbols:
                        self.symbols.remove(symbol)

                    return None

                self.logger.log(f"{symbol}: биржа отклонила ордер: {msg}")

                return None

            return result["data"][0]

        except Exception as e:

            self.logger.log(f"{symbol}: ошибка отправки ордера {e}")

            return None
# =========================================
# ЧАСТЬ 10 — ЗАПУСК СИСТЕМЫ (MAIN)
# =========================================

import sys
import threading
import time
from datetime import datetime
from PyQt5.QtWidgets import QApplication


# -----------------------------------------
# КОНФИГ БОТА
# -----------------------------------------

class BotConfig:

    def __init__(self):

        # API OKX
        self.api_key = ""
        self.api_secret = ""
        self.api_passphrase = ""

        # стратегия
        self.timeframe = "5m"
        self.breakout_period = 20
        self.atr_period = 14

        # риск
        self.risk_per_trade = 0.02
        self.max_positions = 10

        # интервалы обновлений
        self.engine_interval_sec = 2
        self.gui_interval_sec = 2
        self.snapshot_interval_sec = 10


# -----------------------------------------
# SNAPSHOT ПОТОК
# -----------------------------------------

class SnapshotThread(threading.Thread):

    def __init__(self, state, exchange, config, logger):

        super().__init__(daemon=True)

        self.state = state
        self.exchange = exchange
        self.config = config
        self.logger = logger

        self.running = True

    def run(self):

        self.logger.log("Snapshot поток запущен")

        while self.running:

            try:

                balance = self.exchange.get_balance()

                self.state.build_snapshot(
                    balance=balance,
                    equity=balance,
                    available=balance
                )

                self.state.set_last_snapshot_time()

            except Exception as e:

                self.logger.log(f"Ошибка snapshot: {e}")

            time.sleep(self.config.snapshot_interval_sec)

        self.logger.log("Snapshot поток остановлен")

    def stop(self):

        self.running = False


# -----------------------------------------
# MAIN
# -----------------------------------------

def main():

    print("Запуск OKX Turtle Bot")

    # -------------------------------------
    # QT приложение
    # -------------------------------------

    app = QApplication(sys.argv)

    # -------------------------------------
    # CONFIG
    # -------------------------------------

    config = BotConfig()

    # -------------------------------------
    # STATE
    # -------------------------------------

    state = BotState()

    # -------------------------------------
    # LOGGER
    # -------------------------------------

    logger = AppLogger(state=state)

    logger.log("Инициализация системы")

    # -------------------------------------
    # EXCHANGE
    # -------------------------------------

    exchange = OkxExchange(config, logger)

    # -------------------------------------
    # SNAPSHOT THREAD
    # -------------------------------------

    snapshot_thread = SnapshotThread(
        state=state,
        exchange=exchange,
        config=config,
        logger=logger
    )

    snapshot_thread.start()

    # -------------------------------------
    # GUI
    # -------------------------------------

    window = MainWindow(
        config=config,
        exchange=exchange,
        state=state,
        logger=logger
    )

    window.show()

    # -------------------------------------
    # START QT LOOP
    # -------------------------------------

    exit_code = app.exec_()

    # -------------------------------------
    # SHUTDOWN
    # -------------------------------------

    logger.log("Завершение работы")

    try:

        snapshot_thread.stop()

        if window.engine:
            window.engine.stop()

    except Exception as e:

        print("Ошибка остановки потоков:", e)

    sys.exit(exit_code)


# -----------------------------------------
# ENTRY POINT
# -----------------------------------------

if __name__ == "__main__":
    main()