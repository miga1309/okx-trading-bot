# === CHANGELOG HEADER ===
# Version: v108
# Date: 2026-03-25
# Changes: stage 1 modular architecture release entry point; startup moved to bootstrap/application and legacy runtime is wrapped safely for future extraction.
# === END CHANGELOG HEADER ===

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v108", entry_module="main_v108")
    app.run()


if __name__ == "__main__":
    main()
