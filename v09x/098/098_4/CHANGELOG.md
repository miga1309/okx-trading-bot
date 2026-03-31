# Changelog

## v098 — 2026-03-22
- База: рабочая версия v097_1.
- Telegram worker теперь запускается только как отдельный `telegram_worker.exe`, чтобы VPN можно было привязать к нему, а не к `python.exe`.
- GUI показывает статус `TG: EXE MISS`, если `telegram_worker.exe` ещё не собран или отсутствует рядом с программой.
- Кнопка TG START больше не запускает `python.exe`; торговый контур изолирован от Telegram worker.
- Сохранены абсолютные пути `runtime/telegram_queue`, `logs/telegram_worker.log`, `runtime/telegram_worker.pid`.
- Сохранён фикс экспорта анализа для динамического интервала reconcile.
