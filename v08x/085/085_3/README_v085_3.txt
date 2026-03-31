v085_3 stability patch

Run file: main_v085_3.py

Key changes:
- fixed displayed/exported version string to v085_3
- added sync bootstrap guard to reduce repeated SYNC_BOOTSTRAP noise
- added exchange stop dedup via pending algo lookup
- added cancel-timeout protection so stop replacement waits for exchange confirmation
- strengthened execution-risk tracking with health statuses NORMAL/WATCHLIST/QUARANTINE

Notes:
- UI layout module remains ui_layout_v085_2.py
- supporting modules market_quality.py and main_v085_3.py are updated in this package
