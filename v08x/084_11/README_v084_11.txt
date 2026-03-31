OKX Turtle Bot v084_11

Основа:
- рабочая ветка v084_10

Что изменено:
- добавлена foundation-диагностика под hybrid Turtle stop
- в open-position snapshot добавлены поля:
  - turtle_exit_period
  - hybrid_stop_mode
- в экспорт добавлены:
  - trend_capture_analysis.csv
  - position_stop_regime.csv
- в summary добавлены:
  - avg_realized_r
  - avg_trend_move_r
  - donchian_active_positions

Что это значит:
- для Turtle 20 фиксируется exit-period 10
- для Turtle 55 фиксируется exit-period 20
- ATR трактуется как стартовая защита, а развитые позиции помечаются как DONCHIAN_ACTIVE для глубокого анализа

Важно:
это стабильный foundation patch для перехода к hybrid Turtle stop, без агрессивной перепрошивки ядра сопровождения в слепом режиме.

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
