# === CHANGELOG HEADER ===
# Version: v115
# Date: 2026-03-29
# Changes: single-entry main.py retained as the only app entrypoint after modular cleanup; legacy runtime moved under app/legacy_runtime.py and project imports rewired to package modules.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v115")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v115", entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
