# === CHANGELOG HEADER ===
# Version: v108
# Date: 2026-03-25
# Changes: stage 1 architecture entry point; delegates startup to bootstrap/application while preserving root .env and telegram_worker.exe layout.
# === END CHANGELOG HEADER ===

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v108", entry_module="main")
    app.run()


if __name__ == "__main__":
    main()
