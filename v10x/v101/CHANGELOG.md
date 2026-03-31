# CHANGELOG

## v101 — 2026-03-23
- Expanded OKX WebSocket runtime with public candles, order-book snapshots, mark price stream, and private algo-order tracking.
- Scanner now uses WS-first liquidity checks and blocks entries on thin book, liquidity holes, stale book, and stale candle state.
- Gateway now prefers WS candles and WS book snapshots before REST fallback.
- Release cleaned up old launcher duplication: package contains only `main_v101.py` as the main entry file.

## v100 — 2026-03-23
- introduced OKX WebSocket manager for public/private channels with health integration and WS-backed snapshots.
- strengthened popup review persistence for good deals.
- expanded gateway/runtime synchronization diagnostics.
