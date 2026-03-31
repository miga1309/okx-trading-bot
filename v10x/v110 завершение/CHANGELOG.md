# Changelog

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
