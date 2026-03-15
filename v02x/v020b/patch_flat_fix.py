"""
PATCH: Turtle Bot Anti-Flat Filter
создаёт новую версию main_v0.20d_flatfix.py
"""

import re
from pathlib import Path

SOURCE_FILE = "main_v0.20b.py"
TARGET_FILE = "main_v0.20d_flatfix.py"


ANTI_FLAT_CODE = '''

# ===============================
# ANTI FLAT MARKET FILTER
# ===============================

def is_flat_market(candles, atr):
    """
    Фильтр флэта.
    Возвращает True если рынок слишком ровный.
    """

    if len(candles) < 20:
        return True

    highs = [c["high"] for c in candles[-20:]]
    lows = [c["low"] for c in candles[-20:]]

    closes = [c["close"] for c in candles[-20:]]

    channel = max(highs) - min(lows)

    if atr == 0:
        return True

    # канал слишком узкий
    if channel < atr * 1.8:
        return True

    # слишком много одинаковых закрытий
    unique_closes = len(set(round(x, 6) for x in closes))
    if unique_closes < 6:
        return True

    # проверка "пилы"
    direction_changes = 0
    for i in range(1, len(closes)):
        if (closes[i] - closes[i-1]) * (closes[i-1] - closes[i-2] if i>1 else 0) < 0:
            direction_changes += 1

    if direction_changes > 12:
        return True

    # маленькие тела свечей
    bodies = []
    for c in candles[-20:]:
        bodies.append(abs(c["close"] - c["open"]))

    avg_body = sum(bodies) / len(bodies)

    if avg_body < atr * 0.25:
        return True

    return False


# ===============================
# BREAKOUT CONFIRMATION
# ===============================

def breakout_confirmed(last_candle, level, atr, direction):
    """
    Подтверждение пробоя.
    """

    close = last_candle["close"]
    high = last_candle["high"]
    low = last_candle["low"]
    open_ = last_candle["open"]

    body = abs(close - open_)
    candle_range = high - low

    if candle_range == 0:
        return False

    body_ratio = body / candle_range

    # свеча должна быть импульсной
    if body < atr * 0.6:
        return False

    # тело должно быть большим
    if body_ratio < 0.55:
        return False

    if direction == "long":

        # закрытие выше уровня
        if close < level + atr * 0.15:
            return False

        # закрытие возле high
        if (high - close) > candle_range * 0.35:
            return False

    else:

        if close > level - atr * 0.15:
            return False

        if (close - low) > candle_range * 0.35:
            return False

    return True

'''


def patch_file():

    src = Path(SOURCE_FILE)

    if not src.exists():
        print("Файл не найден:", SOURCE_FILE)
        return

    code = src.read_text(encoding="utf-8")

    if "ANTI FLAT MARKET FILTER" in code:
        print("Патч уже установлен")
        return

    # вставляем перед main()
    code = code.replace(
        "def main(",
        ANTI_FLAT_CODE + "\n\ndef main("
    )

    Path(TARGET_FILE).write_text(code, encoding="utf-8")

    print("Готово.")
    print("Создан файл:", TARGET_FILE)


if __name__ == "__main__":
    patch_file()