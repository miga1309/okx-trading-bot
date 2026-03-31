OKX Turtle Bot v105

Запуск: python main_v105.py

Ключевые изменения версии:
- единый stop_engine очищен от части хвостовой stop-логики и получил общий ensure/adopt/amend контур;
- stop-синхронизация по отсутствующей позиции стала одноразовой и тихой;
- market-data worker чистит stale cache entries и логирует missing/pruned cache;
- релиз собран без старых entry-point файлов прошлых версий.
