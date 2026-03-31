# === CHANGELOG HEADER ===
# Version: v110
# Date: 2026-03-25
# Changes: stage 3 modular architecture release entry point; startup still uses legacy GUI/runtime, but scanner/trading/analysis services and GUI binding layer are now attached through the modular bootstrap.
# === END CHANGELOG HEADER ===

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v110', entry_module='main_v110')
    app.run()


if __name__ == '__main__':
    main()
