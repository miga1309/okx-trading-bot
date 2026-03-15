# patch_v024_1_to_v024_2_ui_cleanup.py
# Создаёт новый файл main_v024_2.py на базе main_v024_1.py
#
# Изменения v024_2:
# - Добавлен changelog в начало файла
# - APP_VERSION: v024_1 -> v024_2
# - Удалена колонка "Средняя цена" из таблицы открытых позиций
# - "Добавлено юнитов" -> "Юнитов" в открытых и закрытых таблицах
# - Удалены поля статистики:
#   * Последнее обновление
#   * Последний цикл движка
#   * Последний snapshot
# - График баланса стал информативнее:
#   * добавлена шкала Y
#   * подписи уровней слева
#   * горизонтальные линии сетки с числами
#
# Использование:
#   python patch_v024_1_to_v024_2_ui_cleanup.py

from pathlib import Path
from datetime import datetime
import sys

SOURCE = Path("main_v024_1.py")
TARGET = Path("main_v024_2.py")


def fail(msg: str) -> None:
    print(f"ОШИБКА: {msg}")
    sys.exit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not SOURCE.exists():
        fail(f"Файл не найден: {SOURCE.resolve()}")

    text = SOURCE.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'APP_VERSION = "v024_1"',
        'APP_VERSION = "v024_2"',
        "app_version",
    )

    old_header = '''# ============================================================
# OKX Turtle Bot
# Version: v024_1
# Date: 2026-03-11
# Based on: main_v024.py
#
# Changelog:
# - Removed "Средняя цена" column from open positions table
# - Renamed "Добавлено юнитов" to "Юнитов" in tables
# - Removed extra statistics fields from GUI
# - Improved balance chart with Y-axis labels and scale
# ============================================================

'''
    new_header = f'''# ============================================================
# OKX Turtle Bot
# Version: v024_2
# Date: {datetime.now().strftime("%Y-%m-%d")}
# Based on: main_v024_1.py
#
# Changelog:
# - Removed extra statistics fields from GUI
# - Kept "Юнитов" naming in tables
# - Improved balance chart with Y-axis labels and scale
# - Created as a new versioned file
# ============================================================

'''
    text = replace_once(text, old_header, new_header, "changelog_header")

    TARGET.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Исходник: {SOURCE.resolve()}")
    print(f"Новый файл: {TARGET.resolve()}")
    print("Новая версия: v024_2")


if __name__ == "__main__":
    main()