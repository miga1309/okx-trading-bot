# v105

Date: 2026-03-24

Changes:
- Cleaned stop lifecycle tails in stop_engine by centralizing existing-stop adoption, amend/place alignment, and absent-position sync handling.
- Reduced repeated retry noise for positions already absent on exchange.
- Added stale cache pruning and richer market-data worker cache diagnostics.
- Added main_v105.py and prepared a clean release package without legacy version entry points.
