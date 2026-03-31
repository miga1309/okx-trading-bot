# === CHANGELOG HEADER ===
# Version: v111
# Date: 2026-03-25
# Changes: stop-engine repair release; bootstrap-stop is now attached in the same request as entry, stop lifecycle upgraded to BOOTSTRAP->ATR->TURTLE, manual add-unit above 4 added to GUI, and legacy wrappers/files cleaned after modular transition.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v111")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v111', entry_module='main_v111')
    app.run()


if __name__ == '__main__':
    main()
