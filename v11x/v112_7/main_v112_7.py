# === CHANGELOG HEADER ===
# Version: v112_7
# Date: 2026-03-26
# Changes: full baseline release built from the working v112_6 codebase to serve as the next clean version for further work on full zip-based updates.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v112_7")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v112_7', entry_module='main_v112_7')
    app.run()


if __name__ == '__main__':
    main()
