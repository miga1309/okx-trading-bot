import copy
import json
import math
import threading
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app_core import (
    BotConfig,
    ClosedTrade,
    PositionState,
    STATE_FILE,
    TIMEFRAME_TO_SECONDS,
    TradeLogger,
    EngineStatsLogger,
    TRADE_CSV,
    ENGINE_STATS_FILE,
    format_clock,
)


def _now_ts() -> float:
    return time.time()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _call_first(obj: Any, names: List[str], *args, **kwargs):
    last_err = None
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except TypeError as e:
                last_err = e
                continue
    if last_err:
        raise last_err
    raise AttributeError(f"Не найден ни один метод из списка: {names}")


class TradingEngine:
    def __init__(
        self,
        config: BotConfig,
        gateway: Any,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.gateway = gateway
        self.log_callback = log_callback

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self.positions: Dict[str, PositionState] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.last_snapshot_at: float = 0.0
        self.last_cycle_at: float = 0.0
        self.last_error: str = ""
        self.last_engine_message: str = ""
        self.equity_estimate: float = 0.0
        self.used_margin_estimate: float = 0.0

        self.trade_logger = TradeLogger(TRADE_CSV)
        self.stats_logger = EngineStatsLogger(ENGINE_STATS_FILE)

        self._load_state()

    # ----------------------------- public API -----------------------------

    def start(self) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("Торговый движок запущен")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._log("Торговый движок остановлен")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "positions": [asdict(p) for p in self.positions.values()],
                "closed_trades": [asdict(t) for t in self.closed_trades[-500:]],
                "last_snapshot_at": self.last_snapshot_at,
                "last_cycle_at": self.last_cycle_at,
                "last_error": self.last_error,
                "last_engine_message": self.last_engine_message,
                "equity_estimate": self.equity_estimate,
                "used_margin_estimate": self.used_margin_estimate,
                "running": self.is_running(),
            }

    # ----------------------------- core loop ------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            cycle_started = _now_ts()
            try:
                self._sync_remote_positions()
                self._scan_market_and_trade()
                self._update_snapshot()
                self.last_error = ""
            except Exception as e:
                self.last_error = str(e)
                self._log(f"Ошибка движка: {e}")
                self._log(traceback.format_exc())

            self.last_cycle_at = _now_ts()

            sleep_sec = max(0.5, _safe_float(getattr(self.config, "engine_interval_sec", 2.0), 2.0))
            elapsed = _now_ts() - cycle_started
            remain = max(0.1, sleep_sec - elapsed)

            if self._stop_event.wait(remain):
                break

    # -------------------------- market scanning ---------------------------

    def _scan_market_and_trade(self) -> None:
        instruments = self._get_instruments()
        if not instruments:
            self._log("Не удалось получить список инструментов")
            return

        max_positions = _safe_int(getattr(self.config, "max_positions", 10), 10)
        active_count = len(self.positions)

        timeframe = _safe_str(getattr(self.config, "timeframe", "1m"), "1m")
        candle_limit = max(
            60,
            _safe_int(getattr(self.config, "entry_period", 20), 20)
            + _safe_int(getattr(self.config, "atr_period", 20), 20)
            + 10,
        )

        for inst_id in instruments:
            if self._stop_event.is_set():
                return

            if inst_id in self.positions:
                self._manage_open_position(inst_id, timeframe)
                continue

            if active_count >= max_positions:
                return

            candles = self._get_candles(inst_id, timeframe, candle_limit)
            if len(candles) < 30:
                continue

            stats = self._build_market_stats(candles)
            if self._is_flat_market(stats):
                self._log(
                    f"{inst_id}: пропуск по фильтру флэта "
                    f"(range={stats['range_pct']:.2f}%, atr={stats['atr_pct']:.3f}%, "
                    f"body={stats['body_ratio']:.2f}, eff={stats['eff']:.2f}, flip={stats['flip']:.2f})"
                )
                continue

            signal = self._detect_entry_signal(inst_id, candles, stats)
            if not signal:
                continue

            ok = self._open_position(inst_id, signal, candles, stats)
            if ok:
                active_count += 1

    # ------------------------- signal / position --------------------------

    def _detect_entry_signal(
        self,
        inst_id: str,
        candles: List[Dict[str, float]],
        stats: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        entry_period = _safe_int(getattr(self.config, "entry_period", 20), 20)
        if len(candles) < entry_period + 2:
            return None

        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        prev_close = closes[-2]
        breakout_high = max(highs[-entry_period - 1:-1])
        breakout_low = min(lows[-entry_period - 1:-1])

        if prev_close > breakout_high:
            return {
                "direction": "long",
                "side": "buy",
                "pos_side": "long",
                "breakout": breakout_high,
            }

        if prev_close < breakout_low:
            return {
                "direction": "short",
                "side": "sell",
                "pos_side": "short",
                "breakout": breakout_low,
            }

        return None

    def _open_position(
        self,
        inst_id: str,
        signal: Dict[str, Any],
        candles: List[Dict[str, float]],
        stats: Dict[str, float],
    ) -> bool:
        atr = stats["atr_abs"]
        last_price = candles[-1]["close"]
        if atr <= 0 or last_price <= 0:
            return False

        qty = self._calculate_order_size(inst_id, last_price, atr)
        if qty <= 0:
            return False

        sz = self._format_size(inst_id, qty)

        try:
            response = _call_first(
                self.gateway,
                ["place_market_order", "create_market_order", "market_order"],
                inst_id,
                signal["side"],
                signal.get("pos_side"),
                sz,
            )
        except Exception as e:
            self._log(f"{inst_id}: ошибка открытия ордера: {e}")
            return False

        if not self._order_success(response):
            self._log(f"{inst_id}: биржа отклонила ордер: {response}")
            return False

        stop_price = (
            last_price - 2.0 * atr if signal["direction"] == "long"
            else last_price + 2.0 * atr
        )

        pos = PositionState(
            inst_id=inst_id,
            side=signal["direction"],
            qty=_safe_float(qty),
            entry_price=_safe_float(last_price),
            stop_price=_safe_float(stop_price),
            atr=_safe_float(atr),
            units=1,
            opened_at=format_clock(datetime.now()),
            pnl=0.0,
            pnl_pct=0.0,
        )

        with self._lock:
            self.positions[inst_id] = pos
            self._save_state()

        self._log(
            f"Открыта {signal['direction']} позиция {inst_id}, "
            f"qty={qty:.6f}, ATR={atr:.6f}, stop={stop_price:.6f}"
        )
        return True

    def _manage_open_position(self, inst_id: str, timeframe: str) -> None:
        pos = self.positions.get(inst_id)
        if not pos:
            return

        candles = self._get_candles(inst_id, timeframe, 60)
        if len(candles) < 25:
            return

        stats = self._build_market_stats(candles)
        last_price = candles[-1]["close"]
        atr = stats["atr_abs"]

        pnl = (
            (last_price - pos.entry_price) * pos.qty
            if pos.side == "long"
            else (pos.entry_price - last_price) * pos.qty
        )
        pnl_pct = (
            ((last_price - pos.entry_price) / pos.entry_price) * 100.0
            if pos.side == "long"
            else ((pos.entry_price - last_price) / pos.entry_price) * 100.0
        )

        pos.pnl = pnl
        pos.pnl_pct = pnl_pct
        pos.atr = atr if atr > 0 else pos.atr

        # Трейлинг-стоп по Turtle
        if pos.side == "long":
            new_stop = max(pos.stop_price, last_price - 2.0 * pos.atr)
            pos.stop_price = new_stop
            should_close = last_price <= pos.stop_price
        else:
            new_stop = min(pos.stop_price, last_price + 2.0 * pos.atr)
            pos.stop_price = new_stop
            should_close = last_price >= pos.stop_price

        if should_close:
            self._close_position(inst_id, last_price, "stop")

    def _close_position(self, inst_id: str, exit_price: float, reason: str) -> bool:
        pos = self.positions.get(inst_id)
        if not pos:
            return False

        side = "sell" if pos.side == "long" else "buy"
        pos_side = "long" if pos.side == "long" else "short"

        try:
            # Сначала пробуем штатное закрытие, если оно есть
            try:
                response = _call_first(
                    self.gateway,
                    ["close_position", "close_positions"],
                    inst_id,
                    pos_side,
                )
            except Exception:
                response = _call_first(
                    self.gateway,
                    ["place_market_order", "create_market_order", "market_order"],
                    inst_id,
                    side,
                    pos_side,
                    self._format_size(inst_id, pos.qty),
                    True,
                )
        except Exception as e:
            self._log(f"{inst_id}: ошибка закрытия ордера: {e}")
            return False

        if not self._order_success(response):
            self._log(f"{inst_id}: биржа отклонила закрытие: {response}")
            return False

        pnl = (
            (exit_price - pos.entry_price) * pos.qty
            if pos.side == "long"
            else (pos.entry_price - exit_price) * pos.qty
        )
        pnl_pct = (
            ((exit_price - pos.entry_price) / pos.entry_price) * 100.0
            if pos.side == "long"
            else ((pos.entry_price - exit_price) / pos.entry_price) * 100.0
        )

        closed = ClosedTrade(
            inst_id=pos.inst_id,
            side=pos.side,
            qty=pos.qty,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_time=pos.opened_at,
            exit_time=format_clock(datetime.now()),
            reason=reason,
            duration_sec=0,
            units=pos.units,
        )

        with self._lock:
            self.closed_trades.append(closed)
            self.positions.pop(inst_id, None)
            self._save_state()

        try:
            self.trade_logger.log_closed_trade(closed)
        except Exception:
            pass

        self._log(
            f"Закрыта {pos.side} позиция {inst_id}, "
            f"exit={exit_price:.6f}, pnl={pnl:.6f} ({pnl_pct:.2f}%), reason={reason}"
        )
        return True

    # --------------------------- calculations -----------------------------

    def _build_market_stats(self, candles: List[Dict[str, float]]) -> Dict[str, float]:
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        opens = [c["open"] for c in candles]

        atr_period = min(_safe_int(getattr(self.config, "atr_period", 20), 20), len(candles) - 1)
        trs = []
        for i in range(1, len(candles)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 1]
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            trs.append(tr)

        atr_abs = sum(trs[-atr_period:]) / max(1, atr_period)
        last_close = closes[-1] if closes else 0.0
        atr_pct = (atr_abs / last_close * 100.0) if last_close > 0 else 0.0

        lookback = min(20, len(candles))
        hh = max(highs[-lookback:])
        ll = min(lows[-lookback:])
        range_pct = ((hh - ll) / ll * 100.0) if ll > 0 else 0.0

        bodies = []
        flips = 0
        prev_dir = 0
        for o, c, h, l in zip(opens[-lookback:], closes[-lookback:], highs[-lookback:], lows[-lookback:]):
            candle_range = max(1e-12, h - l)
            body = abs(c - o) / candle_range
            bodies.append(body)

            cur_dir = 1 if c > o else (-1 if c < o else 0)
            if prev_dir != 0 and cur_dir != 0 and cur_dir != prev_dir:
                flips += 1
            if cur_dir != 0:
                prev_dir = cur_dir

        body_ratio = sum(bodies) / max(1, len(bodies))
        flip_ratio = flips / max(1, lookback - 1)

        path = 0.0
        for i in range(1, lookback):
            path += abs(closes[-lookback + i] - closes[-lookback + i - 1])

        displacement = abs(closes[-1] - closes[-lookback])
        efficiency = displacement / path if path > 0 else 0.0

        return {
            "atr_abs": atr_abs,
            "atr_pct": atr_pct,
            "range_pct": range_pct,
            "body_ratio": body_ratio,
            "eff": efficiency,
            "flip": flip_ratio,
        }

    def _is_flat_market(self, stats: Dict[str, float]) -> bool:
        # Специально ослабленный фильтр
        bad = 0

        if stats["range_pct"] < 1.5:
            bad += 1
        if stats["atr_pct"] < 0.25:
            bad += 1
        if stats["body_ratio"] < 0.18:
            bad += 1
        if stats["eff"] < 0.05:
            bad += 1
        if stats["flip"] > 0.75:
            bad += 1

        return bad >= 4

    def _calculate_order_size(self, inst_id: str, price: float, atr: float) -> float:
        balance = self._get_available_balance()
        risk_fraction = _safe_float(getattr(self.config, "risk_per_trade", 0.01), 0.01)
        max_notional_fraction = _safe_float(getattr(self.config, "max_position_fraction", 0.02), 0.02)

        balance = max(balance, 0.0)
        risk_amount = balance * risk_fraction
        stop_distance = max(atr * 2.0, price * 0.0025)

        qty_by_risk = risk_amount / stop_distance if stop_distance > 0 else 0.0
        qty_by_cap = (balance * max_notional_fraction) / price if price > 0 else 0.0

        qty = min(qty_by_risk, qty_by_cap)
        return max(0.0, qty)

    # --------------------------- exchange layer ---------------------------

    def _get_instruments(self) -> List[str]:
        raw = _call_first(
            self.gateway,
            ["get_swap_instruments", "list_swap_instruments", "get_instruments", "list_instruments"],
        )

        items: List[str] = []
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str):
                    items.append(x)
                elif isinstance(x, dict):
                    inst_id = x.get("instId") or x.get("inst_id") or x.get("symbol")
                    if inst_id:
                        items.append(str(inst_id))

        hidden = set(getattr(self.config, "hidden_instruments", []) or [])
        allowed_quote = _safe_str(getattr(self.config, "quote_ccy", "USDT"), "USDT").upper()

        filtered = []
        for inst_id in items:
            if inst_id in hidden:
                continue
            if allowed_quote and f"-{allowed_quote}-SWAP" not in inst_id.upper():
                continue
            filtered.append(inst_id)

        return filtered

    def _get_candles(self, inst_id: str, timeframe: str, limit: int) -> List[Dict[str, float]]:
        raw = _call_first(
            self.gateway,
            ["get_candles", "fetch_candles", "candles"],
            inst_id,
            timeframe,
            limit,
        )

        out: List[Dict[str, float]] = []

        if isinstance(raw, list):
            for row in raw:
                if isinstance(row, dict):
                    out.append(
                        {
                            "open": _safe_float(row.get("open") or row.get("o")),
                            "high": _safe_float(row.get("high") or row.get("h")),
                            "low": _safe_float(row.get("low") or row.get("l")),
                            "close": _safe_float(row.get("close") or row.get("c")),
                            "volume": _safe_float(row.get("volume") or row.get("vol")),
                        }
                    )
                elif isinstance(row, (list, tuple)) and len(row) >= 5:
                    # [ts, o, h, l, c, ...]
                    out.append(
                        {
                            "open": _safe_float(row[1]),
                            "high": _safe_float(row[2]),
                            "low": _safe_float(row[3]),
                            "close": _safe_float(row[4]),
                            "volume": _safe_float(row[5]) if len(row) > 5 else 0.0,
                        }
                    )

        return [x for x in out if x["close"] > 0]

    def _get_available_balance(self) -> float:
        try:
            raw = _call_first(
                self.gateway,
                ["get_available_balance", "fetch_available_balance", "get_balance", "fetch_balance"],
            )
        except Exception:
            return max(self.equity_estimate, 0.0)

        if isinstance(raw, (int, float, str)):
            return _safe_float(raw)

        if isinstance(raw, dict):
            for key in ["availBal", "available", "balance", "eq", "cashBal"]:
                if key in raw:
                    return _safe_float(raw.get(key))

        return 0.0

    def _sync_remote_positions(self) -> None:
        try:
            raw = _call_first(
                self.gateway,
                ["get_positions", "fetch_positions", "list_positions"],
            )
        except Exception:
            return

        if not isinstance(raw, list):
            return

        equity = 0.0
        used = 0.0
        remote_map: Dict[str, PositionState] = {}

        for row in raw:
            if not isinstance(row, dict):
                continue

            inst_id = _safe_str(row.get("instId") or row.get("inst_id"))
            if not inst_id:
                continue

            qty = abs(_safe_float(row.get("pos") or row.get("qty") or row.get("sz")))
            if qty <= 0:
                continue

            side = _safe_str(row.get("posSide") or row.get("side") or row.get("direction")).lower()
            if side in ("buy", "long"):
                side = "long"
            elif side in ("sell", "short"):
                side = "short"
            else:
                # net mode fallback
                net_pos = _safe_float(row.get("pos") or row.get("qty") or row.get("sz"))
                side = "long" if net_pos >= 0 else "short"

            entry_price = _safe_float(row.get("avgPx") or row.get("entryPrice") or row.get("avg_price"))
            mark_price = _safe_float(row.get("markPx") or row.get("mark_price") or row.get("last"))
            pnl = _safe_float(row.get("upl") or row.get("pnl") or row.get("unrealizedPnl"))
            pnl_pct = _safe_float(row.get("uplRatio") or row.get("pnlPct") or row.get("upl_ratio")) * (
                100.0 if abs(_safe_float(row.get("uplRatio") or row.get("pnlPct") or row.get("upl_ratio"))) <= 1.0 else 1.0
            )

            margin = _safe_float(row.get("margin") or row.get("imr") or row.get("usedMargin"))
            used += margin

            remote_map[inst_id] = PositionState(
                inst_id=inst_id,
                side=side,
                qty=qty,
                entry_price=entry_price,
                stop_price=self.positions.get(inst_id).stop_price if inst_id in self.positions else 0.0,
                atr=self.positions.get(inst_id).atr if inst_id in self.positions else 0.0,
                units=self.positions.get(inst_id).units if inst_id in self.positions else 1,
                opened_at=self.positions.get(inst_id).opened_at if inst_id in self.positions else "",
                pnl=pnl,
                pnl_pct=pnl_pct,
            )

        with self._lock:
            for inst_id, remote_pos in remote_map.items():
                if inst_id in self.positions:
                    remote_pos.stop_price = self.positions[inst_id].stop_price
                    remote_pos.atr = self.positions[inst_id].atr
                    remote_pos.units = self.positions[inst_id].units
                    remote_pos.opened_at = self.positions[inst_id].opened_at or remote_pos.opened_at
            self.positions = remote_map

        self.equity_estimate = equity
        self.used_margin_estimate = used

    def _format_size(self, inst_id: str, qty: float) -> str:
        try:
            result = _call_first(self.gateway, ["format_size", "_format_sz"], inst_id, qty)
            return str(result)
        except Exception:
            if qty >= 100:
                return f"{qty:.0f}"
            if qty >= 1:
                return f"{qty:.4f}".rstrip("0").rstrip(".")
            return f"{qty:.6f}".rstrip("0").rstrip(".")

    def _order_success(self, response: Any) -> bool:
        if response is None:
            return False
        if isinstance(response, dict):
            code = _safe_str(response.get("code"), "")
            if code in ("0", ""):
                return True
            data = response.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    return _safe_str(first.get("sCode"), "0") in ("0", "")
        return False

    # ------------------------------ snapshot ------------------------------

    def _update_snapshot(self) -> None:
        self.last_snapshot_at = _now_ts()
        try:
            total_pnl = sum(_safe_float(p.pnl) for p in self.positions.values())
            self.stats_logger.log_engine_stats(
                timestamp=format_clock(datetime.now()),
                open_positions=len(self.positions),
                closed_trades=len(self.closed_trades),
                used_margin=self.used_margin_estimate,
                pnl=total_pnl,
                timeframe=_safe_str(getattr(self.config, "timeframe", "1m")),
            )
        except Exception:
            pass

        self._save_state()

    # ------------------------------- state --------------------------------

    def _save_state(self) -> None:
        try:
            payload = {
                "positions": [asdict(p) for p in self.positions.values()],
                "closed_trades": [asdict(t) for t in self.closed_trades[-1000:]],
                "last_snapshot_at": self.last_snapshot_at,
                "last_cycle_at": self.last_cycle_at,
            }
            Path(STATE_FILE).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_state(self) -> None:
        try:
            path = Path(STATE_FILE)
            if not path.exists():
                return
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.positions = {}
            for row in payload.get("positions", []):
                try:
                    pos = PositionState(**row)
                    self.positions[pos.inst_id] = pos
                except Exception:
                    continue

            self.closed_trades = []
            for row in payload.get("closed_trades", []):
                try:
                    self.closed_trades.append(ClosedTrade(**row))
                except Exception:
                    continue

            self.last_snapshot_at = _safe_float(payload.get("last_snapshot_at"))
            self.last_cycle_at = _safe_float(payload.get("last_cycle_at"))
        except Exception:
            pass

    # ------------------------------- logging ------------------------------

    def _log(self, message: str) -> None:
        self.last_engine_message = message
        if self.log_callback:
            self.log_callback(message)