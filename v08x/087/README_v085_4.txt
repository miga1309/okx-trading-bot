v085_4 night-test patch

Run file: main_v085_4.py

Main changes:
- version string updated to v085_4
- hard-blocked inherited toxic pairs for the night test: BREV-USDT-SWAP, RAVE-USDT-SWAP, CRO-USDT-SWAP, ADA-USDT-SWAP
- hidden pairs are filtered on state load, exchange sync, visible snapshots, and exports so they stop polluting Trading Desk and analysis
- strengthened 5m layered liquidity guard on top of the existing base liquidity filter
- added extra unstable-orderbook rejection path for thin/disappearing liquidity

Notes:
- blocked pairs are ignored by the bot for this test; existing exchange positions remain on OKX but are not processed by the bot
- UI layout module remains ui_layout_v085_2.py
