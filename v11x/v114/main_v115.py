# === CHANGELOG HEADER ===
# Version: v115
# Date: 2026-03-29
# Changes: switched position management to a single UTC minute cycle, paused market scanner during that cycle, refreshed popup snapshots on closed candles and position events, and exposed position-cycle status in the GUI.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v115")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v115', entry_module='main_v115')
    app.run()


if __name__ == '__main__':
    main()
