OKX Turtle Bot v085_1

Основа:
- рабочая ветка v085

Что изменено:
- добавлен отдельный модуль position_reconciler.py
- из main вынесены helper-правила:
  - derive_sync_status
  - turtle_exit_period_from_system
  - determine_hybrid_stop_mode
  - classify_trend_hold_state
  - dynamic sync interval
- в open-position runtime добавлены поля:
  - trend_hold_state
  - reconciler_interval_sec

Экспорт для глубокого анализа усилен:
- position_runtime_regime.csv
- trend_hold_analysis.csv

Summary теперь содержит:
- trend_hold_positions
- avg_retained_r_share

Это patch одновременно в две стороны:
- небольшая архитектурная чистка
- усиление торговой диагностики под удержание трендов

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
