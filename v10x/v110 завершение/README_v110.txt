v110 stage 3 modular architecture release

What changed:
- Added modular scanner/trading/analysis service layer on top of the working v109 core.
- Added GUI presenter/dialog binding layer for the legacy MainWindow.
- Added stage 3 runtime bundle registration so scanner/trading/analysis services bind when TurtleEngine starts.
- Kept .env in the application root.
- Kept telegram_worker.exe in the application root.

Run:
- python main_v110.py
- or python main.py
