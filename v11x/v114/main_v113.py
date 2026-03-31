# === CHANGELOG HEADER ===
# Version: v113
# Date: 2026-03-26
# Changes: update agent now clears previous Telegram full-update payload before saving a new archive and deletes processed full-update zip artifacts after successful apply, so old uploaded packages do not accumulate and reapply.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v113")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v113', entry_module='main_v113')
    app.run()


if __name__ == '__main__':
    main()
