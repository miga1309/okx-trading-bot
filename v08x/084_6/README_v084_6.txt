OKX Turtle Bot v084_6

Основа:
- рабочая ветка v084_5

Что изменено:
- усилен экспорт для глубокого анализа
- добавлены:
  - trade_analysis.csv
  - market_analysis.csv
- в summary добавлены:
  - avg_trend_capture_ratio
  - avg_exit_efficiency
  - markets_traded
  - high_risk_markets
- сохранена foundation-диагностика:
  - trade_diagnostics.csv
  - early_exit_flag / early_exit_gap_pct
  - unit_add_events / stop_move_events
  - last_stop_move_reason
  - market_risk_score

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
