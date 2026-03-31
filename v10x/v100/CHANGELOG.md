# v100 - 2026-03-23

- Added OKX WebSocket manager for public/private channels with reconnect, login, resubscribe, and health snapshots.
- Gateway now consumes fresh WS snapshots for account, positions, ticker, and algo-order visibility when available.
- Connectivity guard now includes ws_public/ws_private components, so stale WS blocks new entries during degradation.
- Fixed scanner review persistence for GOOD deals and aligned popup payload/save flow with review records.
- Main runtime promoted to main_v100.py with expanded synchronization diagnostics.
