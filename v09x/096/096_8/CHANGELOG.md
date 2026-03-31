# v096_8 — 2026-03-22

- Fixed Telegram worker launch on Windows from GUI: queue and worker log now use absolute paths inside local runtime folder.
- Telegram queue default moved from logs/telegram_queue to runtime/telegram_queue to avoid permission issues and fragile relative-path resolution.
- Added directory access validation for Telegram queue/log initialization so startup fails early with deterministic path handling.
- GUI now passes explicit queue/log paths to worker process and writes startup path details into bot log for diagnostics.

# v096_7 — 2026-03-22 (re-release)

- Fixed standalone run_telegram_worker.py startup: .env is now loaded inside telegram_notifier worker entrypoint.
- Added Telegram controls to GUI header: TG START / TG STOP buttons plus live TG status chip.
- Header buttons now start/stop the Telegram queue worker and toggle runtime Telegram notifications without changing trading logic.

# v096_7 — 2026-03-22

- Fixed analysis export crash: analysis_exporter now imports dynamic reconciler interval correctly.
- Fixed scanner export append for hourly analysis mode: scanner files are now written safely into hourly export folders instead of trying to open a directory as a zip archive.
- Preserved scanner summary attachment for normal quick/full zip exports.

# v096_6 — 2026-03-22

- Telegram notifications moved to local queue + separate worker process for split-tunneling through VPN.
- Main bot no longer sends directly to Telegram API; it only enqueues messages/photos.
- Added notifications for bot start/stop, connectivity loss/recovery, position open, pyramid add, position close, stop-engine critical events, hourly status and high-risk alert.
- Preserved screenshot sending by copying files into queue attachments before async delivery.
- Kept trading contour untouched; Telegram delivery failures no longer block trading loop.
