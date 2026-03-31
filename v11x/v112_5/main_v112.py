# === CHANGELOG HEADER ===
# Version: v112
# Date: 2026-03-26
# Changes: rebuilt Telegram remote control release on top of stable v111_6 base; fixed single-worker bridge wiring, added remote bridge cli path propagation, and corrected status/start/stop/reset/analysis command routing.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v112")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v112', entry_module='main_v112')
    app.run()


if __name__ == '__main__':
    main()
