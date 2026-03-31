# v124 — 2026-03-31
- built from v123 as a full-update release for Telegram
- aligned runtime version propagation to v124 across entry/runtime/export layers
- added external watchdog process to record abnormal hard process death when the main app cannot write its own crash log
- added GUI-side abnormal worker-finish recording to watchdog events
- strengthened WS-first position syncing by preferring private WS position snapshots when healthy and making sync-close thresholds more conservative under healthy WS

# v123 — 2026-03-31
- built from v121_1 as a clean full-update base for Telegram remote update
- aligned runtime version metadata and startup version strings to v123
- disabled decorative GUI animation timers to reduce long-session CPU load and idle churn
- increased default GUI snapshot cadence to reduce refresh pressure without changing trading logic
- kept scanner cadence/state compatibility intact for continuing existing open positions after update

# v121_1 — 2026-03-30
- Scanner tempo fix: chunked queue now advances every entry scan cycle instead of idling toward hourly throughput.
- Increased default scanner chunk size from 1 to 3 and added target cycle tuning for production-scale universes.
- Preserves existing open positions/state model; no changes to reconcile/base_unit logic.

# v121 — 2026-03-30
- scanner cadence reworked toward hourly queue processing with pause/resume safety and reduced forced refresh churn
- stop/recovery loops hardened with retry backoff to reduce repeated stop-failure storms and CPU pressure
- sync finalize threshold made more conservative to reduce false sync-close confirmations
- Stop Bot cleanup strengthened to release heavy GUI/scanner runtime load closer to Reset behavior
- remote bridge state/result writes made more resilient on Windows with atomic write retries

# Changelog

## v120_2 - 2026-03-29
- tightened the candle-only market scanner against ultra-flat PASS leaks by adding hard flat-dead detection and a PASS vitality gate
- added flat-run metrics so long shelf-like markets with micro-bodies and repeated closes are blocked as DEAD instead of slipping into PASS
- preserved the new scanner architecture, GUI mappings, and candle-only class model while recalibrating DEAD / SPIKE_DEAD / PASS boundaries

## v120_1 - 2026-03-29
- replaced the legacy market scanner with a new candle-only scanner working on the user-selected timeframe
- scanner now analyzes the last 24 closed candles, classifies markets into DEAD / SPIKE_DEAD / SAW / PASS, and keeps PASS in the GUI instead of Good Trades
- removed legacy scanner dependencies on trades, order book, spread/depth and old ripping/good logic from scanner runtime and GUI mappings
- updated scanner summary metrics, popup labels, review tables, and analytics/export hooks to the new classes
- aligned scanner runtime defaults for hourly rescans with resumable queue progress and safer status TTL handling


## v119 - 2026-03-29
- Stabilization pass from v118 base.
- Hardened live-position usage in Trading Desk popup and manual add preview.
- Reduced duplicate candle work and shortened stop-path sleeps.
- Softened absent-position / PENDING_RECHECK finalize path to reduce false closes.
- Removed remaining GUI-side UI mode / telegram control refresh dependencies.

# Changelog

## v118 - 2026-03-29
- fully removed remaining UI-mode runtime logic and reduced Telegram header control logic to status-file updates only
- hardened manual add >4 units preview to prefer live registry data and only fall back to selected row/snapshot without crashing on missing snapshot state
- reused preloaded position candles inside stop management and shortened legacy sleeps after diagnostic/recovery/stop-move paths to speed up the open-position cycle
- reduced stop-health churn during entry recovery and delayed absent-position sync confirmations slightly to avoid premature close cascades

## v117 - 2026-03-29
- unified runtime leverage on 5x and kept exchange-side leverage setup path
- refreshed Trading Desk popup to prefer live registry/snapshot data and live candles on every open
- repaired manual add >4 units preview path to read live position registry instead of stale snapshot-only state
- removed UI mode / TG header controls / clear ban-list button from GUI and removed duplicate Balance Hub summary card
- kept single visible log tab (System Log), fixed uptime chip refresh, and softened immediate post-entry sync close logic with entry recovery grace

## v116_1 - 2026-03-29
- fixed the real Telegram auto-notify bug: engine/runtime paths now resolve from the version root, so proactive messages land in the same runtime\telegram_queue watched by the worker
- corrected root-based runtime/log/status/pid path resolution for script mode
- preserved unified leverage 5x from v116

## v116 — 2026-03-29
- fixed Telegram proactive notifications: the trading engine now writes to the same runtime telegram_queue watched by the worker, so start/stop/open/close/error alerts reach Telegram without a manual command
- added a worker startup Telegram ping right after successful worker launch from GUI
- unified runtime leverage default to 5x in BotConfig and launch config

## v115 — 2026-03-29
- added a dedicated GUI chip for the open-position minute cycle status and last duration
- переведено сопровождение открытых позиций на единый последовательный UTC-минутный цикл
- во время цикла сопровождения market scanner ставится на мягкую паузу и после цикла автоматически продолжает работу
- добавлено обновление popup snapshot по закрытой свече и после событий позиции
- в GUI выведен статус цикла позиций: прогресс, длительность и время последнего завершения

# v114_1 — 2026-03-28
- Stop Engine: исправлен опасный no-op/lock сценарий, при котором стоп мог считаться «уже выровненным» только по цене и не обновляться на полный текущий объём после добора юнита.
- Stop Engine: для partial coverage добавлен явный bypass no-op и cooldown-lock, чтобы full-cover replace не откладывался из-за совпадения stop price.
- Sync/Reconcile: подтверждённое отсутствие позиции на бирже теперь быстрее финализируется как закрытие через sync без лишнего ожидания второго missing-цикла.
- Close reason: улучшена причина sync-close после подтверждённого отсутствия позиции на бирже, чтобы в анализах было видно exchange-confirmed absence.
- Pyramid/Manual add: при увеличении позиции сохраняется прежний stop-covered qty для явной диагностики partial coverage и немедленного full-cover refresh.

## v114 — 2026-03-27
- Исправлен remote full update: загруженный через Telegram `.zip` теперь распаковывается в staging-папку `updates/full/payload`, а `/update_full` применяет именно содержимое архива, а не сам zip как один файл.
- После успешного full update продолжается очистка processed update-артефактов, чтобы старые пакеты не смешивались со следующим rollout.
- Stop Engine: ошибка OKX `51003` больше не считается успешным `relink`; вместо ложного успеха запускается force-replace биржевого стопа.
- Stop Engine: запрещено ухудшать защитный стоп при переходах режима и recovery; если новый расчёт слабее текущего защитного уровня, сохраняется более жёсткий стоп.
- Stop Engine: убрано ложное признание существующего stop-order как признака живой позиции при confirm-ветке absent-position, чтобы не гонять лишние `51023 Position doesn't exist` повторы.

## v113 — 2026-03-26
- Исправлен remote full-update inbox: перед сохранением нового Telegram zip теперь очищается `updates/full/payload`, чтобы старые архивы не накапливались и не попадали в следующий rollout.
- После успешного `/update_full` агент теперь удаляет обработанные full-update артефакты (`updates/full/payload/*` и `updates/full/manifest.json`).
- В результат `/update_full` добавлен список очищенных update-артефактов, а в текст ответа — счётчик удалённых архивов.

## v112_5 — 2026-03-26
- Реализованы реальные команды `/update_component <name>` и `/update_full` вместо заглушек.
- Добавлены manifest-based обновления из `updates/components/...` и `updates/full/...`.
- Перед обновлением теперь создаётся `pre_update` backup, после обновления — `post_update` backup.
- При ошибке обновления выполняется rollback из backup и возвращается результат в Telegram.
- Для full update добавлено планирование перезапуска приложения после применения файлов.
- Обновлён `build_telegram_remote_exe.bat`: `telegram_remote.exe` теперь собирается сразу в корень проекта.

# v112_3
- Fixed telegram_remote frozen path resolution: in EXE mode paths now resolve from project root instead of PyInstaller _internal temp directory.
- Added --project-root CLI support for telegram_remote.exe so split tunneling can target a single stable EXE path outside the bot folder.
- main_v107 now launches telegram worker with explicit --project-root and --remote-bridge-dir arguments.
- build_telegram_remote_exe.bat updated with single-file EXE instructions.

# v112 — 2026-03-26
- Rebuilt Telegram remote control on top of the stable v111_6 base.
- Fixed single telegram worker bridge path propagation and added --remote-bridge-dir CLI support.
- Corrected /status to read both live remote state and telegram status fallback.
- Corrected /start_bot, /stop_bot, /reset_test, /analysis routing through in-app remote controller.
- Left update commands as safe placeholders with backup notes for later patch stages.

- v111_6 (2026-03-26): fixed exchange stop full-coverage handling so attached/old partial stops are rebuilt to full position size after adds, invalidated stale coverage on qty changes/reconcile, and stopped treating inherited partial algos as valid full-position protection.
# Changelog

## v118 - 2026-03-29
- fully removed remaining UI-mode runtime logic and reduced Telegram header control logic to status-file updates only
- hardened manual add >4 units preview to prefer live registry data and only fall back to selected row/snapshot without crashing on missing snapshot state
- reused preloaded position candles inside stop management and shortened legacy sleeps after diagnostic/recovery/stop-move paths to speed up the open-position cycle
- reduced stop-health churn during entry recovery and delayed absent-position sync confirmations slightly to avoid premature close cascades

## v111_1 — 2026-03-26
- Hotfix for same-request bootstrap-stop entry rejection.
- Removed custom attachAlgoClOrdId from entry attached stops because the exchange was rejecting entry orders with sCode 51000 / "Parameter algoClOrdId error".
- Preserved same-request bootstrap-stop attachment and added a one-time retry path without custom attached stop id if the exchange still rejects the attached stop identifier.

## v111 — 2026-03-25
- Repaired stop lifecycle: BOOTSTRAP -> ATR -> TURTLE.
- Bootstrap-stop is attached in the same order request as position entry and depends on entry system range with 7% buffer.
- Softened initial stop verification and stop-health missing logic to avoid premature panic-closes.
- Added relink/recovery path for missing exchange stop identifiers before amend/replace fallbacks.
- Added working manual add-unit flow above 4 units with Trading Desk button and confirmation dialog.
- Cleaned old wrapper entry files and stale release readmes after the modular transition.

## v110 — 2026-03-25
- Stage 3 modular architecture release.
- Added domain scanner engine and trading engine wrappers.
- Replaced placeholder analysis export engine with a working modular export service.
- Added stage 3 runtime bundle registration for scanner / trading / analysis services.
- Added GUI presenter and dialog proxy layer for legacy MainWindow binding.
- Upgraded exchange facade to stage 3 passthrough.
- Preserved root `.env` and `telegram_worker.exe` expectations.

## v109 — 2026-03-25
- Stage 2 modular architecture release.
- Introduced runtime engine bundle for positions, execution, stops, reconcile, balance and health.

## v108 — 2026-03-25
- Stage 1 modular architecture release.
- Added thin entry points, bootstrap, app/config/infrastructure/session layers and per-engine logging.

## v111_2 - 2026-03-26
- fixed startup state loading for legacy/malformed runtime_state entries with safe filtering and backup creation
- slightly slowed scanner and market-data pacing to reduce transient socket-related fetch issues
- added new entrypoints main_v111_2.py and main.py -> v111_2

- v111_3: fixed same-request/bootstrap stop validation at entry, unified protective-stop normalization for post-entry stop placement/amend, added multi-confirm exchange-absence sync, and added final execution hard-block checks.

- v111_4: fixed entry attached bootstrap-stop re-normalization by using fresh ticker/bid-ask refs right before submit, carrying entry price into attached stop payload, and applying the same fresh normalization to exchange stop place/amend paths.

## v111_5
- Fixed repeated exchange-stop amend loops caused by adopted stops without qty/closeFraction metadata.
- Stopped recursive amend_fallback spam on 51003 by relinking or aborting instead of re-entering recovery endlessly.
- Added dedup for adopted existing stop rows with aligned trigger prices.

## v112_4 — 2026-03-26
- Исправлено раннее ложное подтверждение команд `/start_bot` и `/stop_bot`.
- Remote control теперь ждёт смену состояния через цикл Qt events вместо мгновенной проверки после вызова.
- Усилено определение состояния бота: учитываются worker, engine, `_bot_running` и переходные состояния запуска/остановки.
- Рабочие `/status`, `/reset_test` и `/analysis` сохранены без изменения логики.

## v112_7 — 2026-03-26
- Выпущена полноценная базовая версия 112_7 на основе рабочей 112_6, без patch-only схемы.
- main.py используется как единственный entrypoint текущей версии.
- Версия предназначена как чистая опорная база перед следующим этапом внедрения full update через zip-архив.

- Added a small standalone Telegram Worker Control GUI (`telegram_worker_gui.py` + `build_telegram_worker_gui_exe.bat`) with Start/Stop/Restart, live status, PID, status-file timestamp, and log tail so worker health can be checked without Task Manager.
