OKX Turtle Bot v084_10

Основа:
- рабочая ветка v084_9_1_1

Что изменено:
- сохранена рабочая база после фикса popup и Turtle 20/55
- расширен sync-слой Trading Desk:
  - добавлен статус POSITION_GHOST
  - добавлена цветовая индикация ghost-state
- экспорт для глубокого анализа расширен:
  - position_sync_status.csv
  - ghost_positions в summary
- сохранены:
  - trade_analysis.csv
  - market_analysis.csv
  - position_reconcile_history.csv
  - sync_drift_events.csv

Это стабильный patch-release на базе рабочей 084_9_1_1.
Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
