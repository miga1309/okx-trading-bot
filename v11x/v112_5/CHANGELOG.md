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
