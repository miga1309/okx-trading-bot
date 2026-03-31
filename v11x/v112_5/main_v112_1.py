# === CHANGELOG HEADER ===
# Version: v112_1
# Date: 2026-03-26
# Changes: added first remote bridge release for Telegram control: remote command folders, in-app bridge listener, /analysis /start_bot /stop_bot /reset_test command routing, and one-worker Telegram control expansion.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v112_1")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v112_1', entry_module='main_v112_1')
    app.run()


if __name__ == '__main__':
    main()
