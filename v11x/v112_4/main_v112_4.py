# === CHANGELOG HEADER ===
# Version: v112_4
# Date: 2026-03-26
# Changes: fixed remote start/stop confirmation timing by waiting through Qt event processing, improved running-state detection during engine transitions, and kept analysis/reset/status behavior from v112_3.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v112_4")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v112_4', entry_module='main_v112_4')
    app.run()


if __name__ == '__main__':
    main()
