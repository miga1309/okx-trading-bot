# === CHANGELOG HEADER ===
# Version: v111_3
# Date: 2026-03-26
# Changes: fixed protective-stop validation for entry and post-entry stop flows, hardened absence/sync confirmation before forced close, and added a final execution hard-block check for blacklist/scanner paths.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v111_3")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v111_3', entry_module='main_v111_3')
    app.run()


if __name__ == '__main__':
    main()
