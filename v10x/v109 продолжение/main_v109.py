# === CHANGELOG HEADER ===
# Version: v109
# Date: 2026-03-25
# Changes: stage 2 modular architecture release entry point; startup still uses legacy GUI/runtime, but runtime services for positions/stops/execution/reconcile/balance/health are now attached as separate engines.
# === END CHANGELOG HEADER ===

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version="v109", entry_module="main_v109")
    app.run()


if __name__ == "__main__":
    main()
