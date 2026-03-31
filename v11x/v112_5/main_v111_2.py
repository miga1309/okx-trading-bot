# === CHANGELOG HEADER ===
# Version: v111_2
# Date: 2026-03-26
# Changes: safe legacy-state loading with backup/filtering of malformed records; slightly slowed scanner and market-data pacing to reduce transient socket issues during runtime.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v111_2")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v111_2', entry_module='main_v111_2')
    app.run()


if __name__ == '__main__':
    main()
