# v104

- Treated OKX 51088 as an existing exchange TP/SL conflict and adopted/amended the live stop instead of repeatedly placing duplicates.
- Reworked stop verification/health sync to prefer attaching existing live exchange stops before attempting recovery placement.
- Added one-time absent-position synchronization to stop repeated retry spam after the exchange reports no live position.
- Renamed the initial stop lifecycle to initial_atr_stop to match the actual 1-2 unit ATR stop policy.
- Updated app version to v104 and added main_v104.py as a versioned entry file.
