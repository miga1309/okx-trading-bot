OKX Turtle Bot v084_5

Основа:
- рабочая ветка v084_4

Что изменено:
- Risk Radar очищен от дублей:
  - убраны POS и UPTIME из тела Risk Radar
  - эти показатели остаются в header
- подготовлена первая foundation-диагностика прибыльности в analysis_exporter:
  - trade_diagnostics.csv
  - early_exit_flag
  - early_exit_gap_pct
  - unit_add_events
  - stop_move_events
  - last_stop_move_reason
  - market_risk_score
- версия и UI binding переведены на v084_5

Что сохранено:
- рабочая логика v084
- popup открытых/закрытых сделок
- экспорт "Сдать анализы"
- биржевые стопы
- все таймфреймы
- 16 позиций
- 4 юнита

Проверка перед выпуском:
- синтаксическая компиляция всех .py модулей
