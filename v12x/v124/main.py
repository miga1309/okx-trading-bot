# === CHANGELOG HEADER ===
# Version: v124
# Date: 2026-03-31
# Changes: rebuilt from v123 as a full-update release; strengthened WS-first position state handling, added external watchdog crash detection, fixed runtime version propagation, and reduced dependence on REST position polling when private WS snapshots are healthy.
# === END CHANGELOG HEADER ===

import os

from app.version import APP_VERSION

os.environ["OKX_TURTLE_RUNTIME_VERSION"] = APP_VERSION

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version=APP_VERSION, entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
