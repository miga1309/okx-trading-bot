OKX Turtle Bot v085_2

Основа:
- рабочая ветка v085_1

Что изменено:
- добавлен sync_position_manager.py
- sync-позиции теперь проходят bootstrap-восстановление Turtle-context:
  - system_name
  - entry/exit periods
  - trade_id
  - stop_price / initial_stop_price
  - next_pyramid_price
  - stop_state / position_health_state
- добавлен fallback popup для sync-позиций, если entry_context_file отсутствует
- добавлен market_quality.py
- в liquidity check добавлен sparse candle filter:
  - 10/20 слабых свечей -> блок входа
  - 27/55 слабых свечей -> блок входа
- в экспорт добавлены:
  - market_quality_analysis.csv
  - sync_bootstrap_log.csv

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
