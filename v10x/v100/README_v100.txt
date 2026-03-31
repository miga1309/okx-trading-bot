v100

Main file: main_v100.py

Key changes:
- OKX public/private WebSocket manager added with reconnect and health integration
- gateway uses fresh WS snapshots for positions, account, tickers, and algo visibility when available
- connectivity guard now includes ws_public/ws_private degradation
- popup review save fixed for good deals / tags / comments
