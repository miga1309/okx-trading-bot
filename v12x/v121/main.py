# === CHANGELOG HEADER ===
# Version: v123
# Date: 2026-03-31
# Changes: based on v121_1; disabled GUI animation timers to cut idle CPU load, slowed GUI snapshot defaults, kept scanner cadence improvements, hardened full-update packaging path, and aligned runtime version metadata for clean Telegram full update.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v123")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v123", entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
