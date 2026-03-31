OKX Turtle Bot v084_9_1

Основа:
- фикс на базе v084_9

Исправлено:
- возвращены поля open-position snapshot, которые нужны для GUI:
  - system_name
  - entry_time
  - entry_context_file
  - entry_period
- из-за этого снова корректно отображается:
  - столбец 'Система' (Turtle 20 / Turtle 55)
  - popup открытых позиций
- нормализован trade_context_file для Closed Trades popup

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
