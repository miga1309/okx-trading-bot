# v108

- Stage 1 of modular architecture transition built on top of v107 runtime.
- Added thin entry points `main.py` and `main_v108.py`; heavy startup moved into `bootstrap.py` and `app/application.py`.
- Added `app` layer (`application`, `app_context`, `service_registry`, `event_bus`).
- Added infrastructure layers for logging, storage, exchange wrappers, and session control scaffolding.
- Added routed per-engine text logs and per-engine error logs, plus `system_events.log` and `critical_errors.log`.
- Preserved root-relative runtime expectations for `.env` and `telegram_worker.exe`.
- Removed release `__pycache__` and kept legacy v107 monolith as runtime core for safe Stage 1 migration.

# v107

- Fixed a critical reconciliation bug where positions missing from exchange sync could disappear from runtime-state without being registered in Closed Trades.
- Added staged missing-on-exchange confirmation with explicit logging before forced close finalization.
- Unified close finalization so direct close flow and sync-confirmed close use the same registration path.
- Added close registration diagnostics to position journal and engine stats.
- Downgraded transient market-data socket noise such as WinError 10035 to temporary warnings in the market-data worker.
- Updated release entry point to main_v107.py.
