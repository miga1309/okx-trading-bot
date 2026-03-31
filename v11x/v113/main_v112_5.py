# === CHANGELOG HEADER ===
# Version: v112_5
# Date: 2026-03-26
# Changes: enabled real remote update flow for /update_component and /update_full using manifest-based file replacement, pre/post backup archives, rollback on failure, and full-app restart scheduling for full updates.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v112_5")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v112_5', entry_module='main_v112_5')
    app.run()


if __name__ == '__main__':
    main()
