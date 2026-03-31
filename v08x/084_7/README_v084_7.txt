OKX Turtle Bot v084_7

Основа:
- рабочая ветка v084_6

Что изменено:
- добавлена foundation-актуализация Trading Desk по sync-полям позиции
- в таблицу открытых позиций добавлена колонка Sync:
  - SYNC_OK
  - CLOSE_PENDING
  - STOP_MISSING
  - SYNC_DRIFT
- в экспорт добавлены:
  - position_reconcile_history.csv
  - sync_drift_events.csv
- сохранены:
  - trade_analysis.csv
  - market_analysis.csv

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
