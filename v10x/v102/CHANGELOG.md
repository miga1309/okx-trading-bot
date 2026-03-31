# v102 stop-engine cleanup

Date: 2026-03-24

Changes:
- Fixed broken stop_engine class structure; stop methods are now real StopEngine methods instead of nested/unreachable defs.
- Moved stop update/confirm/manage cycle into stop_engine and left thin wrappers in main_v102.py for compatibility.
- Fixed accidental stop cancellation inside try_pyramid.
- Added post-close stop cancellation attempt after successful close.

# v102

Date: 2026-03-23

Changes:
- Fixed GOOD deals review persistence so tags/comments survive popup reopen and table refresh.
- Added immediate snapshot refresh after position open and add-unit, improving Trading Desk update speed.
- Reworked runtime error counting to ignore transient network noise and non-critical warnings.
- Kept single launch entry file: main_v102.py.
