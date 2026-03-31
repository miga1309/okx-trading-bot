# Changelog

## v097_1 — 2026-03-22
- База: стабильная версия v096_5.
- Telegram вынесен в изолированный queue-worker, чтобы его сбои не валили торговый движок.
- Добавлены кнопки TG START / TG STOP и индикатор TG в шапке GUI.
- Очередь Telegram перенесена в runtime/telegram_queue, пути переведены в абсолютные.
- run_telegram_worker.py теперь сам загружает .env.
- Исправлен экспорт анализа: добавлен импорт динамического интервала reconcile.

v096_5
- Fixed exchange stop recovery/verification flow and removed amend/cancel calls without a valid stop id.
- Treats stale/missing stop cancellation as non-fatal and attempts fresh stop placement.
- Softened initial-stop verify failure: retries recovery instead of immediate force-close.
- Fixed avg_px refresh after pyramid when live reconcile returns total position avgPx.
- Improved runtime export fallbacks for position age/sync/runtime fields.
