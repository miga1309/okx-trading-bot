# v107

- Fixed a critical reconciliation bug where positions missing from exchange sync could disappear from runtime-state without being registered in Closed Trades.
- Added staged missing-on-exchange confirmation with explicit logging before forced close finalization.
- Unified close finalization so direct close flow and sync-confirmed close use the same registration path.
- Added close registration diagnostics to position journal and engine stats.
- Downgraded transient market-data socket noise such as WinError 10035 to temporary warnings in the market-data worker.
- Updated release entry point to main_v107.py.
