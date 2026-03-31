# === CHANGELOG HEADER ===
# Version: v116_1
# Date: 2026-03-29
# Changes: fixed Telegram proactive notifications by correcting runtime root path resolution for engine and worker queue/log/runtime folders, kept unified leverage 5x, and preserved the worker startup ping.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v116")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v116", entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
