# === CHANGELOG HEADER ===
# Version: v119
# Date: 2026-03-29
# Changes: unified leverage 5x across runtime, refreshed Trading Desk popup with live position/chart payload, repaired manual add >4 units preview path, removed UI-mode/TG controls/clear ban-list from GUI, cleaned duplicate Balance Hub data, fixed uptime header updates, and softened post-entry sync close logic with entry-recovery grace.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v119")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v119", entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
