# === CHANGELOG HEADER ===
# Version: v114
# Date: 2026-03-27
# Changes: fixed remote full-update to unpack uploaded zip packages into updates/full payload, cleaned processed update artifacts after apply, hardened stop-engine against false 51003 relink success and stop regressions, and reduced repeated absent-position stop restore loops.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v114")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v114', entry_module='main_v114')
    app.run()


if __name__ == '__main__':
    main()
