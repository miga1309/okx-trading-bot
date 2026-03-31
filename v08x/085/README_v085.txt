OKX Turtle Bot v085

Основа:
- рабочая ветка v084_11

Что входит в v085:
- стабильная база после серии патчей 084_x
- очищенный GUI:
  - без Market Radar
  - без Turtle Signal Center
  - Risk Radar в теле программы
  - без анимированного фона
- Trading Desk с Sync column
- рабочие popup открытых и закрытых сделок
- экспорт глубокого анализа
- foundation под hybrid Turtle stop:
  - Turtle 20 -> exit 10
  - Turtle 55 -> exit 20
  - ATR как стартовая защита
  - развитые позиции помечаются как DONCHIAN_ACTIVE

Файлы анализа:
- trade_analysis.csv
- market_analysis.csv
- position_reconcile_history.csv
- position_sync_status.csv
- sync_drift_events.csv
- trend_capture_analysis.csv
- position_stop_regime.csv

Это release-версия для демо-теста на базе проверенной линии 084_x.

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
