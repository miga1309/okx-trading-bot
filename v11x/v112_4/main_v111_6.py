# === CHANGELOG HEADER ===
# Version: v111_6
# Date: 2026-03-26
# Changes: fixed full-position exchange stop coverage after adds, forced full-cover stop rebuilds instead of adopting partial attached stops, and invalidated stale stop coverage on qty changes/reconcile.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v111_6")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v111_6', entry_module='main_v111_6')
    app.run()


if __name__ == '__main__':
    main()
