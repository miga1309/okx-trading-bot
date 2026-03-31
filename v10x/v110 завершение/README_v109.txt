OKX Turtle Bot v109

Stage 2 architectural release.

What changed:
- Added runtime engines for positions, execution, stops, reconcile, balance, and health.
- Bound runtime services through bootstrap/app context.
- Kept .env and telegram_worker.exe expectations in the project root.
- Preserved legacy trading/runtime logic while moving ownership boundaries into separate engine modules.

Run:
python main_v109.py

Alternative:
python main.py
